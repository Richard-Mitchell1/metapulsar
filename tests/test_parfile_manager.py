"""Tests for ParFileManager functionality."""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch
import tempfile
import numpy as np

from ipta_metapulsar.parfile_manager import ParFileManager
from ipta_metapulsar.pta_registry import PTARegistry


class TestParFileManager:
    """Test cases for ParFileManager class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.registry = PTARegistry()
        self.manager = ParFileManager(self.registry)

    def test_init(self):
        """Test ParFileManager initialization."""
        # Test with custom registry
        custom_registry = PTARegistry()
        manager = ParFileManager(custom_registry)
        assert manager.registry is custom_registry

        # Test with default registry
        manager = ParFileManager()
        assert isinstance(manager.registry, PTARegistry)

    def test_get_output_filename(self):
        """Test output filename generation."""
        filename = self.manager._get_output_filename("J1909-3744", "epta_dr2")
        assert filename == "J1909-3744_epta_dr2.par"

    @patch("ipta_metapulsar.parfile_manager.TOAs")
    def test_calculate_dataset_timespan(self, mock_toas):
        """Test dataset timespan calculation."""
        # Mock TOAs object
        mock_toa_instance = Mock()
        mock_toa_instance.get_mjds.return_value.value = np.array(
            [50000.0, 55000.0, 60000.0]
        )
        mock_toas.return_value = mock_toa_instance

        # Mock registry and file discovery
        with patch.object(self.manager, "_find_file") as mock_find_file:
            mock_find_file.return_value = Path("/fake/tim/file.tim")

            timespan = self.manager._calculate_dataset_timespan(
                "epta_dr2", "J1909-3744"
            )

            assert timespan == 10000.0  # 60000.0 - 50000.0
            mock_toas.assert_called_once()

    @patch("ipta_metapulsar.parfile_manager.TOAs")
    def test_calculate_dataset_timespan_no_tim_file(self, mock_toas):
        """Test dataset timespan calculation when TIM file is not found."""
        with patch.object(self.manager, "_find_file") as mock_find_file:
            mock_find_file.return_value = None

            with pytest.raises(FileNotFoundError):
                self.manager._calculate_dataset_timespan("epta_dr2", "J1909-3744")

    @patch("ipta_metapulsar.parfile_manager.TOAs")
    def test_calculate_dataset_timespan_no_toas(self, mock_toas):
        """Test dataset timespan calculation when no TOAs are found."""
        # Mock TOAs object with empty array
        mock_toa_instance = Mock()
        mock_toa_instance.get_mjds.return_value.value = np.array([])
        mock_toas.return_value = mock_toa_instance

        with patch.object(self.manager, "_find_file") as mock_find_file:
            mock_find_file.return_value = Path("/fake/tim/file.tim")

            with pytest.raises(ValueError, match="No TOAs found"):
                self.manager._calculate_dataset_timespan("epta_dr2", "J1909-3744")

    def test_select_reference_pta(self):
        """Test reference PTA selection based on timespan."""
        parfile_paths = {
            "epta_dr2": Path("/fake/epta.par"),
            "ppta_dr2": Path("/fake/ppta.par"),
            "nanograv_15y": Path("/fake/nanograv.par"),
        }

        with patch.object(self.manager, "_calculate_dataset_timespan") as mock_calc:
            # Mock different timespans for each PTA
            mock_calc.side_effect = lambda pta, pulsar: {
                "epta_dr2": 1000.0,
                "ppta_dr2": 2000.0,  # Longest
                "nanograv_15y": 1500.0,
            }[pta]

            reference_pta = self.manager._select_reference_pta(parfile_paths)
            assert reference_pta == "ppta_dr2"

    def test_select_reference_pta_error_handling(self):
        """Test reference PTA selection with errors."""
        parfile_paths = {
            "epta_dr2": Path("/fake/epta.par"),
            "ppta_dr2": Path("/fake/ppta.par"),
        }

        with patch.object(self.manager, "_calculate_dataset_timespan") as mock_calc:
            # Mock errors for all PTAs
            mock_calc.side_effect = Exception("Test error")

            # The method should still return a PTA (the first one) with 0.0 timespan
            reference_pta = self.manager._select_reference_pta(parfile_paths)
            assert reference_pta in parfile_paths

    def test_convert_pint_to_tdb(self):
        """Test PINT-based unit conversion."""
        # Mock par file content
        parfile_content = "F0 123.456 1\nUNITS TCB\n"

        with patch("ipta_metapulsar.parfile_manager.ModelBuilder") as mock_builder:
            # Mock ModelBuilder and model
            mock_model = Mock()
            mock_model.write_parfile.return_value = None
            mock_builder.return_value.return_value = mock_model

            # Mock StringIO
            with patch("ipta_metapulsar.parfile_manager.StringIO") as mock_stringio:
                mock_output = Mock()
                mock_output.getvalue.return_value = "F0 123.456 1\nUNITS TDB\n"
                mock_stringio.return_value = mock_output

                result = self.manager._convert_pint_to_tdb(parfile_content)
                assert "TDB" in result

    def test_convert_tempo2_to_tdb(self):
        """Test tempo2-based unit conversion."""
        parfile_content = "F0 123.456 1\nUNITS TCB\n"

        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0

            with patch("tempfile.NamedTemporaryFile") as mock_temp_class:
                # Create mock context managers
                mock_input = Mock()
                mock_input.name = "/tmp/input.par"
                mock_input.write = Mock()
                mock_input.flush = Mock()
                mock_input.close = Mock()
                mock_input.__enter__ = Mock(return_value=mock_input)
                mock_input.__exit__ = Mock(return_value=None)

                mock_output = Mock()
                mock_output.name = "/tmp/output.par"
                mock_output.seek = Mock()
                mock_output.read.return_value = "F0 123.456 1\nUNITS TDB\n"
                mock_output.close = Mock()
                mock_output.__enter__ = Mock(return_value=mock_output)
                mock_output.__exit__ = Mock(return_value=None)

                mock_temp_class.side_effect = [mock_input, mock_output]

                with patch("pathlib.Path.unlink"):
                    result = self.manager._convert_tempo2_to_tdb(parfile_content)
                    assert "TDB" in result
                    mock_run.assert_called_once()

    def test_write_consistent_parfiles(self):
        """Test writing consistent par files to output directory."""
        consistent_parfiles = {
            "epta_dr2": "F0 123.456 1\nUNITS TDB\n",
            "ppta_dr2": "F0 123.456 1\nUNITS TDB\n",
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            output_files = self.manager._write_consistent_parfiles(
                consistent_parfiles, "J1909-3744", Path(temp_dir)
            )

            assert len(output_files) == 2
            assert "epta_dr2" in output_files
            assert "ppta_dr2" in output_files

            # Check that files were actually written
            for pta_name, file_path in output_files.items():
                assert file_path.exists()
                assert file_path.name == f"J1909-3744_{pta_name}.par"

    def test_write_consistent_parfiles_temp_dir(self):
        """Test writing consistent par files with temporary directory."""
        consistent_parfiles = {"epta_dr2": "F0 123.456 1\nUNITS TDB\n"}

        output_files = self.manager._write_consistent_parfiles(
            consistent_parfiles, "J1909-3744", None
        )

        assert len(output_files) == 1
        assert "epta_dr2" in output_files
        assert output_files["epta_dr2"].exists()
        assert output_files["epta_dr2"].name == "J1909-3744_epta_dr2.par"


if __name__ == "__main__":
    pytest.main([__file__])
