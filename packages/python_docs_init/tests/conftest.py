"""Pytest configuration for Python Documentation Init."""

import pytest


@pytest.fixture
def sample_data() -> dict[str, str]:
    """Provide sample data for tests.

    Returns:
        Dictionary with sample test data
    """
    return {
        "project_name": "Python Documentation Init",
        "project_slug": "python_docs_init",
        "description": "Automated documentation setup tool for Python projects using MkDocs and GitLab Pages",
    }


@pytest.fixture
def mock_console(monkeypatch: pytest.MonkeyPatch) -> None:
    """Mock Rich console to prevent actual terminal output during tests.

    Args:
        monkeypatch: pytest fixture for monkey patching
    """
    from unittest.mock import MagicMock

    from python_docs_init import cli

    mock = MagicMock()
    monkeypatch.setattr(cli, "console", mock)
