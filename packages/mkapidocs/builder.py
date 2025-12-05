"""Builder and server logic for mkapidocs."""

from __future__ import annotations

import os
import signal
import socket
import subprocess
import time
from contextlib import contextmanager
from pathlib import Path
from shutil import which
from typing import TYPE_CHECKING

from rich.console import Console

if TYPE_CHECKING:
    from collections.abc import Generator
    from types import FrameType

# Initialize Rich console
console = Console()
MKDOCS_FILE = "mkdocs.yml"
CMD_LIST_TYPE = list[str | Path]

# Type alias for signal handlers
SignalHandler = signal.Handlers | None


def is_mkapidocs_in_target_env(repo_path: Path) -> bool:
    """Check if mkapidocs is installed in the target project's environment.

    Args:
        repo_path: Path to target repository.

    Returns:
        True if mkapidocs is installed in the target environment.
    """
    if not (uv_cmd := which("uv")):
        return False

    try:
        # Check if installed using uv pip freeze (more robust/efficient than show)
        result = subprocess.run(
            [uv_cmd, "pip", "freeze"],
            cwd=repo_path,
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError:
        return False
    else:
        return "mkapidocs" in result.stdout


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


@contextmanager
def _signal_handler(process: subprocess.Popen[bytes]) -> Generator[None, None, None]:
    """Context manager for graceful subprocess signal handling.

    Intercepts SIGINT/SIGTERM and forwards SIGINT to the child process,
    allowing it to perform graceful shutdown (e.g., mkdocs serve cleanup).

    Args:
        process: The subprocess to manage.

    Yields:
        None
    """

    def handler(signum: int, _frame: FrameType | None) -> None:
        # Only print in the inner process (target env) to avoid duplicate messages
        # when running via 'uv run' (which creates an outer and inner process).
        if is_running_in_target_env():
            sig_name = signal.Signals(signum).name
            console.print(f"[yellow]Received {sig_name}, stopping server...[/yellow]")

        # If the process is already dead, just return
        if process.poll() is not None:
            return

        # Give the child process a chance to handle the signal from the OS (process group)
        try:
            process.wait(timeout=0.2)
        except subprocess.TimeoutExpired:
            pass
        else:
            return

        # Send SIGINT to allow child process (e.g., mkdocs serve) to handle
        # KeyboardInterrupt and perform graceful shutdown
        process.send_signal(signal.SIGINT)
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            if is_running_in_target_env():
                console.print("[red]Process did not stop, killing...[/red]")
            process.kill()

    original_sigint = signal.signal(signal.SIGINT, handler)
    original_sigterm = signal.signal(signal.SIGTERM, handler)

    try:
        yield
    finally:
        signal.signal(signal.SIGINT, original_sigint)
        signal.signal(signal.SIGTERM, original_sigterm)


def _is_port_in_use(host: str, port: int) -> bool:
    """Check if a port is currently in use.

    Args:
        host: Host address to check.
        port: Port number to check.

    Returns:
        True if port is in use, False otherwise.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(1)
        result = sock.connect_ex((host, port))
        return result == 0


def _kill_process_on_port(port: int) -> bool:
    """Kill any process using the specified port.

    Args:
        port: Port number to free up.

    Returns:
        True if a process was killed, False if port was free.
    """
    try:
        # Use lsof to find process on port
        if not (lsof_cmd := which("lsof")):
            return False

        result = subprocess.run(
            [lsof_cmd, "-t", "-i", f":{port}"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0 and result.stdout.strip():
            pids = result.stdout.strip().split("\n")
            for pid in pids:
                if pid.isdigit():
                    console.print(
                        f"[yellow]Stopping existing process on port {port} (PID: {pid})...[/yellow]"
                    )
                    os.kill(int(pid), signal.SIGINT)
            # Give processes time to shut down gracefully
            time.sleep(1)
            return True
    except (OSError, subprocess.SubprocessError):
        pass
    return False


def _run_subprocess_with_interrupt(
    cmd: list[str | Path], cwd: Path, env: dict[str, str]
) -> int:
    """Run a subprocess with signal handling (SIGINT/SIGTERM).

    Args:
        cmd: Command and arguments to run.
        cwd: Working directory.
        env: Environment variables.

    Returns:
        Exit code from the subprocess, or 0 if interrupted.
    """
    process = subprocess.Popen(cmd, cwd=cwd, env=env)

    try:
        return process.wait()
    except KeyboardInterrupt:
        # User hit Ctrl+C. The child process (and the whole process group)
        # should have received the SIGINT from the OS.
        # We just wait for it to exit gracefully.
        try:
            return process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            # If it doesn't exit in time, kill it
            if is_running_in_target_env():
                console.print("[red]Process did not stop, killing...[/red]")
            process.kill()
            return -9


def _get_mkdocs_plugins() -> list[str]:
    """Get the list of mkdocs plugins to install with uvx.

    Returns:
        List of plugin package names.
    """
    return [
        "mkdocs",
        "mkdocs-material",
        "mkdocstrings[python]",
        "mkdocs-typer2",
        "mkdoxy",
        "mkdocs-mermaid2-plugin",
        "termynal",
    ]


def build_docs(
    target_path: Path, strict: bool = False, output_dir: Path | None = None
) -> int:
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

    # Get source paths and add to PYTHONPATH
    env = os.environ.copy()

    # If running internally (already in target env), call mkdocs directly
    if is_running_in_target_env():
        result = _build_with_mkdocs_direct(target_path, env, strict, output_dir)
        if result is not None:
            return result
        # If mkdocs not found even in internal call (unlikely), fall through?
        # No, if internal call, we expect mkdocs to be there.
        msg = "mkdocs not found in target environment"
        raise FileNotFoundError(msg)

    # Ensure mkapidocs is installed in target environment
    if not is_mkapidocs_in_target_env(target_path):
        msg = (
            "mkapidocs is not installed in the target environment.\n"
            "Please run 'mkapidocs setup' first to initialize the project."
        )
        raise RuntimeError(msg)

    # Always use target environment (which now has mkapidocs)
    return _build_with_target_env(target_path, env, strict, output_dir)


def _build_with_target_env(
    target_path: Path, env: dict[str, str], strict: bool, output_dir: Path | None
) -> int:
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
    # Use --directory to run in the target project's context
    cmd: CMD_LIST_TYPE = [
        uv_cmd,
        "--directory",
        str(target_path),
        "run",
        "mkapidocs",
        "build",
        str(target_path),
    ]
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
    console.print(
        "[blue]:zap: Running mkdocs directly (already in target environment)[/blue]"
    )
    if mkdocs_cmd := which("mkdocs"):
        cmd: CMD_LIST_TYPE = [mkdocs_cmd, "build"]
        if strict:
            cmd.append("--strict")
        if output_dir:
            cmd.extend(["--site-dir", str(output_dir)])
        return _run_subprocess(cmd, target_path, env)
    return None


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

    # Get source paths and add to PYTHONPATH
    env = os.environ.copy()

    # If running internally (already in target env), call mkdocs directly
    if is_running_in_target_env():
        result = _serve_with_mkdocs_direct(target_path, env, host, port)
        if result is not None:
            return result
        msg = "mkdocs not found in target environment"
        raise FileNotFoundError(msg)

    # Ensure mkapidocs is installed in target environment
    if not is_mkapidocs_in_target_env(target_path):
        msg = (
            "mkapidocs is not installed in the target environment.\n"
            "Please run 'mkapidocs setup' first to initialize the project."
        )
        raise RuntimeError(msg)

    # Always use target environment
    return _serve_with_target_env(target_path, env, host, port)


def _serve_with_target_env(
    target_path: Path, env: dict[str, str], host: str, port: int
) -> int:
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

    # Check for and kill existing process on port
    if _is_port_in_use(host, port):
        _kill_process_on_port(port)

    env["MKAPIDOCS_INTERNAL_CALL"] = "1"
    # Use --directory to run in the target project's context
    cmd: CMD_LIST_TYPE = [
        uv_cmd,
        "--directory",
        str(target_path),
        "run",
        "mkapidocs",
        "serve",
        str(target_path),
        "--host",
        host,
        "--port",
        str(port),
    ]

    return _run_subprocess_with_interrupt(cmd, target_path, env)


def _serve_with_mkdocs_direct(
    target_path: Path, env: dict[str, str], host: str, port: int
) -> int | None:
    """Serve docs using mkdocs directly.

    Args:
        target_path: Path to target project.
        env: Environment variables.
        host: Server host address.
        port: Server port.

    Returns:
        Exit code from serve, or None if mkdocs not found.
    """
    console.print(
        "[blue]:zap: Running mkdocs directly (already in target environment)[/blue]"
    )
    if mkdocs_cmd := which("mkdocs"):
        # Check for and kill existing process on port
        if _is_port_in_use(host, port):
            _kill_process_on_port(port)

        cmd: list[str | Path] = [mkdocs_cmd, "serve", "--dev-addr", f"{host}:{port}"]
        return _run_subprocess_with_interrupt(cmd, target_path, env)
    return None
