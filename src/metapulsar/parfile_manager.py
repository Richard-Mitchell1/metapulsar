"""ParFile Manager for Multi-PTA Pulsar Data Combination.

This module provides functionality for managing par files across multiple PTAs,
including making astrophysical parameters consistent and handling unit conversions.
"""

from typing import Dict, List, Optional, Tuple, Union
from pathlib import Path
import tempfile
import subprocess
from io import StringIO
from loguru import logger

# Import PINT for par file parsing and unit conversion
try:
    from pint.models.model_builder import parse_parfile
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

    def write_consistent_parfiles(
        self,
        pulsar_name: str,
        pta_names: List[str] = None,
        reference_pta: str = None,
        combine_components: List[str] = [
            "astrometry",
            "spindown",
            "binary",
            "dispersion",
        ],
        add_dm_derivatives: bool = True,
        output_dir: Path = None,
    ) -> Dict[str, Path]:
        """Make par files consistent by aligning astrophysical parameters

        Args:
            pulsar_name: Name of the pulsar
            pta_names: List of PTA names to include. If None, uses all available.
            reference_pta: PTA to use as reference. If None, auto-selects.
            combine_components: List of components to make consistent:
                ['spindown', 'astrometry', 'binary', 'dispersion']. Defaults to all components.
            add_dm_derivatives: Whether to ensure DM1, DM2 are present in all par files.
                If True: Add DM1, DM2 if missing, align values if present.
                If False: Do not add DM parameters, but align existing DM1, DM2 to reference PTA.
                Note: Only effective when 'dispersion' is in combine_components. Otherwise, a warning is issued.
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

        # 2. Validate reference_pta exists in discovered data, fallback to auto-selection if not
        if reference_pta is None:
            reference_pta = self._select_reference_pta(parfile_paths)
            self.logger.info(f"Auto-selected reference PTA: {reference_pta}")
        elif reference_pta not in parfile_paths:
            self.logger.warning(
                f"Requested reference PTA '{reference_pta}' not found in discovered data. "
                f"Available PTAs: {list(parfile_paths.keys())}. Auto-selecting reference PTA."
            )
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
        """Discover par files using coordinate-based discovery.

        Uses coordinate-based discovery to find par files for a pulsar across PTAs.
        This ensures consistency with the project's coordinate-based pulsar matching approach.
        """
        if pta_names is None:
            pta_configs = self.registry.configs
        else:
            pta_configs = self.registry.get_pta_subset(pta_names)

        # Use coordinate-based discovery to find files
        from .metapulsar_factory import MetaPulsarFactory

        factory = MetaPulsarFactory(self.registry)
        file_pairs = factory.discover_files(pulsar_name, pta_configs)

        # Extract just the par files from the file pairs
        parfiles = {}
        for pta_name, (parfile, timfile) in file_pairs.items():
            parfiles[pta_name] = parfile

        return parfiles

    def _find_file(
        self, pulsar_name: str, base_dir: str, pattern: str
    ) -> Optional[Path]:
        """Find a file matching the pattern in the base directory.

        Uses exact regex matching like the legacy implementation.

        Args:
            pulsar_name: Name of the pulsar to search for
            base_dir: Base directory to search in
            pattern: Regex pattern to match against (includes directory structure)

        Returns:
            Path to the matching file, or None if not found
        """
        import re
        import glob
        import os

        base_path = Path(base_dir)
        if not base_path.exists():
            return None

        # Use recursive glob to find all files, then match with exact regex
        # This matches the legacy implementation approach
        files = glob.glob(f"{base_dir}/**/*", recursive=True)
        regex = re.compile(pattern)

        for file_path in files:
            if os.path.isfile(file_path) and regex.search(file_path):
                # Check if this file matches the pulsar name
                pulsar_name_match = re.search(pattern, file_path)
                if pulsar_name_match and pulsar_name_match.group(1) == pulsar_name:
                    return Path(file_path)

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
             * If add_dm_derivatives=True but 'dispersion' not in combine_components: Issue warning and ignore
             * If add_dm_derivatives=True and 'dispersion' in combine_components: Proceed with DM derivative handling
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

        # Parse all par files
        parfile_dicts = {}
        for pta_name, parfile_content in parfile_data.items():
            try:
                parfile_dict = parse_parfile(StringIO(parfile_content))
                parfile_dicts[pta_name] = parfile_dict
            except Exception as e:
                self.logger.error(f"Error parsing par file for PTA {pta_name}: {e}")
                raise RuntimeError(
                    f"Failed to parse par file for PTA {pta_name}"
                ) from e

        # Get reference PTA parameters
        reference_dict = parfile_dicts[reference_pta]

        # Pre-compute component parameters for ALL components (using clean dictionaries)
        component_params_map = {}
        for component in combine_components:
            from .pint_helpers import get_parameters_by_type_from_parfiles

            component_params_map[component] = get_parameters_by_type_from_parfiles(
                component, parfile_dicts
            )

        # Pre-compute DMX parameters for ALL PTAs (using clean dictionaries)
        dmx_params_map = {}
        for pta_name, parfile_dict in parfile_dicts.items():
            dmx_params_map[pta_name] = self._get_dmx_parameters_from_parfile(
                parfile_dict
            )

        # Process each component
        for component in combine_components:
            self.logger.info(f"Making {component} parameters consistent")

            # Always call standard component consistency logic first
            self._make_component_parameters_consistent(
                parfile_dicts,
                reference_dict,
                reference_pta,
                component,
                component_params_map[component],
            )

            # For dispersion, also apply special DM logic
            if component == "dispersion":
                self._handle_dm_special_cases(
                    parfile_dicts, reference_dict, add_dm_derivatives, dmx_params_map
                )

        # Convert back to par file strings
        consistent_parfiles = {}
        for pta_name, parfile_dict in parfile_dicts.items():
            try:
                consistent_content = self._dict_to_parfile_string(parfile_dict)
                consistent_parfiles[pta_name] = consistent_content
                self.logger.debug(f"Converted PTA {pta_name} par file back to string")
            except Exception as e:
                self.logger.error(f"Error converting par file for PTA {pta_name}: {e}")
                raise RuntimeError(
                    f"Failed to convert par file for PTA {pta_name}"
                ) from e

        return consistent_parfiles

    def _make_component_parameters_consistent(
        self,
        parfile_dicts: Dict[str, Dict],
        reference_dict: Dict,
        reference_pta: str,
        component: str,
        component_params: List[str],
    ) -> None:
        """Make parameters for a specific component consistent.

        Args:
            parfile_dicts: Dictionary mapping PTA names to parsed par file dictionaries
            reference_dict: Reference PTA par file dictionary
            reference_pta: Name of the reference PTA
            component: Component name ('spindown', 'astrometry', 'binary')
            component_params: Pre-computed component parameters
        """
        # If no parameters to process, nothing to do
        if not component_params:
            self.logger.debug(
                f"No parameters found for component {component}, skipping"
            )
            return

        # Extract reference values
        reference_values = {}
        for param in component_params:
            if param in reference_dict:
                reference_values[param] = reference_dict[param]

        # Apply to all PTAs
        for pta_name, parfile_dict in parfile_dicts.items():
            if pta_name == reference_pta:
                continue  # Skip reference PTA

            # Remove ALL existing parameters for this component (regardless of coordinate system)
            # This includes both equatorial and ecliptic parameters
            for param in component_params:
                if param in parfile_dict:
                    parfile_dict.pop(param)

            # Add reference values (simple copy - no conversion)
            # Only add parameters that exist in the reference PTA
            for param, value in reference_values.items():
                parfile_dict[param] = value

    def _handle_dm_special_cases(
        self,
        parfile_dicts: Dict[str, Dict],
        reference_dict: Dict,
        add_dm_derivatives: bool,
        dmx_params_map: Dict[str, List[str]],
    ) -> None:
        """Handle DM-specific special cases: DMX removal, DMEPOCH, DM1/DM2 derivatives."""

        # Handle DMEPOCH explicitly - always add to all PTAs
        reference_dmepoch = reference_dict.get("DMEPOCH", [["55000"]])[0]
        if isinstance(reference_dmepoch, list):
            reference_dmepoch = reference_dmepoch[0]
        else:
            reference_dmepoch = reference_dmepoch.split()[0]
        self.logger.debug(f"Reference DMEPOCH: {reference_dmepoch}")

        # Process each PTA (including reference PTA)
        for pta_name, parfile_dict in parfile_dicts.items():
            # Remove DMX parameters using pre-computed list
            dmx_params = dmx_params_map[pta_name]
            for dmx_param in dmx_params:
                old_value = parfile_dict[dmx_param]
                parfile_dict.pop(dmx_param)
                self.logger.debug(f"PTA {pta_name}: Removed {dmx_param} = {old_value}")

            # Set DMEPOCH for ALL PTAs (always add, matching old logic)
            parfile_dict["DMEPOCH"] = [[f"{reference_dmepoch}", "0"]]  # 0 = frozen
            self.logger.debug(
                f"PTA {pta_name}: Set DMEPOCH = {reference_dmepoch} (frozen)"
            )

            # Handle DM derivatives based on add_dm_derivatives flag
            if add_dm_derivatives:
                # ALWAYS add DM1 and DM2 (matching legacy behavior)
                parfile_dict["DM1"] = [["0.0", "1"]]
                parfile_dict["DM2"] = [["0.0", "1"]]
                self.logger.info(f"PTA {pta_name}: Set DM1 = 0.0, DM2 = 0.0")

    def _create_minimal_parfile_for_component(
        self, parfile_dict: Dict, component: Union[str, List[str]]
    ) -> str:
        """Create minimal parfile for specific component(s) using PINT's component detection.

        Args:
            parfile_dict: Parsed parfile dictionary (from parse_parfile)
            component: Component name ('astrometry', 'spindown', 'binary', 'dispersion')
                      or list of component names. Note: 'spindown' is always included
                      regardless of input, as PINT requires spindown parameters.

        Returns:
            Minimal parfile string with only essential parameters for the component(s)
        """
        from .pint_helpers import create_pint_model

        # Create PINT model directly from dictionary - NO CONVERSION!
        model = create_pint_model(parfile_dict)

        lines = []

        # Helper function to safely get parameter value
        def get_param_value(param_name):
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

        # Handle both single component and list of components
        components_to_process = [component] if isinstance(component, str) else component

        # CRITICAL: Always include spindown component as PINT requires it
        if "spindown" not in components_to_process:
            components_to_process.append("spindown")

        # Extract parameters from the specific component(s)
        from .pint_helpers import get_category_mapping_from_pint

        category_mapping = get_category_mapping_from_pint()

        # Keep track of processed parameters to avoid duplicates
        processed_params = set()

        for comp_name in components_to_process:
            target_category = category_mapping[comp_name]

            for comp in model.components.values():
                if not (hasattr(comp, "category") and comp.category == target_category):
                    continue
                if not hasattr(comp, "params"):
                    continue

                for param_name in comp.params:
                    # Only add if not already processed (avoid duplicates)
                    if param_name not in processed_params:
                        value = get_param_value(param_name)
                        if value is not None:
                            lines.append(f"{param_name}    {value}")
                            processed_params.add(param_name)

        return "\n".join(lines) + "\n"

    def _get_dmx_parameters_from_parfile(self, parfile_dict: Dict) -> List[str]:
        """Get DMX parameters from a parfile using PINT component discovery."""
        from .pint_helpers import create_pint_model

        # Create PINT model directly from dictionary - NO CONVERSION!
        model = create_pint_model(parfile_dict)

        # Find DMX parameters from dispersion_dmx component
        dmx_params = []
        for comp in model.components.values():
            if hasattr(comp, "category") and comp.category == "dispersion_dmx":
                if hasattr(comp, "params"):
                    dmx_params.extend(comp.params)

        return dmx_params

    def _dict_to_parfile_string(self, parfile_dict: Dict) -> str:
        """Convert par file dictionary back to string format.

        Uses PINT's as_parfile() method when possible, falls back to custom implementation.

        Args:
            parfile_dict: Parsed par file dictionary

        Returns:
            Par file content as string
        """
        try:
            # Try to use PINT's as_parfile() method
            # First convert dict back to string format, then create model
            temp_content = self._dict_to_parfile_string_custom(parfile_dict)

            # Create PINT model from string
            from .pint_helpers import create_pint_model

            model = create_pint_model(temp_content)

            # Use PINT's as_parfile() method
            return model.as_parfile()

        except Exception:
            return self._dict_to_parfile_string_custom(parfile_dict)

    def _dict_to_parfile_string_custom(self, parfile_dict: Dict) -> str:
        """Custom implementation for converting par file dictionary to string.

        Args:
            parfile_dict: Parsed par file dictionary

        Returns:
            Par file content as string
        """
        lines = []
        for param_name, param_values in parfile_dict.items():
            for param_value in param_values:
                if isinstance(param_value, list):
                    # Handle list format: [value, error]
                    value_str = " ".join(str(v) for v in param_value)
                else:
                    # Handle string format
                    value_str = str(param_value)
                lines.append(f"{param_name}    {value_str}")

        return "\n".join(lines) + "\n"

    def _determine_parfile_units(
        self, parfile_paths: Dict[str, Path]
    ) -> Tuple[Dict[str, str], Dict[str, str]]:
        """Determine the units of all par files for this pulsar.

        Args:
            parfile_paths: Dictionary mapping PTA names to par file paths

        Returns:
            Tuple of (file_units, parfile_contents) where:
            - file_units: Dictionary mapping PTA names to unit strings (TDB/TCB)
            - parfile_contents: Dictionary mapping PTA names to par file content strings

        Raises:
            RuntimeError: If any par file cannot be read or parsed
        """
        self.logger.info("Determining units for all par files")

        file_units = {}
        parfile_contents = {}

        for pta_name, parfile_path in parfile_paths.items():
            try:
                # Read par file content
                with open(parfile_path, "r") as f:
                    parfile_content = f.read()

                # Parse to check current units
                parfile_dict = parse_parfile(StringIO(parfile_content))
                current_units = parfile_dict.get("UNITS", ["TDB"])[0].upper()

                file_units[pta_name] = current_units
                parfile_contents[pta_name] = parfile_content

            except Exception as e:
                self.logger.error(f"Error reading par file for PTA {pta_name}: {e}")
                raise RuntimeError(f"Failed to read par file for PTA {pta_name}") from e

        return file_units, parfile_contents

    def _convert_units_if_needed(
        self, parfile_paths: Dict[str, Path]
    ) -> Dict[str, str]:
        """Convert par files to consistent units (TDB).

        Only converts if units are mixed (some TDB, some TCB).
        If all files have the same units, no conversion is needed.

        Args:
            parfile_paths: Dictionary mapping PTA names to par file paths

        Returns:
            Dictionary mapping PTA names to par file content strings

        Raises:
            RuntimeError: If unit conversion fails
        """
        self.logger.info("Checking if unit conversion is needed")

        # Determine units for all par files
        file_units, parfile_contents = self._determine_parfile_units(parfile_paths)

        # Check if all units are the same
        unique_units = set(file_units.values())
        if len(unique_units) == 1:
            # All files have the same units, no conversion needed
            self.logger.info(
                f"All par files have {list(unique_units)[0]} units. No conversion needed."
            )
            return parfile_contents

        # Mixed units detected, conversion needed
        self.logger.info(
            f"Mixed units detected: {unique_units}. Converting TCB files to TDB."
        )
        return self._convert_mixed_units(file_units, parfile_contents)

    def _convert_mixed_units(
        self, file_units: Dict[str, str], parfile_contents: Dict[str, str]
    ) -> Dict[str, str]:
        """Convert par files with mixed units to consistent TDB units.

        Args:
            file_units: Dictionary mapping PTA names to unit strings
            parfile_contents: Dictionary mapping PTA names to par file content strings

        Returns:
            Dictionary mapping PTA names to converted par file content strings

        Raises:
            RuntimeError: If unit conversion fails
        """
        converted_parfiles = {}

        for pta_name, parfile_content in parfile_contents.items():
            current_units = file_units[pta_name]

            if current_units == "TDB":
                # Already in TDB, no conversion needed
                converted_parfiles[pta_name] = parfile_content
            else:
                # Convert to TDB
                try:
                    # Get PTA configuration to determine timing package
                    pta_config = self.registry.get_pta(pta_name)
                    timing_package = pta_config.get("timing_package", "pint")

                    if timing_package in ["tempo2", "libstempo"]:
                        # Use tempo2 subprocess for conversion
                        converted_content = self._convert_tempo2_to_tdb(parfile_content)
                    else:
                        # Use PINT ModelBuilder for conversion
                        converted_content = self._convert_pint_to_tdb(parfile_content)

                    converted_parfiles[pta_name] = converted_content

                except Exception as e:
                    self.logger.error(f"Error converting units for PTA {pta_name}: {e}")
                    raise RuntimeError(
                        f"Unit conversion failed for PTA {pta_name}"
                    ) from e

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
            # Create PINT model and parse par file
            from .pint_helpers import create_pint_model

            model = create_pint_model(parfile_content)

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
