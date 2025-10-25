"""Core documentation setup functionality."""

import re
import subprocess
import tomllib
from pathlib import Path

import tomli_w
from jinja2 import Environment, FileSystemLoader


def detect_gitlab_url_base(repo_path: Path) -> str | None:
    """Detect GitLab Pages URL base from git remote.

    Args:
        repo_path: Path to repository.

    Returns:
        GitLab Pages URL base or None if not detected.

    Example:
        git@sourcery.assaabloy.net:aehgfw/tools/python_picotool.git
        -> https://aehgfw.sourcery.assaabloy.net/tools/
    """
    try:
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            check=True,
        )
        remote_url = result.stdout.strip()

        # Parse SSH format: git@host:group/subgroup/project.git
        ssh_match = re.match(r"git@([^:]+):(.+)/([^/]+)\.git", remote_url)
        if ssh_match:
            host = ssh_match.group(1)
            group_path = ssh_match.group(2)
            # Split group path: aehgfw/tools -> aehgfw, tools
            parts = group_path.split("/")
            if len(parts) >= 2:
                subdomain = parts[0]
                path = "/".join(parts[1:])
                return f"https://{subdomain}.{host}/{path}/"

        # Parse HTTPS format: https://host/group/subgroup/project.git
        https_match = re.match(r"https://([^/]+)/(.+)/([^/]+)\.git", remote_url)
        if https_match:
            host = https_match.group(1)
            group_path = https_match.group(2)
            parts = group_path.split("/")
            if len(parts) >= 2:
                subdomain = parts[0]
                path = "/".join(parts[1:])
                return f"https://{subdomain}.{host}/{path}/"

        return None

    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def read_pyproject(repo_path: Path) -> dict:
    """Read and parse pyproject.toml.

    Args:
        repo_path: Path to repository.

    Returns:
        Parsed pyproject.toml contents.

    Raises:
        FileNotFoundError: If pyproject.toml does not exist.
    """
    pyproject_path = repo_path / "pyproject.toml"
    if not pyproject_path.exists():
        raise FileNotFoundError(f"pyproject.toml not found in {repo_path}")

    with open(pyproject_path, "rb") as f:
        return tomllib.load(f)


def write_pyproject(repo_path: Path, config: dict) -> None:
    """Write pyproject.toml.

    Args:
        repo_path: Path to repository.
        config: Configuration dictionary to write.
    """
    pyproject_path = repo_path / "pyproject.toml"
    with open(pyproject_path, "wb") as f:
        tomli_w.dump(config, f)


def detect_c_code(repo_path: Path) -> bool:
    """Detect if repository contains C/C++ source code.

    Args:
        repo_path: Path to repository.

    Returns:
        True if C/C++ files found in source/ directory.
    """
    source_dir = repo_path / "source"
    if not source_dir.exists():
        return False

    c_extensions = {".c", ".h", ".cpp", ".hpp", ".cc", ".hh"}
    return any(file_path.suffix in c_extensions for file_path in source_dir.rglob("*"))


def detect_typer_dependency(pyproject: dict) -> bool:
    """Detect if project depends on Typer.

    Args:
        pyproject: Parsed pyproject.toml.

    Returns:
        True if typer found in dependencies.
    """
    dependencies = pyproject.get("project", {}).get("dependencies", [])
    return any(dep.strip().lower().startswith("typer") for dep in dependencies)


def update_ruff_config(pyproject: dict) -> dict:
    """Add docstring linting rules to ruff configuration.

    Args:
        pyproject: Parsed pyproject.toml.

    Returns:
        Updated pyproject configuration.
    """
    if "tool" not in pyproject:
        pyproject["tool"] = {}
    if "ruff" not in pyproject["tool"]:
        pyproject["tool"]["ruff"] = {}
    if "lint" not in pyproject["tool"]["ruff"]:
        pyproject["tool"]["ruff"]["lint"] = {}
    if "select" not in pyproject["tool"]["ruff"]["lint"]:
        pyproject["tool"]["ruff"]["lint"]["select"] = []

    select = pyproject["tool"]["ruff"]["lint"]["select"]
    if "DOC" not in select:
        select.append("DOC")
    if "D" not in select:
        select.append("D")

    return pyproject


def add_docs_dependencies(pyproject: dict, has_c_code: bool) -> dict:
    """Add documentation dependencies to pyproject.toml.

    Args:
        pyproject: Parsed pyproject.toml.
        has_c_code: Whether repository contains C/C++ code.

    Returns:
        Updated pyproject configuration.
    """
    if "project" not in pyproject:
        pyproject["project"] = {}
    if "optional-dependencies" not in pyproject["project"]:
        pyproject["project"]["optional-dependencies"] = {}

    docs_deps = [
        "mkdocs",
        "mkdocs-material",
        "mkdocs-typer2",
        "mkdocstrings[python]",
        "mkdocs-mermaid2-plugin",
        "termynal",
        "mkdocs-recently-updated-docs",
    ]

    if has_c_code:
        docs_deps.append("mkdoxy")

    pyproject["project"]["optional-dependencies"]["docs"] = docs_deps
    return pyproject


