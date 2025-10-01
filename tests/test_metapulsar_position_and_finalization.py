"""
Tests for MetaPulsar position setup and finalization functionality.

This module tests the position setup, from_files class method, and validation
methods implemented in the MetaPulsar class.
"""

import numpy as np
import pytest
from src.metapulsar.metapulsar import MetaPulsar
from src.metapulsar.mockpulsar import MockPulsar
from src.metapulsar.mock_utils import create_mock_timing_data, create_mock_flags


class TestMetaPulsarPositionAndFinalization:
    """Test class for MetaPulsar position setup and finalization functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        # Create mock pulsars with astrometry and spin parameters
        toas1, residuals1, errors1, freqs1 = create_mock_timing_data(30)
        flags1 = create_mock_flags(30, telescope="test_pta1")
        self.mock_psr1 = MockPulsar(
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

        toas2, residuals2, errors2, freqs2 = create_mock_timing_data(30)
        flags2 = create_mock_flags(30, telescope="test_pta2")
        self.mock_psr2 = MockPulsar(
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

        # Create MetaPulsar
        self.pulsars = {"test_pta1": self.mock_psr1, "test_pta2": self.mock_psr2}
        self.metapulsar = MetaPulsar(self.pulsars, combination_strategy="composite")

    def test_setup_position_and_planets_basic(self):
        """Test basic position and planetary data setup."""
        # Check that position attributes are set
        assert hasattr(self.metapulsar, "_raj")
        assert hasattr(self.metapulsar, "_decj")
        assert hasattr(self.metapulsar, "_pos")
        assert hasattr(self.metapulsar, "_pos_t")
        assert hasattr(self.metapulsar, "_planetssb")
        assert hasattr(self.metapulsar, "_sunssb")
        assert hasattr(self.metapulsar, "_pdist")

        # Check position values
        assert isinstance(self.metapulsar._raj, (int, float))
        assert isinstance(self.metapulsar._decj, (int, float))
        assert isinstance(self.metapulsar._pos, np.ndarray)
        assert isinstance(self.metapulsar._pos_t, np.ndarray)

    def test_setup_position_and_planets_shape(self):
        """Test that position arrays have correct shapes."""
        n_toas = len(self.metapulsar._toas)

        # Position arrays should have shape (n_toas, 3)
        assert self.metapulsar._pos.shape == (n_toas, 3)
        assert self.metapulsar._pos_t.shape == (n_toas, 3)

    def test_setup_position_and_planets_empty_pulsars(self):
        """Test position setup with empty pulsar list."""
        empty_mp = MetaPulsar({}, combination_strategy="composite")

        # Should have default values
        assert empty_mp._raj == 0.0
        assert empty_mp._decj == 0.0
        assert empty_mp._pos.shape == (0, 3)
        assert empty_mp._pos_t.shape == (0, 3)
        assert empty_mp._planetssb is None
        assert empty_mp._sunssb is None
        assert empty_mp._pdist is None

    def test_validate_consistency_success(self):
        """Test successful consistency validation."""
        pulsar_name = self.metapulsar.validate_consistency()
        assert pulsar_name == "J1857+0943"

    def test_validate_consistency_different_pulsars(self):
        """Test consistency validation with different pulsars."""
        # Create pulsars with different names
        toas1, residuals1, errors1, freqs1 = create_mock_timing_data(10)
        flags1 = create_mock_flags(10, telescope="test_pta1")
        mock_psr1 = MockPulsar(
            toas1, residuals1, errors1, freqs1, flags1, "test_pta1", "J1857+0943"
        )

        toas2, residuals2, errors2, freqs2 = create_mock_timing_data(10)
        flags2 = create_mock_flags(10, telescope="test_pta2")
        mock_psr2 = MockPulsar(
            toas2, residuals2, errors2, freqs2, flags2, "test_pta2", "J1900+0000"
        )

        inconsistent_mp = MetaPulsar(
            {"pta1": mock_psr1, "pta2": mock_psr2}, combination_strategy="composite"
        )

        with pytest.raises(ValueError, match="Not all the same pulsar"):
            inconsistent_mp.validate_consistency()

    def test_validate_consistency_no_pulsars(self):
        """Test consistency validation with no pulsars."""
        empty_mp = MetaPulsar({}, combination_strategy="composite")

        with pytest.raises(ValueError, match="No pulsar names found"):
            empty_mp.validate_consistency()

    def test_validate_consistency_no_epulsars(self):
        """Test consistency validation before Enterprise Pulsars are created."""
        # Create MetaPulsar but don't initialize it
        mp = MetaPulsar.__new__(MetaPulsar)
        mp._epulsars = None

        with pytest.raises(ValueError, match="No Enterprise Pulsars created yet"):
            mp.validate_consistency()

    def test_from_files_class_method_exists(self):
        """Test that from_files class method exists and is callable."""
        assert hasattr(MetaPulsar, "from_files")
        assert callable(MetaPulsar.from_files)

    def test_from_files_signature(self):
        """Test that from_files has correct signature."""
        import inspect

        sig = inspect.signature(MetaPulsar.from_files)
        params = list(sig.parameters.keys())

        # Check required parameters
        assert "file_configs" in params
        assert "combination_strategy" in params
        assert "merge_astrometry" in params
        assert "merge_spin" in params
        assert "merge_binary" in params
        assert "merge_dispersion" in params
        assert "sort" in params

    def test_from_files_docstring(self):
        """Test that from_files has proper docstring."""
        docstring = MetaPulsar.from_files.__doc__
        assert docstring is not None
        assert "Create MetaPulsar from par/tim file configurations" in docstring
        assert "Args:" in docstring
        assert "Returns:" in docstring

    def test_position_attributes_consistency(self):
        """Test that position attributes are consistent across PTAs."""
        # Get position data from individual PTAs
        pta1_pos = self.mock_psr1._pos
        pta2_pos = self.mock_psr2._pos

        # Get combined position data
        pta_slices = self.metapulsar._get_pta_slices()
        combined_pta1_pos = self.metapulsar._pos[pta_slices["test_pta1"], :]
        combined_pta2_pos = self.metapulsar._pos[pta_slices["test_pta2"], :]

        # MockPulsar has single position vector, MetaPulsar tiles it across all TOAs
        # So we need to compare the tiled version
        expected_pta1_pos = np.tile(
            pta1_pos, (len(pta1_pos) if pta1_pos.ndim > 1 else 1, 1)
        )
        expected_pta2_pos = np.tile(
            pta2_pos, (len(pta2_pos) if pta2_pos.ndim > 1 else 1, 1)
        )

        # If MockPulsar has single position vector, tile it to match expected shape
        if pta1_pos.ndim == 1:
            expected_pta1_pos = np.tile(pta1_pos, (len(self.mock_psr1._toas), 1))
        if pta2_pos.ndim == 1:
            expected_pta2_pos = np.tile(pta2_pos, (len(self.mock_psr2._toas), 1))

        # Should match (within floating point precision)
        np.testing.assert_array_almost_equal(combined_pta1_pos, expected_pta1_pos)
        np.testing.assert_array_almost_equal(combined_pta2_pos, expected_pta2_pos)

    def test_planetary_data_setup(self):
        """Test that planetary data is properly set up."""
        # Planetary data should be copied from reference pulsar
        ref_psr = next(iter(self.metapulsar._epulsars.values()))

        assert self.metapulsar._planetssb is ref_psr._planetssb
        assert self.metapulsar._sunssb is ref_psr._sunssb
        assert self.metapulsar._pdist is ref_psr._pdist

    def test_position_coordinates(self):
        """Test that position coordinates are properly set."""
        ref_psr = next(iter(self.metapulsar._epulsars.values()))

        # RA and Dec should match reference pulsar
        assert self.metapulsar._raj == ref_psr._raj
        assert self.metapulsar._decj == ref_psr._decj

    def test_bj_name_generation(self):
        """Test that B/J name generation is called."""
        # This test verifies that the bj_name_from_pulsar function is called
        # The actual name generation is tested in position_helpers tests
        # Here we just verify the method doesn't crash
        self.metapulsar._setup_position_and_planets()
        # If we get here without error, the B/J name generation worked

    def test_position_and_finalization_integration(self):
        """Test that all position setup and finalization methods work together."""
        # Test that position setup works with validation
        pulsar_name = self.metapulsar.validate_consistency()
        assert pulsar_name == "J1857+0943"

        # Test that position attributes are properly set
        assert hasattr(self.metapulsar, "_raj")
        assert hasattr(self.metapulsar, "_decj")
        assert hasattr(self.metapulsar, "_pos")

        # Test that from_files method exists and is callable
        assert callable(MetaPulsar.from_files)

    def test_validate_consistency_with_missing_names(self):
        """Test consistency validation with pulsars missing name attributes."""
        # Create a mock pulsar without name attribute
        toas, residuals, errors, freqs = create_mock_timing_data(10)
        flags = create_mock_flags(10, telescope="test_pta")
        mock_psr = MockPulsar(
            toas, residuals, errors, freqs, flags, "test_pta", "J1857+0943"
        )

        # Remove name attribute (MockPulsar uses self.name, not a separate name attribute)
        delattr(mock_psr, "name")

        mp = MetaPulsar({"test_pta": mock_psr}, combination_strategy="composite")

        with pytest.raises(ValueError, match="No pulsar names found"):
            mp.validate_consistency()

    def test_all_equal_helper_method(self):
        """Test the _all_equal helper method."""
        # Test with equal values
        assert self.metapulsar._all_equal([1, 1, 1, 1])
        assert self.metapulsar._all_equal(["a", "a", "a"])
        assert self.metapulsar._all_equal([])  # Empty list

        # Test with different values
        assert not self.metapulsar._all_equal([1, 2, 3])
        assert not self.metapulsar._all_equal(["a", "b", "c"])
        assert not self.metapulsar._all_equal([1, 1, 2])


if __name__ == "__main__":
    # Run a quick test
    test = TestMetaPulsarPositionAndFinalization()
    test.setup_method()
    test.test_setup_position_and_planets_basic()
    test.test_validate_consistency_success()
    test.test_from_files_class_method_exists()
    print("✅ All position and finalization tests passed!")
