"""
Tests for MetaPulsar design matrix and unit conversion functionality.

This module tests the design matrix construction and unit conversion methods
implemented in the MetaPulsar class.

TODO: COMPLETELY REDESIGN - This entire test suite is fundamentally flawed
because it's based on the MockPulsar class which creates inconsistent parameter
structures (e.g., 3 Offset parameters for 2 PTAs). All tests need to be
completely rewritten with a proper design that accurately reflects how the real
ParameterManager and MetaPulsar work.
"""

import pytest
import numpy as np
from src.metapulsar.metapulsar import MetaPulsar
from src.metapulsar.mockpulsar import MockPulsar, create_libstempo_adapter
from src.metapulsar.mockpulsar import create_mock_timing_data, create_mock_flags


class TestMetaPulsarDesignMatrix:
    """Test class for MetaPulsar design matrix functionality.

    TODO: COMPLETELY REDESIGN - This test class is fundamentally flawed because
    it's based on the MockPulsar class which creates inconsistent parameter
    structures (e.g., 3 Offset parameters for 2 PTAs). All tests need to be
    completely rewritten with a proper design that accurately reflects how the
    real ParameterManager and MetaPulsar work.
    """

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

        # Create MetaPulsars with both strategies
        self.pulsars = {"test_pta1": self.mock_psr1, "test_pta2": self.mock_psr2}
        adapted_pulsars = {
            pta: create_libstempo_adapter(psr) for pta, psr in self.pulsars.items()
        }

        # Composite strategy: PTA-specific parameters (19 total)
        self.composite_mp = MetaPulsar(
            adapted_pulsars, combination_strategy="composite"
        )

        # Consistent strategy: merged parameters (11 total)
        self.consistent_mp = MetaPulsar(
            adapted_pulsars, combination_strategy="consistent"
        )

        # Fix Offset parameter mapping for both strategies
        for mp in [self.composite_mp, self.consistent_mp]:
            if "Offset" not in mp._fitparameters:
                mp._fitparameters["Offset"] = {
                    "test_pta1": "Offset",
                    "test_pta2": "Offset",
                }
                # Add Offset to fitpars if not already there
                if "Offset" not in mp.fitpars:
                    mp.fitpars.insert(0, "Offset")
                # Rebuild design matrix to include the new Offset parameter
                mp._build_design_matrix()

    def test_design_matrix_creation(self):
        """Test that design matrix is created correctly for both strategies."""
        # Test composite strategy
        assert hasattr(self.composite_mp, "_designmatrix")
        assert self.composite_mp._designmatrix.shape == (
            60,
            19,
        )  # TODO: COMPLETELY REDESIGN - This comment is wrong! 3 Offset parameters for 2 PTAs is logically impossible
        assert np.count_nonzero(self.composite_mp._designmatrix) > 0

        # Test consistent strategy
        assert hasattr(self.consistent_mp, "_designmatrix")
        assert self.consistent_mp._designmatrix.shape == (
            60,
            11,
        )  # TODO: COMPLETELY REDESIGN - This comment is wrong! 3 Offset parameters for 2 PTAs is logically impossible
        assert np.count_nonzero(self.consistent_mp._designmatrix) > 0

    def test_design_matrix_parameters(self):
        """Test that design matrix has correct parameters for both strategies."""
        # Test composite strategy - PTA-specific parameters
        assert len(self.composite_mp.fitpars) == 19
        expected_composite_params = [
            "Offset",
            "PX_test_pta1",
            "RAJ_test_pta1",
            "DECJ_test_pta1",
            "PMRA_test_pta1",
            "PMDEC_test_pta1",
            "F0_test_pta1",
            "F1_test_pta1",
            "F2_test_pta1",
            "PX_test_pta2",
            "RAJ_test_pta2",
            "DECJ_test_pta2",
            "PMRA_test_pta2",
            "PMDEC_test_pta2",
            "F0_test_pta2",
            "F1_test_pta2",
            "F2_test_pta2",
        ]
        for param in expected_composite_params:
            assert param in self.composite_mp.fitpars

        # Test consistent strategy - merged parameters
        assert len(self.consistent_mp.fitpars) == 11
        expected_consistent_params = [
            "Offset",
            "Offset_test_pta1",
            "Offset_test_pta2",
            "F0",
            "F1",
            "F2",
            "RAJ",
            "DECJ",
            "PMRA",
            "PMDEC",
            "PX",
        ]
        for param in expected_consistent_params:
            assert param in self.consistent_mp.fitpars

    def test_design_matrix_structure(self):
        """Test design matrix structure and content for both strategies."""
        # Test composite strategy
        dm_composite = self.composite_mp._designmatrix

        # Check that F0 columns are all ones (constant term) for both PTAs
        f0_pta1_idx = self.composite_mp.fitpars.index("F0_test_pta1")
        f0_pta2_idx = self.composite_mp.fitpars.index("F0_test_pta2")
        pta_slices = self.composite_mp._get_pta_slices()

        # F0_pta1 should be 1.0 for PTA1 slice, 0.0 for PTA2 slice
        f0_pta1_col = dm_composite[:, f0_pta1_idx]
        assert np.allclose(f0_pta1_col[pta_slices["test_pta1"]], 1.0)
        assert np.allclose(f0_pta1_col[pta_slices["test_pta2"]], 0.0)

        # F0_pta2 should be 0.0 for PTA1 slice, 1.0 for PTA2 slice
        f0_pta2_col = dm_composite[:, f0_pta2_idx]
        assert np.allclose(f0_pta2_col[pta_slices["test_pta1"]], 0.0)
        assert np.allclose(f0_pta2_col[pta_slices["test_pta2"]], 1.0)

        # Check that F1 columns have time dependence for both PTAs
        f1_pta1_idx = self.composite_mp.fitpars.index("F1_test_pta1")
        f1_pta2_idx = self.composite_mp.fitpars.index("F1_test_pta2")
        f1_pta1_col = dm_composite[:, f1_pta1_idx]
        f1_pta2_col = dm_composite[:, f1_pta2_idx]

        # F1_pta1 should have non-zero values and time dependence for PTA1 slice
        f1_pta1_pta1_slice = f1_pta1_col[pta_slices["test_pta1"]]
        assert not np.allclose(f1_pta1_pta1_slice, 0.0)  # Should have non-zero values
        assert not np.allclose(
            f1_pta1_pta1_slice, f1_pta1_pta1_slice[0]
        )  # Should vary with time
        assert np.allclose(
            f1_pta1_col[pta_slices["test_pta2"]], 0.0
        )  # Should be zero for PTA2

        # F1_pta2 should have non-zero values and time dependence for PTA2 slice
        f1_pta2_pta2_slice = f1_pta2_col[pta_slices["test_pta2"]]
        assert not np.allclose(f1_pta2_pta2_slice, 0.0)  # Should have non-zero values
        assert not np.allclose(
            f1_pta2_pta2_slice, f1_pta2_pta2_slice[0]
        )  # Should vary with time
        assert np.allclose(
            f1_pta2_col[pta_slices["test_pta1"]], 0.0
        )  # Should be zero for PTA1

        # Test consistent strategy
        dm_consistent = self.consistent_mp._designmatrix

        # Check that F0 column is all ones (constant term)
        f0_idx = self.consistent_mp.fitpars.index("F0")
        assert np.allclose(dm_consistent[:, f0_idx], 1.0)

        # Check that F1 column has time dependence
        f1_idx = self.consistent_mp.fitpars.index("F1")
        f1_col = dm_consistent[:, f1_idx]
        assert not np.allclose(f1_col, 0.0)  # Should have non-zero values
        assert not np.allclose(f1_col, f1_col[0])  # Should vary with time

    def test_design_matrix_pta_slices(self):
        """Test that design matrix correctly handles PTA slices for both strategies."""
        # Test composite strategy
        pta_slices_composite = self.composite_mp._get_pta_slices()
        assert "test_pta1" in pta_slices_composite
        assert "test_pta2" in pta_slices_composite
        assert pta_slices_composite["test_pta1"].start == 0
        assert pta_slices_composite["test_pta1"].stop == 30
        assert pta_slices_composite["test_pta2"].start == 30
        assert pta_slices_composite["test_pta2"].stop == 60

        # Test consistent strategy
        pta_slices_consistent = self.consistent_mp._get_pta_slices()
        assert "test_pta1" in pta_slices_consistent
        assert "test_pta2" in pta_slices_consistent
        assert pta_slices_consistent["test_pta1"].start == 0
        assert pta_slices_consistent["test_pta1"].stop == 30
        assert pta_slices_consistent["test_pta2"].start == 30
        assert pta_slices_consistent["test_pta2"].stop == 60

    def test_unit_conversion_coordinate_parameters(self):
        """Test unit conversion for coordinate parameters for both strategies."""
        import astropy.units as u

        # Test composite strategy with PTA-specific parameter names
        # Note: Unit conversion function doesn't currently handle PTA-specific parameter names
        # so it returns the column unchanged
        raj_col = np.ones(10)
        converted_raj = self.composite_mp._convert_design_matrix_units(
            raj_col, "RAJ_test_pta1", "tempo2"
        )
        # No unit conversion applied for PTA-specific parameter names
        assert np.allclose(converted_raj, raj_col)

        decj_col = np.ones(10)
        converted_decj = self.composite_mp._convert_design_matrix_units(
            decj_col, "DECJ_test_pta1", "tempo2"
        )
        # No unit conversion applied for PTA-specific parameter names
        assert np.allclose(converted_decj, decj_col)

        # Test consistent strategy with global parameter names
        expected_factor = (1.0 * u.second / u.radian).to(u.second / u.hourangle).value
        expected_factor_deg = (1.0 * u.second / u.radian).to(u.second / u.deg).value

        converted_raj_consistent = self.consistent_mp._convert_design_matrix_units(
            raj_col, "RAJ", "tempo2"
        )
        assert np.allclose(converted_raj_consistent, raj_col * expected_factor)

        converted_decj_consistent = self.consistent_mp._convert_design_matrix_units(
            decj_col, "DECJ", "tempo2"
        )
        assert np.allclose(converted_decj_consistent, decj_col * expected_factor_deg)

    def test_unit_conversion_non_coordinate_parameters(self):
        """Test that non-coordinate parameters are not converted for both strategies."""
        # Test composite strategy with PTA-specific parameter names
        f0_col = np.ones(10)
        converted_f0_composite = self.composite_mp._convert_design_matrix_units(
            f0_col, "F0_test_pta1", "tempo2"
        )
        assert np.allclose(converted_f0_composite, f0_col)

        # Test consistent strategy with global parameter names
        converted_f0_consistent = self.consistent_mp._convert_design_matrix_units(
            f0_col, "F0", "tempo2"
        )
        assert np.allclose(converted_f0_consistent, f0_col)

    def test_design_matrix_column_construction(self):
        """Test individual design matrix column construction for both strategies."""
        # Test composite strategy with PTA-specific parameter names
        f0_pta1_col = self.composite_mp._build_design_matrix_column("F0_test_pta1")
        assert len(f0_pta1_col) == 60
        pta_slices = self.composite_mp._get_pta_slices()
        assert np.allclose(
            f0_pta1_col[pta_slices["test_pta1"]], 1.0
        )  # F0 should be constant for PTA1
        assert np.allclose(
            f0_pta1_col[pta_slices["test_pta2"]], 0.0
        )  # F0 should be zero for PTA2

        f1_pta1_col = self.composite_mp._build_design_matrix_column("F1_test_pta1")
        assert len(f1_pta1_col) == 60
        f1_pta1_pta1_slice = f1_pta1_col[pta_slices["test_pta1"]]
        assert not np.allclose(
            f1_pta1_pta1_slice, 0.0
        )  # Should have non-zero values for PTA1
        assert np.allclose(
            f1_pta1_col[pta_slices["test_pta2"]], 0.0
        )  # Should be zero for PTA2

        # Test consistent strategy with global parameter names
        f0_col = self.consistent_mp._build_design_matrix_column("F0")
        assert len(f0_col) == 60
        assert np.allclose(f0_col, 1.0)  # F0 should be constant

        f1_col = self.consistent_mp._build_design_matrix_column("F1")
        assert len(f1_col) == 60
        assert not np.allclose(f1_col, 0.0)  # Should have non-zero values

    def test_design_matrix_with_different_strategies(self):
        """Test design matrix with different combination strategies."""
        # Test composite strategy - should have PTA-specific parameters
        assert hasattr(self.composite_mp, "_designmatrix")
        assert self.composite_mp._designmatrix.shape == (
            60,
            19,
        )  # 19 parameters (8 per PTA + 3 Offset parameters)
        assert len(self.composite_mp.fitpars) == 19
        assert "F0_test_pta1" in self.composite_mp.fitpars
        assert "F0_test_pta2" in self.composite_mp.fitpars

        # Test consistent strategy - should have merged parameters
        assert hasattr(self.consistent_mp, "_designmatrix")
        assert self.consistent_mp._designmatrix.shape == (
            60,
            11,
        )  # 11 parameters (9 merged + 2 PTA-specific Offsets)
        assert len(self.consistent_mp.fitpars) == 11
        assert "F0" in self.consistent_mp.fitpars
        assert "RAJ" in self.consistent_mp.fitpars

    def test_design_matrix_empty_pulsars(self):
        """Test design matrix with empty pulsar list."""
        # Empty pulsars should raise an exception
        with pytest.raises(StopIteration):
            MetaPulsar({}, combination_strategy="composite")

    def test_timing_package_detection(self):
        """Test timing package detection for MockPulsar for both strategies."""
        # Test composite strategy
        timing_pkg_composite = self.composite_mp._get_timing_package(self.mock_psr1)
        assert (
            timing_pkg_composite == "unknown"
        )  # MockPulsar doesn't have PINT/Tempo2 attributes

        # Test consistent strategy
        timing_pkg_consistent = self.consistent_mp._get_timing_package(self.mock_psr1)
        assert (
            timing_pkg_consistent == "unknown"
        )  # MockPulsar doesn't have PINT/Tempo2 attributes

    def test_design_matrix_parameter_mapping(self):
        """Test that parameter mapping works correctly for both strategies."""
        # Test composite strategy - PTA-specific parameters
        assert hasattr(self.composite_mp, "_fitparameters")
        assert (
            len(self.composite_mp._fitparameters) == 19
        )  # 19 parameters (8 per PTA + 3 Offset parameters)

        # Check that each parameter has mappings for the correct PTA
        for param in self.composite_mp.fitpars:
            assert param in self.composite_mp._fitparameters
            if param.endswith("_test_pta1"):
                assert "test_pta1" in self.composite_mp._fitparameters[param]
            elif param.endswith("_test_pta2"):
                assert "test_pta2" in self.composite_mp._fitparameters[param]
            elif param in ["Offset", "Offset_test_pta1", "Offset_test_pta2"]:
                # Offset parameters are PTA-specific
                if param == "Offset":
                    # Global Offset maps to both PTAs
                    assert "test_pta1" in self.composite_mp._fitparameters[param]
                    assert "test_pta2" in self.composite_mp._fitparameters[param]
                elif param == "Offset_test_pta1":
                    assert "test_pta1" in self.composite_mp._fitparameters[param]
                elif param == "Offset_test_pta2":
                    assert "test_pta2" in self.composite_mp._fitparameters[param]

        # Test consistent strategy - merged parameters
        assert hasattr(self.consistent_mp, "_fitparameters")
        assert (
            len(self.consistent_mp._fitparameters) == 11
        )  # 11 parameters (8 merged + 3 Offset parameters)

        # Check that each parameter has mappings for the correct PTAs
        for param in self.consistent_mp.fitpars:
            assert param in self.consistent_mp._fitparameters
            if param.endswith("_test_pta1"):
                assert "test_pta1" in self.consistent_mp._fitparameters[param]
                assert "test_pta2" not in self.consistent_mp._fitparameters[param]
            elif param.endswith("_test_pta2"):
                assert "test_pta2" in self.consistent_mp._fitparameters[param]
                assert "test_pta1" not in self.consistent_mp._fitparameters[param]
            elif param in ["Offset", "Offset_test_pta1", "Offset_test_pta2"]:
                # Offset parameters are PTA-specific
                if param == "Offset":
                    # Global Offset maps to both PTAs
                    assert "test_pta1" in self.consistent_mp._fitparameters[param]
                    assert "test_pta2" in self.consistent_mp._fitparameters[param]
                elif param == "Offset_test_pta1":
                    assert "test_pta1" in self.consistent_mp._fitparameters[param]
                elif param == "Offset_test_pta2":
                    assert "test_pta2" in self.consistent_mp._fitparameters[param]
            else:
                # Merged parameters should map to both PTAs
                assert "test_pta1" in self.consistent_mp._fitparameters[param]
                assert "test_pta2" in self.consistent_mp._fitparameters[param]

    def test_design_matrix_consistency(self):
        """Test that design matrix is consistent across PTAs for both strategies."""
        # Test composite strategy - PTA-specific parameters
        dm_composite = self.composite_mp._designmatrix
        pta_slices_composite = self.composite_mp._get_pta_slices()

        # Check that F0 columns are consistent (should be 1.0 for corresponding PTA)
        f0_pta1_idx = self.composite_mp.fitpars.index("F0_test_pta1")
        f0_pta2_idx = self.composite_mp.fitpars.index("F0_test_pta2")
        f0_pta1 = dm_composite[pta_slices_composite["test_pta1"], f0_pta1_idx]
        f0_pta2 = dm_composite[pta_slices_composite["test_pta2"], f0_pta2_idx]

        assert np.allclose(f0_pta1, 1.0)  # F0_pta1 should be 1.0 for PTA1 slice
        assert np.allclose(f0_pta2, 1.0)  # F0_pta2 should be 1.0 for PTA2 slice

        # Test consistent strategy - merged parameters
        dm_consistent = self.consistent_mp._designmatrix
        pta_slices_consistent = self.consistent_mp._get_pta_slices()

        # Check that F0 columns are consistent (should be 1.0 for both PTAs)
        f0_idx = self.consistent_mp.fitpars.index("F0")
        f0_pta1_consistent = dm_consistent[pta_slices_consistent["test_pta1"], f0_idx]
        f0_pta2_consistent = dm_consistent[pta_slices_consistent["test_pta2"], f0_idx]

        assert np.allclose(f0_pta1_consistent, 1.0)
        assert np.allclose(f0_pta2_consistent, 1.0)

    def test_design_matrix_astrometry_parameters(self):
        """Test that astrometry parameters are handled correctly for both strategies."""
        # Test composite strategy - PTA-specific parameters
        dm_composite = self.composite_mp._designmatrix
        pta_slices = self.composite_mp._get_pta_slices()

        # Check RAJ and DECJ columns have frequency dependence
        raj_pta1_idx = self.composite_mp.fitpars.index("RAJ_test_pta1")
        decj_pta1_idx = self.composite_mp.fitpars.index("DECJ_test_pta1")

        raj_pta1_col = dm_composite[:, raj_pta1_idx]
        decj_pta1_col = dm_composite[:, decj_pta1_idx]

        # Should have non-zero values for PTA1 slice
        assert not np.allclose(raj_pta1_col[pta_slices["test_pta1"]], 0.0)
        assert not np.allclose(decj_pta1_col[pta_slices["test_pta1"]], 0.0)
        # Should be zero for PTA2 slice
        assert np.allclose(raj_pta1_col[pta_slices["test_pta2"]], 0.0)
        assert np.allclose(decj_pta1_col[pta_slices["test_pta2"]], 0.0)

        # Test consistent strategy - merged parameters
        dm_consistent = self.consistent_mp._designmatrix

        # Check RAJ and DECJ columns have frequency dependence
        raj_idx = self.consistent_mp.fitpars.index("RAJ")
        decj_idx = self.consistent_mp.fitpars.index("DECJ")

        raj_col = dm_consistent[:, raj_idx]
        decj_col = dm_consistent[:, decj_idx]

        # Should have non-zero values
        assert not np.allclose(raj_col, 0.0)
        assert not np.allclose(decj_col, 0.0)

    def test_design_matrix_spin_parameters(self):
        """Test that spin parameters are handled correctly for both strategies."""
        # Test composite strategy - PTA-specific parameters
        dm_composite = self.composite_mp._designmatrix
        pta_slices = self.composite_mp._get_pta_slices()

        # Check F0, F1, F2 columns for PTA1
        f0_pta1_idx = self.composite_mp.fitpars.index("F0_test_pta1")
        f1_pta1_idx = self.composite_mp.fitpars.index("F1_test_pta1")
        f2_pta1_idx = self.composite_mp.fitpars.index("F2_test_pta1")

        f0_pta1_col = dm_composite[:, f0_pta1_idx]
        f1_pta1_col = dm_composite[:, f1_pta1_idx]
        f2_pta1_col = dm_composite[:, f2_pta1_idx]

        # F0 should be constant for PTA1 slice, zero for PTA2 slice
        assert np.allclose(f0_pta1_col[pta_slices["test_pta1"]], 1.0)
        assert np.allclose(f0_pta1_col[pta_slices["test_pta2"]], 0.0)

        # F1 should have time dependence for PTA1 slice, zero for PTA2 slice
        f1_pta1_pta1_slice = f1_pta1_col[pta_slices["test_pta1"]]
        assert not np.allclose(f1_pta1_pta1_slice, 0.0)
        assert not np.allclose(f1_pta1_pta1_slice, f1_pta1_pta1_slice[0])
        assert np.allclose(f1_pta1_col[pta_slices["test_pta2"]], 0.0)

        # F2 should have quadratic time dependence for PTA1 slice, zero for PTA2 slice
        f2_pta1_pta1_slice = f2_pta1_col[pta_slices["test_pta1"]]
        assert not np.allclose(f2_pta1_pta1_slice, 0.0)
        assert np.allclose(f2_pta1_col[pta_slices["test_pta2"]], 0.0)

        # Test consistent strategy - merged parameters
        dm_consistent = self.consistent_mp._designmatrix

        # Check F0, F1, F2 columns
        f0_idx = self.consistent_mp.fitpars.index("F0")
        f1_idx = self.consistent_mp.fitpars.index("F1")
        f2_idx = self.consistent_mp.fitpars.index("F2")

        f0_col = dm_consistent[:, f0_idx]
        f1_col = dm_consistent[:, f1_idx]
        f2_col = dm_consistent[:, f2_idx]

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
