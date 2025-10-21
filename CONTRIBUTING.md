# Contributing to MetaPulsar

We welcome contributions to MetaPulsar! This document provides guidelines for contributing to the project.

## 🚀 Getting Started

### Development Setup

1. **Fork and Clone**
   ```bash
   git clone https://www.github.com/vhaasteren/metapulsar.git
   cd metapulsar
   ```

2. **Install in Development Mode**
   ```bash
   pip install -e ".[dev,libstempo]"
   ```

3. **Install Pre-commit Hooks**
   ```bash
   pre-commit install
   ```

4. **Run Tests**
   ```bash
   pytest
   ```

## 📝 Development Guidelines

### Code Style

- **Python**: Follow PEP 8 style guidelines
- **Formatting**: Use `black` for code formatting
- **Linting**: Use `ruff` for linting
- **Type Hints**: Use type hints for all functions and methods
- **Docstrings**: Follow Google-style docstrings

### Testing

- **Coverage**: Maintain high test coverage (>90%)
- **Test Categories**: Use appropriate pytest markers
  - `@pytest.mark.slow` for slow tests
  - `@pytest.mark.integration` for integration tests
- **MockPulsar**: Use MockPulsar for unit tests when possible

### Documentation

- **Docstrings**: All public functions must have docstrings
- **Examples**: Include usage examples in docstrings
- **Type Hints**: Use type hints for better IDE support

## 🔄 Workflow

### Branch Naming

- `feature/description` - New features
- `fix/description` - Bug fixes
- `docs/description` - Documentation updates
- `test/description` - Test improvements
- `refactor/description` - Code refactoring

### Commit Messages

Use conventional commit format:

```
type(scope): description

[optional body]

[optional footer]
```

Types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`

### Pull Request Process

1. **Create Feature Branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make Changes**
   - Write code following style guidelines
   - Add tests for new functionality
   - Update documentation as needed

3. **Test Changes**
   ```bash
   pytest
   black --check .
   ruff check .
   ```

4. **Commit Changes**
   ```bash
   git add .
   git commit -m "feat: add new feature"
   ```

5. **Push and Create MR**
   ```bash
   git push origin feature/your-feature-name
   ```

## 🧪 Testing Guidelines

### Test Structure

```python
class TestFeatureName:
    """Test class for FeatureName functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        pass
    
    def test_basic_functionality(self):
        """Test basic functionality."""
        pass
    
    def test_edge_cases(self):
        """Test edge cases and error conditions."""
        pass
```

### MockPulsar Usage

Use MockPulsar for testing when possible:

```python
from metapulsar.mockpulsar import MockPulsar
from metapulsar.mockpulsar import create_mock_timing_data, create_mock_flags

def test_metapulsar_creation():
    """Test MetaPulsar creation with MockPulsar."""
    toas, residuals, errors, freqs = create_mock_timing_data(100)
    flags = create_mock_flags(100, telescope='test')
    mock_psr = MockPulsar(toas, residuals, errors, freqs, flags, 'test', 'J1857+0943')
    
    metapulsar = MetaPulsar({'test': mock_psr})
    assert len(metapulsar._toas) == 100
```

## 📚 Documentation Guidelines

### Docstring Format

```python
def function_name(param1: str, param2: int = 10) -> bool:
    """Brief description of the function.
    
    Longer description if needed, explaining the purpose,
    behavior, and any important details.
    
    Args:
        param1: Description of param1
        param2: Description of param2 with default value
        
    Returns:
        Description of return value
        
    Raises:
        ValueError: When param1 is invalid
        RuntimeError: When operation fails
        
    Example:
        >>> result = function_name("test", 20)
        >>> print(result)
        True
    """
```

### API Documentation

- All public classes and functions must be documented
- Include usage examples in docstrings
- Document parameters, return values, and exceptions
- Use type hints consistently

## 🐛 Bug Reports

When reporting bugs, please include:

1. **Description**: Clear description of the bug
2. **Steps to Reproduce**: Minimal code example
3. **Expected Behavior**: What should happen
4. **Actual Behavior**: What actually happens
5. **Environment**: Python version, OS, package versions
6. **Error Messages**: Full traceback if applicable

## ✨ Feature Requests

When requesting features, please include:

1. **Use Case**: Why is this feature needed?
2. **Proposed Solution**: How should it work?
3. **Alternatives**: Other approaches considered
4. **Additional Context**: Any other relevant information

## 📋 Code Review Checklist

### For Contributors

- [ ] Code follows style guidelines
- [ ] Tests are included and passing
- [ ] Documentation is updated
- [ ] Type hints are used
- [ ] No debugging code left behind
- [ ] Commit messages are clear

### For Reviewers

- [ ] Code is readable and well-structured
- [ ] Tests cover the new functionality
- [ ] Documentation is clear and complete
- [ ] No breaking changes without justification
- [ ] Performance implications considered

## 🤝 Community Guidelines

- Be respectful and constructive
- Help others learn and improve
- Ask questions when unsure
- Share knowledge and best practices
- Follow the code of conduct

## 📞 Getting Help

- **Issues**: [GitLab Issues](https://www.github.com/vhaasteren/metapulsar/issues)
- **Email**: [rutger@vhaasteren.com](mailto:rutger@vhaasteren.com)

## 📄 License

By contributing to this project, you agree that your contributions will be licensed under the MIT License.
