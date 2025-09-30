"""Unit tests for PINT helper functions."""

import pytest
from unittest.mock import Mock, patch
from ipta_metapulsar.pint_helpers import (
    get_parameters_by_type_from_pint,
    get_parameter_aliases_from_pint,
    check_component_available_in_model,
    get_parameter_identifiability_from_model,
    PINTDiscoveryError,
    _is_astrometry_parameter,
)

# Test constants for better maintainability
EXPECTED_ASTROMETRY_PARAMS = {
    "RAJ",
    "DECJ",
    "PMRA",
    "PMDEC",
    "ELONG",
    "ELAT",
    "PMELONG",
    "PMELAT",
}
EXPECTED_SPINDOWN_PARAMS = {"F0", "F1", "F2", "PEPOCH"}


@pytest.fixture
def mock_astrometry_components():
    """Fixture for astrometry component mocking to avoid duplication."""
    mock_instance = Mock()
    mock_instance.category_component_map = {
        "astrometry": ["AstrometryEquatorial", "AstrometryEcliptic"]
    }

    # Mock equatorial astrometry component
    mock_astrometry_eq = Mock()
    mock_astrometry_eq.return_value.params = ["RAJ", "DECJ", "PMRA", "PMDEC"]

    # Mock ecliptic astrometry component
    mock_astrometry_ec = Mock()
    mock_astrometry_ec.return_value.params = ["ELONG", "ELAT", "PMELONG", "PMELAT"]

    mock_instance.AstrometryEquatorial = mock_astrometry_eq
    mock_instance.AstrometryEcliptic = mock_astrometry_ec

    return mock_instance


class TestGetParametersByTypeFromPint:
    """Test get_parameters_by_type_from_pint function."""

    def test_astrometry_parameters_discovery(self):
        """Test discovery of astrometry parameters."""
        result = get_parameters_by_type_from_pint("astrometry")

        # Check that we get the expected astrometry parameters
        assert EXPECTED_ASTROMETRY_PARAMS.issubset(set(result))

        # Check that we get additional parameters (PINT discovery is working)
        assert len(result) > len(
            EXPECTED_ASTROMETRY_PARAMS
        ), "Expected PINT to return more parameters than just the basic set"

    def test_spindown_parameters_discovery(self):
        """Test discovery of spindown parameters."""
        result = get_parameters_by_type_from_pint("spindown")

        # Check that we get the expected spindown parameters
        assert EXPECTED_SPINDOWN_PARAMS.issubset(set(result))

        # Check that we get additional parameters (PINT discovery is working)
        assert len(result) > len(
            EXPECTED_SPINDOWN_PARAMS
        ), "Expected PINT to return more parameters than just the basic set"

    def test_unknown_parameter_type(self):
        """Test handling of unknown parameter type."""
        result = get_parameters_by_type_from_pint("unknown_type")
        assert result == []

    def test_empty_parameter_type(self):
        """Test handling of empty parameter type."""
        result = get_parameters_by_type_from_pint("")
        assert result == []

    def test_none_parameter_type(self):
        """Test handling of None parameter type."""
        result = get_parameters_by_type_from_pint(None)
        assert result == []

    def test_pint_discovery_failure_raises_error(self):
        """Test that PINT discovery failure raises PINTDiscoveryError."""
        with patch(
            "ipta_metapulsar.pint_helpers.AllComponents",
            side_effect=Exception("PINT error"),
        ):
            with pytest.raises(PINTDiscoveryError):
                get_parameters_by_type_from_pint("astrometry")


class TestGetParameterAliasesFromPint:
    """Test get_parameter_aliases_from_pint function."""

    def test_alias_discovery_success(self):
        """Test successful alias discovery from PINT."""
        with patch("ipta_metapulsar.pint_helpers.AllComponents") as mock_all_components:
            # Mock the alias map
            mock_instance = Mock()
            mock_instance._param_alias_map = {
                "XDOT": "A1DOT",
                "E": "ECC",
                "STIG": "STIGMA",
                "RAJ": "ELONG",  # Coordinate alias - should be filtered out
                "DECJ": "ELAT",  # Coordinate alias - should be filtered out
            }

            # Mock the category_component_map for coordinate detection
            mock_instance.category_component_map = {
                "astrometry": ["AstrometryEquatorial", "AstrometryEcliptic"]
            }

            # Mock astrometry components for coordinate detection
            mock_astrometry_eq = Mock()
            mock_astrometry_eq.return_value.params = ["RAJ", "DECJ", "PMRA", "PMDEC"]
            mock_astrometry_ec = Mock()
            mock_astrometry_ec.return_value.params = [
                "ELONG",
                "ELAT",
                "PMELONG",
                "PMELAT",
            ]

            mock_instance.AstrometryEquatorial = mock_astrometry_eq
            mock_instance.AstrometryEcliptic = mock_astrometry_ec

            mock_all_components.return_value = mock_instance

            result = get_parameter_aliases_from_pint()

            # Should include simple aliases but exclude coordinate aliases
            assert result["XDOT"] == "A1DOT"
            assert result["E"] == "ECC"
            assert result["STIG"] == "STIGMA"
            assert "RAJ" not in result  # Coordinate alias filtered out
            assert "DECJ" not in result  # Coordinate alias filtered out
            assert result["EDOT"] == "ECCDOT"  # Added manually

    def test_pint_discovery_failure_raises_error(self):
        """Test that PINT discovery failure raises PINTDiscoveryError."""
        with patch(
            "ipta_metapulsar.pint_helpers.AllComponents",
            side_effect=Exception("PINT error"),
        ):
            with pytest.raises(PINTDiscoveryError):
                get_parameter_aliases_from_pint()


