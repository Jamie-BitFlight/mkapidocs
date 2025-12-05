"""Core generation logic for mkapidocs."""

from __future__ import annotations

import ast
import http
import os
import re
import subprocess
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from shutil import which
from typing import TYPE_CHECKING, cast

import httpx
import tomlkit
import typer
from jinja2 import Environment
from rich.console import Console
from rich.panel import Panel
from tomlkit.exceptions import TOMLKitError

from mkapidocs.builder import is_mkapidocs_in_target_env
from mkapidocs.models import (
    CIProvider,
    GitLabCIConfig,
    GitLabIncludeAdapter,
    GitLabIncludeLocal,
    MessageType,
    PyprojectConfig,
    TomlTable,
)
from mkapidocs.project_detection import (
    detect_c_code,
    detect_typer_dependency,
    read_pyproject,
)
from mkapidocs.templates import (
    C_API_MD_TEMPLATE,
    CLI_MD_TEMPLATE,
    GITHUB_ACTIONS_PAGES_TEMPLATE,
    GITLAB_CI_PAGES_TEMPLATE,
    INDEX_MD_TEMPLATE,
    INSTALL_MD_TEMPLATE,
    MKDOCS_YML_TEMPLATE,
    PYTHON_API_MD_TEMPLATE,
)
from mkapidocs.yaml_utils import (
    YAMLError,
    display_file_changes,
    load_yaml_from_path,
    merge_mkdocs_yaml,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

# Initialize Rich console
console = Console()


def display_message(
    message: str, message_type: MessageType = MessageType.INFO, title: str | None = None
) -> None:
    """Display a formatted message panel.

    Args:
        message: The message text to display
        message_type: Type of message (affects styling)
        title: Optional panel title (defaults to message type)
    """
    color, default_title = message_type.value
    panel_title = title or default_title

    panel = Panel.fit(
        message,
        title=f"[bold {color}]{panel_title}[/bold {color}]",
        border_style=color,
        padding=(1, 2),
    )
    console.print(panel)


def _resolve_worktree_gitdir(repo_path: Path, gitdir_path: str) -> Path | None:
    """Resolve gitdir path from a worktree .git file.

    Args:
        repo_path: Path to repository root.
        gitdir_path: The gitdir path from the .git file.

    Returns:
        Path to the main .git directory containing config, or None.
    """
    # Handle relative paths
    if not Path(gitdir_path).is_absolute():
        gitdir_path = str((repo_path / gitdir_path).resolve())

    gitdir = Path(gitdir_path)
    if not gitdir.exists():
        return None

    # Check if this is a worktree path (contains /worktrees/)
    # e.g., /repo/.git/worktrees/branch -> /repo/.git
    if "worktrees" in gitdir.parts:
        worktree_idx = gitdir.parts.index("worktrees")
        main_git_dir = Path(*gitdir.parts[: worktree_idx + 1]).parent
        if (main_git_dir / "config").exists():
            return main_git_dir

    # Direct gitdir reference
    if (gitdir / "config").exists():
        return gitdir

    return None


def _resolve_git_dir(repo_path: Path) -> Path | None:
    """Resolve the actual .git directory, handling worktrees.

    For regular repos, .git is a directory containing config.
    For worktrees, .git is a file containing 'gitdir: /path/to/actual/git/dir'.

    Args:
        repo_path: Path to repository.

    Returns:
        Path to the git directory containing config, or None if not found.
    """
    git_path = repo_path / ".git"

    if not git_path.exists():
        return None

    # Regular repository - .git is a directory
    if git_path.is_dir():
        return git_path

    # Worktree - .git is a file with gitdir pointer
    if not git_path.is_file():
        return None

    try:
        content = git_path.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeDecodeError):
        return None

    if not content.startswith("gitdir:"):
        return None

    gitdir_path = content[7:].strip()
    return _resolve_worktree_gitdir(repo_path, gitdir_path)


def get_git_remote_url(repo_path: Path) -> str | None:
    """Get git remote URL from repository.

    Handles both regular repositories and git worktrees.

    Args:
        repo_path: Path to repository.

    Returns:
        Git remote URL or None if not available.
    """
    git_dir = _resolve_git_dir(repo_path)
    if git_dir is None:
        return None

    git_config_path = git_dir / "config"
    if not git_config_path.exists():
        return None

    try:
        config_content = git_config_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None

    # Match lines like "url = <url>" with any leading whitespace
    pattern = r"^\s*url =\s(.*)$"
    for line in config_content.splitlines():
        if match := re.match(pattern, line):
            return match.group(1).strip()
    return None


def convert_ssh_to_https(git_url: str) -> str:
    """Convert SSH git URL to HTTPS format.

    Args:
        git_url: Git URL in SSH format.

    Returns:
        HTTPS URL format.
    """
    if ssh_protocol_match := re.match(
        r"^(?:ssh://)?git@([^:]+)(?::[0-9]+)?[:/](.+?)(?:\.git)?$", git_url
    ):
        host = ssh_protocol_match.group(1)
        path = ssh_protocol_match.group(2)
        return f"https://{host}/{path}"
    return git_url


def _parse_git_remote(remote_url: str) -> tuple[str, str, str] | None:
    """Parse git remote URL into host, namespace, and project.

    Handles both SSH and HTTPS formats, including nested groups.

    Args:
        remote_url: Git remote URL.

    Returns:
        Tuple of (host, namespace, project) or None if parsing fails.
        Namespace may contain slashes for nested groups (e.g., "group/subgroup").
    """
    # SSH format: git@host:namespace/project.git or git@host:group/subgroup/project.git
    ssh_match = re.match(r"^(?:ssh://)?git@([^:]+)[:/](.+?)(?:\.git)?$", remote_url)
    if ssh_match:
        host = ssh_match.group(1)
        path = ssh_match.group(2)
        # Split path into namespace (everything before last /) and project (last segment)
        if "/" in path:
            last_slash = path.rfind("/")
            namespace = path[:last_slash]
            project = path[last_slash + 1 :]
            return host, namespace, project

    # HTTPS format: https://host/namespace/project.git
    https_match = re.match(r"^https://(?:[^@]+@)?([^/]+)/(.+?)(?:\.git)?$", remote_url)
    if https_match:
        host = https_match.group(1)
        path = https_match.group(2)
        if "/" in path:
            last_slash = path.rfind("/")
            namespace = path[:last_slash]
            project = path[last_slash + 1 :]
            return host, namespace, project

    return None


