from pathlib import Path
import pytest

@pytest.fixture(scope="session")
def parfiles_dir() -> Path:
    return Path(__file__).parent / "fixtures" / "sample_parfiles"

@pytest.fixture
def load_parfile_text(parfiles_dir):
    def _load(name: str) -> str:
        p = (parfiles_dir / name).resolve()
        if not p.exists():
            # helpful debug if it ever happens again
            available_files = [f.name for f in parfiles_dir.iterdir()]
            raise FileNotFoundError(f"Missing test parfile: {p}. Available: {available_files}")
        return p.read_text(encoding="utf-8")
    return _load
