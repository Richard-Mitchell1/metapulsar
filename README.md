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
git clone https://github.com/vhaasteren/metapulsar.git
cd metapulsar

# Install in development mode
pip install -e .

# Install with optional dependencies
pip install -e ".[dev,libstempo,analysis]"
```

### Basic Usage

```python
from metapulsar import MetaPulsarFactory, FileDiscoveryService

# Discover files from multiple PTAs
discovery = FileDiscoveryService()
file_data = discovery.discover_all_files_in_ptas(["epta_dr2", "ppta_dr2"])

# Create MetaPulsar with consistent parameters
factory = MetaPulsarFactory()
metapulsar = factory.create_metapulsar(
    file_data,
    combination_strategy="consistent"
)

# Access combined timing data
print(f"Strategy: {metapulsar.combination_strategy}")
print(f"Number of PTAs: {len(metapulsar._pulsars)}")
print(f"PTA names: {list(metapulsar._pulsars.keys())}")
```

## 📖 Documentation

### Core Components

#### MetaPulsarFactory
High-level factory for creating MetaPulsars from file configurations:

```python
from metapulsar import MetaPulsarFactory, FileDiscoveryService

# Discover files
discovery = FileDiscoveryService()
file_data = discovery.discover_all_files_in_ptas(["epta_dr2", "ppta_dr2"])

# Create MetaPulsar
factory = MetaPulsarFactory()
metapulsar = factory.create_metapulsar(
    file_data,
    combination_strategy="consistent"
)
```

#### FileDiscoveryService
Manages PTA configurations and data discovery:

```python
from metapulsar import FileDiscoveryService

discovery = FileDiscoveryService()

# List available PTAs
print(discovery.list_ptas())
# ['epta_dr2', 'ppta_dr2', 'nanograv_15y', 'mpta_dr1']

# Discover files for specific PTAs
file_data = discovery.discover_all_files_in_ptas(["epta_dr2", "ppta_dr2"])
```

#### ParameterManager
Manages parameter consistency across PTAs:

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

### Advanced Usage

#### Custom PTA Configuration

```python
from metapulsar import FileDiscoveryService

discovery = FileDiscoveryService()

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

#### Parameter Management

```python
from metapulsar import ParameterManager

# Create parameter manager for consistency
param_manager = ParameterManager(
    file_data=file_data,
    reference_pta="epta_dr2",
    combine_components=["astrometry", "spindown", "binary", "dispersion"],
    add_dm_derivatives=True
)

# Build parameter mappings
mapping = param_manager.build_parameter_mappings()
```

#### Combination Strategies

```python
# Consistent strategy: merge parameters across PTAs
metapulsar_consistent = factory.create_metapulsar(
    file_data,
    combination_strategy="consistent",
    reference_pta="epta_dr2"
)

# Composite strategy: preserve original PTA parameters
metapulsar_composite = factory.create_metapulsar(
    file_data,
    combination_strategy="composite"
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
│   ├── parameter_manager.py      # Parameter management
│   ├── file_discovery_service.py # File discovery and PTA management
│   ├── mockpulsar.py             # MockPulsar for testing
│   ├── tim_file_analyzer.py      # TIM file analysis utilities
│   ├── selection_utils.py        # Data selection utilities
│   └── pint_helpers.py           # PINT integration helpers
├── tests/                        # Test suite (219 tests)
├── examples/                     # Usage examples and tutorials
│   ├── notebooks/                # Interactive Jupyter tutorials
│   ├── *.py                      # Python examples
│   └── data/                     # Sample data
├── docs/                         # Documentation
└── pyproject.toml                # Project configuration
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
| PPTA | DR2 | PINT | ✅ Supported |
| NANOGrav | 15yr | PINT | ✅ Supported |
| MPTA | DR1 | PINT | ✅ Supported |
| Custom | Any | PINT/Tempo2 | ✅ Supported |

## 🤝 Contributing

We welcome contributions! Please see our [Contributing Guidelines](CONTRIBUTING.md) for details.

### Development Setup

```bash
# Clone and install in development mode
git clone https://github.com/vhaasteren/metapulsar.git
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
  url={https://github.com/vhaasteren/metapulsar},
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

- **Issues**: [GitHub Issues](https://github.com/vhaasteren/metapulsar/issues)
- **Email**: [rutger@vhaasteren.com](mailto:rutger@vhaasteren.com)
- **Documentation**: [Read the Docs](https://metapulsar.readthedocs.io)

## 📚 Documentation

- **Installation Guide**: [docs/installation.md](docs/installation.md)
- **User Guide**: [docs/user_guide.md](docs/user_guide.md)
- **API Reference**: [docs/api_reference.md](docs/api_reference.md)
- **Developer Guide**: [docs/developer_guide.md](docs/developer_guide.md)
- **Troubleshooting**: [docs/troubleshooting.md](docs/troubleshooting.md)
- **FAQ**: [docs/faq.md](docs/faq.md)

## 🎯 Examples

- **Basic Workflow**: [examples/basic_workflow.py](examples/basic_workflow.py)
- **Parameter Management**: [examples/parameter_management.py](examples/parameter_management.py)
- **Custom PTA Configuration**: [examples/custom_pta_configuration.py](examples/custom_pta_configuration.py)
- **Enterprise Integration**: [examples/enterprise_integration.py](examples/enterprise_integration.py)
- **Interactive Tutorials**: [examples/notebooks/](examples/notebooks/)
