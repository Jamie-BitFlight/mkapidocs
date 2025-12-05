"""Project detection utilities for mkapidocs.

This module contains functions for detecting project features and reading
project configuration. It is separate from generator.py to avoid circular
imports with validators.py.
"""

from __future__ import annotations

import os
import subprocess
from contextlib import suppress
from pathlib import Path
from shutil import which

import tomlkit

from mkapidocs.console import console
from mkapidocs.models import PyprojectConfig


def read_pyproject(repo_path: Path) -> PyprojectConfig:
    """Read and parse pyproject.toml into typed configuration.

    Args:
        repo_path: Path to repository.

    Returns:
        Parsed and validated pyproject.toml configuration.

    Raises:
        FileNotFoundError: If pyproject.toml does not exist.
    """
    pyproject_path = repo_path / "pyproject.toml"
    if not pyproject_path.exists():
        raise FileNotFoundError(f"pyproject.toml not found in {repo_path}")

    with Path(pyproject_path).open(encoding="utf-8") as f:
        raw_data = tomlkit.load(f)

    return PyprojectConfig.from_dict(raw_data)


def _contains_c_files(dir_path: Path, c_extensions: set[str]) -> bool:
    """Check if directory contains any C/C++ source files.

    Args:
        dir_path: Directory path to check.
        c_extensions: Set of file extensions to check (.c, .h, .cpp, etc.).

    Returns:
        True if directory contains at least one file with a C/C++ extension.
    """
    return any(file_path.suffix in c_extensions for file_path in dir_path.rglob("*"))


def _detect_c_code_from_explicit(
    repo_path: Path, explicit_dirs: list[str], c_extensions: set[str]
) -> list[Path]:
    """Detect C code from explicit CLI arguments.

    Args:
        repo_path: Path to repository.
        explicit_dirs: List of explicit directories.
        c_extensions: Set of C extensions.

    Returns:
        List of detected directories.
    """
    found_dirs: list[Path] = []
    for dir_str in explicit_dirs:
        dir_path = (repo_path / dir_str).resolve()
        if (
            dir_path.exists()
            and dir_path.is_dir()
            and _contains_c_files(dir_path, c_extensions)
        ):
            found_dirs.append(dir_path)
    return found_dirs


def _detect_c_code_from_env(
    repo_path: Path, env_dirs: str, c_extensions: set[str]
) -> list[Path]:
    """Detect C code from environment variable.

    Args:
        repo_path: Path to repository.
        env_dirs: Environment variable value.
        c_extensions: Set of C extensions.

    Returns:
        List of detected directories.
    """
    found_dirs: list[Path] = []
    for dir_str in env_dirs.split(":"):
        dir_path = (repo_path / dir_str.strip()).resolve()
        if (
            dir_path.exists()
            and dir_path.is_dir()
            and _contains_c_files(dir_path, c_extensions)
        ):
            found_dirs.append(dir_path)
    return found_dirs


def _detect_c_code_from_config(
    repo_path: Path, pyproject: PyprojectConfig, c_extensions: set[str]
) -> list[Path]:
    """Detect C code from pypis_delivery_service config.

    Args:
        repo_path: Path to repository.
        pyproject: Pyproject configuration.
        c_extensions: Set of C extensions.

    Returns:
        List of detected directories.
    """
    cmake_source_dir = pyproject.cmake_source_dir
    if not cmake_source_dir:
        return []

    dir_path = (repo_path / cmake_source_dir).resolve()
    if not dir_path.exists():
        console.print(
            f"[yellow]Warning: pypis_delivery_service cmake_source_dir '{cmake_source_dir}' "
            + "does not exist, falling back to auto-detection[/yellow]"
        )
    elif not dir_path.is_dir():
        console.print(
            f"[yellow]Warning: pypis_delivery_service cmake_source_dir '{cmake_source_dir}' "
            + "is not a directory, falling back to auto-detection[/yellow]"
        )
    elif not _contains_c_files(dir_path, c_extensions):
        console.print(
            f"[yellow]Warning: pypis_delivery_service cmake_source_dir '{cmake_source_dir}' "
            + "contains no C/C++ files, falling back to auto-detection[/yellow]"
        )
    else:
        # Valid directory with C files
        return [dir_path]
    return []


