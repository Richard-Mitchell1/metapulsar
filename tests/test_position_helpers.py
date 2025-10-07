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
    extract_coordinates_from_parfile_optimized,
    bj_name_from_coordinates_optimized,
    discover_pulsars_by_coordinates_optimized,
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


# ============================================================================
# OPTIMIZED COORDINATE EXTRACTION TESTS
# ============================================================================


class TestOptimizedCoordinateExtraction:
    """Test optimized coordinate extraction functions."""

    def test_extract_coordinates_from_parfile_optimized_equatorial(
        self, load_parfile_text
    ):
        """Test optimized coordinate extraction from equatorial coordinates."""
        parfile_content = load_parfile_text("binary.par")
        coords = extract_coordinates_from_parfile_optimized(parfile_content)

        assert coords is not None, "Failed to extract coordinates"
        ra_hours, dec_deg = coords

        # Verify coordinates are reasonable
        assert 0 <= ra_hours < 24, f"RA out of range: {ra_hours}"
        assert -90 <= dec_deg <= 90, f"DEC out of range: {dec_deg}"

        # Verify J-name generation
        j_name = bj_name_from_coordinates_optimized(ra_hours, dec_deg, "J")
        assert j_name == "J1857+0943", f"J-name mismatch: {j_name}"

    def test_extract_coordinates_from_parfile_optimized_ecliptic_lambda_beta(self):
        """Test optimized coordinate extraction from LAMBDA/BETA coordinates."""
        parfile_content = """
PSR J1857+0943
LAMBDA 285.1234
BETA 9.7214
F0 186.494081
F1 -1.23e-15
PEPOCH 55000.0
DM 10.0
"""

        coords = extract_coordinates_from_parfile_optimized(parfile_content)
        assert coords is not None, "Failed to extract LAMBDA/BETA coordinates"

        ra_hours, dec_deg = coords
        j_name = bj_name_from_coordinates_optimized(ra_hours, dec_deg, "J")

        # Should produce a valid J-name
        assert j_name.startswith("J"), f"Invalid J-name format: {j_name}"
        assert len(j_name) == 10, f"Invalid J-name length: {j_name}"

    def test_extract_coordinates_from_parfile_optimized_ecliptic_elong_elat(self):
        """Test optimized coordinate extraction from ELONG/ELAT coordinates."""
        parfile_content = """
PSR J1857+0943
ELONG 285.1234
ELAT 9.7214
F0 186.494081
F1 -1.23e-15
PEPOCH 55000.0
DM 10.0
"""

        coords = extract_coordinates_from_parfile_optimized(parfile_content)
        assert coords is not None, "Failed to extract ELONG/ELAT coordinates"

        ra_hours, dec_deg = coords
        j_name = bj_name_from_coordinates_optimized(ra_hours, dec_deg, "J")

        # Should produce a valid J-name
        assert j_name.startswith("J"), f"Invalid J-name format: {j_name}"
        assert len(j_name) == 10, f"Invalid J-name length: {j_name}"

    def test_lambda_beta_vs_elong_elat_consistency(self):
        """Test that LAMBDA/BETA and ELONG/ELAT produce identical results."""
        parfile_lambda = """
PSR J1857+0943
LAMBDA 285.1234
BETA 9.7214
F0 186.494081
F1 -1.23e-15
PEPOCH 55000.0
DM 10.0
"""

        parfile_elong = """
PSR J1857+0943
ELONG 285.1234
ELAT 9.7214
F0 186.494081
F1 -1.23e-15
PEPOCH 55000.0
DM 10.0
"""

        coords_lambda = extract_coordinates_from_parfile_optimized(parfile_lambda)
        coords_elong = extract_coordinates_from_parfile_optimized(parfile_elong)

        assert coords_lambda is not None, "Failed to extract LAMBDA/BETA coordinates"
        assert coords_elong is not None, "Failed to extract ELONG/ELAT coordinates"

        # Both should produce identical results
        assert (
            coords_lambda == coords_elong
        ), f"LAMBDA/BETA and ELONG/ELAT results differ: {coords_lambda} != {coords_elong}"

    def test_bj_name_from_coordinates_optimized_j_name(self):
        """Test optimized J-name generation from coordinates."""
        ra_hours = 18.9601  # 18:57:36.4
        dec_deg = 9.7214  # +09:43:17.1

        j_name = bj_name_from_coordinates_optimized(ra_hours, dec_deg, "J")
        expected_j_name = "J1857+0943"

        assert (
            j_name == expected_j_name
        ), f"J-name mismatch: {j_name} != {expected_j_name}"

    def test_bj_name_from_coordinates_optimized_b_name(self):
        """Test optimized B-name generation from coordinates."""
        ra_hours = 18.9601  # 18:57:36.4
        dec_deg = 9.7214  # +09:43:17.1

        b_name = bj_name_from_coordinates_optimized(ra_hours, dec_deg, "B")
        expected_b_name = "B1855+09"  # B-names use FK4 coordinates

        assert (
            b_name == expected_b_name
        ), f"B-name mismatch: {b_name} != {expected_b_name}"

    def test_discover_pulsars_by_coordinates_optimized(self, load_parfile_text):
        """Test optimized pulsar discovery system."""
        # Create test file data
        parfile_content = load_parfile_text("binary.par")
        file_data = {
            "EPTA": [
                {"par": "test.par", "par_content": parfile_content, "tim": "test.tim"}
            ]
        }

        # Run optimized discovery
        coordinate_map = discover_pulsars_by_coordinates_optimized(file_data)

        # Verify results
        assert len(coordinate_map) > 0, "No pulsars discovered"
        assert "J1857+0943" in coordinate_map, "Expected pulsar not found"
        assert "EPTA" in coordinate_map["J1857+0943"], "PTA not found in results"
        assert (
            len(coordinate_map["J1857+0943"]["EPTA"]) == 1
        ), "Incorrect number of files"

    def test_optimized_vs_original_consistency(self, load_parfile_text):
        """Test that optimized functions produce same results as original."""
        parfile_content = load_parfile_text("binary.par")

        # Extract coordinates using optimized method
        coords_opt = extract_coordinates_from_parfile_optimized(parfile_content)
        assert coords_opt is not None, "Optimized extraction failed"

        ra_hours, dec_deg = coords_opt
        j_name_opt = bj_name_from_coordinates_optimized(ra_hours, dec_deg, "J")
        b_name_opt = bj_name_from_coordinates_optimized(ra_hours, dec_deg, "B")

        # Create PINT model for comparison
        from io import StringIO
        from pint.models.model_builder import ModelBuilder

        mb = ModelBuilder()
        model = mb(StringIO(parfile_content), allow_tcb=True, allow_T2=True)

        # Extract using original method
        j_name_orig = bj_name_from_pulsar(model, "J")
        b_name_orig = bj_name_from_pulsar(model, "B")

        # Results should match
        assert (
            j_name_opt == j_name_orig
        ), f"J-name mismatch: {j_name_opt} != {j_name_orig}"
        assert (
            b_name_opt == b_name_orig
        ), f"B-name mismatch: {b_name_opt} != {b_name_orig}"

    def test_malformed_parfile_handling(self):
        """Test handling of malformed parfiles."""
        malformed_parfiles = [
            "",  # Empty content
            "PSR J1857+0943\nF0 186.494081",  # No coordinates
            "PSR J1857+0943\nRAJ invalid\nDECJ 9.7214",  # Invalid RA
            "PSR J1857+0943\nRAJ 18.9601\nDECJ invalid",  # Invalid DEC
        ]

        for parfile_content in malformed_parfiles:
            coords = extract_coordinates_from_parfile_optimized(parfile_content)
            assert (
                coords is None
            ), f"Should return None for malformed parfile: {parfile_content}"

    def test_coordinate_precision_optimized(self):
        """Test coordinate precision in optimized extraction."""
        parfile_content = """
PSR J1857+0943
RAJ 18:57:36.4000
DECJ +09:43:17.1000
F0 186.494081
F1 -1.23e-15
PEPOCH 55000.0
DM 10.0
"""

        coords = extract_coordinates_from_parfile_optimized(parfile_content)
        assert coords is not None, "Failed to extract coordinates"

        ra_hours, dec_deg = coords

        # Verify precision is maintained
        expected_ra = 18.96011111111111  # 18:57:36.4000 in hours
        expected_dec = 9.721416666666667  # +09:43:17.1000 in degrees

        assert (
            abs(ra_hours - expected_ra) < 1e-10
        ), f"RA precision error: {ra_hours} != {expected_ra}"
        assert (
            abs(dec_deg - expected_dec) < 1e-10
        ), f"DEC precision error: {dec_deg} != {expected_dec}"

    def test_coordinate_parameter_aliases_optimized(self):
        """Test that coordinate parameter aliases work correctly."""
        # Test RA/DEC aliases
        parfile_ra_dec = """
PSR J1857+0943
RA 18:57:36.4
DEC +09:43:17.1
F0 186.494081
F1 -1.23e-15
PEPOCH 55000.0
DM 10.0
"""

        coords_ra_dec = extract_coordinates_from_parfile_optimized(parfile_ra_dec)
        assert (
            coords_ra_dec is not None
        ), "Failed to extract coordinates with RA/DEC aliases"

        # Test LAMBDA/BETA aliases (LAMBDA->ELONG, BETA->ELAT)
        parfile_lambda_beta = """
PSR J1857+0943
LAMBDA 285.1234
BETA 9.7214
F0 186.494081
F1 -1.23e-15
PEPOCH 55000.0
DM 10.0
"""

        coords_lambda_beta = extract_coordinates_from_parfile_optimized(
            parfile_lambda_beta
        )
        assert (
            coords_lambda_beta is not None
        ), "Failed to extract coordinates with LAMBDA/BETA aliases"

        # Test that both produce valid J-names
        j_name_ra_dec = bj_name_from_coordinates_optimized(
            coords_ra_dec[0], coords_ra_dec[1], "J"
        )
        j_name_lambda_beta = bj_name_from_coordinates_optimized(
            coords_lambda_beta[0], coords_lambda_beta[1], "J"
        )

        assert j_name_ra_dec.startswith("J"), f"Invalid J-name format: {j_name_ra_dec}"
        assert j_name_lambda_beta.startswith(
            "J"
        ), f"Invalid J-name format: {j_name_lambda_beta}"
        assert len(j_name_ra_dec) == 10, f"Invalid J-name length: {j_name_ra_dec}"
        assert (
            len(j_name_lambda_beta) == 10
        ), f"Invalid J-name length: {j_name_lambda_beta}"
