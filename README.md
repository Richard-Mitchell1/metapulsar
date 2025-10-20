# MetaPulsar

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Tests](https://img.shields.io/badge/tests-219%20passing-brightgreen)](https://github.com/metapulsar)

A framework for combining pulsar timing data from multiple PTA collaborations into unified "metapulsar" objects for gravitational wave detection analysis.

## Features

- **Multi-PTA Data Combination**: Combine data from EPTA, PPTA, NANOGrav, MPTA, and other PTAs
- **Enterprise Integration**: Full compatibility with the Enterprise pulsar timing analysis framework
- **Dual Timing Package Support**: Works with both PINT and libstempo/tempo2
- **Flexible Parameter Management**: Support for "consistent" and "composite" combination strategies
- **Robust Testing**: 219 comprehensive tests with MockPulsar support

## Quick Start

### Installation

```bash
git clone https://github.com/vhaasteren/metapulsar.git
cd metapulsar
pip install -e .
```

### Basic Usage

```python
from metapulsar import create_metapulsar

# Create MetaPulsar
metapulsar = create_metapulsar(
    file_data=pulsar_data,
    combination_strategy="consistent",
    combine_components=["astrometry", "spindown", "binary", "dispersion"],
    add_dm_derivatives=True,
)

# Access combined data
print(f"Number of TOAs: {len(metapulsar.toas)}")
print(f"PTA names: {list(metapulsar._pulsars.keys())}")
```

## Documentation

- **[Quick Guide](docs/QUICK_GUIDE.md)** - Get started in 5 minutes
- **[User Guide](docs/USER_GUIDE.md)** - Complete usage guide
- **[API Reference](docs/API_REFERENCE.md)** - Complete API documentation
- **[Installation](docs/INSTALLATION.md)** - Installation and setup
- **[Troubleshooting](docs/TROUBLESHOOTING.md)** - Common issues and solutions

## Examples

- **[Interactive Tutorials](examples/notebooks/)** - Jupyter notebook examples
- **[Python Examples](examples/)** - Standalone Python examples

## Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src/metapulsar
```

## Dependencies

- **Python 3.8+**
- **numpy** ≥ 1.20.0
- **astropy** ≥ 5.0.0
- **scipy** ≥ 1.7.0
- **pint-pulsar** ≥ 0.9.0
- **enterprise-pulsar** ≥ 3.0.0

## Supported PTAs

- **EPTA** (DR2) - Tempo2
- **PPTA** (DR2) - Tempo2
- **NANOGrav** (15yr) - PINT
- **MPTA** (DR1) - Tempo2
- **Custom** - PINT/Tempo2

## Contributing

We welcome contributions! Please see our [Contributing Guidelines](CONTRIBUTING.md) for details.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Citation

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

## Authors

- **Rutger van Haasteren** - *Lead Developer* - [rutger@vhaasteren.com](mailto:rutger@vhaasteren.com)
- **Wang-Wei Yu** - *Co-Developer* - [wangwei.yu@aei.mpg.de](mailto:wangwei.yu@aei.mpg.de)

## Support

- **Issues**: [GitHub Issues](https://github.com/vhaasteren/metapulsar/issues)
- **Email**: [rutger@vhaasteren.com](mailto:rutger@vhaasteren.com)
- **Documentation**: [Read the Docs](https://metapulsar.readthedocs.io)
