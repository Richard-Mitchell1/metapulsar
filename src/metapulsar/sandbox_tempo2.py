# sandbox_tempo2.py
"""
Process sandbox for libstempo/tempo2 that keeps each pulsar in its own clean
subprocess. A segfault in tempo2/libstempo only kills the worker, not your kernel.

Usage (drop-in):
    from sandbox_tempo2 import tempopulsar
    psr = tempopulsar(parfile="J1713.par", timfile="J1713.tim", dofit=False)
    r = psr.residuals()

Advanced:
    from sandbox_tempo2 import load_many, Policy
    ok, retried, failed = load_many([("J1713.par","J1713.tim"), ...], policy=Policy())

Environment selection (Apple Silicon + Rosetta etc.):
    psr = tempopulsar(..., env_name="tempo2_intel")       # conda env
    psr = tempopulsar(..., env_name="myvenv")             # venv (~/.venvs/myvenv, etc.)
    psr = tempopulsar(..., env_name="arch")               # system python via Rosetta (arch -x86_64)
    psr = tempopulsar(..., env_name="python:/abs/python") # explicit Python path

You can force Rosetta prefix via env var:
    TEMPO2_SANDBOX_WORKER_ARCH_PREFIX="arch -x86_64"
"""

from __future__ import annotations

import base64
import contextlib
import dataclasses
import json
import os
import pickle
import platform
import select
import shutil
import signal
import subprocess
import sys
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

# ---------------------------- Public Exceptions ---------------------------- #


class Tempo2Error(Exception):
    """Base class for sandbox errors."""


class Tempo2Crashed(Tempo2Error):
    """The worker process crashed or died unexpectedly (likely a segfault)."""


class Tempo2Timeout(Tempo2Error):
    """The worker did not reply in time; it was terminated."""


class Tempo2ProtocolError(Tempo2Error):
    """Malformed RPC request/response or other IPC failure."""


class Tempo2ConstructorFailed(Tempo2Error):
    """Constructor failed even after retries."""


# ------------------------------- Policy knobs ----------------------------- #


@dataclass(frozen=True)
class Policy:
    # Constructor protection
    ctor_retry: int = 2  # number of extra tries after the first
    ctor_backoff: float = 0.75  # seconds between ctor retries
    preload_residuals: bool = True  # call residuals() once after ctor

    # RPC protection
    call_timeout_s: float = 120.0  # per-call timeout (seconds)
    kill_grace_s: float = 2.0  # after timeout, wait before SIGKILL

    # Recycling / hygiene
    max_calls_per_worker: int = 200  # recycle after this many good calls
    max_age_s: float = 20 * 60.0  # recycle after this many seconds
    rss_soft_limit_mb: Optional[int] = None  # if provided, recycle when beaten


# -------------------------- Wire serialization helpers --------------------- #

# We send JSON-RPC 2.0 frames. To avoid JSON-encoding numpy arrays and
# cross-arch issues, params/result travel as base64-encoded cloudpickle blobs.

try:
    import cloudpickle as _cp  # best-effort; falls back to pickle if missing
except Exception:
    _cp = pickle


def _b64_dumps_py(obj: Any) -> str:
    return base64.b64encode(_cp.dumps(obj)).decode("ascii")


def _b64_loads_py(s: str) -> Any:
    return _cp.loads(base64.b64decode(s.encode("ascii")))


def _format_exc_tuple() -> Tuple[str, str, str]:
    et, ev, tb = sys.exc_info()
    name = et.__name__ if et else "Exception"
    return (name, str(ev), "".join(traceback.format_exception(et, ev, tb)))


