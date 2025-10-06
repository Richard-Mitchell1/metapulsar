"""Meta-Pulsar Factory for creating MetaPulsars by orchestrating Enterprise Pulsar creation.

This module provides a factory class that creates MetaPulsars by discovering files,
creating Enterprise Pulsars, and wrapping them with metadata.
"""

from typing import Dict, List, Tuple, Optional, Any
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

# Import MetaPulsar and ParameterManager
from .metapulsar import MetaPulsar
from .parameter_manager import ParameterManager
from .position_helpers import discover_pulsars_by_coordinates_optimized

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

# PTARegistry removed - file discovery handled by FileDiscoveryService


class MetaPulsarFactory:
    """Factory for creating MetaPulsars by orchestrating Enterprise Pulsar creation.

    This class provides methods to discover files, create Enterprise Pulsars,
    and wrap them in MetaPulsar objects with appropriate metadata.

    """

    def __init__(self):
        """Initialize the MetaPulsar factory.

        Note: File discovery should be handled separately using FileDiscoveryService.
        This factory only handles object creation from provided file paths.
        """
        self.logger = logger
        # ParameterManager will be instantiated as needed in methods

    def create_metapulsar(
        self,
        file_data: Dict[
            str, List[Dict[str, Any]]
        ],  # Should contain data for single pulsar only
        combination_strategy: str = "consistent",
        reference_pta: str = None,
        combine_components: List[str] = [
            "astrometry",
            "spindown",
            "binary",
            "dispersion",
        ],
        add_dm_derivatives: bool = True,
    ) -> MetaPulsar:
        """Create MetaPulsar using specified combination strategy.

        Args:
            file_data: File data from FileDiscoveryService (should contain data for single pulsar only)
            combination_strategy: Strategy for combining PTAs:
                - "consistent": Astrophysical consistency (modifies par files for consistency, the default)
                - "composite": Multi-PTA composition (preserves original parameters, Borg/FrankenStat methods)
            reference_pta: PTA to use as reference (for consistent strategy)
            combine_components: List of components to make consistent (for consistent strategy).
                Defaults to all components: ["astrometry", "spindown", "binary", "dispersion"]
            add_dm_derivatives: Whether to ensure DM1, DM2 are present in all par files (for consistent strategy)

        Returns:
            MetaPulsar object

        Raises:
            ValueError: If no files found, multiple pulsars detected, or invalid parameters
            RuntimeError: If Enterprise Pulsar creation fails
        """
        self.logger.info(f"Creating MetaPulsar using {combination_strategy} strategy")

        # VALIDATION: Check that all files belong to the same pulsar
        self._validate_single_pulsar_data(file_data)

        return self.create_metapulsar_from_file_data(
            file_data,
            combination_strategy,
            reference_pta,
            combine_components,
            add_dm_derivatives,
        )

    def _validate_single_pulsar_data(
        self, file_data: Dict[str, List[Dict[str, Any]]]
    ) -> None:
        """Validate that file_data contains files for only one pulsar.

        Args:
            file_data: File data to validate

        Raises:
            ValueError: If multiple pulsars detected or no valid files found
        """
        # Group files by pulsar using coordinate-based identification
        pulsar_groups = discover_pulsars_by_coordinates_optimized(file_data)

        if not pulsar_groups:
            raise ValueError("No valid pulsar files found in file_data")

        if len(pulsar_groups) > 1:
            pulsar_names = list(pulsar_groups.keys())
            raise ValueError(
                f"Multiple pulsars detected in file_data: {pulsar_names}. "
                f"create_metapulsar() expects data for a single pulsar. "
                f"Use create_all_metapulsars() for multiple pulsars or "
                f"group_files_by_pulsar() to separate the data first."
            )

        # Log the single pulsar being processed
        pulsar_name = list(pulsar_groups.keys())[0]
        self.logger.info(f"Validated single pulsar data for: {pulsar_name}")

    def group_files_by_pulsar(
        self, file_data: Dict[str, List[Dict[str, Any]]]
    ) -> Dict[str, Dict[str, List[Dict[str, Any]]]]:
        """Group file data by pulsar using coordinate-based identification.

        This utility function takes multi-pulsar file data and groups it by pulsar,
        making it suitable for creating individual MetaPulsars.

        Args:
            file_data: File data from FileDiscoveryService containing multiple pulsars

        Returns:
            Dictionary mapping pulsar names to their respective file data:
            {
                "J1857+0943": {
                    "epta_dr2": [file_dict1, file_dict2, ...],
                    "ppta_dr2": [file_dict3, file_dict4, ...]
                },
                "J1909-3744": {
                    "epta_dr2": [file_dict5, ...],
                    "ppta_dr2": [file_dict6, ...]
                }
            }

        Raises:
            ValueError: If no valid pulsar files found
        """
        self.logger.info(
            "Grouping files by pulsar using coordinate-based identification"
        )

        pulsar_groups = discover_pulsars_by_coordinates_optimized(file_data)

        if not pulsar_groups:
            raise ValueError("No valid pulsar files found in file_data")

        self.logger.info(
            f"Found {len(pulsar_groups)} pulsars: {list(pulsar_groups.keys())}"
        )

        return pulsar_groups

    def list_available_pulsars(self, pta_names: List[str] = None) -> List[str]:
        """List all available pulsars across specified PTAs.

        Args:
            pta_names: List of PTA names to search. If None, searches all PTAs.

        Returns:
            List of pulsar names found across all specified PTAs
        """
        return self.discover_available_pulsars(pta_names)

    def create_metapulsar_from_file_data(
        self,
        file_data: Dict[str, List[Dict[str, Any]]],  # File data format
        combination_strategy: str = "consistent",
        reference_pta: str = None,
        combine_components: List[str] = [
            "astrometry",
            "spindown",
            "binary",
            "dispersion",
        ],
        add_dm_derivatives: bool = True,
    ) -> MetaPulsar:
        """Create MetaPulsar using specified combination strategy.

        Args:
            file_data: File data from FileDiscoveryService
            combination_strategy: "composite" or "consistent"
            reference_pta: PTA to use as reference (for consistent strategy)
            combine_components: List of components to make consistent (for consistent strategy)
                          Defaults to all components
            add_dm_derivatives: Whether to ensure DM1, DM2 are present (for consistent strategy)
        """
        # Convert file data to single file per PTA format
        single_file_data = {}
        for pta_name, file_list in file_data.items():
            if not file_list:
                raise ValueError(f"No files found for PTA {pta_name}")
            single_file_data[pta_name] = file_list[0]  # Take first file

        # Create file_pairs from the file data
        file_pairs = {
            pta: (file_dict["par"], file_dict["tim"])
            for pta, file_dict in single_file_data.items()
        }

        # Process par files if consistent strategy
        if combination_strategy == "consistent":
            # Create ParameterManager for parfile consistency
            parameter_manager = ParameterManager(
                file_data=single_file_data,
                reference_pta=reference_pta,
                combine_components=combine_components,
                add_dm_derivatives=add_dm_derivatives,
            )

            # Make par files consistent
            consistent_parfiles = parameter_manager.make_parfiles_consistent()

            # Update file_pairs with consistent par files
            file_pairs = {
                pta: (consistent_parfiles[pta], single_file_data[pta]["tim"])
                for pta in single_file_data.keys()
                if pta in consistent_parfiles
            }

        # Create PINT/Tempo2 objects from file pairs using file data
        pulsars = self._create_pulsar_objects(file_pairs, single_file_data)

        # Create MetaPulsar with new constructor pattern
        # Canonical name is automatically calculated from pulsar data
        return MetaPulsar(
            pulsars=pulsars,
            combination_strategy=combination_strategy,
            combine_components=combine_components,
            add_dm_derivatives=add_dm_derivatives,
        )

    def create_all_metapulsars(
        self,
        file_data: Dict[str, List[Dict[str, Any]]],
        combination_strategy: str = "consistent",
        reference_pta: str = None,
        combine_components: List[str] = [
            "astrometry",
            "spindown",
            "binary",
            "dispersion",
        ],
        add_dm_derivatives: bool = True,
    ) -> Dict[str, MetaPulsar]:
        """Create MetaPulsars for all available pulsars using file data.

        Args:
            file_data: File data from FileDiscoveryService
            combination_strategy: Strategy for combining PTAs
            reference_pta: PTA to use as reference (for consistent strategy)
            combine_components: List of components to make consistent
            add_dm_derivatives: Whether to ensure DM1, DM2 are present

        Returns:
            Dictionary mapping pulsar names to MetaPulsar objects
        """
        # Group files by pulsar using coordinate-based identification
        pulsar_groups = discover_pulsars_by_coordinates_optimized(file_data)

        metapulsars = {}

        self.logger.info(f"Creating MetaPulsars for {len(pulsar_groups)} pulsars")

        for pulsar_name, pulsar_file_data in pulsar_groups.items():
            try:
                # Create MetaPulsar for this pulsar
                metapulsar = self.create_metapulsar_from_file_data(
                    file_data=pulsar_file_data,
                    combination_strategy=combination_strategy,
                    reference_pta=reference_pta,
                    combine_components=combine_components,
                    add_dm_derivatives=add_dm_derivatives,
                )

                # Canonical name is automatically calculated from pulsar data
                metapulsars[pulsar_name] = metapulsar

            except Exception as e:
                self.logger.warning(
                    f"Failed to create MetaPulsar for {pulsar_name}: {e}"
                )

        self.logger.info(f"Successfully created {len(metapulsars)} MetaPulsars")
        return metapulsars

    def _create_pulsar_objects(
        self,
        file_pairs: Dict[str, Tuple[Path, Path]],
        file_data: Dict[str, Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Create PINT/Tempo2 objects from file pairs using file data.

        Args:
            file_pairs: Dictionary mapping PTA names to (parfile, timfile) tuples
            file_data: Dictionary mapping PTA names to file dictionaries
                      Contains timing_package info from FileDiscoveryService

        Returns:
            Dictionary mapping PTA names to PINT/Tempo2 objects
        """
        pulsar_objects = {}

        for pta_name, (parfile, timfile) in file_pairs.items():
            # Get timing package info from file data
            timing_package = file_data[pta_name]["timing_package"]

            try:
                if timing_package == "pint":
                    # Create PINT objects
                    if get_model_and_toas is None:
                        raise RuntimeError("PINT not available for PINT creation")

                    model, toas = get_model_and_toas(
                        str(parfile), str(timfile), planets=True
                    )
                    pulsar_objects[pta_name] = (model, toas)

                else:  # tempo2
                    # Create Tempo2 object
                    if t2 is None:
                        raise RuntimeError(
                            "libstempo not available for Tempo2 creation"
                        )

                    t2_psr = t2.tempopulsar(str(parfile), str(timfile))
                    pulsar_objects[pta_name] = t2_psr

                self.logger.debug(f"Created {timing_package} object for {pta_name}")

            except Exception as e:
                self.logger.error(f"Failed to create pulsar for {pta_name}: {e}")
                raise RuntimeError(f"Failed to create pulsar for {pta_name}: {e}")

        return pulsar_objects

    def _create_parfile_dicts_from_files(
        self, parfile_files: Dict[str, Path]
    ) -> Dict[str, Dict]:
        """Create parfile dictionaries from parfile files."""
        from .pint_helpers import create_pint_model

        parfile_dicts = {}
        for pta_name, parfile_path in parfile_files.items():
            with open(parfile_path, "r") as f:
                parfile_content = f.read()
            # Use our consolidated function that handles string content properly
            model = create_pint_model(parfile_content)
            # Convert model back to dictionary format
            parfile_dicts[pta_name] = model.get_params_dict()

        return parfile_dicts

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

    def _create_raw_pulsars(
        self,
        file_pairs: Dict[str, Tuple[Path, Path]],
        pta_data_releases: Dict[str, Dict],
    ) -> Dict[str, Any]:
        """Create raw PINT/Tempo2 objects from file pairs.

        Args:
            file_pairs: Dictionary mapping PTA names to (parfile, timfile) tuples
            pta_data_releases: Dictionary of PTA data releases

        Returns:
            Dictionary mapping PTA names to raw PINT/Tempo2 objects

        Raises:
            RuntimeError: If raw pulsar creation fails
        """
        raw_pulsars = {}

        for pta_name, (parfile, timfile) in file_pairs.items():
            data_release = pta_data_releases[pta_name]

            try:
                if data_release["timing_package"] == "pint":
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
                    f"Created raw {data_release['timing_package']} object for {pta_name}"
                )

            except Exception as e:
                self.logger.error(f"Failed to create raw pulsar for {pta_name}: {e}")
                raise RuntimeError(f"Failed to create raw pulsar for {pta_name}: {e}")

        return raw_pulsars

    def _create_minimal_parfile_for_coordinates(self, parfile_content: str) -> str:
        """Create minimal parfile for coordinate discovery using ParameterManager."""
        # Parse into dictionary using PINT
        from pint.models.model_builder import parse_parfile
        from io import StringIO

        parfile_dict = parse_parfile(StringIO(parfile_content))

        # Create ParameterManager with pre-read content (no temp files needed!)
        temp_file_data = {
            "temp": {"par_content": parfile_content, "timespan_days": 1000.0}
        }
        temp_manager = ParameterManager(temp_file_data)

        # Use ParameterManager's component extraction method
        return temp_manager._create_minimal_parfile_for_component(
            parfile_dict, "astrometry"
        )

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

    def _build_metadata(
        self,
        file_pairs: Dict[str, Tuple[Path, Path]],
        pta_data_releases: Dict[str, Dict],
    ) -> Dict[str, Any]:
        """Build metadata for the MetaPulsar.

        Args:
            file_pairs: Dictionary mapping PTA names to (parfile, timfile) tuples
            pta_data_releases: Dictionary of PTA data releases

        Returns:
            Dictionary containing metadata
        """
        return {
            "file_pairs": {
                pta: (str(par), str(tim)) for pta, (par, tim) in file_pairs.items()
            },
            "timing_packages": {
                pta: data_release["timing_package"]
                for pta, data_release in pta_data_releases.items()
            },
            "creation_timestamp": datetime.now().isoformat(),
        }

    def _discover_pulsars_in_pta(self, data_release: Dict) -> List[str]:
        """Discover all pulsars in a single PTA using PINT models.

        Args:
            data_release: PTA data release to search

        Returns:
            List of pulsar names found in the PTA
        """
        base_path = Path(data_release["base_dir"])
        if not base_path.exists():
            return []

        pulsars = set()

        # Use regex only for initial file discovery (this is the ONLY place regex should be used)
        try:
            regex = re.compile(data_release["par_pattern"])
        except re.error as e:
            self.logger.error(
                f"Invalid regex pattern '{data_release['par_pattern']}': {e}"
            )
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
