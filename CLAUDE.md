# Python Documentation Init - AI Development Context

## Project Overview

**Name:** Python Documentation Init
**Description:** Automated documentation setup tool for Python projects using MkDocs and GitLab Pages
**Type:** Pure Python CLI

## Architecture

### Package Structure

```
python_docs_init/
├── packages/python_docs_init/     # Python package
│   ├── __init__.py                  # Package initialization
│   ├── cli.py                       # Typer CLI interface
│   └── tests/                       # Test suite

└── .gitlab/workflows/               # CI/CD workflows
```

### Technology Stack

- **Language:** Python 3.11+
- **CLI Framework:** Typer with Rich for terminal UI
- **Build System:** Hatchling with hatch-vcs for versioning
- **Package Manager:** uv
- **Testing:** pytest with coverage
- **Linting:** ruff, mypy, pyright


## Development Patterns

### CLI Design Principles

1. **Rich Terminal Output:** Use Rich library for formatted output
2. **Type Safety:** Full type hints with strict mypy/pyright checking
3. **User-Friendly Errors:** Convert technical errors to actionable messages
4. **Progress Feedback:** Show progress for long-running operations
5. **Consistent Interface:** Follow Typer best practices

### Code Standards

- Line length: 120 characters
- Docstring style: Google format
- Import sorting: isort via ruff
- Type checking: strict mode enabled
- Test coverage: 80% minimum

### Testing Strategy

- Unit tests for all CLI commands
- Mock external dependencies
- Hardware tests marked with `@pytest.mark.hardware`
- Integration tests separate from unit tests

## CI/CD Pipeline

### Stages

1. **test:** Run pytest, ruff, mypy, pyright in parallel

2. **release:** Package and publish to GitLab PyPI registry


### Release Process

1. Version bumps use semantic versioning (hatch-vcs)
2. Tags trigger release pipeline: `v1.2.3`
3. Builds published to GitLab PyPI registry


## Development Workflow

### Initial Setup

```bash
# Clone repository
git clone https://sourcery.assaabloy.net/.git
cd python_docs_init

# Install dependencies
uv sync --all-extras --dev

# Install pre-commit hooks
uv run pre-commit install
```

### Daily Development

```bash
# Run tests
uv run pytest

# Run linters
uv run pre-commit run --all-files


# Run CLI locally
uv run python_docs_init --help
```

### Making Changes

1. Create feature branch from main
2. Make changes following code standards
3. Add/update tests (maintain 80%+ coverage)
4. Run pre-commit hooks
5. Submit merge request

## Key Design Decisions


### Version Management

- Automatic versioning from git tags (hatch-vcs)
- Single source of truth: git repository
- No manual version bumping required


### Configuration


- Pydantic models for type-safe config
- Support for .env files

- Environment variable overrides
- CLI flags take precedence

## Troubleshooting

### Common Issues


**Import errors:**
- Run `uv sync` to update dependencies
- Check Python version matches requirement

**Test failures:**
- Clear pytest cache: `rm -rf .pytest_cache`
- Regenerate coverage: `uv run pytest --cov`

## Links

- Repository: https://sourcery.assaabloy.net/
- Issue Tracker: https://sourcery.assaabloy.net//-/issues
- CI/CD: https://sourcery.assaabloy.net//-/pipelines

