"""Tests for build and serve functions in mkapidocs.

Tests cover:
- build_docs(): MkDocs build integration with various flags
- serve_docs(): MkDocs serve integration with custom host/port
- get_source_paths_from_pyproject(): Source path detection for PYTHONPATH
- Error handling: missing files, missing commands, subprocess failures
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from pytest_mock import MockerFixture


# Access mkapidocs module functions (deferred lookup at test runtime)
def build_docs(*args, **kwargs):  # type: ignore[no-untyped-def]
    """Wrapper for mkapidocs.build_docs with deferred module lookup."""
    return sys.modules["mkapidocs"].build_docs(*args, **kwargs)


def serve_docs(*args, **kwargs):  # type: ignore[no-untyped-def]
    """Wrapper for mkapidocs.serve_docs with deferred module lookup."""
    return sys.modules["mkapidocs"].serve_docs(*args, **kwargs)


def get_source_paths_from_pyproject(*args, **kwargs):  # type: ignore[no-untyped-def]
    """Wrapper for mkapidocs.get_source_paths_from_pyproject with deferred module lookup."""
    return sys.modules["mkapidocs"].get_source_paths_from_pyproject(*args, **kwargs)


class TestBuildDocs:
    """Test suite for build_docs() function.

    Tests MkDocs build command integration, subprocess handling, and error cases.
    """

    def test_build_docs_success(self, mocker: MockerFixture, mock_repo_path: Path) -> None:
        """Test successful documentation build.

        Tests: build_docs() basic functionality
        How: Mock mkdocs.yml existence, subprocess.run, and which()
        Why: Verify build command construction and execution

        Args:
            mocker: pytest-mock fixture for mocking
            mock_repo_path: Temporary repository directory
        """
        # Arrange
        (mock_repo_path / "mkdocs.yml").write_text("site_name: Test\n")
        docs_dir = mock_repo_path / "docs"
        docs_dir.mkdir()

        mocker.patch("mkapidocs.which", return_value="/usr/local/bin/uvx")
        mock_result = mocker.MagicMock()
        mock_result.returncode = 0
        mock_subprocess = mocker.patch("subprocess.run", return_value=mock_result)

        # Act
        exit_code = build_docs(mock_repo_path)

        # Assert
        assert exit_code == 0
        mock_subprocess.assert_called_once()
        cmd = mock_subprocess.call_args[0][0]
        assert cmd[0] == "/usr/local/bin/uvx"
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

        mocker.patch("mkapidocs.which", return_value="/usr/local/bin/uvx")
        mock_result = mocker.MagicMock()
        mock_result.returncode = 0
        mock_subprocess = mocker.patch("subprocess.run", return_value=mock_result)

        # Act
        exit_code = build_docs(mock_repo_path, strict=True)

        # Assert
        assert exit_code == 0
        cmd = mock_subprocess.call_args[0][0]
        assert "--strict" in cmd

    def test_build_docs_with_custom_output_dir(self, mocker: MockerFixture, mock_repo_path: Path, tmp_path: Path) -> None:
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

        mocker.patch("mkapidocs.which", return_value="/usr/local/bin/uvx")
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
        How: Mock which() to return None
        Why: Verify helpful error when uv not installed

        Args:
            mocker: pytest-mock fixture for mocking
            mock_repo_path: Temporary repository directory
        """
        # Arrange
        (mock_repo_path / "mkdocs.yml").write_text("site_name: Test\n")
        (mock_repo_path / "docs").mkdir()

        mocker.patch("mkapidocs.which", return_value=None)

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

        mocker.patch("mkapidocs.which", return_value="/usr/local/bin/uvx")
        mock_result = mocker.MagicMock()
        mock_result.returncode = 1
        mocker.patch("subprocess.run", return_value=mock_result)

        # Act
        exit_code = build_docs(mock_repo_path)

        # Assert
        assert exit_code == 1

    def test_build_docs_creates_gen_ref_pages_script(self, mocker: MockerFixture, mock_repo_path: Path) -> None:
        """Test build creates gen_ref_pages.py in docs directory.

        Tests: build_docs() generates required scripts
        How: Mock subprocess, verify gen_ref_pages.py written
        Why: Script must exist before mkdocs build runs

        Args:
            mocker: pytest-mock fixture for mocking
            mock_repo_path: Temporary repository directory
        """
        # Arrange
        (mock_repo_path / "mkdocs.yml").write_text("site_name: Test\n")
        docs_dir = mock_repo_path / "docs"
        docs_dir.mkdir()

        mocker.patch("mkapidocs.which", return_value="/usr/local/bin/uvx")
        mock_result = mocker.MagicMock()
        mock_result.returncode = 0
        mocker.patch("subprocess.run", return_value=mock_result)

        # Act
        build_docs(mock_repo_path)

        # Assert
        gen_ref_script = docs_dir / "gen_ref_pages.py"
        assert gen_ref_script.exists()
        content = gen_ref_script.read_text()
        assert "mkdocs-gen-files" in content or "gen_files" in content

    def test_build_docs_sets_pythonpath_from_source_paths(
        self, mocker: MockerFixture, mock_repo_path: Path
    ) -> None:
        """Test build sets PYTHONPATH environment variable from pyproject.toml.

        Tests: build_docs() PYTHONPATH configuration
        How: Mock get_source_paths_from_pyproject, verify env passed to subprocess
        Why: mkdocstrings needs PYTHONPATH to import project modules

        Args:
            mocker: pytest-mock fixture for mocking
            mock_repo_path: Temporary repository directory
        """
        # Arrange
        (mock_repo_path / "mkdocs.yml").write_text("site_name: Test\n")
        (mock_repo_path / "docs").mkdir()

        src_path = mock_repo_path / "src"
        mocker.patch("mkapidocs.get_source_paths_from_pyproject", return_value=[src_path])
        mocker.patch("mkapidocs.which", return_value="/usr/local/bin/uvx")

        mock_result = mocker.MagicMock()
        mock_result.returncode = 0
        mock_subprocess = mocker.patch("subprocess.run", return_value=mock_result)

        # Act
        build_docs(mock_repo_path)

        # Assert
        call_kwargs = mock_subprocess.call_args[1]
        env = call_kwargs["env"]
        assert "PYTHONPATH" in env
        assert str(src_path) in env["PYTHONPATH"]

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

        mocker.patch("mkapidocs.which", return_value="/usr/local/bin/uvx")
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

        Tests: serve_docs() basic functionality
        How: Mock mkdocs.yml existence, subprocess.run, and which()
        Why: Verify serve command construction and execution

        Args:
            mocker: pytest-mock fixture for mocking
            mock_repo_path: Temporary repository directory
        """
        # Arrange
        (mock_repo_path / "mkdocs.yml").write_text("site_name: Test\n")
        docs_dir = mock_repo_path / "docs"
        docs_dir.mkdir()

        mocker.patch("mkapidocs.which", return_value="/usr/local/bin/uvx")
        mock_result = mocker.MagicMock()
        mock_result.returncode = 0
        mock_subprocess = mocker.patch("subprocess.run", return_value=mock_result)

        # Act
        exit_code = serve_docs(mock_repo_path)

        # Assert
        assert exit_code == 0
        mock_subprocess.assert_called_once()
        cmd = mock_subprocess.call_args[0][0]
        assert cmd[0] == "/usr/local/bin/uvx"
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

        mocker.patch("mkapidocs.which", return_value="/usr/local/bin/uvx")
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

        mocker.patch("mkapidocs.which", return_value="/usr/local/bin/uvx")
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

        mocker.patch("mkapidocs.which", return_value="/usr/local/bin/uvx")
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
        How: Mock which() to return None
        Why: Verify helpful error when uv not installed

        Args:
            mocker: pytest-mock fixture for mocking
            mock_repo_path: Temporary repository directory
        """
        # Arrange
        (mock_repo_path / "mkdocs.yml").write_text("site_name: Test\n")
        (mock_repo_path / "docs").mkdir()

        mocker.patch("mkapidocs.which", return_value=None)

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

        mocker.patch("mkapidocs.which", return_value="/usr/local/bin/uvx")
        mock_result = mocker.MagicMock()
        mock_result.returncode = 1
        mocker.patch("subprocess.run", return_value=mock_result)

        # Act
        exit_code = serve_docs(mock_repo_path)

        # Assert
        assert exit_code == 1

    def test_serve_docs_creates_gen_ref_pages_script(self, mocker: MockerFixture, mock_repo_path: Path) -> None:
        """Test serve creates gen_ref_pages.py in docs directory.

        Tests: serve_docs() generates required scripts
        How: Mock subprocess, verify gen_ref_pages.py written
        Why: Script must exist before mkdocs serve runs

        Args:
            mocker: pytest-mock fixture for mocking
            mock_repo_path: Temporary repository directory
        """
        # Arrange
        (mock_repo_path / "mkdocs.yml").write_text("site_name: Test\n")
        docs_dir = mock_repo_path / "docs"
        docs_dir.mkdir()

        mocker.patch("mkapidocs.which", return_value="/usr/local/bin/uvx")
        mock_result = mocker.MagicMock()
        mock_result.returncode = 0
        mocker.patch("subprocess.run", return_value=mock_result)

        # Act
        serve_docs(mock_repo_path)

        # Assert
        gen_ref_script = docs_dir / "gen_ref_pages.py"
        assert gen_ref_script.exists()

    def test_serve_docs_sets_pythonpath_from_source_paths(
        self, mocker: MockerFixture, mock_repo_path: Path
    ) -> None:
        """Test serve sets PYTHONPATH environment variable from pyproject.toml.

        Tests: serve_docs() PYTHONPATH configuration
        How: Mock get_source_paths_from_pyproject, verify env passed to subprocess
        Why: mkdocstrings needs PYTHONPATH to import project modules during live reload

        Args:
            mocker: pytest-mock fixture for mocking
            mock_repo_path: Temporary repository directory
        """
        # Arrange
        (mock_repo_path / "mkdocs.yml").write_text("site_name: Test\n")
        (mock_repo_path / "docs").mkdir()

        src_path = mock_repo_path / "src"
        mocker.patch("mkapidocs.get_source_paths_from_pyproject", return_value=[src_path])
        mocker.patch("mkapidocs.which", return_value="/usr/local/bin/uvx")

        mock_result = mocker.MagicMock()
        mock_result.returncode = 0
        mock_subprocess = mocker.patch("subprocess.run", return_value=mock_result)

        # Act
        serve_docs(mock_repo_path)

        # Assert
        call_kwargs = mock_subprocess.call_args[1]
        env = call_kwargs["env"]
        assert "PYTHONPATH" in env
        assert str(src_path) in env["PYTHONPATH"]


