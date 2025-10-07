"""
Unit tests for LibstempoMockPulsarAdapter.

This module tests the libstempo adapter functionality that allows MockPulsar
to be used as a raw timing object in tests.
"""

import numpy as np
import pytest
from metapulsar.mockpulsar import (
    MockPulsar,
    LibstempoMockPulsarAdapter,
    MockParameter,
    create_libstempo_adapter,
)
from metapulsar.mockpulsar import create_mock_timing_data, create_mock_flags


class TestMockParameter:
    """Test MockParameter class functionality."""

    def test_basic_initialization(self):
        """Test basic MockParameter initialization."""
        param = MockParameter(1.5, 0.1)
        assert param.val == 1.5
        assert param.err == 0.1

    def test_default_error(self):
        """Test MockParameter with default error."""
        param = MockParameter(2.0)
        assert param.val == 2.0
        assert param.err == 0.0


class TestLibstempoMockPulsarAdapter:
    """Test LibstempoMockPulsarAdapter class functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        # Create mock pulsar with astrometry and spin parameters
        toas, residuals, errors, freqs = create_mock_timing_data(30)
        flags = create_mock_flags(30, telescope="test_pta")
        self.mock_psr = MockPulsar(
            toas,
            residuals,
            errors,
            freqs,
            flags,
            "test_pta",
            "J1857+0943",
            astrometry=True,
            spin=True,
        )
        self.adapter = LibstempoMockPulsarAdapter(self.mock_psr)

    def test_initialization(self):
        """Test adapter initialization."""
        assert self.adapter._mock is self.mock_psr
        assert self.adapter.name == "J1857+0943"

    def test_toas_conversion(self):
        """Test TOAs conversion from seconds to days."""
        toas_days = self.adapter.toas()
        expected_days = self.mock_psr._toas / 86400  # Convert seconds to days
        np.testing.assert_array_almost_equal(toas_days, expected_days)

    def test_stoas_conversion(self):
        """Test station TOAs conversion from seconds to days."""
        stoas_days = self.adapter.stoas
        expected_days = self.mock_psr._toas / 86400  # Convert seconds to days
        np.testing.assert_array_almost_equal(stoas_days, expected_days)

    def test_residuals(self):
        """Test residuals method."""
        residuals = self.adapter.residuals()
        np.testing.assert_array_equal(residuals, self.mock_psr._residuals)

    def test_toaerrs_conversion(self):
        """Test TOA errors conversion from seconds to microseconds."""
        toaerrs_us = self.adapter.toaerrs
        expected_us = self.mock_psr._toaerrs * 1e6  # Convert to microseconds
        np.testing.assert_array_almost_equal(toaerrs_us, expected_us)

    def test_designmatrix(self):
        """Test design matrix method."""
        designmatrix = self.adapter.designmatrix()
        np.testing.assert_array_equal(designmatrix, self.mock_psr._designmatrix)

    def test_ssbfreqs_conversion(self):
        """Test SSB frequencies conversion from MHz to Hz."""
        freqs_hz = self.adapter.ssbfreqs()
        expected_hz = self.mock_psr._freqs * 1e6  # Convert to Hz
        np.testing.assert_array_almost_equal(freqs_hz, expected_hz)

    def test_telescope(self):
        """Test telescope method."""
        telescope = self.adapter.telescope()
        expected = self.mock_psr._telescope.astype("S")
        np.testing.assert_array_equal(telescope, expected)

    def test_pars_fit(self):
        """Test pars method for fitted parameters."""
        fit_pars = self.adapter.pars("fit")
        # Adapter excludes Offset parameter (libstempo quirk)
        expected_pars = [p for p in self.mock_psr.fitpars if p != "Offset"]
        assert fit_pars == tuple(expected_pars)

    def test_pars_set(self):
        """Test pars method for set parameters."""
        set_pars = self.adapter.pars("set")
        # Adapter excludes Offset parameter (libstempo quirk)
        expected_pars = [p for p in self.mock_psr.setpars if p != "Offset"]
        assert set_pars == tuple(expected_pars)

    def test_parameter_access(self):
        """Test parameter access via __getitem__."""
        # Test mapped parameters
        raj_param = self.adapter["RAJ"]
        assert isinstance(raj_param, MockParameter)
        assert raj_param.val == self.mock_psr._raj
        assert raj_param.err == 0.0

        f0_param = self.adapter["F0"]
        assert isinstance(f0_param, MockParameter)
        assert f0_param.val == self.mock_psr._f0
        assert f0_param.err == 0.0

    def test_parameter_access_unmapped(self):
        """Test parameter access for unmapped parameters."""
        # Test unmapped parameter (should use lowercase with underscore)
        unknown_param = self.adapter["UNKNOWN"]
        assert isinstance(unknown_param, MockParameter)
        assert unknown_param.val == 0.0  # Default value
        assert unknown_param.err == 0.0

    def test_flags(self):
        """Test flags method."""
        flags = self.adapter.flags()
        expected_flags = (
            list(self.mock_psr._flags.dtype.names)
            if self.mock_psr._flags.dtype.names
            else []
        )
        assert flags == expected_flags

    def test_flagvals(self):
        """Test flagvals method."""
        flagvals = self.adapter.flagvals("telescope")
        expected_flagvals = self.mock_psr._flags["telescope"]
        np.testing.assert_array_equal(flagvals, expected_flagvals)

    def test_psrPos(self):
        """Test psrPos property."""
        pos = self.adapter.psrPos
        np.testing.assert_array_equal(pos, self.mock_psr._pos_t)

    def test_name(self):
        """Test name property."""
        assert self.adapter.name == self.mock_psr.name

    def test_formbats(self):
        """Test formbats method (should be no-op)."""
        # Should not raise any exception
        self.adapter.formbats()

    def test_planetary_data(self):
        """Test planetary data methods."""
        n_toas = len(self.mock_psr._toas)

        # Test all planetary SSB methods
        planets = [
            "mercury",
            "venus",
            "earth",
            "mars",
            "jupiter",
            "saturn",
            "uranus",
            "neptune",
            "pluto",
            "sun",
        ]

        for planet in planets:
            method_name = f"{planet}_ssb"
            data = getattr(self.adapter, method_name)
            assert data.shape == (n_toas, 6)
            np.testing.assert_array_equal(data, np.zeros((n_toas, 6)))


class TestCreateLibstempoAdapter:
    """Test create_libstempo_adapter convenience function."""

    def test_create_adapter(self):
        """Test adapter creation function."""
        toas, residuals, errors, freqs = create_mock_timing_data(20)
        flags = create_mock_flags(20, telescope="test")
        mock_psr = MockPulsar(
            toas,
            residuals,
            errors,
            freqs,
            flags,
            "test",
            "test_psr",
            astrometry=True,
            spin=True,
        )

        adapter = create_libstempo_adapter(mock_psr)
        assert isinstance(adapter, LibstempoMockPulsarAdapter)
        assert adapter._mock is mock_psr


class TestAdapterIntegration:
    """Test adapter integration with Tempo2Pulsar."""

    def test_tempo2pulsar_creation(self):
        """Test that Tempo2Pulsar can be created from adapter."""
        try:
            from enterprise.pulsar import Tempo2Pulsar
        except ImportError:
            pytest.skip("Enterprise not available")

        toas, residuals, errors, freqs = create_mock_timing_data(20)
        flags = create_mock_flags(20, telescope="test")
        mock_psr = MockPulsar(
            toas,
            residuals,
            errors,
            freqs,
            flags,
            "test",
            "test_psr",
            astrometry=True,
            spin=True,
        )

        adapter = create_libstempo_adapter(mock_psr)

        # This should not raise an exception
        tempo2_psr = Tempo2Pulsar(adapter, planets=True)
        assert tempo2_psr is not None
        assert hasattr(tempo2_psr, "name")
        assert tempo2_psr.name == "test_psr"

    def test_unit_conversions(self):
        """Test that unit conversions are correct."""
        toas_sec = np.array([50000.0, 50001.0, 50002.0]) * 86400  # 3 days in seconds
        residuals = np.array([1e-6, 2e-6, 3e-6])  # 1-3 microseconds
        errors = np.array([1e-7, 2e-7, 3e-7])  # 0.1-0.3 microseconds
        freqs = np.array([100.0, 200.0, 300.0])  # 100-300 MHz

        mock_psr = MockPulsar(
            toas_sec,
            residuals,
            errors,
            freqs,
            {},
            "test",
            "test_psr",
            astrometry=True,
            spin=True,
        )
        adapter = LibstempoMockPulsarAdapter(mock_psr)

        toas_days = adapter.toas()
        expected_days = np.array([50000.0, 50001.0, 50002.0])
        np.testing.assert_array_almost_equal(toas_days, expected_days, decimal=10)

        toaerrs_us = adapter.toaerrs
        expected_us = np.array([0.1, 0.2, 0.3])
        np.testing.assert_array_almost_equal(toaerrs_us, expected_us, decimal=10)

        freqs_hz = adapter.ssbfreqs()
        expected_hz = np.array([100000000.0, 200000000.0, 300000000.0])
        np.testing.assert_array_almost_equal(freqs_hz, expected_hz, decimal=10)
