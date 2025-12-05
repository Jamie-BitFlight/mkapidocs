"""Tests for build and serve functions in mkapidocs.

Tests cover:
- build_docs(): MkDocs build integration with various flags
- serve_docs(): MkDocs serve integration with custom host/port
- is_mkapidocs_in_target_env(): Check if mkapidocs installed in target env
- Error handling: missing files, missing commands, subprocess failures
"""

from __future__ import annotations

import shutil
import subprocess
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest

from mkapidocs.builder import build_docs, is_mkapidocs_in_target_env, serve_docs

if TYPE_CHECKING:
    from pathlib import Path

    from pytest_mock import MockerFixture

# Get actual uv path for assertions (may be None if not installed)
ACTUAL_UV_PATH = shutil.which("uv")


class TestBuildDocs:
    """Test suite for build_docs() function.

    Tests MkDocs build command integration, subprocess handling, and error cases.
    """

    def test_build_docs_success(
        self, mocker: MockerFixture, mock_repo_path: Path
    ) -> None:
        """Test successful documentation build via target environment.

        Tests: build_docs() basic functionality via target environment path
        How: Mock mkdocs.yml existence, subprocess.run, and mkapidocs in target env
        Why: Verify build command construction and execution

        Args:
            mocker: pytest-mock fixture for mocking
            mock_repo_path: Temporary repository directory
        """
        # Arrange
        (mock_repo_path / "mkdocs.yml").write_text("site_name: Test\n")
        docs_dir = mock_repo_path / "docs"
        docs_dir.mkdir()

        # Mock mkapidocs installed in target env
        mocker.patch("mkapidocs.builder.is_mkapidocs_in_target_env", return_value=True)
        mocker.patch("mkapidocs.builder.is_running_in_target_env", return_value=False)
        mocker.patch(
            "mkapidocs.builder.which",
            return_value=ACTUAL_UV_PATH or "/usr/local/bin/uv",
        )
        mock_result = mocker.MagicMock()
        mock_result.returncode = 0
        mock_subprocess = mocker.patch(
            "mkapidocs.builder.subprocess.run", return_value=mock_result
        )

        # Act
        exit_code = build_docs(mock_repo_path)

        # Assert
        assert exit_code == 0
        mock_subprocess.assert_called_once()
        cmd = mock_subprocess.call_args[0][0]
        # Check that uv was used (path may vary by environment)
        assert "uv" in cmd[0] or cmd[0].endswith("uv")
        assert "mkapidocs" in cmd
        assert "build" in cmd

    def test_build_docs_with_strict_flag(
        self, mocker: MockerFixture, mock_repo_path: Path
    ) -> None:
        """Test build with --strict flag treats warnings as errors.

        Tests: build_docs(strict=True)
        How: Mock successful build, verify --strict in command args
        Why: Ensure strict mode is properly passed to mkdocs

        Args:
            mocker: pytest-mock fixture for mocking
            mock_repo_path: Temporary repository directory
        """
        # Arrange
        (mock_repo_path / "mkdocs.yml").write_text("site_name: Test\n")
        (mock_repo_path / "docs").mkdir()

        mocker.patch("mkapidocs.builder.is_mkapidocs_in_target_env", return_value=True)
        mocker.patch("mkapidocs.builder.is_running_in_target_env", return_value=False)
        mocker.patch(
            "mkapidocs.builder.which",
            return_value=ACTUAL_UV_PATH or "/usr/local/bin/uv",
        )
        mock_result = mocker.MagicMock()
        mock_result.returncode = 0
        mock_subprocess = mocker.patch(
            "mkapidocs.builder.subprocess.run", return_value=mock_result
        )

        # Act
        exit_code = build_docs(mock_repo_path, strict=True)

        # Assert
        assert exit_code == 0
        cmd = mock_subprocess.call_args[0][0]
        assert "--strict" in cmd

    def test_build_docs_with_custom_output_dir(
        self, mocker: MockerFixture, mock_repo_path: Path, tmp_path: Path
    ) -> None:
        """Test build with custom output directory.

        Tests: build_docs(output_dir=custom_path)
        How: Mock successful build, verify --output-dir in command args
        Why: Ensure custom output location is properly passed to mkdocs

        Args:
            mocker: pytest-mock fixture for mocking
            mock_repo_path: Temporary repository directory
            tmp_path: Pytest temporary directory
        """
        # Arrange
        (mock_repo_path / "mkdocs.yml").write_text("site_name: Test\n")
        (mock_repo_path / "docs").mkdir()
        custom_output = tmp_path / "custom_site"

        mocker.patch("mkapidocs.builder.is_mkapidocs_in_target_env", return_value=True)
        mocker.patch("mkapidocs.builder.is_running_in_target_env", return_value=False)
        mocker.patch(
            "mkapidocs.builder.which",
            return_value=ACTUAL_UV_PATH or "/usr/local/bin/uv",
        )
        mock_result = mocker.MagicMock()
        mock_result.returncode = 0
        mock_subprocess = mocker.patch(
            "mkapidocs.builder.subprocess.run", return_value=mock_result
        )

        # Act
        exit_code = build_docs(mock_repo_path, output_dir=custom_output)

        # Assert
        assert exit_code == 0
        cmd = mock_subprocess.call_args[0][0]
        assert "--output-dir" in cmd
        assert str(custom_output) in cmd

    def test_build_docs_missing_mkdocs_yml(self, mock_repo_path: Path) -> None:
        """Test build fails with FileNotFoundError when mkdocs.yml missing.

        Tests: build_docs() error handling
        How: Call build_docs without creating mkdocs.yml
        Why: Verify validation prevents build attempt on unconfigured project

        Args:
            mock_repo_path: Temporary repository directory
        """
        # Act & Assert
        with pytest.raises(FileNotFoundError, match=r"mkdocs\.yml not found"):
            build_docs(mock_repo_path)

    def test_build_docs_missing_uv_command(
        self, mocker: MockerFixture, mock_repo_path: Path
    ) -> None:
        """Test build fails when uv command not found.

        Tests: build_docs() error handling
        How: Mock which() to return None for uv, but mkapidocs is in target env
        Why: Verify helpful error when uv not installed

        Args:
            mocker: pytest-mock fixture for mocking
            mock_repo_path: Temporary repository directory
        """
        # Arrange
        (mock_repo_path / "mkdocs.yml").write_text("site_name: Test\n")
        (mock_repo_path / "docs").mkdir()

        mocker.patch("mkapidocs.builder.is_mkapidocs_in_target_env", return_value=True)
        mocker.patch("mkapidocs.builder.is_running_in_target_env", return_value=False)
        mocker.patch("mkapidocs.builder.which", return_value=None)

        # Act & Assert
        with pytest.raises(FileNotFoundError, match="uv command not found"):
            build_docs(mock_repo_path)

    def test_build_docs_mkapidocs_not_installed(
        self, mocker: MockerFixture, mock_repo_path: Path
    ) -> None:
        """Test build fails with RuntimeError when mkapidocs not in target env.

        Tests: build_docs() error handling
        How: Mock is_mkapidocs_in_target_env to return False
        Why: Verify user is told to run setup first

        Args:
            mocker: pytest-mock fixture for mocking
            mock_repo_path: Temporary repository directory
        """
        # Arrange
        (mock_repo_path / "mkdocs.yml").write_text("site_name: Test\n")
        (mock_repo_path / "docs").mkdir()

        mocker.patch("mkapidocs.builder.is_mkapidocs_in_target_env", return_value=False)
        mocker.patch("mkapidocs.builder.is_running_in_target_env", return_value=False)

        # Act & Assert
        with pytest.raises(RuntimeError, match="mkapidocs is not installed"):
            build_docs(mock_repo_path)

    def test_build_docs_subprocess_failure(
        self, mocker: MockerFixture, mock_repo_path: Path
    ) -> None:
        """Test build returns non-zero exit code on mkdocs failure.

        Tests: build_docs() subprocess error handling
        How: Mock subprocess.run to return non-zero exit code
        Why: Verify build failures are propagated to caller

        Args:
            mocker: pytest-mock fixture for mocking
            mock_repo_path: Temporary repository directory
        """
        # Arrange
        (mock_repo_path / "mkdocs.yml").write_text("site_name: Test\n")
        (mock_repo_path / "docs").mkdir()

        mocker.patch("mkapidocs.builder.is_mkapidocs_in_target_env", return_value=True)
        mocker.patch("mkapidocs.builder.is_running_in_target_env", return_value=False)
        mocker.patch(
            "mkapidocs.builder.which",
            return_value=ACTUAL_UV_PATH or "/usr/local/bin/uv",
        )
        mock_result = mocker.MagicMock()
        mock_result.returncode = 1
        mocker.patch("mkapidocs.builder.subprocess.run", return_value=mock_result)

        # Act
        exit_code = build_docs(mock_repo_path)

        # Assert
        assert exit_code == 1

    def test_build_docs_internal_call_uses_mkdocs_directly(
        self, mocker: MockerFixture, mock_repo_path: Path
    ) -> None:
        """Test internal calls (via MKAPIDOCS_INTERNAL_CALL) use mkdocs directly.

        Tests: build_docs() internal call path
        How: Mock is_running_in_target_env to return True, verify mkdocs is called directly
        Why: Prevent infinite recursion and use mkdocs directly when already in target env

        Args:
            mocker: pytest-mock fixture for mocking
            mock_repo_path: Temporary repository directory
        """
        # Arrange
        (mock_repo_path / "mkdocs.yml").write_text("site_name: Test\n")
        (mock_repo_path / "docs").mkdir()

        mocker.patch("mkapidocs.builder.is_running_in_target_env", return_value=True)
        mocker.patch("mkapidocs.builder.which", return_value="/usr/bin/mkdocs")
        mock_result = mocker.MagicMock()
        mock_result.returncode = 0
        mock_subprocess = mocker.patch(
            "mkapidocs.builder.subprocess.run", return_value=mock_result
        )

        # Act
        exit_code = build_docs(mock_repo_path)

        # Assert
        assert exit_code == 0
        cmd = mock_subprocess.call_args[0][0]
        assert cmd[0] == "/usr/bin/mkdocs"
        assert "build" in cmd


