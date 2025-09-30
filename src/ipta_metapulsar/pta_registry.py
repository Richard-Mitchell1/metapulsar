"""PTA Registry System for managing PTA configurations and presets.

This module provides a simple dictionary-based system for managing PTA (Pulsar Timing Array)
configurations, including preset configurations for IPTA DR3 data releases.
"""

from typing import Dict, List
from loguru import logger


# Simple, clean PTA configurations
PTA_CONFIGS = {
    "epta_dr2": {
        "base_dir": "/data/IPTA-DR3/EPTA_DR2/",
        "par_pattern": r"([BJ]\d{4}[+-]\d{2,4})/\1\.par",
        "tim_pattern": r"([BJ]\d{4}[+-]\d{2,4})/\1_all\.tim",
        "coordinates": "ecliptical",
        "timing_package": "tempo2",
        "priority": 1,
        "description": "EPTA Data Release 2",
    },
    "ppta_dr2": {
        "base_dir": "/data/IPTA-DR3/PPTA_DR2/",
        "par_pattern": r"([BJ]\d{4}[+-]\d{2,4}[A-Z]?)\.par",
        "tim_pattern": r"([BJ]\d{4}[+-]\d{2,4}[A-Z]?)\.tim",
        "coordinates": "equatorial",
        "timing_package": "tempo2",
        "priority": 1,
        "description": "PPTA Data Release 2",
    },
    "ppta_dr3": {
        "base_dir": "/data/IPTA-DR3/PPTA_DR3/",
        "par_pattern": r"([BJ]\d{4}[+-]\d{2,4}[A-Z]?)\.par",
        "tim_pattern": r"([BJ]\d{4}[+-]\d{2,4}[A-Z]?)\.tim",
        "coordinates": "equatorial",
        "timing_package": "tempo2",
        "priority": 2,
        "description": "PPTA Data Release 3",
    },
    "inpta_dr1": {
        "base_dir": "/data/IPTA-DR3/InPTA_DR1/",
        "par_pattern": r"([BJ]\d{4}[+-]\d{2,4})\/\1\.par",
        "tim_pattern": r"([BJ]\d{4}[+-]\d{2,4})\/\1_all\.tim",
        "coordinates": "equatorial",
        "timing_package": "tempo2",
        "priority": 1,
        "description": "InPTA Data Release 1",
    },
    "inpta_dr1_edited": {
        "base_dir": "/data/IPTA-DR3/InPTA_DR1_edited/",
        "par_pattern": r"([BJ]\d{4}[+-]\d{2,4})\/\1\.par",
        "tim_pattern": r"([BJ]\d{4}[+-]\d{2,4})\/\1_all\.tim",
        "coordinates": "equatorial",
        "timing_package": "tempo2",
        "priority": 2,
        "description": "InPTA Data Release 1 (Edited)",
    },
    "mpta_dr1": {
        "base_dir": "/data/IPTA-DR3/MPTA_DR1/",
        "par_pattern": r"MTMSP-([BJ]\d{4}[+-]\d{2,4})-\.par",
        "tim_pattern": r"([BJ]\d{4}[+-]\d{2,4})_16ch\.tim",
        "coordinates": "equatorial",
        "timing_package": "tempo2",
        "priority": 1,
        "description": "MPTA Data Release 1",
    },
    "nanograv_12y": {
        "base_dir": "/data/IPTA-DR3/NANOGrav_12y/",
        "par_pattern": r"par/([BJ]\d{4}[+-]\d{2,4})(?!.*\.t2)_NANOGrav_12yv2\.gls\.par",
        "tim_pattern": r"tim/([BJ]\d{4}[+-]\d{2,4})_NANOGrav_12yv2\.tim",
        "coordinates": "ecliptical",
        "timing_package": "pint",
        "priority": 1,
        "description": "NANOGrav 12-year Data Release",
    },
    "nanograv_15y": {
        "base_dir": "/data/IPTA-DR3/NANOGrav_15y/",
        "par_pattern": r"par/([BJ]\d{4}[+-]\d{2,4})(?!.*(ao|gbt)).*\.par",
        "tim_pattern": r"tim/([BJ]\d{4}[+-]\d{2,4})(?!.*(ao|gbt)).*\.tim",
        "coordinates": "ecliptical",
        "timing_package": "pint",
        "priority": 2,
        "description": "NANOGrav 15-year Data Release",
    },
}