def _detect_url_base(repo_path: Path, domain: str, io_domain: str) -> str | None:
    """Detect Pages URL base from git remote for a specific domain.

    Args:
        repo_path: Path to repository.
        domain: Git domain (e.g., github.com).
        io_domain: Pages domain (e.g., github.io).

    Returns:
        Pages URL base or None if not detected.
    """
    remote_url = get_git_remote_url(repo_path)
    if remote_url is None:
        return None

    parsed = _parse_git_remote(remote_url)
    if parsed is None:
        return None

    host, namespace, project = parsed

    # Only match exact domain for GitHub/GitLab.com
    if host != domain:
        return None

    # For github.com/gitlab.com, use the standard io domain pattern
    # Get the top-level namespace (first segment before any /)
    top_namespace = namespace.split("/")[0]
    return f"https://{top_namespace}.{io_domain}/{project}/"


def detect_github_url_base(repo_path: Path) -> str | None:
    """Detect GitHub Pages URL base from git remote.

    Args:
        repo_path: Path to repository.

    Returns:
        GitHub Pages URL base or None if not detected.
    """
    return _detect_url_base(repo_path, "github.com", "github.io")


def detect_gitlab_url_base(repo_path: Path) -> str | None:
    """Detect GitLab Pages URL base from git remote.

    For gitlab.com, returns standard gitlab.io URL.
    For enterprise GitLab instances, returns None (requires manual configuration).

    Args:
        repo_path: Path to repository.

    Returns:
        GitLab Pages URL base or None if not detected.
    """
    return _detect_url_base(repo_path, "gitlab.com", "gitlab.io")


def detect_gitlab_enterprise_info(repo_path: Path) -> tuple[str, str, str] | None:
    """Detect enterprise GitLab instance information from git remote.

    Args:
        repo_path: Path to repository.

    Returns:
        Tuple of (host, namespace, project) for enterprise GitLab, or None.
    """
    remote_url = get_git_remote_url(repo_path)
    if remote_url is None:
        return None

    parsed = _parse_git_remote(remote_url)
    if parsed is None:
        return None

    host, namespace, project = parsed

    # Skip known public hosts
    if host in {"github.com", "gitlab.com"}:
        return None

    return host, namespace, project


def _get_gitlab_info(repo_path: Path) -> tuple[str, str, str] | None:
    """Get GitLab host, namespace, and project from git remote.

    Works for both gitlab.com and enterprise GitLab instances.
    This function only parses the git remote - the caller is responsible for
    ensuring this is actually a GitLab repository (via detect_ci_provider).

    Args:
        repo_path: Path to repository.

    Returns:
        Tuple of (host, namespace, project), or None if no git remote.
    """
    remote_url = get_git_remote_url(repo_path)
    if remote_url is None:
        return None

    return _parse_git_remote(remote_url)


@dataclass
class GitLabPagesResult:
    """Result of querying GitLab Pages URL."""

    url: str | None = None
    no_deployments: bool = False  # API succeeded but no Pages deployed yet
    error: str | None = None  # API call failed


# GraphQL query constant for GitLab Pages URL
_GITLAB_PAGES_QUERY = """
query($projectPath: ID!) {
  project(fullPath: $projectPath) {
    pagesDeployments(first: 1) {
      nodes {
        url
      }
    }
  }
}
"""


def _extract_graphql_error(data: dict[str, object]) -> str | None:
    """Extract error message from GraphQL response if present.

    Args:
        data: JSON response from GitLab GraphQL API.

    Returns:
        Error message string if errors present, None otherwise.
    """
    if "errors" not in data:
        return None

    errors = data["errors"]
    if not isinstance(errors, list) or not errors:
        return "Unknown GraphQL error"

    first_error = errors[0]
    if isinstance(first_error, dict):
        return str(first_error.get("message", "Unknown GraphQL error"))
    return "Unknown GraphQL error"


def _extract_pages_url(data: dict[str, object]) -> GitLabPagesResult:
    """Extract Pages URL from successful GraphQL response.

    Args:
        data: JSON response data (after error checking).

    Returns:
        GitLabPagesResult with URL, no_deployments flag, or error.
    """
    response_data = data.get("data")
    if not isinstance(response_data, dict):
        return GitLabPagesResult(error="Invalid response format")

    project = response_data.get("project")
    if not isinstance(project, dict):
        return GitLabPagesResult(error="Project not found (may lack permissions)")

    pages_deployments = project.get("pagesDeployments")
    nodes = (
        pages_deployments.get("nodes") if isinstance(pages_deployments, dict) else None
    )

    if not isinstance(nodes, list) or not nodes:
        return GitLabPagesResult(no_deployments=True)

    first_node = nodes[0]
    if isinstance(first_node, dict):
        url = first_node.get("url")
        if isinstance(url, str):
            return GitLabPagesResult(url=url)

    return GitLabPagesResult(no_deployments=True)


def _parse_gitlab_graphql_response(data: dict[str, object]) -> GitLabPagesResult:
    """Parse GitLab GraphQL response for Pages URL.

    Args:
        data: JSON response from GitLab GraphQL API.

    Returns:
        GitLabPagesResult with parsed data.
    """
    # Check for GraphQL errors first
    if error_msg := _extract_graphql_error(data):
        return GitLabPagesResult(error=error_msg)

    # Extract URL from successful response
    return _extract_pages_url(data)


def query_gitlab_pages_url(gitlab_host: str, project_path: str) -> GitLabPagesResult:
    """Query GitLab GraphQL API for the project's Pages URL.

    Uses the GraphQL API to fetch Pages deployment URL, which only requires
    read_api scope (Guest role) - more permissive than the REST API.
    Checks GITLAB_TOKEN first, then falls back to CI_JOB_TOKEN.

    Args:
        gitlab_host: The GitLab instance hostname (e.g., 'gitlab.com' or 'gitlab.example.com').
        project_path: Project path (e.g., 'namespace/project' or 'group/subgroup/project').

    Returns:
        GitLabPagesResult with url, no_deployments flag, or error message.
    """
    # Check for available tokens
    token = os.environ.get("GITLAB_TOKEN") or os.environ.get("CI_JOB_TOKEN")
    if not token:
        return GitLabPagesResult(error="no_token")

    graphql_url = f"https://{gitlab_host}/api/graphql"
    payload = {"query": _GITLAB_PAGES_QUERY, "variables": {"projectPath": project_path}}

    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.post(
                graphql_url,
                json=payload,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
            )

            if response.status_code != http.HTTPStatus.OK:
                return GitLabPagesResult(error=f"HTTP {response.status_code}")

            data = response.json()
            return _parse_gitlab_graphql_response(data)
    except httpx.RequestError as e:
        return GitLabPagesResult(error=f"Network error: {e}")
    except (ValueError, KeyError, IndexError) as e:
        return GitLabPagesResult(error=f"Parse error: {e}")


