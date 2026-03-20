#!/usr/bin/env python3
"""Generate deterministic pulse-tracking regression fixtures.

The generated datasets encode the scientific scenario behind
``tests/test_pulse_tracking.py``:

- ``epta_like`` is individually coherent with a DM/DM1/DM2 model.
- ``nanograv_like`` is individually coherent with a DMX model.
- Merging them through MetaPulsar's consistent-parfile path removes the DMX
  model and resets DM1/DM2, which breaks coherence unless pulse numbers are
  preserved from the original coherent solutions.
"""

from __future__ import annotations

import argparse
from io import StringIO
from pathlib import Path

import astropy.units as u
import numpy as np
from pint.models import get_model, get_model_and_toas
from pint.models.model_builder import parse_parfile
from pint.residuals import Residuals
from pint.simulation import make_fake_toas_fromMJDs

from metapulsar.pint_helpers import dict_to_parfile_string


FIXTURE_DIR = Path(__file__).resolve().parent
EPTA_PAR = FIXTURE_DIR / "epta_like.par"
EPTA_TIM = FIXTURE_DIR / "epta_like.tim"
NANOGRAV_PAR = FIXTURE_DIR / "nanograv_like.par"
NANOGRAV_TIM = FIXTURE_DIR / "nanograv_like.tim"

PULSAR_NAME = "J2222+2222"
START_MJD = 56000.0
END_MJD = START_MJD + 365.25 * 10.0
PEPOCH = 58000.0
DMEPOCH = 58000.0
F0_HZ = 300.0
F1_HZ_PER_S = -1.0e-15
DM_PC_CM3 = 120.0
DM1_PC_CM3_PER_YR = 0.1
DM2_PC_CM3_PER_YR2 = 0.05

EPTA_EPOCHS = 100
EPTA_FREQS_MHZ = np.array([300.0, 950.0, 1600.0])
NANOGRAV_EPOCHS = 20
NANOGRAV_FREQS_MHZ = np.linspace(300.0, 1600.0, 15)
DMX_HALF_WIDTH_DAYS = 0.01
TOA_ERROR = 1.0 * u.us
OBSERVATORY = "gbt"
SANITY_RMS_THRESHOLD_S = 1.0e-8


def build_truth_model():
    """Create the coherent truth model."""
    truth_par = f"""PSR {PULSAR_NAME}
EPHEM DE440
CLOCK TT(BIPM2021)
UNITS TDB
ELONG 45
ELAT 20
F0 {F0_HZ}
F1 {F1_HZ_PER_S}
PEPOCH {PEPOCH}
DM {DM_PC_CM3}
DM1 {DM1_PC_CM3_PER_YR}
DM2 {DM2_PC_CM3_PER_YR2}
DMEPOCH {DMEPOCH}
"""
    return get_model(StringIO(truth_par), allow_T2=True)


def dm_at_epoch(mjd: float) -> float:
    """Return the truth DM at a given MJD.

    PINT's dispersion Taylor series interprets DM1/DM2 in years relative to
    DMEPOCH, with the second derivative carrying the usual 1/2 factor.
    """
    dt_years = (mjd - DMEPOCH) / 365.25
    return (
        DM_PC_CM3
        + DM1_PC_CM3_PER_YR * dt_years
        + 0.5 * DM2_PC_CM3_PER_YR2 * (dt_years**2)
    )


def make_dataset_toas(model, mjds: np.ndarray, freqs_mhz: np.ndarray, name: str):
    """Generate exact, noiseless multi-frequency TOAs for one PTA-like dataset."""
    return make_fake_toas_fromMJDs(
        mjds * u.day,
        model=model,
        freq=freqs_mhz * u.MHz,
        obs=OBSERVATORY,
        error=TOA_ERROR,
        add_noise=False,
        multi_freqs_in_epoch=True,
        name=name,
        flags={"pta": name},
    )


def build_nanograv_like_parfile_text(truth_model, mjd_epochs: np.ndarray) -> str:
    """Create a DMX-based parfile that is exactly coherent for the synthetic TOAs."""
    par_dict = parse_parfile(StringIO(truth_model.as_parfile()))

    for key in list(par_dict.keys()):
        if key.startswith("DMX") or key in {"DM1", "DM2"}:
            par_dict.pop(key, None)

    par_dict["DMX"] = [str(len(mjd_epochs))]

    for index, mjd in enumerate(mjd_epochs, start=1):
        suffix = f"{index:04d}"
        dmx_value = dm_at_epoch(mjd) - DM_PC_CM3
        par_dict[f"DMX_{suffix}"] = [f"{dmx_value} 1"]
        par_dict[f"DMXR1_{suffix}"] = [f"{mjd - DMX_HALF_WIDTH_DAYS}"]
        par_dict[f"DMXR2_{suffix}"] = [f"{mjd + DMX_HALF_WIDTH_DAYS}"]

    return dict_to_parfile_string(par_dict, format="pint")


def sanity_check(par_path: Path, tim_path: Path) -> float:
    """Return the pre-fit RMS for a fixture pair and assert it is coherent."""
    model, toas = get_model_and_toas(
        str(par_path),
        str(tim_path),
        allow_T2=True,
        planets=True,
    )
    residuals = Residuals(toas, model).time_resids.to(u.s).value
    rms = float(np.sqrt(np.mean(residuals**2)))
    if rms > SANITY_RMS_THRESHOLD_S:
        raise RuntimeError(
            f"Fixture sanity check failed for {par_path.name}: RMS={rms:.3e} s"
        )
    return rms


def generate(force: bool = False) -> None:
    """Generate fixture files in-place."""
    truth_model = build_truth_model()

    epta_epochs = np.linspace(START_MJD, END_MJD, EPTA_EPOCHS)
    nanograv_epochs = np.linspace(START_MJD, END_MJD, NANOGRAV_EPOCHS)

    epta_toas = make_dataset_toas(truth_model, epta_epochs, EPTA_FREQS_MHZ, "epta_like")
    nanograv_toas = make_dataset_toas(
        truth_model, nanograv_epochs, NANOGRAV_FREQS_MHZ, "nanograv_like"
    )

    outputs = {
        EPTA_PAR: truth_model.as_parfile(),
        EPTA_TIM: epta_toas,
        NANOGRAV_PAR: build_nanograv_like_parfile_text(truth_model, nanograv_epochs),
        NANOGRAV_TIM: nanograv_toas,
    }

    for path, value in outputs.items():
        if path.exists() and not force:
            raise FileExistsError(
                f"{path} already exists. Re-run with --force to overwrite fixtures."
            )

        if hasattr(value, "write_TOA_file"):
            value.write_TOA_file(path, format="tempo2", include_pn=False)
        else:
            path.write_text(value, encoding="utf-8")

    epta_rms = sanity_check(EPTA_PAR, EPTA_TIM)
    nanograv_rms = sanity_check(NANOGRAV_PAR, NANOGRAV_TIM)
    print(f"Wrote fixtures to {FIXTURE_DIR}")
    print(f"  {EPTA_PAR.name}: RMS={epta_rms:.3e} s")
    print(f"  {NANOGRAV_PAR.name}: RMS={nanograv_rms:.3e} s")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing fixture files.",
    )
    args = parser.parse_args()
    generate(force=args.force)


if __name__ == "__main__":
    main()
