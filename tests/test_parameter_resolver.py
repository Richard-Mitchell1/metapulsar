"""Unit tests for ParameterResolver class."""

from unittest.mock import Mock, patch
from pint.models import TimingModel
from metapulsar.parameter_resolver import ParameterResolver
from metapulsar.pint_helpers import _is_astrometry_parameter


class TestParameterResolver:
    """Test ParameterResolver class."""

    def setup_method(self):
        """Set up test fixtures."""
        # Create mock PINT models
        self.mock_model1 = Mock(spec=TimingModel)
        self.mock_model1.params = ["F0", "F1", "RAJ", "DECJ", "A1", "PB"]
        self.mock_model1.free_params = ["F0", "F1", "RAJ"]
        self.mock_model1.fittable_params = ["F0", "F1", "RAJ", "DECJ"]

        self.mock_model2 = Mock(spec=TimingModel)
        self.mock_model2.params = ["F0", "F1", "ELONG", "ELAT", "A1", "PB"]
        self.mock_model2.free_params = ["F0", "F1", "ELONG"]
        self.mock_model2.fittable_params = ["F0", "F1", "ELONG", "ELAT"]

        self.pint_models = {"EPTA": self.mock_model1, "PPTA": self.mock_model2}

    @patch("metapulsar.parameter_resolver.get_parameter_aliases_from_pint")
    def test_initialization(self, mock_get_aliases):
        """Test ParameterResolver initialization."""
        mock_get_aliases.return_value = {"XDOT": "A1DOT", "E": "ECC"}

        resolver = ParameterResolver(self.pint_models)

        assert resolver.pint_models == self.pint_models
        assert resolver._aliases == {"XDOT": "A1DOT", "E": "ECC"}
        assert resolver._reverse_aliases == {"A1DOT": ["XDOT"], "ECC": ["E"]}

    @patch("metapulsar.parameter_resolver.get_parameter_aliases_from_pint")
    def test_resolve_parameter_equivalence(self, mock_get_aliases):
        """Test parameter alias resolution."""
        mock_get_aliases.return_value = {"XDOT": "A1DOT", "E": "ECC"}
        resolver = ParameterResolver(self.pint_models)

        # Test alias resolution
        assert resolver.resolve_parameter_equivalence("XDOT") == "A1DOT"
        assert resolver.resolve_parameter_equivalence("E") == "ECC"

        # Test non-alias parameter
        assert resolver.resolve_parameter_equivalence("F0") == "F0"

    @patch("metapulsar.parameter_resolver.get_parameter_aliases_from_pint")
    def test_check_parameter_available_across_ptas_astrometry(self, mock_get_aliases):
        """Test parameter availability checking for astrometry parameters."""
        mock_get_aliases.return_value = {}
        resolver = ParameterResolver(self.pint_models)

        # Mock component availability check
        with patch.object(
            resolver, "check_component_available_across_ptas", return_value=True
        ):
            result = resolver.check_parameter_available_across_ptas("RAJ")
            assert result is True

    @patch("metapulsar.parameter_resolver.get_parameter_aliases_from_pint")
    def test_check_parameter_available_across_ptas_other(self, mock_get_aliases):
        """Test parameter availability checking for non-astrometry parameters."""
        mock_get_aliases.return_value = {"XDOT": "A1DOT"}
        resolver = ParameterResolver(self.pint_models)

        # Test parameter available in all models
        result = resolver.check_parameter_available_across_ptas("F0")
        assert result is True

        # Test parameter not available in all models
        result = resolver.check_parameter_available_across_ptas("UNKNOWN")
        assert result is False

    @patch("metapulsar.parameter_resolver.get_parameter_aliases_from_pint")
    def test_check_component_available_across_ptas(self, mock_get_aliases):
        """Test component availability checking across PTAs."""
        mock_get_aliases.return_value = {}
        resolver = ParameterResolver(self.pint_models)

        with patch(
            "metapulsar.parameter_resolver.check_component_available_in_model"
        ) as mock_check:
            # All models have component
            mock_check.side_effect = [True, True]
            result = resolver.check_component_available_across_ptas("astrometry")
            assert result is True

            # Not all models have component
            mock_check.side_effect = [True, False]
            result = resolver.check_component_available_across_ptas("astrometry")
            assert result is False

    @patch("metapulsar.parameter_resolver.get_parameter_aliases_from_pint")
    def test_check_parameter_identifiable(self, mock_get_aliases):
        """Test parameter identifiability checking."""
        mock_get_aliases.return_value = {}
        resolver = ParameterResolver(self.pint_models)

        with patch(
            "metapulsar.parameter_resolver.get_parameter_identifiability_from_model"
        ) as mock_check:
            # Parameter is identifiable
            mock_check.return_value = True
            result = resolver.check_parameter_identifiable("EPTA", "F0")
            assert result is True
            mock_check.assert_called_once_with(self.mock_model1, "F0")

            # Parameter is not identifiable
            mock_check.return_value = False
            result = resolver.check_parameter_identifiable("EPTA", "F0")
            assert result is False

            # Unknown PTA
            result = resolver.check_parameter_identifiable("UNKNOWN", "F0")
            assert result is False

    @patch("metapulsar.parameter_resolver.get_parameter_aliases_from_pint")
    def test_get_all_possible_parameter_names(self, mock_get_aliases):
        """Test getting all possible parameter names including aliases."""
        mock_get_aliases.return_value = {"XDOT": "A1DOT", "E": "ECC"}
        resolver = ParameterResolver(self.pint_models)

        # Test canonical parameter
        result = resolver._get_all_possible_parameter_names("F0")
        assert result == ["F0"]

        # Test parameter with aliases
        result = resolver._get_all_possible_parameter_names("A1DOT")
        assert set(result) == {"A1DOT", "XDOT"}

        # Test alias parameter
        result = resolver._get_all_possible_parameter_names("XDOT")
        assert set(result) == {"A1DOT", "XDOT"}

    @patch("metapulsar.parameter_resolver.get_parameter_aliases_from_pint")
    def test_is_astrometry_parameter(self, mock_get_aliases):
        """Test astrometry parameter identification."""
        mock_get_aliases.return_value = {}

        # Test astrometry parameters
        assert _is_astrometry_parameter("RAJ") is True
        assert _is_astrometry_parameter("DECJ") is True
        assert _is_astrometry_parameter("ELONG") is True
        assert _is_astrometry_parameter("PMRA") is True

        # Test non-astrometry parameters
        assert _is_astrometry_parameter("F0") is False
        assert _is_astrometry_parameter("A1") is False
        assert _is_astrometry_parameter("PB") is False
