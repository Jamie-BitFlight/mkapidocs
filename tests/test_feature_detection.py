"""Tests for feature detection functions in mkapidocs script.

Tests cover:
- Git remote URL parsing for GitHub Pages
- C/C++ code detection
- Typer dependency detection
- Typer CLI module detection via AST parsing
- Private registry detection from pyproject.toml
"""

from __future__ import annotations

from pathlib import Path

import pytest
from mkapidocs.generator import (
    GitLabPagesResult,
    detect_c_code,
    detect_github_url_base,
    detect_private_registry,
    detect_typer_cli_module,
    detect_typer_dependency,
    query_gitlab_pages_url,
)
from mkapidocs.models import ProjectConfig, PyprojectConfig
from pytest_mock import MockerFixture

# Wrappers removed, using direct imports


class TestGitHubURLDetection:
    """Test suite for GitHub Pages URL detection from git remotes.

    Tests the detect_github_url_base function which parses git remote URLs
    to determine the GitHub Pages site URL.
    """

    def test_detect_github_url_ssh_format(self, mock_repo_path: Path) -> None:
        """Test GitHub URL detection with SSH remote format.

        Tests: detect_github_url_base parses SSH git URLs correctly
        How: Create .git/config file with SSH format git URL
        Why: GitHub SSH remotes are common, must parse to Pages URL

        Args:
            mock_repo_path: Temporary repository directory
            mocker: pytest-mock fixture
        """
        # Arrange
        git_dir = mock_repo_path / ".git"
        git_dir.mkdir()
        git_config = git_dir / "config"
        git_config.write_text(
            """[remote "origin"]
\turl = git@github.com:test-owner/test-repo.git
\tfetch = +refs/heads/*:refs/remotes/origin/*
"""
        )

        # Act
        result = detect_github_url_base(mock_repo_path)

        # Assert
        assert result == "https://test-owner.github.io/test-repo/"

    def test_detect_github_url_https_format(self, mock_repo_path: Path) -> None:
        """Test GitHub URL detection with HTTPS remote format.

        Tests: detect_github_url_base parses HTTPS git URLs correctly
        How: Create .git/config file with HTTPS format git URL
        Why: GitHub HTTPS remotes are common, must parse to Pages URL

        Args:
            mock_repo_path: Temporary repository directory
            mocker: pytest-mock fixture
        """
        # Arrange
        git_dir = mock_repo_path / ".git"
        git_dir.mkdir()
        git_config = git_dir / "config"
        git_config.write_text(
            """[remote "origin"]
\turl = https://github.com/test-owner/test-repo.git
\tfetch = +refs/heads/*:refs/remotes/origin/*
"""
        )

        # Act
        result = detect_github_url_base(mock_repo_path)

        # Assert
        assert result == "https://test-owner.github.io/test-repo/"

    def test_detect_github_url_ssh_without_git_suffix(self, mock_repo_path: Path) -> None:
        """Test GitHub URL detection with SSH format without .git suffix.

        Tests: detect_github_url_base handles URLs without .git extension
        How: Create .git/config file with SSH URL without .git
        Why: Some repositories use remote URLs without .git suffix

        Args:
            mock_repo_path: Temporary repository directory
            mocker: pytest-mock fixture
        """
        # Arrange
        git_dir = mock_repo_path / ".git"
        git_dir.mkdir()
        git_config = git_dir / "config"
        git_config.write_text(
            """[remote "origin"]
\turl = git@github.com:test-owner/test-repo
\tfetch = +refs/heads/*:refs/remotes/origin/*
"""
        )

        # Act
        result = detect_github_url_base(mock_repo_path)

        # Assert
        assert result == "https://test-owner.github.io/test-repo/"

    def test_detect_github_url_no_remote(self, mock_repo_path: Path, mocker: MockerFixture) -> None:
        """Test GitHub URL detection when git remote fails.

        Tests: detect_github_url_base returns None for repositories without remote
        How: Mock subprocess to return non-zero exit code
        Why: Not all repositories have remotes configured

        Args:
            mock_repo_path: Temporary repository directory
            mocker: pytest-mock fixture
        """
        # Arrange
        mock_result = mocker.MagicMock()
        mock_result.returncode = 128  # Git error code
        mock_result.stdout = ""
        mocker.patch("subprocess.run", return_value=mock_result)

        # Act
        result = detect_github_url_base(mock_repo_path)

        # Assert
        assert result is None

    def test_detect_github_url_non_github_remote(self, mock_repo_path: Path, mocker: MockerFixture) -> None:
        """Test GitHub URL detection with non-GitHub remote.

        Tests: detect_github_url_base returns None for GitLab/Bitbucket remotes
        How: Mock subprocess to return GitLab URL
        Why: Function should only parse GitHub URLs

        Args:
            mock_repo_path: Temporary repository directory
            mocker: pytest-mock fixture
        """
        # Arrange
        mock_result = mocker.MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "git@gitlab.com:test-owner/test-repo.git\n"
        mocker.patch("subprocess.run", return_value=mock_result)

        # Act
        result = detect_github_url_base(mock_repo_path)

        # Assert
        assert result is None


