"""
Tests for MetaPulsar design matrix and unit conversion functionality.

This module tests the design matrix construction and unit conversion methods
implemented in the MetaPulsar class.
"""

import numpy as np
from src.metapulsar.metapulsar import MetaPulsar
from src.metapulsar.mockpulsar import MockPulsar, create_libstempo_adapter
from src.metapulsar.mock_utils import create_mock_timing_data, create_mock_flags


class TestMetaPulsarDesignMatrix:
    """Test class for MetaPulsar design matrix functionality."""

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

        # Create MetaPulsar with adapted pulsars
        self.pulsars = {"test_pta1": self.mock_psr1, "test_pta2": self.mock_psr2}
        adapted_pulsars = {
            pta: create_libstempo_adapter(psr) for pta, psr in self.pulsars.items()
        }
        self.metapulsar = MetaPulsar(adapted_pulsars, combination_strategy="composite")

    def test_design_matrix_creation(self):
        """Test that design matrix is created correctly."""
        assert hasattr(self.metapulsar, "_designmatrix")
        assert self.metapulsar._designmatrix.shape == (
            60,
            8,
        )  # 30 + 30 TOAs, 8 parameters
        assert np.count_nonzero(self.metapulsar._designmatrix) > 0

    def test_design_matrix_parameters(self):
        """Test that design matrix has correct parameters."""
        expected_params = ["F0", "F1", "F2", "RAJ", "DECJ", "PMRA", "PMDEC", "PX"]
        assert len(self.metapulsar.fitpars) == 8
        for param in expected_params:
            assert param in self.metapulsar.fitpars

    def test_design_matrix_structure(self):
        """Test design matrix structure and content."""
        dm = self.metapulsar._designmatrix

        # Check that F0 column is all ones (constant term)
        f0_idx = self.metapulsar.fitpars.index("F0")
        assert np.allclose(dm[:, f0_idx], 1.0)

        # Check that F1 column has time dependence
        f1_idx = self.metapulsar.fitpars.index("F1")
        f1_col = dm[:, f1_idx]
        assert not np.allclose(f1_col, 0.0)  # Should have non-zero values
        assert not np.allclose(f1_col, f1_col[0])  # Should vary with time

    def test_design_matrix_pta_slices(self):
        """Test that design matrix correctly handles PTA slices."""
        pta_slices = self.metapulsar._get_pta_slices()

        # Check that slices are correct
        assert "test_pta1" in pta_slices
        assert "test_pta2" in pta_slices

        # Check slice ranges
        assert pta_slices["test_pta1"].start == 0
        assert pta_slices["test_pta1"].stop == 30
        assert pta_slices["test_pta2"].start == 30
        assert pta_slices["test_pta2"].stop == 60

    def test_unit_conversion_coordinate_parameters(self):
        """Test unit conversion for coordinate parameters."""
        import astropy.units as u

        # Test RAJ conversion
        raj_col = np.ones(10)
        converted_raj = self.metapulsar._convert_design_matrix_units(
            raj_col, "RAJ", "tempo2"
        )
        # Should convert from radians to hours using astropy conversion
        expected_factor = (1.0 * u.second / u.radian).to(u.second / u.hourangle).value
        assert np.allclose(converted_raj, raj_col * expected_factor)

        # Test DECJ conversion
        decj_col = np.ones(10)
        converted_decj = self.metapulsar._convert_design_matrix_units(
            decj_col, "DECJ", "tempo2"
        )
        # Should convert from radians to degrees using astropy conversion
        expected_factor_deg = (1.0 * u.second / u.radian).to(u.second / u.deg).value
        assert np.allclose(converted_decj, decj_col * expected_factor_deg)

    def test_unit_conversion_non_coordinate_parameters(self):
        """Test that non-coordinate parameters are not converted."""
        # Test F0 (spin parameter) - should not be converted
        f0_col = np.ones(10)
        converted_f0 = self.metapulsar._convert_design_matrix_units(
            f0_col, "F0", "tempo2"
        )
        assert np.allclose(converted_f0, f0_col)

    def test_design_matrix_column_construction(self):
        """Test individual design matrix column construction."""
        # Test F0 column
        f0_col = self.metapulsar._build_design_matrix_column("F0")
        assert len(f0_col) == 60
        assert np.allclose(f0_col, 1.0)  # F0 should be constant

        # Test F1 column
        f1_col = self.metapulsar._build_design_matrix_column("F1")
        assert len(f1_col) == 60
        assert not np.allclose(f1_col, 0.0)  # Should have non-zero values

    def test_design_matrix_with_different_strategies(self):
        """Test design matrix with different combination strategies."""
        # Test composite strategy
        composite_mp = MetaPulsar(self.pulsars, combination_strategy="composite")
        assert hasattr(composite_mp, "_designmatrix")
        assert composite_mp._designmatrix.shape == (60, 8)

        # Test consistent strategy
        consistent_mp = MetaPulsar(self.pulsars, combination_strategy="consistent")
        assert hasattr(consistent_mp, "_designmatrix")
        assert consistent_mp._designmatrix.shape == (60, 8)

    def test_design_matrix_empty_pulsars(self):
        """Test design matrix with empty pulsar list."""
        empty_mp = MetaPulsar({}, combination_strategy="composite")
        assert hasattr(empty_mp, "_designmatrix")
        assert empty_mp._designmatrix.shape == (0, 0)
        assert len(empty_mp.fitpars) == 0

    def test_timing_package_detection(self):
        """Test timing package detection for MockPulsar."""
        timing_pkg = self.metapulsar._get_timing_package(self.mock_psr1)
        assert timing_pkg == "unknown"  # MockPulsar doesn't have PINT/Tempo2 attributes

    def test_design_matrix_parameter_mapping(self):
        """Test that parameter mapping works correctly."""
        # Check that _fitparameters is properly set up
        assert hasattr(self.metapulsar, "_fitparameters")
        assert len(self.metapulsar._fitparameters) == 8

        # Check that each parameter has mappings for both PTAs
        for param in self.metapulsar.fitpars:
            assert param in self.metapulsar._fitparameters
            assert "test_pta1" in self.metapulsar._fitparameters[param]
            assert "test_pta2" in self.metapulsar._fitparameters[param]

    def test_design_matrix_consistency(self):
        """Test that design matrix is consistent across PTAs."""
        dm = self.metapulsar._designmatrix
        pta_slices = self.metapulsar._get_pta_slices()

        # Check that F0 columns are consistent (should be 1.0 for both PTAs)
        f0_idx = self.metapulsar.fitpars.index("F0")
        f0_pta1 = dm[pta_slices["test_pta1"], f0_idx]
        f0_pta2 = dm[pta_slices["test_pta2"], f0_idx]

        assert np.allclose(f0_pta1, 1.0)
        assert np.allclose(f0_pta2, 1.0)

    def test_design_matrix_astrometry_parameters(self):
        """Test that astrometry parameters are handled correctly."""
        dm = self.metapulsar._designmatrix

        # Check RAJ and DECJ columns have frequency dependence
        raj_idx = self.metapulsar.fitpars.index("RAJ")
        decj_idx = self.metapulsar.fitpars.index("DECJ")

        raj_col = dm[:, raj_idx]
        decj_col = dm[:, decj_idx]

        # Should have non-zero values
        assert not np.allclose(raj_col, 0.0)
        assert not np.allclose(decj_col, 0.0)

    def test_design_matrix_spin_parameters(self):
        """Test that spin parameters are handled correctly."""
        dm = self.metapulsar._designmatrix

        # Check F0, F1, F2 columns
        f0_idx = self.metapulsar.fitpars.index("F0")
        f1_idx = self.metapulsar.fitpars.index("F1")
        f2_idx = self.metapulsar.fitpars.index("F2")

        f0_col = dm[:, f0_idx]
        f1_col = dm[:, f1_idx]
        f2_col = dm[:, f2_idx]

        # F0 should be constant
        assert np.allclose(f0_col, 1.0)

        # F1 should have time dependence
        assert not np.allclose(f1_col, 0.0)
        assert not np.allclose(f1_col, f1_col[0])

        # F2 should have quadratic time dependence
        assert not np.allclose(f2_col, 0.0)


if __name__ == "__main__":
    # Run a quick test
    test = TestMetaPulsarDesignMatrix()
    test.setup_method()
    test.test_design_matrix_creation()
    test.test_design_matrix_parameters()
    test.test_design_matrix_structure()
    print("✅ All design matrix tests passed!")
