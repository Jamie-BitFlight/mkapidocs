"""Tests for validation system in mkapidocs.

Tests cover:
- DoxygenInstaller: download, installation, verification, platform detection
- SystemValidator: git, uv/uvx, doxygen checks
- ProjectValidator: path, git repo, pyproject.toml, feature detection checks
- ValidationResult dataclass functionality
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

import httpx

from mkapidocs.validators import (
    DoxygenInstaller,
    ProjectValidator,
    SystemValidator,
    ValidationResult,
)

if TYPE_CHECKING:
    from pytest_mock import MockerFixture

    from mkapidocs.models import TomlTable


class TestDoxygenInstaller:
    """Test suite for DoxygenInstaller class.

    Tests automatic Doxygen download, installation, and platform detection.
    """

    def test_is_installed_when_doxygen_found(self, mocker: MockerFixture) -> None:
        """Test is_installed returns True when doxygen is in PATH.

        Tests: DoxygenInstaller.is_installed()
        How: Mock which() to return path, mock subprocess to return version
        Why: Verify doxygen detection works correctly when installed

        Args:
            mocker: pytest-mock fixture for mocking
        """
        # Arrange
        _ = mocker.patch("mkapidocs.validators.which", return_value="/usr/bin/doxygen")
        mock_result = mocker.MagicMock()
        mock_result.stdout = "1.9.8"
        _ = mocker.patch("subprocess.run", return_value=mock_result)

        # Act
        is_installed, version = DoxygenInstaller.is_installed()

        # Assert
        assert is_installed is True
        assert version == "1.9.8"

    def test_is_installed_when_doxygen_not_found(self, mocker: MockerFixture) -> None:
        """Test is_installed returns False when doxygen not in PATH.

        Tests: DoxygenInstaller.is_installed()
        How: Mock which() to return None
        Why: Verify detection handles missing doxygen gracefully

        Args:
            mocker: pytest-mock fixture for mocking
        """
        # Arrange
        _ = mocker.patch("mkapidocs.validators.which", return_value=None)

        # Act
        is_installed, version = DoxygenInstaller.is_installed()

        # Assert
        assert is_installed is False
        assert version is None

    def test_is_installed_when_version_check_fails(self, mocker: MockerFixture) -> None:
        """Test is_installed handles subprocess errors gracefully.

        Tests: DoxygenInstaller.is_installed() error handling
        How: Mock which() to succeed, subprocess.run to raise CalledProcessError
        Why: Verify error handling when doxygen binary exists but fails

        Args:
            mocker: pytest-mock fixture for mocking
        """
        # Arrange
        _ = mocker.patch("mkapidocs.validators.which", return_value="/usr/bin/doxygen")
        _ = mocker.patch(
            "subprocess.run", side_effect=subprocess.CalledProcessError(1, "doxygen")
        )

        # Act
        is_installed, version = DoxygenInstaller.is_installed()

        # Assert
        assert is_installed is False
        assert version is None

    def test_get_platform_asset_name_linux_x86_64(self, mocker: MockerFixture) -> None:
        """Test platform detection returns correct asset name for Linux x86_64.

        Tests: DoxygenInstaller.get_platform_asset_name()
        How: Mock platform.system() and platform.machine() to return Linux/x86_64
        Why: Verify correct asset pattern selection for supported platform

        Args:
            mocker: pytest-mock fixture for mocking
        """
        # Arrange
        _ = mocker.patch("mkapidocs.validators.platform.system", return_value="Linux")
        _ = mocker.patch("mkapidocs.validators.platform.machine", return_value="x86_64")

        # Act
        asset_name = DoxygenInstaller.get_platform_asset_name()

        # Assert
        assert asset_name == "doxygen-*.linux.bin.tar.gz"

    def test_get_platform_asset_name_linux_amd64(self, mocker: MockerFixture) -> None:
        """Test platform detection handles amd64 architecture variant.

        Tests: DoxygenInstaller.get_platform_asset_name()
        How: Mock platform.machine() to return amd64
        Why: Verify alternative architecture name is recognized

        Args:
            mocker: pytest-mock fixture for mocking
        """
        # Arrange
        _ = mocker.patch("mkapidocs.validators.platform.system", return_value="Linux")
        _ = mocker.patch("mkapidocs.validators.platform.machine", return_value="amd64")

        # Act
        asset_name = DoxygenInstaller.get_platform_asset_name()

        # Assert
        assert asset_name == "doxygen-*.linux.bin.tar.gz"

    def test_get_platform_asset_name_windows_x86_64(
        self, mocker: MockerFixture
    ) -> None:
        """Test platform detection returns Windows installer for Windows x86_64.

        Tests: DoxygenInstaller.get_platform_asset_name()
        How: Mock platform to return Windows/x86_64
        Why: Verify Windows platform support

        Args:
            mocker: pytest-mock fixture for mocking
        """
        # Arrange
        _ = mocker.patch("mkapidocs.validators.platform.system", return_value="Windows")
        _ = mocker.patch("mkapidocs.validators.platform.machine", return_value="x86_64")

        # Act
        asset_name = DoxygenInstaller.get_platform_asset_name()

        # Assert
        assert asset_name == "doxygen-*-setup.exe"

    def test_get_platform_asset_name_macos_not_supported(
        self, mocker: MockerFixture
    ) -> None:
        """Test platform detection returns None for macOS.

        Tests: DoxygenInstaller.get_platform_asset_name()
        How: Mock platform.system() to return Darwin
        Why: macOS requires Homebrew installation, auto-install not supported

        Args:
            mocker: pytest-mock fixture for mocking
        """
        # Arrange
        _ = mocker.patch("mkapidocs.validators.platform.system", return_value="Darwin")

        # Act
        asset_name = DoxygenInstaller.get_platform_asset_name()

        # Assert
        assert asset_name is None

    def test_get_platform_asset_name_linux_arm_not_supported(
        self, mocker: MockerFixture
    ) -> None:
        """Test platform detection returns None for unsupported Linux architecture.

        Tests: DoxygenInstaller.get_platform_asset_name()
        How: Mock platform to return Linux/aarch64
        Why: Verify unsupported architectures are handled

        Args:
            mocker: pytest-mock fixture for mocking
        """
        # Arrange
        _ = mocker.patch("mkapidocs.validators.platform.system", return_value="Linux")
        _ = mocker.patch(
            "mkapidocs.validators.platform.machine", return_value="aarch64"
        )

        # Act
        asset_name = DoxygenInstaller.get_platform_asset_name()

        # Assert
        assert asset_name is None

    def test_get_platform_asset_name_windows_arm_not_supported(
        self, mocker: MockerFixture
    ) -> None:
        """Test platform detection returns None for Windows ARM.

        Tests: DoxygenInstaller.get_platform_asset_name()
        How: Mock platform to return Windows/aarch64
        Why: Verify unsupported Windows architectures are handled

        Args:
            mocker: pytest-mock fixture for mocking
        """
        # Arrange
        _ = mocker.patch("mkapidocs.validators.platform.system", return_value="Windows")
        _ = mocker.patch(
            "mkapidocs.validators.platform.machine", return_value="aarch64"
        )

        # Act
        asset_name = DoxygenInstaller.get_platform_asset_name()

        # Assert
        assert asset_name is None

    def test_get_platform_asset_name_unknown_os_not_supported(
        self, mocker: MockerFixture
    ) -> None:
        """Test platform detection returns None for unknown operating systems.

        Tests: DoxygenInstaller.get_platform_asset_name()
        How: Mock platform to return FreeBSD
        Why: Verify unknown operating systems fall through to default case

        Args:
            mocker: pytest-mock fixture for mocking
        """
        # Arrange
        _ = mocker.patch("mkapidocs.validators.platform.system", return_value="FreeBSD")
        _ = mocker.patch("mkapidocs.validators.platform.machine", return_value="x86_64")

        # Act
        asset_name = DoxygenInstaller.get_platform_asset_name()

        # Assert
        assert asset_name is None

    def test_download_and_install_unsupported_platform_macos(
        self, mocker: MockerFixture
    ) -> None:
        """Test download_and_install returns error for macOS.

        Tests: DoxygenInstaller.download_and_install()
        How: Mock get_platform_asset_name to return None, platform.system to return Darwin
        Why: Verify helpful error message for macOS users

        Args:
            mocker: pytest-mock fixture for mocking
        """
        # Arrange
        _ = mocker.patch(
            "mkapidocs.validators.DoxygenInstaller.get_platform_asset_name",
            return_value=None,
        )
        _ = mocker.patch("mkapidocs.validators.platform.system", return_value="Darwin")

        # Act
        success, message = DoxygenInstaller.download_and_install()

        # Assert
        assert success is False
        assert "macOS detected" in message
        assert "Homebrew" in message

    def test_download_and_install_unsupported_platform_generic(
        self, mocker: MockerFixture
    ) -> None:
        """Test download_and_install returns error for unsupported platforms.

        Tests: DoxygenInstaller.download_and_install()
        How: Mock get_platform_asset_name to return None, platform to return unsupported OS
        Why: Verify error handling for unsupported platforms

        Args:
            mocker: pytest-mock fixture for mocking
        """
        # Arrange
        _ = mocker.patch(
            "mkapidocs.validators.DoxygenInstaller.get_platform_asset_name",
            return_value=None,
        )
        _ = mocker.patch("mkapidocs.validators.platform.system", return_value="FreeBSD")
        _ = mocker.patch("mkapidocs.validators.platform.machine", return_value="x86_64")

        # Act
        success, message = DoxygenInstaller.download_and_install()

        # Assert
        assert success is False
        assert "Unsupported platform" in message

    def test_download_and_install_http_error(self, mocker: MockerFixture) -> None:
        """Test download_and_install handles HTTP errors gracefully.

        Tests: DoxygenInstaller.download_and_install() error handling
        How: Mock httpx.Client to raise HTTPError
        Why: Verify network error handling

        Args:
            mocker: pytest-mock fixture for mocking
        """
        # Arrange
        _ = mocker.patch(
            "mkapidocs.validators.DoxygenInstaller.get_platform_asset_name",
            return_value="doxygen-*.linux.bin.tar.gz",
        )
        _ = mocker.patch("mkapidocs.validators.platform.system", return_value="Linux")

        # Mock httpx.Client context manager - raise HTTPError specifically
        mock_client = mocker.MagicMock()
        mock_client.__enter__.return_value.get.side_effect = httpx.HTTPError(
            "Connection timeout"
        )
        _ = mocker.patch("mkapidocs.validators.httpx.Client", return_value=mock_client)

        # Mock console.print to avoid output
        _ = mocker.patch("mkapidocs.validators.console.print")

        # Act
        success, message = DoxygenInstaller.download_and_install()

        # Assert
        assert success is False
        assert "HTTP error downloading Doxygen" in message

    def test_download_and_install_no_matching_asset(
        self, mocker: MockerFixture
    ) -> None:
        """Test download_and_install handles missing asset in release.

        Tests: DoxygenInstaller.download_and_install()
        How: Mock GitHub API response with no matching assets
        Why: Verify error handling when expected asset not found

        Args:
            mocker: pytest-mock fixture for mocking
        """
        # Arrange
        _ = mocker.patch(
            "mkapidocs.validators.DoxygenInstaller.get_platform_asset_name",
            return_value="doxygen-*.linux.bin.tar.gz",
        )
        _ = mocker.patch("mkapidocs.validators.platform.system", return_value="Linux")

        # Mock httpx.Client for API call
        mock_response = mocker.MagicMock()
        mock_response.json.return_value = {
            "assets": [{"name": "doxygen-1.9.8-windows-setup.exe"}]
        }

        mock_client = mocker.MagicMock()
        mock_client.__enter__.return_value.get.return_value = mock_response
        _ = mocker.patch("mkapidocs.validators.httpx.Client", return_value=mock_client)

        # Mock console.print
        _ = mocker.patch("mkapidocs.validators.console.print")

        # Act
        success, message = DoxygenInstaller.download_and_install()

        # Assert
        assert success is False
        assert "No matching asset found" in message

    def test_install_linux_binary_success(
        self, mocker: MockerFixture, tmp_path: Path
    ) -> None:
        """Test _install_linux_binary successfully extracts and installs binary.

        Tests: DoxygenInstaller._install_linux_binary()
        How: Mock tarfile extraction, file operations, and shutil.copy2
        Why: Verify successful installation flow on Linux

        Args:
            mocker: pytest-mock fixture for mocking
            tmp_path: Pytest temporary directory
        """
        # Arrange
        tarball_path = tmp_path / "doxygen-1.9.8.tar.gz"
        tarball_path.touch()

        # Mock Path operations
        extract_dir = tmp_path / "extracted"
        extract_dir.mkdir()
        doxygen_bin = extract_dir / "bin" / "doxygen"
        doxygen_bin.parent.mkdir()
        doxygen_bin.touch()

        # Mock tarfile.open
        mock_tar = mocker.MagicMock()
        _ = mocker.patch("tarfile.open", return_value=mock_tar)
        mock_tar.__enter__.return_value.extractall = mocker.MagicMock()

        # Mock os.walk to find doxygen binary
        _ = mocker.patch(
            "os.walk", return_value=[(str(doxygen_bin.parent), [], ["doxygen"])]
        )

        # Mock shutil.copy2
        _ = mocker.patch("shutil.copy2")

        # Mock Path methods
        _ = mocker.patch.object(Path, "chmod")
        # Patch class attributes via module
        _ = mocker.patch(
            "mkapidocs.validators.DoxygenInstaller.CACHE_DIR", tmp_path / "cache"
        )
        _ = mocker.patch(
            "mkapidocs.validators.DoxygenInstaller.INSTALL_DIR", tmp_path / "install"
        )

        # Mock console.print
        _ = mocker.patch("mkapidocs.validators.console.print")

        # Act
        success, message = DoxygenInstaller._install_linux_binary(tarball_path)

        # Assert
        assert success is True
        assert "Doxygen installed to" in message

    def test_install_linux_binary_no_binary_found(
        self, mocker: MockerFixture, tmp_path: Path
    ) -> None:
        """Test _install_linux_binary handles missing binary in archive.

        Tests: DoxygenInstaller._install_linux_binary() error handling
        How: Mock os.walk to return no doxygen binary
        Why: Verify error handling for malformed archives

        Args:
            mocker: pytest-mock fixture for mocking
            tmp_path: Pytest temporary directory
        """
        # Arrange
        tarball_path = tmp_path / "doxygen-1.9.8.tar.gz"
        tarball_path.touch()

        # Mock tarfile.open
        mock_tar = mocker.MagicMock()
        _ = mocker.patch("tarfile.open", return_value=mock_tar)

        # Mock os.walk to find no doxygen binary
        _ = mocker.patch("os.walk", return_value=[("/some/path", [], ["README.md"])])

        _ = mocker.patch(
            "mkapidocs.validators.DoxygenInstaller.CACHE_DIR", tmp_path / "cache"
        )
        _ = mocker.patch("mkapidocs.validators.console.print")

        # Act
        success, message = DoxygenInstaller._install_linux_binary(tarball_path)

        # Assert
        assert success is False
        assert "Could not find doxygen binary" in message


class TestSystemValidator:
    """Test suite for SystemValidator class.

    Tests system-level requirement validation (git, uv, doxygen).
    """

    def test_check_git_installed(self, mocker: MockerFixture) -> None:
        """Test check_git returns passing result when git found.

        Tests: SystemValidator.check_git()
        How: Mock which() and subprocess to return git version
        Why: Verify git detection works correctly

        Args:
            mocker: pytest-mock fixture for mocking
        """
        # Arrange
        _ = mocker.patch("mkapidocs.validators.which", return_value="/usr/bin/git")
        mock_result = mocker.MagicMock()
        mock_result.stdout = "git version 2.39.0"
        _ = mocker.patch("subprocess.run", return_value=mock_result)

        # Act
        result = SystemValidator.check_git()

        # Assert
        assert result.passed is True
        assert result.check_name == "Git"
        assert result.value == "2.39.0"
        assert result.required is True

    def test_check_git_not_found(self, mocker: MockerFixture) -> None:
        """Test check_git returns failing result when git not in PATH.

        Tests: SystemValidator.check_git()
        How: Mock which() to return None
        Why: Verify detection handles missing git

        Args:
            mocker: pytest-mock fixture for mocking
        """
        # Arrange
        _ = mocker.patch("mkapidocs.validators.which", return_value=None)

        # Act
        result = SystemValidator.check_git()

        # Assert
        assert result.passed is False
        assert result.check_name == "Git"
        assert "Not found" in result.message
        assert result.required is True

    def test_check_git_version_check_fails(self, mocker: MockerFixture) -> None:
        """Test check_git handles version check failures.

        Tests: SystemValidator.check_git() error handling
        How: Mock subprocess to raise CalledProcessError
        Why: Verify error handling when git binary exists but fails

        Args:
            mocker: pytest-mock fixture for mocking
        """
        # Arrange
        _ = mocker.patch("mkapidocs.validators.which", return_value="/usr/bin/git")
        _ = mocker.patch(
            "subprocess.run", side_effect=subprocess.CalledProcessError(1, "git")
        )

        # Act
        result = SystemValidator.check_git()

        # Assert
        assert result.passed is False
        assert "version check failed" in result.message

    def test_check_uv_installed(self, mocker: MockerFixture) -> None:
        """Test check_uv returns passing result when uvx found.

        Tests: SystemValidator.check_uv()
        How: Mock which() and subprocess to return uvx version
        Why: Verify uv/uvx detection works correctly

        Args:
            mocker: pytest-mock fixture for mocking
        """
        # Arrange
        _ = mocker.patch(
            "mkapidocs.validators.which", return_value="/usr/local/bin/uvx"
        )
        mock_result = mocker.MagicMock()
        mock_result.stdout = "uvx 0.1.0"
        _ = mocker.patch("subprocess.run", return_value=mock_result)

        # Act
        result = SystemValidator.check_uv()

        # Assert
        assert result.passed is True
        assert result.check_name == "uv/uvx"
        assert result.value == "0.1.0"
        assert result.required is True

    def test_check_uv_not_found(self, mocker: MockerFixture) -> None:
        """Test check_uv returns failing result with install instructions.

        Tests: SystemValidator.check_uv()
        How: Mock which() to return None
        Why: Verify helpful error message includes installation URL

        Args:
            mocker: pytest-mock fixture for mocking
        """
        # Arrange
        _ = mocker.patch("mkapidocs.validators.which", return_value=None)

        # Act
        result = SystemValidator.check_uv()

        # Assert
        assert result.passed is False
        assert result.check_name == "uv/uvx"
        assert "https://docs.astral.sh/uv/" in result.message
        assert result.required is True

    def test_check_doxygen_installed(self, mocker: MockerFixture) -> None:
        """Test check_doxygen returns passing result when doxygen found.

        Tests: SystemValidator.check_doxygen()
        How: Mock DoxygenInstaller.is_installed to return True
        Why: Verify doxygen check delegates to DoxygenInstaller

        Args:
            mocker: pytest-mock fixture for mocking
        """
        # Arrange
        _ = mocker.patch(
            "mkapidocs.validators.DoxygenInstaller.is_installed",
            return_value=(True, "1.9.8"),
        )

        # Act
        result = SystemValidator.check_doxygen()

        # Assert
        assert result.passed is True
        assert result.check_name == "Doxygen"
        assert result.value == "1.9.8"
        assert result.required is False

    def test_check_doxygen_not_installed(self, mocker: MockerFixture) -> None:
        """Test check_doxygen returns informative result when not found.

        Tests: SystemValidator.check_doxygen()
        How: Mock DoxygenInstaller.is_installed to return False
        Why: Verify optional dependency has helpful message about auto-install

        Args:
            mocker: pytest-mock fixture for mocking
        """
        # Arrange
        _ = mocker.patch(
            "mkapidocs.validators.DoxygenInstaller.is_installed",
            return_value=(False, None),
        )

        # Act
        result = SystemValidator.check_doxygen()

        # Assert
        assert result.passed is False
        assert result.check_name == "Doxygen"
        assert "auto-install" in result.message
        assert result.required is False


class TestProjectValidator:
    """Test suite for ProjectValidator class.

    Tests project-specific validation (path, git repo, pyproject.toml, features).
    """

    def test_check_path_exists_valid_directory(self, mock_repo_path: Path) -> None:
        """Test check_path_exists passes for valid directory.

        Tests: ProjectValidator.check_path_exists()
        How: Use mock_repo_path fixture as valid directory
        Why: Verify basic path validation works

        Args:
            mock_repo_path: Temporary repository directory
        """
        # Arrange
        validator = ProjectValidator(mock_repo_path)

        # Act
        result = validator.check_path_exists()

        # Assert
        assert result.passed is True
        assert result.check_name == "Path exists"
        assert "Valid directory" in result.message

    def test_check_path_exists_missing_path(self, tmp_path: Path) -> None:
        """Test check_path_exists fails for non-existent path.

        Tests: ProjectValidator.check_path_exists()
        How: Use non-existent path
        Why: Verify validation catches missing directories

        Args:
            tmp_path: Pytest temporary directory
        """
        # Arrange
        nonexistent_path = tmp_path / "does_not_exist"
        validator = ProjectValidator(nonexistent_path)

        # Act
        result = validator.check_path_exists()

        # Assert
        assert result.passed is False
        assert "does not exist" in result.message

    def test_check_path_exists_file_not_directory(self, tmp_path: Path) -> None:
        """Test check_path_exists fails for file path.

        Tests: ProjectValidator.check_path_exists()
        How: Create file and pass as repo path
        Why: Verify validation requires directory, not file

        Args:
            tmp_path: Pytest temporary directory
        """
        # Arrange
        file_path = tmp_path / "file.txt"
        file_path.touch()
        validator = ProjectValidator(file_path)

        # Act
        result = validator.check_path_exists()

        # Assert
        assert result.passed is False
        assert "not a directory" in result.message

    def test_check_git_repository_valid(self, mock_repo_path: Path) -> None:
        """Test check_git_repository passes for git repo.

        Tests: ProjectValidator.check_git_repository()
        How: Create .git directory in mock repo
        Why: Verify git repository detection

        Args:
            mock_repo_path: Temporary repository directory
        """
        # Arrange
        (mock_repo_path / ".git").mkdir()
        validator = ProjectValidator(mock_repo_path)

        # Act
        result = validator.check_git_repository()

        # Assert
        assert result.passed is True
        assert result.check_name == "Git repository"

    def test_check_git_repository_not_git_repo(self, mock_repo_path: Path) -> None:
        """Test check_git_repository fails when no .git directory.

        Tests: ProjectValidator.check_git_repository()
        How: Use mock repo without .git directory
        Why: Verify validation detects non-git directories

        Args:
            mock_repo_path: Temporary repository directory
        """
        # Arrange
        validator = ProjectValidator(mock_repo_path)

        # Act
        result = validator.check_git_repository()

        # Assert
        assert result.passed is False
        assert "Not a git repository" in result.message

    def test_check_pyproject_toml_valid(
        self, mock_repo_path: Path, mock_pyproject_toml: Path
    ) -> None:
        """Test check_pyproject_toml passes for valid TOML file.

        Tests: ProjectValidator.check_pyproject_toml()
        How: Use mock_pyproject_toml fixture
        Why: Verify pyproject.toml validation and parsing

        Args:
            mock_repo_path: Temporary repository directory
            mock_pyproject_toml: Valid pyproject.toml file
        """
        # Arrange
        validator = ProjectValidator(mock_repo_path)

        # Act
        result = validator.check_pyproject_toml()

        # Assert
        assert result.passed is True
        assert "Valid TOML file" in result.message

    def test_check_pyproject_toml_missing(self, mock_repo_path: Path) -> None:
        """Test check_pyproject_toml fails when file missing.

        Tests: ProjectValidator.check_pyproject_toml()
        How: Use mock repo without pyproject.toml
        Why: Verify validation detects missing configuration

        Args:
            mock_repo_path: Temporary repository directory
        """
        # Arrange
        validator = ProjectValidator(mock_repo_path)

        # Act
        result = validator.check_pyproject_toml()

        # Assert
        assert result.passed is False
        assert "File not found" in result.message

    def test_check_pyproject_toml_invalid_toml(self, mock_repo_path: Path) -> None:
        """Test check_pyproject_toml fails for malformed TOML.

        Tests: ProjectValidator.check_pyproject_toml()
        How: Write invalid TOML syntax to file
        Why: Verify validation catches parse errors

        Args:
            mock_repo_path: Temporary repository directory
        """
        # Arrange
        pyproject_path = mock_repo_path / "pyproject.toml"
        _ = pyproject_path.write_text(
            "[project\nname = invalid"
        )  # Missing closing bracket
        validator = ProjectValidator(mock_repo_path)

        # Act
        result = validator.check_pyproject_toml()

        # Assert
        assert result.passed is False
        assert "Invalid TOML" in result.message

    def test_check_c_code_found(
        self, mocker: MockerFixture, mock_repo_path: Path
    ) -> None:
        """Test check_c_code detects C/C++ source files.

        Tests: ProjectValidator.check_c_code()
        How: Mock detect_c_code to return list with source directory
        Why: Verify C code detection integration

        Args:
            mocker: pytest-mock fixture for mocking
            mock_repo_path: Temporary repository directory
        """
        # Arrange
        _ = mocker.patch(
            "mkapidocs.validators.detect_c_code",
            return_value=[mock_repo_path / "source"],
        )
        validator = ProjectValidator(mock_repo_path)

        # Act
        result = validator.check_c_code()

        # Assert
        assert result.passed is True
        assert "Found in:" in result.message
        assert "source" in result.message
        assert result.value == "Doxygen required"

    def test_check_c_code_not_found(
        self, mocker: MockerFixture, mock_repo_path: Path
    ) -> None:
        """Test check_c_code returns passing result when no C code.

        Tests: ProjectValidator.check_c_code()
        How: Mock detect_c_code to return empty list
        Why: Verify optional C code detection doesn't fail without C code

        Args:
            mocker: pytest-mock fixture for mocking
            mock_repo_path: Temporary repository directory
        """
        # Arrange
        _ = mocker.patch("mkapidocs.validators.detect_c_code", return_value=[])
        validator = ProjectValidator(mock_repo_path)

        # Act
        result = validator.check_c_code()

        # Assert
        assert result.passed is True
        assert "Not found" in result.message
        assert result.value == "Doxygen not needed"

    def test_check_typer_dependency_found(
        self, mocker: MockerFixture, mock_repo_path: Path
    ) -> None:
        """Test check_typer_dependency detects Typer in dependencies.

        Tests: ProjectValidator.check_typer_dependency()
        How: Mock read_pyproject and detect_typer_dependency to return True
        Why: Verify Typer detection integration

        Args:
            mocker: pytest-mock fixture for mocking
            mock_repo_path: Temporary repository directory
        """
        # Arrange
        mock_pyproject = {"project": {"dependencies": ["typer>=0.9.0"]}}
        _ = mocker.patch(
            "mkapidocs.validators.read_pyproject", return_value=mock_pyproject
        )
        _ = mocker.patch(
            "mkapidocs.validators.detect_typer_dependency", return_value=True
        )
        validator = ProjectValidator(mock_repo_path)

        # Act
        result = validator.check_typer_dependency()

        # Assert
        assert result.passed is True
        assert "Found in dependencies" in result.message

    def test_check_typer_dependency_not_found(
        self, mocker: MockerFixture, mock_repo_path: Path
    ) -> None:
        """Test check_typer_dependency returns passing result without Typer.

        Tests: ProjectValidator.check_typer_dependency()
        How: Mock detect_typer_dependency to return False
        Why: Verify optional Typer detection doesn't fail without Typer

        Args:
            mocker: pytest-mock fixture for mocking
            mock_repo_path: Temporary repository directory
        """
        # Arrange
        mock_pyproject: TomlTable = {"project": {"dependencies": []}}
        _ = mocker.patch(
            "mkapidocs.validators.read_pyproject", return_value=mock_pyproject
        )
        _ = mocker.patch(
            "mkapidocs.validators.detect_typer_dependency", return_value=False
        )
        validator = ProjectValidator(mock_repo_path)

        # Act
        result = validator.check_typer_dependency()

        # Assert
        assert result.passed is True
        assert "Not found" in result.message

    def test_check_mkdocs_yml_found(self, mock_repo_path: Path) -> None:
        """Test check_mkdocs_yml passes when mkdocs.yml exists.

        Tests: ProjectValidator.check_mkdocs_yml()
        How: Create mkdocs.yml in mock repo
        Why: Verify mkdocs configuration detection

        Args:
            mock_repo_path: Temporary repository directory
        """
        # Arrange
        _ = (mock_repo_path / "mkdocs.yml").write_text("site_name: Test\n")
        validator = ProjectValidator(mock_repo_path)

        # Act
        result = validator.check_mkdocs_yml()

        # Assert
        assert result.passed is True
        assert "Found" in result.message

    def test_check_mkdocs_yml_missing(self, mock_repo_path: Path) -> None:
        """Test check_mkdocs_yml fails with helpful message when missing.

        Tests: ProjectValidator.check_mkdocs_yml()
        How: Use mock repo without mkdocs.yml
        Why: Verify validation guides user to run setup command

        Args:
            mock_repo_path: Temporary repository directory
        """
        # Arrange
        validator = ProjectValidator(mock_repo_path)

        # Act
        result = validator.check_mkdocs_yml()

        # Assert
        assert result.passed is False
        assert "run setup command first" in result.message


class TestValidationResult:
    """Test suite for ValidationResult dataclass.

    Tests ValidationResult instantiation and field access.
    """

    def test_validation_result_required_fields(self) -> None:
        """Test ValidationResult creation with required fields only.

        Tests: ValidationResult dataclass
        How: Create instance with check_name, passed, message
        Why: Verify minimal valid ValidationResult

        """
        # Act
        result = ValidationResult(
            check_name="Test Check", passed=True, message="Success"
        )

        # Assert
        assert result.check_name == "Test Check"
        assert result.passed is True
        assert result.message == "Success"
        assert result.value is None
        assert result.required is True

    def test_validation_result_all_fields(self) -> None:
        """Test ValidationResult with all fields including optional ones.

        Tests: ValidationResult dataclass with optional fields
        How: Create instance with value and required parameters
        Why: Verify all fields can be set and accessed

        """
        # Act
        result = ValidationResult(
            check_name="Version Check",
            passed=True,
            message="Found",
            value="1.2.3",
            required=False,
        )

        # Assert
        assert result.check_name == "Version Check"
        assert result.passed is True
        assert result.message == "Found"
        assert result.value == "1.2.3"
        assert result.required is False
