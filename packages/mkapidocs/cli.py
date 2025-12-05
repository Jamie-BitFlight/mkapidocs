"""mkapidocs - Automated documentation setup for Python projects.

This script sets up MkDocs documentation for Python repositories with auto-detection
of features like C/C++ code and Typer CLI interfaces.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import httpx
import typer
from rich.console import Console
from tomlkit.exceptions import TOMLKitError

from mkapidocs.builder import build_docs, is_running_in_target_env, serve_docs
from mkapidocs.generator import (
    console as generator_console,
    display_message,
    setup_documentation,
)
from mkapidocs.models import CIProvider, MessageType
from mkapidocs.validators import (
    console as validators_console,
    display_validation_results,
    validate_environment,
)
from mkapidocs.yaml_utils import YAMLError, console as yaml_console

# Initialize Rich console
console = Console()

# Initialize Typer app
app = typer.Typer(
    name="mkapidocs",
    help="Automated documentation setup tool for Python projects using MkDocs and GitHub Pages",
    add_completion=False,
    rich_markup_mode="rich",
)


def handle_error(error: Exception, user_message: str | None = None) -> None:
    """Handle and display errors in a user-friendly way.

    Args:
        error: The exception that occurred
        user_message: Optional user-friendly explanation
    """
    error_msg = user_message or str(error)
    display_message(error_msg, MessageType.ERROR)
    raise typer.Exit(1)


def _find_git_root(path: Path | None = None) -> Path | None:
    """Find the git root directory by walking up parents.

    Args:
        path: Starting path. Defaults to current working directory.

    Returns:
        Path to git root if found, None otherwise.
    """
    if path is None:
        path = Path.cwd()

    # Resolve to absolute path to handle symlinks/relative paths correctly
    path = path.resolve()

    # Check current directory and all parents
    for parent in [path, *path.parents]:
        if (parent / ".git").exists():
            return parent

    return None


def _validate_provider(provider: str | None) -> CIProvider | None:
    """Validate and convert provider string to CIProvider enum.

    Args:
        provider: Provider string from CLI argument.

    Returns:
        CIProvider enum or None if provider is None.

    Raises:
        typer.Exit: If provider string is invalid.
    """
    if not provider:
        return None

    match provider.lower():
        case "github":
            return CIProvider.GITHUB
        case "gitlab":
            return CIProvider.GITLAB
        case _:
            display_message(
                f"Invalid provider '{provider}'. Must be 'github' or 'gitlab'.",
                MessageType.ERROR,
                title="Invalid Provider",
            )
            raise typer.Exit(1)


@app.command()
def version() -> None:
    """Show version information."""
    display_message(
        "[bold cyan]mkapidocs[/bold cyan] version [bold green]1.0.0[/bold green]",
        MessageType.INFO,
        title="Version Information",
    )


@app.command()
def info() -> None:
    """Display package information and installation details."""
    info_text = """