class TestServeDocs:
    """Test suite for serve_docs() function.

    Tests MkDocs serve command integration, subprocess handling, and error cases.
    """

    def test_serve_docs_success(
        self, mocker: MockerFixture, mock_repo_path: Path
    ) -> None:
        """Test successful documentation server start via target environment.

        Tests: serve_docs() basic functionality via target environment path
        How: Mock mkdocs.yml existence, subprocess.Popen, and mkapidocs in target env
        Why: Verify serve command construction and execution

        Args:
            mocker: pytest-mock fixture for mocking
            mock_repo_path: Temporary repository directory
        """
        # Arrange
        (mock_repo_path / "mkdocs.yml").write_text("site_name: Test\n")
        docs_dir = mock_repo_path / "docs"
        docs_dir.mkdir()

        # Mock mkapidocs installed in target env
        mocker.patch("mkapidocs.builder.is_mkapidocs_in_target_env", return_value=True)
        mocker.patch("mkapidocs.builder.is_running_in_target_env", return_value=False)
        mocker.patch(
            "mkapidocs.builder.which",
            return_value=ACTUAL_UV_PATH or "/usr/local/bin/uv",
        )
        mocker.patch("mkapidocs.builder._is_port_in_use", return_value=False)

        mock_process = mocker.MagicMock()
        mock_process.wait.return_value = 0
        mock_popen = mocker.patch(
            "mkapidocs.builder.subprocess.Popen", return_value=mock_process
        )

        # Act
        exit_code = serve_docs(mock_repo_path)

        # Assert
        assert exit_code == 0
        mock_popen.assert_called_once()
        cmd = mock_popen.call_args[0][0]
        # Check that uv was used (path may vary by environment)
        assert "uv" in cmd[0] or cmd[0].endswith("uv")
        assert "mkapidocs" in cmd
        assert "serve" in cmd

    def test_serve_docs_with_custom_host_and_port(
        self, mocker: MockerFixture, mock_repo_path: Path
    ) -> None:
        """Test serve with custom host and port.

        Tests: serve_docs(host='0.0.0.0', port=9000)
        How: Mock subprocess, verify --host and --port in command args
        Why: Ensure custom server address is properly passed to mkapidocs

        Args:
            mocker: pytest-mock fixture for mocking
            mock_repo_path: Temporary repository directory
        """
        # Arrange
        (mock_repo_path / "mkdocs.yml").write_text("site_name: Test\n")
        (mock_repo_path / "docs").mkdir()

        mocker.patch("mkapidocs.builder.is_mkapidocs_in_target_env", return_value=True)
        mocker.patch("mkapidocs.builder.is_running_in_target_env", return_value=False)
        mocker.patch(
            "mkapidocs.builder.which",
            return_value=ACTUAL_UV_PATH or "/usr/local/bin/uv",
        )
        mocker.patch("mkapidocs.builder._is_port_in_use", return_value=False)

        mock_process = mocker.MagicMock()
        mock_process.wait.return_value = 0
        mock_popen = mocker.patch(
            "mkapidocs.builder.subprocess.Popen", return_value=mock_process
        )

        # Act
        exit_code = serve_docs(mock_repo_path, host="0.0.0.0", port=9000)

        # Assert
        assert exit_code == 0
        cmd = mock_popen.call_args[0][0]
        assert "--host" in cmd
        assert "0.0.0.0" in cmd
        assert "--port" in cmd
        assert "9000" in cmd

    def test_serve_docs_default_address(
        self, mocker: MockerFixture, mock_repo_path: Path
    ) -> None:
        """Test serve uses default localhost:8000 when not specified.

        Tests: serve_docs() default parameters
        How: Mock subprocess, verify default --host and --port
        Why: Ensure sensible defaults for local development

        Args:
            mocker: pytest-mock fixture for mocking
            mock_repo_path: Temporary repository directory
        """
        # Arrange
        (mock_repo_path / "mkdocs.yml").write_text("site_name: Test\n")
        (mock_repo_path / "docs").mkdir()

        mocker.patch("mkapidocs.builder.is_mkapidocs_in_target_env", return_value=True)
        mocker.patch("mkapidocs.builder.is_running_in_target_env", return_value=False)
        mocker.patch(
            "mkapidocs.builder.which",
            return_value=ACTUAL_UV_PATH or "/usr/local/bin/uv",
        )
        mocker.patch("mkapidocs.builder._is_port_in_use", return_value=False)

        mock_process = mocker.MagicMock()
        mock_process.wait.return_value = 0
        mock_popen = mocker.patch(
            "mkapidocs.builder.subprocess.Popen", return_value=mock_process
        )

        # Act
        serve_docs(mock_repo_path)

        # Assert
        cmd = mock_popen.call_args[0][0]
        assert "--host" in cmd
        assert "127.0.0.1" in cmd
        assert "--port" in cmd
        assert "8000" in cmd

    def test_serve_docs_keyboard_interrupt_graceful_exit(
        self, mocker: MockerFixture, mock_repo_path: Path
    ) -> None:
        """Test serve handles Ctrl+C (KeyboardInterrupt) gracefully.

        Tests: serve_docs() KeyboardInterrupt handling
        How: Mock subprocess.Popen.wait to raise KeyboardInterrupt first, then return
        Why: Verify clean shutdown on user interrupt

        Args:
            mocker: pytest-mock fixture for mocking
            mock_repo_path: Temporary repository directory
        """
        # Arrange
        (mock_repo_path / "mkdocs.yml").write_text("site_name: Test\n")
        (mock_repo_path / "docs").mkdir()

        mocker.patch("mkapidocs.builder.is_mkapidocs_in_target_env", return_value=True)
        mocker.patch("mkapidocs.builder.is_running_in_target_env", return_value=False)
        mocker.patch(
            "mkapidocs.builder.which",
            return_value=ACTUAL_UV_PATH or "/usr/local/bin/uv",
        )
        mocker.patch("mkapidocs.builder._is_port_in_use", return_value=False)

        mock_process = mocker.MagicMock()
        # First wait() raises KeyboardInterrupt, second wait() (after signal) returns normally
        mock_process.wait.side_effect = [KeyboardInterrupt, 0]
        mocker.patch("mkapidocs.builder.subprocess.Popen", return_value=mock_process)

        # Act
        exit_code = serve_docs(mock_repo_path)

        # Assert
        assert exit_code == 0
        # Verify SIGINT was sent to child process
        # mock_process.send_signal.assert_called() - No longer called, we rely on OS signal propagation

    def test_serve_docs_missing_mkdocs_yml(self, mock_repo_path: Path) -> None:
        """Test serve fails with FileNotFoundError when mkdocs.yml missing.

        Tests: serve_docs() error handling
        How: Call serve_docs without creating mkdocs.yml
        Why: Verify validation prevents serve attempt on unconfigured project

        Args:
            mock_repo_path: Temporary repository directory
        """
        # Act & Assert
        with pytest.raises(FileNotFoundError, match=r"mkdocs\.yml not found"):
            serve_docs(mock_repo_path)

    def test_serve_docs_missing_uv_command(
        self, mocker: MockerFixture, mock_repo_path: Path
    ) -> None:
        """Test serve fails when uv command not found.

        Tests: serve_docs() error handling
        How: Mock which() to return None for uv, but mkapidocs is in target env
        Why: Verify helpful error when uv not installed

        Args:
            mocker: pytest-mock fixture for mocking
            mock_repo_path: Temporary repository directory
        """
        # Arrange
        (mock_repo_path / "mkdocs.yml").write_text("site_name: Test\n")
        (mock_repo_path / "docs").mkdir()

        mocker.patch("mkapidocs.builder.is_mkapidocs_in_target_env", return_value=True)
        mocker.patch("mkapidocs.builder.is_running_in_target_env", return_value=False)
        mocker.patch("mkapidocs.builder.which", return_value=None)
        mocker.patch("mkapidocs.builder._is_port_in_use", return_value=False)

        # Act & Assert
        with pytest.raises(FileNotFoundError, match="uv command not found"):
            serve_docs(mock_repo_path)

    def test_serve_docs_mkapidocs_not_installed(
        self, mocker: MockerFixture, mock_repo_path: Path
    ) -> None:
        """Test serve fails with RuntimeError when mkapidocs not in target env.

        Tests: serve_docs() error handling
        How: Mock is_mkapidocs_in_target_env to return False
        Why: Verify user is told to run setup first

        Args:
            mocker: pytest-mock fixture for mocking
            mock_repo_path: Temporary repository directory
        """
        # Arrange
        (mock_repo_path / "mkdocs.yml").write_text("site_name: Test\n")
        (mock_repo_path / "docs").mkdir()

        mocker.patch("mkapidocs.builder.is_mkapidocs_in_target_env", return_value=False)
        mocker.patch("mkapidocs.builder.is_running_in_target_env", return_value=False)

        # Act & Assert
        with pytest.raises(RuntimeError, match="mkapidocs is not installed"):
            serve_docs(mock_repo_path)

    def test_serve_docs_subprocess_failure(
        self, mocker: MockerFixture, mock_repo_path: Path
    ) -> None:
        """Test serve returns non-zero exit code on mkdocs failure.

        Tests: serve_docs() subprocess error handling
        How: Mock subprocess.Popen.wait to return non-zero exit code
        Why: Verify serve failures are propagated to caller

        Args:
            mocker: pytest-mock fixture for mocking
            mock_repo_path: Temporary repository directory
        """
        # Arrange
        (mock_repo_path / "mkdocs.yml").write_text("site_name: Test\n")
        (mock_repo_path / "docs").mkdir()

        mocker.patch("mkapidocs.builder.is_mkapidocs_in_target_env", return_value=True)
        mocker.patch("mkapidocs.builder.is_running_in_target_env", return_value=False)
        mocker.patch(
            "mkapidocs.builder.which",
            return_value=ACTUAL_UV_PATH or "/usr/local/bin/uv",
        )
        mocker.patch("mkapidocs.builder._is_port_in_use", return_value=False)

        mock_process = mocker.MagicMock()
        mock_process.wait.return_value = 1
        mocker.patch("mkapidocs.builder.subprocess.Popen", return_value=mock_process)

        # Act
        exit_code = serve_docs(mock_repo_path)

        # Assert
        assert exit_code == 1

    def test_serve_docs_kills_existing_process_on_port(
        self, mocker: MockerFixture, mock_repo_path: Path
    ) -> None:
        """Test serve kills existing process on port before starting.

        Tests: serve_docs() port conflict handling
        How: Mock _is_port_in_use to return True, verify _kill_process_on_port called
        Why: Ensure graceful handling of port already in use

        Args:
            mocker: pytest-mock fixture for mocking
            mock_repo_path: Temporary repository directory
        """
        # Arrange
        (mock_repo_path / "mkdocs.yml").write_text("site_name: Test\n")
        (mock_repo_path / "docs").mkdir()

        mocker.patch("mkapidocs.builder.is_mkapidocs_in_target_env", return_value=True)
        mocker.patch("mkapidocs.builder.is_running_in_target_env", return_value=False)
        mocker.patch(
            "mkapidocs.builder.which",
            return_value=ACTUAL_UV_PATH or "/usr/local/bin/uv",
        )
        mocker.patch("mkapidocs.builder._is_port_in_use", return_value=True)
        mock_kill = mocker.patch(
            "mkapidocs.builder._kill_process_on_port", return_value=True
        )

        mock_process = mocker.MagicMock()
        mock_process.wait.return_value = 0
        mocker.patch("mkapidocs.builder.subprocess.Popen", return_value=mock_process)

        # Act
        serve_docs(mock_repo_path)

        # Assert
        mock_kill.assert_called_once_with(8000)


