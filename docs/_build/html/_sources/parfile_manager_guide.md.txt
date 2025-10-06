# ParFileManager and MetaPulsarFactory User Guide

**Version**: 1.0  
**Date**: 2025-09-30  
**Author**: MetaPulsar Team

## Overview

The ParFileManager and MetaPulsarFactory classes provide a comprehensive solution for combining pulsar timing data from multiple PTA (Pulsar Timing Array) collaborations. This guide covers the two main combination strategies and their use cases.

## Table of Contents

1. [Introduction](#introduction)
2. [Combination Strategies](#combination-strategies)
3. [ParFileManager Class](#parfilemanager-class)
4. [MetaPulsarFactory Class](#metapulsarfactory-class)
5. [MetaPulsar Class](#metapulsar-class)
6. [Usage Examples](#usage-examples)
7. [Advanced Configuration](#advanced-configuration)
8. [Troubleshooting](#troubleshooting)
9. [API Reference](#api-reference)

## Introduction

The MetaPulsar framework enables the combination of pulsar timing data from multiple PTA collaborations (EPTA, PPTA, NANOGrav, MPTA, etc.) into unified "metapulsar" objects suitable for gravitational wave detection analysis.

### Key Components

- **ParFileManager**: Handles par file operations, unit conversion, and parameter consistency
- **MetaPulsarFactory**: Orchestrates the creation of MetaPulsar objects with different combination strategies
- **MetaPulsar**: The final composite object containing multi-PTA pulsar data
- **PTARegistry**: Manages PTA configurations and file discovery

## Combination Strategies

### 1. Composite Strategy (Borg/FrankenStat Method)

**Purpose**: Preserve PTA-specific parameter differences for analysis methods that require them.

**Characteristics**:
- Uses raw par files without modification
- Preserves individual PTA parameter values
- Suitable for "Borg" or "FrankenStat" analysis methods
- No parameter harmonization performed

**Use Cases**:
- When PTA-specific systematic effects need to be preserved
- For analysis methods that explicitly model PTA differences
- When parameter consistency is not required

### 2. Consistent Strategy (Astrophysical Consistency)

**Purpose**: Create astrophysically consistent par files for unified analysis.

**Characteristics**:
- Modifies par files to ensure parameter consistency
- Aligns parameters to a reference PTA
- Handles unit conversion (TCB ↔ TDB)
- Manages DM parameter derivatives

**Use Cases**:
- For unified gravitational wave analysis
- When parameter consistency is required
- For cross-PTA comparison studies

## ParFileManager Class

The `ParFileManager` class handles all par file operations for the consistent strategy.

### Key Methods

#### `write_consistent_parfiles()`

Creates astrophysically consistent par files for multiple PTAs.

```python
consistent_files = parfile_manager.write_consistent_parfiles(
    pulsar_name="J1909-3744",
    pta_names=["epta_dr2", "ppta_dr2", "nanograv_15y"],
    reference_pta="epta_dr2",
    combine_components=["spin", "astrometry", "binary", "dispersion"],
    add_dm_derivatives=True,
    output_dir=Path("/output/consistent/")
)
```

**Parameters**:
- `pulsar_name`: Name of the pulsar (e.g., "J1909-3744")
- `pta_names`: List of PTA names to combine
- `reference_pta`: PTA to use as reference for parameter values
- `combine_components`: List of parameter components to make consistent
- `add_dm_derivatives`: Whether to add DM1, DM2 parameters
- `output_dir`: Directory to save consistent par files

**Returns**: Dictionary mapping PTA names to output file paths

### Component Types

The `combine_components` parameter accepts these component types:

- `"spin"`: Spin parameters (F0, F1, F2, etc.)
- `"astrometry"`: Astrometric parameters (RA, DEC, PMRA, PMDEC, etc.)
- `"binary"`: Binary system parameters (PB, A1, E, etc.)
- `"dispersion"`: Dispersion measure parameters (DM, DM1, DM2, etc.)

### DM Parameter Handling

When `add_dm_derivatives=True`:
- DMX parameters are removed from all PTAs
- DM1 and DM2 are added if not present
- All DM parameters are aligned to reference PTA values

When `add_dm_derivatives=False`:
- DMX parameters are removed from all PTAs
- Existing DM1, DM2 are aligned to reference PTA values
- No new DM derivatives are added

**Note**: `add_dm_derivatives=True` requires `"dispersion"` in `combine_components`.

## MetaPulsarFactory Class

The `MetaPulsarFactory` class orchestrates the creation of MetaPulsar objects.

### Key Methods

#### `create_metapulsar()`

Creates a MetaPulsar object with the specified combination strategy.

```python
metapulsar = factory.create_metapulsar(
    pulsar_name="J1909-3744",
    pta_names=["epta_dr2", "ppta_dr2", "nanograv_15y"],
    combination_strategy="consistent",  # or "composite"
    reference_pta="epta_dr2",
    combine_components=["spin", "astrometry", "binary", "dispersion"],
    add_dm_derivatives=True
)
```

#### `list_available_pulsars()`

Lists pulsars available in the specified PTAs.

```python
available_pulsars = factory.list_available_pulsars(["epta_dr2", "ppta_dr2"])
```

### Constructor Parameters

```python
factory = MetaPulsarFactory(
    registry=PTARegistry(),  # Custom PTA registry
    parfile_manager=ParFileManager()  # Custom parfile manager
)
```

## MetaPulsar Class

The `MetaPulsar` class represents the final composite pulsar object.

### Constructor Parameters

```python
metapulsar = MetaPulsar(
    pulsars=enterprise_pulsars,  # Dictionary of PTA -> Enterprise Pulsar
    combination_strategy="composite",  # Strategy used
    sort=True,  # Sort data by time
    planets=True,  # Model solar system planets
    # ... other parameters
)
```

### Combination Strategy Methods

```python
# Get the combination strategy
strategy = metapulsar.get_combination_strategy()

# Check if using composite strategy
is_composite = metapulsar.combination_strategy == "composite"

# Check if using consistent strategy
is_consistent = metapulsar.combination_strategy == "consistent"
```

## Usage Examples

### Basic Usage

```python
from metapulsar import MetaPulsarFactory

# Create factory
factory = MetaPulsarFactory()

# List available pulsars
available_pulsars = factory.list_available_pulsars()
print(f"Available pulsars: {available_pulsars}")

# Create MetaPulsar with composite approach
metapulsar = factory.create_metapulsar(
    "J1909-3744", 
    ["epta_dr2", "ppta_dr2", "nanograv_15y"]
)

# Create MetaPulsar with consistent approach
metapulsar_consistent = factory.create_metapulsar(
    "J1909-3744", 
    ["epta_dr2", "ppta_dr2", "nanograv_15y"],
    combination_strategy="consistent",
    reference_pta="epta_dr2"
)
```

### Custom PTA Registry

```python
from metapulsar import PTARegistry, MetaPulsarFactory

# Create custom PTA registry
custom_registry = PTARegistry()

# Add custom PTA
custom_registry.add_pta("custom_pta", {
    "base_dir": "/data/custom_pta/",
    "par_pattern": r"([BJ]\d{4}[+-]\d{2,4})_custom\.par",
    "tim_pattern": r"([BJ]\d{4}[+-]\d{2,4})_custom\.tim",
    "timing_package": "pint",
    "priority": 1,
    "description": "Custom PTA with specific naming convention"
})

# Create factory with custom registry
factory = MetaPulsarFactory(registry=custom_registry)

# Use custom PTAs
metapulsar = factory.create_metapulsar(
    "J1909-3744", 
    ["custom_pta"],
    combination_strategy="composite"
)
```

### Advanced Configuration

```python
# Custom astrophysical consistency
metapulsar = factory.create_metapulsar(
    "J1909-3744", 
    ["epta_dr2", "ppta_dr2", "nanograv_15y"],
    combination_strategy="consistent",
    reference_pta="epta_dr2",
    combine_components=["spin", "astrometry"],  # Only these components
    add_dm_derivatives=True  # Add DM1, DM2
)

# No DM derivatives
metapulsar_no_dm = factory.create_metapulsar(
    "J1909-3744", 
    ["epta_dr2", "ppta_dr2", "nanograv_15y"],
    combination_strategy="consistent",
    reference_pta="epta_dr2",
    combine_components=["spin", "astrometry", "binary", "dispersion"],
    add_dm_derivatives=False  # Align existing DM1, DM2 only
)
```

### Direct ParFileManager Usage

```python
from metapulsar import ParFileManager
from pathlib import Path

# Create ParFileManager
parfile_manager = ParFileManager()

# Create consistent par files
consistent_files = parfile_manager.write_consistent_parfiles(
    "J1909-3744",
    ["epta_dr2", "ppta_dr2"],
    reference_pta="epta_dr2",
    combine_components=["spin", "astrometry", "binary", "dispersion"],
    add_dm_derivatives=True,
    output_dir=Path("/output/consistent/")
)

print(f"Created files: {consistent_files}")
```

## Advanced Configuration

### PTA Registry Configuration

The `PTARegistry` class manages PTA configurations:

```python
from metapulsar import PTARegistry

# Create empty registry
registry = PTARegistry(configs={})

# Add PTA configuration
registry.add_pta("my_pta", {
    "base_dir": "/data/my_pta/",
    "par_pattern": r"([BJ]\d{4}[+-]\d{2,4})\.par",
    "tim_pattern": r"([BJ]\d{4}[+-]\d{2,4})\.tim",
    "timing_package": "pint",  # or "tempo2"
    "priority": 1,
    "description": "My custom PTA"
})
```

### File Pattern Configuration

Par file patterns use regex with capture groups for pulsar names:

```python
# Example patterns
patterns = {
    "epta_dr2": r"([BJ]\d{4}[+-]\d{2,4})\.par",
    "ppta_dr2": r"([BJ]\d{4}[+-]\d{2,4})\.par", 
    "nanograv_15y": r"([BJ]\d{4}[+-]\d{2,4})\.par",
    "custom_pta": r"pulsar_([BJ]\d{4}[+-]\d{2,4})_custom\.par"
}
```

## Troubleshooting

### Common Issues

1. **File Not Found Errors**
   - Check PTA registry configuration
   - Verify file patterns match actual file names
   - Ensure base directories are correct

2. **Unit Conversion Warnings**
   - Normal when mixing TCB and TDB units
   - Check if conversion is actually needed

3. **DM Derivatives Warning**
   - Occurs when `add_dm_derivatives=True` but `"dispersion"` not in `combine_components`
   - Add `"dispersion"` to `combine_components` or set `add_dm_derivatives=False`

4. **Parameter Discovery Errors**
   - Check PINT installation and version
   - Verify par file format compatibility

### Debug Mode

Enable debug logging:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Validation

Check if files exist before processing:

```python
# List available pulsars first
available = factory.list_available_pulsars()
if "J1909-3744" not in available:
    print("Pulsar not available in any PTA")
```

## API Reference

### ParFileManager

#### `__init__(self, registry: PTARegistry = None)`
Initialize ParFileManager with optional PTA registry.

#### `write_consistent_parfiles(self, pulsar_name: str, pta_names: List[str], reference_pta: str, combine_components: List[str] = ["astrometry", "spin", "binary", "dispersion"], add_dm_derivatives: bool = False, output_dir: Path = None) -> Dict[str, Path]`
Create astrophysically consistent par files.

### MetaPulsarFactory

#### `__init__(self, registry: PTARegistry = None, parfile_manager: ParFileManager = None)`
Initialize factory with optional registry and parfile manager.

#### `create_metapulsar(self, pulsar_name: str, pta_names: List[str], combination_strategy: str = "composite", reference_pta: str = None, combine_components: List[str] = ["astrometry", "spin", "binary", "dispersion"], add_dm_derivatives: bool = False) -> MetaPulsar`
Create MetaPulsar with specified strategy.

#### `list_available_pulsars(self, pta_names: List[str] = None) -> List[str]`
List available pulsars in specified PTAs.

### MetaPulsar

#### `__init__(self, pulsars: Dict[str, Union[Tuple, object]], combination_strategy: str = "composite", **kwargs)`
Initialize MetaPulsar with pulsar data and combination strategy.

#### `get_combination_strategy(self) -> str`
Get the combination strategy used.

**Note**: You can also access the strategy directly via `metapulsar.combination_strategy`.

---

For more examples, see `examples/parfile_manager_usage.py`.

For technical details, see the feature proposal: `ai/prompts/active/2025-09-30-parfile-manager-multi-pta-combination-feature-proposal.md`.
