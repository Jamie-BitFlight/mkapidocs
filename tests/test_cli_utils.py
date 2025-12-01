"""Tests for CLI utility functions."""
# pyright: reportPrivateUsage=false

from pathlib import Path

import pytest
import typer
from mkapidocs.cli import (
    _configure_logging,
    _find_git_root,
    _generate_success_message,
    _get_deployment_command,
    _validate_provider,
    console,
)
from mkapidocs.generator import console as generator_console
from mkapidocs.models import CIProvider
from mkapidocs.validators import console as validators_console
from mkapidocs.yaml_utils import console as yaml_console
from pytest_mock import MockerFixture


def test_find_git_root_at_root(mock_repo_path: Path) -> None:
    """Test finding git root when at the root."""
    # Ensure .git exists (mock_repo_path fixture might not create it by default unless using mock_git_repo)
    (mock_repo_path / ".git").mkdir(exist_ok=True)

    found = _find_git_root(mock_repo_path)
    assert found == mock_repo_path


def test_find_git_root_from_subdir(mock_repo_path: Path) -> None:
    """Test finding git root from a subdirectory."""
    (mock_repo_path / ".git").mkdir(exist_ok=True)
    subdir = mock_repo_path / "subdir" / "nested"
    subdir.mkdir(parents=True)

    found = _find_git_root(subdir)
    assert found == mock_repo_path


def test_find_git_root_worktree(mock_repo_path: Path) -> None:
    """Test finding git root in a worktree (where .git is a file)."""
    # Create .git as a file
    (mock_repo_path / ".git").write_text("gitdir: /path/to/repo.git")

    found = _find_git_root(mock_repo_path)
    assert found == mock_repo_path


def test_validate_provider_valid() -> None:
    """Test validating valid providers."""
    assert _validate_provider("github") == CIProvider.GITHUB
    assert _validate_provider("GitHub") == CIProvider.GITHUB
    assert _validate_provider("gitlab") == CIProvider.GITLAB
    assert _validate_provider("GitLab") == CIProvider.GITLAB


def test_validate_provider_none() -> None:
    """Test validating None provider."""
    assert _validate_provider(None) is None


def test_validate_provider_invalid() -> None:
    """Test validating invalid provider."""
    with pytest.raises(typer.Exit):
        _validate_provider("invalid")


def test_configure_logging(mocker: MockerFixture) -> None:
    """Test logging configuration."""
    # Reset quiet state
    console.quiet = False
    generator_console.quiet = False
    validators_console.quiet = False
    yaml_console.quiet = False

    _configure_logging(True)

    assert console.quiet is True
    assert generator_console.quiet is True
    assert validators_console.quiet is True
    assert yaml_console.quiet is True

    # Reset quiet state for other tests
    console.quiet = False
    generator_console.quiet = False
    validators_console.quiet = False
    yaml_console.quiet = False


def test_get_deployment_command() -> None:
    """Test deployment command generation."""
    cmd_github = _get_deployment_command(CIProvider.GITHUB)
    assert ".github/" in cmd_github
    assert "git push" in cmd_github

    cmd_gitlab = _get_deployment_command(CIProvider.GITLAB)
    assert ".gitlab-ci.yml" in cmd_gitlab
    assert "git push" in cmd_gitlab


def test_generate_success_message(mock_repo_path: Path) -> None:
    """Test success message generation."""
    msg = _generate_success_message(mock_repo_path, CIProvider.GITHUB)
    assert str(mock_repo_path.name) in msg
    assert "uv run mkapidocs serve" in msg
    assert ".github/" in msg
