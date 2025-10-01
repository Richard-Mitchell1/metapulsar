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

# Import MetaPulsar and ParFileManager
from .metapulsar import MetaPulsar
from .parfile_manager import ParFileManager

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
from .position_helpers import bj_name_from_pulsar


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
        self.parfile_manager = ParFileManager(registry=self.registry)

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
        self,
        pulsar_name: str,
        pta_names: List[str] = None,
        combination_strategy: str = "composite",
        reference_pta: str = None,
        combine_components: List[str] = None,
        add_dm_derivatives: bool = True,
    ) -> MetaPulsar:
        """Create MetaPulsar using specified combination strategy.

        Args:
            pulsar_name: Name of the pulsar
            pta_names: List of PTA names to include. If None, uses all available.
            combination_strategy: Strategy for combining PTAs:
                - "composite": Multi-PTA composition (preserves original parameters, Borg/FrankenStat methods)
                - "consistent": Astrophysical consistency (modifies par files for consistency)
            reference_pta: PTA to use as reference (for consistent strategy)
            combine_components: List of components to make consistent (for consistent strategy)
            add_dm_derivatives: Whether to ensure DM1, DM2 are present in all par files (for consistent strategy)

        Returns:
            MetaPulsar object

        Raises:
            ValueError: If no files found for the pulsar or invalid parameters
            RuntimeError: If Enterprise Pulsar creation fails
        """
        self.logger.info(
            f"Creating MetaPulsar for {pulsar_name} using {combination_strategy} strategy"
        )

        # Validate reference_pta if provided
        if reference_pta is not None and reference_pta not in self.registry.configs:
            raise KeyError(
                f"Invalid reference PTA: {reference_pta}. Available PTAs: {list(self.registry.configs.keys())}"
            )

        if combination_strategy == "consistent":
            return self._create_consistent_metapulsar(
                pulsar_name,
                pta_names,
                reference_pta,
                combine_components,
                add_dm_derivatives,
            )
        elif combination_strategy == "composite":
            return self._create_composite_metapulsar(pulsar_name, pta_names)
        else:
            raise ValueError(f"Unknown combination strategy: {combination_strategy}")

    def list_available_pulsars(self, pta_names: List[str] = None) -> List[str]:
        """List all available pulsars across specified PTAs.

        Args:
            pta_names: List of PTA names to search. If None, searches all PTAs.

        Returns:
            List of pulsar names found across all specified PTAs
        """
        return self.discover_available_pulsars(pta_names)

    def _create_consistent_metapulsar(
        self,
        pulsar_name: str,
        pta_names: List[str],
        reference_pta: str,
        combine_components: List[str],
        add_dm_derivatives: bool,
    ) -> MetaPulsar:
        """Create MetaPulsar with astrophysically consistent parameters."""
        # 1. Make par files consistent
        consistent_files = self.parfile_manager.write_consistent_parfiles(
            pulsar_name,
            pta_names,
            reference_pta,
            combine_components,
            add_dm_derivatives,
        )

        # 2. Create Enterprise Pulsars from consistent files
        enterprise_pulsars = self._create_enterprise_pulsars_from_files(
            consistent_files
        )

        # 3. Get canonical name
        pta_configs = self.registry.get_pta_subset(pta_names)
        canonical_name = self._get_canonical_name_for_pulsar(pulsar_name, pta_configs)

        # 4. Create MetaPulsar
        return MetaPulsar(
            pulsars=enterprise_pulsars,
            combination_strategy="consistent",
            canonical_name=canonical_name,
        )

    def _create_composite_metapulsar(
        self, pulsar_name: str, pta_names: List[str]
    ) -> MetaPulsar:
        """Create MetaPulsar with composite approach (preserves original parameters, Borg/FrankenStat methods)."""
        # 1. Discover raw par files
        raw_parfiles = self._discover_parfiles(pulsar_name, pta_names)

        # 2. Check if any par files were found
        if not raw_parfiles:
            # Try coordinate-based discovery as fallback
            pta_configs = (
                self.registry.get_pta_subset(pta_names)
                if pta_names is not None
                else self.registry.configs
            )
            coordinate_map = self._discover_pulsars_by_coordinates(pta_configs)

            # Check if pulsar was found through coordinate discovery
            matching_pulsar = None
            for j_name, pulsar_info in coordinate_map.items():
                if (
                    pulsar_name == j_name
                    or pulsar_name == pulsar_info["preferred_name"]
                    or pulsar_name == pulsar_info["b_name"]
                ):
                    matching_pulsar = pulsar_info
                    break

            if not matching_pulsar:
                raise FileNotFoundError(
                    f"No data found for pulsar '{pulsar_name}' in PTAs: {pta_names}. "
                    f"Please verify the pulsar name and PTA configurations."
                )

            # Use the discovered files from coordinate search
            raw_parfiles = {}
            for pta_name, (parfile, timfile) in matching_pulsar["files"].items():
                raw_parfiles[pta_name] = parfile

        # 3. Create raw PINT/Tempo2 objects from files
        raw_pulsars = self._create_raw_pulsars_from_files(raw_parfiles)

        # 4. Get canonical name
        pta_configs = (
            self.registry.get_pta_subset(pta_names)
            if pta_names is not None
            else self.registry.configs
        )
        canonical_name = self._get_canonical_name_for_pulsar(pulsar_name, pta_configs)

        # 5. Create MetaPulsar
        return MetaPulsar(
            pulsars=raw_pulsars,
            combination_strategy="composite",
            canonical_name=canonical_name,
        )

    def _discover_parfiles(
        self, pulsar_name: str, pta_names: List[str] = None
    ) -> Dict[str, Path]:
        """Discover par files using PTARegistry."""
        return self.parfile_manager._discover_parfiles(pulsar_name, pta_names)

    def _create_raw_pulsars_from_files(
        self, file_paths: Dict[str, Path]
    ) -> Dict[str, Any]:
        """Create raw PINT/Tempo2 objects from file paths."""
        # Convert to file pairs format (par, tim) for the existing method
        file_pairs = {}
        for pta_name, parfile in file_paths.items():
            # Find corresponding tim file
            config = self.registry.configs[pta_name]
            timfile = self._find_timfile(parfile, config)
            file_pairs[pta_name] = (parfile, timfile)

        # Create raw PINT/Tempo2 objects
        return self._create_raw_pulsars(file_pairs, self.registry.configs)

    def _create_raw_pulsars(
        self, file_pairs: Dict[str, Tuple[Path, Path]], pta_configs: Dict[str, Dict]
    ) -> Dict[str, Any]:
        """Create raw PINT/Tempo2 objects from file pairs.

        Args:
            file_pairs: Dictionary mapping PTA names to (parfile, timfile) tuples
            pta_configs: Dictionary of PTA configurations

        Returns:
            Dictionary mapping PTA names to raw PINT/Tempo2 objects

        Raises:
            RuntimeError: If raw pulsar creation fails
        """
        raw_pulsars = {}

        for pta_name, (parfile, timfile) in file_pairs.items():
            config = pta_configs[pta_name]

            try:
                if config["timing_package"] == "pint":
                    # Create raw PINT objects
                    if get_model_and_toas is None:
                        raise RuntimeError("PINT not available for raw PINT creation")

                    model, toas = get_model_and_toas(str(parfile), str(timfile))
                    raw_pulsars[pta_name] = (model, toas)

                else:  # tempo2
                    # Create raw Tempo2 object
                    if t2 is None:
                        raise RuntimeError(
                            "libstempo not available for raw Tempo2 creation"
                        )

                    t2_psr = t2.tempopulsar(str(parfile), str(timfile))
                    raw_pulsars[pta_name] = t2_psr

                self.logger.debug(
                    f"Created raw {config['timing_package']} object for {pta_name}"
                )

            except Exception as e:
                self.logger.error(f"Failed to create raw pulsar for {pta_name}: {e}")
                raise RuntimeError(f"Failed to create raw pulsar for {pta_name}: {e}")

        return raw_pulsars

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
        """Discover all available pulsars using coordinate-based matching.

        Args:
            pta_names: List of PTA names to search. If None, searches all PTAs.

        Returns:
            List of canonical pulsar names (B-names preferred, J-names as fallback)
        """
        pta_configs = (
            self.registry.get_pta_subset(pta_names)
            if pta_names
            else self.registry.configs
        )

        # Use coordinate-based discovery instead of filename-based
        coordinate_map = self._discover_pulsars_by_coordinates(pta_configs)

        # Return preferred names (B-names when available, J-names otherwise)
        pulsar_list = sorted(
            [info["preferred_name"] for info in coordinate_map.values()]
        )
        self.logger.info(
            f"Discovered {len(pulsar_list)} unique pulsars across {len(pta_configs)} PTAs"
        )
        return pulsar_list

    def _discover_pulsars_by_coordinates(
        self, pta_configs: Dict[str, Dict]
    ) -> Dict[str, Dict]:
        """Discover pulsars by reading par files and extracting coordinates."""
        from pint.models.model_builder import parse_parfile, ModelBuilder
        from io import StringIO

        coordinate_map = {}
        builder = ModelBuilder()

        for pta_name, config in pta_configs.items():
            for parfile_path in self._discover_parfiles_in_pta(config):
                try:
                    # Parse the parfile to get the parameter dictionary
                    par_dict = parse_parfile(str(parfile_path))

                    # Create a minimal parfile string with only coordinate parameters
                    minimal_parfile = self._create_minimal_parfile_for_coordinates(
                        par_dict
                    )

                    # Use PINT's ModelBuilder to automatically choose the right astrometry component
                    model = builder(
                        StringIO(minimal_parfile), allow_tcb=True, allow_T2=True
                    )

                    # Extract coordinates using PINT's full capabilities
                    j_name = bj_name_from_pulsar(model, "J")
                    b_name = bj_name_from_pulsar(model, "B")
                    suffix = self._extract_suffix_from_filename(
                        parfile_path, config["par_pattern"]
                    )

                    if j_name not in coordinate_map:
                        coordinate_map[j_name] = {
                            "ptas": [],
                            "files": {},
                            "preferred_name": j_name,
                            "suffix": "",
                            "b_name": b_name,
                        }

                    coordinate_map[j_name]["ptas"].append(pta_name)
                    coordinate_map[j_name]["files"][pta_name] = (
                        parfile_path,
                        self._find_timfile(parfile_path, config),
                    )

                    # Prefer B-name if available
                    if b_name and not coordinate_map[j_name][
                        "preferred_name"
                    ].startswith("B"):
                        coordinate_map[j_name]["preferred_name"] = b_name

                    if suffix:
                        coordinate_map[j_name]["suffix"] = suffix

                except Exception as e:
                    self.logger.warning(f"Failed to process {parfile_path}: {e}")

        return coordinate_map

    def _create_minimal_parfile_for_coordinates(self, par_dict: Dict) -> str:
        """Create a minimal parfile string with only coordinate-related parameters.

        This avoids the 'duplicated keys' error from flagged parameters like EFAC, ECORR
        while still allowing PINT to automatically choose the correct astrometry component.
        """
        coordinate_params = [
            "PSRJ",
            "PSRB",
            "RAJ",
            "DECJ",
            "PMRA",
            "PMDEC",
            "PEPOCH",
            "UNITS",
        ]

        lines = []
        for param in coordinate_params:
            if param in par_dict:
                # Take the first value (ignore flags for now)
                value = (
                    par_dict[param][0]
                    if isinstance(par_dict[param], list)
                    else par_dict[param]
                )
                if isinstance(value, list):
                    value = value[0]
                lines.append(f"{param}    {value}")

        return "\n".join(lines) + "\n"

    def _discover_parfiles_in_pta(self, config: Dict) -> List[Path]:
        """Discover par files in a single PTA configuration."""
        import re

        base_dir = Path(config["base_dir"])
        pattern = config["par_pattern"]

        parfiles = []
        for file_path in base_dir.rglob("*.par"):
            if re.search(pattern, str(file_path)):
                parfiles.append(file_path)

        return parfiles

    def _extract_suffix_from_filename(self, file_path: Path, pattern: str) -> str:
        """Extract suffix (A, B, etc.) from filename if present."""
        import re

        match = re.search(pattern, str(file_path))
        if match:
            coord_part = match.group(1)
            # Check if the coordinate part ends with a letter (suffix)
            suffix_match = re.search(r"([A-Z])$", coord_part)
            if suffix_match:
                return suffix_match.group(1)
        return ""

    def _find_timfile(self, parfile_path: Path, config: Dict) -> Path:
        """Find corresponding tim file for a par file."""
        import re

        match = re.search(config["par_pattern"], str(parfile_path))
        if match:
            pulsar_name = match.group(1)
            return self._find_file(
                pulsar_name, config["base_dir"], config["tim_pattern"]
            )
        return None

    def _discover_files(
        self, pulsar_name: str, pta_configs: Dict[str, Dict]
    ) -> Dict[str, Tuple[Path, Path]]:
        """Discover par/tim files for a pulsar across PTAs using coordinate matching.

        Args:
            pulsar_name: Name of the pulsar (can be J-name, B-name, or preferred name)
            pta_configs: Dictionary of PTA configurations to search

        Returns:
            Dictionary mapping PTA names to (parfile, timfile) tuples
        """
        # First, discover all pulsars by coordinates
        coordinate_map = self._discover_pulsars_by_coordinates(pta_configs)

        # Find the matching pulsar by any of its names
        matching_pulsar = None
        for j_name, pulsar_info in coordinate_map.items():
            if (
                pulsar_name == j_name
                or pulsar_name == pulsar_info["preferred_name"]
                or pulsar_name == pulsar_info["b_name"]
            ):
                matching_pulsar = pulsar_info
                break

        if not matching_pulsar:
            available_names = [
                info["preferred_name"] for info in coordinate_map.values()
            ]
            raise ValueError(
                f"Pulsar '{pulsar_name}' not found. Available: {available_names}"
            )

        return matching_pulsar["files"]

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
            Canonical J-name for the pulsar (used as internal identifier)
        """
        # Use the first Enterprise Pulsar to get coordinates
        first_pulsar = next(iter(enterprise_pulsars.values()))

        # Use existing position helpers for robust name resolution
        try:
            return bj_name_from_pulsar(
                first_pulsar, "J"
            )  # Use J for internal identification
        except Exception as e:
            self.logger.warning(f"Failed to resolve canonical name: {e}")
            # Fallback to a generic name
            return "UNKNOWN"

    def _get_canonical_name_for_pulsar(
        self, pulsar_name: str, pta_configs: Dict[str, Dict]
    ) -> str:
        """Get the canonical name (with suffix) for a pulsar."""
        coordinate_map = self._discover_pulsars_by_coordinates(pta_configs)

        for j_name, pulsar_info in coordinate_map.items():
            if (
                pulsar_name == j_name
                or pulsar_name == pulsar_info["preferred_name"]
                or pulsar_name == pulsar_info["b_name"]
            ):
                canonical_name = pulsar_info["preferred_name"]
                if pulsar_info["suffix"]:
                    canonical_name += pulsar_info["suffix"]
                return canonical_name

        return pulsar_name

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