class TestCCodeDetection:
    """Test suite for C/C++ code detection in repository.

    Tests the detect_c_code function which returns list of directories
    containing C/C++ files.
    """

    def test_detect_c_code_with_c_files(self, mock_c_code_repo: Path) -> None:
        """Test C code detection when .c files present.

        Tests: detect_c_code returns list with source/ directory for repositories with C files
        How: Use mock_c_code_repo fixture with .c and .h files
        Why: C files should trigger Doxygen documentation

        Args:
            mock_c_code_repo: Repository with C source files
        """
        # Act
        result = detect_c_code(mock_c_code_repo)

        # Assert
        assert len(result) == 1
        assert result[0] == mock_c_code_repo / "source"

    def test_detect_c_code_with_cpp_files(self, mock_repo_path: Path) -> None:
        """Test C code detection when .cpp files present.

        Tests: detect_c_code returns list with source/ directory for C++ files
        How: Create source/ directory with .cpp and .hpp files
        Why: C++ files should also trigger Doxygen documentation

        Args:
            mock_repo_path: Temporary repository directory
        """
        # Arrange
        source_dir = mock_repo_path / "source"
        source_dir.mkdir()
        (source_dir / "main.cpp").write_text("int main() { return 0; }")
        (source_dir / "utils.hpp").write_text("#ifndef UTILS_HPP\n#define UTILS_HPP\n#endif")

        # Act
        result = detect_c_code(mock_repo_path)

        # Assert
        assert len(result) == 1
        assert result[0] == source_dir.resolve()

    def test_detect_c_code_no_source_directory(self, mock_repo_path: Path) -> None:
        """Test C code detection when source/ directory missing.

        Tests: detect_c_code returns empty list without source/ directory
        How: Use repo without creating source/ directory
        Why: Function should handle missing directory gracefully

        Args:
            mock_repo_path: Temporary repository directory
        """
        # Act
        result = detect_c_code(mock_repo_path)

        # Assert
        assert result == []

    def test_detect_c_code_source_dir_exists_no_c_files(self, mock_repo_path: Path) -> None:
        """Test C code detection when source/ exists but no C files.

        Tests: detect_c_code returns empty list with only Python files in source/
        How: Create source/ with .py files
        Why: Should only detect C/C++ extensions

        Args:
            mock_repo_path: Temporary repository directory
        """
        # Arrange
        source_dir = mock_repo_path / "source"
        source_dir.mkdir()
        (source_dir / "script.py").write_text('print("hello")')
        (source_dir / "data.txt").write_text("some data")

        # Act
        result = detect_c_code(mock_repo_path)

        # Assert
        assert result == []

    def test_detect_c_code_with_cc_extension(self, mock_repo_path: Path) -> None:
        """Test C code detection with .cc extension (Google C++ style).

        Tests: detect_c_code recognizes .cc extension
        How: Create source/ with .cc file
        Why: .cc is valid C++ extension used by Google

        Args:
            mock_repo_path: Temporary repository directory
        """
        # Arrange
        source_dir = mock_repo_path / "source"
        source_dir.mkdir()
        (source_dir / "main.cc").write_text("int main() { return 0; }")

        # Act
        result = detect_c_code(mock_repo_path)

        # Assert
        assert len(result) == 1
        assert result[0] == source_dir.resolve()


