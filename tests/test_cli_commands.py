"""Tests for CLI commands in mkapidocs script.

Tests cover:
- version command output
- info command output
- setup command with various scenarios
- build command with various scenarios
- serve command invocation
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_mock import MockerFixture
from typer import Typer
from typer.testing import CliRunner


@pytest.fixture
def cli_runner() -> CliRunner:
    """Provide Typer CLI test runner.

    Tests: CLI command execution
    How: Create CliRunner instance from typer.testing
    Why: Enables CLI testing without invoking subprocess

    Returns:
        CliRunner for testing Typer commands
    """
    return CliRunner()


@pytest.fixture
def typer_app() -> Typer:
    """Extract Typer app from mkapidocs module.

    Tests: CLI app instance access
    How: Get app attribute from shared mkapidocs module loaded in conftest
    Why: Ensures all tests use the same Typer app instance

    Returns:
        Typer app instance for CLI testing
    """
    from mkapidocs.cli import app

    return app


class TestVersionCommand:
    """Test suite for version command.

    Tests the version command which displays version information.
    """

    def test_version_command_success(self, cli_runner: CliRunner, typer_app: Typer) -> None:
        """Test version command displays version info.

        Tests: version command shows version number
        How: Invoke version command via CliRunner
        Why: Users need to check installed version

        Args:
            cli_runner: Typer test runner
            typer_app: Typer app instance from fixture
        """
        # Act
        result = cli_runner.invoke(typer_app, ["version"])

        # Assert
        assert result.exit_code == 0
        assert "1.0.0" in result.stdout
        assert "mkapidocs" in result.stdout


class TestInfoCommand:
    """Test suite for info command.

    Tests the info command which displays package information.
    """

    def test_info_command_success(self, cli_runner: CliRunner, typer_app: Typer) -> None:
        """Test info command displays package details.

        Tests: info command shows package metadata
        How: Invoke info command via CliRunner
        Why: Users need package information for troubleshooting

        Args:
            cli_runner: Typer test runner
            typer_app: Typer app instance from fixture
        """
        # Act
        result = cli_runner.invoke(typer_app, ["info"])

        # Assert
        assert result.exit_code == 0
        assert "mkapidocs" in result.stdout
        assert "1.0.0" in result.stdout
        assert "Automated documentation setup tool" in result.stdout


class TestSetupCommand:
    """Test suite for setup command.

    Tests the setup command which initializes documentation for a project.
    """

    def test_setup_command_validation_failure(
        self, cli_runner: CliRunner, mock_repo_path: Path, mocker: MockerFixture, typer_app: Typer
    ) -> None:
        """Test setup command fails when validation fails.

        Tests: setup command exits with error on validation failure
        How: Mock validate_environment to return failure
        Why: Should not proceed with setup if environment invalid

        Args:
            cli_runner: Typer test runner
            mock_repo_path: Temporary repository directory
            mocker: pytest-mock fixture
            typer_app: Typer app instance from fixture
        """
        # Arrange
        mocker.patch("mkapidocs.cli.validate_environment", return_value=(False, []))

        # Act
        result = cli_runner.invoke(typer_app, ["setup", str(mock_repo_path)])

        # Assert
        assert result.exit_code == 1

    def test_setup_command_missing_pyproject(
        self, cli_runner: CliRunner, mock_repo_path: Path, typer_app: Typer
    ) -> None:
        """Test setup command fails when pyproject.toml missing.

        Tests: setup command handles missing pyproject.toml
        How: Run setup on directory without pyproject.toml
        Why: pyproject.toml is required for project metadata

        Args:
            cli_runner: Typer test runner
            mock_repo_path: Temporary repository directory without pyproject.toml
            typer_app: Typer app instance from fixture
        """
        # Act
        result = cli_runner.invoke(typer_app, ["setup", str(mock_repo_path)])

        # Assert
        assert result.exit_code == 1

    def test_setup_command_with_custom_github_url(
        self,
        cli_runner: CliRunner,
        mock_repo_path: Path,
        mock_pyproject_toml: Path,
        mocker: MockerFixture,
        typer_app: Typer,
    ) -> None:
        """Test setup command accepts custom GitHub URL.

        Tests: setup command --github-url-base option
        How: Mock setup_documentation and validation, provide custom URL
        Why: Users may want to override auto-detected GitHub Pages URL

        Args:
            cli_runner: Typer test runner
            mock_repo_path: Temporary repository directory
            mock_pyproject_toml: Mock pyproject.toml file
            mocker: pytest-mock fixture
            typer_app: Typer app instance from fixture
        """
        # Arrange
        mocker.patch("mkapidocs.cli.validate_environment", return_value=(True, []))
        mock_setup = mocker.patch("mkapidocs.cli.setup_documentation")
        custom_url = "https://custom.github.io/project/"

        # Act
        result = cli_runner.invoke(typer_app, ["setup", str(mock_repo_path), "--github-url-base", custom_url])

        # Assert
        assert result.exit_code == 0
        mock_setup.assert_called_once()
        args = mock_setup.call_args[0]
        assert args[2] == custom_url  # Third argument is github_url_base (after repo_path and provider)


class TestBuildCommand:
    """Test suite for build command.

    Tests the build command which builds static documentation.
    """

    def test_build_command_validation_failure(
        self, cli_runner: CliRunner, mock_repo_path: Path, mocker: MockerFixture, typer_app: Typer
    ) -> None:
        """Test build command fails when validation fails.

        Tests: build command exits with error on validation failure
        How: Mock validate_environment to return failure
        Why: Should not attempt build if environment invalid

        Args:
            cli_runner: Typer test runner
            mock_repo_path: Temporary repository directory
            mocker: pytest-mock fixture
            typer_app: Typer app instance from fixture
        """
        # Arrange
        mocker.patch("mkapidocs.cli.validate_environment", return_value=(False, []))

        # Act
        result = cli_runner.invoke(typer_app, ["build", str(mock_repo_path)])

        # Assert
        assert result.exit_code == 1

    def test_build_command_missing_mkdocs_yml(
        self, cli_runner: CliRunner, mock_repo_path: Path, mocker: MockerFixture, typer_app: Typer
    ) -> None:
        """Test build command fails when mkdocs.yml missing.

        Tests: build command handles missing mkdocs.yml
        How: Mock validation to pass, but mkdocs.yml doesn't exist
        Why: Cannot build docs without configuration file

        Args:
            cli_runner: Typer test runner
            mock_repo_path: Temporary repository directory
            mocker: pytest-mock fixture
            typer_app: Typer app instance from fixture
        """
        # Arrange
        mocker.patch("mkapidocs.cli.validate_environment", return_value=(True, []))

        # Act
        result = cli_runner.invoke(typer_app, ["build", str(mock_repo_path)])

        # Assert
        assert result.exit_code == 1

    def test_build_command_success(
        self, cli_runner: CliRunner, mock_repo_path: Path, mocker: MockerFixture, typer_app: Typer
    ) -> None:
        """Test build command succeeds with valid configuration.

        Tests: build command executes mkdocs build successfully
        How: Mock validation, build_docs function, create mkdocs.yml
        Why: Successful build should exit with code 0

        Args:
            cli_runner: Typer test runner
            mock_repo_path: Temporary repository directory
            mocker: pytest-mock fixture
            typer_app: Typer app instance from fixture
        """
        # Arrange
        mocker.patch("mkapidocs.cli.validate_environment", return_value=(True, []))
        mock_build = mocker.patch("mkapidocs.cli.build_docs", return_value=0)
        (mock_repo_path / "mkdocs.yml").write_text("site_name: Test")

        # Act
        result = cli_runner.invoke(typer_app, ["build", str(mock_repo_path)])

        # Assert
        assert result.exit_code == 0
        mock_build.assert_called_once()

    def test_build_command_with_strict_flag(
        self, cli_runner: CliRunner, mock_repo_path: Path, mocker: MockerFixture, typer_app: Typer
    ) -> None:
        """Test build command with --strict flag.

        Tests: build command passes strict=True to build_docs
        How: Mock build_docs, verify strict parameter
        Why: Strict mode treats warnings as errors

        Args:
            cli_runner: Typer test runner
            mock_repo_path: Temporary repository directory
            mocker: pytest-mock fixture
            typer_app: Typer app instance from fixture
        """
        # Arrange
        mocker.patch("mkapidocs.cli.validate_environment", return_value=(True, []))
        mock_build = mocker.patch("mkapidocs.cli.build_docs", return_value=0)
        (mock_repo_path / "mkdocs.yml").write_text("site_name: Test")

        # Act
        result = cli_runner.invoke(typer_app, ["build", str(mock_repo_path), "--strict"])

        # Assert
        assert result.exit_code == 0
        mock_build.assert_called_once()
        assert mock_build.call_args[1]["strict"] is True

    def test_build_command_with_output_dir(
        self, cli_runner: CliRunner, mock_repo_path: Path, mocker: MockerFixture, tmp_path: Path, typer_app: Typer
    ) -> None:
        """Test build command with custom output directory.

        Tests: build command --output-dir option
        How: Mock build_docs, verify output_dir parameter
        Why: Users may want docs in custom location

        Args:
            cli_runner: Typer test runner
            mock_repo_path: Temporary repository directory
            mocker: pytest-mock fixture
            tmp_path: Pytest temporary directory
            typer_app: Typer app instance from fixture
        """
        # Arrange
        mocker.patch("mkapidocs.cli.validate_environment", return_value=(True, []))
        mock_build = mocker.patch("mkapidocs.cli.build_docs", return_value=0)
        (mock_repo_path / "mkdocs.yml").write_text("site_name: Test")
        output_dir = tmp_path / "custom_output"

        # Act
        result = cli_runner.invoke(typer_app, ["build", str(mock_repo_path), "--output-dir", str(output_dir)])

        # Assert
        assert result.exit_code == 0
        mock_build.assert_called_once()
        assert mock_build.call_args[1]["output_dir"] == output_dir

    def test_build_command_build_failure(
        self, cli_runner: CliRunner, mock_repo_path: Path, mocker: MockerFixture, typer_app: Typer
    ) -> None:
        """Test build command handles mkdocs build failure.

        Tests: build command exits with mkdocs exit code on failure
        How: Mock build_docs to return non-zero exit code
        Why: Should propagate build errors to user

        Args:
            cli_runner: Typer test runner
            mock_repo_path: Temporary repository directory
            mocker: pytest-mock fixture
            typer_app: Typer app instance from fixture
        """
        # Arrange
        mocker.patch("mkapidocs.cli.validate_environment", return_value=(True, []))
        mocker.patch("mkapidocs.cli.build_docs", return_value=1)
        (mock_repo_path / "mkdocs.yml").write_text("site_name: Test")

        # Act
        result = cli_runner.invoke(typer_app, ["build", str(mock_repo_path)])

        # Assert
        assert result.exit_code == 1


class TestServeCommand:
    """Test suite for serve command.

    Tests the serve command which serves documentation locally.
    """

    def test_serve_command_validation_failure(
        self, cli_runner: CliRunner, mock_repo_path: Path, mocker: MockerFixture, typer_app: Typer
    ) -> None:
        """Test serve command fails when validation fails.

        Tests: serve command exits with error on validation failure
        How: Mock validate_environment to return failure
        Why: Should not attempt to serve if environment invalid

        Args:
            cli_runner: Typer test runner
            mock_repo_path: Temporary repository directory
            mocker: pytest-mock fixture
            typer_app: Typer app instance from fixture
        """
        # Arrange
        mocker.patch("mkapidocs.cli.validate_environment", return_value=(False, []))

        # Act
        result = cli_runner.invoke(typer_app, ["serve", str(mock_repo_path)])

        # Assert
        assert result.exit_code == 1

    def test_serve_command_missing_mkdocs_yml(
        self, cli_runner: CliRunner, mock_repo_path: Path, mocker: MockerFixture, typer_app: Typer
    ) -> None:
        """Test serve command fails when mkdocs.yml missing.

        Tests: serve command handles missing mkdocs.yml
        How: Mock validation to pass, but mkdocs.yml doesn't exist
        Why: Cannot serve docs without configuration file

        Args:
            cli_runner: Typer test runner
            mock_repo_path: Temporary repository directory
            mocker: pytest-mock fixture
            typer_app: Typer app instance from fixture
        """
        # Arrange
        mocker.patch("mkapidocs.cli.validate_environment", return_value=(True, []))

        # Act
        result = cli_runner.invoke(typer_app, ["serve", str(mock_repo_path)])

        # Assert
        assert result.exit_code == 1

    def test_serve_command_success(
        self, cli_runner: CliRunner, mock_repo_path: Path, mocker: MockerFixture, typer_app: Typer
    ) -> None:
        """Test serve command invokes mkdocs serve.

        Tests: serve command executes mkdocs serve successfully
        How: Mock validation, serve_docs function, create mkdocs.yml
        Why: Successful serve should exit with code 0

        Args:
            cli_runner: Typer test runner
            mock_repo_path: Temporary repository directory
            mocker: pytest-mock fixture
            typer_app: Typer app instance from fixture
        """
        # Arrange
        mocker.patch("mkapidocs.cli.validate_environment", return_value=(True, []))
        mock_serve = mocker.patch("mkapidocs.cli.serve_docs", return_value=0)
        (mock_repo_path / "mkdocs.yml").write_text("site_name: Test")

        # Act
        result = cli_runner.invoke(typer_app, ["serve", str(mock_repo_path)])

        # Assert
        assert result.exit_code == 0
        mock_serve.assert_called_once()

    def test_serve_command_with_host_and_port(
        self, cli_runner: CliRunner, mock_repo_path: Path, mocker: MockerFixture, typer_app: Typer
    ) -> None:
        """Test serve command with custom host and port.

        Tests: serve command --host and --port options
        How: Mock serve_docs, verify host and port parameters
        Why: Users may want to serve on different address/port

        Args:
            cli_runner: Typer test runner
            mock_repo_path: Temporary repository directory
            mocker: pytest-mock fixture
            typer_app: Typer app instance from fixture
        """
        # Arrange
        mocker.patch("mkapidocs.cli.validate_environment", return_value=(True, []))
        mock_serve = mocker.patch("mkapidocs.cli.serve_docs", return_value=0)
        (mock_repo_path / "mkdocs.yml").write_text("site_name: Test")

        # Act
        result = cli_runner.invoke(typer_app, ["serve", str(mock_repo_path), "--host", "0.0.0.0", "--port", "9000"])

        # Assert
        assert result.exit_code == 0
        mock_serve.assert_called_once()
        assert mock_serve.call_args[1]["host"] == "0.0.0.0"
        assert mock_serve.call_args[1]["port"] == 9000