class TestIsMkapidocsInTargetEnv:
    """Test suite for is_mkapidocs_in_target_env function.

    Tests use subprocess mocking since the function now uses 'uv pip freeze'.
    """

    def test_returns_false_if_uv_not_installed(
        self, mocker: MockerFixture, mock_repo_path: Path
    ) -> None:
        """Test returns False when uv is not installed.

        Tests: is_mkapidocs_in_target_env handles missing uv
        """
        mocker.patch("mkapidocs.builder.which", return_value=None)
        assert not is_mkapidocs_in_target_env(mock_repo_path)

    def test_returns_false_if_pip_freeze_fails(
        self, mocker: MockerFixture, mock_repo_path: Path
    ) -> None:
        """Test returns False when uv pip freeze fails.

        Tests: is_mkapidocs_in_target_env handles subprocess failure
        """
        mocker.patch("mkapidocs.builder.which", return_value="/usr/local/bin/uv")
        mocker.patch(
            "mkapidocs.builder.subprocess.run",
            side_effect=subprocess.CalledProcessError(1, "uv pip freeze"),
        )
        assert not is_mkapidocs_in_target_env(mock_repo_path)

    def test_returns_true_if_mkapidocs_in_freeze_output(
        self, mocker: MockerFixture, mock_repo_path: Path
    ) -> None:
        """Test returns True when mkapidocs is in pip freeze output.

        Tests: is_mkapidocs_in_target_env detects mkapidocs
        """
        mocker.patch("mkapidocs.builder.which", return_value="/usr/local/bin/uv")
        mock_result = MagicMock()
        mock_result.stdout = "pytest==7.0.0\nmkapidocs==0.1.0\nruff==0.1.0\n"
        mocker.patch("mkapidocs.builder.subprocess.run", return_value=mock_result)
        assert is_mkapidocs_in_target_env(mock_repo_path)

    def test_returns_true_if_mkapidocs_with_extras_in_freeze_output(
        self, mocker: MockerFixture, mock_repo_path: Path
    ) -> None:
        """Test returns True when mkapidocs with extras is in pip freeze output.

        Tests: is_mkapidocs_in_target_env detects mkapidocs with extras
        """
        mocker.patch("mkapidocs.builder.which", return_value="/usr/local/bin/uv")
        mock_result = MagicMock()
        mock_result.stdout = "pytest==7.0.0\nmkapidocs[all]==0.1.0\nruff==0.1.0\n"
        mocker.patch("mkapidocs.builder.subprocess.run", return_value=mock_result)
        assert is_mkapidocs_in_target_env(mock_repo_path)

    def test_returns_false_if_mkapidocs_not_in_freeze_output(
        self, mocker: MockerFixture, mock_repo_path: Path
    ) -> None:
        """Test returns False when mkapidocs is not in pip freeze output.

        Tests: is_mkapidocs_in_target_env correctly identifies absence
        """
        mocker.patch("mkapidocs.builder.which", return_value="/usr/local/bin/uv")
        mock_result = MagicMock()
        mock_result.stdout = "pytest==7.0.0\nruff==0.1.0\nmkdocs==1.5.0\n"
        mocker.patch("mkapidocs.builder.subprocess.run", return_value=mock_result)
        assert not is_mkapidocs_in_target_env(mock_repo_path)
