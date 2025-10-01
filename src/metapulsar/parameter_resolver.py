"""Parameter resolver for handling parameter equivalence and availability checking.

This module provides the ParameterResolver class that encapsulates the logic
for resolving parameter aliases, checking parameter availability across PINT models,
and validating component availability.
"""

from typing import Dict, List
from pint.models import TimingModel
from .pint_helpers import (
    get_parameter_aliases_from_pint,
    check_component_available_in_model,
    get_parameter_identifiability_from_model,
    _is_astrometry_parameter,
)


class ParameterResolver:
    """Handles parameter equivalence resolution and availability checking.

    This class encapsulates the logic for resolving parameter aliases,
    checking parameter availability across PINT models, and validating component
    availability. It uses PINT helper functions but adds multi-model logic.
    """

    def __init__(self, pint_models: Dict[str, TimingModel]):
        """Initialize resolver with PINT models from multiple PTAs.

        Args:
            pint_models: Dictionary mapping PTA names to PINT TimingModel instances
        """
        self.pint_models = pint_models
        self._aliases = get_parameter_aliases_from_pint()
        self._reverse_aliases = self._build_reverse_aliases()

    def resolve_parameter_equivalence(self, param_name: str) -> str:
        """Resolve parameter aliases to canonical names.

        Args:
            param_name: Original parameter name

        Returns:
            Canonical parameter name for merging purposes
        """
        from loguru import logger

        canonical = self._aliases.get(param_name, param_name)
        if canonical != param_name:
            logger.debug(f"Resolved parameter alias '{param_name}' -> '{canonical}'")
        return canonical

    def check_parameter_available_across_ptas(self, param_name: str) -> bool:
        """Check if parameter is available across all PINT models.

        Args:
            param_name: Parameter name to check

        Returns:
            True if parameter (or its alias) is available in all PINT models
        """
        from loguru import logger

        # For astrometry parameters, check component availability
        if _is_astrometry_parameter(param_name):
            logger.debug(
                f"Checking astrometry parameter '{param_name}' via component availability"
            )
            return self.check_component_available_across_ptas("astrometry")

        # For other parameters, check using alias resolution
        canonical_name = self.resolve_parameter_equivalence(param_name)
        all_possible_names = self._get_all_possible_parameter_names(canonical_name)

        for pta_name, model in self.pint_models.items():
            if not any(name in model.params for name in all_possible_names):
                logger.debug(
                    f"Parameter '{param_name}' not available in PTA '{pta_name}'"
                )
                return False

        logger.debug(f"Parameter '{param_name}' available across all PINT models")
        return True

    def check_component_available_across_ptas(self, component_type: str) -> bool:
        """Check if component type is available across all PINT models.

        Args:
            component_type: Type of component to check

        Returns:
            True if component is available in all PINT models
        """
        for pta_name, model in self.pint_models.items():
            if not check_component_available_in_model(model, component_type):
                return False
        return True

    def check_parameter_identifiable(self, pta_name: str, param_name: str) -> bool:
        """Check if parameter is identifiable in specific PINT model.

        Args:
            pta_name: Name of PTA
            param_name: Parameter name to check

        Returns:
            True if parameter is identifiable in the PINT model
        """
        if pta_name not in self.pint_models:
            return False

        model = self.pint_models[pta_name]
        return get_parameter_identifiability_from_model(model, param_name)

    def _build_reverse_aliases(self) -> Dict[str, List[str]]:
        """Build reverse alias mapping for parameter discovery."""
        reverse_aliases = {}
        for alias, canonical in self._aliases.items():
            if canonical not in reverse_aliases:
                reverse_aliases[canonical] = []
            reverse_aliases[canonical].append(alias)
        return reverse_aliases

    def _get_all_possible_parameter_names(self, param_name: str) -> List[str]:
        """Get all possible parameter names including aliases."""
        # Get canonical name
        canonical = self.resolve_parameter_equivalence(param_name)

        # Get all aliases for this canonical name
        aliases = self._reverse_aliases.get(canonical, [])

        # Return canonical name plus all aliases
        return [canonical] + aliases
