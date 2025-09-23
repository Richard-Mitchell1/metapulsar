"""Unit tests for ParameterManager class."""

import pytest
from unittest.mock import Mock

from pint.models import TimingModel
from ipta_metapulsar.parameter_manager import (
    ParameterManager,
    ParameterMapping,
    ParameterManagerError,
    MissingComponentError,
    ParameterInconsistencyError,
    CoordinateSystemMismatchError,
)


class TestParameterManager:
    """Test cases for ParameterManager class."""

    def setup_method(self):
        """Set up test fixtures."""
        # Create mock PINT models
        self.mock_model1 = Mock(spec=TimingModel)
        self.mock_model1.params = ["F0", "F1", "RAJ", "DECJ", "A1", "PB"]
        self.mock_model1.fit_params = ["F0", "F1", "RAJ", "DECJ", "A1", "PB"]
        self.mock_model1.set_params = []
        self.mock_model1.components = [
            "SpindownBase",
            "AstrometryEquatorial",
            "PulsarBinary",
        ]

        self.mock_model2 = Mock(spec=TimingModel)
        self.mock_model2.params = ["F0", "F1", "ELONG", "ELAT", "A1", "PB"]
        self.mock_model2.fit_params = ["F0", "F1", "ELONG", "ELAT", "A1", "PB"]
        self.mock_model2.set_params = []
        self.mock_model2.components = [
            "SpindownBase",
            "AstrometryEcliptic",
            "PulsarBinary",
        ]

        self.pint_models = {"EPTA": self.mock_model1, "PPTA": self.mock_model2}

        self.param_manager = ParameterManager(self.pint_models)

    def test_initialization(self):
        """Test ParameterManager initialization."""
        assert self.param_manager.pint_models == self.pint_models
        assert isinstance(self.param_manager._simple_aliases, dict)
        assert isinstance(self.param_manager._reverse_aliases, dict)

    def test_resolve_parameter_equivalence_simple_alias(self):
        """Test parameter equivalence resolution for simple aliases."""
        # Mock the simple aliases
        self.param_manager._simple_aliases = {"XDOT": "A1DOT", "E": "ECC"}

        assert self.param_manager.resolve_parameter_equivalence("XDOT") == "A1DOT"
        assert self.param_manager.resolve_parameter_equivalence("E") == "ECC"
        assert self.param_manager.resolve_parameter_equivalence("F0") == "F0"

    def test_resolve_parameter_equivalence_no_coordinate_system(self):
        """Test that coordinate system parameters are NOT treated as equivalents."""
        # Coordinate system parameters should NOT be resolved as equivalents
        # They are handled at the component level, not parameter level
        assert self.param_manager.resolve_parameter_equivalence("ELONG") == "ELONG"
        assert self.param_manager.resolve_parameter_equivalence("LAMBDA") == "LAMBDA"
        assert self.param_manager.resolve_parameter_equivalence("ELAT") == "ELAT"
        assert self.param_manager.resolve_parameter_equivalence("BETA") == "BETA"
        assert self.param_manager.resolve_parameter_equivalence("PMELONG") == "PMELONG"
        assert self.param_manager.resolve_parameter_equivalence("PMELAT") == "PMELAT"

    def test_check_component_available_across_ptas_astrometry(self):
        """Test component availability checking for astrometry."""
        # Both PTAs have astrometry components (different types)
        assert self.param_manager.check_component_available_across_ptas("astrometry")

        # Test with missing astrometry component
        self.mock_model2.components = ["SpindownBase", "PulsarBinary"]
        assert not self.param_manager.check_component_available_across_ptas("astrometry")

    def test_check_component_available_across_ptas_other(self):
        """Test component availability checking for other components."""
        # Both PTAs have spindown components
        assert self.param_manager.check_component_available_across_ptas("spindown")

        # Test with missing component
        assert not self.param_manager.check_component_available_across_ptas("noise")

    def test_check_parameter_available_across_ptas(self):
        """Test parameter availability checking across PTAs."""
        # F0 is available in both PTAs
        assert self.param_manager.check_parameter_available_across_ptas("F0")

        # RAJ is only in EPTA, but ELONG (coordinate equivalent) is in PPTA
        assert self.param_manager.check_parameter_available_across_ptas("RAJ")

        # A1 is available in both PTAs
        assert self.param_manager.check_parameter_available_across_ptas("A1")

        # Non-existent parameter
        assert not self.param_manager.check_parameter_available_across_ptas("NONEXISTENT")

    def test_check_parameter_identifiable(self):
        """Test parameter identifiability checking."""
        # F0 is in fit_params for both PTAs
        assert self.param_manager.check_parameter_identifiable("EPTA", "F0")
        assert self.param_manager.check_parameter_identifiable("PPTA", "F0")

        # A1 is now in fit_params
        assert self.param_manager.check_parameter_identifiable("EPTA", "A1")
        assert self.param_manager.check_parameter_identifiable("PPTA", "A1")

    def test_get_parameters_by_type(self):
        """Test parameter discovery by type."""
        # Mock the AllComponents to return specific parameters
        with pytest.MonkeyPatch().context() as m:
            # Create mock component classes with param_list attributes
            mock_astrometry_equatorial = Mock()
            mock_astrometry_equatorial.param_list = ["RAJ", "DECJ", "PMRA", "PMDEC"]

            mock_astrometry_ecliptic = Mock()
            mock_astrometry_ecliptic.param_list = ["ELONG", "ELAT", "PMELONG", "PMELAT"]

            mock_spindown = Mock()
            mock_spindown.param_list = ["F0", "F1", "F2"]

            mock_binary = Mock()
            mock_binary.param_list = ["A1", "PB", "A1DOT"]

            mock_dispersion = Mock()
            mock_dispersion.param_list = ["DM", "DM1", "DM2"]

            # Create mock AllComponents
            mock_all_components = Mock()
            mock_all_components.AstrometryEquatorial = mock_astrometry_equatorial
            mock_all_components.AstrometryEcliptic = mock_astrometry_ecliptic
            mock_all_components.SpindownBase = mock_spindown
            mock_all_components.PulsarBinary = mock_binary
            mock_all_components.Dispersion = mock_dispersion

            m.setattr(
                "ipta_metapulsar.parameter_manager.AllComponents",
                lambda: mock_all_components,
            )

            # Test parameter discovery
            astrometry_params = self.param_manager.get_parameters_by_type("astrometry")
            assert "RAJ" in astrometry_params
            assert "DECJ" in astrometry_params
            assert "ELONG" in astrometry_params
            assert "ELAT" in astrometry_params

            spindown_params = self.param_manager.get_parameters_by_type("spindown")
            assert "F0" in spindown_params
            assert "F1" in spindown_params

    def test_build_parameter_mappings_success(self):
        """Test successful parameter mapping building."""
        # Mock the get_parameters_by_type method
        self.param_manager.get_parameters_by_type = Mock(
            return_value=["F0", "F1", "RAJ", "A1"]
        )

        result = self.param_manager.build_parameter_mappings(
            merge_astrometry=True, merge_spin=True, merge_binary=False, merge_dm=False
        )

        assert isinstance(result, ParameterMapping)
        assert "F0" in result.fitparameters
        assert "F1" in result.fitparameters
        assert "RAJ" in result.fitparameters
        # A1 is now merged across PTAs
        assert "A1" in result.fitparameters
        assert result.fitparameters["A1"]["EPTA"] == "A1"
        assert result.fitparameters["A1"]["PPTA"] == "A1"

    def test_build_parameter_mappings_parameter_inconsistency(self):
        """Test parameter mapping building with parameter inconsistency."""
        # Mock a parameter that's not available across all PTAs
        self.param_manager.check_parameter_available_across_ptas = Mock(
            return_value=False
        )
        self.param_manager.get_parameters_by_type = Mock(return_value=["F0"])

        with pytest.raises(ParameterInconsistencyError):
            self.param_manager.build_parameter_mappings(merge_spin=True)

    def test_build_parameter_mappings_fit_set_overlap(self):
        """Test parameter mapping building with fit/set parameter overlap."""
        # Create models where same parameter is both fit and set
        self.mock_model1.params = ["F0"]
        self.mock_model1.fit_params = ["F0"]
        self.mock_model1.set_params = ["F0"]

        self.mock_model2.params = ["F0"]
        self.mock_model2.fit_params = ["F0"]
        self.mock_model2.set_params = ["F0"]

        self.param_manager.get_parameters_by_type = Mock(return_value=["F0"])

        with pytest.raises(ParameterInconsistencyError):
            self.param_manager.build_parameter_mappings(merge_spin=True)

    def test_get_all_possible_parameter_names(self):
        """Test getting all possible parameter names."""
        # Mock the reverse aliases
        self.param_manager._reverse_aliases = {"A1DOT": ["XDOT"]}

        # Test with coordinate parameter (should NOT include equivalents)
        names = self.param_manager._get_all_possible_parameter_names("RAJ")
        assert "RAJ" in names
        assert "ELONG" not in names  # No coordinate equivalents
        assert "LAMBDA" not in names  # No coordinate equivalents

        # Test with simple alias
        names = self.param_manager._get_all_possible_parameter_names("A1DOT")
        assert "A1DOT" in names
        assert "XDOT" in names

    def test_coordinate_equivalences_removed(self):
        """Test that coordinate equivalences are no longer used."""
        # Coordinate equivalences should no longer exist
        assert not hasattr(self.param_manager, "_coordinate_equivalences")


