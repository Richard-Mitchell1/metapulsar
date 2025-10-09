"""PINT helper functions for parameter discovery and model interaction.

This module provides pure functions that encapsulate PINT-specific logic
for parameter discovery, alias resolution, and model validation.
"""

from typing import Dict, List
from pint.models import TimingModel
from pint.models.timing_model import AllComponents
from pint.models.parameter import Parameter


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


# Cache for parameter aliases to avoid repeated AllComponents() creation
_parameter_aliases_cache = None


def get_parameter_aliases_from_pint() -> Dict[str, str]:
    """Get parameter aliases from PINT.

    Returns:
        Dictionary mapping aliases to canonical parameter names

    Raises:
        PINTDiscoveryError: If PINT alias discovery fails
    """
    from loguru import logger

    global _parameter_aliases_cache

    # Return cached result if available
    if _parameter_aliases_cache is not None:
        return _parameter_aliases_cache

    try:
        all_components = AllComponents()
        alias_map = all_components._param_alias_map

        # Use all aliases - component-level discovery handles parameter types correctly
        aliases = dict(alias_map)

        # Add missing aliases that PINT doesn't have but legacy expects
        aliases["EDOT"] = "ECCDOT"

        # Cache the result
        _parameter_aliases_cache = aliases

        logger.debug(f"Discovered {len(aliases)} parameter aliases from PINT")
        return aliases
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


def get_parameters_by_type_from_models(
    param_type: str, pint_models: Dict[str, TimingModel]
) -> List[str]:
    """Get parameters by type from PINT models, including dynamic derivatives and aliases.

    Args:
        param_type: Type of parameters to discover ('astrometry', 'spindown', etc.)
        pint_models: Dictionary mapping PTA names to PINT TimingModel instances

    Returns:
        List of parameter names discovered from actual models, including all aliases

    Raises:
        PINTDiscoveryError: If parameter extraction fails
    """
    from loguru import logger

    all_params = set()

    # Get category mapping
    category_mapping = get_category_mapping_from_pint()
    target_category = category_mapping[param_type]

    # Discover parameters from each PTA's actual model
    for pta_name, model in pint_models.items():
        try:
            # Extract parameters for the specific component
            for comp in model.components.values():
                if hasattr(comp, "category") and comp.category == target_category:
                    if hasattr(comp, "params"):
                        all_params.update(comp.params)  # Includes dynamic derivatives!

        except Exception as e:
            logger.warning(
                f"Failed to extract parameters from model for PTA {pta_name}: {e}"
            )
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

    # Create PINT models from parfile dictionaries
    pint_models = {}
    for pta_name, parfile_dict in parfile_dicts.items():
        try:
            pint_models[pta_name] = create_pint_model(parfile_dict)
        except Exception as e:
            logger.warning(f"Failed to create PINT model for PTA {pta_name}: {e}")
            continue

    # Delegate to the models-based function
    return get_parameters_by_type_from_models(param_type, pint_models)


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


def dict_to_parfile_string_pint_driven(parfile_dict: Dict, format: str = "pint") -> str:
    """Convert parfile dictionary to string using PINT's exact formatting.

    Simple approach that preserves ALL parameters without complex categorization.

    Args:
        parfile_dict: Dictionary representation of parfile
        format: Output format ('pint', 'tempo', 'tempo2')

    Returns:
        Formatted parfile string using PINT's exact formatting
    """
    from datetime import datetime

    result = ""

    # Add format headers
    if format.lower() == "tempo2":
        result += "MODE 1\n"
    elif format.lower() == "pint":
        result += "# Created: " + datetime.now().isoformat() + "\n"
        result += "# Format:  PINT\n"
        result += "# By:      MetaPulsar\n"

    # Format ALL parameters using PINT's exact formatting
    for param_name, param_data in parfile_dict.items():
        if len(param_data) >= 1:
            # Handle multiple instances of the same parameter (e.g., multiple JUMP parameters)
            # Multiple instances are detected when we have multiple separate string values
            if isinstance(param_data[0], str) and len(param_data) > 1:
                # Multiple string values - iterate through all of them
                for value in param_data:
                    # Create Parameter object and use PINT's exact formatting
                    param = Parameter()
                    param.name = param_name
                    param.quantity = value
                    param.frozen = True  # Default to frozen for multiple instances

                    result += param.as_parfile_line(format=format)
            else:
                # Single value or list format
                value = param_data[0]
                # Handle different parfile dictionary formats
                if len(param_data) >= 2:
                    frozen = param_data[1] == "0"
                else:
                    frozen = True  # Default to frozen if not specified

                # Create Parameter object and use PINT's exact formatting
                param = Parameter()
                param.name = param_name
                param.quantity = value
                param.frozen = frozen
                # Note: uncertainty cannot be set directly on Parameter object
                # PINT handles uncertainty formatting in as_parfile_line()

                result += param.as_parfile_line(format=format)

    return result


def create_minimal_parfile_for_component(parfile_dict: Dict, component) -> str:
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
