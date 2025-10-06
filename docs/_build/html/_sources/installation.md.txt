# MetaPulsar Installation Guide

## Prerequisites

- Python 3.8+
- Git
- scipy and numpy (assumed to be installed)

## Installation

### From Source (Recommended)

1. **Clone the repository**:
   ```bash
   git clone https://github.com/vhaasteren/metapulsar.git
   cd metapulsar
   ```

2. **Install in development mode**:
   ```bash
   pip install -e .
   ```

3. **Install optional dependencies** (for full functionality):
   ```bash
   pip install -e ".[dev,libstempo,analysis]"
   ```

### From PyPI (Future)

Once published:
```bash
pip install metapulsar
```

## Verification

Test your installation:
```python
import metapulsar
print(metapulsar.__version__)
```

## Development Setup

For contributing to MetaPulsar:

1. **Clone and install**:
   ```bash
   git clone https://github.com/vhaasteren/metapulsar.git
   cd metapulsar
   pip install -e ".[dev]"
   ```

2. **Run tests**:
   ```bash
   make test
   ```

3. **Run linting**:
   ```bash
   make lint
   ```

## Troubleshooting

### Common Issues

1. **Import errors**: Ensure you're in the correct Python environment
2. **Missing dependencies**: Install optional dependencies as needed
3. **Permission errors**: Use `--user` flag with pip if needed

For more help, see the [troubleshooting guide](troubleshooting.md).
