"""Tests for pyproject.toml utility functions.

Tests cover:
- Reading pyproject.toml files
- Writing pyproject.toml files
- Extracting source paths from build configuration
- Updating ruff configuration
"""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest
from mkapidocs.generator import read_pyproject, update_ruff_config, write_pyproject

# Import Pydantic models for test assertions
# Import Pydantic models for test assertions
from mkapidocs.models import ProjectConfig, PyprojectConfig

# Wrappers removed, using direct imports


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
        assert config.project.name == "test-project"
        assert config.project.version == "0.1.0"

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
        config = PyprojectConfig(project=ProjectConfig(name="new-project", version="1.0.0"))

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
        new_config = PyprojectConfig(project=ProjectConfig(name="updated-project", version="2.0.0"))

        # Act
        write_pyproject(mock_pyproject_toml.parent, new_config)

        # Assert
        with open(mock_pyproject_toml, "rb") as f:
            written_config = tomllib.load(f)

        assert written_config["project"]["name"] == "updated-project"
        assert written_config["project"]["version"] == "2.0.0"


class TestUpdateRuffConfig:
    """Test suite for update_ruff_config function."""

    def test_update_ruff_config_adds_docstring_rules(self) -> None:
        """Test adding docstring linting rules to ruff configuration.

        Tests: update_ruff_config adds DOC and D rules
        How: Call function with minimal config, verify rules added
        Why: Documentation projects should enforce docstring standards

        """
        # Arrange
        pyproject = PyprojectConfig(project=ProjectConfig(name="test"))

        # Act
        updated = update_ruff_config(pyproject)

        # Assert
        # Assert
        assert "DOC" in updated.ruff_lint_select
        assert "D" in updated.ruff_lint_select

    def test_update_ruff_config_preserves_existing_rules(self) -> None:
        """Test updating ruff config preserves existing lint rules.

        Tests: update_ruff_config doesn't remove existing rules
        How: Provide config with existing select rules, verify preserved
        Why: Should add docstring rules without removing other rules

        """
        # Arrange
        config = PyprojectConfig(
            project=ProjectConfig(name="test"), tool={"ruff": {"lint": {"select": ["E", "F", "I"]}}}
        )

        # Act
        updated = update_ruff_config(config)

        # Assert
        select = updated.ruff_lint_select
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
        config = PyprojectConfig(project=ProjectConfig(name="test"))

        # Act
        updated_once = update_ruff_config(config)
        updated_twice = update_ruff_config(updated_once)

        # Assert
        select = updated_twice.ruff_lint_select
        assert select.count("DOC") == 1
        assert select.count("D") == 1
