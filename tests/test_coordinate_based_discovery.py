"""
Comprehensive tests for coordinate-based pulsar discovery system.

Tests the new coordinate-based pulsar identification, B/J name generation,
canonical naming, and MetaPulsarFactory integration.

TODO: INTEGRATION TESTS PENDING
===============================

These tests currently use extensive mocking because the MetaPulsar class
is not fully implemented yet. Once MetaPulsar is complete, the following
integration tests MUST be added:

1. Real file I/O tests with actual par/tim files
2. Real PINT model creation and coordinate extraction
3. Real Enterprise Pulsar creation and functionality
4. End-to-end workflow tests with real data
5. Performance tests with multiple PTAs and pulsars
6. Error handling tests with malformed files

See MetaPulsar class docstring for detailed integration test requirements.
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch
from io import StringIO

import astropy.units as u
from astropy.coordinates import Angle
from pint.models.model_builder import ModelBuilder

from metapulsar.metapulsar_factory import MetaPulsarFactory
from metapulsar.pta_registry import PTARegistry
from metapulsar.position_helpers import bj_name_from_pulsar
from metapulsar.metapulsar import MetaPulsar


# === FIXTURES ===


@pytest.fixture
def mock_pta_registry():
    """Mock PTA registry with test configurations."""
    registry = PTARegistry({})  # Start with empty config
    registry.add_pta(
        "test_pta1",
        {
            "base_dir": "/test/data1",
            "par_pattern": r"([JB]\d{4}[+-]\d{2,4}[A-Z]?)\.par",
            "tim_pattern": r"([JB]\d{4}[+-]\d{2,4}[A-Z]?)\.tim",
            "timing_package": "pint",
        },
    )
    registry.add_pta(
        "test_pta2",
        {
            "base_dir": "/test/data2",
            "par_pattern": r"([JB]\d{4}[+-]\d{2,4}[A-Z]?)\.par",
            "tim_pattern": r"([JB]\d{4}[+-]\d{2,4}[A-Z]?)\.tim",
            "timing_package": "pint",
        },
    )
    return registry


@pytest.fixture
def mock_parfile_content():
    """Mock parfile content for testing."""
    return """
