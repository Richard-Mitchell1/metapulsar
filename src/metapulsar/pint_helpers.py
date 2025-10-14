"""PINT helper functions for parameter discovery and model interaction.

This module provides pure functions that encapsulate PINT-specific logic
for parameter discovery, alias resolution, and model validation.
"""

from typing import Dict, List, Tuple, Any
from functools import lru_cache
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


def get_extra_top_level_params_for_category() -> Dict[str, List[str]]:
    """Return extra top-level parameters to include per logical component.

    Some parameters (e.g., BINARY) are defined at the TimingModel top level in
    PINT and are not listed under any component's ``params``. This registry
    allows discovery to include such parameters in a declarative way.
    """
    return {
        "binary": ["BINARY"],
    }


@lru_cache(maxsize=1)
def _get_all_components():
    """Get cached AllComponents instance.

    Uses lru_cache to ensure AllComponents() is only created once,
    avoiding the ~10ms creation cost on subsequent calls.
    """
    return AllComponents()


def resolve_parameter_alias(param_name: str) -> str:
    """Resolve a single parameter alias to canonical name using cached AllComponents.

    This function provides fast on-demand alias resolution by leveraging the
    cached AllComponents instance, avoiding the 12.9ms creation cost.

    Args:
        param_name: Parameter name that might be an alias

    Returns:
        Canonical parameter name, or original name if not an alias
    """
    # Handle special case: EDOT -> ECCDOT alias that PINT doesn't have
    if param_name == "EDOT":
        return "ECCDOT"

    try:
        all_components = _get_all_components()
        canonical, _ = all_components.alias_to_pint_param(param_name)
        return canonical
    except Exception:
        # If alias resolution fails, return the original name
        return param_name


def get_aliases_for_parameter(canonical_param: str) -> List[str]:
    """Get all aliases for a canonical parameter name.

    Args:
        canonical_param: The canonical parameter name

    Returns:
        List of all aliases for this parameter, including the canonical name itself
    """
    try:
        all_components = _get_all_components()
        aliases = [canonical_param]  # Start with canonical name

        # Search through the alias map to find all aliases that map to this canonical name
        alias_map = all_components._param_alias_map
        for alias, canonical in alias_map.items():
            if canonical == canonical_param and alias != canonical_param:
                aliases.append(alias)

        # Handle special case: if canonical is ECCDOT, also include EDOT
        if canonical_param == "ECCDOT" and "EDOT" not in aliases:
            aliases.append("EDOT")

        return aliases
    except Exception:
        # If anything fails, just return the canonical name
        return [canonical_param]


def clear_all_components_cache():
    """Clear the AllComponents cache.

    This is useful for testing to ensure clean state between tests.
    """
    _get_all_components.cache_clear()


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

    # Build complete parameter list including all aliases
    all_params_with_aliases = set()
    for canonical_param in all_params:
        # Get all aliases for this canonical parameter
        aliases = get_aliases_for_parameter(canonical_param)
        all_params_with_aliases.update(aliases)

    # Include extra top-level params for this category if present on any model
    for extra in get_extra_top_level_params_for_category().get(param_type, []):
        # Add the extra only if at least one model has it set
        for tm in pint_models.values():
            if hasattr(tm, extra):
                try:
                    if getattr(tm, extra).value is not None:
                        all_params_with_aliases.add(extra)
                        break
                except Exception:
                    # Be robust to any attribute access issues
                    pass

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


def dict_to_parfile_string(parfile_dict: Dict, format: str = "pint") -> str:
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


def parse_parameter_using_pint(param_name: str, param_value) -> Tuple[Any, bool]:
    """Parse parameter value using PINT's parsing approach.

    This function elegantly handles parfile parameter parsing by extracting
    the parsing logic from PINT's Parameter.from_parfile_line() method.
    It handles the common parfile format of "value fit_status uncertainty" where:
    - value: the parameter value (float for numeric params, string for text params)
    - fit_status: 0=frozen, 1=free (int)
    - uncertainty: optional uncertainty value

    Args:
        param_name: Name of the parameter (e.g., "DM", "DMEPOCH", "UNITS")
        param_value: Parameter value from parfile dict (string or list)

    Returns:
        Tuple of (parsed_value, is_frozen)

    Raises:
        ValueError: If parameter cannot be parsed

    Examples:
        >>> parse_parameter_using_pint("DM", ["123.45 1 0.01"])
        (123.45, False)
        >>> parse_parameter_using_pint("DMEPOCH", ["55000 0"])
        (55000.0, True)
        >>> parse_parameter_using_pint("UNITS", ["TCB 0"])
        ("TCB", True)
    """
    # Handle list format from parse_parfile
    if isinstance(param_value, list):
        param_str = param_value[0]
    else:
        param_str = str(param_value)

    # Split the parameter string into components
    parts = param_str.split()

    if not parts:
        raise ValueError(f"Empty parameter value for {param_name}: {param_value}")

    # Parse value (first component)
    value = parts[0]

    # Try to convert to float for numeric parameters, keep as string for text parameters
    try:
        value = float(value)
    except ValueError:
        # Keep as string for non-numeric parameters like UNITS
        pass

    # Parse fit_status (second component, default to free if not specified)
    is_frozen = False  # Default to free
    if len(parts) > 1:
        try:
            fit_status = int(parts[1])
            is_frozen = fit_status == 0
        except ValueError:
            # If second part is not an integer, treat as uncertainty and assume free
            pass

    return value, is_frozen
