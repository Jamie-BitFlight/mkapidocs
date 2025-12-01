"""Tests for GitLab CI generation logic."""

from __future__ import annotations

from pathlib import Path

from mkapidocs.generator import create_gitlab_ci
from mkapidocs.models import GitLabCIConfig
from pytest_mock import MockerFixture


def test_create_gitlab_ci_adds_deploy_stage_when_missing(tmp_path: Path, mocker: MockerFixture) -> None:
    """Test that deploy stage is added when missing from existing stages."""
    # Arrange
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    gitlab_ci_path = repo_path / ".gitlab-ci.yml"

    # Create .gitlab-ci.yml with stages but no deploy
    gitlab_ci_path.write_text("stages:\n  - test\n  - build\n\ninclude:\n  - local: .gitlab/workflows/other.yml\n")

    # Mock console to avoid output spam
    mocker.patch("mkapidocs.generator.console")

    # Act
    create_gitlab_ci(repo_path)

    # Assert
    content = gitlab_ci_path.read_text()
    assert "deploy" in content
    assert "- deploy" in content

    # Verify valid YAML structure
    config = GitLabCIConfig.load(gitlab_ci_path)
    assert config is not None
    assert config.stages is not None
    assert "deploy" in config.stages


def test_create_gitlab_ci_preserves_existing_deploy_stage(tmp_path: Path, mocker: MockerFixture) -> None:
    """Test that existing deploy stage is preserved and not duplicated."""
    # Arrange
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    gitlab_ci_path = repo_path / ".gitlab-ci.yml"

    # Create .gitlab-ci.yml with existing deploy stage
    initial_content = "stages:\n  - test\n  - deploy\n"
    gitlab_ci_path.write_text(initial_content)

    mocker.patch("mkapidocs.generator.console")

    # Act
    create_gitlab_ci(repo_path)

    # Assert
    content = gitlab_ci_path.read_text()
    # Should still have deploy, and only once if we count lines (rough check)
    assert content.count("- deploy") == 1

    config = GitLabCIConfig.load(gitlab_ci_path)
    assert config is not None
    assert config.stages is not None
    assert "deploy" in config.stages


def test_create_gitlab_ci_creates_stages_if_missing(tmp_path: Path, mocker: MockerFixture) -> None:
    """Test that stages block is created if it doesn't exist."""
    # Arrange
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    gitlab_ci_path = repo_path / ".gitlab-ci.yml"

    # Create .gitlab-ci.yml without stages
    gitlab_ci_path.write_text("variables:\n  FOO: bar\n")

    mocker.patch("mkapidocs.generator.console")

    # Act
    create_gitlab_ci(repo_path)

    # Assert
    content = gitlab_ci_path.read_text()
    assert "stages:" in content
    assert "- deploy" in content

    config = GitLabCIConfig.load(gitlab_ci_path)
    assert config is not None
    assert config.stages is not None
    assert "deploy" in config.stages