def detect_ci_provider(repo_path: Path) -> CIProvider | None:
    """Detect CI/CD provider from git remote URL or filesystem indicators.

    Detection strategy (in order):
    1. Check git remote URL for github or gitlab word in domain (supports custom/enterprise domains)
    2. Check filesystem for CI/CD config files (.gitlab-ci.yml, .gitlab/, .github/)
    3. Return None if provider cannot be determined

    Args:
        repo_path: Path to repository.

    Returns:
        Detected CI provider or None if not detected.
    """
    # Strategy 1: Check git remote URL
    if remote_url := get_git_remote_url(repo_path):
        if re.search(r"\bgithub\b", remote_url):
            return CIProvider.GITHUB
        if re.search(r"\bgitlab\b", remote_url):
            return CIProvider.GITLAB

    # Strategy 2: Check filesystem for CI/CD indicators
    # GitLab CI indicators
    if (repo_path / ".gitlab-ci.yml").exists() or (repo_path / ".gitlab").exists():
        return CIProvider.GITLAB

    # GitHub Actions indicators
    if (repo_path / ".github").exists():
        return CIProvider.GITHUB

    # Strategy 3: Cannot determine provider
    return None


def _get_mkapidocs_repo_root() -> Path | None:
    """Get the root of the mkapidocs repository if running from source.

    Returns:
        Path to repository root if found, None otherwise.
    """
    # packages/mkapidocs/generator.py -> packages/mkapidocs -> packages -> root
    current_file = Path(__file__).resolve()
    potential_root = current_file.parents[2]

    if (potential_root / "pyproject.toml").exists():
        try:
            with Path(potential_root / "pyproject.toml").open(encoding="utf-8") as f:
                config = tomlkit.load(f)
            project = config.get("project")
            if isinstance(project, dict) and project.get("name") == "mkapidocs":
                return potential_root
        except (OSError, TOMLKitError) as e:
            console.print(
                f"[yellow]Debug: Failed to read pyproject.toml at {potential_root}: {e}[/yellow]"
            )

    return None


def _run_subprocess(cmd: Sequence[str | Path], cwd: Path, env: dict[str, str]) -> int:
    """Run a subprocess and return its exit code.

    Args:
        cmd: Command and arguments to run.
        cwd: Working directory.
        env: Environment variables.

    Returns:
        Exit code from the subprocess.
    """
    result = subprocess.run(
        list(cmd), cwd=cwd, env=env, capture_output=False, check=False
    )
    return result.returncode


def ensure_mkapidocs_installed(repo_path: Path) -> bool:
    """Ensure mkapidocs is installed in the target project's environment.

    Checks if already installed first. If not installed, injects it:
    - As editable install with symlink mode if running from mkapidocs source
    - As dev dependency otherwise

    Args:
        repo_path: Path to target project.

    Returns:
        True if mkapidocs was installed (first run), False if already present.
    """
    if not (uv_cmd := which("uv")):
        console.print(
            "[yellow]uv not found. Skipping mkapidocs installation check.[/yellow]"
        )
        return False

    # Check if already installed - skip if so
    if is_mkapidocs_in_target_env(repo_path):
        return False

    console.print(
        "[blue]:syringe: Injecting mkapidocs into target environment...[/blue]"
    )

    # Unset VIRTUAL_ENV to ensure uv uses the target environment
    env = os.environ.copy()
    if "VIRTUAL_ENV" in env:
        del env["VIRTUAL_ENV"]

    repo_root = _get_mkapidocs_repo_root()

    if repo_root:
        console.print(
            f"[blue]Detected mkapidocs source at {repo_root}. Installing in editable mode.[/blue]"
        )
        # Sync to ensure environment exists (only needed for editable dev installs)
        sync_cmd = [uv_cmd, "--directory", str(repo_path), "sync"]
        try:
            _run_subprocess(sync_cmd, repo_path, env)
        except (OSError, subprocess.SubprocessError) as e:
            console.print(
                f"[yellow]Warning: Failed to sync target environment: {e}[/yellow]"
            )

        # Use pip install -e with symlink mode to avoid copy churn
        cmd = [
            uv_cmd,
            "--directory",
            str(repo_path),
            "pip",
            "install",
            "-e",
            str(repo_root),
            "--link-mode=symlink",
        ]
    else:
        console.print("[blue]Installing mkapidocs from registry.[/blue]")
        cmd = [uv_cmd, "--directory", str(repo_path), "add", "--dev", "mkapidocs"]

    try:
        _run_subprocess(cmd, repo_path, env)
    except (OSError, subprocess.SubprocessError) as e:
        console.print(f"[yellow]Warning: Failed to inject mkapidocs: {e}[/yellow]")
        return False
    else:
        console.print("[green]Successfully installed mkapidocs.[/green]")
        return True


def write_pyproject(repo_path: Path, config: PyprojectConfig) -> None:
    """Write pyproject.toml from typed configuration.

    Args:
        repo_path: Path to repository.
        config: Typed configuration to write.
    """
    pyproject_path = repo_path / "pyproject.toml"
    with Path(pyproject_path).open("w", encoding="utf-8") as f:
        tomlkit.dump(config.to_dict(), f)


def _is_typer_app_file(py_file: Path) -> bool:
    """Check if a Python file contains a Typer app.

    Args:
        py_file: Path to Python file.

    Returns:
        True if file contains Typer app instantiation.
    """
    try:
        content = py_file.read_text(encoding="utf-8")

        # Quick text check first (optimization)
        if "typer" not in content.lower() or "Typer(" not in content:
            return False

        # Parse AST to check for Typer app instantiation
        tree = ast.parse(content, filename=str(py_file))
    except (OSError, SyntaxError, UnicodeDecodeError):
        # Skip files that can't be read or parsed
        return False

    has_typer_import = False
    has_typer_app = False

    for node in ast.walk(tree):
        # Check for typer imports
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "typer":
                        has_typer_import = True
            elif node.module == "typer":  # node is ast.ImportFrom
                has_typer_import = True

        # Check for Typer() instantiation
        if isinstance(node, ast.Call) and (
            (isinstance(node.func, ast.Name) and node.func.id == "Typer")
            or (isinstance(node.func, ast.Attribute) and node.func.attr == "Typer")
        ):
            has_typer_app = True

    return has_typer_import and has_typer_app


