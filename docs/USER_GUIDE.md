# MetaPulsar User Guide

Complete guide to using MetaPulsar for multi-PTA pulsar timing data combination.

## Overview

MetaPulsar combines pulsar timing data from multiple PTA collaborations into unified Enterprise pulsar objects. This enables gravitational wave detection analysis using data from EPTA, PPTA, NANOGrav, MPTA, and other PTAs.

## Installation

```bash
# Basic installation
pip install -e .

# With optional dependencies
pip install -e ".[dev,libstempo,analysis]"
```

## Core Workflow

### 1. Data Preparation

#### Manual Single-Pulsar Setup

For single pulsars, manually create the data structure:

```python
pulsar_data = {
    "epta_dr2": [
        {
            "par": "path/to/J0613-0200.par",
            "tim": "path/to/J0613-0200.tim",
            "timing_package": "tempo2",
        }
    ],
    "nanograv_9y": [
        {
            "par": "path/to/J0613-0200.par",
            "tim": "path/to/J0613-0200.tim",
            "timing_package": "pint",
        }
    ],
    "ppta_dr2": [
        {
            "par": "path/to/J0613-0200.par",
            "tim": "path/to/J0613-0200.tim",
            "timing_package": "tempo2",
        }
    ],
}
```

#### Automated Multi-Pulsar Discovery

For multiple pulsars, use automated discovery:

```python
from metapulsar import discover_files, discover_layout, combine_layouts

# Discover layouts
epta_layout = discover_layout('data/ipta-dr2/EPTA_v2.2')
ppta_layout = discover_layout('data/ipta-dr2/PPTA_dr1dr2')
nanograv_layout = discover_layout('data/ipta-dr2/NANOGrav_9y')

# Combine layouts
combined_layout = combine_layouts(epta_layout, ppta_layout, nanograv_layout)

# Discover files
file_data = discover_files(combined_layout)
```

### 2. MetaPulsar Creation

#### Basic Creation

```python
from metapulsar import MetaPulsarFactory

factory = MetaPulsarFactory()
metapulsar = factory.create_metapulsar(
    file_data=pulsar_data,
    combination_strategy="consistent",
    combine_components=["astrometry", "spindown", "binary", "dispersion"],
    add_dm_derivatives=True,
)
```

#### Combination Strategies

**Consistent Strategy** (Recommended):
- Merges compatible parameters across PTAs
- Inherits reference PTA values for merged components
- Creates physically meaningful unified model

**Composite Strategy** (Not Recommended):
- Keeps all parameters separate with PTA suffixes
- Not physically meaningful for gravitational wave analysis

#### Component Merging

Control which parameter types are merged:

- `astrometry`: Position, proper motion, parallax
- `spindown`: Spin frequency and derivatives
- `binary`: Binary orbital parameters
- `dispersion`: Dispersion measure and derivatives

### 3. Reference PTA Selection

The reference PTA determines which parameter values are inherited for merged components.

#### Auto-Selection (Default)

```python
# Automatically select PTA with longest timespan per pulsar
metapulsars = factory.create_all_metapulsars(file_data, reference_pta=None)
```

#### Global Reference

```python
# Use same PTA as reference for all pulsars
metapulsars = factory.create_all_metapulsars(file_data, reference_pta="epta_dr2")
```

#### Manual Selection

```python
# Specify reference PTA per pulsar
metapulsars = factory.create_all_metapulsars(file_data, reference_pta="epta_dr2")
```

### 4. Enterprise Integration

MetaPulsar objects are fully compatible with Enterprise:

```python
# Access combined data
print(f"Number of TOAs: {len(metapulsar.toas)}")
print(f"Frequency range: {metapulsar.freqs.min():.2f} - {metapulsar.freqs.max():.2f} MHz")
print(f"Time span: {(metapulsar.toas.max() - metapulsar.toas.min())/86400.0:.1f} days")

# Access parameters
print(f"Fit parameters: {metapulsar.fitpars}")
print(f"Design matrix: {metapulsar.Mmat}")
```

## Parameter Naming

MetaPulsar uses clear naming conventions:

- **Merged parameters**: No suffix (e.g., `RAJ`, `DECJ`, `F0`)
- **PTA-specific parameters**: Retain PTA suffix (e.g., `JUMP1_nanograv_9y`, `FD1_epta_dr2`)

## Advanced Usage

### Custom PTA Configuration

```python
from metapulsar import FileDiscoveryService

discovery = FileDiscoveryService(working_dir="data/ipta-dr2")

# Add custom PTA
custom_config = {
    "base_dir": "/path/to/custom_pta",
    "par_pattern": r"([BJ]\d{4}[+-]\d{2,4})_custom\.par",
    "tim_pattern": r"([BJ]\d{4}[+-]\d{2,4})_custom\.tim",
    "timing_package": "pint",
    "priority": 1,
    "description": "Custom PTA dataset"
}

discovery.add_pta("custom_pta", custom_config)
```

### Parameter Management

```python
from metapulsar import ParameterManager

param_manager = ParameterManager(
    file_data=file_data,
    reference_pta="epta_dr2",
    combine_components=["astrometry", "spindown", "binary", "dispersion"],
    add_dm_derivatives=True
)

mapping = param_manager.build_parameter_mappings()
```

## Troubleshooting

### Common Issues

1. **File not found**: Check file paths and directory structure
2. **Parameter conflicts**: Verify timing package compatibility
3. **Memory issues**: Process pulsars in smaller batches
4. **Timing package errors**: Ensure correct timing package specification

### Debug Mode

```python
import loguru
loguru.logger.remove()
loguru.logger.add(sys.stdout, level="DEBUG")
```

## Examples

- **Basic Workflow**: `examples/basic_workflow.py`
- **Parameter Management**: `examples/parameter_management.py`
- **Custom PTA Configuration**: `examples/custom_pta_configuration.py`
- **Enterprise Integration**: `examples/enterprise_integration.py`
- **Interactive Tutorials**: `examples/notebooks/`

## API Reference

See `docs/API_REFERENCE.md` for complete API documentation.

## Support

- **Issues**: [GitHub Issues](https://github.com/vhaasteren/metapulsar/issues)
- **Email**: [rutger@vhaasteren.com](mailto:rutger@vhaasteren.com)
- **Documentation**: [Read the Docs](https://metapulsar.readthedocs.io)

