"""
Tests for MetaPulsar data combination functionality.

This module tests the data combination methods:
- _combine_timing_data()
- _combine_flags()
- _get_pta_slices()
"""

import numpy as np
import pytest

from metapulsar.metapulsar import MetaPulsar
from metapulsar.mockpulsar import MockPulsar, create_libstempo_adapter
from metapulsar.mockpulsar import create_mock_timing_data, create_mock_flags


class TestMetaPulsarDataCombination:
    """Tests for MetaPulsar data combination functionality."""

    def _create_adapted_pulsars(self, mock_pulsars):
        """Helper function to convert MockPulsar objects to libstempo adapters."""
        return {pta: create_libstempo_adapter(psr) for pta, psr in mock_pulsars.items()}

    @pytest.fixture
    def mock_pulsars(self):
        """Create mock pulsars for testing."""
        # Create two mock pulsars with different data
        toas1, residuals1, errors1, freqs1 = create_mock_timing_data(50)
        flags1 = create_mock_flags(50, telescope="test_pta1")
        mock_psr1 = MockPulsar(
            toas1,
            residuals1,
            errors1,
            freqs1,
            flags1,
            "test_pta1",
            "J1857+0943",
            astrometry=True,
            spin=True,
        )

        toas2, residuals2, errors2, freqs2 = create_mock_timing_data(50)
        flags2 = create_mock_flags(50, telescope="test_pta2")
        mock_psr2 = MockPulsar(
            toas2,
            residuals2,
            errors2,
            freqs2,
            flags2,
            "test_pta2",
            "J1857+0943",
            astrometry=True,
            spin=True,
        )

        return {"test_pta1": mock_psr1, "test_pta2": mock_psr2}

    def test_timing_data_combination_basic(self, mock_pulsars):
        """Test basic timing data combination."""
        adapted_pulsars = self._create_adapted_pulsars(mock_pulsars)
        metapulsar = MetaPulsar(adapted_pulsars, combination_strategy="composite")

        # Check that data is properly combined
        assert len(metapulsar._toas) == 100  # 50 + 50
        assert len(metapulsar._residuals) == 100
        assert len(metapulsar._toaerrs) == 100
        assert len(metapulsar._ssbfreqs) == 100
        assert len(metapulsar._telescope) == 100

        # Check data types
        assert isinstance(metapulsar._toas, np.ndarray)
        assert isinstance(metapulsar._residuals, np.ndarray)
        assert isinstance(metapulsar._toaerrs, np.ndarray)
        assert isinstance(metapulsar._ssbfreqs, np.ndarray)
        assert isinstance(metapulsar._telescope, np.ndarray)

    def test_timing_data_combination_ordering(self, mock_pulsars):
        """Test that timing data is combined in correct order."""
        adapted_pulsars = self._create_adapted_pulsars(mock_pulsars)
        metapulsar = MetaPulsar(adapted_pulsars, combination_strategy="composite")

        # Check that first 50 elements come from first PTA
        # Compare seconds with seconds (both MockPulsar and MetaPulsar store TOAs in seconds)
        # Use allclose for floating-point comparison due to precision differences
        assert np.allclose(metapulsar._toas[:50], mock_pulsars["test_pta1"]._toas)

        # Check that last 50 elements come from second PTA
        assert np.allclose(metapulsar._toas[50:], mock_pulsars["test_pta2"]._toas)

    def test_flag_combination(self, mock_pulsars):
        """Test flag combination."""
        # Convert MockPulsar objects to libstempo adapters
        adapted_pulsars = {
            pta: create_libstempo_adapter(psr) for pta, psr in mock_pulsars.items()
        }
        metapulsar = MetaPulsar(adapted_pulsars, combination_strategy="composite")

        # Check that flags is a structured numpy array
        assert isinstance(metapulsar._flags, np.ndarray)
        assert metapulsar._flags.dtype.names is not None
        assert "telescope" in metapulsar._flags.dtype.names
        assert "backend" in metapulsar._flags.dtype.names
        assert "pta_dataset" in metapulsar._flags.dtype.names
        assert "timing_package" in metapulsar._flags.dtype.names
        assert "pta" in metapulsar._flags.dtype.names
        assert len(metapulsar._flags) == 100

        # Check flag values
        assert np.array_equal(
            metapulsar._flags["telescope"][:50],
            mock_pulsars["test_pta1"]._flags["telescope"],
        )
        assert np.array_equal(
            metapulsar._flags["telescope"][50:],
            mock_pulsars["test_pta2"]._flags["telescope"],
        )

        # Check PTA-specific flags
        assert np.all(metapulsar._flags["pta_dataset"][:50] == "test_pta1")
        assert np.all(metapulsar._flags["pta_dataset"][50:] == "test_pta2")
        assert np.all(metapulsar._flags["pta"][:50] == "test_pta1")
        assert np.all(metapulsar._flags["pta"][50:] == "test_pta2")

    def test_pta_slice_calculation(self, mock_pulsars):
        """Test PTA slice calculation."""
        adapted_pulsars = self._create_adapted_pulsars(mock_pulsars)
        metapulsar = MetaPulsar(adapted_pulsars, combination_strategy="composite")
        slices = metapulsar._get_pta_slices()

        # Check that slices are correct
        assert "test_pta1" in slices
        assert "test_pta2" in slices

        # Check slice ranges
        assert slices["test_pta1"] == slice(0, 50)
        assert slices["test_pta2"] == slice(50, 100)

    def test_pta_slice_data_access(self, mock_pulsars):
        """Test that PTA slices correctly access data."""
        adapted_pulsars = self._create_adapted_pulsars(mock_pulsars)
        metapulsar = MetaPulsar(adapted_pulsars, combination_strategy="composite")
        slices = metapulsar._get_pta_slices()

        # Test accessing data through slices
        pta1_toas = metapulsar._toas[slices["test_pta1"]]
        pta2_toas = metapulsar._toas[slices["test_pta2"]]

        # Should match original data (compare seconds with seconds)
        # Use allclose for floating-point comparison due to precision differences
        assert np.allclose(pta1_toas, mock_pulsars["test_pta1"]._toas)
        assert np.allclose(pta2_toas, mock_pulsars["test_pta2"]._toas)

    def test_timing_data_combination_empty_pulsars(self):
        """Test timing data combination with empty pulsar list."""
        # Empty pulsars should raise an exception
        with pytest.raises(StopIteration):
            MetaPulsar({}, combination_strategy="composite")

    def test_timing_data_combination_single_pulsar(self):
        """Test timing data combination with single pulsar."""
        toas, residuals, errors, freqs = create_mock_timing_data(25)
        flags = create_mock_flags(25, telescope="single_pta")
        mock_psr = MockPulsar(
            toas,
            residuals,
            errors,
            freqs,
            flags,
            "single_pta",
            "J1857+0943",
            astrometry=True,
            spin=True,
        )

        # Use adapter for MetaPulsar creation
        adapted_pulsar = create_libstempo_adapter(mock_psr)
        metapulsar = MetaPulsar(
            {"single_pta": adapted_pulsar}, combination_strategy="composite"
        )

        # Check that data is preserved (compare seconds with seconds)
        assert len(metapulsar._toas) == 25
        # Use allclose for floating-point comparison due to precision differences
        assert np.allclose(metapulsar._toas, mock_psr._toas)
        assert np.array_equal(metapulsar._residuals, mock_psr._residuals)

    def test_timing_data_combination_different_sizes(self):
        """Test timing data combination with different PTA sizes."""
        # Create pulsars with different sizes
        toas1, residuals1, errors1, freqs1 = create_mock_timing_data(30)
        flags1 = create_mock_flags(30, telescope="small_pta")
        mock_psr1 = MockPulsar(
            toas1,
            residuals1,
            errors1,
            freqs1,
            flags1,
            "small_pta",
            "J1857+0943",
            astrometry=True,
            spin=True,
        )

        toas2, residuals2, errors2, freqs2 = create_mock_timing_data(70)
        flags2 = create_mock_flags(70, telescope="large_pta")
        mock_psr2 = MockPulsar(
            toas2,
            residuals2,
            errors2,
            freqs2,
            flags2,
            "large_pta",
            "J1857+0943",
            astrometry=True,
            spin=True,
        )

        # Use adapters for MetaPulsar creation
        adapted_pulsars = {
            "small_pta": create_libstempo_adapter(mock_psr1),
            "large_pta": create_libstempo_adapter(mock_psr2),
        }
        metapulsar = MetaPulsar(adapted_pulsars, combination_strategy="composite")

        # Check total size
        assert len(metapulsar._toas) == 100  # 30 + 70

        # Check slices
        slices = metapulsar._get_pta_slices()
        assert slices["small_pta"] == slice(0, 30)
        assert slices["large_pta"] == slice(30, 100)

    def test_timing_package_detection(self, mock_pulsars):
        """Test timing package detection."""
        adapted_pulsars = self._create_adapted_pulsars(mock_pulsars)
        metapulsar = MetaPulsar(adapted_pulsars, combination_strategy="composite")

        for pta, psr in mock_pulsars.items():
            package = metapulsar._get_timing_package(psr)
            assert package == "unknown"

    def test_timing_data_frequency_handling(self, mock_pulsars):
        """Test that frequency data is properly handled."""
        adapted_pulsars = self._create_adapted_pulsars(mock_pulsars)
        metapulsar = MetaPulsar(adapted_pulsars, combination_strategy="composite")

        # Check that frequencies are combined correctly
        assert len(metapulsar._ssbfreqs) == 100
        assert isinstance(metapulsar._ssbfreqs, np.ndarray)

        # Check that frequencies match original data
        pta1_freqs = mock_pulsars["test_pta1"]._freqs
        pta2_freqs = mock_pulsars["test_pta2"]._freqs
        expected_freqs = np.concatenate([pta1_freqs, pta2_freqs])
        # Use allclose for floating-point comparison due to precision differences
        assert np.allclose(metapulsar._ssbfreqs, expected_freqs)

    def test_timing_data_consistency(self, mock_pulsars):
        """Test that all timing data arrays have consistent lengths."""
        adapted_pulsars = self._create_adapted_pulsars(mock_pulsars)
        metapulsar = MetaPulsar(adapted_pulsars, combination_strategy="composite")

        # All arrays should have the same length
        arrays = [
            metapulsar._toas,
            metapulsar._residuals,
            metapulsar._toaerrs,
            metapulsar._ssbfreqs,
            metapulsar._telescope,
        ]

        lengths = [len(arr) for arr in arrays]
        assert all(
            length == lengths[0] for length in lengths
        ), f"Inconsistent array lengths: {lengths}"

    def test_flag_structure(self, mock_pulsars):
        """Test that combined flags have correct structure."""
        adapted_pulsars = self._create_adapted_pulsars(mock_pulsars)
        metapulsar = MetaPulsar(adapted_pulsars, combination_strategy="composite")

        # Flags should be a structured numpy array
        assert isinstance(metapulsar._flags, np.ndarray)
        assert metapulsar._flags.dtype.names is not None

        # Check that all expected flags are present
        expected_flags = [
            "telescope",
            "backend",
            "pta_dataset",
            "timing_package",
            "pta",
        ]
        for flag_name in expected_flags:
            assert flag_name in metapulsar._flags.dtype.names

        # Check array length
        assert len(metapulsar._flags) == 100

    def test_data_combination_integration(self, mock_pulsars):
        """End-to-end integration test for data combination functionality."""
        adapted_pulsars = self._create_adapted_pulsars(mock_pulsars)
        metapulsar = MetaPulsar(adapted_pulsars, combination_strategy="composite")

        # Test that all data combination methods work together
        slices = metapulsar._get_pta_slices()

        # Test data access through slices

        for pta, psr in mock_pulsars.items():
            slice_obj = slices[pta]

            # Check TOAs (compare seconds with seconds)
            # Use allclose for floating-point comparison due to precision differences
            assert np.allclose(metapulsar._toas[slice_obj], psr._toas)

            # Check residuals
            assert np.array_equal(metapulsar._residuals[slice_obj], psr._residuals)

            # Check telescope
            assert np.array_equal(metapulsar._telescope[slice_obj], psr._telescope)

        print("✅ Data combination integration test passed!")
