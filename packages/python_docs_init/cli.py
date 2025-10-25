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
app = typer.Typer(
    name=_package_name,
    help=_package_description,
    add_completion=False,
    rich_markup_mode="rich",
)


class CLIError(Exception):
    """Base exception for CLI errors."""

    pass


class MessageType(Enum):
    """Message types with associated display styles."""

    ERROR = ("red", "Error")
    SUCCESS = ("green", "Success")
    INFO = ("blue", "Info")
    WARNING = ("yellow", "Warning")


def display_message(
    message: str,
    message_type: MessageType = MessageType.INFO,
    title: str | None = None,
) -> None:
    """Display a formatted message panel.

    Args:
        message: The message text to display
        message_type: Type of message (affects styling)
        title: Optional panel title (defaults to message type)
    """
    color, default_title = message_type.value
    panel_title = title or default_title

    console.print(
        Panel(
            message,
            title=f"[bold {color}]{panel_title}[/bold {color}]",
            border_style=color,
            padding=(1, 2),
        )
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

    info_text = f"""
[bold cyan]Package:[/bold cyan] {pkg_metadata['Name']}
[bold cyan]Version:[/bold cyan] {pkg_metadata['Version']}
[bold cyan]Summary:[/bold cyan] {pkg_metadata['Summary']}
[bold cyan]Author:[/bold cyan] {pkg_metadata.get('Author-Email', 'N/A')}
[bold cyan]License:[/bold cyan] Unlicense
[bold cyan]Python:[/bold cyan] {pkg_metadata.get('Requires-Python', 'N/A')}
"""
    display_message(info_text.strip(), MessageType.INFO, title="Package Information")


@app.callback()
def main(
    ctx: typer.Context,
    verbose: Annotated[
        bool,
        typer.Option("--verbose", "-v", help="Enable verbose output"),
    ] = False,
) -> None:
    """Python Documentation Init - Automated documentation setup tool for Python projects using MkDocs and GitLab Pages"""
    if ctx.invoked_subcommand is None:
        console.print(ctx.get_help())
        raise typer.Exit(0)

    # Store verbose flag in context for use in commands
    ctx.obj = {"verbose": verbose}


if __name__ == "__main__":
    app()
