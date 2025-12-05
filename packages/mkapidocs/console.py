"""Shared Rich console utilities for mkapidocs.

Provides a single Console instance and helper functions for consistent
output formatting across all modules.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from rich.console import Console, RenderableType
from rich.measure import Measurement

if TYPE_CHECKING:
    from rich.panel import Panel
    from rich.table import Table

# Single shared console instance
console = Console()


def get_rendered_width(renderable: RenderableType) -> int:
    """Get actual rendered width of a Rich renderable.

    Measures the natural width needed to display the renderable without
    wrapping, accounting for color codes, Unicode, styling, padding,
    and borders.

    Args:
        renderable: Any Rich renderable (Panel, Table, Text, etc.)

    Returns:
        Width in characters needed to display the renderable.
    """
    temp_console = Console(width=9999)
    measurement = Measurement.get(temp_console, temp_console.options, renderable)
    return int(measurement.maximum)


def print_table(table: Table) -> None:
    """Print a table at its natural content width.

    Sets the table width to fit its content exactly, preventing
    truncation and ensuring consistent display across environments.

    Args:
        table: Rich Table to print.
    """
    table_width = get_rendered_width(table)
    table.width = table_width
    console.print(table, crop=False, overflow="ignore", no_wrap=True, soft_wrap=True)


def print_panel(panel: Panel) -> None:
    """Print a panel at its natural content width.

    Sets the console width to match the panel's content, preventing
    the panel from expanding to fill the terminal.

    Args:
        panel: Rich Panel to print.
    """
    panel_width = get_rendered_width(panel)
    console.width = panel_width
    console.print(panel, crop=False, overflow="ignore", no_wrap=True, soft_wrap=True)
