"""Tests for pyproject.toml utility functions.

Tests cover:
- Reading pyproject.toml files
- Writing pyproject.toml files
- Extracting source paths from build configuration
- Updating ruff configuration
"""

from __future__ import annotations

import sys
import tomllib
from pathlib import Path
from typing import Any

import pytest


# Module is imported in conftest.py with session scope
# Access functions directly from sys.modules after conftest runs
def read_pyproject(*args, **kwargs):  # type: ignore[no-untyped-def]
    """Wrapper for mkapidocs.read_pyproject with deferred module lookup."""  # noqa: DOC201
    return sys.modules["mkapidocs"].read_pyproject(*args, **kwargs)


def write_pyproject(*args, **kwargs):  # type: ignore[no-untyped-def]
    """Wrapper for mkapidocs.write_pyproject with deferred module lookup."""  # noqa: DOC201
    return sys.modules["mkapidocs"].write_pyproject(*args, **kwargs)


def get_source_paths_from_pyproject(*args, **kwargs):  # type: ignore[no-untyped-def]
    """Wrapper for mkapidocs.get_source_paths_from_pyproject with deferred module lookup."""  # noqa: DOC201
    return sys.modules["mkapidocs"].get_source_paths_from_pyproject(*args, **kwargs)


def update_ruff_config(*args, **kwargs):  # type: ignore[no-untyped-def]
    """Wrapper for mkapidocs.update_ruff_config with deferred module lookup."""  # noqa: DOC201
    return sys.modules["mkapidocs"].update_ruff_config(*args, **kwargs)


class TestReadPyproject:
    """Test suite for read_pyproject function."""

    def test_read_pyproject_success(self, mock_pyproject_toml: Path) -> None:
        """Test reading valid pyproject.toml.

        Tests: read_pyproject parses pyproject.toml correctly
        How: Read mock pyproject.toml fixture
        Why: Core function for extracting project metadata

        Args:
            mock_pyproject_toml: Mock pyproject.toml file path
        """
        # Act
        config = read_pyproject(mock_pyproject_toml.parent)

        # Assert
        assert "project" in config
        assert config["project"]["name"] == "test-project"
        assert config["project"]["version"] == "0.1.0"

    def test_read_pyproject_file_not_found(self, mock_repo_path: Path) -> None:
        """Test reading pyproject.toml when file doesn't exist.

        Tests: read_pyproject raises FileNotFoundError for missing file
        How: Attempt to read from directory without pyproject.toml
        Why: Should provide clear error when project not configured

        Args:
            mock_repo_path: Repository without pyproject.toml
        """
        # Act & Assert
        with pytest.raises(FileNotFoundError, match=r"pyproject.toml not found"):
            read_pyproject(mock_repo_path)


class TestWritePyproject:
    """Test suite for write_pyproject function."""

    def test_write_pyproject_creates_file(self, mock_repo_path: Path) -> None:
        """Test writing pyproject.toml creates valid TOML.

        Tests: write_pyproject creates properly formatted file
        How: Write config dict, read back with tomllib
        Why: Ensures generated pyproject.toml is valid

        Args:
            mock_repo_path: Temporary repository directory
        """
        # Arrange
        config = {
            "project": {
                "name": "new-project",
                "version": "1.0.0",
            }
        }

        # Act
        write_pyproject(mock_repo_path, config)

        # Assert
        pyproject_path = mock_repo_path / "pyproject.toml"
        assert pyproject_path.exists()

        with open(pyproject_path, "rb") as f:
            written_config = tomllib.load(f)

        assert written_config["project"]["name"] == "new-project"
        assert written_config["project"]["version"] == "1.0.0"

    def test_write_pyproject_overwrites_existing(self, mock_pyproject_toml: Path) -> None:
        """Test writing pyproject.toml overwrites existing file.

        Tests: write_pyproject replaces existing configuration
        How: Write new config over existing mock pyproject.toml
        Why: Update operation should replace entire file

        Args:
            mock_pyproject_toml: Existing mock pyproject.toml
        """
        # Arrange
        new_config = {
            "project": {
                "name": "updated-project",
                "version": "2.0.0",
            }
        }

        # Act
        write_pyproject(mock_pyproject_toml.parent, new_config)

        # Assert
        with open(mock_pyproject_toml, "rb") as f:
            written_config = tomllib.load(f)

        assert written_config["project"]["name"] == "updated-project"
        assert written_config["project"]["version"] == "2.0.0"


