"""Shared pytest fixtures for mkapidocs test suite.

This module provides reusable fixtures for testing the mkapidocs standalone script.
All fixtures follow modern Python 3.11+ type hint syntax and pytest-mock standards.
"""

from __future__ import annotations

import sys
from collections.abc import Generator
from pathlib import Path
from types import ModuleType

import pytest
from mkapidocs.models import PyprojectConfig, TomlTable
from pytest_mock import MockerFixture


@pytest.fixture(scope="session", autouse=True)
def mkapidocs_module() -> ModuleType:
    """Import mkapidocs.cli module for testing.

    Tests: Package module import
    How: Import mkapidocs.cli directly as installed package
    Why: Single module instance prevents import state conflicts across test files

    Returns:
        Imported mkapidocs.cli module

    Note:
        Session-scoped with autouse=True to ensure module loads before any test runs.
        This prevents import conflicts where different test files create different
        Typer app instances, causing mocking failures.
    """
    if "mkapidocs" in sys.modules:
        # Module already loaded, return cached version
        return sys.modules["mkapidocs"]

    # Import the package module directly (now installed via uv/pip)
    import mkapidocs.cli as mkapidocs_cli

    # Register as "mkapidocs" for backward compatibility with tests
    sys.modules["mkapidocs"] = mkapidocs_cli

    return sys.modules["mkapidocs"]


@pytest.fixture
def mock_repo_path(tmp_path: Path) -> Path:
    """Create a mock repository directory structure.

    Tests: Repository filesystem structure
    How: Use pytest tmp_path to create temporary directory
    Why: Provides isolated filesystem for each test without side effects

    Args:
        tmp_path: Pytest fixture providing temporary directory

    Returns:
        Path to mock repository root
    """
    repo = tmp_path / "test_repo"
    repo.mkdir()
    return repo


@pytest.fixture
def mock_pyproject_toml(mock_repo_path: Path) -> Path:
    """Create a mock pyproject.toml file with minimal valid configuration.

    Tests: Project configuration parsing
    How: Write minimal pyproject.toml to mock repository
    Why: Provides baseline configuration for testing feature detection

    Args:
        mock_repo_path: Path to mock repository

    Returns:
        Path to created pyproject.toml file
    """
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
    """Create pyproject.toml with Typer dependency and return parsed dict.

    Tests: Typer dependency detection
    How: Write pyproject.toml with typer in dependencies, parse with tomllib
    Why: Enables testing of Typer CLI detection logic

    Args:
        mock_repo_path: Path to mock repository

    Returns:
        Parsed pyproject.toml configuration dictionary
    """
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

    with open(pyproject_path, "rb") as f:
        data = tomllib.load(f)
    return PyprojectConfig.from_dict(data)


@pytest.fixture
def mock_pyproject_with_private_registry(mock_repo_path: Path) -> PyprojectConfig:
    """Create pyproject.toml with private registry configuration.

    Tests: Private registry detection
    How: Write pyproject.toml with [tool.uv.index] configuration
    Why: Enables testing of private registry detection logic

    Args:
        mock_repo_path: Path to mock repository

    Returns:
        Parsed pyproject.toml configuration dictionary
    """
    import tomllib

    pyproject_content = """[project]
name = "test-private-project"
version = "0.1.0"
description = "Test project with private registry"
requires-python = ">=3.11"
dependencies = []

[tool.uv]
index = [{url = "https://private.pypi.org/simple"}]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
"""
    pyproject_path = mock_repo_path / "pyproject.toml"
    pyproject_path.write_text(pyproject_content)

    with open(pyproject_path, "rb") as f:
        data = tomllib.load(f)
    return PyprojectConfig.from_dict(data)


@pytest.fixture
def mock_git_repo(mock_repo_path: Path, mocker: MockerFixture) -> Generator[Path, None, None]:
    """Mock a git repository with remote URL.

    Tests: Git remote URL detection
    How: Mock subprocess.run to return fake git remote output
    Why: Isolates git operations from external git command and filesystem

    Args:
        mock_repo_path: Path to mock repository
        mocker: pytest-mock fixture for mocking

    Yields:
        Path to mock repository with mocked git operations
    """
    # Mock git remote get-url origin
    mock_result = mocker.MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "git@github.com:test-owner/test-repo.git\n"

    mocker.patch("subprocess.run", return_value=mock_result)

    yield mock_repo_path


@pytest.fixture
def mock_c_code_repo(mock_repo_path: Path) -> Path:
    """Create mock repository with C/C++ source files.

    Tests: C/C++ code detection
    How: Create source/ directory with .c and .h files
    Why: Provides test data for C code detection logic

    Args:
        mock_repo_path: Path to mock repository

    Returns:
        Path to mock repository with C code
    """
    source_dir = mock_repo_path / "source"
    source_dir.mkdir()

    # Create C source file
    (source_dir / "main.c").write_text(
        """#include <stdio.h>

int main() {
    printf("Hello, World!\\n");
    return 0;
}
"""
    )

    # Create C header file
    (source_dir / "utils.h").write_text(
        """#ifndef UTILS_H
#define UTILS_H

void helper_function();

#endif
"""
    )

    return mock_repo_path


@pytest.fixture
def mock_typer_cli_repo(mock_repo_path: Path, mock_pyproject_with_typer: TomlTable) -> Path:
    """Create mock repository with Typer CLI application.

    Tests: Typer CLI module detection
    How: Create package structure with CLI module containing Typer app
    Why: Provides test data for Typer CLI detection via AST parsing

    Args:
        mock_repo_path: Path to mock repository
        mock_pyproject_with_typer: Parsed pyproject.toml with Typer dependency

    Returns:
        Path to mock repository with Typer CLI
    """
    # Create package directory
    package_dir = mock_repo_path / "test_cli_project"
    package_dir.mkdir()

    # Create __init__.py
    (package_dir / "__init__.py").write_text('"""Test CLI project package."""')

    # Create cli.py with Typer app
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
def parsed_pyproject() -> PyprojectConfig:
    """Provide minimal parsed pyproject.toml dictionary.

    Tests: Functions that accept parsed pyproject dict as input
    How: Return hardcoded dictionary mimicking tomllib.load output
    Why: Avoids file I/O for unit tests that only need config data

    Returns:
        Minimal pyproject.toml configuration dictionary
    """
    data: TomlTable = {
        "project": {"name": "test-project", "version": "0.1.0", "description": "Test project", "dependencies": []},
        "build-system": {"requires": ["hatchling"], "build-backend": "hatchling.build"},
    }
    return PyprojectConfig.from_dict(data)
