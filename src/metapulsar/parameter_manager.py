"""Unified parameter and par file management for multi-PTA pulsar data.

This module consolidates all parameter management functionality:
- Making par files consistent across PTAs
- Building parameter mappings for MetaPulsar
- Resolving parameter aliases and availability
- Working with both PINT and Tempo2 PTAs
"""

import tempfile
import subprocess
from pathlib import Path
from io import StringIO
from typing import Dict, List, Any, Tuple
import logging

from pint.models.model_builder import parse_parfile
from pint.models.timing_model import TimingModel

from .pint_helpers import (
    get_parameter_aliases_from_pint,
    create_pint_model,
    get_parameters_by_type_from_parfiles,
    check_component_available_in_model,
    get_parameter_identifiability_from_model,
    get_category_mapping_from_pint,
)

logger = logging.getLogger(__name__)


class ParameterManager:
    """Unified parameter and par file management for multi-PTA pulsar data.

    This class consolidates all parameter management functionality:
    - Making par files consistent across PTAs
    - Building parameter mappings for MetaPulsar
    - Resolving parameter aliases and availability
    - Working with both PINT and Tempo2 PTAs
    """

    def __init__(
        self,
        file_data: Dict[str, Dict[str, Any]],  # pta_name -> file data
        reference_pta: str = None,
        combine_components: List[str] = [
            "astrometry",
            "spindown",
            "binary",
            "dispersion",
        ],
        add_dm_derivatives: bool = True,
        output_dir: Path = None,
    ):
        """Initialize with file data and configuration.

        Args:
            file_data: File data from FileDiscoveryService
            reference_pta: PTA to use as reference. If None, auto-selects based on timespan
            combine_components: List of components to make consistent
            add_dm_derivatives: Whether to add DM1, DM2 parameters
            output_dir: Directory for output files
        """
        self.file_data = file_data
        self.combine_components = combine_components
        self.add_dm_derivatives = add_dm_derivatives
        self.output_dir = output_dir

        # Choose reference PTA if not provided
        if reference_pta is None:
            self.reference_pta = self._choose_reference_pta(file_data)
        else:
            self.reference_pta = reference_pta

        self.logger = logger
        self._aliases = get_parameter_aliases_from_pint()
        # Build reverse aliases inline (no separate method needed)
        self._reverse_aliases = {}
        for alias, canonical in self._aliases.items():
            if canonical not in self._reverse_aliases:
                self._reverse_aliases[canonical] = []
            self._reverse_aliases[canonical].append(alias)

    # ===== MAIN PUBLIC METHODS =====

    def make_parfiles_consistent(self) -> Dict[str, Path]:
        """Make par files consistent across PTAs."""
        self.logger.info("Making par files consistent across PTAs")

        # 1. Parse par files into dictionaries
        parfile_dicts = self._parse_parfiles()

        # 2. Convert units if needed
        converted_parfiles = self._convert_units_if_needed(parfile_dicts)

        # 3. Make parameters consistent
        consistent_parfiles = self._make_parameters_consistent(converted_parfiles)

        # 4. Write consistent par files to output directory
        output_files = self._write_consistent_parfiles(consistent_parfiles)

        self.logger.info(
            f"Successfully created {len(output_files)} consistent par files"
        )
        return output_files

    def build_parameter_mappings(self) -> "ParameterMapping":
        """Build parameter mappings for MetaPulsar."""
        self.logger.info("Building parameter mappings for MetaPulsar")

        # 1. Discover parameters for components that should be merged
        mergeable_params = self._discover_mergeable_parameters()

        # 2. Process parameters from all PTAs
        fitparameters, setparameters = self._process_all_pta_parameters(
            mergeable_params
        )

        # 3. Validate consistency
        self._validate_parameter_consistency(fitparameters, setparameters)

        # 4. Build result
        return self._build_parameter_mapping_result(fitparameters, setparameters)

    # ===== PARFILE CONSISTENCY METHODS =====

    def _convert_units_if_needed(
        self, parfile_dicts: Dict[str, Dict]
    ) -> Dict[str, str]:
        """Convert par files to consistent units (TDB)."""
        self.logger.info("Checking if unit conversion is needed")

        # Determine units for all par files
        file_units, parfile_contents = self._determine_parfile_units()

        # Check if all units are the same
        unique_units = set(file_units.values())
        if len(unique_units) == 1:
            self.logger.info(
                f"All par files have {list(unique_units)[0]} units. No conversion needed."
            )
            return parfile_contents

        # Mixed units detected, conversion needed
        self.logger.info(
            f"Mixed units detected: {unique_units}. Converting TCB files to TDB."
        )
        return self._convert_mixed_units(file_units, parfile_contents)

    def _determine_parfile_units(self) -> Tuple[Dict[str, str], Dict[str, str]]:
        """Determine the units of all par files for this pulsar."""
        self.logger.info("Determining units for all par files")

        file_units = {}
        parfile_contents = {}

        for pta_name in self.file_data.keys():
            parfile_content = self._get_parfile_content(pta_name)
            try:
                # Parse to check current units
                parfile_dict = parse_parfile(StringIO(parfile_content))
                current_units = parfile_dict.get("UNITS", ["TDB"])[0].upper()

                file_units[pta_name] = current_units
                parfile_contents[pta_name] = parfile_content

            except Exception as e:
                self.logger.error(f"Error reading par file for PTA {pta_name}: {e}")
                raise RuntimeError(f"Failed to read par file for PTA {pta_name}") from e

        return file_units, parfile_contents

    def _convert_mixed_units(
        self, file_units: Dict[str, str], parfile_contents: Dict[str, str]
    ) -> Dict[str, str]:
        """Convert par files with mixed units to consistent TDB units using appropriate timing package."""
        converted_parfiles = {}

        for pta_name, parfile_content in parfile_contents.items():
            current_units = file_units[pta_name]

            if current_units == "TDB":
                # Already in TDB, no conversion needed
                converted_parfiles[pta_name] = parfile_content
            else:
                # Get timing package for this PTA
                timing_package = self._get_timing_package(pta_name)

                if timing_package == "pint":
                    # Use PINT conversion for PINT PTAs
                    try:
                        converted_content = self._convert_pint_to_tdb(parfile_content)
                        converted_parfiles[pta_name] = converted_content
                        self.logger.debug(f"Converted PTA {pta_name} using PINT")
                    except Exception as e:
                        self.logger.error(
                            f"PINT conversion failed for PTA {pta_name}: {e}"
                        )
                        raise RuntimeError(
                            f"PINT unit conversion failed for PTA {pta_name}"
                        ) from e
                else:
                    # Use Tempo2 conversion for Tempo2 PTAs, or fallback
                    try:
                        converted_content = self._convert_tempo2_to_tdb(parfile_content)
                        converted_parfiles[pta_name] = converted_content
                        self.logger.debug(f"Converted PTA {pta_name} using Tempo2")
                    except Exception as e:
                        self.logger.error(
                            f"Tempo2 conversion failed for PTA {pta_name}: {e}"
                        )
                        raise RuntimeError(
                            f"Tempo2 unit conversion failed for PTA {pta_name}"
                        ) from e

        return converted_parfiles

    def _convert_pint_to_tdb(self, parfile_content: str) -> str:
        """Convert par file from TCB to TDB using PINT ModelBuilder."""
        try:
            # Create PINT model and parse par file
            model = create_pint_model(parfile_content)

            # Write par file with TDB units
            new_file = StringIO()
            model.write_parfile(new_file)

            return new_file.getvalue()
        except Exception as e:
            raise RuntimeError(f"PINT conversion failed: {e}") from e

    def _make_parameters_consistent(
        self, parfile_data: Dict[str, str]
    ) -> Dict[str, str]:
        """Make parameters consistent using reference PTA values."""
        self.logger.info(
            f"Making parameters consistent using reference PTA: {self.reference_pta}"
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
        reference_dict = parfile_dicts[self.reference_pta]

        # Pre-compute component parameters for ALL components
        component_params_map = {}
        for component in self.combine_components:
            component_params_map[component] = get_parameters_by_type_from_parfiles(
                component, parfile_dicts
            )

        # Pre-compute DMX parameters for ALL PTAs
        dmx_params_map = {}
        for pta_name, parfile_dict in parfile_dicts.items():
            dmx_params_map[pta_name] = self._get_dmx_parameters_from_parfile(
                parfile_dict
            )

        # Process each component
        for component in self.combine_components:
            self.logger.info(f"Making {component} parameters consistent")

            # Always call standard component consistency logic first
            self._make_component_parameters_consistent(
                parfile_dicts,
                reference_dict,
                self.reference_pta,
                component,
                component_params_map[component],
            )

            # For dispersion, also apply special DM logic
            if component == "dispersion":
                self._handle_dm_special_cases(
                    parfile_dicts,
                    reference_dict,
                    self.add_dm_derivatives,
                    dmx_params_map,
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
        """Make parameters for a specific component consistent."""
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

            # Remove ALL existing parameters for this component
            for param in component_params:
                if param in parfile_dict:
                    parfile_dict.pop(param)

            # Add reference values
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

            # Set DMEPOCH for ALL PTAs
            parfile_dict["DMEPOCH"] = [[f"{reference_dmepoch}", "0"]]  # 0 = frozen
            self.logger.debug(
                f"PTA {pta_name}: Set DMEPOCH = {reference_dmepoch} (frozen)"
            )

            # Handle DM derivatives based on add_dm_derivatives flag
            if add_dm_derivatives:
                parfile_dict["DM1"] = [["0.0", "1"]]
                parfile_dict["DM2"] = [["0.0", "1"]]
                self.logger.info(f"PTA {pta_name}: Set DM1 = 0.0, DM2 = 0.0")

    def _get_dmx_parameters_from_parfile(self, parfile_dict: Dict) -> List[str]:
        """Get DMX parameters from a parfile using PINT component discovery."""
        # Create PINT model directly from dictionary
        model = create_pint_model(parfile_dict)

        # Find DMX parameters from dispersion_dmx component
        dmx_params = []
        for comp in model.components.values():
            if hasattr(comp, "category") and comp.category == "dispersion_dmx":
                if hasattr(comp, "params"):
                    dmx_params.extend(comp.params)

        return dmx_params

    def _dict_to_parfile_string(self, parfile_dict: Dict) -> str:
        """Convert par file dictionary back to string format."""
        try:
            # Try to use PINT's as_parfile() method
            temp_content = self._dict_to_parfile_string_custom(parfile_dict)

            # Create PINT model from string
            model = create_pint_model(temp_content)

            # Use PINT's as_parfile() method
            return model.as_parfile()
        except Exception:
            return self._dict_to_parfile_string_custom(parfile_dict)

    def _dict_to_parfile_string_custom(self, parfile_dict: Dict) -> str:
        """Custom implementation for converting par file dictionary to string."""
        lines = []
        for param_name, param_values in parfile_dict.items():
            for param_value in param_values:
                if isinstance(param_value, list):
                    # Handle list format: [value, error]
                    value_str = " ".join(str(v) for v in param_value)
                else:
                    # Handle string format
                    value_str = str(param_value)
                lines.append(f"{param_name} {value_str}")

        return "\n".join(lines) + "\n"

    def _write_consistent_parfiles(
        self, consistent_parfiles: Dict[str, str]
    ) -> Dict[str, Path]:
        """Write consistent par files to output directory."""
        if self.output_dir is None:
            self.output_dir = Path(tempfile.mkdtemp(prefix="consistent_parfiles_"))

        self.output_dir.mkdir(parents=True, exist_ok=True)
        output_files = {}

        for pta_name, parfile_content in consistent_parfiles.items():
            output_filename = self._get_output_filename(pta_name)
            output_path = self.output_dir / output_filename

            with open(output_path, "w") as f:
                f.write(parfile_content)

            output_files[pta_name] = output_path
            self.logger.debug(f"Written consistent par file: {output_path}")

        return output_files

    def _get_output_filename(self, pta_name: str) -> str:
        """Generate output filename for consistent par file."""
        return f"consistent_{pta_name}.par"

    # ===== PARAMETER MAPPING METHODS =====

    def _discover_mergeable_parameters(self) -> List[str]:
        """Discover parameters that can be merged based on component types."""
        mergeable_params = []
        for component_type in self.combine_components:
            # Convert file data to parfile_dicts for pint_helpers
            parfile_dicts = {}
            for pta_name in self.file_data.keys():
                parfile_content = self._get_parfile_content(pta_name)
                parfile_dicts[pta_name] = parse_parfile(StringIO(parfile_content))

            params = get_parameters_by_type_from_parfiles(component_type, parfile_dicts)
            mergeable_params.extend(params)
        return mergeable_params

    def _process_all_pta_parameters(
        self, mergeable_params: List[str]
    ) -> Tuple[Dict, Dict]:
        """Process parameters from all PTAs."""
        fitparameters = {}
        setparameters = {}

        # Create PINT models from file data
        pint_models = {}
        for pta_name in self.file_data.keys():
            parfile_content = self._get_parfile_content(pta_name)
            pint_models[pta_name] = create_pint_model(parfile_content)

        for pta_name, model in pint_models.items():
            self._process_pta_parameters(
                pta_name, model, mergeable_params, fitparameters, "free"
            )
            self._process_pta_parameters(
                pta_name, model, mergeable_params, setparameters, "all"
            )

        return fitparameters, setparameters

    def _process_pta_parameters(
        self,
        pta_name: str,
        model: TimingModel,
        mergeable_params: List[str],
        target_dict: Dict,
        parameter_type: str = "all",
    ) -> None:
        """Process parameters for a single PINT model.

        Args:
            pta_name: Name of the PTA
            model: PINT TimingModel instance
            mergeable_params: List of parameters that should be merged
            target_dict: Dictionary to update with parameters
            parameter_type: Type of parameters to process ("free" or "all")
        """
        if parameter_type == "free":
            param_list = model.free_params  # Only free (unfrozen) parameters
            self.logger.debug(
                f"Processing PTA '{pta_name}' with {len(param_list)} free parameters"
            )
        else:
            param_list = model.params  # ALL parameters present in model
            self.logger.debug(
                f"Processing PTA '{pta_name}' with {len(param_list)} total parameters"
            )

        for param_name in param_list:
            meta_parname = self.resolve_parameter_equivalence(param_name)

            # Check if this parameter should be merged
            if param_name in mergeable_params:
                # Add as merged parameter - will fail if not available across PTAs
                self._add_merged_parameter(
                    meta_parname, pta_name, param_name, target_dict
                )
            else:
                # Parameter not mergeable (detector-specific), make it PTA-specific
                self._add_pta_specific_parameter(
                    meta_parname, pta_name, param_name, target_dict
                )

    def _add_merged_parameter(
        self, meta_parname: str, pta_name: str, param_name: str, target_dict: Dict
    ) -> None:
        """Add a merged parameter to target dictionary."""
        if meta_parname not in target_dict:
            target_dict[meta_parname] = {}
        target_dict[meta_parname][pta_name] = param_name

    def _add_pta_specific_parameter(
        self, meta_parname: str, pta_name: str, param_name: str, target_dict: Dict
    ) -> None:
        """Add a PTA-specific parameter to target dictionary."""
        # For PTA-specific parameters, use the original parameter name
        full_parname = f"{param_name}_{pta_name}"
        target_dict[full_parname] = {pta_name: param_name}

    def _validate_parameter_consistency(
        self, fitparameters: Dict, setparameters: Dict
    ) -> None:
        """Validate parameter consistency."""
        # Check that all fit parameters are also in set parameters
        fit_param_names = set(fitparameters.keys())
        set_param_names = set(setparameters.keys())

        missing_from_set = fit_param_names - set_param_names
        if missing_from_set:
            raise ParameterInconsistencyError(
                f"Fit parameters not found in set parameters: {missing_from_set}"
            )

    def _build_parameter_mapping_result(
        self, fitparameters: Dict, setparameters: Dict
    ) -> "ParameterMapping":
        """Build the final ParameterMapping result."""
        merged_parameters = [
            name for name in fitparameters.keys() if len(fitparameters[name]) > 1
        ]
        pta_specific_parameters = [
            name for name in fitparameters.keys() if len(fitparameters[name]) == 1
        ]

        return ParameterMapping(
            fitparameters=fitparameters,
            setparameters=setparameters,
            merged_parameters=merged_parameters,
            pta_specific_parameters=pta_specific_parameters,
        )

    # ===== PARAMETER RESOLUTION METHODS =====

    def resolve_parameter_equivalence(self, param_name: str) -> str:
        """Resolve parameter aliases to canonical names."""
        canonical = self._aliases.get(param_name, param_name)
        if canonical != param_name:
            self.logger.debug(
                f"Resolved parameter alias '{param_name}' -> '{canonical}'"
            )
        return canonical

    def check_component_available_across_ptas(self, component_type: str) -> bool:
        """Check if component type is available across all PINT models."""
        for pta_name in self.file_data.keys():
            parfile_content = self._get_parfile_content(pta_name)
            model = create_pint_model(parfile_content)

            if not check_component_available_in_model(model, component_type):
                return False
        return True

    def check_parameter_identifiable(self, pta_name: str, param_name: str) -> bool:
        """Check if parameter is identifiable in specific PINT model."""
        if pta_name not in self.file_data:
            return False

        parfile_content = self._get_parfile_content(pta_name)
        model = create_pint_model(parfile_content)
        return get_parameter_identifiability_from_model(model, param_name)

    def _parse_parfiles(self) -> Dict[str, Dict]:
        """Parse parfile content strings into dictionaries using PINT's parse_parfile."""
        return {
            pta_name: parse_parfile(StringIO(self._get_parfile_content(pta_name)))
            for pta_name in self.file_data.keys()
        }

    def _create_minimal_parfile_for_component(
        self, parfile_dict: Dict, component
    ) -> str:
        """Create minimal parfile for component discovery using PINT component system.

        Args:
            parfile_dict: Parsed parfile dictionary
            component: String or list of strings specifying component(s) to include.
                      Spindown is always included as PINT requires it.
        """
        # Normalize component to list
        if isinstance(component, str):
            components = [component]
        else:
            components = list(component)

        # Always include spindown - PINT cannot process parfile without it
        if "spindown" not in components:
            components.append("spindown")

        # Create PINT model from parfile dictionary
        model = create_pint_model(parfile_dict)

        # Get category mapping from PINT
        category_mapping = get_category_mapping_from_pint()

        # Extract parameters from all requested components
        component_params = set()
        for comp_name in components:
            target_category = category_mapping.get(comp_name)
            if not target_category:
                continue

            for comp in model.components.values():
                if hasattr(comp, "category") and comp.category == target_category:
                    if hasattr(comp, "params"):
                        component_params.update(comp.params)

        # Create minimal parfile content
        minimal_lines = []
        for param in component_params:
            if param in parfile_dict:
                value = parfile_dict[param]
                if isinstance(value, list):
                    value_str = " ".join(str(v) for v in value)
                else:
                    value_str = str(value)
                minimal_lines.append(f"{param} {value_str}")

        return "\n".join(minimal_lines)

    def _get_parfile_content(self, pta_name: str) -> str:
        """Get parfile content for a specific PTA from file data."""
        parfile_path = self.file_data[pta_name]["par"]
        with open(parfile_path, "r") as f:
            return f.read()

    def _get_timing_package(self, pta_name: str) -> str:
        """Get timing package for a specific PTA from file data."""
        return self.file_data[pta_name]["timing_package"]

    def _choose_reference_pta(self, file_data: Dict[str, Dict[str, Any]]) -> str:
        """Choose reference PTA based on longest timespan."""
        return max(file_data.keys(), key=lambda pta: file_data[pta]["timespan_days"])

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

    def _extract_pulsar_name_from_pint_model(self, parfile_path: Path) -> str:
        """Extract pulsar name from PINT model (PSR parameter)."""
        from pint.models.model_builder import ModelBuilder

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

    def _is_parameter_for_component(
        self, param_name: str, component_params: List[str]
    ) -> bool:
        """Check if parameter belongs to a specific component."""
        return param_name in component_params

    def _get_parfile_dicts(self) -> Dict[str, Dict]:
        """Get parfile dictionaries for all PTAs."""
        return self._parse_parfiles()

    def build_parameter_mapping(self) -> "ParameterMapping":
        """Alias for build_parameter_mappings for backward compatibility."""
        return self.build_parameter_mappings()


class ParameterMapping:
    """Data class for parameter mapping results."""

    def __init__(
        self,
        fitparameters: Dict,
        setparameters: Dict,
        merged_parameters: List[str],
        pta_specific_parameters: List[str],
    ):
        self.fitparameters = fitparameters  # Only FREE parameters (unfrozen)
        self.setparameters = setparameters  # ALL parameters present in model
        self.merged_parameters = merged_parameters
        self.pta_specific_parameters = pta_specific_parameters


class ParameterInconsistencyError(Exception):
    """Raised when parameters are inconsistent across PTAs"""

    pass