class TestTyperDependencyDetection:
    """Test suite for Typer dependency detection in pyproject.toml.

    Tests the detect_typer_dependency function which checks project
    dependencies for the Typer package.
    """

    def test_detect_typer_dependency_present(self, mock_pyproject_with_typer: PyprojectConfig) -> None:
        """Test Typer dependency detection when typer in dependencies.

        Tests: detect_typer_dependency returns True when typer listed
        How: Use mock pyproject dict with typer>=0.9.0
        Why: Typer presence enables CLI documentation features

        Args:
            mock_pyproject_with_typer: Parsed pyproject with Typer
        """
        # Act
        result = detect_typer_dependency(mock_pyproject_with_typer)

        # Assert
        assert result is True

    def test_detect_typer_dependency_absent(self, parsed_pyproject: PyprojectConfig) -> None:
        """Test Typer dependency detection when typer not in dependencies.

        Tests: detect_typer_dependency returns False without typer
        How: Use minimal pyproject without typer
        Why: Should not enable CLI docs for non-CLI projects

        Args:
            parsed_pyproject: Minimal parsed pyproject dict
        """
        # Act
        result = detect_typer_dependency(parsed_pyproject)

        # Assert
        assert result is False

    def test_detect_typer_dependency_no_dependencies_key(self) -> None:
        """Test Typer dependency detection when dependencies key missing.

        Tests: detect_typer_dependency handles missing dependencies gracefully
        How: Pass pyproject dict without project.dependencies key
        Why: Should not crash on malformed pyproject.toml

        """
        # Arrange
        pyproject = PyprojectConfig(project=ProjectConfig(name="test"))

        # Act
        result = detect_typer_dependency(pyproject)

        # Assert
        assert result is False

    def test_detect_typer_dependency_case_insensitive(self) -> None:
        """Test Typer dependency detection is case-insensitive.

        Tests: detect_typer_dependency matches "TYPER" or "Typer"
        How: Pass dependencies with uppercase TYPER
        Why: Dependency names should match regardless of case

        """
        # Arrange
        pyproject = PyprojectConfig(project=ProjectConfig(name="test", dependencies=["TYPER>=0.9.0", "click>=8.0"]))

        # Act
        result = detect_typer_dependency(pyproject)

        # Assert
        assert result is True

    @pytest.mark.parametrize(
        "dependency_string",
        [
            "typer>=0.9.0",
            "typer[all]>=0.9.0",
            "typer",
            "  typer>=0.9.0  ",  # with whitespace
        ],
    )
    def test_detect_typer_dependency_various_formats(self, dependency_string: str) -> None:
        """Test Typer dependency detection with various dependency formats.

        Tests: detect_typer_dependency handles version specifiers and extras
        How: Parametrized test with different typer dependency strings
        Why: PyPI dependencies can have extras, versions, whitespace

        Args:
            dependency_string: Various typer dependency formats
        """
        # Arrange
        pyproject = PyprojectConfig(project=ProjectConfig(name="test", dependencies=[dependency_string]))

        # Act
        result = detect_typer_dependency(pyproject)

        # Assert
        assert result is True


