"""Parameter management for multi-PTA pulsar analysis.

This module provides the ParameterManager class that handles parameter discovery,
alias resolution, merging strategies, and validation using PINT as the single
source of truth.
"""

from typing import Dict, List
from dataclasses import dataclass

from pint.models import TimingModel
from pint.models.model_builder import AllComponents


@dataclass
class ParameterMapping:
    """Structured result for parameter mappings"""

    fitparameters: Dict[str, Dict[str, str]]  # {meta_param: {pta: original_param}}
    setparameters: Dict[str, Dict[str, str]]  # {meta_param: {pta: original_param}}
    merged_parameters: List[str]  # Parameters that are merged across PTAs
    pta_specific_parameters: List[str]  # Parameters that are PTA-specific


class ParameterManagerError(Exception):
    """Base exception for ParameterManager errors"""


class MissingComponentError(ParameterManagerError):
    """Raised when required component is missing across PTAs"""


class ParameterInconsistencyError(ParameterManagerError):
    """Raised when parameters are inconsistent across PTAs"""


class CoordinateSystemMismatchError(ParameterManagerError):
    """Raised when coordinate systems are incompatible for merging"""


class ParameterManager:
    """High-level parameter management for multi-PTA pulsar analysis.

    This class handles parameter discovery, alias resolution, merging strategies,
    and validation using PINT as the single source of truth. Coordinate system
    handling is done at the component level, not parameter level.
    """

    def __init__(self, pint_models: Dict[str, TimingModel]):
        """Initialize ParameterManager with PINT models from multiple PTAs.

        Args:
            pint_models: Dictionary mapping PTA names to PINT TimingModel instances
        """
        self.pint_models = pint_models
        self._simple_aliases = self._get_simple_aliases_from_pint()
        self._reverse_aliases = self._build_reverse_aliases()

    def build_parameter_mappings(
        self,
        merge_astrometry: bool = True,
        merge_spin: bool = True,
        merge_binary: bool = True,
        merge_dm: bool = True,
    ) -> ParameterMapping:
        """Main function that replicates set_parameters_from_meta_pulsars() logic

        This method implements the core workflow:
        1. Build merge_pars list based on merge_config and PINT component discovery
        2. Loop through PTAs and their parameters (fitpars, setpars)
        3. Apply parameter equivalence resolution (aliases + coordinate systems)
        4. Check parameter availability across PTAs for merging
        5. Check parameter identifiability for PTA-specific parameters
        6. Build fitparameters and setparameters mappings
        7. Validate no overlap between fit and set parameters
        8. Return structured ParameterMapping
        """
        # Step 1: Build merge_pars list based on merge_config and PINT component discovery
        merge_config = {
            "astrometry": merge_astrometry,
            "spindown": merge_spin,
            "binary": merge_binary,
            "dispersion": merge_dm,
        }

        merge_pars = []
        for param_type, should_merge in merge_config.items():
            if should_merge:
                params = self.get_parameters_by_type(param_type)
                merge_pars.extend(params)

        # Step 2-6: Process parameters from each PTA
        fitparameters = {}
        setparameters = {}

        for pta_name, model in self.pint_models.items():
            # Process fit parameters
            for param_name in model.params:
                if param_name in model.fit_params:
                    meta_parname = self.resolve_parameter_equivalence(param_name)

                    if param_name in merge_pars:
                        # Check if parameter is available across all PTAs
                        if not self.check_parameter_available_across_ptas(param_name):
                            raise ParameterInconsistencyError(
                                f"Not all PTAs have parameter {meta_parname}"
                            )

                        if meta_parname not in fitparameters:
                            fitparameters[meta_parname] = {}
                        fitparameters[meta_parname][pta_name] = param_name

                    else:
                        # PTA-specific parameter - check if identifiable
                        if self.check_parameter_identifiable(pta_name, param_name):
                            full_parname = f"{meta_parname}_{pta_name}"
                            fitparameters[full_parname] = {pta_name: param_name}

            # Process set parameters
            for param_name in model.params:
                if param_name in model.set_params:
                    meta_parname = self.resolve_parameter_equivalence(param_name)
                    full_parname = f"{meta_parname}_{pta_name}"
                    setparameters[full_parname] = {pta_name: param_name}

        # Step 7: Validate no overlap between fit and set parameters
        # Check for parameters that are both fit in one PTA and set in another
        fit_param_names = set()
        set_param_names = set()

        for param_name, pta_dict in fitparameters.items():
            for pta, original_param in pta_dict.items():
                fit_param_names.add(original_param)

        for param_name, pta_dict in setparameters.items():
            for pta, original_param in pta_dict.items():
                set_param_names.add(original_param)

        overlap = fit_param_names & set_param_names
        if overlap:
            raise ParameterInconsistencyError(
                f"Parameters cannot be both fit and set: {overlap}"
            )

        # Step 8: Build result
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

    def resolve_parameter_equivalence(self, param_name: str) -> str:
        """Resolve simple parameter aliases only

        Returns the canonical parameter name for merging purposes.
        Handles simple parameter aliases (XDOT → A1DOT) but NOT coordinate
        system equivalences, which are handled at the component level.
        """
        # Check simple aliases only
        if param_name in self._simple_aliases:
            return self._simple_aliases[param_name]

        # No equivalence found, return original name
        return param_name

    def check_component_available_across_ptas(self, component_type: str) -> bool:
        """Check if component type is available across all PTAs

        For astrometry: checks if ANY astrometry component (Equatorial or Ecliptic)
        is available across all PTAs.
        For other components: checks if specific component type is available.
        """
        if component_type == "astrometry":
            # Check if any astrometry component is available
            astrometry_components = ["AstrometryEquatorial", "AstrometryEcliptic"]
            for pta_name, model in self.pint_models.items():
                has_astrometry = any(
                    comp in model.components for comp in astrometry_components
                )
                if not has_astrometry:
                    return False
            return True
        else:
            # Map component type names to actual component names
            component_mapping = {
                "spindown": "SpindownBase",
                "binary": "PulsarBinary",
                "dispersion": "Dispersion",
            }

            actual_component = component_mapping.get(component_type, component_type)

            # Check if specific component type is available
            for pta_name, model in self.pint_models.items():
                if actual_component not in model.components:
                    return False
            return True

    def check_parameter_available_across_ptas(self, param_name: str) -> bool:
        """Check if parameter exists across all PTAs (for merging decisions)

        For astrometry parameters: checks if ANY astrometry component exists across PTAs.
        For other parameters: checks if parameter (or its alias) exists in all PTAs.
        """
        # For astrometry parameters, use component-level checking
        astrometry_params = [
            "RAJ",
            "DECJ",
            "ELONG",
            "ELAT",
            "LAMBDA",
            "BETA",
            "PMRA",
            "PMDEC",
            "PMELONG",
            "PMELAT",
            "PMLAMBDA",
            "PMBETA",
            "POSEPOCH",
            "PX",
        ]

        if param_name in astrometry_params:
            return self.check_component_available_across_ptas("astrometry")

        # For other parameters, check individual parameter availability
        # Get all possible parameter names (including aliases only)
        possible_names = self._get_all_possible_parameter_names(param_name)

        for pta_name, model in self.pint_models.items():
            has_param = any(name in model.params for name in possible_names)
            if not has_param:
                return False
        return True

    def check_parameter_identifiable(self, pta_name: str, param_name: str) -> bool:
        """Check if parameter causes observable delays

        Replicates check_fitpar_works() logic using design matrix to determine
        if parameter contributes to observable delays.
        """
        model = self.pint_models[pta_name]

        # Check if parameter is in fit parameters
        if param_name not in model.fit_params:
            return False

        # For now, assume all fit parameters are identifiable
        # TODO: Implement design matrix check when Enterprise integration is available
        return True

    def get_parameters_by_type(self, param_type: str) -> List[str]:
        """Get parameters by type using PINT component discovery

        Uses PINT's component hierarchy to discover parameters by type
        (astrometry, spindown, binary, dispersion, etc.).
        """
        try:
            all_components = AllComponents()

            # Map parameter types to PINT component classes
            component_mapping = {
                "astrometry": ["AstrometryEquatorial", "AstrometryEcliptic"],
                "spindown": ["SpindownBase"],
                "binary": ["PulsarBinary"],
                "dispersion": ["Dispersion"],
            }

            if param_type not in component_mapping:
                return []

            # Get all parameters from the relevant components
            all_params = set()
            for component_name in component_mapping[param_type]:
                try:
                    component_class = getattr(all_components, component_name)
                    # Get parameters from the component class
                    if hasattr(component_class, "param_list"):
                        all_params.update(component_class.param_list)
                    elif hasattr(component_class, "params"):
                        all_params.update(component_class.params)
                except (AttributeError, TypeError):
                    # Component not available, continue
                    continue

            return list(all_params)

        except Exception:
            # Fallback to known parameters if PINT discovery fails
            parameter_mapping = {
                "astrometry": [
                    "RAJ",
                    "DECJ",
                    "ELONG",
                    "ELAT",
                    "LAMBDA",
                    "BETA",
                    "PMRA",
                    "PMDEC",
                    "PMELONG",
                    "PMELAT",
                    "PMLAMBDA",
                    "PMBETA",
                    "POSEPOCH",
                    "PX",
                ],
                "spindown": ["PEPOCH"]
                + [f"F{i}" for i in range(20)]
                + [f"P{i}" for i in range(20)],
                "binary": [
                    "BINARY",
                    "PB",
                    "PBDOT",
                    "A1",
                    "A1DOT",
                    "XDOT",
                    "OM",
                    "T0",
                    "OMDOT",
                    "TASC",
                    "GAMMA",
                    "ECC",
                    "E",
                    "ECCDOT",
                    "EDOT",
                    "KOM",
                    "KIN",
                    "SINI",
                    "SHAPMAX",
                    "H4",
                    "H3",
                    "STIG",
                    "STIGMA",
                    "EPS1",
                    "EPS2",
                    "EPS1DOT",
                    "EPS2DOT",
                    "DR",
                    "DTH",
                    "SHAPIRO",
                    "M2",
                    "A0",
                    "B0",
                    "OM2DOT",
                ],
                "dispersion": ["DMEPOCH", "DM", "DM1", "DM2"],
            }

            return parameter_mapping.get(param_type, [])

    def _get_simple_aliases_from_pint(self) -> Dict[str, str]:
        """Get simple parameter aliases from PINT (not coordinate-related)"""
        try:
            all_components = AllComponents()
            alias_map = all_components._param_alias_map

            # Filter out coordinate-related aliases (RAJ/ELONG, etc.)
            # Keep only simple parameter aliases
            simple_aliases = {}
            for alias, canonical in alias_map.items():
                # Skip coordinate system aliases
                if not self._is_coordinate_alias(alias, canonical):
                    simple_aliases[alias] = canonical

            # Add missing aliases that PINT doesn't have but legacy expects
            simple_aliases["EDOT"] = "ECCDOT"

            return simple_aliases
        except Exception:
            # Fallback to known aliases if PINT discovery fails
            return {
                "XDOT": "A1DOT",
                "E": "ECC",
                "EDOT": "ECCDOT",
                "STIG": "STIGMA",
                "VARSIGMA": "STIGMA",
                "RA": "RAJ",
                "DEC": "DECJ",
            }

    def _is_coordinate_alias(self, alias: str, canonical: str) -> bool:
        """Check if alias is coordinate-related (should be handled at component level)"""
        coordinate_params = [
            "RAJ",
            "DECJ",
            "ELONG",
            "ELAT",
            "LAMBDA",
            "BETA",
            "PMRA",
            "PMDEC",
            "PMELONG",
            "PMELAT",
            "PMLAMBDA",
            "PMBETA",
        ]
        return alias in coordinate_params or canonical in coordinate_params

    def _build_reverse_aliases(self) -> Dict[str, List[str]]:
        """Build reverse alias mapping for parameter discovery"""
        reverse_aliases = {}

        for alias, canonical in self._simple_aliases.items():
            if canonical not in reverse_aliases:
                reverse_aliases[canonical] = []
            reverse_aliases[canonical].append(alias)

        return reverse_aliases

    def _get_all_possible_parameter_names(self, param_name: str) -> List[str]:
        """Get all possible parameter names including aliases only"""
        possible_names = [param_name]

        # Add simple aliases (both directions)
        if param_name in self._reverse_aliases:
            possible_names.extend(self._reverse_aliases[param_name])

        # Check if param_name is an alias of something else
        for canonical, aliases in self._reverse_aliases.items():
            if param_name in aliases:
                possible_names.append(canonical)
                possible_names.extend(aliases)

        return list(set(possible_names))  # Remove duplicates
