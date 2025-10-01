"""Test data discovery and availability."""

import pytest
from pathlib import Path
from metapulsar import PTARegistry


@pytest.mark.integration
class TestDataDiscovery:
    """Test data discovery functionality."""

    def test_pta_registry_loading(self):
        """Test that PTA registry loads correctly."""
        registry = PTARegistry()
        configs = registry.list_ptas()

        # Should have both DR2 and DR3 configurations
        assert len(configs) > 0
        assert "epta_dr1_v2_2" in configs
        assert "ppta_dr2" in configs
        assert "nanograv_9y" in configs
        assert "epta_dr2" in configs
        assert "inpta_dr1" in configs
        assert "mpta_dr1" in configs
        assert "nanograv_12y" in configs
        assert "nanograv_15y" in configs

    def test_pta_config_structure(self):
        """Test that PTA configurations have required fields."""
        registry = PTARegistry()

        for config_name in registry.list_ptas():
            config = registry.get_pta(config_name)

            # Check required fields
            assert "base_dir" in config
            assert "par_pattern" in config
            assert "tim_pattern" in config
            assert "timing_package" in config
            assert "priority" in config
            assert "description" in config

            # Check data types
            assert isinstance(config["base_dir"], str)
            assert isinstance(config["par_pattern"], str)
            assert isinstance(config["tim_pattern"], str)
            assert config["timing_package"] in ["pint", "tempo2"]
            assert isinstance(config["priority"], int)
            assert isinstance(config["description"], str)

    def test_data_directory_structure(self, available_data_sets):
        """Test that data directories exist and have expected structure."""
        if "dr2" in available_data_sets:
            dr2_data = available_data_sets["dr2"]

            # Check EPTA DR1 v2.2
            if dr2_data["epta"].exists():
                assert (dr2_data["epta"] / "J0030+0451").exists()
                assert (dr2_data["epta"] / "J0613-0200").exists()

            # Check PPTA DR2
            if dr2_data["ppta"].exists():
                assert (dr2_data["ppta"] / "par").exists()
                assert (dr2_data["ppta"] / "tim").exists()

            # Check NANOGrav 9y
            if dr2_data["nanograv"].exists():
                assert (dr2_data["nanograv"] / "par").exists()
                assert (dr2_data["nanograv"] / "tim").exists()

        if "dr3" in available_data_sets:
            dr3_data = available_data_sets["dr3"]

            # Check EPTA DR2
            if dr3_data["epta"].exists():
                assert (dr3_data["epta"] / "J0030+0451").exists()
                assert (dr3_data["epta"] / "J0437-4715").exists()

            # Check InPTA DR1
            if dr3_data["inpta"].exists():
                assert (dr3_data["inpta"] / "J0030+0451").exists()

            # Check MPTA DR1
            if dr3_data["mpta"].exists():
                assert (dr3_data["mpta"] / "MTMSP-J0030+0451-.par").exists()

    def test_par_file_discovery(self, available_data_sets, test_pulsars):
        """Test that par files can be discovered for test pulsars."""
        registry = PTARegistry()

        for config_name in registry.list_ptas():
            config = registry.get_pta(config_name)
            base_dir = Path(config["base_dir"])

            if not base_dir.exists():
                continue

            for pulsar in test_pulsars:
                # Try to find par file using the pattern
                par_files = list(base_dir.glob(f"**/{pulsar}*.par"))
                if par_files:
                    # Found at least one par file for this pulsar
                    assert len(par_files) > 0
                    break  # Found at least one config with this pulsar

    def test_tim_file_discovery(self, available_data_sets, test_pulsars):
        """Test that tim files can be discovered for test pulsars."""
        registry = PTARegistry()

        for config_name in registry.list_ptas():
            config = registry.get_pta(config_name)
            base_dir = Path(config["base_dir"])

            if not base_dir.exists():
                continue

            for pulsar in test_pulsars:
                # Try to find tim file using the pattern
                tim_files = list(base_dir.glob(f"**/{pulsar}*.tim"))
                if tim_files:
                    # Found at least one tim file for this pulsar
                    assert len(tim_files) > 0
                    break  # Found at least one config with this pulsar

    @pytest.mark.slow
    def test_data_availability_summary(self, available_data_sets):
        """Test and report data availability summary."""
        registry = PTARegistry()

        print("\n=== Data Availability Summary ===")

        for config_name in registry.list_ptas():
            config = registry.get_pta(config_name)
            base_dir = Path(config["base_dir"])

            if base_dir.exists():
                par_count = len(list(base_dir.glob("**/*.par")))
                tim_count = len(list(base_dir.glob("**/*.tim")))
                print(f"✓ {config_name}: {par_count} par files, {tim_count} tim files")
            else:
                print(f"✗ {config_name}: Directory not found ({base_dir})")

        print("================================\n")