class TestTyperCLIModuleDetection:
    """Test suite for Typer CLI module detection via AST parsing.

    Tests the detect_typer_cli_module function which searches the
    package structure for Python files containing Typer app instances.
    """

    def test_detect_typer_cli_module_found(
        self, mock_typer_cli_repo: Path, mock_pyproject_with_typer: PyprojectConfig
    ) -> None:
        """Test Typer CLI module detection when CLI module exists.

        Tests: detect_typer_cli_module returns list of module paths for Typer apps
        How: Use mock repo with package containing cli.py with Typer app
        Why: Enables automatic CLI documentation generation

        Args:
            mock_typer_cli_repo: Repository with Typer CLI
            mock_pyproject_with_typer: Parsed pyproject with Typer
        """
        # Act
        result = detect_typer_cli_module(mock_typer_cli_repo, mock_pyproject_with_typer)

        # Assert
        assert result == ["test_cli_project.cli"]

    def test_detect_typer_cli_module_no_package(
        self, mock_repo_path: Path, mock_pyproject_with_typer: PyprojectConfig
    ) -> None:
        """Test Typer CLI module detection when package directory missing.

        Tests: detect_typer_cli_module returns empty list without package
        How: Use repo without creating package directory
        Why: Should handle projects without source code gracefully

        Args:
            mock_repo_path: Empty repository directory
            mock_pyproject_with_typer: Parsed pyproject with Typer
        """
        # Act
        result = detect_typer_cli_module(mock_repo_path, mock_pyproject_with_typer)

        # Assert
        assert result == []

    def test_detect_typer_cli_module_no_typer_import(
        self, mock_repo_path: Path, mock_pyproject_with_typer: PyprojectConfig
    ) -> None:
        """Test Typer CLI module detection when Python files lack typer import.

        Tests: detect_typer_cli_module returns empty list without typer imports
        How: Create package with .py files but no typer usage
        Why: Should only detect files with actual Typer usage

        Args:
            mock_repo_path: Temporary repository directory
            mock_pyproject_with_typer: Parsed pyproject with Typer
        """
        # Arrange
        package_dir = mock_repo_path / "test_cli_project"
        package_dir.mkdir()
        (package_dir / "__init__.py").write_text('"""Package without CLI."""')
        (package_dir / "utils.py").write_text("def helper(): pass")

        # Act
        result = detect_typer_cli_module(mock_repo_path, mock_pyproject_with_typer)

        # Assert
        assert result == []

    def test_detect_typer_cli_module_skips_test_files(
        self, mock_repo_path: Path, mock_pyproject_with_typer: PyprojectConfig
    ) -> None:
        """Test Typer CLI module detection skips test files.

        Tests: detect_typer_cli_module ignores test_*.py files
        How: Create package with Typer app only in test file
        Why: Test files should not be documented as CLI entry points

        Args:
            mock_repo_path: Temporary repository directory
            mock_pyproject_with_typer: Parsed pyproject with Typer
        """
        # Arrange
        package_dir = mock_repo_path / "test_cli_project"
        package_dir.mkdir()
        (package_dir / "__init__.py").write_text('"""Package."""')
        (package_dir / "test_cli.py").write_text(
            """import typer
app = typer.Typer()
"""
        )

        # Act
        result = detect_typer_cli_module(mock_repo_path, mock_pyproject_with_typer)

        # Assert
        assert result == []


