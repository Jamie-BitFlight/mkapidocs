"""Compute the version number and store it in the `__version__` variable.

Based on <https://github.com/maresb/hatch-vcs-footgun-example>.
"""

from __future__ import annotations

import os


def _get_hatch_version() -> str | None:
    """Compute the most up-to-date version number in a development environment.

    Returns `None` if Hatchling is not installed, e.g. in a production environment.

    For more details, see <https://github.com/maresb/hatch-vcs-footgun-example/>.

    Returns:
        The version string from hatchling, or None if hatchling is not installed.
    """
    try:
        # hatchling is an optional development dependency without type stubs
        from hatchling.metadata.core import (  # pyright: ignore[reportMissingImports]
            ProjectMetadata,  # pyright: ignore[reportUnknownVariableType]
        )
        from hatchling.plugin.manager import (  # pyright: ignore[reportMissingImports]
            PluginManager,  # pyright: ignore[reportUnknownVariableType]
        )
        from hatchling.utils.fs import locate_file  # pyright: ignore[reportMissingImports,reportUnknownVariableType]
    except ImportError:
        # Hatchling is not installed, so probably we are not in
        # a development environment.
        return None

    # All following lines interact with untyped hatchling library
    pyproject_toml = locate_file(__file__, "pyproject.toml")  # pyright: ignore[reportUnknownVariableType]
    if pyproject_toml is None:
        raise RuntimeError("pyproject.toml not found although hatchling is installed")
    root = os.path.dirname(pyproject_toml)  # pyright: ignore[reportUnknownVariableType,reportUnknownArgumentType]
    metadata = ProjectMetadata(root=root, plugin_manager=PluginManager())  # pyright: ignore[reportUnknownVariableType]
    # Version can be either statically set in pyproject.toml or computed dynamically:
    version_value = metadata.core.version or metadata.hatch.version.cached  # pyright: ignore[reportUnknownVariableType,reportUnknownMemberType]
    return str(version_value)  # pyright: ignore[reportUnknownArgumentType]


def _get_importlib_metadata_version() -> str:
    """Compute the version number using importlib.metadata.

    This is the official Pythonic way to get the version number of an installed
    package. However, it is only updated when a package is installed. Thus, if a
    package is installed in editable mode, and a different version is checked out,
    then the version number will not be updated.

    Returns:
        The version string from importlib.metadata.
    """
    from importlib.metadata import version

    __version__ = version(__package__ or __name__)
    return __version__


__version__ = _get_hatch_version() or _get_importlib_metadata_version()
