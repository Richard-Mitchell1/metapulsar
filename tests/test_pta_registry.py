"""Tests for PTA Registry System."""

import pytest
from metapulsar.pta_registry import PTARegistry


class TestPTARegistry:
    """Test PTARegistry class."""

    def test_initialization(self):
        """Test registry initialization with presets."""
        registry = PTARegistry()

        # Should have loaded presets
        assert len(registry.configs) > 0

        # Check that some expected PTAs are present
        expected_ptas = ["epta_dr2", "ppta_dr2", "nanograv_15y"]
        for pta in expected_ptas:
            assert pta in registry.configs

    def test_add_pta(self):
        """Test adding a PTA configuration."""
        registry = PTARegistry()
        initial_count = len(registry.configs)

        config = {
            "base_dir": "/data/custom",
            "par_pattern": r"([BJ]\d{4}[+-]\d{2,4})\.par",
            "tim_pattern": r"([BJ]\d{4}[+-]\d{2,4})\.tim",
            "timing_package": "pint",
            "priority": 1,
            "description": "Custom PTA",
        }

        registry.add_pta("custom_pta", config)

        assert len(registry.configs) == initial_count + 1
        assert "custom_pta" in registry.configs
        assert registry.configs["custom_pta"] == config

    def test_add_duplicate_pta(self):
        """Test that adding duplicate PTA raises ValueError."""
        registry = PTARegistry()

        config = {
            "base_dir": "/data/custom",
            "par_pattern": r"([BJ]\d{4}[+-]\d{2,4})\.par",
            "tim_pattern": r"([BJ]\d{4}[+-]\d{2,4})\.tim",
            "timing_package": "pint",
        }

        with pytest.raises(ValueError, match="PTA 'epta_dr2' already exists"):
            registry.add_pta("epta_dr2", config)

    def test_get_pta(self):
        """Test getting a PTA configuration."""
        registry = PTARegistry()

        config = registry.get_pta("epta_dr2")

        assert config["timing_package"] == "tempo2"

    def test_get_nonexistent_pta(self):
        """Test that getting nonexistent PTA raises KeyError."""
        registry = PTARegistry()

        with pytest.raises(KeyError, match="PTA 'nonexistent' not found"):
            registry.get_pta("nonexistent")

    def test_list_ptas(self):
        """Test listing PTA names."""
        registry = PTARegistry()

        pta_list = registry.list_ptas()

        assert isinstance(pta_list, list)
        assert len(pta_list) > 0
        assert "epta_dr2" in pta_list

    def test_get_pta_subset(self):
        """Test getting a subset of PTA configurations."""
        registry = PTARegistry()

        subset = registry.get_pta_subset(["epta_dr2", "ppta_dr2"])

        assert len(subset) == 2
        assert "epta_dr2" in subset
        assert "ppta_dr2" in subset

    def test_get_pta_subset_nonexistent(self):
        """Test that getting subset with nonexistent PTA raises KeyError."""
        registry = PTARegistry()

        with pytest.raises(KeyError, match="PTA 'nonexistent' not found"):
            registry.get_pta_subset(["epta_dr2", "nonexistent"])

    def test_preset_configurations(self):
        """Test that preset configurations are valid."""
        registry = PTARegistry()

        for pta_name, config in registry.configs.items():
            # Check that all required fields are present
            assert "base_dir" in config
            assert "par_pattern" in config
            assert "tim_pattern" in config
            assert config["timing_package"] in ["pint", "tempo2"]

            # Check that patterns are valid regex
            import re

            re.compile(config["par_pattern"])
            re.compile(config["tim_pattern"])

    def test_validation(self):
        """Test configuration validation."""
        registry = PTARegistry()

        # Test missing required keys
        with pytest.raises(ValueError, match="Missing required keys"):
            registry.add_pta("test", {"base_dir": "/data"})

        # Test invalid timing package
        with pytest.raises(ValueError, match="Invalid timing_package"):
            registry.add_pta(
                "test",
                {
                    "base_dir": "/data",
                    "par_pattern": r"([BJ]\d{4}[+-]\d{2,4})\.par",
                    "tim_pattern": r"([BJ]\d{4}[+-]\d{2,4})\.tim",
                    "timing_package": "invalid",
                },
            )

    def test_filtering_methods(self):
        """Test filtering methods."""
        registry = PTARegistry()

        # Test timing package filtering
        pint_ptas = registry.get_ptas_by_timing_package("pint")
        tempo2_ptas = registry.get_ptas_by_timing_package("tempo2")

        assert len(pint_ptas) > 0
        assert len(tempo2_ptas) > 0
        assert "nanograv_15y" in pint_ptas
        assert "epta_dr2" in tempo2_ptas
