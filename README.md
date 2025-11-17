<p align="left">
  <img src="docs/logo/metapulsar_logo_notext.png" alt="MetaPulsar Logo" width="180" />
</p>

# MetaPulsar

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![DOI](https://zenodo.org/badge/727659043.svg)](https://doi.org/10.5281/zenodo.17626664)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Tests](https://img.shields.io/badge/tests-219%20passing-brightgreen)](https://github.com/metapulsar)

A framework for combining pulsar timing data from multiple PTA collaborations into unified "metapulsar" objects for gravitational wave detection analysis.

## Features

- **Multi-PTA Data Combination**: Combine data from EPTA, PPTA, NANOGrav, MPTA, and other PTAs
- **Enterprise Integration**: Full compatibility with the Enterprise pulsar timing analysis package
- **Dual Timing Package Support**: Works with both PINT and libstempo/tempo2
- **Flexible Parameter Management**: Support for "consistent" and "composite" combination strategies

## Quick Start

### Installation

```bash
git clone https://github.com/vhaasteren/metapulsar.git
cd metapulsar
pip install -e .

# With optional dependencies
pip install -e ".[dev,libstempo]"
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

- **[Interactive Tutorial](examples/notebooks/using_metapulsar.ipynb)** - Complete usage guide with examples
- **[API Reference](docs/API_REFERENCE.md)** - Complete API documentation
- **[Method Description](docs/METHOD_DESCRIPTION.md)** - Detailed description of the direct combination method

## Examples

- **[Python Examples](examples/)** - Standalone Python examples

## Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src/metapulsar
```

## Troubleshooting

### Debug Mode

```python
import loguru
import sys
loguru.logger.remove()
loguru.logger.add(sys.stdout, level="DEBUG")
```

## Dependencies

- **Python 3.9+**
- **numpy** ≥ 1.20.0
- **astropy** ≥ 5.0.0
- **scipy** ≥ 1.7.0
- **pint-pulsar** ≥ 0.9.0
- **enterprise-pulsar** ≥ 3.0.0


## Contributing

We welcome contributions! Please see our [Contributing Guidelines](CONTRIBUTING.md) for details.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Citation

If you use this software in your research, please cite:

```bibtex
@software{metapulsar,
  title={MetaPulsar},
  author={van Haasteren, Rutger and Yu, Wang-Wei and Wright, David},
  year={2025},
  doi={10.5281/zenodo.17626664},
  url={https://github.com/vhaasteren/metapulsar},
  license={MIT}
}
```

## Authors

- **Rutger van Haasteren** - *Lead Developer* - [rutger@vhaasteren.com](mailto:rutger@vhaasteren.com)
- **Wang-Wei Yu** - *Co-Developer* - [wangwei.yu@aei.mpg.de](mailto:wangwei.yu@aei.mpg.de)
- **David Wright** - *Co-Developer* - [dcw3.dev@gmail.com](mailto:dcw3.dev@gmail.com)

## Support

- **Issues**: [GitHub Issues](https://github.com/vhaasteren/metapulsar/issues)
- **Email**: [rutger@vhaasteren.com](mailto:rutger@vhaasteren.com)
