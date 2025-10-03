"""MetaPulsar parameter manager for high-level parameter mapping workflow.

This module provides the MetaPulsarParameterManager class that orchestrates
the complete workflow of building parameter mappings from multiple PINT models.
"""

from typing import Dict, List, Tuple
from pint.models import TimingModel
from .parameter_resolver import ParameterResolver


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


class MetaPulsarParameterManager:
    """Handles high-level parameter mapping workflow using PINT models.

    This class orchestrates the complete workflow of building parameter
    mappings from multiple PINT models, using ParameterResolver for all
    parameter/component checks and PINT helpers for discovery.
    """

    def __init__(
        self, pint_models: Dict[str, TimingModel], parfile_dicts: Dict[str, Dict]
    ):
        """Initialize manager with PINT models and parfile dictionaries from multiple PTAs.

        Args:
            pint_models: Dictionary mapping PTA names to PINT TimingModel instances
            parfile_dicts: Dictionary mapping PTA names to parfile dictionaries

        Raises:
            ValueError: If PTA names in pint_models and parfile_dicts don't match
        """
        # Validate input consistency
        if set(pint_models.keys()) != set(parfile_dicts.keys()):
            raise ValueError(
                f"PTA names mismatch: pint_models has {set(pint_models.keys())}, "
                f"parfile_dicts has {set(parfile_dicts.keys())}"
            )

        self.pint_models = pint_models
        self.parfile_dicts = parfile_dicts  # NEW: Add parfile dictionaries
        self.resolver = ParameterResolver(pint_models)

    def build_parameter_mappings(
        self,
        combine_components: List[str] = [
            "astrometry",
            "spindown",
            "binary",
            "dispersion",
        ],
    ) -> ParameterMapping:
        """Build parameter mappings from PINT models.

        This is the main workflow method that:
        1. Discovers parameters to merge using PINT helpers
        2. Processes each PTA's parameters using resolver
        3. Builds fitparameters and setparameters mappings
        4. Validates consistency and returns structured result

        Args:
            combine_components: List of component types to merge

        Returns:
            ParameterMapping with fitparameters, setparameters, etc.

        Raises:
            ParameterInconsistencyError: If parameters are inconsistent
            MissingComponentError: If required components are missing
        """
        # Step 1: Discover parameters for components that should be merged
        mergeable_params = self._discover_mergeable_parameters(combine_components)

        # Step 2-6: Process parameters using resolver
        fitparameters, setparameters = self._process_all_pta_parameters(
            mergeable_params
        )

        # Step 7: Validate consistency
        self._validate_parameter_consistency(fitparameters, setparameters)

        # Step 8: Build result
        return self._build_parameter_mapping_result(fitparameters, setparameters)

    def _discover_mergeable_parameters(
        self, combine_components: List[str]
    ) -> List[str]:
        """Discover parameters that can be merged based on component types.

        Args:
            combine_components: List of component types to merge

        Returns:
            List of parameter names that can potentially be merged
        """
        from .pint_helpers import get_parameters_by_type_from_parfiles

        mergeable_params = []
        for component_type in combine_components:
            params = get_parameters_by_type_from_parfiles(
                component_type, self.parfile_dicts
            )
            mergeable_params.extend(params)
        return mergeable_params

    def _process_all_pta_parameters(
        self, mergeable_params: List[str]
    ) -> Tuple[Dict, Dict]:
        """Process parameters from all PTAs.

        Args:
            mergeable_params: List of parameters that should be merged

        Returns:
            Tuple of (fitparameters, setparameters) dictionaries
        """
        fitparameters = {}
        setparameters = {}

        for pta_name, model in self.pint_models.items():
            self._process_pta_fit_parameters(
                pta_name, model, mergeable_params, fitparameters
            )
            self._process_pta_set_parameters(pta_name, model, setparameters)

        return fitparameters, setparameters

    def _process_pta_fit_parameters(
        self,
        pta_name: str,
        model: TimingModel,
        mergeable_params: List[str],  # Renamed from merge_pars
        fitparameters: Dict,
    ) -> None:
        """Process FREE parameters for a single PINT model.

        Args:
            pta_name: Name of the PTA
            model: PINT TimingModel instance
            mergeable_params: List of parameters that should be merged
            fitparameters: Dictionary to update with fit parameters

        Raises:
            ParameterInconsistencyError: If a parameter that should be merged is not available across all PTAs
        """
        from loguru import logger

        logger.debug(
            f"_process_pta_fit_parameters: Processing PTA '{pta_name}' with {len(model.free_params)} free parameters"
        )
        logger.debug(
            f"_process_pta_fit_parameters: mergeable_params = {mergeable_params}"
        )
        logger.debug(
            f"_process_pta_fit_parameters: model.free_params = {model.free_params}"
        )

        for param_name in model.free_params:  # Only free (unfrozen) parameters
            meta_parname = self.resolver.resolve_parameter_equivalence(param_name)
            logger.debug(
                f"_process_pta_fit_parameters: param_name='{param_name}' -> meta_parname='{meta_parname}'"
            )

            # Check if this parameter should be merged (is in mergeable_params)
            if param_name in mergeable_params:
                logger.debug(
                    f"_process_pta_fit_parameters: '{param_name}' is mergeable, calling _add_merged_parameter"
                )
                # Add as merged parameter - will fail if not available across PTAs
                self._add_merged_parameter(
                    meta_parname, pta_name, param_name, fitparameters
                )
            else:
                logger.debug(
                    f"_process_pta_fit_parameters: '{param_name}' is NOT mergeable, calling _add_pta_specific_parameter"
                )
                # Parameter not mergeable (detector-specific), make it PTA-specific
                self._add_pta_specific_parameter(
                    meta_parname, pta_name, param_name, fitparameters
                )

    def _process_pta_set_parameters(
        self, pta_name: str, model: TimingModel, setparameters: Dict
    ) -> None:
        """Process ALL parameters (present in model) for a single PINT model.

        Args:
            pta_name: Name of the PTA
            model: PINT TimingModel instance
            setparameters: Dictionary to update with ALL model parameters
        """
        for param_name in model.params:  # ALL parameters present in model
            # For setparameters, always use PTA-specific naming like legacy
            full_parname = f"{param_name}_{pta_name}"
            setparameters[full_parname] = {pta_name: param_name}

    def _add_merged_parameter(
        self, meta_parname: str, pta_name: str, param_name: str, fitparameters: Dict
    ) -> None:
        """Add a merged parameter to fitparameters.

        Args:
            meta_parname: Canonical parameter name
            pta_name: Name of the PTA
            param_name: Original parameter name
            fitparameters: Dictionary to update
        """
        from loguru import logger

        logger.debug(
            f"_add_merged_parameter: meta_parname='{meta_parname}', pta_name='{pta_name}', param_name='{param_name}'"
        )

        # Check availability using resolver
        if not self.resolver.check_parameter_available_across_ptas(param_name):
            raise ParameterInconsistencyError(
                f"Not all PTAs have parameter {meta_parname}"
            )

        if meta_parname not in fitparameters:
            fitparameters[meta_parname] = {}
        fitparameters[meta_parname][pta_name] = param_name

        logger.debug(
            f"_add_merged_parameter: Added to fitparameters['{meta_parname}']['{pta_name}'] = '{param_name}'"
        )

    def _add_pta_specific_parameter(
        self, meta_parname: str, pta_name: str, param_name: str, fitparameters: Dict
    ) -> None:
        """Add a PTA-specific parameter to fitparameters.

        Args:
            meta_parname: Canonical parameter name
            pta_name: Name of the PTA
            param_name: Original parameter name
            fitparameters: Dictionary to update
        """
        from loguru import logger

        logger.debug(
            f"_add_pta_specific_parameter: meta_parname='{meta_parname}', pta_name='{pta_name}', param_name='{param_name}'"
        )

        # PTA-specific parameter - check identifiability using resolver
        is_identifiable = self.resolver.check_parameter_identifiable(
            pta_name, param_name
        )
        logger.debug(
            f"_add_pta_specific_parameter: check_parameter_identifiable('{pta_name}', '{param_name}') = {is_identifiable}"
        )

        if is_identifiable:
            # For PTA-specific parameters, use the original parameter name
            # This preserves the PTA-specific naming convention
            full_parname = f"{param_name}_{pta_name}"
            fitparameters[full_parname] = {pta_name: param_name}
            logger.debug(
                f"_add_pta_specific_parameter: Added to fitparameters['{full_parname}'] = {{'{pta_name}': '{param_name}'}}"
            )
        else:
            logger.debug(
                f"_add_pta_specific_parameter: Parameter '{param_name}' not identifiable, skipping"
            )

    def _validate_parameter_consistency(
        self, fitparameters: Dict, setparameters: Dict
    ) -> None:
        """Validate parameter consistency.

        Args:
            fitparameters: Dictionary of fit parameters
            setparameters: Dictionary of set parameters

        Raises:
            ParameterInconsistencyError: If parameters are inconsistent
        """
        # Check that all fit parameters are also in set parameters
        # This ensures fitparameters ⊆ setparameters (free ⊆ present)
        fit_param_names = set(fitparameters.keys())
        set_param_names = set(setparameters.keys())

        missing_from_set = fit_param_names - set_param_names
        if missing_from_set:
            raise ParameterInconsistencyError(
                f"Fit parameters not found in set parameters: {missing_from_set}"
            )

        # Note: PINT automatically validates that free_params ⊆ fittable_params
        # when setting free_params, so we don't need to check this here

    def _build_parameter_mapping_result(
        self, fitparameters: Dict, setparameters: Dict
    ) -> ParameterMapping:
        """Build the final ParameterMapping result.

        Args:
            fitparameters: Dictionary of fit parameters
            setparameters: Dictionary of set parameters

        Returns:
            ParameterMapping instance
        """
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