def detect_typer_cli_module(repo_path: Path, pyproject: PyprojectConfig) -> list[str]:
    """Detect all Python modules containing Typer CLI apps.

    Searches the package structure for Python files that import Typer
    and instantiate a Typer() app instance. Collects ALL matching modules
    to support monorepos with multiple CLI applications.

    Args:
        repo_path: Path to repository.
        pyproject: Parsed pyproject.toml.

    Returns:
        List of module paths (e.g., ["package_name.cli", "package_name.tool2.main"]).
        Empty list if no Typer apps found.
    """
    # Get project name and convert to package name
    project_name = pyproject.project.name
    package_name = project_name.replace("-", "_")

    # Determine source paths to scan
    # We scan standard locations: src/package_name, packages/package_name, and package_name (flat layout)
    potential_paths = [
        repo_path / "packages" / package_name,
        repo_path / "src" / package_name,
        repo_path / package_name,
    ]
    source_paths = [p for p in potential_paths if p.exists() and p.is_dir()]

    if not source_paths:
        return []

    # Collect all Typer CLI modules
    cli_modules: list[str] = []

    # Search for Python files with Typer app
    for source_path in source_paths:
        for py_file in source_path.rglob("*.py"):
            # Skip test files
            if "test" in py_file.name or py_file.name.startswith("test_"):
                continue

            if _is_typer_app_file(py_file):
                # Convert file path to module path
                relative_path = py_file.relative_to(source_path)
                module_parts = [*list(relative_path.parts[:-1]), relative_path.stem]
                module_path = ".".join([package_name, *module_parts])
                cli_modules.append(module_path)

    return cli_modules


def detect_private_registry(pyproject: PyprojectConfig) -> tuple[bool, str | None]:
    """Detect if project uses private registry from uv configuration.

    Args:
        pyproject: Parsed pyproject.toml.

    Returns:
        Tuple of (is_private_registry, registry_url).
    """
    if pyproject.uv_index:
        first_index = pyproject.uv_index[0]
        url = first_index.get("url")
        return True, url if isinstance(url, str) else None

    return False, None


def update_ruff_config(pyproject: PyprojectConfig) -> PyprojectConfig:
    """Add docstring linting rules to ruff configuration.

    Args:
        pyproject: Parsed pyproject.toml.

    Returns:
        Updated pyproject configuration.
    """
    tool = pyproject.tool

    # Ensure tool.ruff exists and is a table
    ruff_raw = tool.get("ruff")
    ruff: TomlTable = cast("TomlTable", ruff_raw) if isinstance(ruff_raw, dict) else {}
    tool["ruff"] = ruff

    # Ensure tool.ruff.lint exists and is a table
    lint_raw = ruff.get("lint")
    lint: TomlTable = lint_raw if isinstance(lint_raw, dict) else {}
    ruff["lint"] = lint

    # Ensure tool.ruff.lint.select exists and is a list of strings
    select_raw = lint.get("select")
    select: list[str] = (
        [s for s in select_raw if isinstance(s, str)]
        if isinstance(select_raw, list)
        else []
    )
    lint["select"] = select

    # Add docstring rules if not present
    if "DOC" not in select:
        select.append("DOC")
    if "D" not in select:
        select.append("D")

    return pyproject


def create_mkdocs_config(
    repo_path: Path,
    project_name: str,
    site_url: str,
    c_source_dirs: list[Path],
    has_typer: bool,
    ci_provider: CIProvider,
    cli_modules: list[str] | None = None,
) -> bool:
    """Create or update mkdocs.yml configuration file.

    If the file exists, performs a smart merge that preserves user customizations
    while updating template-owned keys. If the file doesn't exist, creates it fresh.

    Args:
        repo_path: Path to repository.
        project_name: Name of the project.
        site_url: Full URL for GitHub Pages site.
        c_source_dirs: List of directories containing C/C++ code (empty if none).
        has_typer: Whether repository uses Typer.
        ci_provider: CI/CD provider type (GITHUB or GITLAB).
        cli_modules: List of detected CLI module paths (empty/None if none).

    Returns:
        True if mkdocs.yml was created fresh (first run), False if updated existing.

    Raises:
        CLIError: If existing YAML cannot be parsed or merge fails
    """
    env = Environment(keep_trailing_newline=True, autoescape=True)
    template = env.from_string(MKDOCS_YML_TEMPLATE)

    # Convert absolute Path objects to relative string paths for template
    c_source_dirs_relative = [
        str(path.relative_to(repo_path)) for path in c_source_dirs
    ]

    # Prepare CLI module information for template
    cli_modules_list = cli_modules or []
    cli_nav_items: list[dict[str, str]] = []
    if cli_modules_list:
        for cli_module in cli_modules_list:
            module_parts = cli_module.split(".")
            friendly_name = (
                "-".join(module_parts[1:]) if len(module_parts) > 1 else module_parts[0]
            )
            display_name = " ".join(
                word.capitalize() for word in friendly_name.split("-")
            )
            filename = (
                f"cli-api-{friendly_name}.md"
                if len(cli_modules_list) > 1
                else "cli-api.md"
            )
            cli_nav_items.append({"display_name": display_name, "filename": filename})

    content = template.render(
        project_name=project_name,
        site_url=site_url,
        c_source_dirs=c_source_dirs_relative,
        has_typer=has_typer,
        ci_provider=ci_provider.value,
        cli_modules=cli_nav_items,
    )

    mkdocs_path = repo_path / "mkdocs.yml"

    is_first_run = not mkdocs_path.exists()

    if mkdocs_path.exists():
        # File exists - perform smart merge
        merged_content, changes = merge_mkdocs_yaml(mkdocs_path, content)
        _ = mkdocs_path.write_text(merged_content)
        display_file_changes(mkdocs_path, changes)
    else:
        # New file - create fresh
        _ = mkdocs_path.write_text(content)
        console.print(f"[green]:white_check_mark:[/green] Created {mkdocs_path.name}")

    return is_first_run


def _is_pages_job(job: dict[str, object]) -> bool:
    """Check if a job is a GitHub Pages deployment job.

    Args:
        job: Job dictionary.

    Returns:
        True if job is a Pages deployment job.
    """
    # Check steps for actions/deploy-pages
    steps: list[object] = cast("list[object]", job.get("steps", []))
    for step in steps:
        if isinstance(step, dict) and "uses" in step:
            uses = str(step["uses"])
            if "actions/deploy-pages" in uses:
                return True

    # Check environment
    environment = job.get("environment")
    env_name = ""
    if isinstance(environment, dict):
        name = str(environment.get("name", ""))
        env_name = name
    elif isinstance(environment, str):
        env_name = environment

    return env_name == "github-pages" or env_name.startswith("github-pages")


def _uses_mkapidocs(job: dict[str, object]) -> bool:
    """Check if a job uses mkapidocs.

    Args:
        job: Job dictionary.

    Returns:
        True if job uses mkapidocs.
    """
    steps: list[object] = cast("list[object]", job.get("steps", []))
    for step in steps:
        if isinstance(step, dict) and "run" in step:
            run_cmd = str(step["run"])
            if "mkapidocs" in run_cmd:
                return True
    return False