class TestCheckComponentAvailableInModel:
    """Test check_component_available_in_model function."""

    def test_component_available(self):
        """Test when component is available in model."""
        mock_model = Mock()
        mock_component = Mock()
        mock_component.category = "astrometry"
        mock_model.components = {"AstrometryEquatorial": mock_component}

        result = check_component_available_in_model(mock_model, "astrometry")
        assert result is True

    def test_component_not_available(self):
        """Test when component is not available in model."""
        mock_model = Mock()
        mock_component = Mock()
        mock_component.category = "other"
        mock_model.components = {"OtherComponent": mock_component}

        result = check_component_available_in_model(mock_model, "astrometry")
        assert result is False

    def test_unknown_component_type(self):
        """Test handling of unknown component type."""
        mock_model = Mock()
        result = check_component_available_in_model(mock_model, "unknown_type")
        assert result is False

    def test_empty_components_dict(self):
        """Test handling of empty components dictionary."""
        mock_model = Mock()
        mock_model.components = {}
        result = check_component_available_in_model(mock_model, "astrometry")
        assert result is False

    def test_none_components_attribute(self):
        """Test handling of None components attribute."""
        mock_model = Mock()
        mock_model.components = None
        # The current implementation doesn't handle None components gracefully
        with pytest.raises(AttributeError):
            check_component_available_in_model(mock_model, "astrometry")


class TestGetParameterIdentifiabilityFromModel:
    """Test get_parameter_identifiability_from_model function."""

    def test_parameter_identifiable(self):
        """Test when parameter is both fittable and free."""
        mock_model = Mock()
        mock_model.fittable_params = ["F0", "F1", "RAJ"]
        mock_model.free_params = ["F0", "RAJ"]

        result = get_parameter_identifiability_from_model(mock_model, "F0")
        assert result is True

    def test_parameter_not_fittable(self):
        """Test when parameter is not fittable."""
        mock_model = Mock()
        mock_model.fittable_params = ["F0", "F1"]
        mock_model.free_params = ["F0", "F1", "RAJ"]

        result = get_parameter_identifiability_from_model(mock_model, "RAJ")
        assert result is False

    def test_parameter_not_free(self):
        """Test when parameter is not free (frozen)."""
        mock_model = Mock()
        mock_model.fittable_params = ["F0", "F1", "RAJ"]
        mock_model.free_params = ["F0", "F1"]

        result = get_parameter_identifiability_from_model(mock_model, "RAJ")
        assert result is False

    def test_parameter_neither_fittable_nor_free(self):
        """Test when parameter is neither fittable nor free."""
        mock_model = Mock()
        mock_model.fittable_params = ["F0", "F1"]
        mock_model.free_params = ["F0"]

        result = get_parameter_identifiability_from_model(mock_model, "RAJ")
        assert result is False

    def test_empty_fittable_params(self):
        """Test when fittable_params is empty."""
        mock_model = Mock()
        mock_model.fittable_params = []
        mock_model.free_params = ["F0", "F1"]

        result = get_parameter_identifiability_from_model(mock_model, "F0")
        assert result is False

    def test_empty_free_params(self):
        """Test when free_params is empty."""
        mock_model = Mock()
        mock_model.fittable_params = ["F0", "F1"]
        mock_model.free_params = []

        result = get_parameter_identifiability_from_model(mock_model, "F0")
        assert result is False

    def test_nonexistent_parameter(self):
        """Test when parameter doesn't exist in either list."""
        mock_model = Mock()
        mock_model.fittable_params = ["F0", "F1"]
        mock_model.free_params = ["F0", "F1"]

        result = get_parameter_identifiability_from_model(mock_model, "NONEXISTENT")
        assert result is False


class TestIsAstrometryParameter:
    """Test _is_astrometry_parameter helper function."""

    def test_astrometry_parameter_true(self, mock_astrometry_components):
        """Test that astrometry parameters are correctly identified."""
        with patch("ipta_metapulsar.pint_helpers.AllComponents") as mock_all_components:
            mock_all_components.return_value = mock_astrometry_components

            # Test expected astrometry parameters
            for param in EXPECTED_ASTROMETRY_PARAMS:
                assert (
                    _is_astrometry_parameter(param) is True
                ), f"Parameter {param} should be identified as astrometry"

    def test_astrometry_parameter_false(self, mock_astrometry_components):
        """Test that non-astrometry parameters are correctly identified."""
        with patch("ipta_metapulsar.pint_helpers.AllComponents") as mock_all_components:
            mock_all_components.return_value = mock_astrometry_components

            # Test non-astrometry parameters
            non_astrometry_params = ["XDOT", "E", "F0", "F1", "PEPOCH", "NONEXISTENT"]
            for param in non_astrometry_params:
                assert (
                    _is_astrometry_parameter(param) is False
                ), f"Parameter {param} should not be identified as astrometry"

    def test_empty_parameter_name(self, mock_astrometry_components):
        """Test handling of empty parameter name."""
        with patch("ipta_metapulsar.pint_helpers.AllComponents") as mock_all_components:
            mock_all_components.return_value = mock_astrometry_components

            assert _is_astrometry_parameter("") is False

    def test_none_parameter_name(self, mock_astrometry_components):
        """Test handling of None parameter name."""
        with patch("ipta_metapulsar.pint_helpers.AllComponents") as mock_all_components:
            mock_all_components.return_value = mock_astrometry_components

            assert _is_astrometry_parameter(None) is False