class PTARegistry:
    """Simple registry for PTA configurations using dictionaries.

    This class provides a clean, simple interface for managing PTA configurations.
    Uses dictionaries for configuration storage.
    """

    def __init__(self, configs: Dict = None):
        """Initialize the PTA registry.

        Args:
            configs: Dictionary of PTA configurations. If None, uses default presets.
        """
        self.configs = configs or PTA_CONFIGS.copy()
        logger.debug(
            f"Initialized PTA registry with {len(self.configs)} configurations"
        )

    def get_pta(self, name: str) -> Dict:
        """Get a PTA configuration by name.

        Args:
            name: Name of the PTA configuration

        Returns:
            Dictionary containing PTA configuration

        Raises:
            KeyError: If PTA not found
        """
        if name not in self.configs:
            raise KeyError(f"PTA '{name}' not found in registry")

        return self.configs[name]

    def list_ptas(self) -> List[str]:
        """Get list of all PTA names in the registry.

        Returns:
            List of PTA names, sorted by priority (descending) then name
        """
        return sorted(
            self.configs.keys(), key=lambda x: (-self.configs[x].get("priority", 0), x)
        )

    def get_pta_subset(self, pta_names: List[str]) -> Dict[str, Dict]:
        """Get a subset of PTA configurations.

        Args:
            pta_names: List of PTA names to retrieve

        Returns:
            Dictionary mapping PTA names to configuration dictionaries

        Raises:
            KeyError: If any PTA name not found
        """
        result = {}
        for name in pta_names:
            if name not in self.configs:
                raise KeyError(f"PTA '{name}' not found in registry")
            result[name] = self.configs[name]

        return result

    def add_pta(self, name: str, config: Dict) -> None:
        """Add a PTA configuration to the registry.

        Args:
            name: Name of the PTA configuration
            config: Dictionary containing PTA configuration

        Raises:
            ValueError: If PTA with same name already exists or config is invalid
        """
        if name in self.configs:
            raise ValueError(f"PTA '{name}' already exists in registry")

        # Simple validation
        self._validate_config(config)

        self.configs[name] = config
        logger.debug(f"Added PTA configuration: {name}")

    def update_pta(self, name: str, config: Dict) -> None:
        """Update an existing PTA configuration.

        Args:
            name: Name of the PTA configuration
            config: Dictionary containing updated PTA configuration

        Raises:
            KeyError: If PTA not found
            ValueError: If config is invalid
        """
        if name not in self.configs:
            raise KeyError(f"PTA '{name}' not found in registry")

        # Simple validation
        self._validate_config(config)

        self.configs[name] = config
        logger.debug(f"Updated PTA configuration: {name}")

    def remove_pta(self, name: str) -> None:
        """Remove a PTA configuration from the registry.

        Args:
            name: Name of the PTA configuration to remove

        Raises:
            KeyError: If PTA not found
        """
        if name not in self.configs:
            raise KeyError(f"PTA '{name}' not found in registry")

        del self.configs[name]
        logger.debug(f"Removed PTA configuration: {name}")

    def _validate_config(self, config: Dict) -> None:
        """Validate a PTA configuration dictionary.

        Args:
            config: Configuration dictionary to validate

        Raises:
            ValueError: If configuration is invalid
        """
        required_keys = {
            "base_dir",
            "par_pattern",
            "tim_pattern",
            "coordinates",
            "timing_package",
        }
        missing_keys = required_keys - config.keys()

        if missing_keys:
            raise ValueError(f"Missing required keys: {missing_keys}")

        if config["coordinates"] not in ["equatorial", "ecliptical"]:
            raise ValueError(
                f"Invalid coordinates: {config['coordinates']}. Must be 'equatorial' or 'ecliptical'"
            )

        if config["timing_package"] not in ["pint", "tempo2"]:
            raise ValueError(
                f"Invalid timing_package: {config['timing_package']}. Must be 'pint' or 'tempo2'"
            )

        # Validate regex patterns
        import re

        try:
            re.compile(config["par_pattern"])
            re.compile(config["tim_pattern"])
        except re.error as e:
            raise ValueError(f"Invalid regex pattern: {e}")

    def get_ptas_by_timing_package(self, timing_package: str) -> List[str]:
        """Get PTA names that use a specific timing package.

        Args:
            timing_package: Timing package to filter by ('pint' or 'tempo2')

        Returns:
            List of PTA names using the specified timing package
        """
        return [
            name
            for name, config in self.configs.items()
            if config.get("timing_package") == timing_package
        ]

    def get_ptas_by_coordinates(self, coordinates: str) -> List[str]:
        """Get PTA names that use a specific coordinate system.

        Args:
            coordinates: Coordinate system to filter by ('equatorial' or 'ecliptical')

        Returns:
            List of PTA names using the specified coordinate system
        """
        return [
            name
            for name, config in self.configs.items()
            if config.get("coordinates") == coordinates
        ]

    def __len__(self) -> int:
        """Get the number of PTA configurations."""
        return len(self.configs)

    def __contains__(self, name: str) -> bool:
        """Check if a PTA configuration exists."""
        return name in self.configs

    def __repr__(self) -> str:
        """String representation of the registry."""
        return f"PTARegistry({len(self.configs)} PTAs: {list(self.configs.keys())})"