def _check_existing_github_workflow(workflow_file: Path) -> bool:
    """Check if a GitHub workflow file already handles Pages deployment.

    Args:
        workflow_file: Path to workflow file.

    Returns:
        True if Pages deployment is found.
    """
    workflow = load_yaml_from_path(workflow_file)

    if workflow is None or "jobs" not in workflow:
        return False

    jobs = cast("dict[str, object]", workflow.get("jobs", {}))

    for job_name, job in jobs.items():
        if not isinstance(job, dict):
            continue

        # Cast job to dict[str, object] for helper functions
        job_dict = cast("dict[str, object]", job)

        if _is_pages_job(job_dict):
            if _uses_mkapidocs(job_dict):
                console.print(
                    f"[green]Found existing pages deployment job '{job_name}' in '{workflow_file.name}' using mkapidocs.[/green]"
                )
            else:
                console.print(
                    f"[yellow]Found existing pages deployment job '{job_name}' in '{workflow_file.name}'.[/yellow]"
                )
                console.print(
                    "[yellow]You should update it to run 'uv run mkapidocs build' before deployment.[/yellow]"
                )
            return True

    return False


def create_github_actions(repo_path: Path) -> None:
    """Create .github/workflows/pages.yml for GitHub Pages deployment.

    Creates a fresh GitHub Actions workflow file. If the file exists, it will be
    overwritten with the template (no smart merge for GitHub Actions).

    Args:
        repo_path: Path to repository.
    """
    github_dir = repo_path / ".github" / "workflows"
    github_dir.mkdir(parents=True, exist_ok=True)

    # Check for existing pages deployment in any workflow
    for workflow_file in github_dir.glob("*.y*ml"):
        if _check_existing_github_workflow(workflow_file):
            return

    content = GITHUB_ACTIONS_PAGES_TEMPLATE

    workflow_path = github_dir / "pages.yml"
    exists_before = workflow_path.exists()

    # Always write fresh - GitHub Actions workflows are simpler
    _ = workflow_path.write_text(content)

    if exists_before:
        console.print(f"[green]:white_check_mark:[/green] Updated {workflow_path.name}")
    else:
        console.print(f"[green]:white_check_mark:[/green] Created {workflow_path.name}")


def _strip_quotes(s: str) -> str:
    """Strip leading and trailing quotes from a string.

    Args:
        s: String to strip quotes from.

    Returns:
        String with leading and trailing quotes removed.
    """
    return s.strip(" \"'")


def _check_existing_gitlab_ci(gitlab_ci_path: Path) -> bool:
    """Check if .gitlab-ci.yml already includes the pages workflow.

    Args:
        gitlab_ci_path: Path to .gitlab-ci.yml.

    Returns:
        True if pages workflow include is found.
    """
    with suppress(YAMLError, OSError):
        config = GitLabCIConfig.load(gitlab_ci_path)
        if config is None:
            return False

        # Validate with Pydantic for typed access
        validated = GitLabIncludeAdapter.validate_python(config.include_list)
        includes = validated if isinstance(validated, list) else [validated]

        for inc in includes:
            if isinstance(inc, GitLabIncludeLocal):
                if _strip_quotes(inc.local) == ".gitlab/workflows/pages.gitlab-ci.yml":
                    console.print(
                        "[green]Found existing pages workflow include in '.gitlab-ci.yml'.[/green]"
                    )
                    return True
            elif (
                isinstance(inc, str)
                and _strip_quotes(inc) == ".gitlab/workflows/pages.gitlab-ci.yml"
            ):
                console.print(
                    "[green]Found existing pages workflow include in '.gitlab-ci.yml'.[/green]"
                )
                return True

    return False


def _ensure_pages_stage(gitlab_ci_path: Path) -> None:
    """Ensure 'pages' stage exists in .gitlab-ci.yml.

    Args:
        gitlab_ci_path: Path to .gitlab-ci.yml.
    """
    if not gitlab_ci_path.exists():
        return

    with suppress(YAMLError, OSError):
        config = GitLabCIConfig.load(gitlab_ci_path)
        if config:
            stages = config.stages or []
            if "pages" not in stages:
                if GitLabCIConfig.add_stage_and_save(gitlab_ci_path, "pages"):
                    console.print(
                        f"[green]:white_check_mark: Added 'pages' stage to {gitlab_ci_path.name}[/green]"
                    )
                else:
                    console.print(
                        f"[yellow]Could not automatically add 'pages' stage to {gitlab_ci_path.name}. Please add it manually.[/yellow]"
                    )


def create_gitlab_ci(repo_path: Path) -> None:
    """Create or update .gitlab-ci.yml for GitLab Pages deployment.

    Creates .gitlab/workflows/pages.gitlab-ci.yml and includes it in .gitlab-ci.yml.

    Args:
        repo_path: Path to repository.
    """
    gitlab_ci_path = repo_path / ".gitlab-ci.yml"
    workflows_dir = repo_path / ".gitlab" / "workflows"
    pages_workflow_path = workflows_dir / "pages.gitlab-ci.yml"

    # Create workflows directory
    workflows_dir.mkdir(parents=True, exist_ok=True)

    # Write pages workflow file (only if doesn't exist)
    if not pages_workflow_path.exists():
        _ = pages_workflow_path.write_text(GITLAB_CI_PAGES_TEMPLATE, encoding="utf-8")
        console.print(
            f"[green]:white_check_mark: Created {pages_workflow_path.relative_to(repo_path)}[/green]"
        )

    # Check for existing include
    if _check_existing_gitlab_ci(gitlab_ci_path):
        return

    include_entry: dict[str, str] = {"local": ".gitlab/workflows/pages.gitlab-ci.yml"}

    if gitlab_ci_path.exists():
        # Modify existing file
        try:
            if GitLabCIConfig.add_include_and_save(gitlab_ci_path, include_entry):
                console.print(
                    f"[green]:white_check_mark: Added include to {gitlab_ci_path.name}[/green]"
                )
            else:
                # Fallback to append if structure is weird
                with gitlab_ci_path.open("a", encoding="utf-8") as f:
                    f.write(
                        "\ninclude:\n  - local: .gitlab/workflows/pages.gitlab-ci.yml\n"
                    )
                console.print(
                    f"[green]:white_check_mark: Appended include to {gitlab_ci_path.name}[/green]"
                )

        except (YAMLError, OSError):
            # Fallback to append
            with gitlab_ci_path.open("a", encoding="utf-8") as f:
                f.write(
                    "\ninclude:\n  - local: .gitlab/workflows/pages.gitlab-ci.yml\n"
                )
            console.print(
                f"[green]:white_check_mark: Appended include to {gitlab_ci_path.name}[/green]"
            )
    else:
        # Create new file
        initial_content = "include:\n  - local: .gitlab/workflows/pages.gitlab-ci.yml\n"
        _ = gitlab_ci_path.write_text(initial_content, encoding="utf-8")
        console.print(
            f"[green]:white_check_mark: Created {gitlab_ci_path.name}[/green]"
        )

    # Ensure 'pages' stage exists (required for the pages job)
    _ensure_pages_stage(gitlab_ci_path)


