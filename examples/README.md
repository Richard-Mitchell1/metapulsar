# MetaPulsar Examples

This directory contains comprehensive examples and tutorials for the MetaPulsar framework.

## Structure

### Python Scripts
- `basic_workflow.py` - Complete workflow from file discovery to MetaPulsar creation
- `parameter_management.py` - ParameterManager usage and strategies
- `custom_pta_configuration.py` - Adding custom PTA configurations
- `enterprise_integration.py` - Integration with Enterprise framework

### Interactive Tutorials
- `notebooks/01_basic_usage.ipynb` - Basic workflow tutorial
- `notebooks/02_parameter_management.ipynb` - Parameter management tutorial
- `notebooks/03_enterprise_integration.ipynb` - Enterprise integration tutorial
- `notebooks/04_advanced_workflows.ipynb` - Advanced use cases

### Sample Data
- `data/sample_data/` - Sample data for examples

### Legacy Examples
- `staggered_selection_usage.ipynb` - Staggered selection utilities (specific feature)

## Getting Started

1. **Run Python Scripts**:
   ```bash
   python examples/basic_workflow.py
   python examples/parameter_management.py
   python examples/custom_pta_configuration.py
   python examples/enterprise_integration.py
   ```

2. **Open Interactive Tutorials**:
   ```bash
   jupyter notebook examples/notebooks/
   ```

## Examples vs Tests

- **Examples**: Demonstrate workflows and educate users
- **Tests**: Verify functionality and ensure code quality
- **Separation**: Examples are educational, tests are comprehensive

## Example Categories

### 1. Basic Usage

- **Simple Flag Selection**: Select based on single flags
- **Specific Value Selection**: Select specific flag values
- **All Values Selection**: Select all unique flag values

### 2. Staggered Selection

- **Primary Flag Available**: Use primary flag when available
- **Fallback Behavior**: Fallback to secondary flags when primary is missing
- **Multiple Fallbacks**: Triple fallback scenarios

### 3. Frequency Filtering

- **Band Selection**: Select specific frequency bands
- **Combined Filtering**: Flag selection with frequency filtering
- **Multiple Bands**: Different selections for different frequency ranges

### 4. Enterprise Integration

- **Selection Wrapper**: Using with Enterprise Selection class
- **Parameter Generation**: Generating parameters for Enterprise models
- **Model Building**: Building complete Enterprise models

### 5. Real-world Scenarios

- **Multi-PTA Analysis**: Selections for different PTA collaborations
- **Backend Selection**: Backend-specific selections with fallback
- **Complex Criteria**: Multiple selection criteria

### 6. Advanced Patterns

- **Performance Optimization**: Optimizing for large datasets
- **Caching Strategies**: Caching selections for repeated use
- **Batch Processing**: Processing multiple pulsars efficiently

### 7. Error Handling

- **Edge Cases**: Handling missing flags, empty values, etc.
- **Debugging Tools**: Tools for debugging selection issues
- **Validation**: Validating selection results

## Customization

### Creating Your Own Examples

1. **Copy the template**:
   ```bash
   cp staggered_selection_usage.ipynb my_example.ipynb
   ```

2. **Modify for your use case**:
   - Update the mock data to match your data
   - Add your specific selection criteria
   - Include your analysis workflow

3. **Test with real data**:
   - Replace mock data with your actual pulsar data
   - Verify selections work as expected
   - Document any issues or improvements

### Adding New Examples

1. **Create new notebook**:
   ```bash
   touch my_new_example.ipynb
   ```

2. **Follow the structure**:
   - Clear title and description
   - Step-by-step instructions
   - Code examples with explanations
   - Expected outputs
   - Troubleshooting tips

3. **Update this README**:
   - Add your example to the contents list
   - Describe what it demonstrates
   - Include any special requirements

## Troubleshooting

### Common Issues

1. **Import Errors**:
   ```python
   # Make sure MetaPulsar is installed
   pip install -e .
   
   # Check Python path
   import sys
   print(sys.path)
   ```

2. **Enterprise Compatibility**:
   ```python
   # Check Enterprise version
   import enterprise
   print(enterprise.__version__)
   
   # Test basic functionality
   from enterprise.signals.selections import Selection
   ```

3. **Data Issues**:
   ```python
   # Check your data structure
   print(f"Flags: {list(flags.keys())}")
   print(f"Frequencies: {len(freqs)} TOAs")
   print(f"Flag values: {[np.unique(v) for v in flags.values()]}")
   ```

### Getting Help

1. **Check the documentation**:
   - API documentation: `../docs/selection_utils_api.md`
   - Integration guide: `../docs/enterprise_integration_guide.md`

2. **Run the tests**:
   ```bash
   python -m pytest tests/test_selections.py -v
   ```

3. **Debug with examples**:
   - Use the debugging tools in the examples
   - Check the test cases for reference implementations

## Contributing

### Adding Examples

1. **Follow the style guide**:
   - Use clear, descriptive names
   - Include comprehensive docstrings
   - Add comments explaining complex logic
   - Test with real data

2. **Document your examples**:
   - Update this README
   - Include usage instructions
   - Document any special requirements

3. **Test thoroughly**:
   - Test with different datasets
   - Verify Enterprise compatibility
   - Check performance implications

### Reporting Issues

1. **Check existing issues**:
   - Look for similar problems in the issue tracker
   - Check the troubleshooting section

2. **Provide details**:
   - Describe the problem clearly
   - Include error messages
   - Provide minimal reproducible examples
   - Include system information

## License

This examples directory is part of MetaPulsar and follows the same license terms.
