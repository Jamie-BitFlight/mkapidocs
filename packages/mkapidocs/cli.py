"""mkapidocs - Automated documentation setup for Python projects.

This script sets up MkDocs documentation for Python repositories with auto-detection
of features like C/C++ code and Typer CLI interfaces.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from mkapidocs.builder import build_docs, serve_docs
from mkapidocs.generator import display_message, setup_documentation
from mkapidocs.models import CIProvider, MessageType
from mkapidocs.validators import display_validation_results, validate_environment

# Initialize Rich console
console = Console()

# Initialize Typer app
app = typer.Typer(
    name="python-docs-init",
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
[bold cyan]Package:[/bold cyan] python-docs-init
[bold cyan]Version:[/bold cyan] 1.0.0
[bold cyan]Summary:[/bold cyan] Automated documentation setup tool for Python projects
[bold cyan]License:[/bold cyan] Unlicense
[bold cyan]Python:[/bold cyan] >=3.11
"""
    display_message(info_text.strip(), MessageType.INFO, title="Package Information")


@app.command()
def setup(
    repo_path: Annotated[
        Path, typer.Argument(help="Path to Python repository to set up documentation for", resolve_path=True)
    ],
    provider: Annotated[
        str | None,
        typer.Option(
            "--provider",
            help="CI/CD provider: 'github' or 'gitlab' (auto-detected if not provided)",
            rich_help_panel="Configuration",
        ),
    ] = None,
    github_url_base: Annotated[
        str | None,
        typer.Option(
            "--github-url-base",
            help="Base URL for GitHub Pages (auto-detected from git remote if not provided)",
            rich_help_panel="Configuration",
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
) -> None:
    """Set up MkDocs documentation for a Python repository.

    Args:
        repo_path: Path to the repository
        provider: CI/CD provider ('github' or 'gitlab')
        github_url_base: Base URL for GitHub Pages (deprecated, use --provider)
        c_source_dirs: Explicit C/C++ source directories (overrides auto-detection)
    """
    try:
        # Validate environment before setup
        console.print()
        all_passed, results = validate_environment(repo_path, check_mkdocs=False, auto_install_doxygen=True)
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
        ci_provider: CIProvider | None = None
        if provider:
            provider_lower = provider.lower()
            if provider_lower == "github":
                ci_provider = CIProvider.GITHUB
            elif provider_lower == "gitlab":
                ci_provider = CIProvider.GITLAB
            else:
                display_message(
                    f"Invalid provider '{provider}'. Must be 'github' or 'gitlab'.",
                    MessageType.ERROR,
                    title="Invalid Provider",
                )
                raise typer.Exit(1)

        display_message(
            f"Setting up documentation for [bold cyan]{repo_path}[/bold cyan]...",
            MessageType.INFO,
            title="Starting Setup",
        )

        ci_provider = setup_documentation(repo_path, ci_provider, github_url_base, c_source_dirs)

        # Display completion message with provider-specific instructions
        if ci_provider == CIProvider.GITHUB:
            next_steps_msg = (
                f"Documentation setup complete for [bold cyan]{repo_path.name}[/bold cyan]\n\n"
                f"Next steps:\n"
                f"  1. Preview docs locally: [bold]uv run mkapidocs serve {repo_path}[/bold]\n"
                f"  2. Build docs: [bold]uv run mkapidocs build {repo_path}[/bold]\n"
                f"  3. Commit and push changes to enable GitHub Pages"
            )
        else:  # ci_provider == CIProvider.GITLAB
            next_steps_msg = (
                f"Documentation setup complete for [bold cyan]{repo_path.name}[/bold cyan]\n\n"
                f"Next steps:\n"
                f"  1. Preview docs locally: [bold]uv run mkapidocs serve {repo_path}[/bold]\n"
                f"  2. Build docs: [bold]uv run mkapidocs build {repo_path}[/bold]\n"
                f"  3. Commit and push changes to enable GitLab Pages"
            )

        display_message(next_steps_msg, MessageType.SUCCESS, title="Setup Complete")

    except typer.Exit:
        # Re-raise typer.Exit to allow proper exit handling
        # (error message already displayed before raising Exit)
        raise
    except FileNotFoundError as e:
        handle_error(e, f"Repository setup failed: {e}")
    except ValueError as e:
        handle_error(e, str(e))
    except Exception as e:
        handle_error(e, f"An unexpected error occurred during setup: {e}")


@app.command()
def build(
    repo_path: Annotated[
        Path, typer.Argument(help="Path to Python repository to build documentation for", resolve_path=True)
    ],
    strict: Annotated[
        bool, typer.Option("--strict", help="Enable strict mode (warnings as errors)", rich_help_panel="Build Options")
    ] = False,
    output_dir: Annotated[
        Path | None,
        typer.Option("--output-dir", help="Custom output directory (default: site/)", rich_help_panel="Build Options"),
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
    try:
        # Validate environment before build
        console.print()
        all_passed, results = validate_environment(repo_path, check_mkdocs=True, auto_install_doxygen=True)
        display_validation_results(results, title="Pre-Build Validation")
        console.print()

        if not all_passed:
            display_message(
                "Validation failed - please fix the issues above before building.",
                MessageType.ERROR,
                title="Validation Failed",
            )
            raise typer.Exit(1)

        display_message(
            f"Building documentation for [bold cyan]{repo_path}[/bold cyan]...",
            MessageType.INFO,
            title="Building Documentation",
        )

        exit_code = build_docs(repo_path, strict=strict, output_dir=output_dir)

        if exit_code == 0:
            output_path = output_dir or (repo_path / "site")
            display_message(
                f"Documentation built successfully in [bold cyan]{output_path}[/bold cyan]",
                MessageType.SUCCESS,
                title="Build Complete",
            )
        else:
            display_message(
                f"Documentation build failed with exit code {exit_code}", MessageType.ERROR, title="Build Failed"
            )
            raise typer.Exit(exit_code)

    except FileNotFoundError as e:
        handle_error(e, str(e))
        raise typer.Exit(1) from None
    except Exception as e:
        handle_error(e, f"Build failed: {e}")
        raise typer.Exit(1) from None


@app.command()
def serve(
    repo_path: Annotated[
        Path, typer.Argument(help="Path to Python repository to serve documentation for", resolve_path=True)
    ],
    host: Annotated[
        str, typer.Option("--host", help="Server host address", rich_help_panel="Server Options")
    ] = "127.0.0.1",
    port: Annotated[
        int, typer.Option("--port", help="Server port", min=1, max=65535, rich_help_panel="Server Options")
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
    try:
        # Validate environment before serving
        console.print()
        all_passed, results = validate_environment(repo_path, check_mkdocs=True, auto_install_doxygen=True)
        display_validation_results(results, title="Pre-Serve Validation")
        console.print()

        if not all_passed:
            display_message(
                "Validation failed - please fix the issues above before serving.",
                MessageType.ERROR,
                title="Validation Failed",
            )
            raise typer.Exit(1)

        display_message(
            f"Starting documentation server for [bold cyan]{repo_path}[/bold cyan]...\n"
            + f"Server address: [bold cyan]http://{host}:{port}[/bold cyan]\n"
            + "Press Ctrl+C to stop",
            MessageType.INFO,
            title="Documentation Server",
        )

        exit_code = serve_docs(repo_path, host=host, port=port)

        if exit_code == 0:
            display_message("Server stopped", MessageType.INFO, title="Server Stopped")
        else:
            display_message(f"Server failed with exit code {exit_code}", MessageType.ERROR, title="Server Failed")
            raise typer.Exit(exit_code)

    except FileNotFoundError as e:
        handle_error(e, str(e))
        raise typer.Exit(1) from None
    except Exception as e:
        handle_error(e, f"Server failed: {e}")
        raise typer.Exit(1) from None


@app.callback()
def main(
    ctx: typer.Context, verbose: Annotated[bool, typer.Option("--verbose", "-v", help="Enable verbose output")] = False
) -> None:
    """Mkapidocs - Automated documentation setup tool."""
    if ctx.invoked_subcommand is None:
        console.print(ctx.get_help())
        raise typer.Exit(0)

    ctx.obj = {"verbose": verbose}


if __name__ == "__main__":
    app()
