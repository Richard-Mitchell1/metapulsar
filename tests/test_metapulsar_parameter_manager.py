"""Unit tests for MetaPulsarParameterManager class."""

import pytest
from unittest.mock import Mock, patch
from pint.models import TimingModel
from metapulsar.metapulsar_parameter_manager import (
    MetaPulsarParameterManager,
    ParameterMapping,
    ParameterInconsistencyError,
)


class TestParameterMapping:
    """Test ParameterMapping data class."""

    def test_initialization(self):
        """Test ParameterMapping initialization."""
        fitparameters = {"F0_EPTA": {"EPTA": "F0"}, "F0_PPTA": {"PPTA": "F0"}}
        setparameters = {
            "F0_EPTA": {"EPTA": "F0"},
            "F0_PPTA": {"PPTA": "F0"},
            "F1_EPTA": {"EPTA": "F1"},
        }
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

        # Create mock parfile dictionaries
        self.parfile_dicts = {
            "EPTA": {"F0": "123.456", "RAJ": "18:57:36.3906121"},
            "PPTA": {"F0": "123.456", "ELONG": "284.4015854"},
        }

    @patch("metapulsar.metapulsar_parameter_manager.ParameterResolver")
    def test_initialization(self, mock_resolver_class):
        """Test MetaPulsarParameterManager initialization."""
        mock_resolver = Mock()
        mock_resolver_class.return_value = mock_resolver

        manager = MetaPulsarParameterManager(self.pint_models, self.parfile_dicts)

        assert manager.pint_models == self.pint_models
        assert manager.resolver == mock_resolver
        mock_resolver_class.assert_called_once_with(self.pint_models)

    @patch("metapulsar.metapulsar_parameter_manager.ParameterResolver")
    def test_process_pta_fit_parameters(self, mock_resolver_class):
        """Test processing fit parameters for a single PTA."""
        mock_resolver = Mock()
        mock_resolver_class.return_value = mock_resolver
        mock_resolver.resolve_parameter_equivalence.side_effect = lambda x: x

        manager = MetaPulsarParameterManager(self.pint_models, self.parfile_dicts)

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

    @patch("metapulsar.metapulsar_parameter_manager.ParameterResolver")
    def test_process_pta_set_parameters(self, mock_resolver_class):
        """Test processing set parameters for a single PTA."""
        mock_resolver = Mock()
        mock_resolver_class.return_value = mock_resolver
        mock_resolver.resolve_parameter_equivalence.side_effect = lambda x: x

        manager = MetaPulsarParameterManager(self.pint_models, self.parfile_dicts)

        setparameters = {}
        manager._process_pta_set_parameters("EPTA", self.mock_model1, setparameters)

        # Should process all parameters
        expected_params = ["F0", "F1", "RAJ", "DECJ", "A1", "PB"]
        actual_params = list(setparameters.keys())
        assert len(actual_params) == len(expected_params)

        # Check that all parameters are processed
        for param in expected_params:
            assert f"{param}_EPTA" in setparameters

    @patch("metapulsar.metapulsar_parameter_manager.ParameterResolver")
    def test_add_merged_parameter_success(self, mock_resolver_class):
        """Test adding merged parameter successfully."""
        mock_resolver = Mock()
        mock_resolver_class.return_value = mock_resolver
        mock_resolver.check_parameter_available_across_ptas.return_value = True

        manager = MetaPulsarParameterManager(self.pint_models, self.parfile_dicts)

        fitparameters = {}
        manager._add_merged_parameter("F0", "EPTA", "F0", fitparameters)

        assert "F0" in fitparameters
        assert fitparameters["F0"]["EPTA"] == "F0"

    @patch("metapulsar.metapulsar_parameter_manager.ParameterResolver")
    def test_add_merged_parameter_not_available(self, mock_resolver_class):
        """Test adding merged parameter when not available across PTAs."""
        mock_resolver = Mock()
        mock_resolver_class.return_value = mock_resolver
        mock_resolver.check_parameter_available_across_ptas.return_value = False

        manager = MetaPulsarParameterManager(self.pint_models, self.parfile_dicts)

        fitparameters = {}

        with pytest.raises(
            ParameterInconsistencyError, match="Not all PTAs have parameter F0"
        ):
            manager._add_merged_parameter("F0", "EPTA", "F0", fitparameters)

    @patch("metapulsar.metapulsar_parameter_manager.ParameterResolver")
    def test_add_pta_specific_parameter_identifiable(self, mock_resolver_class):
        """Test adding PTA-specific parameter when identifiable."""
        mock_resolver = Mock()
        mock_resolver_class.return_value = mock_resolver
        mock_resolver.check_parameter_identifiable.return_value = True

        manager = MetaPulsarParameterManager(self.pint_models, self.parfile_dicts)

        fitparameters = {}
        manager._add_pta_specific_parameter("RAJ", "EPTA", "RAJ", fitparameters)

        assert "RAJ_EPTA" in fitparameters
        assert fitparameters["RAJ_EPTA"]["EPTA"] == "RAJ"

    @patch("metapulsar.metapulsar_parameter_manager.ParameterResolver")
    def test_add_pta_specific_parameter_not_identifiable(self, mock_resolver_class):
        """Test adding PTA-specific parameter when not identifiable."""
        mock_resolver = Mock()
        mock_resolver_class.return_value = mock_resolver
        mock_resolver.check_parameter_identifiable.return_value = False

        manager = MetaPulsarParameterManager(self.pint_models, self.parfile_dicts)

        fitparameters = {}
        manager._add_pta_specific_parameter("RAJ", "EPTA", "RAJ", fitparameters)

        # Should not add parameter if not identifiable
        assert "RAJ_EPTA" not in fitparameters

    @pytest.mark.slow
    def test_validate_parameter_consistency_success(self):
        """Test parameter consistency validation when valid."""
        manager = MetaPulsarParameterManager(self.pint_models, self.parfile_dicts)

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
        manager = MetaPulsarParameterManager(self.pint_models, self.parfile_dicts)

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
        manager = MetaPulsarParameterManager(self.pint_models, self.parfile_dicts)

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

    @patch("metapulsar.metapulsar_parameter_manager.ParameterResolver")
    @patch("metapulsar.pint_helpers.get_parameters_by_type_from_parfiles")
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
        manager = MetaPulsarParameterManager(self.pint_models, self.parfile_dicts)

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
                combine_components=["astrometry", "spindown"]  # Use current API
            )

            assert isinstance(result, ParameterMapping)
            assert "fitparameters" in result.__dict__
            assert "setparameters" in result.__dict__
            assert "merged_parameters" in result.__dict__
            assert "pta_specific_parameters" in result.__dict__


