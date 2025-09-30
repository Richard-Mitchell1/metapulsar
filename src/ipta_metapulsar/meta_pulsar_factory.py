"""Meta-Pulsar Factory for creating MetaPulsars by orchestrating Enterprise Pulsar creation.

This module provides a factory class that creates MetaPulsars by discovering files,
creating Enterprise Pulsars, and wrapping them with metadata.
"""

from typing import Dict, List, Tuple, Union, Optional, Any
from pathlib import Path
import re
from datetime import datetime
from loguru import logger

# Import Enterprise Pulsar classes
try:
    from enterprise.pulsar import PintPulsar, Tempo2Pulsar
except ImportError:
    PintPulsar = None
    Tempo2Pulsar = None

# Import PINT for model creation
try:
    from pint.models import get_model_and_toas
except ImportError:
    get_model_and_toas = None

# Import libstempo for Tempo2Pulsar creation
try:
    import libstempo as t2
except ImportError:
    t2 = None

from .pta_registry import PTARegistry
from .metapulsar import MetaPulsar
from .position_helpers import j_name_from_pulsar


class MetaPulsarFactory:
    """Factory for creating MetaPulsars by orchestrating Enterprise Pulsar creation.

    This class provides methods to discover files, create Enterprise Pulsars,
    and wrap them in MetaPulsar objects with appropriate metadata.
    """

    def __init__(self, registry: PTARegistry = None):
        """Initialize the MetaPulsar factory.

        Args:
            registry: PTARegistry instance to use. If None, creates a new one.
        """
        self.registry = registry or PTARegistry()
        self.logger = logger

        # Check dependencies
        self._check_dependencies()

    def _check_dependencies(self) -> None:
        """Check that required dependencies are available."""
        missing_deps = []

        if PintPulsar is None or Tempo2Pulsar is None:
            missing_deps.append("enterprise")

        if get_model_and_toas is None:
            missing_deps.append("pint")

        if t2 is None:
            missing_deps.append("libstempo")

        if missing_deps:
            self.logger.warning(
                f"Missing dependencies: {missing_deps}. "
                "Some functionality may not work."
            )

    def create_metapulsar(
        self, pulsar_name: str, pta_names: List[str] = None
    ) -> MetaPulsar:
        """Create MetaPulsar by creating Enterprise Pulsars for each PTA.

        Args:
            pulsar_name: Name of the pulsar to create MetaPulsar for
            pta_names: List of PTA names to include. If None, uses all available PTAs.

        Returns:
            MetaPulsar object containing Enterprise Pulsars from all available PTAs

        Raises:
            ValueError: If no files found for the pulsar
            RuntimeError: If Enterprise Pulsar creation fails
        """
        self.logger.info(f"Creating MetaPulsar for {pulsar_name}")

        # 1. Get PTA configurations
        pta_configs = (
            self.registry.get_pta_subset(pta_names)
            if pta_names
            else self.registry.configs
        )

        # 2. Discover files
        file_pairs = self._discover_files(pulsar_name, pta_configs)

        if not file_pairs:
            raise ValueError(f"No files found for pulsar {pulsar_name}")

        self.logger.debug(
            f"Found files for {pulsar_name} in {len(file_pairs)} PTAs: {list(file_pairs.keys())}"
        )

        # 3. Create Enterprise Pulsars
        enterprise_pulsars = self._create_enterprise_pulsars(file_pairs, pta_configs)

        # 4. Resolve canonical name
        canonical_name = self._resolve_canonical_name(enterprise_pulsars)

        # 5. Build metadata (for future use)
        # metadata = self._build_metadata(file_pairs, pta_configs)

        # 6. Create MetaPulsar directly using constructor
        # Convert enterprise_pulsars to the format expected by MetaPulsar constructor
        pulsars_dict = {}
        for pta_name, enterprise_pulsar in enterprise_pulsars.items():
            # For now, store the enterprise pulsar directly
            # TODO: Convert to PINT model/TOAs tuple format if needed
            pulsars_dict[pta_name] = enterprise_pulsar

        metapulsar = MetaPulsar(pulsars=pulsars_dict, planets=True)

        self.logger.info(
            f"Successfully created MetaPulsar {canonical_name} with {len(enterprise_pulsars)} PTAs"
        )
        return metapulsar

    def create_all_metapulsars(
        self, pta_names: List[str] = None
    ) -> Dict[str, MetaPulsar]:
        """Create MetaPulsars for all available pulsars.

        Args:
            pta_names: List of PTA names to include. If None, uses all available PTAs.

        Returns:
            Dictionary mapping pulsar names to MetaPulsar objects
        """
        available_pulsars = self.discover_available_pulsars(pta_names)
        metapulsars = {}

        self.logger.info(f"Creating MetaPulsars for {len(available_pulsars)} pulsars")

        for pulsar_name in available_pulsars:
            try:
                metapulsars[pulsar_name] = self.create_metapulsar(
                    pulsar_name, pta_names
                )
            except Exception as e:
                self.logger.warning(
                    f"Failed to create MetaPulsar for {pulsar_name}: {e}"
                )

        self.logger.info(f"Successfully created {len(metapulsars)} MetaPulsars")
        return metapulsars

    def discover_available_pulsars(self, pta_names: List[str] = None) -> List[str]:
        """Discover all available pulsars across PTAs.

        Args:
            pta_names: List of PTA names to search. If None, searches all PTAs.

        Returns:
            List of pulsar names found across all specified PTAs
        """
        pta_configs = (
            self.registry.get_pta_subset(pta_names)
            if pta_names
            else self.registry.configs
        )
        all_pulsars = set()

        for pta_name, config in pta_configs.items():
            pulsars = self._discover_pulsars_in_pta(config)
            all_pulsars.update(pulsars)
            self.logger.debug(f"Found {len(pulsars)} pulsars in {pta_name}")

        pulsar_list = sorted(list(all_pulsars))
        self.logger.info(
            f"Discovered {len(pulsar_list)} unique pulsars across {len(pta_configs)} PTAs"
        )
        return pulsar_list

    def _discover_files(
        self, pulsar_name: str, pta_configs: Dict[str, Dict]
    ) -> Dict[str, Tuple[Path, Path]]:
        """Discover par/tim files for a pulsar across PTAs.

        Args:
            pulsar_name: Name of the pulsar to search for
            pta_configs: Dictionary of PTA configurations to search

        Returns:
            Dictionary mapping PTA names to (parfile, timfile) tuples
        """
        file_pairs = {}

        for pta_name, config in pta_configs.items():
            parfile = self._find_file(
                pulsar_name, config["base_dir"], config["par_pattern"]
            )
            timfile = self._find_file(
                pulsar_name, config["base_dir"], config["tim_pattern"]
            )

            if parfile and timfile:
                file_pairs[pta_name] = (parfile, timfile)
                self.logger.debug(
                    f"Found files for {pulsar_name} in {pta_name}: {parfile}, {timfile}"
                )
            else:
                self.logger.debug(f"No files found for {pulsar_name} in {pta_name}")

        return file_pairs

    def _create_enterprise_pulsars(
        self, file_pairs: Dict[str, Tuple[Path, Path]], pta_configs: Dict[str, Dict]
    ) -> Dict[str, Union[PintPulsar, Tempo2Pulsar]]:
        """Create Enterprise Pulsars from file pairs.

        Args:
            file_pairs: Dictionary mapping PTA names to (parfile, timfile) tuples
            pta_configs: Dictionary of PTA configurations

        Returns:
            Dictionary mapping PTA names to Enterprise Pulsar objects

        Raises:
            RuntimeError: If Enterprise Pulsar creation fails
        """
        enterprise_pulsars = {}

        for pta_name, (parfile, timfile) in file_pairs.items():
            config = pta_configs[pta_name]

            try:
                if config["timing_package"] == "pint":
                    # Create PintPulsar
                    if get_model_and_toas is None:
                        raise RuntimeError("PINT not available for PintPulsar creation")

                    model, toas = get_model_and_toas(str(parfile), str(timfile))
                    enterprise_pulsars[pta_name] = PintPulsar(toas, model, planets=True)

                else:  # tempo2
                    # Create Tempo2Pulsar
                    if t2 is None:
                        raise RuntimeError(
                            "libstempo not available for Tempo2Pulsar creation"
                        )

                    t2_psr = t2.tempopulsar(str(parfile), str(timfile))
                    enterprise_pulsars[pta_name] = Tempo2Pulsar(t2_psr, planets=True)

                self.logger.debug(
                    f"Created {config['timing_package']} Enterprise Pulsar for {pta_name}"
                )

            except Exception as e:
                self.logger.error(
                    f"Failed to create Enterprise Pulsar for {pta_name}: {e}"
                )
                raise RuntimeError(
                    f"Failed to create Enterprise Pulsar for {pta_name}: {e}"
                )

        return enterprise_pulsars

    def _resolve_canonical_name(
        self, enterprise_pulsars: Dict[str, Union[PintPulsar, Tempo2Pulsar]]
    ) -> str:
        """Resolve canonical name using position helpers.

        Args:
            enterprise_pulsars: Dictionary of Enterprise Pulsars

        Returns:
            Canonical J-name for the pulsar
        """
        # Use the first Enterprise Pulsar to get coordinates
        first_pulsar = next(iter(enterprise_pulsars.values()))

        # Use existing position helpers for robust name resolution
        try:
            return j_name_from_pulsar(first_pulsar)
        except Exception as e:
            self.logger.warning(f"Failed to resolve canonical name: {e}")
            # Fallback to a generic name
            return "UNKNOWN"

    def _build_metadata(
        self, file_pairs: Dict[str, Tuple[Path, Path]], pta_configs: Dict[str, Dict]
    ) -> Dict[str, Any]:
        """Build metadata for the MetaPulsar.

        Args:
            file_pairs: Dictionary mapping PTA names to (parfile, timfile) tuples
            pta_configs: Dictionary of PTA configurations

        Returns:
            Dictionary containing metadata
        """
        return {
            "file_pairs": {
                pta: (str(par), str(tim)) for pta, (par, tim) in file_pairs.items()
            },
            "timing_packages": {
                pta: config["timing_package"] for pta, config in pta_configs.items()
            },
            "creation_timestamp": datetime.now().isoformat(),
        }

    def _find_file(
        self, pulsar_name: str, base_dir: str, pattern: str
    ) -> Optional[Path]:
        """Find a file matching the pattern in the base directory.

        Args:
            pulsar_name: Name of the pulsar to search for
            base_dir: Base directory to search in
            pattern: Regex pattern to match (must capture pulsar name in group 1)

        Returns:
            Path to the matching file, or None if not found
        """
        base_path = Path(base_dir)
        if not base_path.exists():
            return None

        # Compile regex pattern
        try:
            regex = re.compile(pattern)
        except re.error as e:
            self.logger.error(f"Invalid regex pattern '{pattern}': {e}")
            return None

        # Search for matching files
        for file_path in base_path.rglob("*"):
            if file_path.is_file():
                match = regex.search(str(file_path))
                if match and match.group(1) == pulsar_name:
                    return file_path

        return None

    def _discover_pulsars_in_pta(self, config: Dict) -> List[str]:
        """Discover all pulsars in a single PTA.

        Args:
            config: PTA configuration to search

        Returns:
            List of pulsar names found in the PTA
        """
        base_path = Path(config["base_dir"])
        if not base_path.exists():
            return []

        pulsars = set()

        try:
            regex = re.compile(config["par_pattern"])
        except re.error as e:
            self.logger.error(f"Invalid regex pattern '{config['par_pattern']}': {e}")
            return []

        for file_path in base_path.rglob("*.par"):
            match = regex.search(str(file_path))
            if match:
                pulsars.add(match.group(1))

        return list(pulsars)
