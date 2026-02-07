# mkapidocs Test Suite

Pytest test suite for the mkapidocs package (178 tests, minimum 70% coverage required).

## Structure

```
tests/
├── conftest.py                      # Shared fixtures (mock repos, pyproject configs)
├── test_feature_detection.py        # Feature detection: C code, Typer, registries, git (32 tests)
├── test_template_rendering.py       # Template rendering and YAML merge (41 tests)
├── test_validation_system.py        # Environment/project validation (39 tests)
├── test_build_serve.py              # Build/serve logic and env detection (22 tests)
├── test_cli_commands.py             # CLI command tests via Typer runner (15 tests)
├── test_cli_utils.py                # CLI utility functions (9 tests)
├── test_pyproject_functions.py      # pyproject.toml parsing utilities (7 tests)
├── test_auto_install.py             # Doxygen auto-install (6 tests)
├── test_workflow_conflict.py        # Workflow conflict detection (6 tests)
├── test_gitlab_ci_update.py         # GitLab CI update logic (1 test)
└── README.md                        # This file
```

## Running Tests

```bash
uv run pytest                                          # All tests with coverage
uv run pytest tests/test_cli_commands.py -v            # Single file
uv run pytest tests/test_cli_commands.py::test_name -v # Single test
uv run pytest -k "test_pattern" -v                     # Pattern match
```

## Fixtures

Shared fixtures in `conftest.py`:

- `mkapidocs_module` — Session-scoped module import (prevents import state conflicts)
- `mock_repo_path` — Temporary directory as mock repository
- `mock_pyproject_toml` — Minimal valid pyproject.toml
- `mock_pyproject_with_typer` — pyproject.toml with Typer dependency
- `mock_pyproject_with_private_registry` — pyproject.toml with uv index config
- `mock_git_repo` — Mock repository with mocked git remote
- `mock_c_code_repo` — Mock repository with C/C++ source files
- `mock_typer_cli_repo` — Mock repository with Typer CLI application
- `parsed_pyproject` — Minimal parsed PyprojectConfig for unit tests
