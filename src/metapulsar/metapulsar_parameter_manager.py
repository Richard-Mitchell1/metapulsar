"""MetaPulsar parameter manager for high-level parameter mapping workflow.

This module provides the MetaPulsarParameterManager class that orchestrates
the complete workflow of building parameter mappings from multiple PINT models.
"""

from typing import Dict, List, Tuple
from pint.models import TimingModel
from .parameter_resolver import ParameterResolver
from .pint_helpers import get_parameters_by_type_from_pint


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

    def __init__(self, pint_models: Dict[str, TimingModel]):
        """Initialize manager with PINT models from multiple PTAs.

        Args:
            pint_models: Dictionary mapping PTA names to PINT TimingModel instances
        """
        self.pint_models = pint_models
        self.resolver = ParameterResolver(pint_models)

    def build_parameter_mappings(
        self,
        merge_astrometry: bool = True,
        merge_spin: bool = True,
        merge_binary: bool = True,
        merge_dm: bool = True,
    ) -> ParameterMapping:
        """Build parameter mappings from PINT models.

        This is the main workflow method that:
        1. Discovers parameters to merge using PINT helpers
        2. Processes each PTA's parameters using resolver
        3. Builds fitparameters and setparameters mappings
        4. Validates consistency and returns structured result

        Args:
            merge_astrometry: Whether to merge astrometry parameters
            merge_spin: Whether to merge spindown parameters
            merge_binary: Whether to merge binary parameters
            merge_dm: Whether to merge dispersion parameters

        Returns:
            ParameterMapping with fitparameters, setparameters, etc.

        Raises:
            ParameterInconsistencyError: If parameters are inconsistent
            MissingComponentError: If required components are missing
        """
        # Step 1: Build merge_pars list using PINT helpers
        merge_pars = self._build_merge_parameters_list(
            {
                "astrometry": merge_astrometry,
                "spindown": merge_spin,
                "binary": merge_binary,
                "dispersion": merge_dm,
            }
        )

        # Step 2-6: Process parameters using resolver
        fitparameters, setparameters = self._process_all_pta_parameters(merge_pars)

        # Step 7: Validate consistency
        self._validate_parameter_consistency(fitparameters, setparameters)

        # Step 8: Build result
        return self._build_parameter_mapping_result(fitparameters, setparameters)

    def _build_merge_parameters_list(self, merge_config: Dict[str, bool]) -> List[str]:
        """Build list of parameters to merge based on configuration.

        Args:
            merge_config: Dictionary mapping parameter types to merge flags

        Returns:
            List of parameter names to merge
        """
        merge_pars = []
        for param_type, should_merge in merge_config.items():
            if should_merge:
                params = get_parameters_by_type_from_pint(param_type)
                merge_pars.extend(params)
        return merge_pars

    def _process_all_pta_parameters(self, merge_pars: List[str]) -> Tuple[Dict, Dict]:
        """Process parameters from all PTAs.

        Args:
            merge_pars: List of parameters to merge

        Returns:
            Tuple of (fitparameters, setparameters) dictionaries
        """
        fitparameters = {}
        setparameters = {}

        for pta_name, model in self.pint_models.items():
            self._process_pta_fit_parameters(pta_name, model, merge_pars, fitparameters)
            self._process_pta_set_parameters(pta_name, model, setparameters)

        return fitparameters, setparameters

    def _process_pta_fit_parameters(
        self,
        pta_name: str,
        model: TimingModel,
        merge_pars: List[str],
        fitparameters: Dict,
    ) -> None:
        """Process FREE parameters for a single PINT model.

        Args:
            pta_name: Name of the PTA
            model: PINT TimingModel instance
            merge_pars: List of parameters to merge
            fitparameters: Dictionary to update with fit parameters
        """
        for param_name in model.free_params:  # Only free (unfrozen) parameters
            meta_parname = self.resolver.resolve_parameter_equivalence(param_name)

            if param_name in merge_pars:
                self._add_merged_parameter(
                    meta_parname, pta_name, param_name, fitparameters
                )
            else:
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
            meta_parname = self.resolver.resolve_parameter_equivalence(param_name)
            full_parname = f"{meta_parname}_{pta_name}"
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
        # Check availability using resolver
        if not self.resolver.check_parameter_available_across_ptas(param_name):
            raise ParameterInconsistencyError(
                f"Not all PTAs have parameter {meta_parname}"
            )

        if meta_parname not in fitparameters:
            fitparameters[meta_parname] = {}
        fitparameters[meta_parname][pta_name] = param_name

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
        # PTA-specific parameter - check identifiability using resolver
        if self.resolver.check_parameter_identifiable(pta_name, param_name):
            full_parname = f"{meta_parname}_{pta_name}"
            fitparameters[full_parname] = {pta_name: param_name}

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