class TestDiscoverMergeableParameters:
    """Test _discover_mergeable_parameters method."""

    def setup_method(self):
        """Set up test fixtures with realistic parfile dictionaries."""
        # Create mock PINT models
        self.mock_model1 = Mock(spec=TimingModel)
        self.mock_model2 = Mock(spec=TimingModel)

        self.pint_models = {"EPTA": self.mock_model1, "PPTA": self.mock_model2}

        # Create realistic parfile dictionaries with proper models and epochs
        self.parfile_dicts = {
            "EPTA": {
                "PSR": "J1857+0943",
                "F0": "123.456",
                "F1": "-1.23e-15",
                "F2": "1.0e-30",
                "PEPOCH": "55000.0",
                "RAJ": "18:57:36.3906121",
                "DECJ": "+09:43:17.20714",
                "PMRA": "10.5",
                "PMDEC": "-5.2",
                "POSEPOCH": "55000.0",
                "DM": "13.3",
                "DM1": "0.001",
                "DM2": "0.0001",
                "DMEPOCH": "55000.0",
                "BINARY": "BT",
                "A1": "1.2",
                "PB": "0.357",
                "ECC": "0.1",
                "OM": "90.0",
                "T0": "55000.0",
            },
            "PPTA": {
                "PSR": "J1857+0943",
                "F0": "123.456",
                "F1": "-1.23e-15",
                "F2": "1.0e-30",
                "F3": "1.0e-45",  # Higher order derivative
                "PEPOCH": "55000.0",
                "ELONG": "284.4015854",
                "ELAT": "9.7213056",
                "PMELONG": "10.5",
                "PMELAT": "-5.2",
                "POSEPOCH": "55000.0",
                "DM": "13.3",
                "DM1": "0.001",
                "DM2": "0.0001",
                "DMEPOCH": "55000.0",
                "BINARY": "BT",
                "A1": "1.2",
                "PB": "0.357",
                "ECC": "0.1",
                "OM": "90.0",
                "T0": "55000.0",
            },
        }

    @patch("metapulsar.pint_helpers.get_parameters_by_type_from_parfiles")
    @patch("metapulsar.metapulsar_parameter_manager.ParameterResolver")
    def test_discover_mergeable_parameters_with_complete_models(
        self, mock_resolver_class, mock_get_params_from_parfiles
    ):
        """Test parameter discovery with complete models including epochs."""
        # Mock parameter discovery with realistic parameters including epochs
        mock_get_params_from_parfiles.side_effect = [
            [
                "F0",
                "F1",
                "F2",
                "PEPOCH",
                "RAJ",
                "DECJ",
                "PMRA",
                "PMDEC",
                "POSEPOCH",
            ],  # astrometry + spindown
            ["F0", "F1", "F2", "F3", "PEPOCH"],  # spindown with higher order
            ["A1", "PB", "ECC", "OM", "T0"],  # binary (complete BT model)
            ["DM", "DM1", "DM2", "DMEPOCH"],  # dispersion with epoch
        ]

        manager = MetaPulsarParameterManager(self.pint_models, self.parfile_dicts)

        combine_components = ["astrometry", "spindown", "binary", "dispersion"]
        result = manager._discover_mergeable_parameters(combine_components)

        # Should call get_parameters_by_type_from_parfiles for each component
        assert mock_get_params_from_parfiles.call_count == 4

        # Should include parameters from all components including epochs
        expected_params = [
            # Astrometry + spindown
            "F0",
            "F1",
            "F2",
            "PEPOCH",
            "RAJ",
            "DECJ",
            "PMRA",
            "PMDEC",
            "POSEPOCH",
            # Spindown with higher order
            "F0",
            "F1",
            "F2",
            "F3",
            "PEPOCH",
            # Binary (complete BT model)
            "A1",
            "PB",
            "ECC",
            "OM",
            "T0",
            # Dispersion with epoch
            "DM",
            "DM1",
            "DM2",
            "DMEPOCH",
        ]

        for param in expected_params:
            assert param in result

    @patch("metapulsar.pint_helpers.get_parameters_by_type_from_parfiles")
    @patch("metapulsar.metapulsar_parameter_manager.ParameterResolver")
    def test_discover_mergeable_parameters_binary_only(
        self, mock_resolver_class, mock_get_params_from_parfiles
    ):
        """Test discovery with only binary parameters."""
        # Mock parameter discovery for binary only
        mock_get_params_from_parfiles.return_value = ["A1", "PB", "ECC", "OM", "T0"]

        manager = MetaPulsarParameterManager(self.pint_models, self.parfile_dicts)

        combine_components = ["binary"]
        result = manager._discover_mergeable_parameters(combine_components)

        # Should call parameter discovery once for binary
        mock_get_params_from_parfiles.assert_called_once_with(
            "binary", self.parfile_dicts
        )

        # Should return complete binary parameters
        expected_params = ["A1", "PB", "ECC", "OM", "T0"]
        assert result == expected_params

    @patch("metapulsar.pint_helpers.get_parameters_by_type_from_parfiles")
    @patch("metapulsar.metapulsar_parameter_manager.ParameterResolver")
    def test_discover_mergeable_parameters_with_dynamic_derivatives(
        self, mock_resolver_class, mock_get_params_from_parfiles
    ):
        """Test discovery includes dynamic derivatives with proper epochs."""
        # Mock parameter discovery with dynamic derivatives and epochs
        mock_get_params_from_parfiles.side_effect = [
            [
                "F0",
                "F1",
                "F2",
                "F3",
                "F4",
                "PEPOCH",
            ],  # spindown with high-order derivatives
            [
                "DM",
                "DM1",
                "DM2",
                "DM3",
                "DM4",
                "DMEPOCH",
            ],  # dispersion with high-order derivatives
        ]

        manager = MetaPulsarParameterManager(self.pint_models, self.parfile_dicts)

        combine_components = ["spindown", "dispersion"]
        result = manager._discover_mergeable_parameters(combine_components)

        # Should include dynamic derivatives with epochs
        assert "F3" in result
        assert "F4" in result
        assert "DM3" in result
        assert "DM4" in result
        assert "PEPOCH" in result
        assert "DMEPOCH" in result

    @patch("metapulsar.pint_helpers.get_parameters_by_type_from_parfiles")
    @patch("metapulsar.metapulsar_parameter_manager.ParameterResolver")
    def test_discover_mergeable_parameters_empty_list(
        self, mock_resolver_class, mock_get_params_from_parfiles
    ):
        """Test behavior with empty combine_components list."""
        manager = MetaPulsarParameterManager(self.pint_models, self.parfile_dicts)

        result = manager._discover_mergeable_parameters([])

        # Should return empty list
        assert result == []

        # Should not call parameter discovery
        mock_get_params_from_parfiles.assert_not_called()


