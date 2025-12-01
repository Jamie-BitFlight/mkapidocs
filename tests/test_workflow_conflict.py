"""Tests for preventing conflicting workflow creation."""

from pathlib import Path

import pytest
from mkapidocs.generator import create_github_actions, create_gitlab_ci


def test_github_actions_existing_pages_job(mock_repo_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Test that pages.yml is not created if a pages deployment job exists."""
    github_dir = mock_repo_path / ".github" / "workflows"
    github_dir.mkdir(parents=True, exist_ok=True)

    # Create existing workflow with pages deployment
    (github_dir / "ci.yml").write_text("""
name: CI
on: [push]
jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Deploy to GitHub Pages
        id: deployment
        uses: actions/deploy-pages@v4
""")

    create_github_actions(mock_repo_path)

    # Verify pages.yml was NOT created
    assert not (github_dir / "pages.yml").exists()

    # Verify warning message
    captured = capsys.readouterr()
    assert "Found existing pages deployment job 'deploy' in 'ci.yml'" in captured.out
    assert "You should update it to run 'uv run mkapidocs build'" in captured.out


def test_github_actions_existing_pages_job_with_mkapidocs(
    mock_repo_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Test that pages.yml is not created if a pages deployment job exists and uses mkapidocs."""
    github_dir = mock_repo_path / ".github" / "workflows"
    github_dir.mkdir(parents=True, exist_ok=True)

    # Create existing workflow with pages deployment and mkapidocs
    (github_dir / "ci.yml").write_text("""
name: CI
on: [push]
jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: uv run mkapidocs build .
      - name: Deploy to GitHub Pages
        id: deployment
        uses: actions/deploy-pages@v4
""")

    create_github_actions(mock_repo_path)

    # Verify pages.yml was NOT created
    assert not (github_dir / "pages.yml").exists()

    # Verify success message
    captured = capsys.readouterr()
    assert "Found existing pages deployment job 'deploy' in 'ci.yml' using mkapidocs" in captured.out


def test_github_actions_no_conflict(mock_repo_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Test that pages.yml IS created if no pages deployment job exists."""
    github_dir = mock_repo_path / ".github" / "workflows"
    github_dir.mkdir(parents=True, exist_ok=True)

    # Create existing workflow WITHOUT pages deployment
    (github_dir / "ci.yml").write_text("""
name: CI
on: [push]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: pytest
""")

    create_github_actions(mock_repo_path)

    # Verify pages.yml WAS created
    assert (github_dir / "pages.yml").exists()

    captured = capsys.readouterr()
    assert "Created pages.yml" in captured.out


def test_gitlab_ci_existing_pages_job(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Test when .gitlab-ci.yml already has a pages job (via include)."""
    (tmp_path / ".gitlab-ci.yml").write_text("include:\n  - local: .gitlab/workflows/pages.gitlab-ci.yml\n")

    # Create the included file too, to simulate a real setup
    workflows_dir = tmp_path / ".gitlab" / "workflows"
    workflows_dir.mkdir(parents=True)
    (workflows_dir / "pages.gitlab-ci.yml").write_text("pages:\n  script:\n    - echo 'deploy'\n")

    create_gitlab_ci(tmp_path)

    assert (tmp_path / ".gitlab-ci.yml").read_text() == "include:\n  - local: .gitlab/workflows/pages.gitlab-ci.yml\n"
    captured = capsys.readouterr()
    assert "Found existing pages workflow include" in captured.out


def test_gitlab_ci_existing_pages_job_with_mkapidocs(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Test when .gitlab-ci.yml already has a pages job using mkapidocs (via include)."""
    (tmp_path / ".gitlab-ci.yml").write_text("include:\n  - local: .gitlab/workflows/pages.gitlab-ci.yml\n")

    workflows_dir = tmp_path / ".gitlab" / "workflows"
    workflows_dir.mkdir(parents=True)
    (workflows_dir / "pages.gitlab-ci.yml").write_text("pages:\n  script:\n    - uv run mkapidocs build\n")

    create_gitlab_ci(tmp_path)

    assert (tmp_path / ".gitlab-ci.yml").read_text() == "include:\n  - local: .gitlab/workflows/pages.gitlab-ci.yml\n"
    captured = capsys.readouterr()
    assert "Found existing pages workflow include" in captured.out


def test_gitlab_ci_no_conflict(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Test when .gitlab-ci.yml exists but has no pages job."""
    (tmp_path / ".gitlab-ci.yml").write_text("stages:\n  - test\n")

    create_gitlab_ci(tmp_path)

    content = (tmp_path / ".gitlab-ci.yml").read_text()
    assert "include:" in content
    assert ".gitlab/workflows/pages.gitlab-ci.yml" in content
    assert (tmp_path / ".gitlab" / "workflows" / "pages.gitlab-ci.yml").exists()

    captured = capsys.readouterr()
    assert "Added include to .gitlab-ci.yml" in captured.out or "Appended include to .gitlab-ci.yml" in captured.out
