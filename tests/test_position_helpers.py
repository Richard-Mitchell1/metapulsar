"""
Comprehensive tests for position_helpers module.

Tests coordinate conversion between PINT TimingModel, libstempo tempopulsar,
and Enterprise Pulsar objects, plus J-name generation.
"""

import pytest
from io import StringIO
from dataclasses import dataclass

import astropy.units as u
from astropy.coordinates import SkyCoord, ICRS, BarycentricTrueEcliptic
from pint.models.model_builder import ModelBuilder

from metapulsar.position_helpers import (
    _skycoord_from_pint_model,
    _skycoord_from_enterprise,
    _skycoord_from_libstempo,
    bj_name_from_pulsar,
)

# === FIXTURES ===


@pytest.fixture
def mb():
    """PINT ModelBuilder instance."""
    return ModelBuilder()


@pytest.fixture
def model_J(mb, load_parfile_text):
    """PINT model from binary.par file."""
    return _build_pint_model(mb, load_parfile_text("binary.par"))


@pytest.fixture
def model_B(mb, load_parfile_text):
    """PINT model from binary-B.par file."""
    return _build_pint_model(mb, load_parfile_text("binary-B.par"))


# === HELPER FUNCTIONS ===


def _build_pint_model(mb: ModelBuilder, par_text: str):
    """Build PINT model from parfile text."""
    return mb(StringIO(par_text), allow_tcb=True, allow_T2=True)


# === MOCK CLASSES ===


@dataclass
class LibstempoParam:
    """Mock libstempo parameter with .val attribute."""

    val: float


class LibstempoMock:
    """Mock libstempo tempopulsar with dict-like parameter access."""

    def __init__(self, mapping):
        self._m = mapping

    def __getitem__(self, key):
        return self._m[key]


class EnterpriseMock:
    """Mock Enterprise Pulsar with internal coordinate attributes."""

    def __init__(self, raj_rad: float, decj_rad: float):
        self._raj = raj_rad
        self._decj = decj_rad


# === UTILITY FUNCTIONS ===


def _icrs_from_model(model) -> SkyCoord:
    """Ground-truth ICRS from the PINT model using your extractor."""
    return _skycoord_from_pint_model(model).transform_to(ICRS())


def enterprise_from_model(model) -> EnterpriseMock:
    """Create Enterprise mock from PINT model coordinates."""
    c = _icrs_from_model(model)
    return EnterpriseMock(c.ra.to(u.rad).value, c.dec.to(u.rad).value)


def libstempo_from_model_equatorial(model) -> LibstempoMock:
    """Mock with RAJ/DECJ (in radians)."""
    c = _icrs_from_model(model)
    mapping = {
        "RAJ": LibstempoParam(c.ra.to(u.rad).value),
        "DECJ": LibstempoParam(c.dec.to(u.rad).value),
        # No ecliptic keys so _skycoord_from_libstempo takes equatorial branch
    }
    return LibstempoMock(mapping)


def libstempo_from_model_ecliptic(model) -> LibstempoMock:
    """Mock with ELONG/ELAT only (in radians) to hit the ecliptic branch."""
    c = _icrs_from_model(model).transform_to(BarycentricTrueEcliptic(equinox="J2000"))
    mapping = {
        "ELONG": LibstempoParam(c.lon.to(u.rad).value),
        "ELAT": LibstempoParam(c.lat.to(u.rad).value),
        # Intentionally omit RAJ/DECJ so the code must use ecliptic path
    }
    return LibstempoMock(mapping)


def _assert_coords_close(c1: SkyCoord, c2: SkyCoord, atol_rad=1e-10):
    """Assert two SkyCoord objects are close within tolerance."""
    sep = c1.separation(c2).to(u.rad).value
    assert sep <= atol_rad, f"Coords differ by {sep} rad (> {atol_rad})"


# === TEST CLASSES ===


