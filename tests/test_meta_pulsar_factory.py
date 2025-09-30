"""Tests for Meta-Pulsar Factory."""

import pytest
from unittest.mock import Mock, patch
from pathlib import Path
from ipta_metapulsar.meta_pulsar_factory import MetaPulsarFactory
from ipta_metapulsar.pta_registry import PTARegistry


class TestMetaPulsarFactory:
    """Test MetaPulsarFactory class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.registry = PTARegistry()
        self.factory = MetaPulsarFactory(self.registry)

    def test_initialization(self):
        """Test factory initialization."""
        factory = MetaPulsarFactory()
        assert factory.registry is not None
        assert len(factory.registry.configs) > 0

    def test_initialization_with_custom_registry(self):
        """Test factory initialization with custom registry."""
        custom_registry = PTARegistry()
        factory = MetaPulsarFactory(custom_registry)
        assert factory.registry is custom_registry

    @patch("ipta_metapulsar.meta_pulsar_factory.PintPulsar")
    @patch("ipta_metapulsar.meta_pulsar_factory.get_model_and_toas")
    @patch("ipta_metapulsar.meta_pulsar_factory.j_name_from_pulsar")
    def test_create_metapulsar_success(
        self, mock_j_name, mock_get_model, mock_pint_pulsar
    ):
        """Test successful MetaPulsar creation."""
        # Mock dependencies
        mock_j_name.return_value = "J1857+0943"
        mock_model = Mock()
        mock_toas = Mock()
        mock_get_model.return_value = (mock_model, mock_toas)
        mock_enterprise_psr = Mock()
        mock_pint_pulsar.return_value = mock_enterprise_psr

        # Create a test PTA config
        test_config = {
            "base_dir": "/data/test",
            "par_pattern": r"([BJ]\d{4}[+-]\d{2,4})\.par",
            "tim_pattern": r"([BJ]\d{4}[+-]\d{2,4})\.tim",
            "timing_package": "pint",
            "priority": 1,
            "description": "Test PTA",
        }
        self.registry.add_pta("test_pta", test_config)

        # Mock file discovery
        with patch.object(self.factory, "_discover_files") as mock_discover:
            mock_discover.return_value = {
                "test_pta": (
                    Path("/data/test/J1857+0943.par"),
                    Path("/data/test/J1857+0943.tim"),
                )
            }

            # Create MetaPulsar
            metapulsar = self.factory.create_metapulsar("J1857+0943", ["test_pta"])

            assert metapulsar is not None
            # The legacy create_metapulsar is a placeholder, so we just check it was created
            assert hasattr(metapulsar, "pulsars")

    def test_create_metapulsar_no_files_found(self):
        """Test MetaPulsar creation when no files are found."""
        with patch.object(self.factory, "_discover_files") as mock_discover:
            mock_discover.return_value = {}

            with pytest.raises(
                ValueError, match=r"No files found for pulsar J1857\+0943"
            ):
                self.factory.create_metapulsar("J1857+0943")

    @patch("ipta_metapulsar.meta_pulsar_factory.PintPulsar")
    @patch("ipta_metapulsar.meta_pulsar_factory.get_model_and_toas")
    def test_create_metapulsar_enterprise_creation_fails(
        self, mock_get_model, mock_pint_pulsar
    ):
        """Test MetaPulsar creation when Enterprise Pulsar creation fails."""
        # Mock dependencies to raise exception
        mock_get_model.side_effect = Exception("PINT error")

        # Create a test PTA config
        test_config = {
            "base_dir": "/data/test",
            "par_pattern": r"([BJ]\d{4}[+-]\d{2,4})\.par",
            "tim_pattern": r"([BJ]\d{4}[+-]\d{2,4})\.tim",
            "timing_package": "pint",
            "priority": 1,
            "description": "Test PTA",
        }
        self.registry.add_pta("test_pta", test_config)

        # Mock file discovery
        with patch.object(self.factory, "_discover_files") as mock_discover:
            mock_discover.return_value = {
                "test_pta": (
                    Path("/data/test/J1857+0943.par"),
                    Path("/data/test/J1857+0943.tim"),
                )
            }

            with pytest.raises(
                RuntimeError, match="Failed to create Enterprise Pulsar for test_pta"
            ):
                self.factory.create_metapulsar("J1857+0943", ["test_pta"])

    @patch("ipta_metapulsar.meta_pulsar_factory.PintPulsar")
    @patch("ipta_metapulsar.meta_pulsar_factory.get_model_and_toas")
    @patch("ipta_metapulsar.meta_pulsar_factory.j_name_from_pulsar")
    def test_create_all_metapulsars(
        self, mock_j_name, mock_get_model, mock_pint_pulsar
    ):
        """Test creating all MetaPulsars."""
        # Mock dependencies
        mock_j_name.return_value = "J1857+0943"
        mock_model = Mock()
        mock_toas = Mock()
        mock_get_model.return_value = (mock_model, mock_toas)
        mock_enterprise_psr = Mock()
        mock_pint_pulsar.return_value = mock_enterprise_psr

        # Create a test PTA config
        test_config = {
            "base_dir": "/data/test",
            "par_pattern": r"([BJ]\d{4}[+-]\d{2,4})\.par",
            "tim_pattern": r"([BJ]\d{4}[+-]\d{2,4})\.tim",
            "timing_package": "pint",
            "priority": 1,
            "description": "Test PTA",
        }
        self.registry.add_pta("test_pta", test_config)

        # Mock file discovery and pulsar discovery
        with patch.object(
            self.factory, "_discover_files"
        ) as mock_discover, patch.object(
            self.factory, "_discover_pulsars_in_pta"
        ) as mock_discover_psrs:

            mock_discover.return_value = {
                "test_pta": (
                    Path("/data/test/J1857+0943.par"),
                    Path("/data/test/J1857+0943.tim"),
                )
            }
            mock_discover_psrs.return_value = ["J1857+0943"]

            # Create all MetaPulsars
            metapulsars = self.factory.create_all_metapulsars(["test_pta"])

            assert len(metapulsars) == 1
            assert "J1857+0943" in metapulsars
            assert metapulsars["J1857+0943"] is not None

    def test_discover_available_pulsars(self):
        """Test discovering available pulsars."""
        # Create a test PTA config
        test_config = {
            "base_dir": "/data/test",
            "par_pattern": r"([BJ]\d{4}[+-]\d{2,4})\.par",
            "tim_pattern": r"([BJ]\d{4}[+-]\d{2,4})\.tim",
            "timing_package": "pint",
            "priority": 1,
            "description": "Test PTA",
        }
        self.registry.add_pta("test_pta", test_config)

        # Mock pulsar discovery
        with patch.object(self.factory, "_discover_pulsars_in_pta") as mock_discover:
            mock_discover.return_value = ["J1857+0943", "J1939+2134"]

            pulsars = self.factory.discover_available_pulsars(["test_pta"])

            assert len(pulsars) == 2
            assert "J1857+0943" in pulsars
            assert "J1939+2134" in pulsars

    def test_discover_files(self):
        """Test file discovery."""
        # Create a test PTA config
        test_config = {
            "base_dir": "/data/test",
            "par_pattern": r"([BJ]\d{4}[+-]\d{2,4})\.par",
            "tim_pattern": r"([BJ]\d{4}[+-]\d{2,4})\.tim",
            "timing_package": "pint",
            "priority": 1,
            "description": "Test PTA",
        }

        # Mock file finding
        with patch.object(self.factory, "_find_file") as mock_find:
            mock_find.side_effect = [
                Path("/data/test/J1857+0943.par"),  # par file
                Path("/data/test/J1857+0943.tim"),  # tim file
            ]

            file_pairs = self.factory._discover_files(
                "J1857+0943", {"test_pta": test_config}
            )

            assert len(file_pairs) == 1
            assert "test_pta" in file_pairs
            assert file_pairs["test_pta"] == (
                Path("/data/test/J1857+0943.par"),
                Path("/data/test/J1857+0943.tim"),
            )

    def test_find_file_success(self):
        """Test successful file finding."""
        with patch("pathlib.Path.exists") as mock_exists, patch(
            "pathlib.Path.rglob"
        ) as mock_rglob:

            mock_exists.return_value = True
            mock_file = Mock()
            mock_file.is_file.return_value = True
            mock_file.__str__ = Mock(return_value="/data/test/J1857+0943.par")
            mock_rglob.return_value = [mock_file]

            # Mock regex matching
            with patch("re.compile") as mock_compile:
                mock_regex = Mock()
                mock_regex.search.return_value = Mock(
                    group=lambda x: "J1857+0943" if x == 1 else None
                )
                mock_compile.return_value = mock_regex

                result = self.factory._find_file(
                    "J1857+0943", "/data/test", r"([BJ]\d{4}[+-]\d{2,4})\.par"
                )

                assert result == mock_file

    def test_find_file_not_found(self):
        """Test file finding when file doesn't exist."""
        with patch("pathlib.Path.exists") as mock_exists:
            mock_exists.return_value = False

            result = self.factory._find_file(
                "J1857+0943", "/data/test", r"([BJ]\d{4}[+-]\d{2,4})\.par"
            )

            assert result is None

    def test_discover_pulsars_in_pta(self):
        """Test discovering pulsars in a single PTA."""
        test_config = {
            "base_dir": "/data/test",
            "par_pattern": r"([BJ]\d{4}[+-]\d{2,4})\.par",
            "tim_pattern": r"([BJ]\d{4}[+-]\d{2,4})\.tim",
            "timing_package": "pint",
            "priority": 1,
            "description": "Test PTA",
        }

        with patch("pathlib.Path.exists") as mock_exists, patch(
            "pathlib.Path.rglob"
        ) as mock_rglob:

            mock_exists.return_value = True
            mock_file1 = Mock()
            mock_file1.is_file.return_value = True
            mock_file1.__str__ = Mock(return_value="/data/test/J1857+0943.par")
            mock_file2 = Mock()
            mock_file2.is_file.return_value = True
            mock_file2.__str__ = Mock(return_value="/data/test/J1939+2134.par")
            mock_rglob.return_value = [mock_file1, mock_file2]

            # Mock regex matching
            with patch("re.compile") as mock_compile:
                mock_regex = Mock()
                mock_regex.search.side_effect = [
                    Mock(group=lambda x: "J1857+0943" if x == 1 else None),
                    Mock(group=lambda x: "J1939+2134" if x == 1 else None),
                ]
                mock_compile.return_value = mock_regex

                pulsars = self.factory._discover_pulsars_in_pta(test_config)

                assert len(pulsars) == 2
                assert "J1857+0943" in pulsars
                assert "J1939+2134" in pulsars

    def test_build_metadata(self):
        """Test metadata building."""
        file_pairs = {
            "epta_dr2": (Path("/data/epta.par"), Path("/data/epta.tim")),
            "ppta_dr3": (Path("/data/ppta.par"), Path("/data/ppta.tim")),
        }

        pta_configs = {
            "epta_dr2": {
                "base_dir": "/data/epta",
                "par_pattern": r"([BJ]\d{4}[+-]\d{2,4})\.par",
                "tim_pattern": r"([BJ]\d{4}[+-]\d{2,4})\.tim",
                "timing_package": "tempo2",
                "priority": 1,
                "description": "EPTA DR2",
            },
            "ppta_dr3": {
                "base_dir": "/data/ppta",
                "par_pattern": r"([BJ]\d{4}[+-]\d{2,4})\.par",
                "tim_pattern": r"([BJ]\d{4}[+-]\d{2,4})\.tim",
                "timing_package": "tempo2",
                "priority": 2,
                "description": "PPTA DR3",
            },
        }

        metadata = self.factory._build_metadata(file_pairs, pta_configs)

        assert "file_pairs" in metadata
        assert "timing_packages" in metadata
        assert "creation_timestamp" in metadata
        assert metadata["timing_packages"]["epta_dr2"] == "tempo2"
        assert metadata["timing_packages"]["ppta_dr3"] == "tempo2"
