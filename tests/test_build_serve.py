"""Tests for build and serve functions in mkapidocs.

Tests cover:
- build_docs(): MkDocs build integration with various flags
- serve_docs(): MkDocs serve integration with custom host/port
- get_source_paths_from_pyproject(): Source path detection for PYTHONPATH
- Error handling: missing files, missing commands, subprocess failures
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from mkapidocs.builder import build_docs, is_mkapidocs_in_target_env, serve_docs
from pytest_mock import MockerFixture

# Get actual uvx path for assertions (may be None if not installed)
ACTUAL_UVX_PATH = shutil.which("uvx")


class TestBuildDocs:
    """Test suite for build_docs() function.

    Tests MkDocs build command integration, subprocess handling, and error cases.
    """

    def test_build_docs_success(self, mocker: MockerFixture, mock_repo_path: Path) -> None:
        """Test successful documentation build.

        Tests: build_docs() basic functionality via uvx fallback path
        How: Mock mkdocs.yml existence, subprocess.run, and ensure uvx fallback
        Why: Verify build command construction and execution

        Args:
            mocker: pytest-mock fixture for mocking
            mock_repo_path: Temporary repository directory
        """
        # Arrange
        (mock_repo_path / "mkdocs.yml").write_text("site_name: Test\n")
        docs_dir = mock_repo_path / "docs"
        docs_dir.mkdir()

        # Force uvx fallback path by mocking target env checks
        mocker.patch("mkapidocs.builder.is_mkapidocs_in_target_env", return_value=False)
        mocker.patch("mkapidocs.builder.is_running_in_target_env", return_value=False)
        mocker.patch("mkapidocs.builder.which", return_value=ACTUAL_UVX_PATH or "/usr/local/bin/uvx")
        mock_result = mocker.MagicMock()
        mock_result.returncode = 0
        mock_subprocess = mocker.patch("subprocess.run", return_value=mock_result)

        # Act
        exit_code = build_docs(mock_repo_path)

        # Assert
        assert exit_code == 0
        mock_subprocess.assert_called_once()
        cmd = mock_subprocess.call_args[0][0]
        # Check that uvx was used (path may vary by environment)
        assert "uvx" in cmd[0] or cmd[0].endswith("uvx")
        assert "mkdocs" in cmd
        assert "build" in cmd

    def test_build_docs_with_strict_flag(self, mocker: MockerFixture, mock_repo_path: Path) -> None:
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

        mocker.patch("mkapidocs.builder.is_mkapidocs_in_target_env", return_value=False)
        mocker.patch("mkapidocs.builder.is_running_in_target_env", return_value=False)
        mocker.patch("mkapidocs.builder.which", return_value=ACTUAL_UVX_PATH or "/usr/local/bin/uvx")
        mock_result = mocker.MagicMock()
        mock_result.returncode = 0
        mock_subprocess = mocker.patch("subprocess.run", return_value=mock_result)

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
        How: Mock successful build, verify --site-dir in command args
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

        mocker.patch("mkapidocs.builder.is_mkapidocs_in_target_env", return_value=False)
        mocker.patch("mkapidocs.builder.is_running_in_target_env", return_value=False)
        mocker.patch("mkapidocs.builder.which", return_value=ACTUAL_UVX_PATH or "/usr/local/bin/uvx")
        mock_result = mocker.MagicMock()
        mock_result.returncode = 0
        mock_subprocess = mocker.patch("subprocess.run", return_value=mock_result)

        # Act
        exit_code = build_docs(mock_repo_path, output_dir=custom_output)

        # Assert
        assert exit_code == 0
        cmd = mock_subprocess.call_args[0][0]
        assert "--site-dir" in cmd
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

    def test_build_docs_missing_uvx_command(self, mocker: MockerFixture, mock_repo_path: Path) -> None:
        """Test build fails when uvx command not found.

        Tests: build_docs() error handling
        How: Mock which() to return None, force uvx fallback path
        Why: Verify helpful error when uv not installed

        Args:
            mocker: pytest-mock fixture for mocking
            mock_repo_path: Temporary repository directory
        """
        # Arrange
        (mock_repo_path / "mkdocs.yml").write_text("site_name: Test\n")
        (mock_repo_path / "docs").mkdir()

        # Force uvx fallback path, then uvx returns None
        mocker.patch("mkapidocs.builder.is_mkapidocs_in_target_env", return_value=False)
        mocker.patch("mkapidocs.builder.is_running_in_target_env", return_value=False)
        mocker.patch("mkapidocs.builder.which", return_value=None)

        # Act & Assert
        with pytest.raises(FileNotFoundError, match="uvx command not found"):
            build_docs(mock_repo_path)

    def test_build_docs_subprocess_failure(self, mocker: MockerFixture, mock_repo_path: Path) -> None:
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

        mocker.patch("mkapidocs.builder.is_mkapidocs_in_target_env", return_value=False)
        mocker.patch("mkapidocs.builder.is_running_in_target_env", return_value=False)
        mocker.patch("mkapidocs.builder.which", return_value=ACTUAL_UVX_PATH or "/usr/local/bin/uvx")
        mock_result = mocker.MagicMock()
        mock_result.returncode = 1
        mocker.patch("subprocess.run", return_value=mock_result)

        # Act
        exit_code = build_docs(mock_repo_path)

        # Assert
        assert exit_code == 1

    def test_build_docs_includes_all_required_plugins(self, mocker: MockerFixture, mock_repo_path: Path) -> None:
        """Test build command includes all mkdocs plugins via --with flags.

        Tests: build_docs() plugin installation
        How: Mock subprocess, verify --with flags in command
        Why: All plugins must be available for mkdocs build

        Args:
            mocker: pytest-mock fixture for mocking
            mock_repo_path: Temporary repository directory
        """
        # Arrange
        (mock_repo_path / "mkdocs.yml").write_text("site_name: Test\n")
        (mock_repo_path / "docs").mkdir()

        mocker.patch("mkapidocs.builder.is_mkapidocs_in_target_env", return_value=False)
        mocker.patch("mkapidocs.builder.is_running_in_target_env", return_value=False)
        mocker.patch("mkapidocs.builder.which", return_value=ACTUAL_UVX_PATH or "/usr/local/bin/uvx")
        mock_result = mocker.MagicMock()
        mock_result.returncode = 0
        mock_subprocess = mocker.patch("subprocess.run", return_value=mock_result)

        # Act
        build_docs(mock_repo_path)

        # Assert
        cmd = mock_subprocess.call_args[0][0]
        cmd_str = " ".join(cmd)
        assert "--with" in cmd_str
        assert "mkdocs-material" in cmd_str
        assert "mkdocstrings" in cmd_str
        assert "mkdocs-typer2" in cmd_str


class TestServeDocs:
    """Test suite for serve_docs() function.

    Tests MkDocs serve command integration, subprocess handling, and error cases.
    """

    def test_serve_docs_success(self, mocker: MockerFixture, mock_repo_path: Path) -> None:
        """Test successful documentation server start.

        Tests: serve_docs() basic functionality via uvx fallback path
        How: Mock mkdocs.yml existence, subprocess.run, and ensure uvx fallback
        Why: Verify serve command construction and execution

        Args:
            mocker: pytest-mock fixture for mocking
            mock_repo_path: Temporary repository directory
        """
        # Arrange
        (mock_repo_path / "mkdocs.yml").write_text("site_name: Test\n")
        docs_dir = mock_repo_path / "docs"
        docs_dir.mkdir()

        # Force uvx fallback path
        mocker.patch("mkapidocs.builder.is_mkapidocs_in_target_env", return_value=False)
        mocker.patch("mkapidocs.builder.is_running_in_target_env", return_value=False)
        mocker.patch("mkapidocs.builder.which", return_value=ACTUAL_UVX_PATH or "/usr/local/bin/uvx")
        mock_result = mocker.MagicMock()
        mock_result.returncode = 0
        mock_subprocess = mocker.patch("subprocess.run", return_value=mock_result)

        # Act
        exit_code = serve_docs(mock_repo_path)

        # Assert
        assert exit_code == 0
        mock_subprocess.assert_called_once()
        cmd = mock_subprocess.call_args[0][0]
        # Check that uvx was used (path may vary by environment)
        assert "uvx" in cmd[0] or cmd[0].endswith("uvx")
        assert "mkdocs" in cmd
        assert "serve" in cmd

    def test_serve_docs_with_custom_host_and_port(self, mocker: MockerFixture, mock_repo_path: Path) -> None:
        """Test serve with custom host and port.

        Tests: serve_docs(host='0.0.0.0', port=9000)
        How: Mock subprocess, verify --dev-addr in command args
        Why: Ensure custom server address is properly passed to mkdocs

        Args:
            mocker: pytest-mock fixture for mocking
            mock_repo_path: Temporary repository directory
        """
        # Arrange
        (mock_repo_path / "mkdocs.yml").write_text("site_name: Test\n")
        (mock_repo_path / "docs").mkdir()

        mocker.patch("mkapidocs.builder.is_mkapidocs_in_target_env", return_value=False)
        mocker.patch("mkapidocs.builder.is_running_in_target_env", return_value=False)
        mocker.patch("mkapidocs.builder.which", return_value=ACTUAL_UVX_PATH or "/usr/local/bin/uvx")
        mock_result = mocker.MagicMock()
        mock_result.returncode = 0
        mock_subprocess = mocker.patch("subprocess.run", return_value=mock_result)

        # Act
        exit_code = serve_docs(mock_repo_path, host="0.0.0.0", port=9000)  # noqa: S104

        # Assert
        assert exit_code == 0
        cmd = mock_subprocess.call_args[0][0]
        assert "--dev-addr" in cmd
        assert "0.0.0.0:9000" in cmd

    def test_serve_docs_default_address(self, mocker: MockerFixture, mock_repo_path: Path) -> None:
        """Test serve uses default localhost:8000 when not specified.

        Tests: serve_docs() default parameters
        How: Mock subprocess, verify default --dev-addr
        Why: Ensure sensible defaults for local development

        Args:
            mocker: pytest-mock fixture for mocking
            mock_repo_path: Temporary repository directory
        """
        # Arrange
        (mock_repo_path / "mkdocs.yml").write_text("site_name: Test\n")
        (mock_repo_path / "docs").mkdir()

        mocker.patch("mkapidocs.builder.is_mkapidocs_in_target_env", return_value=False)
        mocker.patch("mkapidocs.builder.is_running_in_target_env", return_value=False)
        mocker.patch("mkapidocs.builder.which", return_value=ACTUAL_UVX_PATH or "/usr/local/bin/uvx")
        mock_result = mocker.MagicMock()
        mock_result.returncode = 0
        mock_subprocess = mocker.patch("subprocess.run", return_value=mock_result)

        # Act
        serve_docs(mock_repo_path)

        # Assert
        cmd = mock_subprocess.call_args[0][0]
        assert "--dev-addr" in cmd
        assert "127.0.0.1:8000" in cmd

    def test_serve_docs_keyboard_interrupt_graceful_exit(self, mocker: MockerFixture, mock_repo_path: Path) -> None:
        """Test serve handles Ctrl+C (KeyboardInterrupt) gracefully.

        Tests: serve_docs() KeyboardInterrupt handling
        How: Mock subprocess.run to raise KeyboardInterrupt
        Why: Verify clean shutdown on user interrupt

        Args:
            mocker: pytest-mock fixture for mocking
            mock_repo_path: Temporary repository directory
        """
        # Arrange
        (mock_repo_path / "mkdocs.yml").write_text("site_name: Test\n")
        (mock_repo_path / "docs").mkdir()

        mocker.patch("mkapidocs.builder.is_mkapidocs_in_target_env", return_value=False)
        mocker.patch("mkapidocs.builder.is_running_in_target_env", return_value=False)
        mocker.patch("mkapidocs.builder.which", return_value=ACTUAL_UVX_PATH or "/usr/local/bin/uvx")
        mocker.patch("subprocess.run", side_effect=KeyboardInterrupt)

        # Act
        exit_code = serve_docs(mock_repo_path)

        # Assert
        assert exit_code == 0

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

    def test_serve_docs_missing_uvx_command(self, mocker: MockerFixture, mock_repo_path: Path) -> None:
        """Test serve fails when uvx command not found.

        Tests: serve_docs() error handling
        How: Mock which() to return None, force uvx fallback path
        Why: Verify helpful error when uv not installed

        Args:
            mocker: pytest-mock fixture for mocking
            mock_repo_path: Temporary repository directory
        """
        # Arrange
        (mock_repo_path / "mkdocs.yml").write_text("site_name: Test\n")
        (mock_repo_path / "docs").mkdir()

        # Force uvx fallback path, then uvx returns None
        mocker.patch("mkapidocs.builder.is_mkapidocs_in_target_env", return_value=False)
        mocker.patch("mkapidocs.builder.is_running_in_target_env", return_value=False)
        mocker.patch("mkapidocs.builder.which", return_value=None)

        # Act & Assert
        with pytest.raises(FileNotFoundError, match="uvx command not found"):
            serve_docs(mock_repo_path)

    def test_serve_docs_subprocess_failure(self, mocker: MockerFixture, mock_repo_path: Path) -> None:
        """Test serve returns non-zero exit code on mkdocs failure.

        Tests: serve_docs() subprocess error handling
        How: Mock subprocess.run to return non-zero exit code
        Why: Verify serve failures are propagated to caller

        Args:
            mocker: pytest-mock fixture for mocking
            mock_repo_path: Temporary repository directory
        """
        # Arrange
        (mock_repo_path / "mkdocs.yml").write_text("site_name: Test\n")
        (mock_repo_path / "docs").mkdir()

        mocker.patch("mkapidocs.builder.is_mkapidocs_in_target_env", return_value=False)
        mocker.patch("mkapidocs.builder.is_running_in_target_env", return_value=False)
        mocker.patch("mkapidocs.builder.which", return_value=ACTUAL_UVX_PATH or "/usr/local/bin/uvx")
        mock_result = mocker.MagicMock()
        mock_result.returncode = 1
        mocker.patch("subprocess.run", return_value=mock_result)

        # Act
        exit_code = serve_docs(mock_repo_path)

        # Assert
        assert exit_code == 1


class TestIsMkapidocsInTargetEnv:
    """Test suite for is_mkapidocs_in_target_env function."""

    def test_returns_false_if_no_pyproject(self, mock_repo_path: Path) -> None:
        """Test returns False when pyproject.toml is missing.

        Tests: is_mkapidocs_in_target_env handles missing file
        """
        assert not is_mkapidocs_in_target_env(mock_repo_path)

    def test_returns_false_if_no_dev_dependencies(self, mock_repo_path: Path) -> None:
        """Test returns False when no dev dependencies defined.

        Tests: is_mkapidocs_in_target_env handles missing config
        """
        (mock_repo_path / "pyproject.toml").write_text("[project]\nname='test'")
        assert not is_mkapidocs_in_target_env(mock_repo_path)

    def test_returns_true_if_mkapidocs_in_dev_dependencies(self, mock_repo_path: Path) -> None:
        """Test returns True when mkapidocs is in dev dependencies.

        Tests: is_mkapidocs_in_target_env detects dependency
        """
        content = """
[project]
name = "test"

[dependency-groups]
dev = ["mkapidocs", "pytest"]
"""
        (mock_repo_path / "pyproject.toml").write_text(content)
        assert is_mkapidocs_in_target_env(mock_repo_path)

    def test_returns_true_if_mkapidocs_with_version_in_dev_dependencies(self, mock_repo_path: Path) -> None:
        """Test returns True when mkapidocs with version constraint is in dev dependencies.

        Tests: is_mkapidocs_in_target_env detects dependency with version
        """
        content = """
[project]
name = "test"

[dependency-groups]
dev = ["mkapidocs>=0.1.0", "pytest"]
"""
        (mock_repo_path / "pyproject.toml").write_text(content)
        assert is_mkapidocs_in_target_env(mock_repo_path)

    def test_returns_false_if_mkapidocs_not_in_dev_dependencies(self, mock_repo_path: Path) -> None:
        """Test returns False when mkapidocs is not in dev dependencies.

        Tests: is_mkapidocs_in_target_env correctly identifies absence
        """
        content = """
[project]
name = "test"

[dependency-groups]
dev = ["pytest", "ruff"]
"""
        (mock_repo_path / "pyproject.toml").write_text(content)
        assert not is_mkapidocs_in_target_env(mock_repo_path)