class TestBJNameGeneration:
    """Test B/J-name generation from various pulsar objects."""

    @pytest.mark.parametrize("parfile_name", ["binary.par", "binary-B.par"])
    def test_j_name_from_pint_model(self, mb, load_parfile_text, parfile_name):
        """Test J-name generation from PINT models."""
        par_text = load_parfile_text(parfile_name)
        model = _build_pint_model(mb, par_text)
        jlabel = bj_name_from_pulsar(model, "J")
        assert jlabel == "J1857+0943"

    @pytest.mark.parametrize("parfile_name", ["binary.par", "binary-B.par"])
    def test_b_name_from_pint_model(self, mb, load_parfile_text, parfile_name):
        """Test B-name generation from PINT models."""
        par_text = load_parfile_text(parfile_name)
        model = _build_pint_model(mb, par_text)
        blabel = bj_name_from_pulsar(model, "B")
        assert blabel == "B1855+09"

    def test_name_consistency_across_parfiles(self, model_J, model_B):
        """Test that names are consistent between different parfile formats."""
        jl_j = bj_name_from_pulsar(model_J, "J")
        jl_b = bj_name_from_pulsar(model_B, "J")
        bl_j = bj_name_from_pulsar(model_J, "B")
        bl_b = bj_name_from_pulsar(model_B, "B")
        assert jl_j == jl_b == "J1857+0943"
        assert bl_j == bl_b == "B1855+09"

    def test_default_name_type_is_j(self, model_J):
        """Test that default name type is J."""
        jlabel = bj_name_from_pulsar(model_J)
        assert jlabel == "J1857+0943"

    def test_invalid_name_type_raises_error(self, model_J):
        """Test that invalid name type raises ValueError."""
        with pytest.raises(ValueError):
            bj_name_from_pulsar(model_J, "X")


class TestCoordinateConversion:
    """Test coordinate conversion between different pulsar object types."""

    @pytest.mark.parametrize("which", ["J", "B"])
    def test_skycoord_from_enterprise_matches_pint(self, which, model_J, model_B):
        """Test Enterprise mock produces same coordinates as PINT model."""
        model = model_J if which == "J" else model_B
        truth = _icrs_from_model(model)

        emock = enterprise_from_model(model)
        c_ent = _skycoord_from_enterprise(emock).transform_to(ICRS())

        _assert_coords_close(c_ent, truth)

    @pytest.mark.parametrize("which", ["J", "B"])
    def test_skycoord_from_libstempo_equatorial_matches_pint(
        self, which, model_J, model_B
    ):
        """Test libstempo equatorial mock produces same coordinates as PINT model."""
        model = model_J if which == "J" else model_B
        truth = _icrs_from_model(model)

        lmock = libstempo_from_model_equatorial(model)
        c_lt = _skycoord_from_libstempo(lmock).transform_to(ICRS())

        _assert_coords_close(c_lt, truth)

    @pytest.mark.parametrize("which", ["J", "B"])
    def test_skycoord_from_libstempo_ecliptic_matches_pint(
        self, which, model_J, model_B
    ):
        """Test libstempo ecliptic mock produces same coordinates as PINT model."""
        model = model_J if which == "J" else model_B
        truth = _icrs_from_model(model)

        lmock = libstempo_from_model_ecliptic(model)
        c_lt = _skycoord_from_libstempo(lmock).transform_to(ICRS())

        _assert_coords_close(c_lt, truth)


class TestEndToEndJNameGeneration:
    """Test end-to-end J-name generation using mocks."""

    @pytest.mark.parametrize("which", ["J", "B"])
    def test_j_label_from_enterprise_mock(self, which, model_J, model_B):
        """Test J-name generation from Enterprise mock objects."""
        model = model_J if which == "J" else model_B
        emock = enterprise_from_model(model)
        assert bj_name_from_pulsar(emock, "J") == "J1857+0943"

    @pytest.mark.parametrize("which", ["J", "B"])
    def test_b_label_from_enterprise_mock(self, which, model_J, model_B):
        """Test B-name generation from Enterprise mock objects."""
        model = model_J if which == "J" else model_B
        emock = enterprise_from_model(model)
        assert bj_name_from_pulsar(emock, "B") == "B1855+09"

    @pytest.mark.parametrize(
        "which,variant", [("J", "eq"), ("B", "eq"), ("J", "ecl"), ("B", "ecl")]
    )
    def test_j_label_from_libstempo_mocks(self, which, variant, model_J, model_B):
        """Test J-name generation from libstempo mock objects."""
        model = model_J if which == "J" else model_B
        if variant == "eq":
            lmock = libstempo_from_model_equatorial(model)
        else:
            lmock = libstempo_from_model_ecliptic(model)
        assert bj_name_from_pulsar(lmock, "J") == "J1857+0943"

    @pytest.mark.parametrize(
        "which,variant", [("J", "eq"), ("B", "eq"), ("J", "ecl"), ("B", "ecl")]
    )
    def test_b_label_from_libstempo_mocks(self, which, variant, model_J, model_B):
        """Test B-name generation from libstempo mock objects."""
        model = model_J if which == "J" else model_B
        if variant == "eq":
            lmock = libstempo_from_model_equatorial(model)
        else:
            lmock = libstempo_from_model_ecliptic(model)
        assert bj_name_from_pulsar(lmock, "B") == "B1855+09"
