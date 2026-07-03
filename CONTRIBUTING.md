# Contributing to Maestro

Thank you for your interest in contributing to Maestro!

## Development Setup

1. **Clone the Repository**:
   ```bash
   git clone https://github.com/aryansinghnagar/Maestro.git
   cd Maestro
   ```

2. **Install Dependencies**:
   ```bash
   pip install -e .[dev]
   ```

3. **Install Pre-Commit Hooks**:
   ```bash
   pre-commit install
   ```

## Development Guidelines

- **Code Style**: Code must be formatted using `black` and linted with `ruff`.
- **Typing**: Strict type annotations are required (`mypy`).
- **Tests**: Write tests for all new features. Ensure overall coverage is >=80%.
  Run tests:
  ```bash
  python -m pytest
  ```
- **Commits**: Follow the Conventional Commits specification.
