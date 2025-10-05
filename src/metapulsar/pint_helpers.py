"""PINT helper functions for parameter discovery and model interaction.

This module provides pure functions that encapsulate PINT-specific logic
for parameter discovery, alias resolution, and model validation.
"""

from typing import Dict, List
from pint.models import TimingModel
from pint.models.model_builder import AllComponents


class PINTDiscoveryError(Exception):
    """Raised when PINT component discovery fails"""


class KeyReturningDict(dict):
    """Dictionary that returns the key itself when key is not found."""

    def __missing__(self, key):
        return key


def get_category_mapping_from_pint() -> Dict[str, str]:
    """Get component category mappings from PINT.

    Returns:
        Dictionary mapping parameter type names to PINT category names
    """
    mapping = {
        "astrometry": "astrometry",
        "spindown": "spindown",
        "binary": "pulsar_system",
        "dispersion": "dispersion_constant",
    }

    return KeyReturningDict(mapping)


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


def get_parameters_by_type_from_parfiles(
    param_type: str, parfile_dicts: Dict[str, Dict]
) -> List[str]:
    """Get parameters by type from parfile dictionaries using PINT, including dynamic derivatives and aliases.

    Args:
        param_type: Type of parameters to discover ('astrometry', 'spindown', etc.)
        parfile_dicts: Dictionary mapping PTA names to parfile dictionaries

    Returns:
        List of parameter names discovered from actual parfiles, including all aliases

    Raises:
        PINTDiscoveryError: If PINT model creation fails
    """
    from loguru import logger

    all_params = set()

    # Get category mapping
    category_mapping = get_category_mapping_from_pint()
    target_category = category_mapping[param_type]

    # Discover parameters from each PTA's actual parfile
    for pta_name, parfile_dict in parfile_dicts.items():
        try:
            # Create PINT model from parfile data using consolidated function
            model = create_pint_model(parfile_dict)

            # Extract parameters for the specific component
            for comp in model.components.values():
                if hasattr(comp, "category") and comp.category == target_category:
                    if hasattr(comp, "params"):
                        all_params.update(comp.params)  # Includes dynamic derivatives!

        except Exception as e:
            logger.warning(f"Failed to parse parfile for PTA {pta_name}: {e}")
            continue

    # Get parameter aliases from PINT
    alias_map = get_parameter_aliases_from_pint()

    # Create reverse mapping: canonical -> all aliases
    canonical_to_aliases = {}
    for alias, canonical in alias_map.items():
        if canonical not in canonical_to_aliases:
            canonical_to_aliases[canonical] = []
        canonical_to_aliases[canonical].append(alias)

    # Build complete parameter list including all aliases
    all_params_with_aliases = set()
    for canonical_param in all_params:
        all_params_with_aliases.add(canonical_param)  # Add canonical name
        if canonical_param in canonical_to_aliases:
            all_params_with_aliases.update(
                canonical_to_aliases[canonical_param]
            )  # Add all aliases

    logger.debug(
        f"Component {param_type}: Found {len(all_params)} canonical parameters, {len(all_params_with_aliases)} total with aliases"
    )
    return list(all_params_with_aliases)


def create_pint_model(parfile_data) -> TimingModel:
    """Create PINT model from parfile data (string or dict).

    Args:
        parfile_data: String content or dictionary representation of parfile

    Returns:
        PINT TimingModel instance

    Raises:
        PINTDiscoveryError: If model creation fails
    """
    from pint.models.model_builder import ModelBuilder
    from pint.exceptions import (
        TimingModelError,
        MissingParameter,
        UnknownParameter,
        UnknownBinaryModel,
        InvalidModelParameters,
        ComponentConflict,
    )
    from io import StringIO
    from loguru import logger

    try:
        builder = ModelBuilder()

        # Handle both string and dict inputs
        if isinstance(parfile_data, str):
            model = builder(StringIO(parfile_data), allow_tcb=True, allow_T2=True)
        else:  # dict
            model = builder(parfile_data, allow_tcb=True, allow_T2=True)

        return model
    except (
        TimingModelError,
        MissingParameter,
        UnknownParameter,
        UnknownBinaryModel,
        InvalidModelParameters,
        ComponentConflict,
    ) as e:
        logger.error(f"PINT model creation failed: {e}")
        raise  # Re-raise the original exception
    except Exception as e:
        logger.error(f"Unexpected error creating PINT model: {e}")
        raise PINTDiscoveryError(f"Unexpected error creating PINT model: {e}")
