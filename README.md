# Python Documentation Init

Automated documentation setup tool for Python projects using MkDocs and GitLab Pages

## Quick Start

Install from GitLab PyPI registry:

```bash
pip install python_docs_init --index-url 
```

Configure pip to use the GitLab registry by default:

```bash
pip config set global.index-url 
```

## Usage

### Basic Commands

```bash
# Show version information
python_docs_init version

# Show package information
python_docs_init info

# Get help
python_docs_init --help
```



## Development

### Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) package manager


### Setup

```bash
# Clone the repository
git clone https://sourcery.assaabloy.net/.git
cd python_docs_init

# Install dependencies
uv sync --all-extras --dev

# Install pre-commit hooks
uv run pre-commit install
```



### Running Tests

```bash
# Run all tests with coverage
uv run pytest

# Run specific test file
uv run pytest tests/test_cli.py

# Run with verbose output
uv run pytest -v
```

### Code Quality

```bash
# Run all pre-commit hooks
uv run pre-commit run --all-files

# Run specific checks
uv run ruff check .
uv run mypy packages/python_docs_init
uv run pyright packages/python_docs_init
```

## Project Structure

```
python_docs_init/
├── packages/
│   └── python_docs_init/
│       ├── __init__.py
│       ├── cli.py
│       └── tests/

├── .gitlab/
│   └── workflows/
│       ├── defaults.gitlab-ci.yml
│       ├── pytest.gitlab-ci.yml
│       ├── python-static-analysis.gitlab-ci.yml
│       └── release.gitlab-ci.yml
├── .gitlab-ci.yml
├── .pre-commit-config.yaml
├── pyproject.toml
└── README.md
```

## License

Unlicense

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests and linting
5. Submit a merge request

## Links

- [Repository](https://sourcery.assaabloy.net/)
- [Issue Tracker](https://sourcery.assaabloy.net//-/issues)
- [Documentation](https://sourcery.assaabloy.net//-/blob/main/README.md)
