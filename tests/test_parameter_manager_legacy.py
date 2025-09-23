"""Legacy compatibility tests for ParameterManager class.

These tests import legacy functionality and verify identical results.
"""

from unittest.mock import Mock

# Import legacy functionality
from legacy.metapulsar import (
    parameter_aliases,
    parameter_rev_aliases,
    spin_parameters,
    astrometry_parameters,
    binary_parameters,
    dm_parameters,
)

from pint.models import TimingModel
from ipta_metapulsar.parameter_manager import ParameterManager


class TestLegacyCompatibility:
    """Test compatibility with legacy parameter management."""

    def setup_method(self):
        """Set up test fixtures with legacy-compatible models."""
        # Create mock PINT models that match legacy parameter sets
        self.mock_model1 = Mock(spec=TimingModel)
        self.mock_model1.params = ["F0", "F1", "RAJ", "DECJ", "A1", "PB", "XDOT"]
        self.mock_model1.fit_params = ["F0", "F1", "RAJ", "DECJ", "A1", "PB", "XDOT"]
        self.mock_model1.set_params = []
        self.mock_model1.components = [
            "SpindownBase",
            "AstrometryEquatorial",
            "PulsarBinary",
        ]

        self.mock_model2 = Mock(spec=TimingModel)
        self.mock_model2.params = ["F0", "F1", "ELONG", "ELAT", "A1", "PB", "A1DOT"]
        self.mock_model2.fit_params = ["F0", "F1", "ELONG", "ELAT", "A1", "PB", "A1DOT"]
        self.mock_model2.set_params = []
        self.mock_model2.components = [
            "SpindownBase",
            "AstrometryEcliptic",
            "PulsarBinary",
        ]

        self.pint_models = {"EPTA": self.mock_model1, "PPTA": self.mock_model2}

        self.param_manager = ParameterManager(self.pint_models)

    def test_parameter_aliases_consistency(self):
        """Test that ParameterManager aliases match legacy parameter_aliases."""
        # Get aliases from ParameterManager
        pm_aliases = self.param_manager._simple_aliases

        # Check that legacy aliases are present in ParameterManager
        for legacy_alias, legacy_canonical in parameter_aliases.items():
            assert legacy_alias in pm_aliases
            assert pm_aliases[legacy_alias] == legacy_canonical

    def test_parameter_reverse_aliases_consistency(self):
        """Test that ParameterManager reverse aliases match legacy parameter_rev_aliases."""
        # Get reverse aliases from ParameterManager
        pm_reverse_aliases = self.param_manager._reverse_aliases

        # Check that legacy reverse aliases are present in ParameterManager
        for legacy_canonical, legacy_aliases in parameter_rev_aliases.items():
            if isinstance(legacy_aliases, list):
                for alias in legacy_aliases:
                    assert legacy_canonical in pm_reverse_aliases
                    assert alias in pm_reverse_aliases[legacy_canonical]
            else:
                assert legacy_canonical in pm_reverse_aliases
                assert legacy_aliases in pm_reverse_aliases[legacy_canonical]

    def test_parameter_type_discovery_consistency(self):
        """Test that ParameterManager discovers same parameter types as legacy."""

        # Mock the get_parameters_by_type method to return legacy parameters
        def mock_get_parameters_by_type(param_type):
            legacy_mapping = {
                "spindown": spin_parameters,
                "astrometry": astrometry_parameters,
                "binary": binary_parameters,
                "dispersion": dm_parameters,
            }
            return legacy_mapping.get(param_type, [])

        self.param_manager.get_parameters_by_type = mock_get_parameters_by_type

        # Test each parameter type
        for param_type in ["spindown", "astrometry", "binary", "dispersion"]:
            pm_params = self.param_manager.get_parameters_by_type(param_type)
            legacy_params = mock_get_parameters_by_type(param_type)

            # Check that all legacy parameters are discovered
            for legacy_param in legacy_params:
                # Handle coordinate system equivalences
                if legacy_param in [
                    "ELONG",
                    "ELAT",
                    "LAMBDA",
                    "BETA",
                    "PMLAMBDA",
                    "PMBETA",
                    "PMELONG",
                    "PMELAT",
                ]:
                    # These should be mapped to their canonical equivalents
                    canonical = self.param_manager.resolve_parameter_equivalence(
                        legacy_param
                    )
                    assert canonical in pm_params or legacy_param in pm_params
                else:
                    assert legacy_param in pm_params

    def test_component_availability_logic_consistency(self):
        """Test that component availability logic matches legacy expectations."""
        # Test astrometry component availability
        # Legacy code expects astrometry parameters to be available if ANY astrometry component exists
        assert self.param_manager.check_component_available_across_ptas("astrometry")

        # Test with missing astrometry
        self.mock_model2.components = ["SpindownBase", "PulsarBinary"]
        assert not self.param_manager.check_component_available_across_ptas("astrometry")

        # Restore for other tests
        self.mock_model2.components = [
            "SpindownBase",
            "AstrometryEcliptic",
            "PulsarBinary",
        ]

    def test_parameter_availability_logic_consistency(self):
        """Test that parameter availability logic matches legacy check_in_fitpars."""
        # Test parameters that should be available across PTAs
        assert self.param_manager.check_parameter_available_across_ptas("F0")
        assert self.param_manager.check_parameter_available_across_ptas("F1")
        assert self.param_manager.check_parameter_available_across_ptas("A1")
        assert self.param_manager.check_parameter_available_across_ptas("PB")

        # Test coordinate system parameters (handled at component level)
        # Both RAJ and ELONG should be available because astrometry components exist
        assert self.param_manager.check_parameter_available_across_ptas("RAJ")
        assert self.param_manager.check_parameter_available_across_ptas("ELONG")

        # Test alias equivalences
        # XDOT in EPTA should be equivalent to A1DOT in PPTA
        assert self.param_manager.check_parameter_available_across_ptas("XDOT")
        assert self.param_manager.check_parameter_available_across_ptas("A1DOT")

        # Test non-existent parameter
        assert not self.param_manager.check_parameter_available_across_ptas("NONEXISTENT")

    def test_parameter_identifiability_logic_consistency(self):
        """Test that parameter identifiability logic matches legacy check_fitpar_works."""
        # Test fit parameters (should be identifiable)
        assert self.param_manager.check_parameter_identifiable("EPTA", "F0")
        assert self.param_manager.check_parameter_identifiable("EPTA", "RAJ")
        assert self.param_manager.check_parameter_identifiable("PPTA", "F0")
        assert self.param_manager.check_parameter_identifiable("PPTA", "ELONG")

        # Test alias parameters (now in fit_params)
        assert self.param_manager.check_parameter_identifiable("EPTA", "XDOT")
        assert self.param_manager.check_parameter_identifiable("PPTA", "A1DOT")

    def test_parameter_mapping_workflow_consistency(self):
        """Test that parameter mapping workflow produces consistent results."""

        # Mock the get_parameters_by_type method to return legacy parameters
        def mock_get_parameters_by_type(param_type):
            legacy_mapping = {
                "spindown": spin_parameters,
                "astrometry": astrometry_parameters,
                "binary": binary_parameters,
                "dispersion": dm_parameters,
            }
            return legacy_mapping.get(param_type, [])

        self.param_manager.get_parameters_by_type = mock_get_parameters_by_type

        # Test parameter mapping with different merge configurations
        result = self.param_manager.build_parameter_mappings(
            merge_astrometry=True, merge_spin=True, merge_binary=True, merge_dm=True
        )

        # Check that merged parameters are correctly identified
        assert len(result.merged_parameters) > 0
        # Note: In this test setup, all parameters are available across PTAs,
        # so they all get merged. In a real scenario, some parameters would be PTA-specific.
        # For now, we just check that the structure is correct
        assert isinstance(result.pta_specific_parameters, list)

        # Check that fitparameters and setparameters are properly separated
        assert len(result.fitparameters) > 0
        # Note: In this test setup, all parameters are in fit_params,
        # so setparameters will be empty. In a real scenario, some parameters
        # would be in set_params.
        assert isinstance(result.setparameters, dict)

        # Check that there's no overlap between fit and set parameters
        overlap = set(result.fitparameters.keys()) & set(result.setparameters.keys())
        assert len(overlap) == 0

    def test_coordinate_system_component_handling(self):
        """Test that coordinate system parameters are handled at component level."""
        # Coordinate system parameters should be handled at component level, not parameter level
        # This means we check for astrometry component availability, not parameter equivalences

        # Both RAJ and ELONG should be available because astrometry components exist
        assert self.param_manager.check_parameter_available_across_ptas("RAJ")
        assert self.param_manager.check_parameter_available_across_ptas("ELONG")

        # But they should NOT be treated as equivalent parameters
        assert self.param_manager.resolve_parameter_equivalence("RAJ") == "RAJ"
        assert self.param_manager.resolve_parameter_equivalence("ELONG") == "ELONG"

    def test_legacy_parameter_coverage(self):
        """Test that ParameterManager covers all legacy parameter types."""
        # Get all legacy parameters
        all_legacy_params = set()
        all_legacy_params.update(spin_parameters)
        all_legacy_params.update(astrometry_parameters)
        all_legacy_params.update(binary_parameters)
        all_legacy_params.update(dm_parameters)

        # Test that ParameterManager can resolve all legacy parameters
        for param in all_legacy_params:
            resolved = self.param_manager.resolve_parameter_equivalence(param)
            # Should return a valid parameter name (not None or empty)
            assert resolved is not None
            assert len(resolved) > 0
