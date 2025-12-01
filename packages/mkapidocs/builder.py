"""Builder and server logic for mkapidocs."""

from __future__ import annotations

import os
import subprocess
from importlib.resources import files
from pathlib import Path
from shutil import which
from typing import cast

import tomlkit
from rich.console import Console

# Initialize Rich console
console = Console()
MKDOCS_FILE = "mkdocs.yml"
CMD_LIST_TYPE = list[str | Path] | list[str]


def is_mkapidocs_in_target_env(repo_path: Path) -> bool:
    """Check if mkapidocs is installed in the target project's environment.

    Args:
        repo_path: Path to target repository.

    Returns:
        True if mkapidocs is in the target's pyproject.toml dev dependencies.
    """
    pyproject_path = repo_path / "pyproject.toml"
    if not pyproject_path.exists():
        return False

    try:
        with open(pyproject_path, encoding="utf-8") as f:
            config = tomlkit.load(f)

        dependency_groups = config.get("dependency-groups")
        if not isinstance(dependency_groups, dict):
            return False
        # Cast to known type to avoid unknown type propagation
        typed_dep_groups = cast(dict[str, object], dependency_groups)
        dev_deps_raw = typed_dep_groups.get("dev")
        if not isinstance(dev_deps_raw, list):
            return False
        # Cast to known type and filter to strings
        typed_list = cast(list[object], dev_deps_raw)
        dev_deps: list[str] = [str(dep) for dep in typed_list if isinstance(dep, str)]
        return any(dep.startswith("mkapidocs") or "mkapidocs" in dep for dep in dev_deps)
    except Exception:
        return False


def is_running_in_target_env() -> bool:
    """Check if mkapidocs is being run from within a target project's environment.

    This prevents infinite recursion when mkapidocs calls itself via uv run.

    Returns:
        True if we're already running in a project environment (not standalone).
    """
    # Check if MKAPIDOCS_INTERNAL_CALL environment variable is set
    return os.environ.get("MKAPIDOCS_INTERNAL_CALL") == "1"


def _run_subprocess(cmd: list[str | Path], cwd: Path, env: dict[str, str]) -> int:
    """Run a subprocess and return its exit code.

    Args:
        cmd: Command and arguments to run.
        cwd: Working directory.
        env: Environment variables.

    Returns:
        Exit code from the subprocess.
    """
    result = subprocess.run(cmd, cwd=cwd, env=env, capture_output=False, check=False)
    return result.returncode


def _run_subprocess_with_interrupt(cmd: list[str | Path], cwd: Path, env: dict[str, str]) -> int:
    """Run a subprocess with KeyboardInterrupt handling.

    Args:
        cmd: Command and arguments to run.
        cwd: Working directory.
        env: Environment variables.

    Returns:
        Exit code from the subprocess, or 0 if interrupted.
    """
    try:
        result = subprocess.run(cmd, cwd=cwd, env=env, capture_output=False, check=False)
    except KeyboardInterrupt:
        return 0
    else:
        return result.returncode


def _get_mkdocs_plugins() -> list[str]:
    """Get the list of mkdocs plugins to install with uvx.

    Returns:
        List of plugin package names.
    """
    return [
        "mkdocs",
        "mkdocs-material",
        "mkdocs-gen-files",
        "mkdocs-literate-nav",
        "mkdocstrings[python]",
        "mkdocs-typer2",
        "mkdoxy",
        "mkdocs-mermaid2-plugin",
        "termynal",
    ]