class TestGetSourcePathsFromPyproject:
    """Test suite for get_source_paths_from_pyproject function."""

    def test_get_source_paths_hatch_sources_mapping(self, mock_repo_path: Path) -> None:
        """Test extracting source paths from Hatch sources configuration.

        Tests: get_source_paths_from_pyproject handles Hatch sources
        How: Create pyproject with tool.hatch.build.targets.wheel.sources
        Why: Hatch projects need correct PYTHONPATH for documentation

        Args:
            mock_repo_path: Temporary repository directory
        """
        # Arrange
        pyproject_content = """[project]
name = "test-project"
version = "0.1.0"

[tool.hatch.build.targets.wheel]
sources = {"packages/mypackage" = "mypackage"}
"""
        (mock_repo_path / "pyproject.toml").write_text(pyproject_content)

        # Act
        paths = get_source_paths_from_pyproject(mock_repo_path)

        # Assert
        assert len(paths) == 1
        assert paths[0] == mock_repo_path / "packages"

    def test_get_source_paths_hatch_packages_list(self, mock_repo_path: Path) -> None:
        """Test extracting source paths from Hatch packages configuration.

        Tests: get_source_paths_from_pyproject handles Hatch packages
        How: Create pyproject with tool.hatch.build.targets.wheel.packages
        Why: Alternative Hatch configuration pattern

        Args:
            mock_repo_path: Temporary repository directory
        """
        # Arrange
        pyproject_content = """[project]
name = "test-project"
version = "0.1.0"

[tool.hatch.build.targets.wheel]
packages = ["src/mypackage"]
"""
        (mock_repo_path / "pyproject.toml").write_text(pyproject_content)

        # Act
        paths = get_source_paths_from_pyproject(mock_repo_path)

        # Assert
        assert len(paths) == 1
        assert paths[0] == mock_repo_path / "src"

    def test_get_source_paths_setuptools_where(self, mock_repo_path: Path) -> None:
        """Test extracting source paths from setuptools configuration.

        Tests: get_source_paths_from_pyproject handles setuptools
        How: Create pyproject with tool.setuptools.packages.find.where
        Why: Setuptools projects need PYTHONPATH configuration

        Args:
            mock_repo_path: Temporary repository directory
        """
        # Arrange
        pyproject_content = """[project]
name = "test-project"
version = "0.1.0"

[tool.setuptools.packages.find]
where = ["src"]
"""
        (mock_repo_path / "pyproject.toml").write_text(pyproject_content)

        # Act
        paths = get_source_paths_from_pyproject(mock_repo_path)

        # Assert
        assert len(paths) == 1
        assert paths[0] == mock_repo_path / "src"

    def test_get_source_paths_no_config(self, mock_repo_path: Path) -> None:
        """Test extracting source paths when no build config present.

        Tests: get_source_paths_from_pyproject returns empty list
        How: Create minimal pyproject without build configuration
        Why: Should handle projects without explicit source paths

        Args:
            mock_repo_path: Temporary repository directory
        """
        # Arrange
        pyproject_content = """[project]
name = "test-project"
version = "0.1.0"
"""
        (mock_repo_path / "pyproject.toml").write_text(pyproject_content)

        # Act
        paths = get_source_paths_from_pyproject(mock_repo_path)

        # Assert
        assert paths == []

    def test_get_source_paths_missing_pyproject(self, mock_repo_path: Path) -> None:
        """Test extracting source paths when pyproject.toml missing.

        Tests: get_source_paths_from_pyproject handles missing file
        How: Call function on directory without pyproject.toml
        Why: Should return empty list for projects without config

        Args:
            mock_repo_path: Repository without pyproject.toml
        """
        # Act
        paths = get_source_paths_from_pyproject(mock_repo_path)

        # Assert
        assert paths == []

    def test_get_source_paths_invalid_toml(self, mock_repo_path: Path) -> None:
        """Test extracting source paths from malformed pyproject.toml.

        Tests: get_source_paths_from_pyproject handles parse errors
        How: Create invalid TOML file
        Why: Should return empty list for corrupt configuration

        Args:
            mock_repo_path: Temporary repository directory
        """
        # Arrange
        (mock_repo_path / "pyproject.toml").write_text("invalid [ toml")

        # Act
        paths = get_source_paths_from_pyproject(mock_repo_path)

        # Assert
        assert paths == []


class TestUpdateRuffConfig:
    """Test suite for update_ruff_config function."""

    def test_update_ruff_config_adds_docstring_rules(self, parsed_pyproject: dict[str, Any]) -> None:
        """Test adding docstring linting rules to ruff configuration.

        Tests: update_ruff_config adds DOC and D rules
        How: Call function with minimal config, verify rules added
        Why: Documentation projects should enforce docstring standards

        Args:
            parsed_pyproject: Minimal pyproject configuration
        """
        # Act
        updated = update_ruff_config(parsed_pyproject)

        # Assert
        assert "tool" in updated
        assert "ruff" in updated["tool"]
        assert "lint" in updated["tool"]["ruff"]
        assert "select" in updated["tool"]["ruff"]["lint"]
        assert "DOC" in updated["tool"]["ruff"]["lint"]["select"]
        assert "D" in updated["tool"]["ruff"]["lint"]["select"]

    def test_update_ruff_config_preserves_existing_rules(self) -> None:
        """Test updating ruff config preserves existing lint rules.

        Tests: update_ruff_config doesn't remove existing rules
        How: Provide config with existing select rules, verify preserved
        Why: Should add docstring rules without removing other rules

        """
        # Arrange
        config = {
            "project": {"name": "test"},
            "tool": {
                "ruff": {
                    "lint": {
                        "select": ["E", "F", "I"]
                    }
                }
            }
        }

        # Act
        updated = update_ruff_config(config)

        # Assert
        select = updated["tool"]["ruff"]["lint"]["select"]
        assert "E" in select
        assert "F" in select
        assert "I" in select
        assert "DOC" in select
        assert "D" in select

    def test_update_ruff_config_idempotent(self) -> None:
        """Test updating ruff config is idempotent.

        Tests: update_ruff_config doesn't duplicate rules
        How: Call function twice on same config
        Why: Re-running setup should not corrupt configuration

        """
        # Arrange
        config = {"project": {"name": "test"}}

        # Act
        updated_once = update_ruff_config(config)
        updated_twice = update_ruff_config(updated_once)

        # Assert
        select = updated_twice["tool"]["ruff"]["lint"]["select"]
        assert select.count("DOC") == 1
        assert select.count("D") == 1