def create_index_page(
    repo_path: Path,
    project_name: str,
    description: str,
    c_source_dirs: list[Path],
    has_typer: bool,
    license_name: str,
    has_private_registry: bool,
    private_registry_url: str | None,
) -> None:
    """Create docs/index.md homepage.

    Only creates if doesn't exist - preserves user customizations.

    Args:
        repo_path: Path to repository.
        project_name: Name of the project.
        description: Project description.
        c_source_dirs: List of directories containing C/C++ code (empty if none).
        has_typer: Whether repository uses Typer.
        license_name: License name.
        has_private_registry: Whether project uses private registry.
        private_registry_url: URL of private registry if configured.
    """
    docs_dir = repo_path / "docs"
    docs_dir.mkdir(exist_ok=True)

    index_path = docs_dir / "index.md"

    # Only create if doesn't exist - preserve user customizations
    if index_path.exists():
        return

    env = Environment(keep_trailing_newline=True, autoescape=True)
    template = env.from_string(INDEX_MD_TEMPLATE)

    content = template.render(
        project_name=project_name,
        description=description,
        c_source_dirs=c_source_dirs,
        has_typer=has_typer,
        license=license_name,
        has_private_registry=has_private_registry,
        private_registry_url=private_registry_url,
    )

    _ = index_path.write_text(content)


def create_api_reference(
    repo_path: Path,
    project_name: str,
    c_source_dirs: list[Path],
    cli_modules: list[str] | None = None,
) -> None:
    """Create API reference documentation pages.

    Args:
        repo_path: Path to repository.
        project_name: Name of the project.
        c_source_dirs: List of directories containing C/C++ code (empty if none).
        cli_modules: List of detected CLI module paths (e.g., ["package.cli", "package.tool2.main"]),
                     or None/empty list if no CLI detected.
    """
    generated_dir = repo_path / "docs" / "generated"
    generated_dir.mkdir(parents=True, exist_ok=True)

    env = Environment(keep_trailing_newline=True, autoescape=True)
    package_name = project_name.replace("-", "_")

    # Python API
    python_template = env.from_string(PYTHON_API_MD_TEMPLATE)
    python_content = python_template.render(package_name=package_name)
    _ = (generated_dir / "python-api.md").write_text(python_content)

    # C API - only create if C/C++ source directories detected
    if c_source_dirs:
        c_template = env.from_string(C_API_MD_TEMPLATE)
        c_content = c_template.render(project_name=project_name)
        _ = (generated_dir / "c-api.md").write_text(c_content)

    # CLI - create a separate file for each CLI module detected
    if cli_modules:
        cli_template = env.from_string(CLI_MD_TEMPLATE)
        for cli_module in cli_modules:
            # Extract a friendly name from the module path for the filename
            # e.g., "package.cli" -> "cli", "package.tool2.main" -> "tool2-main"
            module_parts = cli_module.split(".")
            # Remove package name prefix and join remaining parts
            friendly_name = (
                "-".join(module_parts[1:]) if len(module_parts) > 1 else module_parts[0]
            )

            cli_content = cli_template.render(
                project_name=project_name,
                package_name=package_name,
                cli_module=cli_module,
            )
            filename = (
                f"cli-api-{friendly_name}.md" if len(cli_modules) > 1 else "cli-api.md"
            )
            _ = (generated_dir / filename).write_text(cli_content)


def create_generated_content(
    repo_path: Path,
    project_name: str,
    c_source_dirs: list[Path],
    cli_modules: list[str],
    has_private_registry: bool,
    private_registry_url: str | None,
    has_scripts: bool,
) -> None:
    """Create generated content snippets for inclusion in user docs.

    These files are regenerated on every setup and git-ignored.

    Args:
        repo_path: Path to repository.
        project_name: Name of the project.
        c_source_dirs: List of directories containing C/C++ code (empty if none).
        cli_modules: List of detected CLI modules (empty if none).
        has_private_registry: Whether project uses private registry.
        private_registry_url: URL of private registry if configured.
        has_scripts: Whether project has CLI scripts in [project.scripts].
    """
    generated_dir = repo_path / "docs" / "generated"
    generated_dir.mkdir(parents=True, exist_ok=True)

    # index-features.md
    features: list[str] = []
    features.extend((
        "## Key Features\n",
        "- **[Python API Reference](python-api.md)** - Complete API documentation",
    ))

    if cli_modules:
        if len(cli_modules) == 1:
            features.append(
                "- **[CLI Reference](cli-api.md)** - Command-line interface"
            )
        else:
            # Multiple CLI apps - link to each one
            features.append("- **CLI References:**")
            for cli_module in cli_modules:
                module_parts = cli_module.split(".")
                friendly_name = (
                    "-".join(module_parts[1:])
                    if len(module_parts) > 1
                    else module_parts[0]
                )
                # Create a nice display name (e.g., "tool2-main" -> "Tool2 Main")
                display_name = " ".join(
                    word.capitalize() for word in friendly_name.split("-")
                )
                features.append(
                    f"  - **[{display_name}](cli-api-{friendly_name}.md)** - CLI interface"
                )

    if c_source_dirs:
        features.append("- **[C API Reference](c-api.md)** - C/C++ API documentation")

    features_content = "\n".join(features) + "\n"
    _ = (generated_dir / "index-features.md").write_text(features_content)

    # install-command.md - context-aware install instructions
    install_lines: list[str] = []

    # CLI tool installation (only if project has scripts)
    if has_scripts:
        install_lines.extend(("To install as a CLI tool:", "", "```bash"))
        if has_private_registry and private_registry_url:
            install_lines.append(
                f'uv tool install --index="{private_registry_url}" {project_name}'
            )
        else:
            install_lines.append(f"uv tool install {project_name}")
        install_lines.extend(("```", ""))

    # Package dependency installation
    install_lines.extend(("To add to your project dependencies:", "", "```bash"))
    if has_private_registry and private_registry_url:
        install_lines.append(f'uv add --index="{private_registry_url}" {project_name}')
    else:
        install_lines.append(f"uv add {project_name}")
    install_lines.extend((
        "```",
        "",
        "To add as a development dependency:",
        "",
        "```bash",
    ))
    if has_private_registry and private_registry_url:
        install_lines.append(
            f'uv add --dev --index="{private_registry_url}" {project_name}'
        )
    else:
        install_lines.append(f"uv add --dev {project_name}")
    install_lines.append("```")

    install_content = "\n".join(install_lines) + "\n"
    _ = (generated_dir / "install-command.md").write_text(install_content)