def build_docs(target_path: Path, strict: bool = False, output_dir: Path | None = None) -> int:
    """Build documentation using target project's environment or uvx fallback.

    If mkapidocs is installed in the target project's environment, uses that
    environment via 'uv run mkapidocs build'. Otherwise falls back to uvx
    with standalone plugin installation.

    Args:
        target_path: Path to target project containing mkdocs.yml.
        strict: Enable strict mode.
        output_dir: Custom output directory.

    Returns:
        Exit code from mkdocs build.

    Raises:
        FileNotFoundError: If mkdocs.yml not found.
    """
    mkdocs_yml = target_path / MKDOCS_FILE
    if not mkdocs_yml.exists():
        msg = f"{MKDOCS_FILE} not found in {target_path}"
        raise FileNotFoundError(msg)

    # Generate gen_ref_pages.py just-in-time for this build
    gen_ref_script = target_path / "docs" / "generated" / "gen_ref_pages.py"
    gen_ref_script.parent.mkdir(parents=True, exist_ok=True)

    # Read script content from resources using modern files() API
    script_content = files("mkapidocs.resources").joinpath("gen_ref_pages.py").read_text()

    _ = gen_ref_script.write_text(script_content)

    # Get source paths and add to PYTHONPATH
    env = os.environ.copy()

    # Check if we should use target project's environment
    if is_mkapidocs_in_target_env(target_path) and not is_running_in_target_env():
        return _build_with_target_env(target_path, env, strict, output_dir)

    # If running internally (already in target env), call mkdocs directly
    if is_running_in_target_env():
        result = _build_with_mkdocs_direct(target_path, env, strict, output_dir)
        if result is not None:
            return result

    # Fallback to uvx with standalone plugin installation
    return _build_with_uvx(target_path, env, strict, output_dir)


def _build_with_target_env(target_path: Path, env: dict[str, str], strict: bool, output_dir: Path | None) -> int:
    """Build docs using target project's environment via uv run.

    Args:
        target_path: Path to target project.
        env: Environment variables.
        strict: Enable strict mode.
        output_dir: Custom output directory.

    Returns:
        Exit code from build.

    Raises:
        FileNotFoundError: If uv command not found.
    """
    console.print("[blue]:rocket: Using target project's environment for build[/blue]")

    if not (uv_cmd := which("uv")):
        msg = "uv command not found. Please install uv."
        raise FileNotFoundError(msg)

    env["MKAPIDOCS_INTERNAL_CALL"] = "1"
    cmd: CMD_LIST_TYPE = [uv_cmd, "run", "mkapidocs", "build", "."]
    if strict:
        cmd.append("--strict")
    if output_dir:
        cmd.extend(["--output-dir", str(output_dir)])

    return _run_subprocess(cmd, target_path, env)


def _build_with_mkdocs_direct(
    target_path: Path, env: dict[str, str], strict: bool, output_dir: Path | None
) -> int | None:
    """Build docs using mkdocs directly.

    Args:
        target_path: Path to target project.
        env: Environment variables.
        strict: Enable strict mode.
        output_dir: Custom output directory.

    Returns:
        Exit code from build, or None if mkdocs not found.
    """
    console.print("[blue]:zap: Running mkdocs directly (already in target environment)[/blue]")
    if mkdocs_cmd := which("mkdocs"):
        cmd: CMD_LIST_TYPE = [mkdocs_cmd, "build"]
        if strict:
            cmd.append("--strict")
        if output_dir:
            cmd.extend(["--site-dir", str(output_dir)])
        return _run_subprocess(cmd, target_path, env)
    return None


def _build_with_uvx(target_path: Path, env: dict[str, str], strict: bool, output_dir: Path | None) -> int:
    """Build docs using uvx with standalone plugin installation.

    Args:
        target_path: Path to target project.
        env: Environment variables.
        strict: Enable strict mode.
        output_dir: Custom output directory.

    Returns:
        Exit code from build.

    Raises:
        FileNotFoundError: If uvx command not found.
    """
    console.print("[blue]:wrench: Using standalone uvx environment for build[/blue]")

    if not (uvx_cmd := which("uvx")):
        msg = "uvx command not found. Please install uv."
        raise FileNotFoundError(msg)

    cmd: CMD_LIST_TYPE = [uvx_cmd]
    for plugin in _get_mkdocs_plugins():
        cmd.extend(["--with", plugin])
    cmd.extend(["--from", "mkdocs", "mkdocs", "build"])

    if strict:
        cmd.append("--strict")
    if output_dir:
        cmd.extend(["--site-dir", str(output_dir)])

    return _run_subprocess(cmd, target_path, env)


