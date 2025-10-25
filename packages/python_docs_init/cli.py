"""CLI interface for Python Documentation Init.

This module provides a comprehensive command-line interface for Automated documentation setup tool for Python projects using MkDocs and GitLab Pages.
"""

from enum import Enum
from importlib import metadata
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.panel import Panel

# Initialize Rich console
console = Console()

# Get package metadata dynamically
_package_metadata = metadata.metadata(__package__ or __name__)
_package_name = _package_metadata["Name"]
_package_description = _package_metadata["Summary"]

# Initialize Typer app with rich help
app = typer.Typer(name=_package_name, help=_package_description, add_completion=False, rich_markup_mode="rich")


class CLIError(Exception):
    """Base exception for CLI errors."""

    pass


class MessageType(Enum):
    """Message types with associated display styles."""

    ERROR = ("red", "Error")
    SUCCESS = ("green", "Success")
    INFO = ("blue", "Info")
    WARNING = ("yellow", "Warning")


def display_message(message: str, message_type: MessageType = MessageType.INFO, title: str | None = None) -> None:
    """Display a formatted message panel.

    Args:
        message: The message text to display
        message_type: Type of message (affects styling)
        title: Optional panel title (defaults to message type)
    """
    color, default_title = message_type.value
    panel_title = title or default_title

    console.print(
        Panel(message, title=f"[bold {color}]{panel_title}[/bold {color}]", border_style=color, padding=(1, 2))
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
    version_str = metadata.version("python_docs_init")
    display_message(
        f"[bold cyan]Python Documentation Init[/bold cyan] version [bold green]{version_str}[/bold green]",
        MessageType.INFO,
        title="Version Information",
    )


@app.command()
def info() -> None:
    """Display package information and installation details."""
    pkg_metadata = metadata.metadata("python_docs_init")

    # Handle optional metadata fields with try/except
    try:
        author_email = pkg_metadata["Author-Email"]
    except KeyError:
        author_email = "N/A"

    try:
        requires_python = pkg_metadata["Requires-Python"]
    except KeyError:
        requires_python = "N/A"

    info_text = f"""
[bold cyan]Package:[/bold cyan] {pkg_metadata["Name"]}
[bold cyan]Version:[/bold cyan] {pkg_metadata["Version"]}
[bold cyan]Summary:[/bold cyan] {pkg_metadata["Summary"]}
[bold cyan]Author:[/bold cyan] {author_email}
[bold cyan]License:[/bold cyan] Unlicense
[bold cyan]Python:[/bold cyan] {requires_python}
"""
    display_message(info_text.strip(), MessageType.INFO, title="Package Information")


@app.command()
def setup(
    repo_path: Annotated[
        Path,
        typer.Argument(
            help="Path to Python repository to set up documentation for",
            exists=True,
            file_okay=False,
            dir_okay=True,
            resolve_path=True,
        ),
    ],
    gitlab_url_base: Annotated[
        str | None,
        typer.Option(
            "--gitlab-url-base",
            help="Base URL for GitLab Pages (auto-detected from git remote if not provided)",
            rich_help_panel="Configuration",
        ),
    ] = None,
) -> None:
    """Set up MkDocs documentation for a Python repository.

    This command will:
    - Detect project features (C/C++ code, Typer CLI)
    - Add documentation dependencies to pyproject.toml
    - Create mkdocs.yml configuration
    - Set up GitLab CI for Pages deployment
    - Generate initial documentation structure

    Args:
        repo_path: Path to the repository
        gitlab_url_base: Base URL for GitLab Pages (auto-detected if not provided)
    """
    try:
        # Import here to avoid circular imports and keep startup fast
        from python_docs_init.setup import setup_documentation

        display_message(
            f"Setting up documentation for [bold cyan]{repo_path}[/bold cyan]...",
            MessageType.INFO,
            title="Starting Setup",
        )

        setup_documentation(repo_path, gitlab_url_base)

        display_message(
            f"Documentation setup complete for [bold cyan]{repo_path.name}[/bold cyan]\n\n"
            f"Next steps:\n"
            f"  1. Install docs dependencies: [bold]uv sync --extra docs[/bold]\n"
            f"  2. Build documentation locally: [bold]mkdocs serve[/bold]\n"
            f"  3. Commit and push changes to enable GitLab Pages",
            MessageType.SUCCESS,
            title="Setup Complete",
        )

    except FileNotFoundError as e:
        handle_error(e, f"Repository setup failed: {e}")
    except ValueError as e:
        handle_error(e, str(e))
    except Exception as e:
        handle_error(e, f"An unexpected error occurred during setup: {e}")


@app.command()
def validate(
    repo_path: Annotated[
        Path,
        typer.Argument(
            help="Path to Python repository to validate documentation for",
            exists=True,
            file_okay=False,
            dir_okay=True,
            resolve_path=True,
        ),
    ],
) -> None:
    """Validate documentation setup for a Python repository.

    This command checks that all required documentation files and configuration
    are present and properly configured.

    Args:
        repo_path: Path to the repository
    """
    display_message(
        f"Validation for [bold cyan]{repo_path}[/bold cyan] is not yet implemented.\n\n"
        f"This feature will check:\n"
        f"  - mkdocs.yml configuration\n"
        f"  - Documentation dependencies in pyproject.toml\n"
        f"  - GitLab CI configuration\n"
        f"  - Documentation file structure",
        MessageType.WARNING,
        title="Not Implemented",
    )


@app.callback()
def main(
    ctx: typer.Context, verbose: Annotated[bool, typer.Option("--verbose", "-v", help="Enable verbose output")] = False
) -> None:
    """Python Documentation Init - Automated documentation setup tool for Python projects using MkDocs and GitLab Pages"""
    if ctx.invoked_subcommand is None:
        console.print(ctx.get_help())
        raise typer.Exit(0)

    # Store verbose flag in context for use in commands
    ctx.obj = {"verbose": verbose}


if __name__ == "__main__":
    app()
