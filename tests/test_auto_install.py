"""Tests for auto-install functionality."""

from __future__ import annotations

from pathlib import Path

from mkapidocs.generator import ensure_mkapidocs_installed
from pytest_mock import MockerFixture


class TestEnsureMkapidocsInstalled:
    """Test suite for ensure_mkapidocs_installed function."""

    def test_uv_not_installed(self, mock_repo_path: Path, mocker: MockerFixture) -> None:
        """Test when uv is not installed.

        Tests: ensure_mkapidocs_installed returns early if uv not found
        How: Mock which to return None
        """
        # Arrange
        mocker.patch("mkapidocs.generator.which", return_value=None)
        mock_console = mocker.patch("mkapidocs.generator.console")

        # Act
        ensure_mkapidocs_installed(mock_repo_path)

        # Assert - should print warning about uv not found
        mock_console.print.assert_called()
        args = mock_console.print.call_args_list[1][0][0]
        assert "uv not found" in args

    def test_installs_from_registry_when_not_in_source(self, mock_repo_path: Path, mocker: MockerFixture) -> None:
        """Test installing mkapidocs from registry when not running from source.

        Tests: ensure_mkapidocs_installed uses 'uv add --dev' when not in source repo
        How: Mock _get_mkapidocs_repo_root to return None
        """
        # Arrange
        mocker.patch("mkapidocs.generator.which", return_value="/usr/local/bin/uv")
        mocker.patch("mkapidocs.generator._get_mkapidocs_repo_root", return_value=None)
        mock_subprocess = mocker.patch("mkapidocs.generator._run_subprocess")

        # Act
        ensure_mkapidocs_installed(mock_repo_path)

        # Assert
        mock_subprocess.assert_called_once()
        cmd = mock_subprocess.call_args[0][0]
        assert "uv" in cmd[0]
        assert "add" in cmd
        assert "--dev" in cmd
        assert "mkapidocs" in cmd

    def test_installs_editable_when_in_source(self, mock_repo_path: Path, mocker: MockerFixture) -> None:
        """Test installing mkapidocs in editable mode when running from source.

        Tests: ensure_mkapidocs_installed uses 'uv pip install -e' when in source repo
        How: Mock _get_mkapidocs_repo_root to return a path
        """
        # Arrange
        source_path = Path("/home/user/repos/mkapidocs")
        mocker.patch("mkapidocs.generator.which", return_value="/usr/local/bin/uv")
        mocker.patch("mkapidocs.generator._get_mkapidocs_repo_root", return_value=source_path)
        mock_subprocess = mocker.patch("mkapidocs.generator._run_subprocess")

        # Act
        ensure_mkapidocs_installed(mock_repo_path)

        # Assert - should call sync first, then pip install -e
        assert mock_subprocess.call_count == 2
        # First call: sync
        sync_cmd = mock_subprocess.call_args_list[0][0][0]
        assert "sync" in sync_cmd
        # Second call: pip install -e
        install_cmd = mock_subprocess.call_args_list[1][0][0]
        assert "pip" in install_cmd
        assert "install" in install_cmd
        assert "-e" in install_cmd
        assert str(source_path) in install_cmd

    def test_install_fails_gracefully(self, mock_repo_path: Path, mocker: MockerFixture) -> None:
        """Test handling of installation failure.

        Tests: ensure_mkapidocs_installed handles install failure gracefully
        How: Mock _run_subprocess to raise exception
        """
        # Arrange
        mocker.patch("mkapidocs.generator.which", return_value="/usr/local/bin/uv")
        mocker.patch("mkapidocs.generator._get_mkapidocs_repo_root", return_value=None)
        mocker.patch("mkapidocs.generator._run_subprocess", side_effect=RuntimeError("Install failed"))
        mock_console = mocker.patch("mkapidocs.generator.console")

        # Act
        ensure_mkapidocs_installed(mock_repo_path)

        # Assert - should print warning
        mock_console.print.assert_called()
        # Find the warning call
        warning_printed = False
        for call in mock_console.print.call_args_list:
            if "Failed to inject mkapidocs" in str(call):
                warning_printed = True
                break
        assert warning_printed

    def test_removes_virtual_env_from_environment(self, mock_repo_path: Path, mocker: MockerFixture) -> None:
        """Test that VIRTUAL_ENV is removed from environment before running uv.

        Tests: ensure_mkapidocs_installed unsets VIRTUAL_ENV
        How: Mock environment with VIRTUAL_ENV and verify it's not passed to subprocess
        """
        # Arrange
        mocker.patch("mkapidocs.generator.which", return_value="/usr/local/bin/uv")
        mocker.patch("mkapidocs.generator._get_mkapidocs_repo_root", return_value=None)
        mocker.patch.dict("os.environ", {"VIRTUAL_ENV": "/some/venv"})
        mock_subprocess = mocker.patch("mkapidocs.generator._run_subprocess")

        # Act
        ensure_mkapidocs_installed(mock_repo_path)

        # Assert - check that VIRTUAL_ENV was not passed in env
        call_env = mock_subprocess.call_args[0][2]
        assert "VIRTUAL_ENV" not in call_env
