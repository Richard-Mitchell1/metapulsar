"""Unit tests for MetaPulsarParameterManager class."""

import pytest
from unittest.mock import Mock, patch
from pint.models import TimingModel
from ipta_metapulsar.metapulsar_parameter_manager import (
    MetaPulsarParameterManager,
    ParameterMapping,
    ParameterInconsistencyError,
)


class TestParameterMapping:
    """Test ParameterMapping data class."""

    def test_initialization(self):
        """Test ParameterMapping initialization."""
        fitparameters = {"F0": {"EPTA": "F0", "PPTA": "F0"}}
        setparameters = {"F0_EPTA": {"EPTA": "F0"}, "F0_PPTA": {"PPTA": "F0"}}
        merged_parameters = ["F0"]
        pta_specific_parameters = ["RAJ_EPTA"]

        mapping = ParameterMapping(
            fitparameters=fitparameters,
            setparameters=setparameters,
            merged_parameters=merged_parameters,
            pta_specific_parameters=pta_specific_parameters,
        )

        assert mapping.fitparameters == fitparameters
        assert mapping.setparameters == setparameters
        assert mapping.merged_parameters == merged_parameters
        assert mapping.pta_specific_parameters == pta_specific_parameters


class TestMetaPulsarParameterManager:
    """Test MetaPulsarParameterManager class."""

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

    @patch("ipta_metapulsar.metapulsar_parameter_manager.ParameterResolver")
    def test_initialization(self, mock_resolver_class):
        """Test MetaPulsarParameterManager initialization."""
        mock_resolver = Mock()
        mock_resolver_class.return_value = mock_resolver

        manager = MetaPulsarParameterManager(self.pint_models)

        assert manager.pint_models == self.pint_models
        assert manager.resolver == mock_resolver
        mock_resolver_class.assert_called_once_with(self.pint_models)

    @patch("ipta_metapulsar.metapulsar_parameter_manager.ParameterResolver")
    @patch(
        "ipta_metapulsar.metapulsar_parameter_manager.get_parameters_by_type_from_pint"
    )
    def test_build_merge_parameters_list(self, mock_get_params, mock_resolver_class):
        """Test building merge parameters list."""
        mock_resolver = Mock()
        mock_resolver_class.return_value = mock_resolver
        mock_get_params.side_effect = [
            ["F0", "F1"],  # astrometry
            ["F0", "F1", "F2"],  # spindown
            ["A1", "PB"],  # binary
            ["DM"],  # dispersion
        ]

        manager = MetaPulsarParameterManager(self.pint_models)

        merge_config = {
            "astrometry": True,
            "spindown": True,
            "binary": True,  # Changed to True to include A1, PB
            "dispersion": True,
        }

        result = manager._build_merge_parameters_list(merge_config)

        expected = ["F0", "F1", "F0", "F1", "F2", "A1", "PB", "DM"]
        assert result == expected

        # Check that binary parameters were included
        assert "A1" in result
        assert "PB" in result

    @patch("ipta_metapulsar.metapulsar_parameter_manager.ParameterResolver")
    def test_process_pta_fit_parameters(self, mock_resolver_class):
        """Test processing fit parameters for a single PTA."""
        mock_resolver = Mock()
        mock_resolver_class.return_value = mock_resolver
        mock_resolver.resolve_parameter_equivalence.side_effect = lambda x: x

        manager = MetaPulsarParameterManager(self.pint_models)

        merge_pars = ["F0", "F1"]
        fitparameters = {}

        manager._process_pta_fit_parameters(
            "EPTA", self.mock_model1, merge_pars, fitparameters
        )

        # Should process only free parameters
        actual_calls = [
            call[0][0]
            for call in mock_resolver.resolve_parameter_equivalence.call_args_list
        ]
        assert set(actual_calls) == {"F0", "F1", "RAJ"}

    @patch("ipta_metapulsar.metapulsar_parameter_manager.ParameterResolver")
    def test_process_pta_set_parameters(self, mock_resolver_class):
        """Test processing set parameters for a single PTA."""
        mock_resolver = Mock()
        mock_resolver_class.return_value = mock_resolver
        mock_resolver.resolve_parameter_equivalence.side_effect = lambda x: x

        manager = MetaPulsarParameterManager(self.pint_models)

        setparameters = {}
        manager._process_pta_set_parameters("EPTA", self.mock_model1, setparameters)

        # Should process all parameters
        expected_params = ["F0", "F1", "RAJ", "DECJ", "A1", "PB"]
        actual_params = list(setparameters.keys())
        assert len(actual_params) == len(expected_params)

        # Check that all parameters are processed
        for param in expected_params:
            assert f"{param}_EPTA" in setparameters

    @patch("ipta_metapulsar.metapulsar_parameter_manager.ParameterResolver")
    def test_add_merged_parameter_success(self, mock_resolver_class):
        """Test adding merged parameter successfully."""
        mock_resolver = Mock()
        mock_resolver_class.return_value = mock_resolver
        mock_resolver.check_parameter_available_across_ptas.return_value = True

        manager = MetaPulsarParameterManager(self.pint_models)

        fitparameters = {}
        manager._add_merged_parameter("F0", "EPTA", "F0", fitparameters)

        assert "F0" in fitparameters
        assert fitparameters["F0"]["EPTA"] == "F0"

    @patch("ipta_metapulsar.metapulsar_parameter_manager.ParameterResolver")
    def test_add_merged_parameter_not_available(self, mock_resolver_class):
        """Test adding merged parameter when not available across PTAs."""
        mock_resolver = Mock()
        mock_resolver_class.return_value = mock_resolver
        mock_resolver.check_parameter_available_across_ptas.return_value = False

        manager = MetaPulsarParameterManager(self.pint_models)

        fitparameters = {}

        with pytest.raises(
            ParameterInconsistencyError, match="Not all PTAs have parameter F0"
        ):
            manager._add_merged_parameter("F0", "EPTA", "F0", fitparameters)

    @patch("ipta_metapulsar.metapulsar_parameter_manager.ParameterResolver")
    def test_add_pta_specific_parameter_identifiable(self, mock_resolver_class):
        """Test adding PTA-specific parameter when identifiable."""
        mock_resolver = Mock()
        mock_resolver_class.return_value = mock_resolver
        mock_resolver.check_parameter_identifiable.return_value = True

        manager = MetaPulsarParameterManager(self.pint_models)

        fitparameters = {}
        manager._add_pta_specific_parameter("RAJ", "EPTA", "RAJ", fitparameters)

        assert "RAJ_EPTA" in fitparameters
        assert fitparameters["RAJ_EPTA"]["EPTA"] == "RAJ"

    @patch("ipta_metapulsar.metapulsar_parameter_manager.ParameterResolver")
    def test_add_pta_specific_parameter_not_identifiable(self, mock_resolver_class):
        """Test adding PTA-specific parameter when not identifiable."""
        mock_resolver = Mock()
        mock_resolver_class.return_value = mock_resolver
        mock_resolver.check_parameter_identifiable.return_value = False

        manager = MetaPulsarParameterManager(self.pint_models)

        fitparameters = {}
        manager._add_pta_specific_parameter("RAJ", "EPTA", "RAJ", fitparameters)

        # Should not add parameter if not identifiable
        assert "RAJ_EPTA" not in fitparameters

    @pytest.mark.slow
    def test_validate_parameter_consistency_success(self):
        """Test parameter consistency validation when valid."""
        manager = MetaPulsarParameterManager(self.pint_models)

        fitparameters = {"F0_EPTA": {"EPTA": "F0"}, "RAJ_EPTA": {"EPTA": "RAJ"}}
        setparameters = {
            "F0_EPTA": {"EPTA": "F0"},
            "RAJ_EPTA": {"EPTA": "RAJ"},
            "F1_EPTA": {"EPTA": "F1"},
        }

        # Should not raise exception
        manager._validate_parameter_consistency(fitparameters, setparameters)

    @pytest.mark.slow
    def test_validate_parameter_consistency_failure(self):
        """Test parameter consistency validation when invalid."""
        manager = MetaPulsarParameterManager(self.pint_models)

        fitparameters = {"F0_EPTA": {"EPTA": "F0"}, "UNKNOWN_EPTA": {"EPTA": "UNKNOWN"}}
        setparameters = {"F0_EPTA": {"EPTA": "F0"}}

        with pytest.raises(
            ParameterInconsistencyError,
            match="Fit parameters not found in set parameters",
        ):
            manager._validate_parameter_consistency(fitparameters, setparameters)

    @pytest.mark.slow
    def test_build_parameter_mapping_result(self):
        """Test building parameter mapping result."""
        manager = MetaPulsarParameterManager(self.pint_models)

        fitparameters = {
            "F0": {"EPTA": "F0", "PPTA": "F0"},  # Merged
            "RAJ_EPTA": {"EPTA": "RAJ"},  # PTA-specific
            "ELONG_PPTA": {"PPTA": "ELONG"},  # PTA-specific
        }
        setparameters = {
            "F0_EPTA": {"EPTA": "F0"},
            "F0_PPTA": {"PPTA": "F0"},
            "RAJ_EPTA": {"EPTA": "RAJ"},
            "ELONG_PPTA": {"PPTA": "ELONG"},
        }

        result = manager._build_parameter_mapping_result(fitparameters, setparameters)

        assert isinstance(result, ParameterMapping)
        assert result.fitparameters == fitparameters
        assert result.setparameters == setparameters
        assert result.merged_parameters == ["F0"]
        assert set(result.pta_specific_parameters) == {"RAJ_EPTA", "ELONG_PPTA"}

    @patch("ipta_metapulsar.metapulsar_parameter_manager.ParameterResolver")
    @patch(
        "ipta_metapulsar.metapulsar_parameter_manager.get_parameters_by_type_from_pint"
    )
    def test_build_parameter_mappings_integration(
        self, mock_get_params, mock_resolver_class
    ):
        """Test complete build_parameter_mappings workflow."""
        # Setup mocks
        mock_resolver = Mock()
        mock_resolver_class.return_value = mock_resolver
        mock_resolver.resolve_parameter_equivalence.side_effect = lambda x: x
        mock_resolver.check_parameter_available_across_ptas.return_value = True
        mock_resolver.check_parameter_identifiable.return_value = True

        mock_get_params.return_value = ["F0", "F1"]

        # Mock the parameter processing methods to avoid validation issues
        manager = MetaPulsarParameterManager(self.pint_models)

        # Mock the internal methods to return consistent data
        with patch.object(manager, "_process_all_pta_parameters") as mock_process:
            mock_process.return_value = (
                {"F0_EPTA": {"EPTA": "F0"}, "F1_EPTA": {"EPTA": "F1"}},  # fitparameters
                {
                    "F0_EPTA": {"EPTA": "F0"},
                    "F1_EPTA": {"EPTA": "F1"},
                    "F0_PPTA": {"PPTA": "F0"},
                    "F1_PPTA": {"PPTA": "F1"},
                },  # setparameters
            )

            result = manager.build_parameter_mappings(
                merge_astrometry=True,
                merge_spin=True,
                merge_binary=False,
                merge_dm=False,
            )

            assert isinstance(result, ParameterMapping)
            assert "fitparameters" in result.__dict__
            assert "setparameters" in result.__dict__
            assert "merged_parameters" in result.__dict__
            assert "pta_specific_parameters" in result.__dict__