def create_mkdocs_config(repo_path: Path, project_name: str, site_url: str, has_c_code: bool, has_typer: bool) -> None:
    """Create mkdocs.yml configuration file.

    Args:
        repo_path: Path to repository.
        project_name: Name of the project.
        site_url: Full URL for GitLab Pages site.
        has_c_code: Whether repository contains C/C++ code.
        has_typer: Whether repository uses Typer.
    """
    template_dir = Path(__file__).parent / "templates"
    # S701: autoescape not needed - generating YAML config files, not HTML
    env = Environment(loader=FileSystemLoader(template_dir))  # noqa: S701
    template = env.get_template("mkdocs.yml.j2")

    content = template.render(project_name=project_name, site_url=site_url, has_c_code=has_c_code, has_typer=has_typer)

    mkdocs_path = repo_path / "mkdocs.yml"
    mkdocs_path.write_text(content)


def create_gitlab_ci(repo_path: Path) -> None:
    """Create or update .gitlab/workflows/pages.gitlab-ci.yml.

    Args:
        repo_path: Path to repository.
    """
    gitlab_dir = repo_path / ".gitlab" / "workflows"
    gitlab_dir.mkdir(parents=True, exist_ok=True)

    template_dir = Path(__file__).parent / "templates"
    # S701: autoescape not needed - generating YAML config files, not HTML
    env = Environment(loader=FileSystemLoader(template_dir))  # noqa: S701
    template = env.get_template("gitlab-ci.yml.j2")

    content = template.render()

    ci_path = gitlab_dir / "pages.gitlab-ci.yml"
    ci_path.write_text(content)


def create_index_page(repo_path: Path, project_name: str, description: str) -> None:
    """Create docs/index.md homepage.

    Args:
        repo_path: Path to repository.
        project_name: Name of the project.
        description: Project description from pyproject.toml.
    """
    docs_dir = repo_path / "docs"
    docs_dir.mkdir(exist_ok=True)

    template_dir = Path(__file__).parent / "templates"
    # S701: autoescape not needed - generating Markdown documentation, not HTML
    env = Environment(loader=FileSystemLoader(template_dir))  # noqa: S701
    template = env.get_template("index.md.j2")

    content = template.render(project_name=project_name, description=description)

    index_path = docs_dir / "index.md"
    index_path.write_text(content)


def create_api_reference(repo_path: Path, project_name: str, has_c_code: bool) -> None:
    """Create API reference documentation pages.

    Args:
        repo_path: Path to repository.
        project_name: Name of the project.
        has_c_code: Whether repository contains C/C++ code.
    """
    reference_dir = repo_path / "docs" / "reference"
    reference_dir.mkdir(parents=True, exist_ok=True)

    template_dir = Path(__file__).parent / "templates"
    # S701: autoescape not needed - generating Markdown documentation, not HTML
    env = Environment(loader=FileSystemLoader(template_dir))  # noqa: S701

    python_template = env.get_template("python_api.md.j2")
    package_name = project_name.replace("-", "_")
    python_content = python_template.render(package_name=package_name)
    (reference_dir / "python.md").write_text(python_content)

    if has_c_code:
        c_template = env.get_template("c_api.md.j2")
        c_content = c_template.render(project_name=project_name)
        (reference_dir / "c.md").write_text(c_content)


def setup_documentation(repo_path: Path, gitlab_url_base: str | None = None) -> None:
    """Set up MkDocs documentation for a Python repository.

    Args:
        repo_path: Path to repository.
        gitlab_url_base: Base URL for GitLab Pages. If None, auto-detect from git remote.

    Raises:
        ValueError: If gitlab_url_base is None and auto-detection fails.
    """
    pyproject = read_pyproject(repo_path)

    project_name = pyproject.get("project", {}).get("name", repo_path.name)
    description = pyproject.get("project", {}).get("description", "")

    # Auto-detect GitLab URL if not provided
    if gitlab_url_base is None:
        gitlab_url_base = detect_gitlab_url_base(repo_path)
        if gitlab_url_base is None:
            raise ValueError(
                "Could not auto-detect GitLab URL from git remote. "
                "Please provide --gitlab-url-base option."
            )

    site_url = f"{gitlab_url_base.rstrip('/')}/{project_name}/"

    has_c_code = detect_c_code(repo_path)
    has_typer = detect_typer_dependency(pyproject)

    pyproject = update_ruff_config(pyproject)
    pyproject = add_docs_dependencies(pyproject, has_c_code)
    write_pyproject(repo_path, pyproject)

    create_mkdocs_config(repo_path, project_name, site_url, has_c_code, has_typer)
    create_gitlab_ci(repo_path)
    create_index_page(repo_path, project_name, description)
    create_api_reference(repo_path, project_name, has_c_code)
