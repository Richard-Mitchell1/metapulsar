# Sample Data for MetaPulsar Examples

This directory contains sample data files for MetaPulsar examples and tutorials.

## Structure

```
sample_data/
├── README.md                    # This file
├── epta_dr2/                   # EPTA DR2 sample data
│   ├── J1909-3744.par          # Sample par file
│   └── J1909-3744.tim          # Sample tim file
├── ppta_dr2/                   # PPTA DR2 sample data
│   ├── J1909-3744.par          # Sample par file
│   └── J1909-3744.tim          # Sample tim file
└── custom_pta/                 # Custom PTA sample data
    ├── J1909-3744_custom.par   # Sample par file
    └── J1909-3744_custom.tim   # Sample tim file
```

## Usage

These sample files are designed to work with the MetaPulsar examples and tutorials. They provide:

- **Realistic file formats**: Proper par and tim file structures
- **Consistent naming**: Follows PTA naming conventions
- **Educational content**: Clear examples for learning

## Note

These are sample files for educational purposes. For real analysis, use actual PTA data files from the respective collaborations.

## File Formats

- **Par files**: Pulsar parameter files (PINT/TEMPO2 format)
- **Tim files**: Timing data files (PINT/TEMPO2 format)

## Integration

The sample data integrates with:
- `examples/basic_workflow.py`
- `examples/parameter_management.py`
- `examples/custom_pta_configuration.py`
- `examples/enterprise_integration.py`
- All tutorial notebooks in `examples/notebooks/`

