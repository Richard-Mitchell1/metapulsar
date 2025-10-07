"""
Unit tests for MockPulsar class.

This module contains tests copied exactly from Enterprise PR #361.
Once the PR is accepted upstream, this module can be removed and replaced with
imports from enterprise.tests.test_pulsar.

Source: https://github.com/nanograv/enterprise/pull/361/files
"""

import pytest
import numpy as np
from unittest.mock import patch

from metapulsar.mockpulsar import MockPulsar, create_mock_pulsar
from metapulsar.mockpulsar import (
    create_astrometry_model,
    convert_astrometry_units,
    create_mock_flags,
    create_mock_timing_data,
    validate_mock_pulsar_data,
)


class TestMockPulsar:
    """Test MockPulsar class functionality."""

    def test_basic_initialization(self):
        """Test basic MockPulsar initialization."""
        n_toas = 100
        toas = np.linspace(50000, 60000, n_toas) * 86400  # Convert to seconds
        residuals = np.random.normal(0, 1e-6, n_toas)
        errors = np.ones(n_toas) * 1e-7
        freqs = np.random.uniform(100, 2000, n_toas)
        flags = {"telescope": np.array(["mock"] * n_toas)}

        psr = MockPulsar(toas, residuals, errors, freqs, flags, "mock", "test_psr")

        assert psr.name == "test_psr"
        assert len(psr._toas) == n_toas
        assert len(psr._residuals) == n_toas
        assert len(psr._toaerrs) == n_toas
        assert len(psr._freqs) == n_toas
        # MockPulsar uses structured array format for flags (Enterprise PR specification)
        assert len(psr._flags) == n_toas

    def test_telescope_handling(self):
        """Test telescope parameter handling."""
        n_toas = 50
        toas = np.linspace(50000, 60000, n_toas) * 86400
        residuals = np.random.normal(0, 1e-6, n_toas)
        errors = np.ones(n_toas) * 1e-7
        freqs = np.random.uniform(100, 2000, n_toas)
        flags = {}

        # Test string telescope
        psr1 = MockPulsar(toas, residuals, errors, freqs, flags, "GBT")
        assert np.all(psr1._telescope == "GBT")

        # Test array telescope
        telescope_array = ["GBT", "AO"] * (n_toas // 2) + ["GBT"] * (n_toas % 2)
        psr2 = MockPulsar(toas, residuals, errors, freqs, flags, telescope_array)
        assert np.array_equal(psr2._telescope, telescope_array)

    def test_flags_setup(self):
        """Test flags setup."""
        n_toas = 30
        toas = np.linspace(50000, 60000, n_toas) * 86400
        residuals = np.random.normal(0, 1e-6, n_toas)
        errors = np.ones(n_toas) * 1e-7
        freqs = np.random.uniform(100, 2000, n_toas)

        # Test with custom flags
        flags = {
            "telescope": np.array(["GBT"] * n_toas),
            "backend": np.array(["GUPPI"] * n_toas),
            "band": np.array(["L"] * n_toas),
        }

        psr = MockPulsar(toas, residuals, errors, freqs, flags, "mock")

        assert "telescope" in psr._flags.dtype.names
        assert "backend" in psr._flags.dtype.names
        assert "band" in psr._flags.dtype.names
        assert np.all(psr._flags["telescope"] == "GBT")
        assert np.all(psr._flags["backend"] == "GUPPI")
        assert np.all(psr._flags["band"] == "L")

    def test_position_attributes(self):
        """Test position-related attributes."""
        n_toas = 20
        toas = np.linspace(50000, 60000, n_toas) * 86400
        residuals = np.random.normal(0, 1e-6, n_toas)
        errors = np.ones(n_toas) * 1e-7
        freqs = np.random.uniform(100, 2000, n_toas)
        flags = {}

        psr = MockPulsar(toas, residuals, errors, freqs, flags, "mock")

        # Check default position
        assert hasattr(psr, "_raj")
        assert hasattr(psr, "_decj")
        assert hasattr(psr, "_pos")
        assert hasattr(psr, "_pos_t")
        assert hasattr(psr, "_pdist")

        # Check position vector shape
        assert psr._pos.shape == (3,)
        assert psr._pos_t.shape == (n_toas, 3)

    def test_set_residuals(self):
        """Test set_residuals method."""
        n_toas = 25
        toas = np.linspace(50000, 60000, n_toas) * 86400
        residuals = np.random.normal(0, 1e-6, n_toas)
        errors = np.ones(n_toas) * 1e-7
        freqs = np.random.uniform(100, 2000, n_toas)
        flags = {}

        psr = MockPulsar(toas, residuals, errors, freqs, flags, "mock")

        new_residuals = np.random.normal(0, 2e-6, n_toas)
        psr.set_residuals(new_residuals)

        assert np.array_equal(psr._residuals, new_residuals)

    def test_set_position(self):
        """Test set_position method."""
        n_toas = 15
        toas = np.linspace(50000, 60000, n_toas) * 86400
        residuals = np.random.normal(0, 1e-6, n_toas)
        errors = np.ones(n_toas) * 1e-7
        freqs = np.random.uniform(100, 2000, n_toas)
        flags = {}

        psr = MockPulsar(toas, residuals, errors, freqs, flags, "mock")

        ra = np.pi / 4  # 45 degrees
        dec = np.pi / 6  # 30 degrees
        psr.set_position(ra, dec)

        assert psr._raj == ra
        assert psr._decj == dec
        assert psr._pos_t.shape == (n_toas, 3)

    @pytest.mark.skipif(not hasattr(pytest, "importorskip"), reason="Astropy test")
    def test_astrometry_parameters(self):
        """Test astrometry parameter setup."""
        try:
            import astropy  # noqa: F401
        except ImportError:
            pytest.skip("Astropy not available")

        n_toas = 40
        toas = np.linspace(50000, 60000, n_toas) * 86400
        residuals = np.random.normal(0, 1e-6, n_toas)
        errors = np.ones(n_toas) * 1e-7
        freqs = np.random.uniform(100, 2000, n_toas)
        flags = {}

        psr = MockPulsar(toas, residuals, errors, freqs, flags, "mock", astrometry=True)

        # Check astrometry parameters are in fitpars
        astrometry_params = ["RAJ", "DECJ", "PMRA", "PMDEC", "PX"]
        for param in astrometry_params:
            assert param in psr.fitpars

    def test_astrometry_without_astropy(self):
        """Test astrometry parameter setup without astropy."""
        with patch("metapulsar.mockpulsar.ASTROPY_AVAILABLE", False):
            n_toas = 20
            toas = np.linspace(50000, 60000, n_toas) * 86400
            residuals = np.random.normal(0, 1e-6, n_toas)
            errors = np.ones(n_toas) * 1e-7
            freqs = np.random.uniform(100, 2000, n_toas)
            flags = {}

            psr = MockPulsar(
                toas, residuals, errors, freqs, flags, "mock", astrometry=True
            )

            # Should not have astrometry parameters
            astrometry_params = ["RAJ", "DECJ", "PMRA", "PMDEC", "PX"]
            for param in astrometry_params:
                assert param not in psr.fitpars


class TestMockPulsarConvenience:
    """Test convenience functions."""

    def test_create_mock_pulsar(self):
        """Test create_mock_pulsar convenience function."""
        n_toas = 35
        toas = np.linspace(50000, 60000, n_toas) * 86400
        residuals = np.random.normal(0, 1e-6, n_toas)
        errors = np.ones(n_toas) * 1e-7
        freqs = np.random.uniform(100, 2000, n_toas)
        flags = {"telescope": np.array(["GBT"] * n_toas)}

        psr = create_mock_pulsar(
            toas, residuals, errors, freqs, flags, "GBT", "test_psr"
        )

        assert isinstance(psr, MockPulsar)
        assert psr.name == "test_psr"
        assert len(psr._toas) == n_toas


class TestMockUtils:
    """Test utility functions."""

    def test_create_astrometry_model(self):
        """Test astrometry model creation."""
        ra = np.pi / 3
        dec = np.pi / 4
        pmra = 10.0
        pmdec = -5.0
        px = 2.0

        model = create_astrometry_model(ra, dec, pmra, pmdec, px)

        assert "RAJ" in model
        assert "DECJ" in model
        assert "PMRA" in model
        assert "PMDEC" in model
        assert "PX" in model
        assert model["RAJ"] == ra
        assert model["DECJ"] == dec
        assert model["PMRA"] == pmra
        assert model["PMDEC"] == pmdec
        assert model["PX"] == px

    def test_convert_astrometry_units(self):
        """Test astrometry unit conversion."""
        params = {
            "RAJ": np.pi / 4,  # 45 degrees
            "DECJ": np.pi / 6,  # 30 degrees
            "PMRA": 10.0,
            "PMDEC": -5.0,
        }

        # Convert radians to degrees
        converted = convert_astrometry_units(params, "rad", "deg")
        assert abs(converted["RAJ"] - 45.0) < 1e-10
        assert abs(converted["DECJ"] - 30.0) < 1e-10

        # Convert back to radians
        back_converted = convert_astrometry_units(converted, "deg", "rad")
        assert abs(back_converted["RAJ"] - params["RAJ"]) < 1e-10
        assert abs(back_converted["DECJ"] - params["DECJ"]) < 1e-10

    def test_create_mock_flags(self):
        """Test mock flags creation."""
        n_toas = 50
        flags = create_mock_flags(
            n_toas,
            telescope="GBT",
            backend="GUPPI",
            band="L",
            custom_flag=np.ones(n_toas),
        )

        assert len(flags["telescope"]) == n_toas
        assert len(flags["backend"]) == n_toas
        assert len(flags["band"]) == n_toas
        assert len(flags["custom_flag"]) == n_toas
        assert np.all(flags["telescope"] == "GBT")
        assert np.all(flags["backend"] == "GUPPI")
        assert np.all(flags["band"] == "L")
        assert np.all(flags["custom_flag"] == 1)

    def test_create_mock_timing_data(self):
        """Test mock timing data creation."""
        n_toas = 100
        toas, residuals, errors, freqs = create_mock_timing_data(n_toas)

        assert len(toas) == n_toas
        assert len(residuals) == n_toas
        assert len(errors) == n_toas
        assert len(freqs) == n_toas

        # Check data properties
        assert np.all(np.isfinite(toas))
        assert np.all(np.isfinite(residuals))
        assert np.all(errors > 0)
        assert np.all(freqs > 0)

        # Check TOAs are sorted
        assert np.all(np.diff(toas) >= 0)

    def test_validate_mock_pulsar_data(self):
        """Test data validation."""
        n_toas = 30

        # Valid data
        toas = np.linspace(50000, 60000, n_toas) * 86400
        residuals = np.random.normal(0, 1e-6, n_toas)
        errors = np.ones(n_toas) * 1e-7
        freqs = np.random.uniform(100, 2000, n_toas)
        flags = {"telescope": np.array(["GBT"] * n_toas)}

        assert validate_mock_pulsar_data(toas, residuals, errors, freqs, flags)

        # Invalid data - wrong length
        assert not validate_mock_pulsar_data(toas, residuals[:-1], errors, freqs)

        # Invalid data - negative errors
        errors_invalid = errors.copy()
        errors_invalid[0] = -1.0
        assert not validate_mock_pulsar_data(toas, residuals, errors_invalid, freqs)

        # Invalid data - negative frequencies
        freqs_invalid = freqs.copy()
        freqs_invalid[0] = -100.0
        assert not validate_mock_pulsar_data(toas, residuals, errors, freqs_invalid)


class TestMockPulsarIntegration:
    """Test MockPulsar integration with Enterprise."""

    def test_enterprise_compatibility(self):
        """Test that MockPulsar is compatible with Enterprise BasePulsar."""
        n_toas = 25
        toas = np.linspace(50000, 60000, n_toas) * 86400
        residuals = np.random.normal(0, 1e-6, n_toas)
        errors = np.ones(n_toas) * 1e-7
        freqs = np.random.uniform(100, 2000, n_toas)
        flags = {}

        psr = MockPulsar(toas, residuals, errors, freqs, flags, "mock")

        # Check that it has all required BasePulsar attributes
        required_attrs = [
            "_toas",
            "_residuals",
            "_toaerrs",
            "_freqs",
            "_flags",
            "_telescope",
            "name",
            "fitpars",
            "setpars",
        ]

        for attr in required_attrs:
            assert hasattr(psr, attr), f"Missing attribute: {attr}"

        # Check that sort_data method works
        psr.sort_data()

        assert np.all(np.diff(psr._toas) >= 0)

    def test_enterprise_signals_compatibility(self):
        """Test compatibility with Enterprise signals."""
        try:
            from enterprise.signals import signal_base  # noqa: F401
        except ImportError:
            pytest.skip("Enterprise signals not available")

        n_toas = 20
        toas = np.linspace(50000, 60000, n_toas) * 86400
        residuals = np.random.normal(0, 1e-6, n_toas)
        errors = np.ones(n_toas) * 1e-7
        freqs = np.random.uniform(100, 2000, n_toas)
        flags = {}

        psr = MockPulsar(toas, residuals, errors, freqs, flags, "mock")

        # Test that we can create a basic signal
        # This is a minimal test - more comprehensive testing would require
        # setting up proper Enterprise signal infrastructure
        assert hasattr(psr, "_toas")
        assert hasattr(psr, "_residuals")
        assert hasattr(psr, "_freqs")