def update_gitignore(
    repo_path: Path, provider: CIProvider, include_generated: bool = False
) -> None:
    """Update .gitignore to exclude MkDocs build artifacts.

    Adds build directory (/site/ for GitHub, /public/ for GitLab) and .mkdocs_cache/
    entries if they are not already present. Optionally includes docs/generated/ to .gitignore.

    Args:
        repo_path: Path to repository.
        provider: CI provider (determines build directory).
        include_generated: Whether to add docs/generated/ to gitignore.
    """
    gitignore_path = repo_path / ".gitignore"

    # Use provider-specific build directory
    build_dir = "/public/" if provider == CIProvider.GITLAB else "/site/"
    entries_to_add = [build_dir, ".mkdocs_cache/"]
    if include_generated:
        entries_to_add.append("docs/generated/")

    # Read existing content or start with empty string
    existing_lines: list[str]
    if gitignore_path.exists():
        existing_content = gitignore_path.read_text()
        existing_lines = existing_content.splitlines()
    else:
        existing_content = ""
        existing_lines = []

    # Determine which entries need to be added
    missing_entries: list[str] = []
    for entry in entries_to_add:
        # Check if entry exists (as exact match or without leading slash)
        normalized_entry = entry.lstrip("/")
        is_present = any(
            line.strip() == entry
            or line.strip() == normalized_entry
            or line.strip() == f"/{normalized_entry}"
            for line in existing_lines
        )
        if not is_present:
            missing_entries.append(entry)

    # Add missing entries if any
    if missing_entries:
        # Ensure content ends with newline before adding entries
        if existing_content and not existing_content.endswith("\n"):
            existing_content += "\n"

        # Add section header if we're adding to existing file
        if existing_content:
            existing_content += "\n# MkDocs documentation\n"
        else:
            existing_content = "# MkDocs documentation\n"

        # Add each missing entry
        for entry in missing_entries:
            existing_content += f"{entry}\n"

        # Write updated content
        _ = gitignore_path.write_text(existing_content)


def create_supporting_docs(
    repo_path: Path,
    project_name: str,
    pyproject: PyprojectConfig,
    c_source_dirs: list[Path],
    has_typer: bool,
    site_url: str,
    git_url: str | None = None,
) -> None:
    """Create supporting documentation pages.

    Args:
        repo_path: Path to repository.
        project_name: Name of the project.
        pyproject: Parsed pyproject.toml.
        c_source_dirs: List of directories containing C/C++ code (empty if none).
        has_typer: Whether repository uses Typer.
        site_url: Full URL for GitHub Pages site.
        git_url: Git repository URL.
    """
    docs_dir = repo_path / "docs"
    docs_dir.mkdir(exist_ok=True)

    env = Environment(keep_trailing_newline=True, autoescape=True)

    requires_python = pyproject.project.requires_python or "3.11+"

    if git_url is None:
        git_url = get_git_remote_url(repo_path)
        if git_url is not None:
            git_url = convert_ssh_to_https(git_url)

    has_private_registry, private_registry_url = detect_private_registry(pyproject)

    template_context = {
        "project_name": project_name,
        "requires_python": requires_python,
        "git_url": git_url,
        "c_source_dirs": c_source_dirs,
        "has_typer": has_typer,
        "site_url": site_url,
        "has_private_registry": has_private_registry,
        "private_registry_url": private_registry_url,
        "script_names": pyproject.script_names,
        "has_scripts": pyproject.has_scripts,
    }

    # Create install.md (only if doesn't exist - preserve user customizations)
    install_path = docs_dir / "install.md"
    if not install_path.exists():
        install_template = env.from_string(INSTALL_MD_TEMPLATE)
        install_content = install_template.render(**template_context)
        _ = install_path.write_text(install_content)


def _get_project_info(pyproject: PyprojectConfig) -> tuple[str, str, str]:
    """Extract project name, description, and license from pyproject.

    Args:
        pyproject: Parsed pyproject.toml.

    Returns:
        Tuple containing (project_name, description, license_name).
    """
    project_name = pyproject.project.name
    description = pyproject.project.description or ""
    license_info = pyproject.project.license
    # Handle both string and dict license formats
    if isinstance(license_info, dict):
        license_name = license_info.get("text", "See LICENSE file")
    elif isinstance(license_info, str):
        license_name = license_info
    else:
        license_name = "See LICENSE file"
    return project_name, description, license_name


def _detect_gitlab_site_url(repo_path: Path) -> str:
    """Detect GitLab Pages site URL from git remote and API.

    Args:
        repo_path: Path to repository.

    Returns:
        Detected or heuristic site URL.
    """
    gitlab_info = _get_gitlab_info(repo_path)

    if not gitlab_info:
        # No git remote at all - use generic placeholder
        detected_url = f"https://example.gitlab.io/{repo_path.name}"
        warning_message = (
            "Could not auto-detect GitLab Pages URL.\n\n"
            f"Using placeholder: [cyan]{detected_url}[/cyan]\n\n"
            "[bold]After setup:[/bold]\n"
            "Edit [cyan]mkdocs.yml[/cyan] and update [cyan]site_url[/cyan] to the correct value."
        )
        display_message(
            warning_message,
            MessageType.WARNING,
            title="GitLab URL - Manual Configuration Required",
        )
        return detected_url

    host, namespace, project = gitlab_info
    project_path = f"{namespace}/{project}"
    is_enterprise = host != "gitlab.com"
    title_prefix = "Enterprise GitLab" if is_enterprise else "GitLab Pages"

    # Try to query GitLab API for Pages URL if token is available
    api_result = query_gitlab_pages_url(host, project_path)

    if api_result.url:
        detected_url = api_result.url.rstrip("/")
        display_message(
            f"GitLab Pages URL retrieved from API: [cyan]{detected_url}[/cyan]",
            MessageType.SUCCESS,
            title=title_prefix,
        )
        return detected_url

    # Use heuristic-based URL
    if is_enterprise:
        detected_url = f"https://{namespace.split('/')[0]}.pages.{host}/{project}"
    else:
        detected_url = f"https://{namespace}.gitlab.io/{project}"

    # Provide appropriate hint based on what happened
    if api_result.no_deployments:
        hint = "Pages not deployed yet. URL will be confirmed after first deployment."
    elif api_result.error == "no_token":
        hint = "Set [cyan]GITLAB_TOKEN[/cyan] environment variable to query Pages URL from API."
    else:
        hint = f"API error: {api_result.error}"

    warning_message = (
        f"GitLab instance: [bold cyan]{host}[/bold cyan]\n\n"
        f"[bold]Repository:[/bold] {project_path}\n\n"
        f"[bold]Hint:[/bold] {hint}\n\n"
        f"Using heuristic URL: [cyan]{detected_url}[/cyan]\n\n"
        "[bold]After setup:[/bold]\n"
        "Edit [cyan]mkdocs.yml[/cyan] and update [cyan]site_url[/cyan] if the URL is incorrect."
    )
    display_message(
        warning_message,
        MessageType.WARNING,
        title=f"{title_prefix} - URL May Need Adjustment",
    )
    return detected_url


