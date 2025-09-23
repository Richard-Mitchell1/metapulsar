"""PINT helper functions for parameter discovery and model interaction.

This module provides pure functions that encapsulate PINT-specific logic
for parameter discovery, alias resolution, and model validation.
"""

from typing import Dict, List
from pint.models import TimingModel
from pint.models.model_builder import AllComponents


class PINTDiscoveryError(Exception):
    """Raised when PINT component discovery fails"""


def get_category_mapping_from_pint() -> Dict[str, str]:
    """Get component category mappings from PINT.

    Returns:
        Dictionary mapping parameter type names to PINT category names
    """
    return {
        "astrometry": "astrometry",
        "spindown": "spindown",
        "binary": "pulsar_system",
        "dispersion": "dispersion_constant",
    }


def get_parameters_by_type_from_pint(param_type: str) -> List[str]:
    """Get parameters by type using PINT component discovery.

    Args:
        param_type: Type of parameters to discover ('astrometry', 'spindown', etc.)

    Returns:
        List of parameter names discovered from PINT components

    Raises:
        PINTDiscoveryError: If PINT component discovery fails
    """
    from loguru import logger

    try:
        all_components = AllComponents()

        # Discover category mapping from PINT
        category_mapping = get_category_mapping_from_pint()

        if param_type not in category_mapping:
            logger.warning(f"Unknown parameter type: {param_type}")
            return []

        target_category = category_mapping[param_type]

        # Get all parameters from components with matching category
        all_params = set()
        astrometry_components = all_components.category_component_map.get(
            target_category, []
        )

        for component_name in astrometry_components:
            try:
                component_class = getattr(all_components, component_name)
                # Create an instance to get the params
                component_instance = component_class()
                if hasattr(component_instance, "params"):
                    all_params.update(component_instance.params)

            except (AttributeError, TypeError, Exception):
                # Component not available, continue
                continue

        logger.debug(f"Discovered {len(all_params)} parameters for type '{param_type}'")
        return list(all_params)

    except Exception as e:
        logger.error(f"PINT component discovery failed: {e}")
        # NO FALLBACK - fail gracefully as per SSOT principle
        raise PINTDiscoveryError(
            f"Failed to discover parameters for type '{param_type}': {e}"
        )


def get_parameter_aliases_from_pint() -> Dict[str, str]:
    """Get simple parameter aliases from PINT.

    Returns:
        Dictionary mapping aliases to canonical parameter names
        Excludes coordinate system aliases (handled at component level)

    Raises:
        PINTDiscoveryError: If PINT alias discovery fails
    """
    from loguru import logger

    try:
        all_components = AllComponents()
        alias_map = all_components._param_alias_map

        # Filter out coordinate-related aliases (RAJ/ELONG, etc.)
        # Keep only simple parameter aliases
        simple_aliases = {}
        for alias, canonical in alias_map.items():
            # Skip coordinate system aliases (astrometry parameters)
            if not _is_astrometry_parameter(alias):
                simple_aliases[alias] = canonical

        # Add missing aliases that PINT doesn't have but legacy expects
        simple_aliases["EDOT"] = "ECCDOT"

        logger.debug(f"Discovered {len(simple_aliases)} parameter aliases from PINT")
        return simple_aliases
    except Exception as e:
        logger.error(f"PINT alias discovery failed: {e}")
        # NO FALLBACK - fail gracefully as per SSOT principle
        raise PINTDiscoveryError(f"Failed to discover parameter aliases: {e}")


def check_component_available_in_model(model: TimingModel, component_type: str) -> bool:
    """Check if component type is available in a single PINT model.

    Args:
        model: PINT TimingModel instance
        component_type: Type of component to check ('astrometry', 'spindown', etc.)

    Returns:
        True if component is available in the model
    """
    from loguru import logger

    # Discover category mapping from PINT
    category_mapping = get_category_mapping_from_pint()

    if component_type not in category_mapping:
        logger.warning(f"Unknown component type: {component_type}")
        return False

    target_category = category_mapping[component_type]

    # Check if any component with the target category is available
    for component in model.components.values():
        if hasattr(component, "category") and component.category == target_category:
            logger.debug(f"Found component with category '{target_category}' in model")
            return True

    logger.debug(f"No component with category '{target_category}' found in model")
    return False


def get_parameter_identifiability_from_model(
    model: TimingModel, param_name: str
) -> bool:
    """Check if parameter is identifiable in a single PINT model.

    Args:
        model: PINT TimingModel instance
        param_name: Name of parameter to check

    Returns:
        True if parameter is fittable and free (identifiable)
    """
    from loguru import logger

    # Check if parameter is fittable (has derivatives implemented)
    if param_name not in model.fittable_params:
        logger.debug(f"Parameter '{param_name}' not fittable (no derivatives)")
        return False

    # Check if parameter is free (unfrozen)
    if param_name not in model.free_params:
        logger.debug(f"Parameter '{param_name}' not in free_params")
        return False

    logger.debug(f"Parameter '{param_name}' is identifiable (fittable and free)")
    return True


def _is_astrometry_parameter(param_name: str) -> bool:
    """Check if parameter is astrometry-related by discovering from PINT components."""
    from pint.models.model_builder import AllComponents

    all_components = AllComponents()

    # Get all astrometry components from PINT
    astrometry_components = all_components.category_component_map.get("astrometry", [])

    # Collect all parameters from astrometry components
    astrometry_params = set()
    for component_name in astrometry_components:
        try:
            # Access component from the components dictionary
            component_instance = all_components.components[component_name]
            if hasattr(component_instance, "params"):
                astrometry_params.update(component_instance.params)
        except (KeyError, AttributeError, TypeError, Exception):
            # Component not available or can't be instantiated, continue
            continue

    return param_name in astrometry_params
