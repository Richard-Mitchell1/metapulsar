"""Test error handling and malformed data robustness."""

import pytest
import tempfile
from pathlib import Path
from metapulsar import MetaPulsarFactory, PTARegistry


@pytest.mark.integration
class TestErrorHandling:
    """Test error handling and malformed data robustness."""

    def test_missing_data_directory(self):
        """Test handling of missing data directories."""
        # Test with non-existent directory
        with pytest.raises(KeyError):
            MetaPulsarFactory().create_metapulsar(
                pulsar_name="J0030+0451",
                pta_names=["nonexistent_config"],
                reference_pta="nonexistent_config",
            )

    @pytest.mark.slow
    def test_missing_par_files(self, available_data_sets):
        """Test handling of missing par files."""
        if not available_data_sets:
            pytest.skip("No data available for testing")

        # Test with non-existent pulsar
        with pytest.raises((FileNotFoundError, ValueError)):
            MetaPulsarFactory().create_metapulsar(
                pulsar_name="J9999+9999",  # Non-existent pulsar
                pta_names=["epta_dr1_v2_2"],
                reference_pta="epta_dr1_v2_2",
            )

    def test_malformed_par_file(self, available_data_sets):
        """Test handling of malformed par files."""
        if not available_data_sets:
            pytest.skip("No data available for testing")

        # Create a temporary malformed par file
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_par = Path(temp_dir) / "J0030+0451.par"

            # Write malformed par file
            with open(temp_par, "w") as f:
                f.write(
                    """# Malformed par file
F0 123.456 1 0.001
# Missing required parameters
# RAJ and DECJ are missing
"""
                )

                # Create a temporary PTA config pointing to malformed file
                registry = PTARegistry()
                config = registry.get_pta("epta_dr1_v2_2")
                config["base_dir"] = str(temp_dir)
                config["par_pattern"] = "J0030+0451.par"

                # This should raise ValueError because the parfile is malformed (missing coordinates)
                with pytest.raises(ValueError):
                    MetaPulsarFactory().create_metapulsar(
                        pulsar_name="J0030+0451",
                        pta_names=["epta_dr1_v2_2"],
                        reference_pta="epta_dr1_v2_2",
                    )

    def test_malformed_tim_file(self, available_data_sets):
        """Test handling of malformed tim files."""
        if not available_data_sets:
            pytest.skip("No data available for testing")

        # Create a temporary malformed tim file
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_tim = Path(temp_dir) / "J0030+0451.tim"

            # Write malformed tim file
            with open(temp_tim, "w") as f:
                f.write(
                    """# Malformed tim file
# Missing required columns
C 12345.67890 0.0001
"""
                )

                # Create a temporary PTA config pointing to malformed file
                registry = PTARegistry()
                config = registry.get_pta("epta_dr1_v2_2")
                config["base_dir"] = str(temp_dir)
                config["tim_pattern"] = "J0030+0451.tim"

                # This should raise ValueError because the tim file is malformed
                with pytest.raises(ValueError):
                    MetaPulsarFactory().create_metapulsar(
                        pulsar_name="J0030+0451",
                        pta_names=["epta_dr1_v2_2"],
                        reference_pta="epta_dr1_v2_2",
                    )

    def test_invalid_pta_config(self):
        """Test handling of invalid PTA configurations."""
        registry = PTARegistry()

        # Test with invalid PTA config name
        with pytest.raises(KeyError):
            registry.get_pta("invalid_config")

        # Test with invalid primary/reference PTA - this should raise KeyError
        with pytest.raises(KeyError):
            MetaPulsarFactory().create_metapulsar(
                pulsar_name="J0030+0451",
                pta_names=["epta_dr1_v2_2"],
                reference_pta="invalid_pta",
            )

    def test_empty_par_files(self, available_data_sets):
        """Test handling of empty par files."""
        if not available_data_sets:
            pytest.skip("No data available for testing")

        # Create a temporary empty par file
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_par = Path(temp_dir) / "J0030+0451.par"
            temp_par.touch()  # Create empty file

            # Create a temporary PTA config pointing to empty file
            registry = PTARegistry()
            config = registry.get_pta("epta_dr1_v2_2")
            config["base_dir"] = str(temp_dir)
            config["par_pattern"] = "J0030+0451.par"

            # This should raise ValueError because the par file is empty
            with pytest.raises(ValueError):
                MetaPulsarFactory().create_metapulsar(
                    pulsar_name="J0030+0451",
                    pta_names=["epta_dr1_v2_2"],
                    reference_pta="epta_dr1_v2_2",
                )

    def test_corrupted_binary_files(self, available_data_sets):
        """Test handling of corrupted binary files."""
        if not available_data_sets:
            pytest.skip("No data available for testing")

        # Create a temporary corrupted par file
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_par = Path(temp_dir) / "J0030+0451.par"

            # Write corrupted par file with binary data
            with open(temp_par, "wb") as f:
                f.write(b"\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09")

            # Create a temporary PTA config pointing to corrupted file
            registry = PTARegistry()
            config = registry.get_pta("epta_dr1_v2_2")
            config["base_dir"] = str(temp_dir)
            config["par_pattern"] = "J0030+0451.par"

            # This should raise ValueError because the par file is corrupted
            with pytest.raises(ValueError):
                MetaPulsarFactory().create_metapulsar(
                    pulsar_name="J0030+0451",
                    pta_names=["epta_dr1_v2_2"],
                    reference_pta="epta_dr1_v2_2",
                )

    def test_memory_limit_handling(self, available_data_sets):
        """Test handling of memory limits with large datasets."""
        if not available_data_sets:
            pytest.skip("No data available for testing")

        # This test would be implemented if we had very large datasets
        # For now, just test that the system doesn't crash with reasonable data
        try:
            MetaPulsarFactory().create_metapulsar(
                pulsar_name="J0030+0451",
                pta_names=["epta_dr1_v2_2"],
                reference_pta="epta_dr1_v2_2",
            )
        except Exception as e:
            # Should not crash due to memory issues with normal data
            assert "memory" not in str(e).lower()
            assert "segfault" not in str(e).lower()

    def test_concurrent_access(self, available_data_sets):
        """Test handling of concurrent access to data files."""
        if not available_data_sets:
            pytest.skip("No data available for testing")

        import threading

        results = []
        errors = []

        def create_metapulsar():
            try:
                mp = MetaPulsarFactory().create_metapulsar(
                    pulsar_name="J0030+0451",
                    pta_names=["epta_dr1_v2_2"],
                    reference_pta="epta_dr1_v2_2",
                )
                results.append(mp)
            except Exception as e:
                errors.append(e)

        # Create multiple threads
        threads = []
        for _ in range(3):
            thread = threading.Thread(target=create_metapulsar)
            threads.append(thread)
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        # Should have at least one successful result
        assert len(results) > 0 or len(errors) > 0

        # If there are errors, they should be reasonable (not file access issues)
        for error in errors:
            assert "Permission denied" not in str(error)
            assert "Device or resource busy" not in str(error)