class TestPrivateRegistryDetection:
    """Test suite for private registry detection from pyproject.toml.

    Tests the detect_private_registry function which checks for
    private PyPI registry configuration in tool.uv.index.
    """

    def test_detect_private_registry_present(self, mock_pyproject_with_private_registry: PyprojectConfig) -> None:
        """Test private registry detection when configured.

        Tests: detect_private_registry returns True and URL when configured
        How: Use mock pyproject with [tool.uv.index] section
        Why: Private registries require special GitHub Actions authentication

        Args:
            mock_pyproject_with_private_registry: Parsed pyproject with registry
        """
        # Act
        is_private, registry_url = detect_private_registry(mock_pyproject_with_private_registry)

        # Assert
        assert is_private is True
        assert registry_url == "https://private.pypi.org/simple"

    def test_detect_private_registry_absent(self, parsed_pyproject: PyprojectConfig) -> None:
        """Test private registry detection when not configured.

        Tests: detect_private_registry returns False and None without config
        How: Use minimal pyproject without uv.index section
        Why: Most projects use public PyPI

        Args:
            parsed_pyproject: Minimal parsed pyproject dict
        """
        # Act
        is_private, registry_url = detect_private_registry(parsed_pyproject)

        # Assert
        assert is_private is False
        assert registry_url is None

    def test_detect_private_registry_empty_index_list(self) -> None:
        """Test private registry detection with empty index list.

        Tests: detect_private_registry handles empty index list
        How: Pass pyproject with tool.uv.index = []
        Why: Should not crash on empty configuration

        """
        # Arrange
        # Arrange
        pyproject = PyprojectConfig(project=ProjectConfig(name="test"), tool={"uv": {"index": []}})

        # Act
        is_private, registry_url = detect_private_registry(pyproject)

        # Assert
        assert is_private is False
        assert registry_url is None

    def test_detect_private_registry_no_tool_section(self) -> None:
        """Test private registry detection when tool section uses defaults.

        Tests: detect_private_registry handles default tool config
        How: Pass pyproject without explicit tool configuration
        Why: Should handle projects without uv configuration gracefully

        """
        # Arrange
        pyproject = PyprojectConfig(project=ProjectConfig(name="test"))

        # Act
        is_private, registry_url = detect_private_registry(pyproject)

        # Assert
        assert is_private is False
        assert registry_url is None


