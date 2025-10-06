# Enterprise Integration Guide for Staggered Selection Utilities

This guide provides detailed instructions for integrating the staggered selection utilities with Enterprise for pulsar timing analysis.

## Table of Contents

- [Overview](#overview)
- [Basic Integration](#basic-integration)
- [Advanced Usage Patterns](#advanced-usage-patterns)
- [Model Building Examples](#model-building-examples)
- [Performance Optimization](#performance-optimization)
- [Troubleshooting](#troubleshooting)
- [Best Practices](#best-practices)

## Overview

The staggered selection utilities are designed to work seamlessly with Enterprise's `Selection` class, providing a modern, well-documented API for creating selection functions. This guide covers everything from basic integration to advanced model building scenarios.

### Key Benefits

- **Enterprise Compatibility**: Full compatibility with `enterprise.signals.selections.Selection`
- **Hierarchical Selection**: Support for staggered selection with automatic fallback
- **Frequency Filtering**: Optional frequency band filtering
- **Type Safety**: Complete type hints for better IDE support
- **Performance**: Efficient numpy-based operations

## Basic Integration

### Simple Selection

```python
from enterprise.signals.selections import Selection
from enterprise.signals import white_signals
from metapulsar.selection_utils import create_staggered_selection

# Create a simple group-based selection
group_sel = create_staggered_selection("efac", {"group": None})

# Wrap with Enterprise Selection
efac_selection = Selection(group_sel)

# Use in Enterprise model
white_signal = white_signals.MeasurementNoise(
    efac=efac_selection,
    log10_efac=Uniform(-10, 10)
)
```

### Staggered Selection

```python
# Create staggered selection with fallback
staggered_sel = create_staggered_selection("ecorr", {("group", "f"): None})

# Wrap with Enterprise Selection
ecorr_selection = Selection(staggered_sel)

# Use in Enterprise model
white_signal = white_signals.MeasurementNoise(
    ecorr=ecorr_selection,
    log10_ecorr=Uniform(-10, 10)
)
```

### Frequency Band Selection

```python
# Create frequency band selection
band_sel = create_staggered_selection(
    "band", 
    {"group": None}, 
    freq_range=(400, 1000)  # 400-1000 MHz
)

# Wrap with Enterprise Selection
band_selection = Selection(band_sel)

# Use in Enterprise model
white_signal = white_signals.MeasurementNoise(
    efac=band_selection,
    log10_efac=Uniform(-10, 10)
)
```

## Advanced Usage Patterns

### Multiple Selection Criteria

```python
# Create multiple selections for different purposes
efac_sel = create_staggered_selection("efac", {"group": None})
ecorr_sel = create_staggered_selection("ecorr", {("group", "f"): None})
band_sel = create_staggered_selection("band", {"group": None}, freq_range=(400, 1000))

# Wrap with Enterprise Selections
efac_selection = Selection(efac_sel)
ecorr_selection = Selection(ecorr_sel)
band_selection = Selection(band_sel)

# Use in Enterprise model
white_signal = white_signals.MeasurementNoise(
    efac=efac_selection,
    ecorr=ecorr_selection,
    log10_efac=Uniform(-10, 10),
    log10_ecorr=Uniform(-10, 10)
)
```

### PTA-Specific Selections

```python
# Create PTA-specific selections
def create_pta_selections():
    """Create selections specific to each PTA."""
    
    # EPTA-specific selection
    epta_sel = create_staggered_selection("efac", {"pta": "EPTA"})
    
    # PPTA-specific selection with fallback
    ppta_sel = create_staggered_selection("efac", {("pta", "group"): "PPTA"})
    
    # NANOGrav-specific selection
    nanograv_sel = create_staggered_selection("efac", {"pta": "NANOGrav"})
    
    return {
        'EPTA': Selection(epta_sel),
        'PPTA': Selection(ppta_sel),
        'NANOGrav': Selection(nanograv_sel)
    }

# Use in model
pta_selections = create_pta_selections()
white_signal = white_signals.MeasurementNoise(
    efac=pta_selections['EPTA'],
    log10_efac=Uniform(-10, 10)
)
```

### Complex Staggered Selection

```python
# Create complex staggered selection with multiple fallbacks
complex_sel = create_staggered_selection("efac", {
    ("group", "f", "B"): None,  # Triple fallback
    "pta": "EPTA"  # PTA-specific
})

# Wrap with Enterprise Selection
complex_selection = Selection(complex_sel)

# Use in Enterprise model
white_signal = white_signals.MeasurementNoise(
    efac=complex_selection,
    log10_efac=Uniform(-10, 10)
)
```

## Model Building Examples

### Basic Pulsar Model

```python
from enterprise.pulsar import Pulsar
from enterprise.signals import white_signals, red_signals
from enterprise.models import model_singlepsr_noise
from metapulsar.selection_utils import create_staggered_selection

# Load pulsar data
psr = Pulsar(parfile, timfile)

# Create selections
efac_sel = create_staggered_selection("efac", {"group": None})
ecorr_sel = create_staggered_selection("ecorr", {("group", "f"): None})

# Create white noise signal
white_signal = white_signals.MeasurementNoise(
    efac=Selection(efac_sel),
    ecorr=Selection(ecorr_sel),
    log10_efac=Uniform(-10, 10),
    log10_ecorr=Uniform(-10, 10)
)

# Create red noise signal
red_signal = red_signals.RedNoise(
    log10_A=Uniform(-20, -11),
    gamma=Uniform(0, 7)
)

# Build model
model = model_singlepsr_noise(psr, white_signal, red_signal)
```

### Multi-PTA Model

```python
from enterprise.pulsar import Pulsar
from enterprise.signals import white_signals, red_signals, gp_signals
from enterprise.models import model_singlepsr_noise
from metapulsar.selection_utils import create_staggered_selection

def create_multi_pta_model(psr):
    """Create a model with multi-PTA selections."""
    
    # Create PTA-specific selections
    pta_efac_sel = create_staggered_selection("efac", {"pta": None})
    pta_ecorr_sel = create_staggered_selection("ecorr", {("pta", "group"): None})
    
    # Create backend-specific selections
    backend_sel = create_staggered_selection("efac", {("backend", "group"): None})
    
    # Create frequency band selections
    low_band_sel = create_staggered_selection(
        "band_low", {"group": None}, freq_range=(100, 500)
    )
    high_band_sel = create_staggered_selection(
        "band_high", {"group": None}, freq_range=(1000, 2000)
    )
    
    # Create white noise signal
    white_signal = white_signals.MeasurementNoise(
        efac=Selection(pta_efac_sel),
        ecorr=Selection(pta_ecorr_sel),
        log10_efac=Uniform(-10, 10),
        log10_ecorr=Uniform(-10, 10)
    )
    
    # Create red noise signal
    red_signal = red_signals.RedNoise(
        log10_A=Uniform(-20, -11),
        gamma=Uniform(0, 7)
    )
    
    # Create GWB signal
    gwb_signal = gp_signals.FourierBasisGP(
        log10_A=Uniform(-18, -14),
        gamma=Uniform(4, 5)
    )
    
    # Build model
    model = model_singlepsr_noise(psr, white_signal, red_signal, gwb_signal)
    
    return model

# Use the model
psr = Pulsar(parfile, timfile)
model = create_multi_pta_model(psr)
```

### Custom Selection Factory

```python
class SelectionFactory:
    """Factory for creating standardized selections."""
    
    @staticmethod
    def create_efac_selection(flag_criteria=None, freq_range=None):
        """Create standardized EFAC selection."""
        if flag_criteria is None:
            flag_criteria = {"group": None}
        
        sel_func = create_staggered_selection("efac", flag_criteria, freq_range)
        return Selection(sel_func)
    
    @staticmethod
    def create_ecorr_selection(flag_criteria=None, freq_range=None):
        """Create standardized ECORR selection."""
        if flag_criteria is None:
            flag_criteria = {("group", "f"): None}
        
        sel_func = create_staggered_selection("ecorr", flag_criteria, freq_range)
        return Selection(sel_func)
    
    @staticmethod
    def create_band_selection(band_name, freq_range, flag_criteria=None):
        """Create frequency band selection."""
        if flag_criteria is None:
            flag_criteria = {"group": None}
        
        sel_func = create_staggered_selection(band_name, flag_criteria, freq_range)
        return Selection(sel_func)

# Use the factory
factory = SelectionFactory()

# Create standardized selections
efac_sel = factory.create_efac_selection()
ecorr_sel = factory.create_ecorr_selection()
low_band_sel = factory.create_band_selection("low_band", (100, 500))
high_band_sel = factory.create_band_selection("high_band", (1000, 2000))

# Use in model
white_signal = white_signals.MeasurementNoise(
    efac=efac_sel,
    ecorr=ecorr_sel,
    log10_efac=Uniform(-10, 10),
    log10_ecorr=Uniform(-10, 10)
)
```

## Performance Optimization

### Memory Optimization

```python
# For large datasets, consider chunked processing
def process_large_dataset(psr, chunk_size=10000):
    """Process large dataset in chunks."""
    
    n_toas = len(psr.toas)
    selections = []
    
    for i in range(0, n_toas, chunk_size):
        end_idx = min(i + chunk_size, n_toas)
        
        # Create chunk-specific selections
        chunk_sel = create_staggered_selection("efac", {"group": None})
        selections.append(Selection(chunk_sel))
    
    return selections
```

### Computational Optimization

```python
# Pre-compute selections for repeated use
class CachedSelectionFactory:
    """Factory with caching for repeated selections."""
    
    def __init__(self):
        self._cache = {}
    
    def get_selection(self, name, flag_criteria, freq_range=None):
        """Get cached selection or create new one."""
        cache_key = (name, str(flag_criteria), freq_range)
        
        if cache_key not in self._cache:
            sel_func = create_staggered_selection(name, flag_criteria, freq_range)
            self._cache[cache_key] = Selection(sel_func)
        
        return self._cache[cache_key]

# Use cached factory
factory = CachedSelectionFactory()
efac_sel = factory.get_selection("efac", {"group": None})
```

### Batch Processing

```python
# Process multiple pulsars efficiently
def process_multiple_pulsars(pulsar_list):
    """Process multiple pulsars with shared selections."""
    
    # Create shared selections
    efac_sel = create_staggered_selection("efac", {"group": None})
    ecorr_sel = create_staggered_selection("ecorr", {("group", "f"): None})
    
    # Wrap with Enterprise Selections
    efac_selection = Selection(efac_sel)
    ecorr_selection = Selection(ecorr_sel)
    
    # Create models for all pulsars
    models = []
    for psr in pulsar_list:
        white_signal = white_signals.MeasurementNoise(
            efac=efac_selection,
            ecorr=ecorr_selection,
            log10_efac=Uniform(-10, 10),
            log10_ecorr=Uniform(-10, 10)
        )
        
        model = model_singlepsr_noise(psr, white_signal)
        models.append(model)
    
    return models
```

## Troubleshooting

### Common Issues

#### 1. Selection Not Working

**Problem**: Selection returns empty results
```python
result = sel_func(flags, freqs)  # Returns: {}
```

**Debugging**:
```python
# Check flag values
print(f"Available flags: {list(flags.keys())}")
for flag_name, values in flags.items():
    print(f"{flag_name}: {np.unique(values)}")

# Check frequency range
print(f"Frequency range: {freqs.min():.1f} - {freqs.max():.1f}")

# Test with simple criteria
simple_sel = create_staggered_selection("test", {"group": None})
result = simple_sel(flags, freqs)
print(f"Simple selection result: {result}")
```

#### 2. Enterprise Integration Issues

**Problem**: Selection doesn't work with Enterprise
```python
# TypeError: selection_function() missing 1 required positional argument
```

**Solution**:
```python
# Ensure correct function signature
def test_selection_function(flags, freqs):
    """Test function with correct signature."""
    return sel_func(flags, freqs)

# Test with Enterprise
selection = Selection(test_selection_function)
```

#### 3. Performance Issues

**Problem**: Slow selection performance
```python
# Selection takes too long
```

**Solutions**:
```python
# Use specific values instead of None
specific_sel = create_staggered_selection("efac", {"group": "ASP_430"})

# Pre-filter data
filtered_freqs = freqs[(freqs >= 400) & (freqs < 1000)]
filtered_flags = {k: v[(freqs >= 400) & (freqs < 1000)] for k, v in flags.items()}

# Use cached selections
factory = CachedSelectionFactory()
efac_sel = factory.get_selection("efac", {"group": None})
```

### Debugging Tools

```python
def debug_selection(sel_func, flags, freqs):
    """Debug selection function."""
    
    print("=== Selection Debug Info ===")
    print(f"Flags: {list(flags.keys())}")
    print(f"Frequencies: {len(freqs)} TOAs")
    print(f"Frequency range: {freqs.min():.1f} - {freqs.max():.1f}")
    
    for flag_name, values in flags.items():
        unique_values = np.unique(values)
        print(f"{flag_name}: {len(unique_values)} unique values: {unique_values}")
    
    result = sel_func(flags, freqs)
    print(f"Result: {len(result)} selections")
    for key, mask in result.items():
        print(f"  {key}: {mask.sum()} TOAs selected")
    
    return result

# Use debug function
result = debug_selection(sel_func, flags, freqs)
```

## Best Practices

### 1. Selection Design

- **Use realistic flag names**: Use actual flag names from your data
- **Test with real data**: Always test selections with your actual pulsar data
- **Document selections**: Document the purpose and behavior of each selection
- **Use fallback wisely**: Use staggered selection for robust multi-PTA analysis

### 2. Performance

- **Minimize flag criteria**: Use only necessary flag criteria
- **Pre-filter data**: Apply frequency filtering early when possible
- **Cache selections**: Cache frequently used selections
- **Batch processing**: Process multiple pulsars in batches

### 3. Error Handling

- **Validate inputs**: Check flag names and values before creating selections
- **Handle edge cases**: Test with empty data, missing flags, etc.
- **Provide feedback**: Give clear error messages for common issues

### 4. Integration

- **Test Enterprise compatibility**: Always test with Enterprise Selection class
- **Use type hints**: Leverage type hints for better IDE support
- **Follow conventions**: Follow Enterprise naming conventions

### 5. Documentation

- **Document selections**: Document the purpose and behavior of each selection
- **Provide examples**: Include realistic usage examples
- **Update documentation**: Keep documentation up to date with code changes

## Conclusion

The staggered selection utilities provide a powerful and flexible API for creating Enterprise-compatible selection functions. By following this guide, you can effectively integrate them into your pulsar timing analysis workflows while maintaining good performance and reliability.

For more information, see:
- [API Documentation](selection_utils_api.md)
- [Usage Examples](examples/staggered_selection_usage.ipynb)
- [Test Suite](tests/test_selections.py)