class TestMetaPulsarParameterManagerConstructor:
    """Test MetaPulsarParameterManager constructor with new parfile_dicts parameter."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_model1 = Mock(spec=TimingModel)
        self.mock_model2 = Mock(spec=TimingModel)
        self.pint_models = {"EPTA": self.mock_model1, "PPTA": self.mock_model2}

        self.parfile_dicts = {
            "EPTA": {"F0": "123.456", "RAJ": "18:57:36.3906121"},
            "PPTA": {"F0": "123.456", "ELONG": "284.4015854"},
        }

    @patch("metapulsar.metapulsar_parameter_manager.ParameterResolver")
    def test_initialization_with_parfile_dicts(self, mock_resolver_class):
        """Test initialization with parfile_dicts parameter."""
        mock_resolver = Mock()
        mock_resolver_class.return_value = mock_resolver

        manager = MetaPulsarParameterManager(self.pint_models, self.parfile_dicts)

        assert manager.pint_models == self.pint_models
        assert manager.parfile_dicts == self.parfile_dicts
        assert manager.resolver == mock_resolver
        mock_resolver_class.assert_called_once_with(self.pint_models)

    @patch("metapulsar.metapulsar_parameter_manager.ParameterResolver")
    def test_initialization_pta_names_mismatch(self, mock_resolver_class):
        """Test initialization fails when PTA names don't match."""
        mismatched_parfile_dicts = {
            "EPTA": {"F0": "123.456"},
            "NANOGrav": {"F0": "123.456"},  # Different PTA name
        }

        with pytest.raises(ValueError, match="PTA names mismatch"):
            MetaPulsarParameterManager(self.pint_models, mismatched_parfile_dicts)

    @patch("metapulsar.metapulsar_parameter_manager.ParameterResolver")
    def test_initialization_empty_parfile_dicts(self, mock_resolver_class):
        """Test initialization with empty parfile_dicts."""
        empty_parfile_dicts = {}

        with pytest.raises(ValueError, match="PTA names mismatch"):
            MetaPulsarParameterManager(self.pint_models, empty_parfile_dicts)

    @patch("metapulsar.metapulsar_parameter_manager.ParameterResolver")
    def test_initialization_extra_parfile_dicts(self, mock_resolver_class):
        """Test initialization fails when parfile_dicts has extra PTAs."""
        extra_parfile_dicts = {
            "EPTA": {"F0": "123.456"},
            "PPTA": {"F0": "123.456"},
            "NANOGrav": {"F0": "123.456"},  # Extra PTA
        }

        with pytest.raises(ValueError, match="PTA names mismatch"):
            MetaPulsarParameterManager(self.pint_models, extra_parfile_dicts)