def _detect_provider_and_url(
    repo_path: Path, provider: CIProvider | None, site_url: str | None
) -> tuple[CIProvider, str]:
    """Detect CI provider and site URL.

    Args:
        repo_path: Path to repository.
        provider: Explicitly provided CI provider (or None).
        site_url: Explicitly provided site URL (or None for auto-detection).

    Returns:
        Tuple containing (detected_provider, site_url).
    """
    # Auto-detect provider if not specified
    if provider is None:
        provider = detect_ci_provider(repo_path)
        if provider is None:
            error_message = (
                "Could not auto-detect CI/CD provider.\n\n"
                "[bold]Detection attempts:[/bold]\n"
                "  1. Git remote URL (github.com or gitlab.com)\n"
                "  2. Filesystem indicators (.gitlab-ci.yml, .gitlab/, .github/)\n\n"
                "[bold]Solution:[/bold]\n"
                "Explicitly specify provider with [cyan]--provider github[/cyan] or [cyan]--provider gitlab[/cyan]"
            )
            display_message(
                error_message, MessageType.ERROR, title="Provider Detection Failed"
            )
            raise typer.Exit(1)

    # If site_url is explicitly provided, use it directly
    if site_url:
        return provider, site_url.rstrip("/")

    # Detect site URL based on provider
    if provider == CIProvider.GITHUB:
        github_url_base = detect_github_url_base(repo_path)
        if github_url_base is None:
            raise ValueError(
                "Could not auto-detect GitHub URL from git remote. Please provide --site-url option."
            )
        return provider, github_url_base.rstrip("/")

    # GitLab provider
    return provider, _detect_gitlab_site_url(repo_path)


def _detect_features(
    repo_path: Path, pyproject: PyprojectConfig, c_source_dirs: list[str] | None
) -> tuple[list[Path], list[str], bool, bool, str | None]:
    """Detect project features (C code, Typer, private registry).

    Args:
        repo_path: Path to repository.
        pyproject: Parsed pyproject.toml.
        c_source_dirs: Explicit C source directories (or None).

    Returns:
        Tuple containing (c_source_dirs_list, cli_modules, has_typer, has_private_registry, private_registry_url).
    """
    c_source_dirs_list = detect_c_code(
        repo_path, explicit_dirs=c_source_dirs, pyproject=pyproject
    )
    has_typer = detect_typer_dependency(pyproject)
    has_private_registry, private_registry_url = detect_private_registry(pyproject)

    # Detect Typer CLI modules if Typer is a dependency
    cli_modules: list[str] = []
    if has_typer:
        cli_modules = detect_typer_cli_module(repo_path, pyproject)

        # FAIL if Typer is a dependency but no CLI modules found
        if not cli_modules:
            error_message = (
                ":x: Typer detected in dependencies but no CLI module found.\n\n"
                "[bold]Why this matters:[/bold]\n"
                "CLI documentation cannot be generated without a detectable Typer app.\n\n"
                "[bold]How to fix:[/bold]\n"
                "Option 1: Remove Typer from dependencies if not using CLI\n"
                "Option 2: Add a CLI module with [cyan]app = typer.Typer()[/cyan] instantiation\n\n"
                "[bold]What the detector looks for:[/bold]\n"
                "Python files that import Typer and instantiate [cyan]Typer()[/cyan]\n"
                "Example: [cyan]import typer[/cyan] and [cyan]app = typer.Typer()[/cyan]"
            )
            display_message(
                error_message, MessageType.ERROR, title="Typer CLI Not Found"
            )
            raise typer.Exit(1)

    return (
        c_source_dirs_list,
        cli_modules,
        has_typer,
        has_private_registry,
        private_registry_url,
    )


@dataclass
class SetupResult:
    """Result of setup_documentation() with context for messaging."""

    provider: CIProvider
    is_first_run: bool  # True if mkdocs.yml was created fresh
    mkapidocs_installed: bool  # True if mkapidocs was installed (not already present)


def setup_documentation(
    repo_path: Path,
    provider: CIProvider | None = None,
    site_url: str | None = None,
    c_source_dirs: list[str] | None = None,
) -> SetupResult:
    """Set up MkDocs documentation for a Python repository.

    Args:
        repo_path: Path to repository.
        provider: CI/CD provider (auto-detected if None).
        site_url: Explicit Pages URL (auto-detected if None).
        c_source_dirs: Optional list of C/C++ source directories from CLI.

    Returns:
        SetupResult with provider, first_run flag, and installation status.

    Raises:
        ValueError: If provider cannot be auto-detected.
        typer.Exit: If setup fails.
    """
    pyproject = read_pyproject(repo_path)

    project_name, description, license_name = _get_project_info(pyproject)
    provider, final_site_url = _detect_provider_and_url(repo_path, provider, site_url)
    c_source_dirs_list, cli_modules, _, has_private_registry, private_registry_url = (
        _detect_features(repo_path, pyproject, c_source_dirs)
    )

    # has_typer_cli flag is True if CLI modules were actually detected
    has_typer_cli = len(cli_modules) > 0

    is_first_run = create_mkdocs_config(
        repo_path,
        project_name,
        final_site_url,
        c_source_dirs_list,
        has_typer_cli,
        provider,
        cli_modules,
    )

    # Create CI/CD configuration based on provider
    if provider == CIProvider.GITHUB:
        create_github_actions(repo_path)
    elif provider == CIProvider.GITLAB:
        create_gitlab_ci(repo_path)

    create_index_page(
        repo_path,
        project_name,
        description,
        c_source_dirs_list,
        has_typer_cli,
        license_name,
        has_private_registry,
        private_registry_url,
    )
    create_api_reference(repo_path, project_name, c_source_dirs_list, cli_modules)
    create_generated_content(
        repo_path,
        project_name,
        c_source_dirs_list,
        cli_modules,
        has_private_registry,
        private_registry_url,
        pyproject.has_scripts,
    )
    create_supporting_docs(
        repo_path,
        project_name,
        pyproject,
        c_source_dirs_list,
        has_typer_cli,
        final_site_url,
        git_url=None,
    )

    update_gitignore(repo_path, provider)

    # Add mkapidocs to target project's dev dependencies
    mkapidocs_installed = ensure_mkapidocs_installed(repo_path)

    return SetupResult(
        provider=provider,
        is_first_run=is_first_run,
        mkapidocs_installed=mkapidocs_installed,
    )