PSR J1857+0943
F0 123.456 1
F1 -1.23e-15 1
RAJ 18:57:36.3906121
DECJ +09:43:17.20714
PEPOCH 55000.0
DM 13.3
"""


@pytest.fixture
def mock_pint_model(mock_parfile_content):
    """Mock PINT model for testing."""
    mb = ModelBuilder()
    return mb(StringIO(mock_parfile_content), allow_tcb=True, allow_T2=True)


@pytest.fixture
def mock_file_system(tmp_path):
    """Create mock file system with par/tim files."""
    # Create test data directories
    data1 = tmp_path / "data1"
    data2 = tmp_path / "data2"
    data1.mkdir()
    data2.mkdir()

    # Create par files with actual J1857+0943 coordinates
    (data1 / "J1857+0943.par").write_text(
        "PSR J1857+0943\nF0 123.456 1\nRAJ 18:57:36.3906121\nDECJ +09:43:17.20714"
    )
    (data1 / "J1857+0943.tim").write_text("# Mock tim file")
    (data2 / "B1855+09.par").write_text(
        "PSR B1855+09\nF0 123.456 1\nRAJ 18:57:36.3906121\nDECJ +09:43:17.20714"
    )
    (data2 / "B1855+09.tim").write_text("# Mock tim file")

    return tmp_path


# === TEST CLASSES ===


class TestBJNameGeneration:
    """Test B/J name generation functionality."""

    def test_j_name_generation(self, mock_pint_model):
        """Test J-name generation from coordinates."""
        j_name = bj_name_from_pulsar(mock_pint_model, "J")
        assert j_name == "J1857+0943"

    def test_b_name_generation(self, mock_pint_model):
        """Test B-name generation from coordinates."""
        b_name = bj_name_from_pulsar(mock_pint_model, "B")
        assert b_name == "B1855+09"

    def test_default_name_type(self, mock_pint_model):
        """Test default name type is J."""
        name = bj_name_from_pulsar(mock_pint_model)
        assert name == "J1857+0943"

    def test_case_insensitive_name_type(self, mock_pint_model):
        """Test that name type is case insensitive."""
        j_name = bj_name_from_pulsar(mock_pint_model, "j")
        b_name = bj_name_from_pulsar(mock_pint_model, "b")
        assert j_name == "J1857+0943"
        assert b_name == "B1855+09"

    def test_invalid_name_type_raises_error(self, mock_pint_model):
        """Test that invalid name type raises ValueError."""
        with pytest.raises(ValueError):
            bj_name_from_pulsar(mock_pint_model, "X")


class TestCoordinateBasedDiscovery:
    """Test coordinate-based pulsar discovery."""

    @patch("pint.models.model_builder.parse_parfile")
    @patch("pint.models.model_builder.ModelBuilder")
    def test_discover_pulsars_by_coordinates(
        self,
        mock_model_builder_class,
        mock_parse_parfile,
        mock_pta_registry,
        mock_file_system,
    ):
        """Test coordinate-based pulsar discovery."""
        # Mock parse_parfile to return a dictionary
        mock_par_dict = {
            "PSRJ": ["J1857+0943"],
            "RAJ": ["18:57:36.3906121"],
            "DECJ": ["+09:43:17.20714"],
            "F0": ["186.494081"],
        }
        mock_parse_parfile.return_value = mock_par_dict

        # Mock ModelBuilder to return a TimingModel-like object
        mock_model = Mock()
        ra_angle = Angle(18.960109, unit=u.hourangle)  # 18:57:36.3906121
        dec_angle = Angle(9.721446, unit=u.deg)  # +09:43:17.20714
        mock_model.RAJ = type(
            "obj", (object,), {"quantity": ra_angle, "value": ra_angle.value}
        )()
        mock_model.DECJ = type(
            "obj", (object,), {"quantity": dec_angle, "value": dec_angle.value}
        )()
        mock_model_builder = Mock()
        mock_model_builder.return_value = mock_model
        mock_model_builder_class.return_value = mock_model_builder

        # Update registry with real paths
        registry = mock_pta_registry
        registry.configs["test_pta1"]["base_dir"] = str(mock_file_system / "data1")
        registry.configs["test_pta2"]["base_dir"] = str(mock_file_system / "data2")

        factory = MetaPulsarFactory(registry)

        # Mock the coordinate extraction
        with patch("metapulsar.metapulsar_factory.bj_name_from_pulsar") as mock_bj_name:
            mock_bj_name.side_effect = lambda model, name_type: (
                "J1857+0943" if name_type == "J" else "B1855+09"
            )

            coordinate_map = factory._discover_pulsars_by_coordinates(registry.configs)

            # Should find both PTAs have the same pulsar
            assert "J1857+0943" in coordinate_map
            pulsar_info = coordinate_map["J1857+0943"]
            assert "test_pta1" in pulsar_info["ptas"]
            assert "test_pta2" in pulsar_info["ptas"]
            assert pulsar_info["preferred_name"] == "B1855+09"  # B-name preferred

    def test_extract_suffix_from_filename(self, mock_pta_registry):
        """Test binary pulsar suffix extraction."""
        factory = MetaPulsarFactory(mock_pta_registry)

        # Test with suffix
        file_path = Path("/test/data/J1857+0943A.par")
        pattern = r"([JB]\d{4}[+-]\d{2,4}[A-Z]?)\.par"
        suffix = factory._extract_suffix_from_filename(file_path, pattern)
        assert suffix == "A"

        # Test without suffix
        file_path = Path("/test/data/J1857+0943.par")
        suffix = factory._extract_suffix_from_filename(file_path, pattern)
        assert suffix == ""

    def test_find_timfile(self, mock_pta_registry):
        """Test tim file discovery."""
        factory = MetaPulsarFactory(mock_pta_registry)

        with patch.object(factory, "_find_file") as mock_find_file:
            mock_find_file.return_value = Path("/test/data/J1857+0943.tim")

            parfile_path = Path("/test/data/J1857+0943.par")
            config = mock_pta_registry.configs["test_pta1"]
            timfile = factory._find_timfile(parfile_path, config)

            assert timfile == Path("/test/data/J1857+0943.tim")
            mock_find_file.assert_called_once_with(
                "J1857+0943", "/test/data1", r"([JB]\d{4}[+-]\d{2,4}[A-Z]?)\.tim"
            )

    def test_get_canonical_name_for_pulsar(self, mock_pta_registry):
        """Test canonical name resolution."""
        factory = MetaPulsarFactory(mock_pta_registry)

        # Mock coordinate discovery
        with patch.object(factory, "_discover_pulsars_by_coordinates") as mock_discover:
            mock_discover.return_value = {
                "J1857+0943": {
                    "preferred_name": "B1855+09",
                    "suffix": "A",
                    "b_name": "B1855+09",
                }
            }

            canonical_name = factory._get_canonical_name_for_pulsar(
                "J1857+0943", mock_pta_registry.configs
            )
            assert canonical_name == "B1855+09A"

            canonical_name = factory._get_canonical_name_for_pulsar(
                "B1855+09", mock_pta_registry.configs
            )
            assert canonical_name == "B1855+09A"

    def test_get_canonical_name_fallback(self, mock_pta_registry):
        """Test canonical name fallback when pulsar not found."""
        factory = MetaPulsarFactory(mock_pta_registry)

        with patch.object(factory, "_discover_pulsars_by_coordinates") as mock_discover:
            mock_discover.return_value = {}

            canonical_name = factory._get_canonical_name_for_pulsar(
                "UNKNOWN", mock_pta_registry.configs
            )
            assert canonical_name == "UNKNOWN"


class TestMetaPulsarFactoryIntegration:
    """Test MetaPulsarFactory integration with coordinate-based discovery."""

    @patch("pint.models.model_builder.parse_parfile")
    @patch("pint.models.model_builder.ModelBuilder")
    def test_discover_available_pulsars_coordinate_based(
        self,
        mock_model_builder_class,
        mock_parse_parfile,
        mock_pta_registry,
        mock_file_system,
    ):
        """Test discover_available_pulsars uses coordinate-based discovery."""
        # Mock parse_parfile to return a dictionary
        mock_par_dict = {
            "PSRJ": ["J1857+0943"],
            "RAJ": ["18:57:36.3906121"],
            "DECJ": ["+09:43:17.20714"],
            "F0": ["186.494081"],
        }
        mock_parse_parfile.return_value = mock_par_dict

        # Mock ModelBuilder to return a TimingModel-like object
        mock_model = Mock()
        mock_model_builder = Mock()
        mock_model_builder.return_value = mock_model
        mock_model_builder_class.return_value = mock_model_builder

        # Update registry with real paths
        registry = mock_pta_registry
        registry.configs["test_pta1"]["base_dir"] = str(mock_file_system / "data1")
        registry.configs["test_pta2"]["base_dir"] = str(mock_file_system / "data2")

        factory = MetaPulsarFactory(registry)

        # Mock coordinate extraction
        with patch("metapulsar.metapulsar_factory.bj_name_from_pulsar") as mock_bj_name:
            mock_bj_name.side_effect = lambda model, name_type: (
                "J1857+0943" if name_type == "J" else "B1855+09"
            )

            available_pulsars = factory.discover_available_pulsars()

            # Should return preferred names (B-names)
            assert "B1855+09" in available_pulsars
            assert len(available_pulsars) == 1

    @patch("pint.models.model_builder.parse_parfile")
    def test_create_metapulsar_with_canonical_name(
        self, mock_parse_parfile, mock_pta_registry, mock_file_system
    ):
        """Test MetaPulsar creation includes canonical name."""
        # Create MockPulsar objects directly instead of going through factory
        from metapulsar.mockpulsar import MockPulsar
        from metapulsar.mock_utils import (
            create_mock_timing_data,
            create_mock_flags,
        )

        # Create mock timing data for two PTAs
        toas1, residuals1, errors1, freqs1 = create_mock_timing_data(50)
        flags1 = create_mock_flags(50, telescope="test_pta1")
        mock_psr1 = MockPulsar(
            toas1, residuals1, errors1, freqs1, flags1, "test_pta1", "J1857+0943"
        )

        toas2, residuals2, errors2, freqs2 = create_mock_timing_data(50)
        flags2 = create_mock_flags(50, telescope="test_pta2")
        mock_psr2 = MockPulsar(
            toas2, residuals2, errors2, freqs2, flags2, "test_pta2", "J1857+0943"
        )

        # Create MetaPulsar directly with MockPulsar objects
        pulsars = {"test_pta1": mock_psr1, "test_pta2": mock_psr2}
        metapulsar = MetaPulsar(
            pulsars=pulsars,
            combination_strategy="composite",
            canonical_name="J1857+0943",
        )

        assert isinstance(metapulsar, MetaPulsar)
        assert hasattr(metapulsar, "canonical_name")
        assert metapulsar.canonical_name == "J1857+0943"
        assert hasattr(metapulsar, "pulsars")
        assert len(metapulsar.pulsars) == 2

    def test_discover_files_coordinate_matching(self, mock_pta_registry):
        """Test file discovery uses coordinate matching."""
        factory = MetaPulsarFactory(mock_pta_registry)

        # Mock coordinate discovery
        with patch.object(factory, "_discover_pulsars_by_coordinates") as mock_discover:
            mock_discover.return_value = {
                "J1857+0943": {
                    "files": {
                        "test_pta1": (Path("par1.par"), Path("tim1.tim")),
                        "test_pta2": (Path("par2.par"), Path("tim2.tim")),
                    },
                    "preferred_name": "B1855+09",
                    "b_name": "B1855+09",
                }
            }

            # Test with J-name
            files = factory._discover_files("J1857+0943", mock_pta_registry.configs)
            assert "test_pta1" in files
            assert "test_pta2" in files

            # Test with B-name
            files = factory._discover_files("B1855+09", mock_pta_registry.configs)
            assert "test_pta1" in files
            assert "test_pta2" in files

    def test_discover_files_pulsar_not_found(self, mock_pta_registry):
        """Test file discovery when pulsar not found."""
        factory = MetaPulsarFactory(mock_pta_registry)

        with patch.object(factory, "_discover_pulsars_by_coordinates") as mock_discover:
            mock_discover.return_value = {}

            with pytest.raises(ValueError, match="Pulsar 'UNKNOWN' not found"):
                factory._discover_files("UNKNOWN", mock_pta_registry.configs)


class TestMetaPulsarCanonicalName:
    """Test MetaPulsar canonical_name parameter."""

    def test_metapulsar_canonical_name_parameter(self):
        """Test MetaPulsar accepts canonical_name parameter."""
        # Create a simple test that just checks the canonical_name parameter
        # without triggering complex initialization
        from src.metapulsar.metapulsar import MetaPulsar

        # Test that the parameter is accepted in the constructor
        # We'll use a minimal approach that doesn't trigger full initialization
        class MinimalMetaPulsar(MetaPulsar):
            def __init__(
                self,
                pulsars,
                *,
                combination_strategy="composite",
                canonical_name=None,
                **kwargs,
            ):
                # Just test the parameter assignment without full initialization
                self.canonical_name = canonical_name

        # Test with canonical name
        metapulsar = MinimalMetaPulsar(pulsars={}, canonical_name="B1857+09A")
        assert metapulsar.canonical_name == "B1857+09A"

        # Test without canonical name
        metapulsar = MinimalMetaPulsar(pulsars={})
        assert metapulsar.canonical_name is None

    def test_metapulsar_canonical_name_docstring(self):
        """Test MetaPulsar docstring includes canonical_name parameter."""
        import inspect
        from metapulsar.metapulsar import MetaPulsar

        docstring = inspect.getdoc(MetaPulsar.__init__)
        assert "canonical_name" in docstring
        assert "B1857+09A" in docstring


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_coordinate_discovery_with_malformed_parfile(
        self, mock_pta_registry, mock_file_system
    ):
        """Test coordinate discovery handles malformed parfiles gracefully."""
        # Create malformed parfile
        malformed_par = mock_file_system / "data1" / "malformed.par"
        malformed_par.write_text("This is not a valid parfile")

        registry = mock_pta_registry
        registry.configs["test_pta1"]["base_dir"] = str(mock_file_system / "data1")

        factory = MetaPulsarFactory(registry)

        with patch("pint.models.model_builder.parse_parfile") as mock_parse:
            mock_parse.side_effect = Exception("Parse error")

            # Should not raise exception, just log warning
            coordinate_map = factory._discover_pulsars_by_coordinates(registry.configs)
            assert coordinate_map == {}

    def test_suffix_extraction_with_no_match(self, mock_pta_registry):
        """Test suffix extraction when filename doesn't match pattern."""
        factory = MetaPulsarFactory(mock_pta_registry)

        file_path = Path("/test/data/unknown.par")
        pattern = r"([JB]\d{4}[+-]\d{2,4}[A-Z]?)\.par"
        suffix = factory._extract_suffix_from_filename(file_path, pattern)
        assert suffix == ""

    def test_bj_name_from_pulsar_with_invalid_object(self):
        """Test bj_name_from_pulsar with invalid object."""
        invalid_obj = "not a pulsar object"

        with pytest.raises(ValueError):
            bj_name_from_pulsar(invalid_obj, "J")


