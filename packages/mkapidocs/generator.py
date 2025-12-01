"""Core generation logic for mkapidocs."""

from __future__ import annotations

import ast
import os
import re
import subprocess
from contextlib import suppress
from pathlib import Path
from shutil import which
from typing import cast

import tomlkit
from jinja2 import Environment
from rich.console import Console
from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError
from tomlkit import exceptions

from mkapidocs.models import (
    CIProvider,
    GitLabCIConfig,
    GitLabIncludeAdapter,
    GitLabIncludeLocal,
    MessageType,
    PyprojectConfig,
    TomlTable,
    TomlValue,
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
from mkapidocs.yaml_utils import display_file_changes, merge_mkdocs_yaml

# Initialize Rich console
console = Console()


def display_message(message: str, message_type: MessageType = MessageType.INFO, title: str | None = None) -> None:
    """Display a formatted message panel.

    Args:
        message: The message text to display
        message_type: Type of message (affects styling)
        title: Optional panel title (defaults to message type)
    """
    from rich.panel import Panel

    color, default_title = message_type.value
    panel_title = title or default_title

    console.print(
        Panel(message, title=f"[bold {color}]{panel_title}[/bold {color}]", border_style=color, padding=(1, 2))
    )


def get_git_remote_url(repo_path: Path) -> str | None:
    """Get git remote URL from repository.

    Args:
        repo_path: Path to repository.

    Returns:
        Git remote URL or None if not available.
    """
    git_config_path = repo_path / ".git" / "config"

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
    if ssh_protocol_match := re.match(r"^(?:ssh://)?git@([^:]+)(?::[0-9]+)?[:/](.+?)(?:\.git)?$", git_url):
        host = ssh_protocol_match.group(1)
        path = ssh_protocol_match.group(2)
        return f"https://{host}/{path}"
    return git_url


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

    # Escape dots in domain for regex
    escaped_domain = re.escape(domain)

    # Parse SSH format: git@domain:owner/repo.git
    ssh_pattern = rf"^(?:ssh://)?git@{escaped_domain}[:/]([^/]+)/([^/]+?)(?:\.git)?$"
    if match := re.match(ssh_pattern, remote_url):
        owner = match.group(1)
        repo = match.group(2)
        return f"https://{owner}.{io_domain}/{repo}/"

    # Parse HTTPS format: https://domain/owner/repo.git
    https_pattern = rf"^https://(?:[^@]+@)?{escaped_domain}/([^/]+)/([^/]+?)(?:\.git)?$"
    if match := re.match(https_pattern, remote_url):
        owner = match.group(1)
        repo = match.group(2)
        return f"https://{owner}.{io_domain}/{repo}/"

    return None


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

    Args:
        repo_path: Path to repository.

    Returns:
        GitLab Pages URL base or None if not detected.
    """
    return _detect_url_base(repo_path, "gitlab.com", "gitlab.io")


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


def ensure_mkapidocs_installed(repo_path: Path) -> None:
    """Ensure mkapidocs is installed in the target environment.

    Checks if mkapidocs is installed via 'uv pip show'. If not, installs it
    as a dev dependency using 'uv add --dev'.

    Args:
        repo_path: Path to repository.
    """
    if not (uv_cmd := which("uv")):
        console.print("[yellow]uv not found. Skipping mkapidocs installation check.[/yellow]")
        return

    try:
        # Check if installed
        subprocess.run([uv_cmd, "pip", "show", "mkapidocs"], cwd=repo_path, check=True, capture_output=True)
    except subprocess.CalledProcessError:
        # Not installed, install it
        console.print("[yellow]mkapidocs not found in environment. Installing as dev dependency...[/yellow]")
        try:
            subprocess.run([uv_cmd, "add", "--dev", "mkapidocs"], cwd=repo_path, check=True)
            console.print("[green]Successfully installed mkapidocs.[/green]")
        except subprocess.CalledProcessError:
            console.print("[red]Failed to install mkapidocs. Please install it manually.[/red]")
            # We don't raise here, we let the user try to proceed or fail later


def read_pyproject(repo_path: Path) -> PyprojectConfig:
    """Read and parse pyproject.toml into typed configuration.

    Args:
        repo_path: Path to repository.

    Returns:
        Parsed and validated pyproject.toml configuration.

    Raises:
        FileNotFoundError: If pyproject.toml does not exist.
        FileNotFoundError: If pyproject.toml does not exist.
    """
    pyproject_path = repo_path / "pyproject.toml"
    if not pyproject_path.exists():
        raise FileNotFoundError(f"pyproject.toml not found in {repo_path}")

    with open(pyproject_path, encoding="utf-8") as f:
        raw_data = tomlkit.load(f)

    return PyprojectConfig.from_dict(raw_data)


def write_pyproject(repo_path: Path, config: PyprojectConfig) -> None:
    """Write pyproject.toml from typed configuration.

    Args:
        repo_path: Path to repository.
        config: Typed configuration to write.
    """
    pyproject_path = repo_path / "pyproject.toml"
    with open(pyproject_path, "w", encoding="utf-8") as f:
        tomlkit.dump(config.to_dict(), f)


def _contains_c_files(dir_path: Path, c_extensions: set[str]) -> bool:
    """Check if directory contains any C/C++ source files.

    Args:
        dir_path: Directory path to check.
        c_extensions: Set of file extensions to check (.c, .h, .cpp, etc.).

    Returns:
        True if directory contains at least one file with a C/C++ extension.
    """
    return any(file_path.suffix in c_extensions for file_path in dir_path.rglob("*"))


def _detect_c_code_from_explicit(repo_path: Path, explicit_dirs: list[str], c_extensions: set[str]) -> list[Path]:
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
        if dir_path.exists() and dir_path.is_dir() and _contains_c_files(dir_path, c_extensions):
            found_dirs.append(dir_path)
    return found_dirs


def _detect_c_code_from_env(repo_path: Path, env_dirs: str, c_extensions: set[str]) -> list[Path]:
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
        if dir_path.exists() and dir_path.is_dir() and _contains_c_files(dir_path, c_extensions):
            found_dirs.append(dir_path)
    return found_dirs


def _detect_c_code_from_config(repo_path: Path, pyproject: PyprojectConfig, c_extensions: set[str]) -> list[Path]:
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

    with suppress(subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
        result = subprocess.run(
            [git_cmd, "ls-files"], cwd=repo_path, capture_output=True, text=True, check=True, timeout=10
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
            found_dirs: list[Path] = []
            for dir_path in sorted(c_dirs):
                if dir_path.exists() and dir_path.is_dir() and _contains_c_files(dir_path, c_extensions):
                    found_dirs.append(dir_path)
            return found_dirs
    return []


def detect_c_code(
    repo_path: Path, explicit_dirs: list[str] | None = None, pyproject: PyprojectConfig | None = None
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
        found_dirs = _detect_c_code_from_explicit(repo_path, explicit_dirs, c_extensions)
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
    if source_dir.exists() and source_dir.is_dir() and _contains_c_files(source_dir, c_extensions):
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
    ruff: TomlTable = cast(TomlTable, ruff_raw) if isinstance(ruff_raw, dict) else {}
    tool["ruff"] = ruff

    # Ensure tool.ruff.lint exists and is a table
    lint_raw = ruff.get("lint")
    lint: TomlTable = lint_raw if isinstance(lint_raw, dict) else {}
    ruff["lint"] = lint

    # Ensure tool.ruff.lint.select exists and is a list of strings
    select_raw = lint.get("select")
    select: list[str] = [s for s in select_raw if isinstance(s, str)] if isinstance(select_raw, list) else []
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
) -> None:
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

    Raises:
        CLIError: If existing YAML cannot be parsed or merge fails
    """
    env = Environment(keep_trailing_newline=True, autoescape=True)
    template = env.from_string(MKDOCS_YML_TEMPLATE)

    # Convert absolute Path objects to relative string paths for template
    c_source_dirs_relative = [str(path.relative_to(repo_path)) for path in c_source_dirs]

    # Prepare CLI module information for template
    cli_modules_list = cli_modules if cli_modules else []
    cli_nav_items: list[dict[str, str]] = []
    if cli_modules_list:
        for cli_module in cli_modules_list:
            module_parts = cli_module.split(".")
            friendly_name = "-".join(module_parts[1:]) if len(module_parts) > 1 else module_parts[0]
            display_name = " ".join(word.capitalize() for word in friendly_name.split("-"))
            filename = f"cli-api-{friendly_name}.md" if len(cli_modules_list) > 1 else "cli-api.md"
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

    if mkdocs_path.exists():
        # File exists - perform smart merge
        merged_content, changes = merge_mkdocs_yaml(mkdocs_path, content)
        _ = mkdocs_path.write_text(merged_content)
        display_file_changes(mkdocs_path, changes)
    else:
        # New file - create fresh
        _ = mkdocs_path.write_text(content)
        console.print(f"[green]:white_check_mark:[/green] Created {mkdocs_path.name}")


def _is_pages_job(job: dict[str, object]) -> bool:
    """Check if a job is a GitHub Pages deployment job.

    Args:
        job: Job dictionary.

    Returns:
        True if job is a Pages deployment job.
    """
    # Check steps for actions/deploy-pages
    steps: list[object] = cast(list[object], job.get("steps", []))
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
    steps: list[object] = cast(list[object], job.get("steps", []))
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
    yaml = YAML()
    with suppress(YAMLError, OSError):
        workflow_content = workflow_file.read_text(encoding="utf-8")
        workflow = yaml.load(workflow_content)

        if not isinstance(workflow, dict) or "jobs" not in workflow:
            return False

        jobs = cast(dict[str, object], workflow.get("jobs", {}))

        for job_name, job in jobs.items():
            if not isinstance(job, dict):
                continue

            # Cast job to dict[str, object] for helper functions
            job_dict = cast(dict[str, object], job)

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
                if inc.local == ".gitlab/workflows/pages.gitlab-ci.yml":
                    console.print("[green]Found existing pages workflow include in '.gitlab-ci.yml'.[/green]")
                    return True
            elif inc == ".gitlab/workflows/pages.gitlab-ci.yml":
                console.print("[green]Found existing pages workflow include in '.gitlab-ci.yml'.[/green]")
                return True

    return False


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

    # Write pages workflow file
    if not pages_workflow_path.exists():
        _ = pages_workflow_path.write_text(GITLAB_CI_PAGES_TEMPLATE, encoding="utf-8")
        console.print(f"[green]:white_check_mark: Created {pages_workflow_path.relative_to(repo_path)}[/green]")
    else:
        console.print(f"[yellow]Skipping {pages_workflow_path.relative_to(repo_path)} (already exists)[/yellow]")

    # Check for existing include
    if _check_existing_gitlab_ci(gitlab_ci_path):
        return

    include_entry: dict[str, str] = {"local": ".gitlab/workflows/pages.gitlab-ci.yml"}

    if gitlab_ci_path.exists():
        # Modify existing file
        try:
            if GitLabCIConfig.add_include_and_save(gitlab_ci_path, include_entry):
                console.print(f"[green]:white_check_mark: Added include to {gitlab_ci_path.name}[/green]")
            else:
                # Fallback to append if structure is weird
                with gitlab_ci_path.open("a", encoding="utf-8") as f:
                    f.write("\ninclude:\n  - local: .gitlab/workflows/pages.gitlab-ci.yml\n")
                console.print(f"[green]:white_check_mark: Appended include to {gitlab_ci_path.name}[/green]")

        except (YAMLError, OSError):
            # Fallback to append
            with gitlab_ci_path.open("a", encoding="utf-8") as f:
                f.write("\ninclude:\n  - local: .gitlab/workflows/pages.gitlab-ci.yml\n")
            console.print(f"[green]:white_check_mark: Appended include to {gitlab_ci_path.name}[/green]")
    else:
        # Create new file
        initial_content = "include:\n  - local: .gitlab/workflows/pages.gitlab-ci.yml\n"
        _ = gitlab_ci_path.write_text(initial_content, encoding="utf-8")
        console.print(f"[green]:white_check_mark: Created {gitlab_ci_path.name}[/green]")


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
        console.print(f"[yellow]  Preserving existing {index_path.name}[/yellow]")
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
    repo_path: Path, project_name: str, c_source_dirs: list[Path], cli_modules: list[str] | None = None
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
            friendly_name = "-".join(module_parts[1:]) if len(module_parts) > 1 else module_parts[0]

            cli_content = cli_template.render(
                project_name=project_name, package_name=package_name, cli_module=cli_module
            )
            filename = f"cli-api-{friendly_name}.md" if len(cli_modules) > 1 else "cli-api.md"
            _ = (generated_dir / filename).write_text(cli_content)


def create_generated_content(
    repo_path: Path,
    project_name: str,
    c_source_dirs: list[Path],
    cli_modules: list[str],
    has_private_registry: bool,
    private_registry_url: str | None,
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
    """
    generated_dir = repo_path / "docs" / "generated"
    generated_dir.mkdir(parents=True, exist_ok=True)

    # index-features.md
    features: list[str] = []
    features.append("## Key Features\n")
    features.append("- **[Python API Reference](python-api.md)** - Complete API documentation")

    if cli_modules:
        if len(cli_modules) == 1:
            features.append("- **[CLI Reference](cli-api.md)** - Command-line interface")
        else:
            # Multiple CLI apps - link to each one
            features.append("- **CLI References:**")
            for cli_module in cli_modules:
                module_parts = cli_module.split(".")
                friendly_name = "-".join(module_parts[1:]) if len(module_parts) > 1 else module_parts[0]
                # Create a nice display name (e.g., "tool2-main" -> "Tool2 Main")
                display_name = " ".join(word.capitalize() for word in friendly_name.split("-"))
                features.append(f"  - **[{display_name}](cli-api-{friendly_name}.md)** - CLI interface")

    if c_source_dirs:
        features.append("- **[C API Reference](c-api.md)** - C/C++ API documentation")

    features_content = "\n".join(features) + "\n"
    _ = (generated_dir / "index-features.md").write_text(features_content)

    # install-command.md
    if has_private_registry and private_registry_url:
        # Private registry installation
        install_content = f"""To install from the private registry:

```bash
uv add --index="{private_registry_url}" {project_name}
```
"""
    else:
        # Standard installation
        install_content = f"""To install the package:

```bash
uv add {project_name}
```
"""

    _ = (generated_dir / "install-command.md").write_text(install_content)


def update_gitignore(repo_path: Path, provider: CIProvider, include_generated: bool = False) -> None:
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

    # Only include docs/generated/ if explicitly requested (backward compatibility for setup)
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
            line.strip() == entry or line.strip() == normalized_entry or line.strip() == f"/{normalized_entry}"
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
    }

    # Create install.md (only if doesn't exist - preserve user customizations)
    install_path = docs_dir / "install.md"
    if not install_path.exists():
        install_template = env.from_string(INSTALL_MD_TEMPLATE)
        install_content = install_template.render(**template_context)
        _ = install_path.write_text(install_content)
    else:
        console.print(f"[yellow]  Preserving existing {install_path.name}[/yellow]")


def _ensure_mkapidocs_dependency(config: TomlTable, dep_spec: str, pyproject_path: Path, repo_path: Path) -> None:
    """Ensure mkapidocs is in dependency-groups."""
    # Initialize dependency-groups if it doesn't exist
    if "dependency-groups" not in config:
        config["dependency-groups"] = {}

    # Get dependency-groups as a properly typed dict
    dep_groups_raw = config.get("dependency-groups")
    if not isinstance(dep_groups_raw, dict):
        dep_groups: TomlTable = {}
        config["dependency-groups"] = dep_groups
    else:
        dep_groups = dep_groups_raw

    # Initialize dev group if it doesn't exist
    if "dev" not in dep_groups:
        dep_groups["dev"] = []

    # Convert to list if it's not already
    raw_dev_deps = dep_groups.get("dev")
    if not isinstance(raw_dev_deps, list):
        dev_deps: list[str] = []
        dep_groups["dev"] = dev_deps
    else:
        # Cast to known type and filter to strings
        typed_list = cast(list[TomlValue], raw_dev_deps)
        dev_deps = [str(dep) for dep in typed_list if isinstance(dep, str)]

    # Check if mkapidocs is already in dependencies
    has_mkapidocs = any(dep.startswith("mkapidocs") or "mkapidocs" in dep for dep in dev_deps)

    if not has_mkapidocs:
        # Add mkapidocs with local path
        new_dep = f"mkapidocs @ file://{dep_spec}"
        dev_deps.append(new_dep)
        # Update config with the new dependency list
        dep_groups["dev"] = dev_deps

        # Write updated pyproject.toml
        with open(pyproject_path, "w", encoding="utf-8") as f:
            tomlkit.dump(config, f)

        console.print(f"[green]:white_check_mark: Added mkapidocs to {repo_path}/pyproject.toml[/green]")

        # Run uv sync to install mkapidocs in target project
        if uv_cmd := which("uv"):
            console.print("[blue]Installing mkapidocs in target project environment...[/blue]")
            result = subprocess.run([uv_cmd, "sync"], cwd=repo_path, capture_output=True, text=True, check=False)
            if result.returncode == 0:
                console.print("[green]:white_check_mark: Successfully installed mkapidocs in target project[/green]")
            else:
                console.print(f"[yellow]:warning: Failed to sync dependencies: {result.stderr}[/yellow]")
        else:
            console.print("[yellow]:warning: uv command not found, skipping sync[/yellow]")
    else:
        console.print("[blue]:information: mkapidocs already in target project dependencies[/blue]")


def add_mkapidocs_to_target_project(repo_path: Path) -> None:
    """Add mkapidocs to target project's dev dependencies.

    Adds mkapidocs to the target project's [dependency-groups] dev section
    and runs uv sync to install it in the project's environment.

    Args:
        repo_path: Path to target repository.
    """
    pyproject_path = repo_path / "pyproject.toml"
    if not pyproject_path.exists():
        console.print("[yellow]:warning: No pyproject.toml found, skipping mkapidocs installation[/yellow]")
        return

    try:
        # Read current pyproject.toml
        with open(pyproject_path, encoding="utf-8") as f:
            config = tomlkit.load(f)

        # Get the path to mkapidocs (this package)
        # First try to find it in the current environment
        mkapidocs_path = Path(__file__).parent.parent.parent

        # Check if we're in a development environment or installed
        if (mkapidocs_path / "pyproject.toml").exists():
            # Development mode - use local path
            dep_spec = str(mkapidocs_path.absolute())
            _ensure_mkapidocs_dependency(config, dep_spec, pyproject_path, repo_path)
        else:
            # Installed mode - will need to use git URL or PyPI when available
            # For now, skip if not in dev mode
            console.print(
                "[yellow]:warning: mkapidocs not in development mode, skipping installation in target[/yellow]"
            )

    except (OSError, exceptions.ParseError):
        console.print("[red]:warning: Failed to read pyproject.toml[/red]")
    except Exception as e:
        console.print(f"[yellow]:warning: Failed to add mkapidocs to target project: {e}[/yellow]")


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


def _detect_provider_and_url(
    repo_path: Path, provider: CIProvider | None, github_url_base: str | None
) -> tuple[CIProvider, str]:
    """Detect CI provider and site URL.

    Args:
        repo_path: Path to repository.
        provider: Explicitly provided CI provider (or None).
        github_url_base: Explicitly provided GitHub URL base (or None).

    Returns:
        Tuple containing (detected_provider, site_url).
    """
    import typer

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
            display_message(error_message, MessageType.ERROR, title="Provider Detection Failed")
            raise typer.Exit(1)

    # Detect site URL based on provider
    if provider == CIProvider.GITHUB:
        if github_url_base is None:
            github_url_base = detect_github_url_base(repo_path)
            if github_url_base is None:
                raise ValueError(
                    "Could not auto-detect GitHub URL from git remote. Please provide --github-url-base option."
                )
        site_url = github_url_base.rstrip("/")
    else:  # provider == CIProvider.GITLAB
        gitlab_url_base = detect_gitlab_url_base(repo_path)
        if gitlab_url_base is None:
            # Try to construct from repo name if auto-detection fails
            # This is a fallback - users can manually edit mkdocs.yml later
            site_url = f"https://example.gitlab.io/{repo_path.name}"
            console.print(
                f"[yellow]:warning: Could not auto-detect GitLab Pages URL. Using placeholder: {site_url}[/yellow]"
            )
        else:
            site_url = gitlab_url_base.rstrip("/")

    return provider, site_url


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
    import typer

    c_source_dirs_list = detect_c_code(repo_path, explicit_dirs=c_source_dirs, pyproject=pyproject)
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
            display_message(error_message, MessageType.ERROR, title="Typer CLI Not Found")
            raise typer.Exit(1)

    return c_source_dirs_list, cli_modules, has_typer, has_private_registry, private_registry_url


def setup_documentation(
    repo_path: Path,
    provider: CIProvider | None = None,
    github_url_base: str | None = None,
    c_source_dirs: list[str] | None = None,
) -> CIProvider:
    """Set up MkDocs documentation for a Python repository.

    Args:
        repo_path: Path to repository.
        provider: CI/CD provider (auto-detected if None).
        github_url_base: Base URL for GitHub Pages (deprecated, for backward compatibility).
        c_source_dirs: Optional list of C/C++ source directories from CLI.

    Returns:
        The CI provider that was used for setup.

    Raises:
        ValueError: If provider cannot be auto-detected.
        typer.Exit: If setup fails.
    """
    pyproject = read_pyproject(repo_path)

    project_name, description, license_name = _get_project_info(pyproject)
    provider, site_url = _detect_provider_and_url(repo_path, provider, github_url_base)
    c_source_dirs_list, cli_modules, _, has_private_registry, private_registry_url = _detect_features(
        repo_path, pyproject, c_source_dirs
    )

    # has_typer_cli flag is True if CLI modules were actually detected
    has_typer_cli = len(cli_modules) > 0

    create_mkdocs_config(repo_path, project_name, site_url, c_source_dirs_list, has_typer_cli, provider, cli_modules)

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
        repo_path, project_name, c_source_dirs_list, cli_modules, has_private_registry, private_registry_url
    )
    create_supporting_docs(
        repo_path, project_name, pyproject, c_source_dirs_list, has_typer_cli, site_url, git_url=None
    )

    update_gitignore(repo_path, provider)

    # Add mkapidocs to target project's dev dependencies
    add_mkapidocs_to_target_project(repo_path)

    return provider