def _detect_c_code_from_git(repo_path: Path, c_extensions: set[str]) -> list[Path]:
    """Detect C code via git ls-files.

    Args:
        repo_path: Path to repository.
        c_extensions: Set of C extensions.

    Returns:
        List of detected directories.
    """
    if not (git_cmd := which("git")):
        return []

    with suppress(
        subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError
    ):
        result = subprocess.run(
            [git_cmd, "ls-files"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )
        # Find unique directories containing C/C++ files
        c_dirs: set[Path] = set()
        for line in result.stdout.strip().split("\n"):
            if not line:
                continue
            file_path = Path(line)
            if file_path.suffix in c_extensions and len(file_path.parts) > 1:
                # Get the top-level directory of this file
                c_dirs.add(repo_path / file_path.parts[0])

        if c_dirs:
            # Verify directories exist and contain C/C++ files
            found_dirs: list[Path] = [
                dir_path
                for dir_path in sorted(c_dirs)
                if dir_path.exists()
                and dir_path.is_dir()
                and _contains_c_files(dir_path, c_extensions)
            ]
            return found_dirs
    return []


def detect_c_code(
    repo_path: Path,
    explicit_dirs: list[str] | None = None,
    pyproject: PyprojectConfig | None = None,
) -> list[Path]:
    """Detect directories containing C/C++ source code.

    Detection priority (first match wins):
    1. explicit_dirs parameter (from CLI --c-source-dirs)
    2. MKAPIDOCS_C_SOURCE_DIRS environment variable (colon-separated paths)
    3. [tool.pypis_delivery_service] cmake_source_dir in pyproject.toml
    4. Auto-detect via git ls-files for C/C++ extensions
    5. Fallback to source/ directory if it exists

    Args:
        repo_path: Path to repository root.
        explicit_dirs: Optional list of directory paths from CLI option.
        pyproject: Optional parsed pyproject.toml for reading config.

    Returns:
        List of absolute Path objects to directories containing C/C++ code.
        Empty list if no C/C++ code found.
    """
    c_extensions = {".c", ".h", ".cpp", ".hpp", ".cc", ".hh"}

    # Priority 1: Explicit CLI option
    if explicit_dirs:
        found_dirs = _detect_c_code_from_explicit(
            repo_path, explicit_dirs, c_extensions
        )
        if found_dirs:
            return found_dirs

    # Priority 2: Environment variable
    if env_dirs := os.getenv("MKAPIDOCS_C_SOURCE_DIRS"):
        found_dirs = _detect_c_code_from_env(repo_path, env_dirs, c_extensions)
        if found_dirs:
            return found_dirs

    # Priority 3: pypis_delivery_service config
    if pyproject:
        found_dirs = _detect_c_code_from_config(repo_path, pyproject, c_extensions)
        if found_dirs:
            return found_dirs

    # Priority 4: Auto-detect via git ls-files
    if found_dirs := _detect_c_code_from_git(repo_path, c_extensions):
        return found_dirs

    # Priority 5: Fallback to source/ directory
    source_dir = repo_path / "source"
    if (
        source_dir.exists()
        and source_dir.is_dir()
        and _contains_c_files(source_dir, c_extensions)
    ):
        return [source_dir.resolve()]

    return []


def detect_typer_dependency(pyproject: PyprojectConfig) -> bool:
    """Detect if project depends on Typer.

    Args:
        pyproject: Parsed pyproject.toml.

    Returns:
        True if typer found in dependencies.
    """
    dependencies = pyproject.project.dependencies
    return any(dep.strip().lower().startswith("typer") for dep in dependencies)