[bold cyan]Package:[/bold cyan] mkapidocs
[bold cyan]Version:[/bold cyan] 1.0.0
[bold cyan]Summary:[/bold cyan] Automated documentation setup tool for Python projects
[bold cyan]License:[/bold cyan] Unlicense
[bold cyan]Python:[/bold cyan] >=3.11
"""
    display_message(info_text.strip(), MessageType.INFO, title="Package Information")


def _configure_logging(quiet: bool) -> None:
    """Configure global logging state.

    Args:
        quiet: Whether to suppress output.
    """
    if quiet:
        console.quiet = True
        generator_console.quiet = True
        validators_console.quiet = True
        yaml_console.quiet = True


def _get_deployment_command(provider: CIProvider) -> str:
    """Get the provider-specific deployment command.

    Args:
        provider: The CI provider.

    Returns:
        The deployment command string.
    """
    base_cmd = "git add mkdocs.yml docs/ pyproject.toml .gitignore"
    if provider == CIProvider.GITHUB:
        return f'{base_cmd} .github/ && git commit -m "docs: setup mkapidocs configuration" && git push'
    return f'{base_cmd} .gitlab/ .gitlab-ci.yml && git commit -m "docs: setup mkapidocs configuration" && git push'


def _generate_success_message(repo_path: Path, provider: CIProvider) -> str:
    """Generate the completion message with next steps.

    Args:
        repo_path: Path to the repository.
        provider: The CI provider.

    Returns:
        The success message string.
    """
    try:
        display_path = repo_path.relative_to(Path.cwd())
        path_str = "." if display_path == Path() else str(display_path)
    except ValueError:
        path_str = str(repo_path)

    deploy_cmd = _get_deployment_command(provider)

    return (
        f"Documentation setup complete for [bold cyan]{repo_path.name}[/bold cyan]\n\n"
        f"Available commands:\n"
        f"  • Preview docs locally: [bold]uv run mkapidocs serve {path_str}[/bold]\n"
        f"  • Build docs: [bold]uv run mkapidocs build {path_str}[/bold]\n"
        f"  • Deploy: [bold]{deploy_cmd}[/bold]"
    )


@app.command()
def setup(
    repo_path: Annotated[
        Path | None,
        typer.Argument(
            help="Path to Python repository to set up documentation for",
            metavar="directory",
            resolve_path=True,
        ),
    ] = None,
    provider: Annotated[
        str | None,
        typer.Option(
            "--provider",
            help="CI/CD provider: 'github' or 'gitlab' (auto-detected if not provided)",
            rich_help_panel="Configuration",
        ),
    ] = None,
    site_url: Annotated[
        str | None,
        typer.Option(
            "--site-url",
            help="Pages URL for documentation site (e.g., https://user.github.io/repo or https://group.pages.gitlab.com/project)",
            rich_help_panel="Configuration",
        ),
    ] = None,
    github_url_base: Annotated[
        str | None,
        typer.Option(
            "--github-url-base",
            help="[deprecated] Use --site-url instead",
            rich_help_panel="Configuration",
            hidden=True,
        ),
    ] = None,
    c_source_dirs: Annotated[
        list[str] | None,
        typer.Option(
            "--c-source-dirs",
            help="Directories containing C/C++ source code (comma-separated, relative to repo root)",
            rich_help_panel="C/C++ Configuration",
        ),
    ] = None,
    quiet: Annotated[
        bool,
        typer.Option(
            "--quiet",
            "-q",
            help="Suppress output (only show errors)",
            rich_help_panel="Configuration",
        ),
    ] = False,
) -> None:
    """Set up MkDocs documentation for a Python repository.

    Args:
        repo_path: Path to the repository
        provider: CI/CD provider ('github' or 'gitlab')
        site_url: Explicit Pages URL (bypasses auto-detection)
        github_url_base: Deprecated, use --site-url instead
        c_source_dirs: Explicit C/C++ source directories (overrides auto-detection)
        quiet: Suppress output (only show errors)
    """
    _configure_logging(quiet)

    # Resolve repo_path
    if repo_path is None:
        repo_path = _find_git_root() or Path()

    # Validate environment before setup
    console.print()
    all_passed, results = validate_environment(
        repo_path, check_mkdocs=False, auto_install_doxygen=True
    )
    display_validation_results(results, title="Pre-Setup Validation")
    console.print()

    if not all_passed:
        display_message(
            "Validation failed - please fix the issues above before continuing.",
            MessageType.ERROR,
            title="Validation Failed",
        )
        raise typer.Exit(1)

    # Parse provider argument
    ci_provider = _validate_provider(provider)

    # Handle deprecated --github-url-base option
    effective_site_url = site_url
    if github_url_base and not site_url:
        effective_site_url = github_url_base
        display_message(
            "--github-url-base is deprecated. Use --site-url instead.",
            MessageType.WARNING,
            title="Deprecated Option",
        )

    try:
        display_message(
            f"Setting up documentation for [bold cyan]{repo_path}[/bold cyan]...",
            MessageType.INFO,
            title="Starting Setup",
        )

        result = setup_documentation(
            repo_path, ci_provider, effective_site_url, c_source_dirs
        )

        # Display completion message only on first run (when mkdocs.yml was created)
        if result.is_first_run:
            msg = _generate_success_message(repo_path, result.provider)
            display_message(msg, MessageType.SUCCESS, title="Setup Complete")

    except typer.Exit:
        # Re-raise typer.Exit to allow proper exit handling
        # (error message already displayed before raising Exit)
        raise
    except FileNotFoundError as e:
        handle_error(e, f"Repository setup failed: {e}")
    except ValueError as e:
        handle_error(e, str(e))
    except TOMLKitError as e:
        handle_error(e, f"Failed to parse pyproject.toml: {e}")
    except YAMLError as e:
        handle_error(e, f"Failed to parse YAML configuration: {e}")
    except httpx.RequestError as e:
        handle_error(e, f"Network request failed (GitLab API): {e}")
    except OSError as e:
        handle_error(e, f"File system error: {e}")


@app.command()
def build(
    repo_path: Annotated[
        Path | None,
        typer.Argument(
            help="Path to Python repository to build documentation for",
            metavar="directory",
            resolve_path=True,
        ),
    ] = None,
    strict: Annotated[
        bool,
        typer.Option(
            "--strict",
            help="Enable strict mode (warnings as errors)",
            rich_help_panel="Build Options",
        ),
    ] = False,
    output_dir: Annotated[
        Path | None,
        typer.Option(
            "--output-dir",
            help="Custom output directory (default: site/)",
            rich_help_panel="Build Options",
        ),
    ] = None,
) -> None:
    """Build documentation using uvx mkdocs with all required plugins.

    This command uses uvx to run mkdocs with all necessary plugins
    in an isolated environment, without requiring mkdocs to be installed
    in the target project.

    Args:
        repo_path: Path to the repository
        strict: Enable strict mode
        output_dir: Custom output directory
    """
    # Resolve repo_path
    if repo_path is None:
        repo_path = _find_git_root() or Path()

    # Validate environment before build
    console.print()
    all_passed, results = validate_environment(
        repo_path, check_mkdocs=True, auto_install_doxygen=True
    )
    display_validation_results(results, title="Pre-Build Validation")
    console.print()

    if not all_passed:
        display_message(
            "Validation failed - please fix the issues above before building.",
            MessageType.ERROR,
            title="Validation Failed",
        )
        raise typer.Exit(1)

    try:
        display_message(
            f"Building documentation for [bold cyan]{repo_path}[/bold cyan]...",
            MessageType.INFO,
            title="Building Documentation",
        )

        exit_code = build_docs(repo_path, strict=strict, output_dir=output_dir)

    except FileNotFoundError as e:
        handle_error(e, str(e))
    except RuntimeError as e:
        handle_error(e, f"Build environment error: {e}")
    except OSError as e:
        handle_error(e, f"File system error: {e}")

    if exit_code == 0:
        output_path = output_dir or (repo_path / "site")
        display_message(
            f"Documentation built successfully in [bold cyan]{output_path}[/bold cyan]",
            MessageType.SUCCESS,
            title="Build Complete",
        )
    else:
        display_message(
            f"Documentation build failed with exit code {exit_code}",
            MessageType.ERROR,
            title="Build Failed",
        )
        raise typer.Exit(exit_code)


@app.command()
def serve(
    repo_path: Annotated[
        Path | None,
        typer.Argument(
            help="Path to Python repository to serve documentation for",
            metavar="directory",
            resolve_path=True,
        ),
    ] = None,
    host: Annotated[
        str,
        typer.Option(
            "--host", help="Server host address", rich_help_panel="Server Options"
        ),
    ] = "127.0.0.1",
    port: Annotated[
        int,
        typer.Option(
            "--port",
            help="Server port",
            min=1,
            max=65535,
            rich_help_panel="Server Options",
        ),
    ] = 8000,
) -> None:
    """Serve documentation with live preview using uvx mkdocs.

    This command uses uvx to run mkdocs serve with all necessary plugins
    in an isolated environment, without requiring mkdocs to be installed
    in the target project.

    Args:
        repo_path: Path to the repository
        host: Server host address
        port: Server port
    """
    # Resolve repo_path
    if repo_path is None:
        repo_path = _find_git_root() or Path()

    # Validate environment before serving
    console.print()
    all_passed, results = validate_environment(
        repo_path, check_mkdocs=True, auto_install_doxygen=True
    )
    display_validation_results(results, title="Pre-Serve Validation")
    console.print()

    if not all_passed:
        display_message(
            "Validation failed - please fix the issues above before serving.",
            MessageType.ERROR,
            title="Validation Failed",
        )
        raise typer.Exit(1)

    try:
        if is_running_in_target_env():
            display_message(
                f"Starting documentation server for [bold cyan]{repo_path}[/bold cyan]...\n"
                + f"Server address: [bold cyan]http://{host}:{port}[/bold cyan]\n"
                + "Press Ctrl+C to stop",
                MessageType.INFO,
                title="Documentation Server",
            )

        exit_code = serve_docs(repo_path, host=host, port=port)

    except FileNotFoundError as e:
        handle_error(e, str(e))
    except RuntimeError as e:
        handle_error(e, f"Server environment error: {e}")
    except OSError as e:
        handle_error(e, f"File system error: {e}")
    except (KeyboardInterrupt, typer.Abort):
        exit_code = 0

    if exit_code == 0:
        if is_running_in_target_env():
            display_message("Server stopped", MessageType.INFO, title="Server Stopped")
    else:
        if is_running_in_target_env():
            display_message(
                f"Server failed with exit code {exit_code}",
                MessageType.ERROR,
                title="Server Failed",
            )
        raise typer.Exit(exit_code)


@app.callback()
def main(
    ctx: typer.Context,
    verbose: Annotated[
        bool, typer.Option("--verbose", "-v", help="Enable verbose output")
    ] = False,
) -> None:
    """Mkapidocs - Automated documentation setup tool."""
    if ctx.invoked_subcommand is None:
        console.print(ctx.get_help())
        raise typer.Exit(0)

    ctx.obj = {"verbose": verbose}


if __name__ == "__main__":
    app()
