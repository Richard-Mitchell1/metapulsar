# MetaPulsar Quick Guide

A minimal guide to combining pulsar timing data from multiple PTA collaborations.

## What is MetaPulsar?

MetaPulsar combines pulsar timing data from multiple PTA collaborations (EPTA, PPTA, NANOGrav, MPTA, etc.) into unified "metapulsar" objects for gravitational wave detection analysis.

## Key Concepts

- **Reference PTA**: The PTA whose parameters are inherited by the MetaPulsar for merged model components
- **Consistent Strategy**: Merges compatible parameters from different PTAs where possible
- **Component Merging**: Controls which parameter types (astrometry, spindown, binary, dispersion) are merged
- **Parameter Naming**: Merged parameters have no suffix, PTA-specific parameters retain PTA suffixes

## Part 1: Manual Single-Pulsar Setup

### Data Structure

```python
pulsar_data = {
    "epta_dr2": [{"par": "path/to/file.par", "tim": "path/to/file.tim", "timing_package": "tempo2"}],
    "nanograv_9y": [{"par": "path/to/file.par", "tim": "path/to/file.tim", "timing_package": "pint"}],
    "ppta_dr2": [{"par": "path/to/file.par", "tim": "path/to/file.tim", "timing_package": "tempo2"}],
}
```

### Create MetaPulsar

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

## Part 2: Automated Multi-Pulsar Processing

### Discover Files

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

### Create All MetaPulsars

```python
# Filter to specific pulsars
from metapulsar import get_pulsar_names_from_file_data, filter_file_data_by_pulsars

pulsar_selection = ['B1855+09', 'J1939+2135', 'J0030+0451']
filtered_data = filter_file_data_by_pulsars(file_data, pulsar_selection)

# Create MetaPulsars
metapulsars = factory.create_all_metapulsars(filtered_data, reference_pta=None)
```

## Part 3: Enterprise Integration

The resulting MetaPulsar is a fully functional Enterprise pulsar:

```python
# Access combined data
print(f"Number of TOAs: {len(metapulsar.toas)}")
print(f"Frequency range: {metapulsar.freqs.min():.2f} - {metapulsar.freqs.max():.2f} MHz")
print(f"Time span: {(metapulsar.toas.max() - metapulsar.toas.min())/86400.0:.1f} days")

# Parameter naming
print("Merged parameters (no suffix):", [p for p in metapulsar.fitpars if not any(suffix in p for suffix in ['_epta_dr2', '_nanograv_9y', '_ppta_dr2'])])
print("PTA-specific parameters (with suffix):", [p for p in metapulsar.fitpars if any(suffix in p for suffix in ['_epta_dr2', '_nanograv_9y', '_ppta_dr2'])])
```

## Reference PTA Selection

- **Auto-selection**: Choose PTA with longest timespan per pulsar (default)
- **Global reference**: Use same PTA for all pulsars
- **Manual**: Specify reference PTA per pulsar

```python
# Auto-select reference PTA (default)
metapulsars = factory.create_all_metapulsars(file_data, reference_pta=None)

# Use specific PTA as reference
metapulsars = factory.create_all_metapulsars(file_data, reference_pta="epta_dr2")
```

## Installation

```bash
pip install -e .
```

## Next Steps

- See `examples/notebooks/using_metapulsar.ipynb` for detailed examples
- Check `examples/` directory for more usage patterns
- Read full documentation in `docs/` directory

