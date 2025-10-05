"""Tests for FileDiscoveryService."""

import pytest
from pathlib import Path
from unittest.mock import patch
from metapulsar.file_discovery_service import FileDiscoveryService, PTA_CONFIGS


class TestFileDiscoveryService:
    """Test FileDiscoveryService functionality."""

    def test_init_default_configs(self):
        """Test initialization with default configurations."""
        service = FileDiscoveryService()
        assert service.pta_configs == PTA_CONFIGS

    def test_init_custom_configs(self):
        """Test initialization with custom configurations."""
        custom_configs = {
            "test_pta": {
                "base_dir": "/test/path",
                "par_pattern": r"test_(\w+)\.par",
                "tim_pattern": r"test_(\w+)\.tim",
                "timing_package": "pint",
                "priority": 1,
            }
        }
        service = FileDiscoveryService(custom_configs)
        assert service.pta_configs == custom_configs

    def test_discover_patterns_in_pta_success(self):
        """Test discovering patterns in a single PTA."""
        service = FileDiscoveryService()

        with patch.object(service, "_discover_patterns_in_config") as mock_discover:
            mock_discover.return_value = ["J1857+0943", "B1855+09"]

            result = service.discover_patterns_in_pta("epta_dr2")

            assert result == ["J1857+0943", "B1855+09"]
            mock_discover.assert_called_once()

    def test_discover_patterns_in_pta_not_found(self):
        """Test discovering patterns with non-existent PTA."""
        service = FileDiscoveryService()

        with pytest.raises(KeyError, match="PTA 'nonexistent' not found"):
            service.discover_patterns_in_pta("nonexistent")

    def test_discover_patterns_in_ptas_success(self):
        """Test discovering patterns in multiple PTAs."""
        service = FileDiscoveryService()

        with patch.object(service, "discover_patterns_in_pta") as mock_discover:
            mock_discover.side_effect = [["J1857+0943"], ["J1857+0943", "B1855+09"]]

            result = service.discover_patterns_in_ptas(["epta_dr2", "ppta_dr2"])

            assert result == {
                "epta_dr2": ["J1857+0943"],
                "ppta_dr2": ["J1857+0943", "B1855+09"],
            }

    def test_discover_all_files_in_ptas_success(self):
        """Test discovering all files in PTAs."""
        service = FileDiscoveryService()

        with patch.object(
            service, "_discover_all_file_pairs_in_config"
        ) as mock_discover:
            mock_discover.return_value = [
                {
                    "par": Path("/test/J1857+0943.par"),
                    "tim": Path("/test/J1857+0943.tim"),
                }
            ]

            result = service.discover_all_files_in_ptas(["epta_dr2"])

            assert "epta_dr2" in result
            assert len(result["epta_dr2"]) == 1
            assert result["epta_dr2"][0]["par"] == Path("/test/J1857+0943.par")
            assert result["epta_dr2"][0]["tim"] == Path("/test/J1857+0943.tim")
            assert result["epta_dr2"][0]["timing_package"] == "tempo2"
            assert result["epta_dr2"][0]["priority"] == 1

    def test_discover_all_files_in_ptas_all_ptas(self):
        """Test discovering files in all PTAs when no specific PTAs provided."""
        service = FileDiscoveryService()

        with patch.object(service, "list_ptas") as mock_list:
            mock_list.return_value = ["epta_dr2", "ppta_dr2"]

            with patch.object(
                service, "_discover_all_file_pairs_in_config"
            ) as mock_discover:
                mock_discover.return_value = []

                result = service.discover_all_files_in_ptas()

                assert "epta_dr2" in result
                assert "ppta_dr2" in result

    def test_list_ptas_sorted_by_priority(self):
        """Test listing PTAs sorted by priority."""
        service = FileDiscoveryService()

        result = service.list_ptas()

        # Should be sorted by priority (descending) then name
        assert isinstance(result, list)
        assert len(result) > 0

    def test_add_pta_success(self):
        """Test adding a new PTA configuration."""
        service = FileDiscoveryService()

        new_config = {
            "base_dir": "/test/path",
            "par_pattern": r"test_(\w+)\.par",
            "tim_pattern": r"test_(\w+)\.tim",
            "timing_package": "pint",
            "priority": 1,
        }

        service.add_pta("test_pta", new_config)

        assert "test_pta" in service.pta_configs
        assert service.pta_configs["test_pta"] == new_config

    def test_add_pta_duplicate(self):
        """Test adding duplicate PTA configuration."""
        service = FileDiscoveryService()

        with pytest.raises(ValueError, match="PTA 'epta_dr2' already exists"):
            service.add_pta("epta_dr2", {})

    def test_add_pta_invalid_config(self):
        """Test adding PTA with invalid configuration."""
        service = FileDiscoveryService()

        invalid_config = {
            "base_dir": "/test/path",
            # Missing required keys
        }

        with pytest.raises(ValueError, match="Missing required keys"):
            service.add_pta("test_pta", invalid_config)

    def test_validate_config_success(self):
        """Test validating valid configuration."""
        service = FileDiscoveryService()

        valid_config = {
            "base_dir": "/test/path",
            "par_pattern": r"test_(\w+)\.par",
            "tim_pattern": r"test_(\w+)\.tim",
            "timing_package": "pint",
            "priority": 1,
        }

        # Should not raise any exception
        service._validate_config(valid_config)

    def test_validate_config_missing_keys(self):
        """Test validating configuration with missing keys."""
        service = FileDiscoveryService()

        invalid_config = {
            "base_dir": "/test/path",
            # Missing par_pattern, tim_pattern, timing_package
        }

        with pytest.raises(ValueError, match="Missing required keys"):
            service._validate_config(invalid_config)

    def test_validate_config_invalid_timing_package(self):
        """Test validating configuration with invalid timing package."""
        service = FileDiscoveryService()

        invalid_config = {
            "base_dir": "/test/path",
            "par_pattern": r"test_(\w+)\.par",
            "tim_pattern": r"test_(\w+)\.tim",
            "timing_package": "invalid",
            "priority": 1,
        }

        with pytest.raises(ValueError, match="Invalid timing_package"):
            service._validate_config(invalid_config)

    def test_validate_config_invalid_regex(self):
        """Test validating configuration with invalid regex patterns."""
        service = FileDiscoveryService()

        invalid_config = {
            "base_dir": "/test/path",
            "par_pattern": r"invalid[regex",  # Invalid regex
            "tim_pattern": r"test_(\w+)\.tim",
            "timing_package": "pint",
            "priority": 1,
        }

        with pytest.raises(ValueError, match="Invalid regex pattern"):
            service._validate_config(invalid_config)

    @patch("pathlib.Path.exists")
    @patch("pathlib.Path.rglob")
    def test_discover_patterns_in_config_success(self, mock_rglob, mock_exists):
        """Test discovering patterns in a configuration."""
        service = FileDiscoveryService()

        mock_exists.return_value = True
        mock_rglob.return_value = [
            Path("/test/J1857+0943.par"),
            Path("/test/B1855+09.par"),
        ]

        config = {"base_dir": "/test", "par_pattern": r"([BJ]\d{4}[+-]\d{2,4})\.par"}

        result = service._discover_patterns_in_config(config)

        assert "J1857+0943" in result
        assert "B1855+09" in result

    @patch("pathlib.Path.exists")
    def test_discover_patterns_in_config_no_base_dir(self, mock_exists):
        """Test discovering patterns when base directory doesn't exist."""
        service = FileDiscoveryService()

        mock_exists.return_value = False

        config = {
            "base_dir": "/nonexistent",
            "par_pattern": r"([BJ]\d{4}[+-]\d{2,4})\.par",
        }

        result = service._discover_patterns_in_config(config)

        assert result == []

    @patch("pathlib.Path.exists")
    @patch("pathlib.Path.rglob")
    def test_discover_all_file_pairs_in_config_success(self, mock_rglob, mock_exists):
        """Test discovering all file pairs in a configuration."""
        service = FileDiscoveryService()

        mock_exists.return_value = True
        mock_rglob.return_value = [
            Path("/test/J1857+0943.par"),
            Path("/test/J1857+0943.tim"),
        ]

        config = {
            "base_dir": "/test",
            "par_pattern": r"([BJ]\d{4}[+-]\d{2,4})\.par",
            "tim_pattern": r"([BJ]\d{4}[+-]\d{2,4})\.tim",
        }

        result = service._discover_all_file_pairs_in_config(config)

        assert len(result) == 1
        assert result[0]["par"] == Path("/test/J1857+0943.par")
        assert result[0]["tim"] == Path("/test/J1857+0943.tim")

    @patch("pathlib.Path.exists")
    def test_discover_all_file_pairs_in_config_no_base_dir(self, mock_exists):
        """Test discovering file pairs when base directory doesn't exist."""
        service = FileDiscoveryService()

        mock_exists.return_value = False

        config = {
            "base_dir": "/nonexistent",
            "par_pattern": r"([BJ]\d{4}[+-]\d{2,4})\.par",
            "tim_pattern": r"([BJ]\d{4}[+-]\d{2,4})\.tim",
        }

        result = service._discover_all_file_pairs_in_config(config)

        assert result == []
