# MetaPulsar

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Tests](https://img.shields.io/badge/tests-219%20passing-brightgreen)](https://github.com/metapulsar)

A comprehensive framework for combining pulsar timing data from multiple PTA (Pulsar Timing Array) collaborations into unified "metapulsar" objects for gravitational wave detection analysis.

## 🌟 Features

- **Multi-PTA Data Combination**: Seamlessly combine data from EPTA, PPTA, NANOGrav, MPTA, and other PTAs
- **Enterprise Integration**: Full compatibility with the Enterprise pulsar timing analysis framework
- **Dual Timing Package Support**: Works with both PINT and libstempo/tempo2
- **Flexible Parameter Management**: Support for both "consistent" and "composite" combination strategies
- **Robust Testing**: 219 comprehensive tests with MockPulsar support
- **Professional Documentation**: Complete API documentation and usage examples

## 🚀 Quick Start

### Installation

```bash
# Clone the repository
git clone https://gitlab.aei.uni-hannover.de/vhaasteren/metapulsar.git
cd metapulsar

# Install in development mode
pip install -e .

# Install with optional dependencies
pip install -e ".[dev,libstempo,analysis]"
```

### Basic Usage

```python
from metapulsar import MetaPulsar, MetaPulsarFactory, PTARegistry

# Create a MetaPulsar from multiple PTAs
registry = PTARegistry()
factory = MetaPulsarFactory(registry)

# Create MetaPulsar with consistent parameters
metapulsar = factory.create_metapulsar(
    pulsar_name="J1857+0943",
    pta_names=["epta_dr2", "ppta_dr3", "nanograv_12p5yr"],
    combination_strategy="consistent"
)

# Access combined timing data
print(f"Combined TOAs: {len(metapulsar._toas)}")
print(f"Parameters: {metapulsar.fitpars}")
print(f"Design matrix shape: {metapulsar._designmatrix.shape}")
```

## 📖 Documentation

### Core Components

#### MetaPulsar Class
The central class that combines pulsar timing data from multiple PTAs:

```python
from metapulsar import MetaPulsar

# Create from raw pulsar objects
metapulsar = MetaPulsar(
    pulsars={
        'epta': pint_pulsar_epta,
        'ppta': tempo2_pulsar_ppta,
        'nanograv': pint_pulsar_nanograv
    },
    combination_strategy="consistent",  # or "composite"
    merge_astrometry=True,
    merge_spin=True,
    merge_binary=True,
    merge_dispersion=True
)
```

#### MetaPulsarFactory
High-level factory for creating MetaPulsars from file configurations:

```python
from metapulsar import MetaPulsarFactory, PTARegistry

# Initialize factory
registry = PTARegistry()
factory = MetaPulsarFactory(registry)

# Create MetaPulsar from files
metapulsar = factory.create_metapulsar(
    pulsar_name="J1857+0943",
    pta_names=["epta_dr2", "ppta_dr3"],
    combination_strategy="consistent"
)
```

#### PTARegistry
Manages PTA configurations and data discovery:

```python
from metapulsar import PTARegistry

registry = PTARegistry()

# List available PTAs
print(registry.list_ptas())
# ['epta_dr2', 'ppta_dr3', 'nanograv_12p5yr', 'mpta_dr1']

# Get PTA configuration
config = registry.get_pta("epta_dr2")
print(config['timing_package'])  # 'pint' or 'tempo2'
```

### Advanced Usage

#### Custom PTA Configuration

```python
# Add custom PTA
custom_config = {
    "base_dir": "/path/to/custom_pta",
    "par_pattern": r"([BJ]\d{4}[+-]\d{2,4})\.par",
    "tim_pattern": r"([BJ]\d{4}[+-]\d{2,4})\.tim",
    "coordinates": "equatorial",
    "timing_package": "pint",
    "priority": 1,
    "description": "Custom PTA dataset"
}

registry.add_pta("custom_pta", custom_config)
```

#### Parameter Management

```python
# Consistent strategy: merge parameters across PTAs
metapulsar_consistent = MetaPulsar(
    pulsars=pulsars,
    combination_strategy="consistent",
    merge_astrometry=True,    # Merge RA, Dec, proper motion
    merge_spin=True,          # Merge spin parameters
    merge_binary=True,        # Merge binary parameters
    merge_dispersion=True     # Merge DM parameters
)

# Composite strategy: preserve original PTA parameters
metapulsar_composite = MetaPulsar(
    pulsars=pulsars,
    combination_strategy="composite"
)
```

#### File-based Creation

```python
# Create MetaPulsar directly from files
metapulsar = MetaPulsar.from_files(
    file_configs=[
        {"pta": "epta_dr2", "parfile": "path/to/epta.par", "timfile": "path/to/epta.tim"},
        {"pta": "ppta_dr3", "parfile": "path/to/ppta.par", "timfile": "path/to/ppta.tim"}
    ],
    combination_strategy="consistent"
)
```

## 🧪 Testing

The package includes comprehensive test coverage:

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src/metapulsar

# Run specific test categories
pytest -m "not slow"  # Skip slow tests
pytest -m integration  # Run only integration tests
```

### Test Categories

- **Unit Tests**: Individual component testing
- **Integration Tests**: End-to-end workflow testing
- **MockPulsar Tests**: Synthetic data testing
- **Legacy Compatibility**: Backward compatibility testing

## 📁 Project Structure

```
metapulsar/
├── src/metapulsar/                # Main package
│   ├── metapulsar.py             # Core MetaPulsar class
│   ├── metapulsar_factory.py     # Factory for creation
│   ├── metapulsar_parameter_manager.py  # Parameter management
│   ├── mockpulsar.py             # MockPulsar for testing
│   ├── pta_registry.py           # PTA configuration management
│   ├── parfile_manager.py        # Par file handling
│   ├── position_helpers.py       # Coordinate utilities
│   └── selection_utils.py        # Data selection utilities
├── tests/                        # Test suite (219 tests)
├── examples/                     # Usage examples
├── docs/                         # Documentation
└── data/                         # Sample data
```

## 🔧 Dependencies

### Core Dependencies
- **Python 3.8+**
- **numpy** ≥ 1.20.0
- **astropy** ≥ 5.0.0
- **scipy** ≥ 1.7.0
- **pint-pulsar** ≥ 0.9.0
- **enterprise-pulsar** ≥ 3.0.0

### Optional Dependencies
- **libstempo** ≥ 2.0.0 (for tempo2 support)
- **matplotlib** ≥ 3.5.0 (for analysis)
- **xarray** ≥ 0.20.0 (for data analysis)

## 📊 Supported PTAs

| PTA | Dataset | Timing Package | Status |
|-----|---------|----------------|--------|
| EPTA | DR2 | PINT | ✅ Supported |
| PPTA | DR3 | PINT | ✅ Supported |
| NANOGrav | 12.5yr | PINT | ✅ Supported |
| MPTA | DR1 | PINT | ✅ Supported |
| Custom | Any | PINT/Tempo2 | ✅ Supported |

## 🤝 Contributing

We welcome contributions! Please see our [Contributing Guidelines](CONTRIBUTING.md) for details.

### Development Setup

```bash
# Clone and install in development mode
git clone https://gitlab.aei.uni-hannover.de/vhaasteren/metapulsar.git
cd metapulsar
pip install -e ".[dev]"

# Install pre-commit hooks
pre-commit install

# Run tests
pytest
```

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 📚 Citation

If you use this software in your research, please cite:

```bibtex
@software{metapulsar,
  title={MetaPulsar},
  author={van Haasteren, Rutger and Yu, Wang-Wei},
  year={2025},
  url={https://gitlab.aei.uni-hannover.de/vhaasteren/metapulsar},
  license={MIT}
}
```

## 👥 Authors

- **Rutger van Haasteren** - *Lead Developer* - [rutger@vhaasteren.com](mailto:rutger@vhaasteren.com)
- **Wang-Wei Yu** - *Co-Developer* - [wangwei.yu@aei.mpg.de](mailto:wangwei.yu@aei.mpg.de)

## 🙏 Acknowledgments

- The International Pulsar Timing Array (IPTA) collaboration
- The Enterprise pulsar timing analysis package
- The PINT pulsar timing package
- The libstempo/tempo2 timing packages

## 📞 Support

For questions, issues, or contributions:

- **Issues**: [GitLab Issues](https://gitlab.aei.uni-hannover.de/vhaasteren/metapulsar/-/issues)
- **Email**: [rutger@vhaasteren.com](mailto:rutger@vhaasteren.com)
- **Documentation**: [Read the Docs](https://metapulsar.readthedocs.io)

---

**Note**: This is currently a private repository. It will be moved to GitHub and made public in the future.
