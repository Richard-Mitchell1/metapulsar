# MetaPulsar User Guide

## Quick Start

MetaPulsar combines pulsar timing data from multiple PTA collaborations into unified objects for gravitational wave detection.

### Basic Usage

```python
from metapulsar import MetaPulsarFactory, FileDiscoveryService

# Create file discovery service
discovery = FileDiscoveryService()

# Discover files for a pulsar
file_data = discovery.discover_all_files_in_ptas(["epta_dr2", "ppta_dr3"])

# Create factory
factory = MetaPulsarFactory()

# Create MetaPulsar
metapulsar = factory.create_metapulsar(
    file_data,
    combination_strategy="consistent"
)
```

## Core Concepts

### Combination Strategies

1. **Consistent**: Astrophysical consistency across PTAs
   - Aligns parameters to reference PTA values
   - Suitable for unified gravitational wave analysis

2. **Composite**: Multi-PTA composition
   - Uses raw par files without modification
   - Preserves PTA-specific parameter differences
   - Suitable for 'Borg' or 'FrankenStat' analysis methods

### File Discovery

```python
from metapulsar import FileDiscoveryService

# Create file discovery service
discovery = FileDiscoveryService()

# For notebooks or when running from different directories, specify working directory
# discovery = FileDiscoveryService(working_dir="/path/to/project/root")

# List available PTAs
ptas = discovery.list_ptas()
print(f"Available PTAs: {ptas}")

# Discover files for specific PTAs
files = discovery.discover_all_files_in_ptas(["epta_dr1_v2_2", "ppta_dr2"])
```

### Parameter Management

```python
from metapulsar import ParameterManager

# Assuming file_data is obtained from FileDiscoveryService
# and contains paths to par/tim files for multiple PTAs
# For example:
file_data = {
    "epta_dr2": [{"par": "path/to/epta.par", "tim": "path/to/epta.tim"}],
    "ppta_dr3": [{"par": "path/to/ppta.par", "tim": "path/to/ppta.tim"}],
}

param_manager = ParameterManager(
    file_data=file_data,
    reference_pta="epta_dr2",
    combine_components=["astrometry", "spindown", "binary", "dispersion"],
    add_dm_derivatives=True
)

mapping = param_manager.build_parameter_mappings(
    merge_astrometry=True,
    merge_spin=True,
    merge_binary=False
)
```

## Advanced Usage

### Custom PTA Configuration

#### Manual Configuration

```python
# Add custom PTA manually
discovery.add_pta("custom_pta", {
    "base_dir": "/data/custom_pta/",
    "par_pattern": r"([BJ]\d{4}[+-]\d{2,4})_custom\.par",
    "tim_pattern": r"([BJ]\d{4}[+-]\d{2,4})_custom\.tim",
    "timing_package": "pint",
    "priority": 1,
    "description": "Custom PTA for demonstration"
})
```

#### Automatic Pattern Discovery

For new PTA data releases with unknown directory structures, use the Pattern Discovery Engine to automatically generate appropriate regex patterns:

```python
from metapulsar import LayoutDiscoveryService, PTA_DATA_RELEASES

# Initialize layout discovery service
engine = LayoutDiscoveryService()

# Analyze new PTA data structure
data_dir = Path("/path/to/new/pta/data")
structure = engine.analyze_directory_structure(data_dir)
data_release = engine.generate_pta_data_release(structure)

print(f"Discovered patterns:")
print(f"  Par: {data_release['par_pattern']}")
print(f"  Tim: {data_release['tim_pattern']}")
print(f"  Timing: {data_release['timing_package']}")

# Add discovered data release to FileDiscoveryService
PTA_DATA_RELEASES["new_pta"] = {
    "base_dir": str(data_dir),
    "par_pattern": data_release["par_pattern"],
    "tim_pattern": data_release["tim_pattern"],
    "timing_package": data_release["timing_package"],
    "description": "Auto-discovered PTA data release"
}

# Create NEW FileDiscoveryService instance to use the new PTA
discovery = FileDiscoveryService()
files = discovery.discover_all_files_in_ptas(["new_pta"])
```

**Pattern Discovery Engine Features:**
- **Automatic Pattern Generation**: No manual regex writing required
- **Complex Structure Support**: Handles deeply nested directory structures
- **Wideband Data Filtering**: Automatically excludes wideband data files
- **Timing Package Detection**: Auto-detects PINT vs tempo2 from file content
- **High Accuracy**: 100% pattern matching on test data
- **Future-Proof**: Scales to any PTA data release format

For detailed information about the Pattern Discovery Engine, see the [Pattern Discovery Guide](pattern_discovery_guide.md).

### Enterprise Integration

```python
from metapulsar import create_staggered_selection

# Create staggered selection for Enterprise
selection = create_staggered_selection(
    flags=flags,
    freqs=freqs,
    primary_flag="telescope",
    fallback_flags=["backend", "freq_band"],
    freq_bands={"low": (50, 200), "mid": (200, 800), "high": (800, 2000)}
)
```

## Examples

See the `examples/` directory for comprehensive usage examples:
- `basic_workflow.py` - Complete workflow tutorial
- `parameter_management.py` - Parameter management strategies
- `custom_pta_configuration.py` - Custom PTA setup
- `enterprise_integration.py` - Enterprise framework integration

## API Reference

For detailed API documentation, see [API Reference](api_reference.md).

## Troubleshooting

For common issues and solutions, see [Troubleshooting Guide](troubleshooting.md).
