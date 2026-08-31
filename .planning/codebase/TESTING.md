# Testing Patterns

**Analysis Date:** 2026-02-07

## Test Framework

**Runner:**
- pytest 8.4.2+
- Config: `pyproject.toml` [tool.pytest.ini_options]

**Assertion Library:**
- pytest built-in assert syntax

**Mocking:**
- pytest-mock 3.14.0+ (MockerFixture)
- Supports patch(), MagicMock(), and property mocking

**Coverage:**
- pytest-cov 7.0.0+
- Minimum requirement: 70% coverage (fail_under = 70)
- Coverage omits: tests/*, .venv/*, run-pytest.py, .github/*

**Run Commands:**
```bash
uv run pytest                                          # All tests with coverage report
uv run pytest tests/test_cli_commands.py -v            # Single test file
uv run pytest tests/test_cli_commands.py::test_name -v # Single test function
uv run pytest -k "test_pattern" -v                     # Tests matching pattern
uv run pytest --cov=packages/mkapidocs --cov-report=term-missing  # Coverage details
```

## Test File Organization

**Location:**
- `/home/user/mkapidocs/tests/` directory
- Tests are co-located with project root, not next to source

**Naming:**
- Files: `test_*.py` pattern required
- Classes: `Test*` pattern required (e.g., `TestVersionCommand`)
- Functions: `test_*` pattern required

**pythonpath:**
- Configured to include `packages/` so imports work directly: `from mkapidocs.cli import app`

**Directory Structure:**
```
/home/user/mkapidocs/
├── tests/
│   ├── __init__.py                          # Empty module marker
│   ├── conftest.py                          # Shared pytest fixtures
│   ├── test_auto_install.py                 # DoxygenInstaller tests
│   ├── test_build_serve.py                  # build_docs/serve_docs tests
│   ├── test_cli_commands.py                 # CLI command tests
│   ├── test_cli_utils.py                    # CLI utility tests
│   ├── test_feature_detection.py            # Feature detection tests
│   ├── test_gitlab_ci_update.py             # GitLab CI workflow tests
│   ├── test_pyproject_functions.py          # TOML read/write tests
│   ├── test_template_rendering.py           # Template generation tests
│   ├── test_validation_system.py            # Validator class tests
│   ├── test_workflow_conflict.py            # Workflow conflict detection tests
│   └── README.md                            # Test documentation
```

## Test Structure

**Suite Organization:**

Tests use class-based organization with clear naming patterns. Each test file has multiple test classes, each grouping related functionality:

```python
"""Tests for CLI commands in mkapidocs script.

Tests cover:
- version command output
- info command output
- setup command with various scenarios
- build command with various scenarios
- serve command invocation
"""

class TestVersionCommand:
    """Test suite for version command."""

    def test_version_command_success(
        self, cli_runner: CliRunner, typer_app: Typer
    ) -> None:
        """Test version command displays version info.

        Tests: version command shows version number
        How: Invoke version command via CliRunner
        Why: Users need to check installed version

        Args:
            cli_runner: Typer test runner
            typer_app: Typer app instance from fixture
        """
        # Act
        result = cli_runner.invoke(typer_app, ["version"])

        # Assert
        assert result.exit_code == 0
        assert "1.0.0" in result.stdout
        assert "mkapidocs" in result.stdout
```

**Docstring Pattern:**

All test functions include 3-line docstrings explaining:
- **Tests:** What aspect is being tested
- **How:** The testing approach (what setup/invocation)
- **Why:** The business reasoning (why this matters)

Then Args section lists fixture dependencies.

**Patterns:**

1. **Arrange-Act-Assert (AAA):**
   - Arrange: Set up test data and mocks
   - Act: Call the function/method
   - Assert: Verify expected behavior

2. **Fixture-based Setup:**
   - All reusable test data provided via pytest fixtures in `conftest.py`
   - Fixtures are function-scoped by default (fresh instance per test)
   - Session-scoped fixtures for expensive resources (e.g., module import)

3. **Type Hints:**
   - All test functions have type hints on parameters and return type
   - Fixtures in conftest.py have full type annotations

4. **Class Grouping:**
   - Related tests grouped in Test classes (e.g., TestVersionCommand, TestInfoCommand)
   - Makes test output readable and allows class-level setup if needed

## Mocking

**Framework:** pytest-mock (MockerFixture)

**Common Patterns:**

```python
# Mocking subprocess calls (git, doxygen checks)
def test_is_installed_when_doxygen_found(self, mocker: MockerFixture) -> None:
    # Arrange
    _ = mocker.patch("mkapidocs.validators.which", return_value="/usr/bin/doxygen")
    mock_result = mocker.MagicMock()
    mock_result.stdout = "1.9.8"
    _ = mocker.patch("subprocess.run", return_value=mock_result)

    # Act
    is_installed, version = DoxygenInstaller.is_installed()

    # Assert
    assert is_installed is True
    assert version == "1.9.8"
```

```python
# Mocking filesystem operations (git config reading)
def test_detect_github_url_ssh_format(self, mock_repo_path: Path) -> None:
    # Arrange: Create real .git/config file in temp directory
    git_dir = mock_repo_path / ".git"
    git_dir.mkdir()
    git_config = git_dir / "config"
    git_config.write_text(
        """[remote "origin"]
\turl = git@github.com:test-owner/test-repo.git
\tfetch = +refs/heads/*:refs/remotes/origin/*
"""
    )

    # Act
    result = detect_github_url_base(mock_repo_path)

    # Assert
    assert result == "https://test-owner.github.io/test-repo/"
```

```python
# Mocking CLI integration (setup validation, file writing)
def test_setup_command_with_custom_github_url(
    self, cli_runner: CliRunner, mock_repo_path: Path,
    mock_pyproject_toml: Path, mocker: MockerFixture, typer_app: Typer
) -> None:
    # Arrange
    mocker.patch("mkapidocs.cli.validate_environment", return_value=(True, []))
    mock_setup = mocker.patch("mkapidocs.cli.setup_documentation")

    # Act
    custom_url = "https://custom.github.io/project/"
    result = cli_runner.invoke(
        typer_app, ["setup", str(mock_repo_path), "--github-url-base", custom_url]
    )

    # Assert
    mock_setup.assert_called_once()
    args = mock_setup.call_args[0]
    assert args[3] == custom_url  # Verify URL was passed correctly
```

**What to Mock:**
- External commands (git, doxygen, uv/uvx, mkdocs)
- Subprocess operations
- File I/O that's not testing file handling itself
- Environment detection (git remotes, installed tools)
- CLI framework integration (validate_environment, setup_documentation)

**What NOT to Mock:**
- File operations being tested (YAML merge, pyproject.toml parsing)
- Actual fixture data creation (use real files in tmp_path)
- Core business logic of functions being tested
- Exception behavior (test real exceptions)

## Fixtures and Factories

**Test Data Fixtures:**

Shared fixtures in `conftest.py` provide reusable test data:

```python
@pytest.fixture
def mock_repo_path(tmp_path: Path) -> Path:
    """Create a mock repository directory structure.

    Tests: Repository filesystem structure
    How: Use pytest tmp_path to create temporary directory
    Why: Provides isolated filesystem for each test without side effects
    """
    repo = tmp_path / "test_repo"
    repo.mkdir()
    return repo


@pytest.fixture
def mock_pyproject_toml(mock_repo_path: Path) -> Path:
    """Create a mock pyproject.toml file with minimal valid configuration."""
    pyproject_content = """[project]
name = "test-project"
version = "0.1.0"
description = "Test project for documentation"
requires-python = ">=3.11"
dependencies = []

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
"""
    pyproject_path = mock_repo_path / "pyproject.toml"
    pyproject_path.write_text(pyproject_content)
    return pyproject_path


@pytest.fixture
def mock_pyproject_with_typer(mock_repo_path: Path) -> PyprojectConfig:
    """Create pyproject.toml with Typer dependency and return parsed config."""
    import tomllib

    pyproject_content = """[project]
name = "test-cli-project"
version = "0.1.0"
description = "Test CLI project"
requires-python = ">=3.11"
dependencies = ["typer>=0.9.0"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
"""
    pyproject_path = mock_repo_path / "pyproject.toml"
    pyproject_path.write_text(pyproject_content)

    with Path(pyproject_path).open("rb") as f:
        data = tomllib.load(f)
    return PyprojectConfig.from_dict(data)


@pytest.fixture
def mock_c_code_repo(mock_repo_path: Path) -> Path:
    """Create mock repository with C/C++ source files."""
    source_dir = mock_repo_path / "source"
    source_dir.mkdir()

    (source_dir / "main.c").write_text(
        """#include <stdio.h>

int main() {
    printf("Hello, World!\\n");
    return 0;
}
"""
    )

    (source_dir / "utils.h").write_text(
        """#ifndef UTILS_H
#define UTILS_H

void helper_function();

#endif
"""
    )

    return mock_repo_path


@pytest.fixture
def mock_typer_cli_repo(
    mock_repo_path: Path, mock_pyproject_with_typer: TomlTable
) -> Path:
    """Create mock repository with Typer CLI application."""
    package_dir = mock_repo_path / "test_cli_project"
    package_dir.mkdir()

    (package_dir / "__init__.py").write_text('"""Test CLI project package."""')

    (package_dir / "cli.py").write_text(
        """\"\"\"CLI module with Typer application.\"\"\"
import typer

app = typer.Typer()

@app.command()
def hello(name: str) -> None:
    \"\"\"Say hello.\"\"\"
    print(f"Hello {name}!")

if __name__ == "__main__":
    app()
"""
    )

    return mock_repo_path


@pytest.fixture
def mock_git_repo(
    mock_repo_path: Path, mocker: MockerFixture
) -> Generator[Path, None, None]:
    """Mock a git repository with remote URL.

    Tests: Git remote URL detection
    How: Mock subprocess.run to return fake git remote output
    Why: Isolates git operations from external git command
    """
    mock_result = mocker.MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "git@github.com:test-owner/test-repo.git\n"

    mocker.patch("subprocess.run", return_value=mock_result)

    return mock_repo_path
```

**Location:**
- `tests/conftest.py`: All shared fixtures live here
- Fixtures follow function or session scope based on cost/side effects
- Session-scoped: module imports (mkapidocs_module)
- Function-scoped: test data (mock_repo_path, mock_pyproject_toml)

**Usage:**
- Fixtures are injected as test function parameters
- pytest automatically discovers and injects fixtures by name
- Fixtures can depend on other fixtures (e.g., mock_pyproject_with_typer depends on mock_repo_path)

## Coverage

**Requirements:** 70% minimum (enforced by pytest-cov)

**View Coverage:**
```bash
uv run pytest --cov=packages/mkapidocs --cov-report=html    # HTML report in htmlcov/
uv run pytest --cov=packages/mkapidocs --cov-report=term-missing  # Terminal with missing lines
```

**Configuration:**
```toml
[tool.coverage.run]
omit = ["tests/*", ".venv/*", "run-pytest.py", ".github/*"]

[tool.coverage.report]
show_missing = true
fail_under = 70
```

**Coverage Report:**
- Terminal output includes missing lines marked with `*` symbol
- HTML report available in `htmlcov/index.html` after running
- Fail under 70% will cause pytest to exit with failure

## Test Types

**Unit Tests:**

Isolated tests of single functions or classes. Most tests are unit tests.

Example: `tests/test_validation_system.py::TestDoxygenInstaller::test_is_installed_when_doxygen_found`

Tests a single method in isolation by mocking external dependencies (which(), subprocess.run).

**Integration Tests:**

Tests of CLI commands using CliRunner from typer.testing. These verify command parsing, option handling, and integration with core functions.

Example: `tests/test_cli_commands.py::TestSetupCommand::test_setup_command_with_custom_github_url`

Uses CliRunner to invoke Typer app with arguments, mocks the core setup_documentation function to verify correct parameters are passed through the CLI layer.

**Error/Exception Tests:**

Tests verify error handling via pytest.raises():

```python
def test_read_pyproject_file_not_found(self, mock_repo_path: Path) -> None:
    """Test reading pyproject.toml when file doesn't exist."""
    # Act & Assert
    with pytest.raises(FileNotFoundError, match=r"pyproject.toml not found"):
        read_pyproject(mock_repo_path)
```

Pattern: Use `pytest.raises(ExceptionType, match=regex)` to verify exception type and message pattern.

**Validation Tests:**

Tests verify validators and checks. Example: `tests/test_validation_system.py` tests DoxygenInstaller, SystemValidator, ProjectValidator.

Tests both success cases and error cases:
- `test_is_installed_when_doxygen_found` - success case
- `test_is_installed_when_doxygen_not_found` - missing tool
- `test_is_installed_when_version_check_fails` - tool present but check fails

## Common Test Patterns

**Setup and Teardown:**

No explicit setup/teardown needed in most tests because:
- pytest tmp_path fixture handles directory cleanup automatically
- Mock patches are automatically reverted after test function
- Fixtures are function-scoped (fresh instance per test)

Cleanup is implicit via pytest's fixture system.

**Error Testing:**

```python
def test_read_pyproject_file_not_found(self, mock_repo_path: Path) -> None:
    """Test reading pyproject.toml when file doesn't exist.

    Tests: read_pyproject raises FileNotFoundError for missing file
    How: Attempt to read from directory without pyproject.toml
    Why: Should provide clear error when project not configured
    """
    # Act & Assert
    with pytest.raises(FileNotFoundError, match=r"pyproject.toml not found"):
        read_pyproject(mock_repo_path)
```

**CLI Testing:**

CLI commands tested via CliRunner from typer.testing:

```python
def test_version_command_success(
    self, cli_runner: CliRunner, typer_app: Typer
) -> None:
    """Test version command displays version info."""
    # Act
    result = cli_runner.invoke(typer_app, ["version"])

    # Assert
    assert result.exit_code == 0
    assert "1.0.0" in result.stdout
    assert "mkapidocs" in result.stdout
```

Pattern: invoke(app, [args_list]) returns result with exit_code, stdout, and exception attributes.

**Filesystem Testing:**

Real files created in tmp_path, no mocking:

```python
def test_creates_valid_yaml_basic_config(self, mock_repo_path: Path) -> None:
    """Test mkdocs.yml generation creates valid YAML."""
    # Arrange
    project_name = "test-project"
    site_url = "https://test-user.github.io/test-project/"

    # Act
    create_mkdocs_config(
        repo_path=mock_repo_path,
        project_name=project_name,
        site_url=site_url,
        c_source_dirs=[],
        has_typer=False,
        ci_provider=CIProvider.GITHUB,
    )

    # Assert
    mkdocs_path = mock_repo_path / "mkdocs.yml"
    assert mkdocs_path.exists()

    content = mkdocs_path.read_text()
    assert f"site_name: {project_name}" in content
    assert f"site_url: {site_url}" in content
```

Pattern: Create files in mock_repo_path, call function that writes files, verify output.

## Test Linting

Test files have relaxed linting rules configured in pyproject.toml:

```toml
[tool.ruff.lint.per-file-ignores]
"**/tests/**" = [
    "S",    # Security checks not needed in tests
    "D",    # Docstring requirements relaxed for tests
    "E501", # Line length relaxed for test data
    "ANN",  # Type annotations optional for test fixtures/methods
    "DOC",  # Docstring content requirements relaxed
    "PLC",  # Local imports acceptable in test helpers
    "SLF",  # Private name imports acceptable for testing internals
    "PLR",  # Testing private methods is valid test pattern
    "EXE",  # Shebang executable check skipped for PEP723 test files
    "N",    # camelCase in test names acceptable when testing API fields
    "T",    # print() statements are intentional for CI output visibility
]
```

Key relaxations:
- **D**: Docstrings optional in tests (though best practice to include them)
- **S**: Security checks disabled (test code is not production)
- **ANN**: Type annotations optional on fixture parameters (though recommended)
- **SLF**: Can import/test private members
- **PLR**: Can test private methods via _underscore names
- **N**: camelCase allowed in test variable names (e.g., testProject)

---

*Testing analysis: 2026-02-07*
