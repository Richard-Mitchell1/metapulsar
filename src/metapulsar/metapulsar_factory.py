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
        combination_strategy: str = "consistent",
        reference_pta: str = None,
        combine_components: List[str] = None,
        add_dm_derivatives: bool = True,
    ) -> MetaPulsar:
        """Create MetaPulsar using specified combination strategy.

        Args:
            pulsar_name: Name of the pulsar
            pta_names: List of PTA names to include. If None, uses all available.
            combination_strategy: Strategy for combining PTAs:
                - "consistent": Astrophysical consistency (modifies par files for consistency, the default)
                - "composite": Multi-PTA composition (preserves original parameters, Borg/FrankenStat methods)
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
        # 1. Discover original files (regex patterns OK here)
        pta_configs = self.registry.get_pta_subset(pta_names)
        original_files = self.discover_files(pulsar_name, pta_configs)

        # 2. Make par files consistent
        consistent_files = self.parfile_manager.write_consistent_parfiles(
            pulsar_name,
            pta_names,
            reference_pta,
            combine_components,
            add_dm_derivatives,
        )

        # 3. Create file pairs: (consistent_par, original_tim) - direct file paths!
        file_pairs = {}
        for pta_name in pta_names:
            if pta_name in original_files and pta_name in consistent_files:
                original_par, original_tim = original_files[pta_name]
                consistent_par = consistent_files[pta_name]
                file_pairs[pta_name] = (consistent_par, original_tim)  # Direct paths!

        # 4. Create Enterprise Pulsars (no regex patterns needed)
        enterprise_pulsars = self._create_enterprise_pulsars(file_pairs, pta_configs)

        # 5. Get canonical name
        canonical_name = self._get_canonical_name_for_pulsar(pulsar_name, pta_configs)

        # 6. Create MetaPulsar
        return MetaPulsar(
            pulsars=enterprise_pulsars,
            combination_strategy="consistent",
            canonical_name=canonical_name,
        )

    def _create_composite_metapulsar(
        self, pulsar_name: str, pta_names: List[str]
    ) -> MetaPulsar:
        """Create MetaPulsar with composite approach (preserves original parameters, Borg/FrankenStat methods)."""
        # 1. Discover raw par files using coordinate-based discovery
        raw_parfiles = self._discover_parfiles(pulsar_name, pta_names)

        # 2. Check if any par files were found
        if not raw_parfiles:
            raise FileNotFoundError(
                f"No data found for pulsar '{pulsar_name}' in PTAs: {pta_names}. "
                f"Please verify the pulsar name and PTA configurations."
            )

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

    def _extract_pulsar_name_from_pint_model(self, parfile_path: Path) -> str:
        """Extract pulsar name from PINT model (PSR parameter)."""
        from pint.models.model_builder import ModelBuilder
        from io import StringIO

        try:
            # Read par file with PINT
            with open(parfile_path, "r") as f:
                par_content = f.read()

            builder = ModelBuilder()
            model = builder(StringIO(par_content), allow_tcb=True, allow_T2=True)

            # Extract pulsar name from PINT model
            return model.PSR.value

        except Exception as e:
            raise ValueError(f"Cannot extract pulsar name from {parfile_path}: {e}")

    def _find_timfile_by_name(self, pulsar_name: str, config: Dict) -> Optional[Path]:
        """Find corresponding tim file using simple string matching (like legacy system)."""
        base_dir = Path(config["base_dir"])

        # Find all tim files that contain the pulsar name (simple string matching)
        for timfile_path in base_dir.rglob("*.tim"):
            if pulsar_name in str(timfile_path):
                return timfile_path

        return None

    def _create_raw_pulsars_from_files(
        self, file_paths: Dict[str, Path]
    ) -> Dict[str, Any]:
        """Create raw PINT/Tempo2 objects from file paths."""
        # Use discovery to find corresponding tim files for each par file
        file_pairs = {}
        for pta_name, parfile in file_paths.items():
            # Use discovery to find the corresponding tim file
            pta_configs = {pta_name: self.registry.configs[pta_name]}
            # Extract pulsar name from par file path for discovery
            pulsar_name = self._extract_pulsar_name_from_pint_model(parfile)
            discovered_files = self.discover_files(pulsar_name, pta_configs)

            if pta_name in discovered_files:
                original_par, timfile = discovered_files[pta_name]
                file_pairs[pta_name] = (
                    parfile,
                    timfile,
                )  # Use the provided par file, discovered tim file
            else:
                raise FileNotFoundError(f"Could not find tim file for {parfile}")

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
        from pint.models.model_builder import ModelBuilder
        from io import StringIO

        coordinate_map = {}
        builder = ModelBuilder()

        for pta_name, config in pta_configs.items():
            for parfile_path in self._discover_parfiles_in_pta(config):
                try:
                    # Read par file with PINT to get full model
                    with open(parfile_path, "r") as f:
                        par_content = f.read()

                    model = builder(
                        StringIO(par_content), allow_tcb=True, allow_T2=True
                    )

                    # Extract pulsar name from PINT model (no regex needed!)
                    pulsar_name = model.PSR.value

                    # Extract coordinates using PINT's full capabilities
                    j_name = bj_name_from_pulsar(model, "J")
                    b_name = bj_name_from_pulsar(model, "B")

                    if j_name not in coordinate_map:
                        coordinate_map[j_name] = {
                            "ptas": [],
                            "files": {},
                            "preferred_name": j_name,
                            "suffix": "",
                            "b_name": b_name,
                        }

                    coordinate_map[j_name]["ptas"].append(pta_name)

                    # Find corresponding tim file using simple string matching (no recursion!)
                    timfile = self._find_timfile_by_name(pulsar_name, config)

                    coordinate_map[j_name]["files"][pta_name] = (parfile_path, timfile)

                    # Prefer B-name if available
                    if b_name and not coordinate_map[j_name][
                        "preferred_name"
                    ].startswith("B"):
                        coordinate_map[j_name]["preferred_name"] = b_name

                except ValueError as e:
                    # Re-raise ValueError from bj_name_from_pulsar (malformed parfiles)
                    # This will propagate up to the caller
                    raise e
                except Exception as e:
                    # Log other exceptions (file I/O, etc.) as warnings
                    self.logger.warning(f"Failed to process {parfile_path}: {e}")

        return coordinate_map

    def _create_minimal_parfile_for_coordinates(self, parfile_path: Path) -> str:
        """Create minimal parfile using PINT's component detection.

        This approach:
        1. Loads the full parfile with PINT to detect components
        2. Extracts parameters from astrometry and spindown components
        3. Includes base parameters (PSR, UNITS)
        4. Creates a minimal parfile with only essential parameters
        """
        from pint.models.model_builder import ModelBuilder

        # Load the full parfile with PINT
        builder = ModelBuilder()
        model = builder(str(parfile_path), allow_tcb=True, allow_T2=True)

        lines = []

        # Helper function to safely get parameter value
        def get_param_value(param_name):
            """Safely extract parameter value from model."""
            try:
                param_obj = getattr(model, param_name, None)
                if param_obj is None:
                    return None
                return (
                    param_obj.value if hasattr(param_obj, "value") else str(param_obj)
                )
            except (AttributeError, TypeError):
                return None

        # Base parameters that are always needed
        base_params = ["PSR", "UNITS"]
        for param in base_params:
            value = get_param_value(param)
            if value is not None:
                lines.append(f"{param}    {value}")

        # Extract parameters from astrometry components
        for comp in model.components.values():
            if not (hasattr(comp, "category") and comp.category == "astrometry"):
                continue
            if not hasattr(comp, "params"):
                continue

            for param_name in comp.params:
                value = get_param_value(param_name)
                if value is not None:
                    lines.append(f"{param_name}    {value}")

        # Extract parameters from spindown components
        for comp in model.components.values():
            if not (hasattr(comp, "category") and comp.category == "spindown"):
                continue
            if not hasattr(comp, "params"):
                continue

            for param_name in comp.params:
                value = get_param_value(param_name)
                if value is not None:
                    lines.append(f"{param_name}    {value}")

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

    def _find_timfile(self, parfile_path: Path, config: Dict) -> Path:
        """Find corresponding tim file for a par file using PINT-based approach."""
        # Extract pulsar name from PINT model
        pulsar_name = self._extract_pulsar_name_from_pint_model(parfile_path)

        # Find tim file using simple string matching
        return self._find_timfile_by_name(pulsar_name, config)

    def discover_files(
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
        # Avoid recursion by using a cached coordinate map if available
        if hasattr(self, "_cached_coordinate_map"):
            coordinate_map = self._cached_coordinate_map
        else:
            coordinate_map = self._discover_pulsars_by_coordinates(pta_configs)
            self._cached_coordinate_map = coordinate_map

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

    def _discover_pulsars_in_pta(self, config: Dict) -> List[str]:
        """Discover all pulsars in a single PTA using PINT models.

        Args:
            config: PTA configuration to search

        Returns:
            List of pulsar names found in the PTA
        """
        base_path = Path(config["base_dir"])
        if not base_path.exists():
            return []

        pulsars = set()

        # Use regex only for initial file discovery (this is the ONLY place regex should be used)
        try:
            regex = re.compile(config["par_pattern"])
        except re.error as e:
            self.logger.error(f"Invalid regex pattern '{config['par_pattern']}': {e}")
            return []

        for file_path in base_path.rglob("*.par"):
            if regex.search(str(file_path)):  # Only check if file matches pattern
                try:
                    # Extract pulsar name from PINT model (no regex!)
                    pulsar_name = self._extract_pulsar_name_from_pint_model(file_path)
                    pulsars.add(pulsar_name)
                except Exception as e:
                    self.logger.warning(
                        f"Failed to extract pulsar name from {file_path}: {e}"
                    )

        return list(pulsars)
