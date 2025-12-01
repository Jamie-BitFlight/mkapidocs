"""Tests for auto-install functionality."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock

from mkapidocs.generator import ensure_mkapidocs_installed
from pytest_mock import MockerFixture


class TestEnsureMkapidocsInstalled:
    """Test suite for ensure_mkapidocs_installed function."""

    def test_already_installed(self, mock_repo_path: Path, mocker: MockerFixture) -> None:
        """Test when mkapidocs is already installed.

        Tests: ensure_mkapidocs_installed does nothing if installed
        How: Mock uv pip show to succeed
        """
        # Arrange
        mocker.patch("mkapidocs.generator.which", return_value="uv")
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value.returncode = 0

        # Act
        ensure_mkapidocs_installed(mock_repo_path)

        # Assert
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert args == ["uv", "pip", "show", "mkapidocs"]

    def test_not_installed_installs_successfully(self, mock_repo_path: Path, mocker: MockerFixture) -> None:
        """Test installing mkapidocs when missing.

        Tests: ensure_mkapidocs_installed installs if missing
        How: Mock uv pip show to fail, then uv add to succeed
        """
        # Arrange
        mocker.patch("mkapidocs.generator.which", return_value="uv")
        mock_run = mocker.patch("subprocess.run")
        # First call (show) fails, second call (add) succeeds
        mock_run.side_effect = [subprocess.CalledProcessError(1, ["uv", "pip", "show"]), MagicMock(returncode=0)]

        # Act
        ensure_mkapidocs_installed(mock_repo_path)

        # Assert
        assert mock_run.call_count == 2
        # First call: check
        assert mock_run.call_args_list[0][0][0] == ["uv", "pip", "show", "mkapidocs"]
        # Second call: install
        assert mock_run.call_args_list[1][0][0] == ["uv", "add", "--dev", "mkapidocs"]

    def test_install_fails(self, mock_repo_path: Path, mocker: MockerFixture) -> None:
        """Test handling of installation failure.

        Tests: ensure_mkapidocs_installed handles install failure gracefully
        How: Mock both calls to fail
        """
        # Arrange
        mock_run = mocker.patch("subprocess.run")
        mock_run.side_effect = subprocess.CalledProcessError(1, "cmd")
        mock_console = mocker.patch("mkapidocs.generator.console")

        # Act
        ensure_mkapidocs_installed(mock_repo_path)

        # Assert
        assert mock_run.call_count == 2
        mock_console.print.assert_called()
        # Should verify it printed the error message
        args = mock_console.print.call_args_list[-1][0][0]
        assert "Failed to install mkapidocs" in args