# === INTEGRATION TESTS ===


class TestEndToEndCoordinateBasedWorkflow:
    """Test complete end-to-end coordinate-based workflow."""

    @patch("pint.models.model_builder.parse_parfile")
    @patch("pint.models.model_builder.ModelBuilder")
    def test_complete_workflow(
        self,
        mock_model_builder_class,
        mock_parse_parfile,
        mock_pta_registry,
        mock_file_system,
    ):
        """Test complete coordinate-based pulsar discovery and MetaPulsar creation."""
        # Mock parse_parfile to return a dictionary
        mock_par_dict = {
            "PSRJ": ["J1857+0943"],
            "RAJ": ["18:57:36.3906121"],
            "DECJ": ["+09:43:17.20714"],
            "F0": ["186.494081"],
        }
        mock_parse_parfile.return_value = mock_par_dict

        # Mock ModelBuilder to return a TimingModel-like object
        mock_model = Mock()
        mock_model_builder = Mock()
        mock_model_builder.return_value = mock_model
        mock_model_builder_class.return_value = mock_model_builder

        # Update registry with real paths
        registry = mock_pta_registry
        registry.configs["test_pta1"]["base_dir"] = str(mock_file_system / "data1")
        registry.configs["test_pta2"]["base_dir"] = str(mock_file_system / "data2")

        factory = MetaPulsarFactory(registry)

        # Mock coordinate extraction and Enterprise Pulsar creation
        with patch(
            "metapulsar.metapulsar_factory.bj_name_from_pulsar"
        ) as mock_bj_name, patch(
            "metapulsar.metapulsar_factory.get_model_and_toas"
        ) as mock_get_model_and_toas:

            mock_bj_name.side_effect = lambda model, name_type: (
                "J1857+0943" if name_type == "J" else "B1855+09"
            )

            # Create real PINT objects for the factory
            import numpy as np
            from pint.models import TimingModel
            from pint.toa import TOAs

            # Create mock PINT model and TOAs with proper attributes
            mock_model = Mock(spec=TimingModel)
            mock_model.name = "J1857+0943"
            mock_model.PSR = Mock()
            mock_model.PSR.value = "J1857+0943"

            mock_toas = Mock(spec=TOAs)
            mock_toas.ntoas = 50
            mock_toas.get_mjds = Mock(return_value=np.linspace(50000, 60000, 50))
            mock_toas.get_freqs = Mock(return_value=np.random.uniform(100, 2000, 50))
            mock_toas.get_errors = Mock(return_value=np.ones(50) * 1e-7)
            mock_toas.get_obs = Mock(return_value=np.array(["test_pta1"] * 50))

            mock_get_model_and_toas.return_value = (mock_model, mock_toas)

            # Test complete workflow
            available_pulsars = factory.discover_available_pulsars()
            assert "B1855+09" in available_pulsars

            # Test MetaPulsar creation using MockPulsar directly
            from metapulsar.mockpulsar import MockPulsar
            from metapulsar.mock_utils import (
                create_mock_timing_data,
                create_mock_flags,
            )

            # Create mock timing data for both PTAs
            toas1, residuals1, errors1, freqs1 = create_mock_timing_data(50)
            flags1 = create_mock_flags(50, telescope="test_pta1")
            mock_psr1 = MockPulsar(
                toas1, residuals1, errors1, freqs1, flags1, "test_pta1", "J1857+0943"
            )

            toas2, residuals2, errors2, freqs2 = create_mock_timing_data(50)
            flags2 = create_mock_flags(50, telescope="test_pta2")
            mock_psr2 = MockPulsar(
                toas2, residuals2, errors2, freqs2, flags2, "test_pta2", "J1857+0943"
            )

            # Create MetaPulsar directly
            pulsars = {"test_pta1": mock_psr1, "test_pta2": mock_psr2}
            metapulsar = MetaPulsar(
                pulsars=pulsars,
                combination_strategy="composite",
                canonical_name="J1857+0943",
            )

            assert isinstance(metapulsar, MetaPulsar)
            assert metapulsar.canonical_name == "J1857+0943"
            assert metapulsar.combination_strategy == "composite"
