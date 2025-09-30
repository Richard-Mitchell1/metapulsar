"""ParFile Manager for Multi-PTA Pulsar Data Combination.

This module provides functionality for managing par files across multiple PTAs,
including making astrophysical parameters consistent and handling unit conversions.
"""

from typing import Dict, List, Optional
from pathlib import Path
import tempfile
import subprocess
from io import StringIO
from loguru import logger

# Import PINT for par file parsing and unit conversion
try:
    from pint.models.model_builder import parse_parfile, ModelBuilder
    from pint.toa import TOAs
except ImportError as e:
    logger.error("PINT is required but not available. Please install pint-pulsar.")
    raise ImportError("PINT is required for par file operations") from e

# Import libstempo for tempo2 operations
try:
    import libstempo  # noqa: F401
except ImportError as e:
    logger.error("libstempo is required but not available. Please install libstempo.")
    raise ImportError("libstempo is required for tempo2 operations") from e

from .pta_registry import PTARegistry


class ParFileManager:
    """Manages par file operations for multi-PTA pulsar data combination."""

    def __init__(self, registry: PTARegistry = None):
        """Initialize ParFile Manager.

        Args:
            registry: PTARegistry instance to use. If None, creates a new one.
        """
        self.registry = registry or PTARegistry()
        self.logger = logger

    def make_parfiles_consistent(
        self,
        pulsar_name: str,
        pta_names: List[str] = None,
        reference_pta: str = None,
        combine_components: List[str] = None,
        add_dm_derivatives: bool = True,
        output_dir: Path = None,
    ) -> Dict[str, Path]:
        """Make par files consistent by aligning astrophysical parameters

        Args:
            pulsar_name: Name of the pulsar
            pta_names: List of PTA names to include. If None, uses all available.
            reference_pta: PTA to use as reference. If None, auto-selects.
            combine_components: List of components to make consistent:
                ['spin', 'astrometry', 'binary', 'dm']. If None, makes all consistent.
            add_dm_derivatives: Whether to ensure DM1, DM2 are present in all par files.
                If True: Add DM1, DM2 if missing, align values if present.
                If False: Do not add DM parameters, but align existing DM1, DM2 to reference PTA.
                Note: Only effective when 'dm' is in combine_components. Otherwise, a warning is issued.
            output_dir: Directory to save consistent par files. If None, uses temp dir.
                Output files are named as: f"{pulsar_name}_{pta_name}.par"

        Returns:
            Dictionary mapping PTA names to consistent par file paths

        Raises:
            ImportError: If required dependencies (PINT, libstempo) are not available when needed
            FileNotFoundError: If par files cannot be found for specified pulsar/PTAs
            ValueError: If invalid parameters or PTA configurations are provided
            RuntimeError: If unit conversion or parameter consistency operations fail
        """
        self.logger.info(f"Making par files consistent for pulsar {pulsar_name}")

        # 1. Discover par files using existing PTARegistry functionality
        parfile_paths = self._discover_parfiles(pulsar_name, pta_names)
        if not parfile_paths:
            raise FileNotFoundError(f"No par files found for pulsar {pulsar_name}")

        # 2. If reference_pta is None, auto-select using _select_reference_pta()
        if reference_pta is None:
            reference_pta = self._select_reference_pta(parfile_paths)
            self.logger.info(f"Auto-selected reference PTA: {reference_pta}")

        # 3. Convert units if needed using _convert_units_if_needed()
        converted_parfiles = self._convert_units_if_needed(parfile_paths)

        # 4. Make parameters consistent using _make_parameters_consistent()
        consistent_parfiles = self._make_parameters_consistent(
            converted_parfiles, reference_pta, combine_components, add_dm_derivatives
        )

        # 5. Write consistent par files to output directory
        output_files = self._write_consistent_parfiles(
            consistent_parfiles, pulsar_name, output_dir
        )

        self.logger.info(
            f"Successfully created {len(output_files)} consistent par files"
        )
        return output_files

    def _discover_parfiles(
        self, pulsar_name: str, pta_names: List[str] = None
    ) -> Dict[str, Path]:
        """Discover par files using existing PTARegistry functionality.

        Uses the existing PTARegistry and file discovery logic from the current codebase.
        """
        if pta_names is None:
            pta_configs = self.registry.configs
        else:
            pta_configs = self.registry.get_pta_subset(pta_names)

        parfiles = {}
        for pta_name, config in pta_configs.items():
            parfile = self._find_file(
                pulsar_name, config["base_dir"], config["par_pattern"]
            )
            if parfile:
                parfiles[pta_name] = parfile
                self.logger.debug(
                    f"Found par file for {pulsar_name} in {pta_name}: {parfile}"
                )
            else:
                self.logger.debug(f"No par file found for {pulsar_name} in {pta_name}")

        return parfiles

    def _find_file(
        self, pulsar_name: str, base_dir: str, pattern: str
    ) -> Optional[Path]:
        """Find a file matching the pattern in the base directory.

        Args:
            pulsar_name: Name of the pulsar to search for
            base_dir: Base directory to search in
            pattern: Regex pattern to match against

        Returns:
            Path to the matching file, or None if not found
        """
        import re
        import glob

        base_path = Path(base_dir)
        if not base_path.exists():
            return None

        # Convert regex pattern to glob pattern for directory traversal
        # This is a simplified approach - in practice, you might need more sophisticated pattern matching
        search_pattern = str(base_path / "**" / f"*{pulsar_name}*")

        for file_path in glob.glob(search_pattern, recursive=True):
            file_path = Path(file_path)
            if re.search(pattern, str(file_path)):
                return file_path

        return None

    def _select_reference_pta(self, parfile_paths: Dict[str, Path]) -> str:
        """Select reference PTA based on dataset length (longest time span).

        Args:
            parfile_paths: Dictionary mapping PTA names to par file paths

        Returns:
            Name of the PTA with the longest dataset (largest max(toa_mjd) - min(toa_mjd))

        Implementation details:
        1. For each PTA, discover corresponding TIM file using PTARegistry
        2. Parse TIM file using PINT to extract TOA MJD values (see ./ref-packages/PINT/)
        3. Calculate time span: max(toa_mjd) - min(toa_mjd)
        4. Return PTA name with the longest time span
        5. Handle cases where TIM files are missing or invalid
        """
        self.logger.info("Selecting reference PTA based on dataset length")

        timespans = {}
        for pta_name in parfile_paths.keys():
            try:
                timespan = self._calculate_dataset_timespan(
                    pta_name, parfile_paths[pta_name].parent.name
                )
                timespans[pta_name] = timespan
                self.logger.debug(f"PTA {pta_name}: {timespan:.1f} days")
            except Exception as e:
                self.logger.warning(
                    f"Could not calculate timespan for PTA {pta_name}: {e}"
                )
                timespans[pta_name] = 0.0

        if not timespans:
            raise RuntimeError("Could not calculate timespans for any PTA")

        reference_pta = max(timespans, key=timespans.get)
        self.logger.info(
            f"Selected reference PTA: {reference_pta} ({timespans[reference_pta]:.1f} days)"
        )
        return reference_pta

    def _calculate_dataset_timespan(self, pta_name: str, pulsar_name: str) -> float:
        """Calculate the time span of a dataset for a given PTA and pulsar.

        Args:
            pta_name: Name of the PTA
            pulsar_name: Name of the pulsar

        Returns:
            Time span in days (max(toa_mjd) - min(toa_mjd))

        Implementation details:
        1. Use PTARegistry to discover TIM file for the PTA/pulsar combination
        2. Parse TIM file to extract TOA MJD values
        3. Calculate and return time span
        4. Handle parsing errors gracefully
        """
        try:
            # Get PTA configuration
            pta_config = self.registry.get_pta(pta_name)

            # Find TIM file using the same pattern matching as par files
            tim_file_path = self._find_file(
                pulsar_name, pta_config["base_dir"], pta_config["tim_pattern"]
            )

            if tim_file_path is None:
                raise FileNotFoundError(f"No TIM file found for PTA {pta_name}")

            # Parse TIM file using PINT
            toas = TOAs(str(tim_file_path))
            mjd_values = toas.get_mjds().value

            if len(mjd_values) == 0:
                raise ValueError(f"No TOAs found in TIM file for PTA {pta_name}")

            timespan = float(mjd_values.max() - mjd_values.min())
            return timespan

        except Exception as e:
            self.logger.error(f"Error calculating timespan for PTA {pta_name}: {e}")
            raise

    def _make_parameters_consistent(
        self,
        parfile_data: Dict[str, str],
        reference_pta: str,
        combine_components: List[str],
        add_dm_derivatives: bool = True,
    ) -> Dict[str, str]:
        """Make parameters consistent using reference PTA values.

        Implementation details:
        1. Validate dependencies and parameters:
           - Check if PINT is available, raise ImportError if not
           - Check if libstempo is available, raise ImportError if not
           - Validate add_dm_derivatives parameter:
             * If add_dm_derivatives=True but 'dm' not in combine_components: Issue warning and ignore
             * If add_dm_derivatives=True and 'dm' in combine_components: Proceed with DM derivative handling
        2. Parse reference PTA par file to extract parameter values using existing parameter mapping
        3. For each non-reference PTA:
           a. Parse par file using PINT's parse_parfile()
           b. Remove existing parameters that need to be made consistent
           c. Copy parameter values from reference PTA
        4. Special handling for DM parameters:
           - If making DM consistent: Remove all DMX parameters (DMX_001, DMX_002, etc.)
           - If NOT making DM consistent: Keep DMX parameters as-is
           - Keep DM parameter but align its value with reference PTA
           - If add_dm_derivatives=True: Ensure each par file has DM1, DM2 with consistent values
             (use reference PTA values if present, otherwise use 0.0 for both)
           - If add_dm_derivatives=False: Do not add DM parameters, but if reference PTA has DM1, DM2,
             then align all PTAs to match reference PTA values
        5. Handle parameter aliases using existing parameter mapping functionality
        6. Write modified par files back to strings
        7. Log all operations using loguru logger
        """
        self.logger.info(
            f"Making parameters consistent using reference PTA: {reference_pta}"
        )

        # Validate add_dm_derivatives parameter
        if add_dm_derivatives and "dm" not in combine_components:
            self.logger.warning(
                "add_dm_derivatives=True but 'dm' not in combine_components. Ignoring add_dm_derivatives."
            )
            add_dm_derivatives = False

        # Parse reference PTA par file
        # TODO: Use reference_parfile for parameter consistency logic
        # reference_parfile = parfile_data[reference_pta]
        # reference_params = parse_parfile(StringIO(reference_parfile))

        consistent_parfiles = {}

        for pta_name, parfile_content in parfile_data.items():
            if pta_name == reference_pta:
                # Keep reference PTA as-is
                consistent_parfiles[pta_name] = parfile_content
                continue

            self.logger.debug(f"Making parameters consistent for PTA: {pta_name}")

            # Parse current PTA par file
            # TODO: Use current_params for parameter consistency logic
            # current_params = parse_parfile(StringIO(parfile_content))

            # TODO: Implement parameter consistency logic
            # This will be implemented in the next step

            # For now, return the original content
            consistent_parfiles[pta_name] = parfile_content

        return consistent_parfiles

    def _convert_units_if_needed(
        self, parfile_paths: Dict[str, Path]
    ) -> Dict[str, str]:
        """Convert par files to consistent units (TDB).

        Implementation details:
        1. Parse each par file using PINT's parse_parfile()
        2. Check UNITS parameter in each par file
        3. For tempo2/libstempo PTAs: Set UNITS to TCB if not specified
        4. For PINT PTAs: Set UNITS to TDB if not specified
        5. Convert TCB to TDB using appropriate method:
           - PINT files: Use ModelBuilder with allow_tcb=True, and allow_T2=True then write_parfile()
           - Tempo2 files: Use subprocess to call 'tempo2 -gr transform parFile outputFile tdb'
        6. Handle conversion errors with proper logging and exceptions
        7. Return converted par file content as strings
        """
        self.logger.info("Converting par files to consistent units (TDB)")

        converted_parfiles = {}

        for pta_name, parfile_path in parfile_paths.items():
            try:
                # Read par file content
                with open(parfile_path, "r") as f:
                    parfile_content = f.read()

                # Parse to check current units
                parfile_dict = parse_parfile(StringIO(parfile_content))

                # Get PTA configuration to determine timing package
                pta_config = self.registry.get_pta(pta_name)
                timing_package = pta_config.get("timing_package", "pint")

                # Check if conversion is needed
                current_units = parfile_dict.get("UNITS", ["TDB"])[0]

                if current_units.upper() == "TDB":
                    # Already in TDB, no conversion needed
                    converted_parfiles[pta_name] = parfile_content
                    self.logger.debug(f"PTA {pta_name}: Already in TDB units")
                else:
                    # Convert to TDB
                    if timing_package in ["tempo2", "libstempo"]:
                        # Use tempo2 subprocess for conversion
                        converted_content = self._convert_tempo2_to_tdb(parfile_content)
                    else:
                        # Use PINT ModelBuilder for conversion
                        converted_content = self._convert_pint_to_tdb(parfile_content)

                    converted_parfiles[pta_name] = converted_content
                    self.logger.debug(
                        f"PTA {pta_name}: Converted from {current_units} to TDB"
                    )

            except Exception as e:
                self.logger.error(f"Error converting units for PTA {pta_name}: {e}")
                raise RuntimeError(f"Unit conversion failed for PTA {pta_name}") from e

        return converted_parfiles

    def _convert_tempo2_to_tdb(self, parfile_content: str) -> str:
        """Convert par file from TCB to TDB using tempo2 subprocess."""
        with tempfile.NamedTemporaryFile(
            mode="w+", suffix=".par", delete=False
        ) as input_file:
            input_file.write(parfile_content)
            input_file.flush()

            with tempfile.NamedTemporaryFile(
                mode="w+", suffix=".par", delete=False
            ) as output_file:
                try:
                    # Run tempo2 transform command
                    subprocess.run(
                        [
                            "tempo2",
                            "-gr",
                            "transform",
                            input_file.name,
                            output_file.name,
                            "tdb",
                        ],
                        check=True,
                        capture_output=True,
                        text=True,
                    )

                    # Read converted content
                    output_file.seek(0)
                    converted_content = output_file.read()

                    return converted_content

                except subprocess.CalledProcessError as e:
                    raise RuntimeError(f"Tempo2 conversion failed: {e.stderr}") from e
                finally:
                    # Clean up temporary files
                    input_file.close()
                    output_file.close()
                    Path(input_file.name).unlink(missing_ok=True)
                    Path(output_file.name).unlink(missing_ok=True)

    def _convert_pint_to_tdb(self, parfile_content: str) -> str:
        """Convert par file from TCB to TDB using PINT ModelBuilder."""
        try:
            # Create ModelBuilder and parse par file
            mb = ModelBuilder()
            model = mb(StringIO(parfile_content), allow_tcb=True)

            # Write par file with TDB units
            new_file = StringIO()
            model.write_parfile(new_file)

            return new_file.getvalue()

        except Exception as e:
            raise RuntimeError(f"PINT conversion failed: {e}") from e

    def _write_consistent_parfiles(
        self,
        consistent_parfiles: Dict[str, str],
        pulsar_name: str,
        output_dir: Path = None,
    ) -> Dict[str, Path]:
        """Write consistent par files to output directory."""
        if output_dir is None:
            output_dir = Path(
                tempfile.mkdtemp(prefix=f"consistent_parfiles_{pulsar_name}_")
            )

        output_dir.mkdir(parents=True, exist_ok=True)
        output_files = {}

        for pta_name, parfile_content in consistent_parfiles.items():
            output_filename = self._get_output_filename(pulsar_name, pta_name)
            output_path = output_dir / output_filename

            with open(output_path, "w") as f:
                f.write(parfile_content)

            output_files[pta_name] = output_path
            self.logger.debug(f"Written consistent par file: {output_path}")

        return output_files

    def _get_output_filename(self, pulsar_name: str, pta_name: str) -> str:
        """Generate output filename for consistent par file.

        Args:
            pulsar_name: Name of the pulsar
            pta_name: Name of the PTA

        Returns:
            Filename in format: f"{pulsar_name}_{pta_name}.par"
        """
        return f"{pulsar_name}_{pta_name}.par"