class TestGetSourcePathsFromPyproject:
    """Test suite for get_source_paths_from_pyproject() function.

    Tests source path detection from various pyproject.toml configurations.
    """

    def test_returns_empty_list_when_no_pyproject_toml(self, mock_repo_path: Path) -> None:
        """Test returns empty list when pyproject.toml missing.

        Tests: get_source_paths_from_pyproject()
        How: Call function with repo path without pyproject.toml
        Why: Verify graceful handling of missing configuration

        Args:
            mock_repo_path: Temporary repository directory
        """
        # Act
        paths = get_source_paths_from_pyproject(mock_repo_path)

        # Assert
        assert paths == []

    def test_returns_empty_list_when_pyproject_toml_invalid(self, mock_repo_path: Path) -> None:
        """Test returns empty list when pyproject.toml has invalid TOML.

        Tests: get_source_paths_from_pyproject() error handling
        How: Create malformed TOML file
        Why: Verify parse errors don't crash function

        Args:
            mock_repo_path: Temporary repository directory
        """
        # Arrange
        pyproject_path = mock_repo_path / "pyproject.toml"
        pyproject_path.write_text("[project\nname = invalid")  # Missing closing bracket

        # Act
        paths = get_source_paths_from_pyproject(mock_repo_path)

        # Assert
        assert paths == []

    def test_detects_hatch_sources_mapping(self, mock_repo_path: Path) -> None:
        """Test detects source paths from Hatch sources configuration.

        Tests: get_source_paths_from_pyproject() Hatch sources support
        How: Create pyproject.toml with [tool.hatch.build.targets.wheel] sources
        Why: Verify Hatch sources mapping is parsed correctly

        Args:
            mock_repo_path: Temporary repository directory
        """
        # Arrange
        pyproject_content = """[project]
name = "test-project"

[tool.hatch.build.targets.wheel]
sources = {"packages/mypackage" = "mypackage"}
"""
        (mock_repo_path / "pyproject.toml").write_text(pyproject_content)

        # Act
        paths = get_source_paths_from_pyproject(mock_repo_path)

        # Assert
        assert len(paths) == 1
        assert paths[0] == mock_repo_path / "packages"

    def test_detects_hatch_packages_list(self, mock_repo_path: Path) -> None:
        """Test detects source paths from Hatch packages list.

        Tests: get_source_paths_from_pyproject() Hatch packages support
        How: Create pyproject.toml with [tool.hatch.build.targets.wheel] packages
        Why: Verify Hatch packages list is parsed correctly

        Args:
            mock_repo_path: Temporary repository directory
        """
        # Arrange
        pyproject_content = """[project]
name = "test-project"

[tool.hatch.build.targets.wheel]
packages = ["src/mypackage"]
"""
        (mock_repo_path / "pyproject.toml").write_text(pyproject_content)

        # Act
        paths = get_source_paths_from_pyproject(mock_repo_path)

        # Assert
        assert len(paths) == 1
        assert paths[0] == mock_repo_path / "src"

    def test_detects_setuptools_where_configuration(self, mock_repo_path: Path) -> None:
        """Test detects source paths from setuptools where configuration.

        Tests: get_source_paths_from_pyproject() setuptools support
        How: Create pyproject.toml with [tool.setuptools.packages.find] where
        Why: Verify setuptools configuration is parsed correctly

        Args:
            mock_repo_path: Temporary repository directory
        """
        # Arrange
        pyproject_content = """[project]
name = "test-project"

[tool.setuptools.packages.find]
where = ["src"]
"""
        (mock_repo_path / "pyproject.toml").write_text(pyproject_content)

        # Act
        paths = get_source_paths_from_pyproject(mock_repo_path)

        # Assert
        assert len(paths) == 1
        assert paths[0] == mock_repo_path / "src"

    def test_detects_setuptools_where_string(self, mock_repo_path: Path) -> None:
        """Test handles setuptools where as string instead of list.

        Tests: get_source_paths_from_pyproject() flexible input handling
        How: Create pyproject.toml with where as string
        Why: Verify function handles both string and list formats

        Args:
            mock_repo_path: Temporary repository directory
        """
        # Arrange
        pyproject_content = """[project]
name = "test-project"

[tool.setuptools.packages.find]
where = "lib"
"""
        (mock_repo_path / "pyproject.toml").write_text(pyproject_content)

        # Act
        paths = get_source_paths_from_pyproject(mock_repo_path)

        # Assert
        assert len(paths) == 1
        assert paths[0] == mock_repo_path / "lib"

    def test_returns_empty_list_when_no_configuration_found(self, mock_repo_path: Path) -> None:
        """Test returns empty list when no build configuration present.

        Tests: get_source_paths_from_pyproject() fallback behavior
        How: Create minimal pyproject.toml without build tool config
        Why: Verify function doesn't crash with minimal configuration

        Args:
            mock_repo_path: Temporary repository directory
        """
        # Arrange
        pyproject_content = """[project]
name = "test-project"
version = "0.1.0"
"""
        (mock_repo_path / "pyproject.toml").write_text(pyproject_content)

        # Act
        paths = get_source_paths_from_pyproject(mock_repo_path)

        # Assert
        assert paths == []

    def test_handles_single_file_packages_at_root(self, mock_repo_path: Path) -> None:
        """Test handles packages at repository root correctly.

        Tests: get_source_paths_from_pyproject() root package detection
        How: Create pyproject.toml with package at root (no parent directory)
        Why: Verify single-file packages at root return repo path

        Args:
            mock_repo_path: Temporary repository directory
        """
        # Arrange
        pyproject_content = """[project]
name = "test-project"

[tool.hatch.build.targets.wheel]
packages = ["mypackage"]
"""
        (mock_repo_path / "pyproject.toml").write_text(pyproject_content)

        # Act
        paths = get_source_paths_from_pyproject(mock_repo_path)

        # Assert
        assert len(paths) == 1
        assert paths[0] == mock_repo_path

    def test_prioritizes_hatch_sources_over_packages(self, mock_repo_path: Path) -> None:
        """Test prioritizes sources mapping over packages list when both present.

        Tests: get_source_paths_from_pyproject() priority logic
        How: Create pyproject.toml with both sources and packages
        Why: Verify sources takes precedence per expected behavior

        Args:
            mock_repo_path: Temporary repository directory
        """
        # Arrange
        pyproject_content = """[project]
name = "test-project"

[tool.hatch.build.targets.wheel]
sources = {"lib/mypackage" = "mypackage"}
packages = ["src/otherpackage"]
"""
        (mock_repo_path / "pyproject.toml").write_text(pyproject_content)

        # Act
        paths = get_source_paths_from_pyproject(mock_repo_path)

        # Assert
        assert len(paths) == 1
        assert paths[0] == mock_repo_path / "lib"

    def test_prioritizes_hatch_over_setuptools(self, mock_repo_path: Path) -> None:
        """Test prioritizes Hatch configuration over setuptools when both present.

        Tests: get_source_paths_from_pyproject() priority logic
        How: Create pyproject.toml with both Hatch and setuptools config
        Why: Verify Hatch takes precedence

        Args:
            mock_repo_path: Temporary repository directory
        """
        # Arrange
        pyproject_content = """[project]
name = "test-project"

[tool.hatch.build.targets.wheel]
packages = ["hatch_src/mypackage"]

[tool.setuptools.packages.find]
where = ["setuptools_src"]
"""
        (mock_repo_path / "pyproject.toml").write_text(pyproject_content)

        # Act
        paths = get_source_paths_from_pyproject(mock_repo_path)

        # Assert
        assert len(paths) == 1
        assert paths[0] == mock_repo_path / "hatch_src"
