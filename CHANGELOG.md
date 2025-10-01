# Changelog

All notable changes to MetaPulsar will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Comprehensive README.md with usage examples
- CONTRIBUTING.md with development guidelines
- CHANGELOG.md for tracking changes
- Updated CITATION.cff with proper project information

## [0.1.0] - 2025-09-30

### Added
- **Core MetaPulsar Class**: Complete implementation with BasePulsar inheritance
- **Multi-PTA Data Combination**: Support for combining data from multiple PTAs
- **Parameter Management**: Both "consistent" and "composite" combination strategies
- **Design Matrix Construction**: Full design matrix building with unit conversion
- **Position and Planetary Data**: Complete position setup and validation
- **MockPulsar Support**: Enterprise-compatible mock pulsar for testing
- **MetaPulsarFactory**: High-level factory for creating MetaPulsars
- **PTARegistry**: PTA configuration management system
- **ParFileManager**: Par file consistency and unit conversion
- **PositionHelpers**: Coordinate conversion and B/J name generation
- **SelectionUtils**: Data selection utilities
- **Comprehensive Test Suite**: 219 tests covering all functionality

### Features
- **Enterprise Integration**: Full compatibility with Enterprise pulsar timing framework
- **Dual Timing Package Support**: Works with both PINT and libstempo/tempo2
- **Flexible Parameter Merging**: Fine-grained control over parameter combination
- **Unit Conversion**: Automatic handling of PINT/Tempo2 unit differences
- **Error Handling**: Robust error handling with loguru logging
- **File-based Creation**: Direct creation from par/tim files
- **Validation**: Comprehensive validation and consistency checking

### Technical Details
- **Python 3.8+ Support**: Compatible with modern Python versions
- **Type Hints**: Complete type annotation throughout
- **Documentation**: Comprehensive docstrings and examples
- **Code Quality**: Black formatting, ruff linting, mypy type checking
- **Testing**: pytest with comprehensive coverage
- **Pre-commit Hooks**: Automated code quality checks

### Supported PTAs
- EPTA DR2 (PINT)
- PPTA DR3 (PINT)
- NANOGrav 12.5yr (PINT)
- MPTA DR1 (PINT)
- Custom PTAs (PINT/Tempo2)

### Dependencies
- numpy >= 1.20.0
- astropy >= 5.0.0
- scipy >= 1.7.0
- pint-pulsar >= 0.9.0
- enterprise-pulsar >= 3.0.0
- Optional: libstempo >= 2.0.0, matplotlib >= 3.5.0

## [0.0.1] - 2025-09-01

### Added
- Initial project structure
- Basic package setup
- Legacy prototype analysis
- Supporting infrastructure development

---

## Version History

- **0.1.0**: Complete MetaPulsar implementation with all core features
- **0.0.1**: Initial project setup and infrastructure development
