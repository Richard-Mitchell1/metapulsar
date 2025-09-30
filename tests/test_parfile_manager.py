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

    def test_convert_units_mixed_units(self):
        """Test unit conversion when units are mixed."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create test par files with mixed units
            tdb_file = Path(temp_dir) / "tdb.par"
            tcb_file = Path(temp_dir) / "tcb.par"

            tdb_file.write_text("F0 123.456 1\nUNITS TDB\n")
            tcb_file.write_text("F0 123.456 1\nUNITS TCB\n")

            parfile_paths = {"epta_dr2": tdb_file, "ppta_dr2": tcb_file}

            with patch.object(self.manager, "_convert_tempo2_to_tdb") as mock_convert:
                mock_convert.return_value = "F0 123.456 1\nUNITS TDB\n"

                result = self.manager._convert_units_if_needed(parfile_paths)

                # Should have converted the TCB file
                assert len(result) == 2
                assert "epta_dr2" in result
                assert "ppta_dr2" in result
                mock_convert.assert_called_once()

    def test_convert_units_same_units(self):
        """Test unit conversion when all units are the same."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create test par files with same units
            tdb_file1 = Path(temp_dir) / "tdb1.par"
            tdb_file2 = Path(temp_dir) / "tdb2.par"

            tdb_file1.write_text("F0 123.456 1\nUNITS TDB\n")
            tdb_file2.write_text("F0 123.456 1\nUNITS TDB\n")

            parfile_paths = {"epta_dr2": tdb_file1, "ppta_dr2": tdb_file2}

            result = self.manager._convert_units_if_needed(parfile_paths)

            # Should return original content without conversion
            assert len(result) == 2
            assert "epta_dr2" in result
            assert "ppta_dr2" in result
            assert "UNITS TDB" in result["epta_dr2"]
            assert "UNITS TDB" in result["ppta_dr2"]

    def test_make_parameters_consistent_spin(self):
        """Test making spin parameters consistent."""
        parfile_data = {
            "epta_dr2": "F0 123.456 1\nF1 -1.23e-15 1\nPEPOCH 55000.0\n",
            "ppta_dr2": "F0 124.000 1\nF1 -1.50e-15 1\nPEPOCH 55000.0\n",
        }

        result = self.manager._make_parameters_consistent(
            parfile_data, "epta_dr2", ["spin"], False
        )

        # Both should have the same F0 and F1 values from reference PTA
        # PINT as_parfile() format: "F0                                123.456 1 0.0"
        assert "F0                                123.456 1" in result["epta_dr2"]
        assert "F1                              -1.23e-15 1" in result["epta_dr2"]
        assert "F0                                123.456 1" in result["ppta_dr2"]
        assert "F1                              -1.23e-15 1" in result["ppta_dr2"]

    def test_make_parameters_consistent_dm_with_derivatives(self):
        """Test making DM parameters consistent with derivatives."""
        parfile_data = {
            "epta_dr2": "DM 10.5 1\nDMEPOCH 55000.0\nDM1 0.1 1\nDM2 0.01 1\n",
            "ppta_dr2": "DM 11.0 1\nDMEPOCH 55000.0\nDMX_001 0.1 1\n",
        }

        result = self.manager._make_parameters_consistent(
            parfile_data, "epta_dr2", ["dispersion"], True
        )

        # Both should have the same DM values from reference PTA
        # Custom format: "DM    10.5 1"
        assert "DM    10.5 1" in result["epta_dr2"]
        assert "DM    10.5 1" in result["ppta_dr2"]
        assert "DM1    0.1 1" in result["epta_dr2"]
        assert "DM1    0.1 1" in result["ppta_dr2"]
        assert "DM2    0.01 1" in result["epta_dr2"]
        assert "DM2    0.01 1" in result["ppta_dr2"]

        # DMX parameters should be removed from non-reference PTA
        assert "DMX_001" not in result["ppta_dr2"]

    def test_make_parameters_consistent_dm_without_derivatives(self):
        """Test making DM parameters consistent without adding derivatives."""
        parfile_data = {
            "epta_dr2": "DM 10.5 1\nDMEPOCH 55000.0\nDM1 0.1 1\n",
            "ppta_dr2": "DM 11.0 1\nDMEPOCH 55000.0\nDM1 0.2 1\n",
        }

        result = self.manager._make_parameters_consistent(
            parfile_data, "epta_dr2", ["dispersion"], False
        )

        # Both should have the same DM values from reference PTA
        assert "DM    10.5 1" in result["epta_dr2"]
        assert "DM    10.5 1" in result["ppta_dr2"]
        assert "DM1    0.1 1" in result["epta_dr2"]
        assert "DM1    0.1 1" in result["ppta_dr2"]  # Aligned to reference

    def test_make_parameters_consistent_astrometry(self):
        """Test making astrometry parameters consistent."""
        parfile_data = {
            "epta_dr2": "RAJ 12:34:56.789\nDECJ 12:34:56.789\nPMRA 10.5 1\n",
            "ppta_dr2": "RAJ 12:35:00.000\nDECJ 12:35:00.000\nPMRA 11.0 1\n",
        }

        result = self.manager._make_parameters_consistent(
            parfile_data, "epta_dr2", ["astrometry"], False
        )

        # Both should have the same astrometry values from reference PTA
        assert "RAJ    12:34:56.789" in result["epta_dr2"]
        assert "RAJ    12:34:56.789" in result["ppta_dr2"]
        assert "DECJ    12:34:56.789" in result["epta_dr2"]
        assert "DECJ    12:34:56.789" in result["ppta_dr2"]
        assert "PMRA    10.5 1" in result["epta_dr2"]
        assert "PMRA    10.5 1" in result["ppta_dr2"]

    def test_make_parameters_consistent_dm_derivatives_warning(self):
        """Test warning when add_dm_derivatives=True but dispersion not in combine_components."""
        parfile_data = {"epta_dr2": "F0 123.456 1\n", "ppta_dr2": "F0 124.000 1\n"}

        with patch("loguru.logger.warning") as mock_warning:
            self.manager._make_parameters_consistent(
                parfile_data,
                "epta_dr2",
                ["spin"],
                True,  # add_dm_derivatives=True but no 'dispersion'
            )

            # Should issue warning about DM derivatives
            warning_calls = [
                call
                for call in mock_warning.call_args_list
                if "add_dm_derivatives=True but 'dispersion' not in combine_components"
                in str(call)
            ]
            assert len(warning_calls) == 1

    def test_get_component_parameters(self):
        """Test getting component parameters."""
        spin_params = self.manager._get_component_parameters("spin")
        assert "F0" in spin_params
        assert "F1" in spin_params
        assert "PEPOCH" in spin_params

        astrometry_params = self.manager._get_component_parameters("astrometry")
        assert "RAJ" in astrometry_params
        assert "DECJ" in astrometry_params
        assert "PMRA" in astrometry_params

        binary_params = self.manager._get_component_parameters("binary")
        assert "PB" in binary_params
        assert "A1" in binary_params
        assert "ECC" in binary_params

        # Test unknown component
        unknown_params = self.manager._get_component_parameters("unknown")
        assert unknown_params == []

    def test_dict_to_parfile_string(self):
        """Test converting par file dictionary back to string."""
        parfile_dict = {
            "F0": [["123.456", "1"]],
            "F1": [["-1.23e-15", "1"]],
            "PEPOCH": [["55000.0", "1"]],
        }

        result = self.manager._dict_to_parfile_string(parfile_dict)

        # PINT as_parfile() format: "F0                                123.456 1 0.0"
        assert "F0                                123.456 1" in result
        assert "F1                              -1.23e-15 1" in result
        assert "PEPOCH             55000.0000000000000000" in result


if __name__ == "__main__":
    pytest.main([__file__])