class TestParameterMapping:
    """Test cases for ParameterMapping dataclass."""

    def test_parameter_mapping_creation(self):
        """Test ParameterMapping dataclass creation."""
        fitparams = {"F0": {"EPTA": "F0", "PPTA": "F0"}}
        setparams = {"A1_EPTA": {"EPTA": "A1"}}
        merged = ["F0"]
        pta_specific = ["A1_EPTA"]

        mapping = ParameterMapping(
            fitparameters=fitparams,
            setparameters=setparams,
            merged_parameters=merged,
            pta_specific_parameters=pta_specific,
        )

        assert mapping.fitparameters == fitparams
        assert mapping.setparameters == setparams
        assert mapping.merged_parameters == merged
        assert mapping.pta_specific_parameters == pta_specific


class TestErrorHandling:
    """Test error handling in ParameterManager."""

    def test_parameter_manager_error_inheritance(self):
        """Test error class inheritance."""
        assert issubclass(MissingComponentError, ParameterManagerError)
        assert issubclass(ParameterInconsistencyError, ParameterManagerError)
        assert issubclass(CoordinateSystemMismatchError, ParameterManagerError)

    def test_error_raising(self):
        """Test that errors can be raised."""
        with pytest.raises(ParameterManagerError):
            raise ParameterManagerError("Test error")

        with pytest.raises(MissingComponentError):
            raise MissingComponentError("Missing component")

        with pytest.raises(ParameterInconsistencyError):
            raise ParameterInconsistencyError("Parameter inconsistency")

        with pytest.raises(CoordinateSystemMismatchError):
            raise CoordinateSystemMismatchError("Coordinate mismatch")
