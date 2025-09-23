"""Unit tests for PINT helper functions."""

import pytest
from unittest.mock import Mock, patch
from ipta_metapulsar.pint_helpers import (
    get_parameters_by_type_from_pint,
    get_parameter_aliases_from_pint,
    check_component_available_in_model,
    get_parameter_identifiability_from_model,
    PINTDiscoveryError,
    _is_coordinate_alias,
)


class TestGetParametersByTypeFromPint:
    """Test get_parameters_by_type_from_pint function."""

    def test_astrometry_parameters_discovery(self):
        """Test discovery of astrometry parameters."""
        with patch("ipta_metapulsar.pint_helpers.AllComponents") as mock_all_components:
            # Mock component classes with params attribute
            mock_astrometry_eq = Mock()
            mock_astrometry_eq.return_value.params = ["RAJ", "DECJ", "PMRA", "PMDEC"]

            mock_astrometry_ec = Mock()
            mock_astrometry_ec.return_value.params = [
                "ELONG",
                "ELAT",
                "PMELONG",
                "PMELAT",
            ]

            # Mock AllComponents instance
            mock_instance = Mock()
            mock_instance.category_component_map = {
                "astrometry": ["AstrometryEquatorial", "AstrometryEcliptic"]
            }
            mock_instance.AstrometryEquatorial = mock_astrometry_eq
            mock_instance.AstrometryEcliptic = mock_astrometry_ec

            mock_all_components.return_value = mock_instance

            result = get_parameters_by_type_from_pint("astrometry")

            expected = [
                "RAJ",
                "DECJ",
                "PMRA",
                "PMDEC",
                "ELONG",
                "ELAT",
                "PMELONG",
                "PMELAT",
            ]
            assert set(result) == set(expected)

    def test_spindown_parameters_discovery(self):
        """Test discovery of spindown parameters."""
        with patch("ipta_metapulsar.pint_helpers.AllComponents") as mock_all_components:
            mock_spindown = Mock()
            mock_spindown.return_value.params = ["F0", "F1", "F2", "PEPOCH"]

            mock_instance = Mock()
            mock_instance.category_component_map = {"spindown": ["Spindown"]}
            mock_instance.Spindown = mock_spindown

            mock_all_components.return_value = mock_instance

            result = get_parameters_by_type_from_pint("spindown")
            assert set(result) == {"F0", "F1", "F2", "PEPOCH"}

    def test_unknown_parameter_type(self):
        """Test handling of unknown parameter type."""
        result = get_parameters_by_type_from_pint("unknown_type")
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


class TestIsCoordinateAlias:
    """Test _is_coordinate_alias helper function."""

    def test_coordinate_alias_true(self):
        """Test that coordinate aliases are correctly identified."""
        with patch("ipta_metapulsar.pint_helpers.AllComponents") as mock_all_components:
            # Mock astrometry components for coordinate detection
            mock_instance = Mock()
            mock_instance.category_component_map = {
                "astrometry": ["AstrometryEquatorial", "AstrometryEcliptic"]
            }

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

            assert _is_coordinate_alias("RAJ", "ELONG") is True
            assert _is_coordinate_alias("ELONG", "RAJ") is True
            assert _is_coordinate_alias("PMRA", "PMELONG") is True
            assert _is_coordinate_alias("PMELONG", "PMRA") is True

    def test_coordinate_alias_false(self):
        """Test that non-coordinate aliases are correctly identified."""
        with patch("ipta_metapulsar.pint_helpers.AllComponents") as mock_all_components:
            # Mock astrometry components for coordinate detection
            mock_instance = Mock()
            mock_instance.category_component_map = {
                "astrometry": ["AstrometryEquatorial", "AstrometryEcliptic"]
            }

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

            assert _is_coordinate_alias("XDOT", "A1DOT") is False
            assert _is_coordinate_alias("E", "ECC") is False
            assert _is_coordinate_alias("F0", "F0") is False