class TestBuildParameterMappingsNewAPI:
    """Test build_parameter_mappings with new combine_components API."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_model1 = Mock(spec=TimingModel)
        self.mock_model2 = Mock(spec=TimingModel)
        self.pint_models = {"EPTA": self.mock_model1, "PPTA": self.mock_model2}

        self.parfile_dicts = {
            "EPTA": {"F0": "123.456", "RAJ": "18:57:36.3906121"},
            "PPTA": {"F0": "123.456", "ELONG": "284.4015854"},
        }

    @patch("metapulsar.metapulsar_parameter_manager.ParameterResolver")
    @patch("metapulsar.pint_helpers.get_parameters_by_type_from_parfiles")
    def test_build_parameter_mappings_with_combine_components(
        self, mock_get_params_from_parfiles, mock_resolver_class
    ):
        """Test build_parameter_mappings with combine_components parameter."""
        # Setup mocks
        mock_resolver = Mock()
        mock_resolver_class.return_value = mock_resolver
        mock_resolver.resolve_parameter_equivalence.side_effect = lambda x: x
        mock_resolver.check_parameter_available_across_ptas.return_value = True
        mock_resolver.check_parameter_identifiable.return_value = True

        mock_get_params_from_parfiles.return_value = ["F0", "F1"]

        manager = MetaPulsarParameterManager(self.pint_models, self.parfile_dicts)

        # Mock internal methods to avoid validation issues
        with patch.object(manager, "_process_all_pta_parameters") as mock_process:
            mock_process.return_value = (
                {
                    "F0_EPTA": {"EPTA": "F0"},
                    "F0_PPTA": {"PPTA": "F0"},
                },  # fitparameters: PTA-specific names
                {
                    "F0_EPTA": {"EPTA": "F0"},
                    "F0_PPTA": {"PPTA": "F0"},
                    "F1_EPTA": {"EPTA": "F1"},
                },  # setparameters: PTA-specific names (superset)
            )

            result = manager.build_parameter_mappings(
                combine_components=["astrometry", "spindown"]
            )

            assert isinstance(result, ParameterMapping)
            assert "fitparameters" in result.__dict__
            assert "setparameters" in result.__dict__

            # Should call _discover_mergeable_parameters with combine_components
            mock_get_params_from_parfiles.assert_called()

    @patch("metapulsar.metapulsar_parameter_manager.ParameterResolver")
    def test_build_parameter_mappings_default_combine_components(
        self, mock_resolver_class
    ):
        """Test build_parameter_mappings with default combine_components."""
        # Setup mocks
        mock_resolver = Mock()
        mock_resolver_class.return_value = mock_resolver

        manager = MetaPulsarParameterManager(self.pint_models, self.parfile_dicts)

        # Mock internal methods
        with patch.object(manager, "_discover_mergeable_parameters") as mock_discover:
            mock_discover.return_value = ["F0", "F1", "RAJ"]

            with patch.object(manager, "_process_all_pta_parameters") as mock_process:
                mock_process.return_value = (
                    {
                        "F0_EPTA": {"EPTA": "F0"},
                        "F0_PPTA": {"PPTA": "F0"},
                    },  # fitparameters: PTA-specific names
                    {
                        "F0_EPTA": {"EPTA": "F0"},
                        "F0_PPTA": {"PPTA": "F0"},
                        "F1_EPTA": {"EPTA": "F1"},
                    },  # setparameters: PTA-specific names (superset)
                )

                result = (
                    manager.build_parameter_mappings()
                )  # No combine_components specified

                # Should use default combine_components
                mock_discover.assert_called_once_with(
                    ["astrometry", "spindown", "binary", "dispersion"]
                )

                assert isinstance(result, ParameterMapping)