class TestGitLabPagesURLQuery:
    """Test suite for GitLab API Pages URL query.

    Tests the query_gitlab_pages_url function which fetches
    the Pages URL from GitLab API using available tokens.
    """

    def test_query_returns_error_without_token(self, mocker: MockerFixture) -> None:
        """Test that query returns error when no token is available.

        Tests: query_gitlab_pages_url returns error without GITLAB_TOKEN or CI_JOB_TOKEN
        How: Ensure environment variables are not set
        """
        # Arrange
        mocker.patch.dict("os.environ", {}, clear=True)

        # Act
        result = query_gitlab_pages_url("gitlab.example.com", "group/project")

        # Assert
        assert isinstance(result, GitLabPagesResult)
        assert result.url is None
        assert result.error == "no_token"

    def test_query_returns_url_on_success(self, mocker: MockerFixture) -> None:
        """Test that query returns URL when GraphQL API call succeeds.

        Tests: query_gitlab_pages_url returns URL from GraphQL response
        How: Mock httpx.Client to return successful GraphQL response with URL
        """
        # Arrange
        mocker.patch.dict("os.environ", {"GITLAB_TOKEN": "test-token"})
        mock_response = mocker.MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {
                "project": {"pagesDeployments": {"nodes": [{"url": "https://group.pages.gitlab.example.com/project"}]}}
            }
        }

        mock_client = mocker.MagicMock()
        mock_client.__enter__ = mocker.MagicMock(return_value=mock_client)
        mock_client.__exit__ = mocker.MagicMock(return_value=False)
        mock_client.post.return_value = mock_response

        mocker.patch("httpx.Client", return_value=mock_client)

        # Act
        result = query_gitlab_pages_url("gitlab.example.com", "group/project")

        # Assert
        assert isinstance(result, GitLabPagesResult)
        assert result.url == "https://group.pages.gitlab.example.com/project"
        assert result.error is None
        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        assert "gitlab.example.com/api/graphql" in call_args[0][0]

    def test_query_returns_error_on_api_error(self, mocker: MockerFixture) -> None:
        """Test that query returns error on API error.

        Tests: query_gitlab_pages_url returns error on 403/404 status
        How: Mock httpx.Client to return error status
        """
        # Arrange
        mocker.patch.dict("os.environ", {"GITLAB_TOKEN": "test-token"})
        mock_response = mocker.MagicMock()
        mock_response.status_code = 403

        mock_client = mocker.MagicMock()
        mock_client.__enter__ = mocker.MagicMock(return_value=mock_client)
        mock_client.__exit__ = mocker.MagicMock(return_value=False)
        mock_client.post.return_value = mock_response

        mocker.patch("httpx.Client", return_value=mock_client)

        # Act
        result = query_gitlab_pages_url("gitlab.example.com", "group/project")

        # Assert
        assert isinstance(result, GitLabPagesResult)
        assert result.url is None
        assert result.error == "HTTP 403"

    def test_query_returns_error_on_network_error(self, mocker: MockerFixture) -> None:
        """Test that query returns error on network error.

        Tests: query_gitlab_pages_url handles network errors gracefully
        How: Mock httpx.Client.post to raise RequestError
        """
        import httpx

        # Arrange
        mocker.patch.dict("os.environ", {"GITLAB_TOKEN": "test-token"})

        mock_client = mocker.MagicMock()
        mock_client.__enter__ = mocker.MagicMock(return_value=mock_client)
        mock_client.__exit__ = mocker.MagicMock(return_value=False)
        mock_client.post.side_effect = httpx.RequestError("Connection failed")

        mocker.patch("httpx.Client", return_value=mock_client)

        # Act
        result = query_gitlab_pages_url("gitlab.example.com", "group/project")

        # Assert
        assert isinstance(result, GitLabPagesResult)
        assert result.url is None
        assert result.error is not None
        assert "Network error" in result.error

    def test_query_uses_ci_job_token_as_fallback(self, mocker: MockerFixture) -> None:
        """Test that query uses CI_JOB_TOKEN when GITLAB_TOKEN is not set.

        Tests: query_gitlab_pages_url falls back to CI_JOB_TOKEN
        How: Set only CI_JOB_TOKEN and verify API call is made
        """
        # Arrange
        mocker.patch.dict("os.environ", {"CI_JOB_TOKEN": "job-token"}, clear=True)
        mock_response = mocker.MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {"project": {"pagesDeployments": {"nodes": [{"url": "https://pages.example.com/project"}]}}}
        }

        mock_client = mocker.MagicMock()
        mock_client.__enter__ = mocker.MagicMock(return_value=mock_client)
        mock_client.__exit__ = mocker.MagicMock(return_value=False)
        mock_client.post.return_value = mock_response

        mocker.patch("httpx.Client", return_value=mock_client)

        # Act
        result = query_gitlab_pages_url("gitlab.example.com", "namespace/project")

        # Assert
        assert isinstance(result, GitLabPagesResult)
        assert result.url == "https://pages.example.com/project"
        # Verify the token was used in the Authorization header
        call_kwargs = mock_client.post.call_args
        assert call_kwargs[1]["headers"]["Authorization"] == "Bearer job-token"

    def test_query_returns_no_deployments_when_empty(self, mocker: MockerFixture) -> None:
        """Test that query returns no_deployments flag when project has no Pages deployments.

        Tests: query_gitlab_pages_url returns no_deployments=True for empty deployments
        How: Mock GraphQL response with empty nodes array
        """
        # Arrange
        mocker.patch.dict("os.environ", {"GITLAB_TOKEN": "test-token"})
        mock_response = mocker.MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": {"project": {"pagesDeployments": {"nodes": []}}}}

        mock_client = mocker.MagicMock()
        mock_client.__enter__ = mocker.MagicMock(return_value=mock_client)
        mock_client.__exit__ = mocker.MagicMock(return_value=False)
        mock_client.post.return_value = mock_response

        mocker.patch("httpx.Client", return_value=mock_client)

        # Act
        result = query_gitlab_pages_url("gitlab.example.com", "group/project")

        # Assert
        assert isinstance(result, GitLabPagesResult)
        assert result.url is None
        assert result.no_deployments is True
        assert result.error is None