def serve_docs(target_path: Path, host: str = "127.0.0.1", port: int = 8000) -> int:
    """Serve documentation using target project's environment or uvx fallback.

    If mkapidocs is installed in the target project's environment, uses that
    environment via 'uv run mkapidocs serve'. Otherwise falls back to uvx
    with standalone plugin installation.

    Args:
        target_path: Path to target project containing mkdocs.yml.
        host: Server host address.
        port: Server port.

    Returns:
        Exit code from mkdocs serve.

    Raises:
        FileNotFoundError: If mkdocs.yml not found.
    """
    mkdocs_yml = target_path / MKDOCS_FILE
    if not mkdocs_yml.exists():
        msg = f"{MKDOCS_FILE} not found in {target_path}"
        raise FileNotFoundError(msg)

    # Generate gen_ref_pages.py just-in-time for serving
    gen_ref_script = target_path / "docs" / "generated" / "gen_ref_pages.py"
    gen_ref_script.parent.mkdir(parents=True, exist_ok=True)

    # Read script content from resources using modern files() API
    script_content = files("mkapidocs.resources").joinpath("gen_ref_pages.py").read_text()

    _ = gen_ref_script.write_text(script_content)

    # Get source paths and add to PYTHONPATH
    env = os.environ.copy()

    # Check if we should use target project's environment
    if is_mkapidocs_in_target_env(target_path) and not is_running_in_target_env():
        return _serve_with_target_env(target_path, env, host, port)

    # If running internally (already in target env), call mkdocs directly
    if is_running_in_target_env():
        result = _serve_with_mkdocs_direct(target_path, env, host, port)
        if result is not None:
            return result

    # Fallback to uvx with standalone plugin installation
    return _serve_with_uvx(target_path, env, host, port)


def _serve_with_target_env(target_path: Path, env: dict[str, str], host: str, port: int) -> int:
    """Serve docs using target project's environment via uv run.

    Args:
        target_path: Path to target project.
        env: Environment variables.
        host: Server host address.
        port: Server port.

    Returns:
        Exit code from serve.

    Raises:
        FileNotFoundError: If uv command not found.
    """
    console.print("[blue]:rocket: Using target project's environment for serve[/blue]")

    if not (uv_cmd := which("uv")):
        msg = "uv command not found. Please install uv."
        raise FileNotFoundError(msg)

    env["MKAPIDOCS_INTERNAL_CALL"] = "1"
    cmd: CMD_LIST_TYPE = [uv_cmd, "run", "mkapidocs", "serve", ".", "--host", host, "--port", str(port)]

    return _run_subprocess_with_interrupt(cmd, target_path, env)


def _serve_with_mkdocs_direct(target_path: Path, env: dict[str, str], host: str, port: int) -> int | None:
    """Serve docs using mkdocs directly.

    Args:
        target_path: Path to target project.
        env: Environment variables.
        host: Server host address.
        port: Server port.

    Returns:
        Exit code from serve, or None if mkdocs not found.
    """
    console.print("[blue]:zap: Running mkdocs directly (already in target environment)[/blue]")
    if mkdocs_cmd := which("mkdocs"):
        cmd: list[str | Path] = [mkdocs_cmd, "serve", "--dev-addr", f"{host}:{port}"]
        return _run_subprocess_with_interrupt(cmd, target_path, env)
    return None


def _serve_with_uvx(target_path: Path, env: dict[str, str], host: str, port: int) -> int:
    """Serve docs using uvx with standalone plugin installation.

    Args:
        target_path: Path to target project.
        env: Environment variables.
        host: Server host address.
        port: Server port.

    Returns:
        Exit code from serve.

    Raises:
        FileNotFoundError: If uvx command not found.
    """
    console.print("[blue]:wrench: Using standalone uvx environment for serve[/blue]")

    if not (uvx_cmd := which("uvx")):
        msg = "uvx command not found. Please install uv."
        raise FileNotFoundError(msg)

    cmd: CMD_LIST_TYPE = [uvx_cmd]
    for plugin in _get_mkdocs_plugins():
        cmd.extend(["--with", plugin])
    cmd.extend(["--from", "mkdocs", "mkdocs", "serve", "--dev-addr", f"{host}:{port}"])

    return _run_subprocess_with_interrupt(cmd, target_path, env)
