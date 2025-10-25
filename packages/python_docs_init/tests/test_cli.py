"""Tests for Python Documentation Init CLI."""

from importlib import metadata

import pytest
from typer.testing import CliRunner

from python_docs_init.cli import app

runner = CliRunner()


def test_version_command() -> None:
    """Test the version command displays correct version."""
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert "Python Documentation Init" in result.stdout
    # Verify version is displayed
    version = metadata.version("python_docs_init")
    assert version in result.stdout


def test_info_command() -> None:
    """Test the info command displays package information."""
    result = runner.invoke(app, ["info"])
    assert result.exit_code == 0
    assert "Python Documentation Init" in result.stdout
    assert "Unlicense" in result.stdout


def test_help_command() -> None:
    """Test the help command works."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "Python Documentation Init" in result.stdout
    assert "Automated documentation setup tool for Python projects using MkDocs and GitLab Pages" in result.stdout


def test_verbose_flag() -> None:
    """Test that verbose flag is accepted."""
    result = runner.invoke(app, ["--verbose", "version"])
    assert result.exit_code == 0


def test_no_command_shows_help() -> None:
    """Test that running without command shows help."""
    result = runner.invoke(app, [])
    assert result.exit_code == 0
    assert "Python Documentation Init" in result.stdout
