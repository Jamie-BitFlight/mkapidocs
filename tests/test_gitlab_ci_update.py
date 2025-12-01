"""Tests for updating GitLab CI configuration."""

from pathlib import Path

import pytest
from mkapidocs.generator import create_gitlab_ci


def test_gitlab_ci_create_new(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Test creating a new .gitlab-ci.yml."""
    create_gitlab_ci(tmp_path)

    gitlab_ci_path = tmp_path / ".gitlab-ci.yml"
    assert gitlab_ci_path.exists()
    content = gitlab_ci_path.read_text(encoding="utf-8")
    assert "include:" in content
    assert ".gitlab/workflows/pages.gitlab-ci.yml" in content

    pages_workflow = tmp_path / ".gitlab" / "workflows" / "pages.gitlab-ci.yml"
    assert pages_workflow.exists()
    assert "pages:" in pages_workflow.read_text()