def _current_rss_mb_portable() -> Optional[int]:
    try:
        if sys.platform.startswith("linux"):
            with open("/proc/self/statm") as f:
                pages = int(f.read().split()[1])
            rss = pages * (os.sysconf("SC_PAGE_SIZE") // 1024 // 1024)
            return rss
    except Exception:
        pass
    try:
        import psutil  # type: ignore

        return int(psutil.Process(os.getpid()).memory_info().rss / (1024 * 1024))
    except Exception:
        return None


# ----------------------------- Worker (stdio) ------------------------------ #


def _worker_stdio_main() -> None:
    """
    Runs inside the worker interpreter (possibly Rosetta x86_64).
    Protocol:
      1) Immediately print a single 'hello' JSON line with environment info.
      2) Then serve JSON-RPC 2.0 requests line-by-line on stdin/stdout.
         Methods: ctor, get, set, call, del, rss, bye
         Each request's 'params_b64' is a pickled dict of parameters.
         Each response uses 'result_b64' for Python results, or 'error'.
    """
    # Step 1: hello handshake
    hello = {
        "hello": {
            "python": sys.version.split()[0],
            "executable": sys.executable,
            "machine": platform.machine(),
            "platform": platform.platform(),
            "has_libstempo": False,
            "tempo2_version": None,
        }
    }
    try:
        try:
            from libstempo import tempopulsar as _lib_tempopulsar  # noqa
            import numpy as _np  # noqa

            hello["hello"]["has_libstempo"] = True
            # best-effort tempo2 version probe
            try:
                from libstempo import tempo2  # type: ignore

                hello["hello"]["tempo2_version"] = getattr(
                    tempo2, "TEMPO2_VERSION", None
                )
            except Exception:
                pass
        except Exception:
            pass
    finally:
        sys.stdout.write(json.dumps(hello) + "\n")
        sys.stdout.flush()

    # If libstempo failed to import at hello, try once more here to return clean errors
    try:
        from libstempo import tempopulsar as _lib_tempopulsar  # noqa
        import numpy as _np  # noqa
    except Exception:
        # Keep serving, but report on first request
        _lib_tempopulsar = None  # type: ignore
        _np = None  # type: ignore

    obj = None

    def _write_response(resp: Dict[str, Any]) -> None:
        sys.stdout.write(json.dumps(resp) + "\n")
        sys.stdout.flush()

    # JSON-RPC loop
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except Exception:
            _write_response(
                {
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {"code": -32700, "message": "parse error"},
                }
            )
            continue

        rid = req.get("id", None)
        method = req.get("method", "")
        params_b64 = req.get("params_b64", None)

        # Decode params dict if present
        params = {}
        if params_b64 is not None:
            try:
                params = _b64_loads_py(params_b64)
                if not isinstance(params, dict):
                    raise TypeError("params_b64 must decode to dict")
            except Exception:
                et, ev, tb = _format_exc_tuple()
                _write_response(
                    {
                        "jsonrpc": "2.0",
                        "id": rid,
                        "error": {
                            "code": -32602,
                            "message": f"invalid params: {ev}",
                            "data": tb,
                        },
                    }
                )
                continue

        # Handle methods
        try:
            if method == "bye":
                _write_response(
                    {"jsonrpc": "2.0", "id": rid, "result_b64": _b64_dumps_py("bye")}
                )
                return

            if method == "rss":
                rss = _current_rss_mb_portable()
                _write_response(
                    {"jsonrpc": "2.0", "id": rid, "result_b64": _b64_dumps_py(rss)}
                )
                continue

            if method == "ctor":
                if _lib_tempopulsar is None:
                    raise ImportError("libstempo not available in worker")
                obj = _lib_tempopulsar(**params["kwargs"])
                if params.get("preload_residuals", True):
                    _ = obj.residuals(updatebats=True, formresiduals=True)
                _write_response(
                    {
                        "jsonrpc": "2.0",
                        "id": rid,
                        "result_b64": _b64_dumps_py("constructed"),
                    }
                )
                continue

            if obj is None:
                raise RuntimeError("object not constructed")

            if method == "get":
                name = params["name"]
                val = getattr(obj, name)
                # copy numpy views to decouple from lib memory
                try:
                    import numpy as _np2  # local alias

                    if hasattr(val, "base") and isinstance(val, _np2.ndarray):
                        val = val.copy()
                except Exception:
                    pass
                _write_response(
                    {"jsonrpc": "2.0", "id": rid, "result_b64": _b64_dumps_py(val)}
                )
                continue

            if method == "set":
                name, value = params["name"], params["value"]
                setattr(obj, name, value)
                _write_response(
                    {"jsonrpc": "2.0", "id": rid, "result_b64": _b64_dumps_py(None)}
                )
                continue

            if method == "call":
                name = params["name"]
                args = tuple(params.get("args", ()))
                kwargs = dict(params.get("kwargs", {}))
                meth = getattr(obj, name)
                out = meth(*args, **kwargs)
                try:
                    import numpy as _np2

                    if hasattr(out, "base") and isinstance(out, _np2.ndarray):
                        out = out.copy()
                except Exception:
                    pass
                _write_response(
                    {"jsonrpc": "2.0", "id": rid, "result_b64": _b64_dumps_py(out)}
                )
                continue

            if method == "del":
                try:
                    del obj
                except Exception:
                    pass
                obj = None
                _write_response(
                    {"jsonrpc": "2.0", "id": rid, "result_b64": _b64_dumps_py(None)}
                )
                continue

            _write_response(
                {
                    "jsonrpc": "2.0",
                    "id": rid,
                    "error": {"code": -32601, "message": f"method not found: {method}"},
                }
            )
        except Exception:
            et, ev, tb = _format_exc_tuple()
            _write_response(
                {
                    "jsonrpc": "2.0",
                    "id": rid,
                    "error": {"code": -32000, "message": f"{et}: {ev}", "data": tb},
                }
            )


# ------------------------------ Subprocess client -------------------------- #


class _WorkerProc:
    """
    JSON-RPC over stdio subprocess.
    Launches the worker in the requested environment (conda/venv/arch/system).
    """

    def __init__(self, policy: Policy, cmd: List[str], require_x86_64: bool = False):
        self.policy = policy
        self.cmd = cmd
        self.proc: Optional[subprocess.Popen] = None
        self._id = 0
        self._start(require_x86_64=require_x86_64)

    # ---------- process management ----------

    def _start(self, require_x86_64: bool = False):
        self._hard_kill()  # just in case

        # Ensure unbuffered text I/O
        env = os.environ.copy()
        env.setdefault("PYTHONUNBUFFERED", "1")

        self.proc = subprocess.Popen(
            self.cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,  # line buffered
        )

        # Hello handshake (one line of JSON)
        hello = self._readline_with_timeout(self.policy.call_timeout_s)
        if hello is None:
            self._hard_kill()
            raise Tempo2Timeout("worker did not send hello in time")

        try:
            hello_obj = json.loads(hello)
        except Exception:
            self._hard_kill()
            raise Tempo2ProtocolError(f"malformed hello: {hello!r}")

        info = hello_obj.get("hello", {})
        if require_x86_64:
            if str(info.get("machine", "")).lower() != "x86_64":
                self._hard_kill()
                raise Tempo2Error(
                    f"worker arch is {info.get('machine')}, but x86_64 is required for quad precision"
                )

        if not info.get("has_libstempo", False):
            # Keep the worker up; subsequent ctor will return a clean error,
            # but we can already warn here to fail fast.
            self._hard_kill()
            raise Tempo2Error(
                "libstempo is not importable inside the selected environment. "
                f"Worker executable: {info.get('executable')}"
            )

        self.birth = time.time()
        self.calls_ok = 0

    def _readline_with_timeout(self, timeout: float) -> Optional[str]:
        if self.proc is None or self.proc.stdout is None:
            return None
        end = time.time() + timeout
        while time.time() < end:
            rlist, _, _ = select.select(
                [self.proc.stdout], [], [], max(0.01, end - time.time())
            )
            if rlist:
                line = self.proc.stdout.readline()
                if not line:  # EOF
                    return None
                return line.rstrip("\n")
        return None

    def _hard_kill(self):
        if self.proc and self.proc.poll() is None:
            try:
                self.proc.terminate()
            except Exception:
                pass
            t0 = time.time()
            while (
                self.proc.poll() is None
                and (time.time() - t0) < self.policy.kill_grace_s
            ):
                time.sleep(0.01)
            if self.proc.poll() is None:
                with contextlib.suppress(Exception):
                    os.kill(self.proc.pid, signal.SIGKILL)
        self.proc = None

    def close(self):
        if self.proc and self.proc.poll() is None:
            try:
                self._send_rpc("bye", {})
                # ignore response; we're closing anyway
            except Exception:
                pass
        self._hard_kill()

    def __del__(self):
        with contextlib.suppress(Exception):
            self.close()

    # ---------- JSON-RPC helpers ----------

    def _send_rpc(
        self, method: str, params: Dict[str, Any], timeout: Optional[float] = None
    ) -> Any:
        if self.proc is None or self.proc.stdin is None or self.proc.stdout is None:
            raise Tempo2Crashed("worker not running")

        self._id += 1
        rid = self._id
        frame = {
            "jsonrpc": "2.0",
            "id": rid,
            "method": method,
            "params_b64": _b64_dumps_py(params),
        }
        line = json.dumps(frame) + "\n"

        try:
            self.proc.stdin.write(line)
            self.proc.stdin.flush()
        except Exception as e:
            self._hard_kill()
            raise Tempo2Crashed(f"send failed: {e!r}")

        # Wait for response
        t = self.policy.call_timeout_s if timeout is None else timeout
        resp_line = self._readline_with_timeout(t)
        if resp_line is None:
            self._hard_kill()
            raise Tempo2Timeout(f"RPC '{method}' timed out")

        try:
            resp = json.loads(resp_line)
        except Exception:
            self._hard_kill()
            raise Tempo2ProtocolError(f"malformed response: {resp_line!r}")

        if resp.get("id") != rid:
            self._hard_kill()
            raise Tempo2ProtocolError(
                f"mismatched id in response: {resp.get('id')} vs {rid}"
            )

        if "error" in resp and resp["error"] is not None:
            err = resp["error"]
            msg = err.get("message", "error")
            data = err.get("data", "")
            raise Tempo2Error(f"{msg}\n{data}")

        result_b64 = resp.get("result_b64", None)
        return _b64_loads_py(result_b64) if result_b64 is not None else None

    # Public RPCs
    def ctor(self, kwargs: Dict[str, Any], preload_residuals: bool):
        return self._send_rpc(
            "ctor", {"kwargs": kwargs, "preload_residuals": preload_residuals}
        )

    def get(self, name: str):
        return self._send_rpc("get", {"name": name})

    def set(self, name: str, value: Any):
        return self._send_rpc("set", {"name": name, "value": value})

    def call(self, name: str, args=(), kwargs=None):
        return self._send_rpc(
            "call", {"name": name, "args": tuple(args), "kwargs": dict(kwargs or {})}
        )

    def rss(self) -> Optional[int]:
        try:
            return self._send_rpc("rss", {})
        except Exception:
            return None


# ------------------------- Command resolution (env_name) -------------------- #


def _detect_environment_type(env_name: str) -> str:
    """
    Return "conda", "venv", "arch", "python", or "unknown".
    """
    if env_name.startswith("python:"):
        return "python"

    # conda family
    for tool in ("conda", "mamba", "micromamba"):
        try:
            r = subprocess.run(
                [tool, "run", "-n", env_name, "python", "--version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if r.returncode == 0:
                return "conda:" + tool
        except Exception:
            pass

    # common venv locations
    venv_paths = [
        Path.home() / ".venvs" / env_name / "bin" / "python",
        Path.home() / "venvs" / env_name / "bin" / "python",
        Path.home() / ".virtualenvs" / env_name / "bin" / "python",
        Path.cwd() / env_name / "bin" / "python",
        Path.cwd() / ".venv" / "bin" / "python",  # only if env_name == '.venv'
    ]
    for p in venv_paths:
        if p.exists():
            return "venv"

    if env_name in ("arch", "rosetta", "system"):
        return "arch"

    return "unknown"


def _find_venv_python_path(env_name: str) -> Optional[str]:
    venv_paths = [
        Path.home() / ".venvs" / env_name / "bin" / "python",
        Path.home() / "venvs" / env_name / "bin" / "python",
        Path.home() / ".virtualenvs" / env_name / "bin" / "python",
        Path.cwd() / env_name / "bin" / "python",
        Path.cwd() / ".venv" / "bin" / "python",
    ]
    for p in venv_paths:
        if p.exists():
            return str(p)
    return None


def _resolve_worker_cmd(env_name: Optional[str]) -> Tuple[List[str], bool]:
    """
    Build the subprocess command to run the worker and whether we require x86_64.
    Returns (cmd, require_x86_64)
    """

    # Base invocation that runs this file in worker mode:
    # python -c "import sandbox_tempo2 as m; m._worker_stdio_main()"
    def python_to_worker_cmd(python_exe: str) -> List[str]:
        return [python_exe, "-c", "import sandbox_tempo2 as m; m._worker_stdio_main()"]

    arch_prefix_env = os.environ.get("TEMPO2_SANDBOX_WORKER_ARCH_PREFIX", "").strip()
    require_x86_64 = False

    # No env_name -> use current python (no Rosetta)
    if env_name is None:
        py = sys.executable
        return (python_to_worker_cmd(py), False)

    # Explicit python path
    if env_name.startswith("python:"):
        py = env_name.split(":", 1)[1]
        return (python_to_worker_cmd(py), False)

    etype = _detect_environment_type(env_name)

    # conda/mamba/micromamba
    if etype.startswith("conda:"):
        tool = etype.split(":", 1)[1]
        cmd = [
            tool,
            "run",
            "-n",
            env_name,
            "python",
            "-c",
            "import sandbox_tempo2 as m; m._worker_stdio_main()",
        ]
        # Choosing to require x86_64 only if user *explicitly* asks via arch prefix or env_name == "arch"
        require_x86_64 = "arch" in env_name.lower()
        if arch_prefix_env:
            cmd = arch_prefix_env.split() + cmd
            require_x86_64 = True
        return (cmd, require_x86_64)

    # venv
    if etype == "venv":
        py = _find_venv_python_path(env_name)
        if not py:
            raise Tempo2Error(f"virtualenv '{env_name}' not found in common locations")
        cmd = python_to_worker_cmd(py)
        if arch_prefix_env:
            cmd = arch_prefix_env.split() + cmd
            require_x86_64 = True
        return (cmd, require_x86_64)

    # system Rosetta
    if etype == "arch":
        # try system python (python3 or python)
        py = shutil.which("python3") or shutil.which("python")
        if not py:
            raise Tempo2Error("could not find system python for arch mode")
        arch = arch_prefix_env.split() if arch_prefix_env else ["arch", "-x86_64"]
        require_x86_64 = True
        return (arch + python_to_worker_cmd(py), require_x86_64)

    raise Tempo2Error(
        f"Environment '{env_name}' not found. "
        "Use a conda env name, a venv name, 'arch', or 'python:/abs/python'."
    )


# ------------------------------ Public proxy ------------------------------- #


@dataclasses.dataclass
class _State:
    created_at: float
    calls_ok: int


class tempopulsar:
    """
    Proxy for libstempo.tempopulsar living inside an isolated subprocess.

    Constructor kwargs are forwarded to libstempo.tempopulsar unchanged.

    Args:
        env_name: Environment name (conda env or venv name, 'arch', or 'python:/abs/python').
        **kwargs: Additional arguments passed to libstempo.tempopulsar
    """

    __slots__ = (
        "_policy",
        "_wp",
        "_state",
        "_ctor_kwargs",
        "_env_name",
        "_require_x86",
    )

    def __init__(self, env_name: Optional[str] = None, **kwargs):
        policy = kwargs.pop("policy", None)
        self._policy: Policy = policy if isinstance(policy, Policy) else Policy()
        self._env_name = env_name
        self._ctor_kwargs = dict(kwargs)
        self._wp: Optional[_WorkerProc] = None
        self._state = _State(created_at=time.time(), calls_ok=0)
        self._require_x86 = False

        self._construct_with_retries()

    # --------------- construction / reconstruction with retries --------------- #

    def _construct_with_retries(self):
        last_exc: Optional[Exception] = None
        for _ in range(1 + self._policy.ctor_retry):
            try:
                cmd, require_x86 = _resolve_worker_cmd(self._env_name)
                self._require_x86 = require_x86
                self._wp = _WorkerProc(self._policy, cmd, require_x86_64=require_x86)
                # ctor on the worker (libstempo.tempopulsar)
                self._wp.ctor(
                    self._ctor_kwargs, preload_residuals=self._policy.preload_residuals
                )
                self._state.created_at = time.time()
                self._state.calls_ok = 0
                return
            except Exception as e:
                last_exc = e
                # kill and retry
                try:
                    if self._wp:
                        self._wp.close()
                except Exception:
                    pass
                self._wp = None
                time.sleep(self._policy.ctor_backoff)
        raise Tempo2ConstructorFailed(
            f"tempopulsar ctor failed after retries: {last_exc}"
        )

    # ----------------------------- recycling policy --------------------------- #

    def _should_recycle(self) -> bool:
        if self._wp is None:
            return True
        if (time.time() - self._state.created_at) > self._policy.max_age_s:
            return True
        if self._state.calls_ok >= self._policy.max_calls_per_worker:
            return True
        if self._policy.rss_soft_limit_mb:
            rss = self._wp.rss()
            if rss and rss > self._policy.rss_soft_limit_mb:
                return True
        return False

    def _recycle(self):
        if self._wp is not None:
            with contextlib.suppress(Exception):
                self._wp.close()
            self._wp = None
        self._construct_with_retries()

    # ---------------------------- RPC convenience ----------------------------- #

    def _rpc(self, call: str, **payload):
        if self._wp is None:
            self._construct_with_retries()
        if self._should_recycle():
            self._recycle()
        assert self._wp is not None
        try:
            if call == "get":
                out = self._wp.get(payload["name"])
            elif call == "set":
                out = self._wp.set(payload["name"], payload["value"])
            elif call == "call":
                out = self._wp.call(
                    payload["name"], payload.get("args", ()), payload.get("kwargs", {})
                )
            else:
                raise Tempo2ProtocolError(f"unknown call {call}")
            self._state.calls_ok += 1
            return out
        except (Tempo2Timeout, Tempo2Crashed, Tempo2ProtocolError, Tempo2Error):
            # automatic one-time recycle on a fresh worker
            self._recycle()
            assert self._wp is not None
            if call == "get":
                out = self._wp.get(payload["name"])
            elif call == "set":
                out = self._wp.set(payload["name"], payload["value"])
            else:
                out = self._wp.call(
                    payload["name"], payload.get("args", ()), payload.get("kwargs", {})
                )
            self._state.calls_ok += 1
            return out

    # ------------------------ Attribute proxying magic ------------------------ #

    def __getattr__(self, name: str):
        def _remote_method(*args, **kwargs):
            return self._rpc("call", name=name, args=args, kwargs=kwargs)

        # Try a GET first; if it errors, assume it's a method
        try:
            val = self._rpc("get", name=name)
        except Tempo2Error:
            return _remote_method
        if callable(val):
            return _remote_method
        return val

    def __setattr__(self, name: str, value: Any):
        if name in tempopulsar.__slots__:
            return object.__setattr__(self, name, value)
        _ = self._rpc("set", name=name, value=value)
        return None

    # Explicit helpers for common call shapes
    def residuals(self, **kwargs):
        return self._rpc("call", name="residuals", kwargs=kwargs)

    def designmatrix(self, **kwargs):
        return self._rpc("call", name="designmatrix", kwargs=kwargs)

    def toas(self, **kwargs):
        return self._rpc("call", name="toas", kwargs=kwargs)

    def fit(self, **kwargs):
        return self._rpc("call", name="fit", kwargs=kwargs)

    def __del__(self):
        with contextlib.suppress(Exception):
            if self._wp is not None:
                self._wp.close()


# -------------------------- Bulk loader (optional) -------------------------- #


@dataclass
class LoadReport:
    par: str
    tim: Optional[str]
    attempts: int
    ok: bool
    error: Optional[str] = None
    retried: bool = False


def load_many(
    pairs: Iterable[Tuple[str, Optional[str]]],
    policy: Optional[Policy] = None,
    parallel: int = 8,
) -> Tuple[Dict[str, tempopulsar], Dict[str, LoadReport], List[LoadReport]]:
    """
    Bulk-load many pulsars with bounded parallelism.
    Returns: (ok_by_name, retried_by_name, failed_list)

    ok_by_name:      {psr_name: tempopulsar proxy}
    retried_by_name: {psr_name: LoadReport} (those that required >=1 retry)
    failed_list:     [LoadReport,...]
    """
    pol = policy if isinstance(policy, Policy) else Policy()

    def _one(par, tim):
        attempts = 0
        report = LoadReport(par=par, tim=tim, attempts=0, ok=False)
        last_exc = None
        for _ in range(1 + pol.ctor_retry):
            attempts += 1
            try:
                psr = tempopulsar(parfile=par, timfile=tim, policy=pol)
                name = getattr(psr, "name")
                report.attempts = attempts
                report.ok = True
                report.retried = attempts > 1
                return ("ok", name, psr, report)
            except Exception as e:
                last_exc = e
                time.sleep(pol.ctor_backoff)
        report.attempts = attempts
        report.ok = False
        report.error = f"{last_exc.__class__.__name__}: {last_exc}"
        return ("fail", None, None, report)

    ok: Dict[str, tempopulsar] = {}
    retried: Dict[str, LoadReport] = {}
    failed: List[LoadReport] = []

    with ThreadPoolExecutor(max_workers=max(1, parallel)) as ex:
        futs = {ex.submit(_one, par, tim): (par, tim) for (par, tim) in pairs}
        for fut in as_completed(futs):
            kind, name, psr, report = fut.result()
            if kind == "ok":
                ok[name] = psr
                if report.retried:
                    retried[name] = report
            else:
                failed.append(report)
    return ok, retried, failed


# ------------------------------- Quick helpers ------------------------------ #


def setup_instructions(env_name: str = "tempo2_intel"):
    print("Setup instructions for environment '{}':".format(env_name))
    print("\n1. Conda (recommended):")
    print(f"   conda create -n {env_name} python=3.11")
    print(f"   conda activate {env_name}")
    print("   conda install -c conda-forge tempo2 libstempo")
    print(f'   # then just: psr = tempopulsar(..., env_name="{env_name}")')
    print("\n2. Virtual Environment (Rosetta):")
    print(f"   arch -x86_64 /usr/local/bin/python3 -m venv ~/.venvs/{env_name}")
    print(f"   source ~/.venvs/{env_name}/bin/activate")
    print("   pip install tempo2 libstempo")
    print(f'   # then just: psr = tempopulsar(..., env_name="{env_name}")')
    print("\n3. System Python with Rosetta:")
    print("   # Install Intel Python first (or use system one under arch).")
    print(
        '   # You can force Rosetta via TEMPO2_SANDBOX_WORKER_ARCH_PREFIX="arch -x86_64"'
    )
    print('   # then: psr = tempopulsar(..., env_name="arch")')


def detect_and_guide(env_name: str):
    et = _detect_environment_type(env_name)
    print(f"Environment detection for '{env_name}': {et}")
    if et.startswith("conda:"):
        print("✅ Conda env detected; just use env_name as given.")
    elif et == "venv":
        p = _find_venv_python_path(env_name)
        if p:
            print(f"✅ venv detected at {p}")
        else:
            print("❌ venv name matched, but python path not resolved.")
    elif et == "arch":
        print("✅ Rosetta/system arch mode will be used.")
    elif et == "python":
        print("✅ Using explicit Python path.")
    else:
        print(
            "❌ Not found. Use conda env name, venv name, 'arch', or 'python:/abs/python'."
        )


# ------------------------------ Module runner ------------------------------- #

if __name__ == "__main__":
    # If executed directly, act as worker (useful for manual debugging):
    _worker_stdio_main()
