"""mkapidocs - Automated documentation setup for Python projects.

This package provides tools for setting up MkDocs documentation with automatic
feature detection for Python projects.
"""

from __future__ import annotations

__version__ = "0.1.1"

# Export main CLI app for entry point
from mkapidocs.cli import app

__all__ = ["__version__", "app"]
