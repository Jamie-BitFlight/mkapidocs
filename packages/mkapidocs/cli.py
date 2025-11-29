"""mkapidocs - Automated documentation setup for Python projects.

This script sets up MkDocs documentation for Python repositories with auto-detection
of features like C/C++ code and Typer CLI interfaces.
"""

from __future__ import annotations

import os
import platform
import re
import subprocess
import tarfile
import tomllib
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from shutil import which
from typing import Annotated, Any

import httpx
import tomli_w
import typer
import yaml
from jinja2 import Environment
from rich import box
from rich.console import Console
from rich.measure import Measurement
from rich.panel import Panel
from rich.table import Table

# Initialize Rich console
console = Console()

# Initialize Typer app
app = typer.Typer(
    name="python-docs-init",
    help="Automated documentation setup tool for Python projects using MkDocs and GitHub Pages",
    add_completion=False,
    rich_markup_mode="rich",
)


# ============================================================================
# Template Strings (inline Jinja2 templates)
# ============================================================================

MKDOCS_YML_TEMPLATE = """site_name: {{ project_name }}
site_url: {{ site_url }}
{% if ci_provider == 'gitlab' %}
site_dir: public
{% else %}
site_dir: site
{% endif %}

theme:
  name: material
  features:
    - navigation.tabs
    - navigation.sections
    - navigation.expand
    - navigation.top
    - search.suggest
    - search.highlight
    - content.code.copy
  palette:
    - scheme: default
      primary: indigo
      accent: indigo
      toggle:
        icon: material/brightness-7
        name: Switch to dark mode
    - scheme: slate
      primary: indigo
      accent: indigo
      toggle:
        icon: material/brightness-4
        name: Switch to light mode

plugins:
  - search
  - gen-files:
      scripts:
        - docs/generated/gen_ref_pages.py
  - literate-nav:
      nav_file: SUMMARY.md
  - mkdocstrings:
      handlers:
        python:
          options:
            docstring_style: google
            show_source: true
            show_root_heading: true
            show_category_heading: true
            members_order: source
{% if has_typer %}
  - mkdocs-typer2
{% endif %}
{% if c_source_dirs %}
  - mkdoxy:
      projects:
        {{ project_name }}:
          src-dirs: {{ c_source_dirs | join(' ') }}
          full-doc: True
          doxy-cfg:
            FILE_PATTERNS: "*.c *.h *.cpp *.hpp"
            RECURSIVE: True
            EXTRACT_ALL: True
{% endif %}
  - mermaid2
  - termynal
  - recently-updated:
      limit: 10
      exclude:
        - index.md

markdown_extensions:
  - admonition
  - pymdownx.details
  - pymdownx.superfences:
      custom_fences:
        - name: mermaid
          class: mermaid
          format: !!python/name:mermaid2.fence_mermaid_custom
  - pymdownx.highlight:
      anchor_linenums: true
  - pymdownx.inlinehilite
  - pymdownx.snippets
  - pymdownx.tabbed:
      alternate_style: true
  - tables
  - attr_list
  - md_in_html

nav:
  - Home: index.md
  - About: about.md
  - Getting Started:
    - Installation: install.md
  - API Reference:
    - Python API: generated/python-api.md
{% if c_source_dirs %}
    - C API: generated/c-api.md
{% endif %}
{% if has_typer %}
{% if cli_modules|length == 1 %}
    - CLI Reference: generated/{{ cli_modules[0].filename }}
{% else %}
    - CLI Reference:
{% for cli_item in cli_modules %}
      - {{ cli_item.display_name }}: generated/{{ cli_item.filename }}
{% endfor %}
{% endif %}
{% endif %}
  - Repository Files: repository/SUMMARY.md
"""

GITHUB_ACTIONS_PAGES_TEMPLATE = """name: Deploy Documentation

"on":
  push:
    branches:
      - main

permissions:
  contents: read
  pages: write
  id-token: write

concurrency:
  group: "pages"
  cancel-in-progress: false

jobs:
  build:
    name: Build Documentation
    runs-on: ubuntu-latest
    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install uv
        uses: astral-sh/setup-uv@v4

      - name: Build documentation
        run: ./mkapidocs.py build . --strict

      - name: Upload artifact
        uses: actions/upload-pages-artifact@v3
        with:
          path: ./site

  deploy:
    name: Deploy to GitHub Pages
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    runs-on: ubuntu-latest
    needs: build
    steps:
      - name: Deploy to GitHub Pages
        id: deployment
        uses: actions/deploy-pages@v4
"""

GITLAB_CI_PAGES_TEMPLATE = """pages:
  stage: deploy
  image: ghcr.io/astral-sh/uv:python3.11
  script:
    - ./mkapidocs.py build . --strict
  artifacts:
    paths:
      - public
  rules:
    - if: $CI_COMMIT_BRANCH == $CI_DEFAULT_BRANCH
"""

INDEX_MD_TEMPLATE = """# {{ project_name }}

{{ description }}

--8<-- "generated/index-features.md"

## Quick Start

```bash
uv pip install {{ project_name }}
```

--8<-- "generated/install-registry.md"

For detailed installation instructions, see the [Installation Guide](install.md).

## Recently Updated

<!-- RECENTLY_UPDATED_DOCS -->

## License

{{ license }}
"""

CLI_MD_TEMPLATE = """# CLI Reference

Command-line interface documentation for {{ project_name }}.

## Commands

::: mkdocs-typer2
    :module: {{ cli_module }}
    :name: {{ package_name }}
"""

PYTHON_API_MD_TEMPLATE = """# Python API Reference

::: {{ package_name }}
    options:
      show_source: true
      members_order: source
"""

C_API_MD_TEMPLATE = """# C API Reference

Documentation generated from C source files using Doxygen.

{{ '{{' }} mkdoxy('{{ project_name }}') {{ '}}' }}
"""

GEN_REF_PAGES_PY = '''"""Generate documentation pages from nested markdown files."""

from pathlib import Path

import mkdocs_gen_files

# Root of the repository
root = Path.cwd()

# Find all markdown files outside docs/ directory
markdown_files = []
for md_path in root.rglob("*.md"):
    # Skip files in these directories
    skip_dirs = {".venv", "site", "docs", ".git", "__pycache__", ".pytest_cache", "node_modules"}
    if any(part.startswith(".") or part in skip_dirs for part in md_path.parts):
        continue

    # Skip if file is in docs directory
    try:
        md_path.relative_to(root / "docs")
        continue
    except ValueError:
        pass

    markdown_files.append(md_path)

# Build navigation structure
nav_structure = {}
doc_paths = []

# Create virtual docs for each discovered markdown file
for md_path in sorted(markdown_files):
    # Get relative path from root
    rel_path = md_path.relative_to(root)

    # Create a virtual doc path in the "Repository Files" section
    if rel_path.name == "README.md":
        # For README.md files, use the directory name
        # Root README.md becomes about.md, nested ones become index.md in their directory
        doc_path = f"repository/{'/'.join(rel_path.parts[:-1])}/index.md" if len(rel_path.parts) > 1 else "about.md"
    else:
        # For other .md files, keep their name
        doc_path = f"repository/{rel_path}"

    # Read the original file and write to virtual doc
    with mkdocs_gen_files.open(doc_path, "w") as f:
        content = md_path.read_text()
        # Add a breadcrumb header
        f.write(f"# {rel_path}\\n\\n")
        f.write(content)

    # Set edit path to point to the original file
    mkdocs_gen_files.set_edit_path(doc_path, rel_path)

    doc_paths.append((rel_path, doc_path))

# Generate SUMMARY.md for literate-nav
with mkdocs_gen_files.open("repository/SUMMARY.md", "w") as nav_file:
    nav_file.write("# Repository Files\\n\\n")

    # Group by directory
    current_dir = None
    for rel_path, doc_path in sorted(doc_paths):
        parent_dir = str(rel_path.parent) if rel_path.parent != Path(".") else "Root"

        # Write directory header
        if current_dir != parent_dir:
            current_dir = parent_dir
            nav_file.write(f"\\n## {parent_dir}\\n\\n")

        # Write file link
        # Remove 'repository/' prefix from doc_path for the link
        link_path = doc_path.replace("repository/", "")
        nav_file.write(f"- [{rel_path.name}]({link_path})\\n")
'''

# Additional template strings for install.md, quick-start-guide.md, etc.
# These are truncated for brevity - include full content
INSTALL_MD_TEMPLATE = """# Installation

This guide provides detailed installation instructions for {{ project_name }}.

## Prerequisites

- Python {{ requires_python if requires_python else "3.11+" }}
- uv package manager
- Git (for development installation)
{% if has_private_registry %}
- Registry credentials (for private registry access)
{% endif %}

## Quick Install

{% if has_private_registry %}
To add {{ project_name }} as a dependency to your project from the private registry:

### Method 1: Inline Registry Flag (Recommended for Quick Setup)

```bash
uv add --index="{{ private_registry_url }}" {{ project_name }}
```

### Method 2: Configure Registry in pyproject.toml (Recommended for Projects)

First, add the private registry to your `pyproject.toml`:

```toml
[tool.uv]
index = [
    { url = "{{ private_registry_url }}", name = "private" }
]
```

Then install normally:

```bash
uv add {{ project_name }}
```

For more details on uv registry configuration, see the [uv documentation](https://docs.astral.sh/uv/reference/settings/).
{% else %}
To add {{ project_name }} as a dependency to your project:

```bash
uv add {{ project_name }}
```
{% endif %}

## Development Installation

For development work, clone the repository and install with all dependencies:

```bash
# Clone the repository
git clone {{ git_url if git_url else "REPOSITORY_URL" }}
cd {{ project_name }}

# Install with all dependencies
uv sync --all-extras

# Or install specific extras
uv sync --extra dev
```
{% if c_source_dirs %}

## Building C Extensions

This project includes C/C++ extensions. A C compiler is required:

**Linux/macOS:**
- GCC or Clang should be available by default
- Install build-essential on Ubuntu/Debian: `sudo apt install build-essential`

**Windows:**
- Install Microsoft Visual C++ Build Tools
- Or use MinGW-w64
{% endif %}

## Verification

Verify the installation:

```bash
# Check installed version
python -c "from importlib.metadata import version; print(version('{{ project_name }}'))"
{% if has_typer %}

# Display CLI help
{{ project_name }} --help
{% endif %}
```

## Troubleshooting

### Common Issues

**Import Error**

If you get an import error, ensure the package is installed in your active Python environment:

```bash
python -c "import {{ project_name.replace('-', '_') }}"
```

**Permission Error**

uv automatically manages virtual environments, so permission errors should not occur. If you encounter permission issues, ensure uv is properly installed:

```bash
# Verify uv installation
uv --version

# Add the package to your project
uv add {{ project_name }}
```
{% if c_source_dirs %}

**C Extension Build Failure**

If C extensions fail to build, ensure you have a working C compiler installed. See the "Building C Extensions" section above.
{% endif %}

## Uninstallation

To remove {{ project_name }} from your project:

```bash
uv remove {{ project_name }}
```

## Next Steps

- [API Reference](generated/python-api.md) - Explore the API documentation
{% if has_typer %}
- [CLI Reference](generated/cli-api.md) - Command-line interface documentation
{% endif %}
"""

# ============================================================================
# Exceptions and Message Types
# ============================================================================


class CLIError(Exception):
    """Base exception for CLI errors."""


class BuildError(Exception):
    """Exception raised when documentation build fails."""


class MessageType(Enum):
    """Message types with associated display styles."""

    ERROR = ("red", "Error")
    SUCCESS = ("green", "Success")
    INFO = ("blue", "Info")
    WARNING = ("yellow", "Warning")


class CIProvider(Enum):
    """CI/CD provider types."""

    GITHUB = "github"
    GITLAB = "gitlab"


# ============================================================================
# Validation Infrastructure
# ============================================================================


@dataclass
class ValidationResult:
    """Result of a validation check.

    Attributes:
        check_name: Name of the validation check
        passed: Whether the check passed
        message: Status message or error details
        value: Optional value (e.g., version string)
        required: Whether this check is required for operation
    """

    check_name: str
    passed: bool
    message: str
    value: str | None = None
    required: bool = True


class DoxygenInstaller:
    """Handles automatic Doxygen installation from GitHub releases."""

    GITHUB_API_URL = "https://api.github.com/repos/doxygen/doxygen/releases/latest"
    CACHE_DIR = Path.home() / ".cache" / "doxygen-binaries"
    INSTALL_DIR = Path.home() / ".local" / "bin"

    @classmethod
    def is_installed(cls) -> tuple[bool, str | None]:
        """Check if Doxygen is installed and get version.

        Returns:
            Tuple of (is_installed, version_string)
        """
        doxygen_path = which("doxygen")
        if not doxygen_path:
            return False, None

        try:
            result = subprocess.run([doxygen_path, "--version"], capture_output=True, text=True, check=True, timeout=5)
            version = result.stdout.strip()
            return True, version
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
            return False, None

    @classmethod
    def get_platform_asset_name(cls) -> str | None:
        """Determine correct Doxygen asset name for current platform.

        Returns:
            Asset name pattern to match, or None if platform not supported
        """
        system = platform.system().lower()
        machine = platform.machine().lower()

        match system:
            case "linux":
                if "x86_64" in machine or "amd64" in machine:
                    return "doxygen-*.linux.bin.tar.gz"
                return None
            case "windows":
                if "x86_64" in machine or "amd64" in machine:
                    return "doxygen-*-setup.exe"
                return None
            case "darwin":
                # macOS requires Homebrew, can't auto-install DMG
                return None
            case _:
                return None

    @classmethod
    def download_and_install(cls) -> tuple[bool, str]:
        """Download and install Doxygen from GitHub releases.

        Returns:
            Tuple of (success, message)
        """
        asset_pattern = cls.get_platform_asset_name()
        if asset_pattern is None:
            system = platform.system()
            if system == "Darwin":
                return False, "macOS detected: Please install Doxygen via Homebrew: brew install doxygen"
            return False, f"Unsupported platform: {system} {platform.machine()}"

        try:
            # Fetch latest release info
            console.print("[blue]Fetching Doxygen release information...[/blue]")
            with httpx.Client(timeout=30.0) as client:
                response = client.get(cls.GITHUB_API_URL)
                response.raise_for_status()
                release_data = response.json()

            # Find matching asset
            asset = None
            for asset_item in release_data.get("assets", []):
                # Match pattern with wildcard
                import fnmatch

                if fnmatch.fnmatch(asset_item["name"], asset_pattern):
                    asset = asset_item
                    break

            if not asset:
                return False, f"No matching asset found for pattern: {asset_pattern}"

            asset_name = asset["name"]
            asset_url = asset["browser_download_url"]

            # Extract SHA256 from API response (GitHub stores it in the API metadata)
            # Note: GitHub doesn't provide checksums in the public API for releases
            # We'll download but warn about verification
            console.print(f"[blue]Downloading {asset_name}...[/blue]")

            cls.CACHE_DIR.mkdir(parents=True, exist_ok=True)
            download_path = cls.CACHE_DIR / asset_name

            # Download file (follow redirects)
            with httpx.Client(timeout=300.0, follow_redirects=True) as client:
                with client.stream("GET", asset_url) as response:
                    response.raise_for_status()
                    with open(download_path, "wb") as f:
                        for chunk in response.iter_bytes(chunk_size=8192):
                            f.write(chunk)

            console.print(f"[green]Downloaded to {download_path}[/green]")

            # Extract and install (Linux only, Windows requires manual setup)
            if platform.system().lower() == "linux":
                return cls._install_linux_binary(download_path)

            return False, "Downloaded, but automatic installation only supported on Linux"

        except httpx.HTTPError as e:
            return False, f"HTTP error downloading Doxygen: {e}"
        except Exception as e:
            return False, f"Failed to install Doxygen: {e}"

    @classmethod
    def _install_linux_binary(cls, tarball_path: Path) -> tuple[bool, str]:
        """Extract and install Linux Doxygen binary.

        Args:
            tarball_path: Path to downloaded tar.gz file

        Returns:
            Tuple of (success, message)
        """
        try:
            # Extract tarball
            extract_dir = cls.CACHE_DIR / "extracted"
            extract_dir.mkdir(parents=True, exist_ok=True)

            console.print(f"[blue]Extracting {tarball_path.name}...[/blue]")
            with tarfile.open(tarball_path, "r:gz") as tar:
                tar.extractall(extract_dir)

            # Find doxygen binary in extracted files
            doxygen_bin = None
            for root, _dirs, files in os.walk(extract_dir):
                if "doxygen" in files:
                    doxygen_bin = Path(root) / "doxygen"
                    break

            if not doxygen_bin or not doxygen_bin.exists():
                return False, "Could not find doxygen binary in extracted archive"

            # Copy to install directory
            cls.INSTALL_DIR.mkdir(parents=True, exist_ok=True)
            install_path = cls.INSTALL_DIR / "doxygen"

            import shutil

            shutil.copy2(doxygen_bin, install_path)
            install_path.chmod(0o755)

            # Add to PATH for current process
            if str(cls.INSTALL_DIR) not in os.environ.get("PATH", ""):
                os.environ["PATH"] = f"{cls.INSTALL_DIR}:{os.environ.get('PATH', '')}"

            console.print(f"[green]Installed Doxygen to {install_path}[/green]")
            return True, f"Doxygen installed to {install_path}"

        except Exception as e:
            return False, f"Failed to extract/install: {e}"


class SystemValidator:
    """Validates system-level requirements."""

    @staticmethod
    def check_git() -> ValidationResult:
        """Check if git is installed.

        Returns:
            Validation result with git version
        """
        git_path = which("git")
        if not git_path:
            return ValidationResult(check_name="Git", passed=False, message="Not found - install git", required=True)

        try:
            result = subprocess.run([git_path, "--version"], capture_output=True, text=True, check=True, timeout=5)
            version = result.stdout.strip().replace("git version ", "")
            return ValidationResult(check_name="Git", passed=True, message="Installed", value=version, required=True)
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            return ValidationResult(
                check_name="Git", passed=False, message="Found but version check failed", required=True
            )

    @staticmethod
    def check_uv() -> ValidationResult:
        """Check if uv/uvx is installed.

        Returns:
            Validation result with uv version
        """
        uvx_path = which("uvx")
        if not uvx_path:
            return ValidationResult(
                check_name="uv/uvx",
                passed=False,
                message="Not found - install uv from https://docs.astral.sh/uv/",
                required=True,
            )

        try:
            result = subprocess.run([uvx_path, "--version"], capture_output=True, text=True, check=True, timeout=5)
            version = result.stdout.strip().replace("uvx ", "")
            return ValidationResult(check_name="uv/uvx", passed=True, message="Installed", value=version, required=True)
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            return ValidationResult(
                check_name="uv/uvx", passed=False, message="Found but version check failed", required=True
            )

    @staticmethod
    def check_doxygen() -> ValidationResult:
        """Check if Doxygen is installed.

        Returns:
            Validation result with Doxygen version
        """
        is_installed, version = DoxygenInstaller.is_installed()

        if is_installed:
            return ValidationResult(
                check_name="Doxygen", passed=True, message="Installed", value=version, required=False
            )

        return ValidationResult(
            check_name="Doxygen",
            passed=False,
            message="Not found (can auto-install if C/C++ code detected)",
            required=False,
        )


class ProjectValidator:
    """Validates target project requirements."""

    def __init__(self, repo_path: Path):
        """Initialize validator with target repository path.

        Args:
            repo_path: Path to target repository
        """
        self.repo_path = repo_path

    def check_path_exists(self) -> ValidationResult:
        """Check if repository path exists and is a directory.

        Returns:
            Validation result
        """
        if not self.repo_path.exists():
            return ValidationResult(
                check_name="Path exists", passed=False, message=f"Path does not exist: {self.repo_path}", required=True
            )

        if not self.repo_path.is_dir():
            return ValidationResult(
                check_name="Path exists",
                passed=False,
                message=f"Path is not a directory: {self.repo_path}",
                required=True,
            )

        return ValidationResult(check_name="Path exists", passed=True, message="Valid directory", required=True)

    def check_git_repository(self) -> ValidationResult:
        """Check if path is a git repository.

        Returns:
            Validation result
        """
        git_dir = self.repo_path / ".git"
        if not git_dir.exists():
            return ValidationResult(
                check_name="Git repository",
                passed=False,
                message="Not a git repository (no .git directory)",
                required=True,
            )

        return ValidationResult(check_name="Git repository", passed=True, message="Valid git repository", required=True)

    def check_pyproject_toml(self) -> ValidationResult:
        """Check if pyproject.toml exists.

        Returns:
            Validation result
        """
        pyproject_path = self.repo_path / "pyproject.toml"
        if not pyproject_path.exists():
            return ValidationResult(check_name="pyproject.toml", passed=False, message="File not found", required=True)

        # Try to parse it
        try:
            with open(pyproject_path, "rb") as f:
                tomllib.load(f)
            return ValidationResult(check_name="pyproject.toml", passed=True, message="Valid TOML file", required=True)
        except Exception as e:
            return ValidationResult(
                check_name="pyproject.toml", passed=False, message=f"Invalid TOML: {e}", required=True
            )

    def check_c_code(self) -> ValidationResult:
        """Check if repository contains C/C++ source code.

        Returns:
            Validation result
        """
        try:
            pyproject = read_pyproject(self.repo_path)
        except FileNotFoundError:
            pyproject = None

        c_source_dirs = detect_c_code(self.repo_path, pyproject=pyproject)

        if c_source_dirs:
            # Get relative paths for display
            relative_dirs = [str(d.relative_to(self.repo_path)) for d in c_source_dirs]
            dirs_display = ", ".join(relative_dirs)
            return ValidationResult(
                check_name="C/C++ code",
                passed=True,
                message=f"Found in: {dirs_display}",
                value="Doxygen required",
                required=False,
            )

        return ValidationResult(
            check_name="C/C++ code", passed=True, message="Not found", value="Doxygen not needed", required=False
        )

    def check_typer_dependency(self) -> ValidationResult:
        """Check if project depends on Typer.

        Returns:
            Validation result
        """
        try:
            pyproject = read_pyproject(self.repo_path)
            has_typer = detect_typer_dependency(pyproject)

            if has_typer:
                return ValidationResult(
                    check_name="Typer dependency", passed=True, message="Found in dependencies", required=False
                )

            return ValidationResult(check_name="Typer dependency", passed=True, message="Not found", required=False)
        except Exception as e:
            return ValidationResult(
                check_name="Typer dependency", passed=False, message=f"Could not check: {e}", required=False
            )

    def check_mkdocs_yml(self) -> ValidationResult:
        """Check if mkdocs.yml exists (for build/serve commands).

        Returns:
            Validation result
        """
        mkdocs_path = self.repo_path / "mkdocs.yml"
        if not mkdocs_path.exists():
            return ValidationResult(
                check_name="mkdocs.yml", passed=False, message="File not found - run setup command first", required=True
            )

        return ValidationResult(check_name="mkdocs.yml", passed=True, message="Found", required=True)


# ============================================================================
# Display Functions
# ============================================================================


def display_message(message: str, message_type: MessageType = MessageType.INFO, title: str | None = None) -> None:
    """Display a formatted message panel.

    Args:
        message: The message text to display
        message_type: Type of message (affects styling)
        title: Optional panel title (defaults to message type)
    """
    color, default_title = message_type.value
    panel_title = title or default_title

    console.print(
        Panel(message, title=f"[bold {color}]{panel_title}[/bold {color}]", border_style=color, padding=(1, 2))
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


def _get_table_width(table: Table) -> int:
    """Get the natural width of a table using a temporary wide console.

    Args:
        table: The Rich table to measure

    Returns:
        The width in characters needed to display the table
    """
    temp_console = Console(width=9999)
    measurement = Measurement.get(temp_console, temp_console.options, table)
    return int(measurement.maximum)


def display_validation_results(results: list[ValidationResult], title: str = "Environment Validation") -> None:
    """Display validation results in a Rich formatted table.

    Args:
        results: List of validation results
        title: Table title
    """
    table = Table(title=f":mag: {title}", box=box.MINIMAL_DOUBLE_HEAD, title_style="bold cyan", show_header=True)

    table.add_column("Check", style="cyan", no_wrap=True)
    table.add_column("Status", justify="center", no_wrap=True)
    table.add_column("Details", style="dim")
    table.add_column("Version/Info", style="magenta")

    for result in results:
        # Determine status icon using emoji tokens
        if result.passed:
            status = ":white_check_mark:"
            status_style = "green"
        else:
            status = ":x:" if result.required else ":warning:"
            status_style = "red" if result.required else "yellow"

        # Format details with color
        details = f"[{status_style}]{result.message}[/{status_style}]"

        # Add row
        table.add_row(result.check_name, status, details, result.value or "")

    # Set table width to natural size
    table_width = _get_table_width(table)
    table.width = table_width

    # Display table
    console.print(table, crop=False, overflow="ignore", no_wrap=True, soft_wrap=True)


def validate_environment(
    repo_path: Path, check_mkdocs: bool = False, auto_install_doxygen: bool = False
) -> tuple[bool, list[ValidationResult]]:
    """Validate system and project requirements.

    Args:
        repo_path: Path to target repository
        check_mkdocs: Whether to check for mkdocs.yml
        auto_install_doxygen: Whether to auto-install Doxygen if needed

    Returns:
        Tuple of (all_required_passed, list of results)
    """
    results: list[ValidationResult] = []

    # System checks
    sys_validator = SystemValidator()
    results.append(sys_validator.check_git())
    results.append(sys_validator.check_uv())
    doxygen_result = sys_validator.check_doxygen()
    results.append(doxygen_result)

    # Project checks
    proj_validator = ProjectValidator(repo_path)
    path_result = proj_validator.check_path_exists()
    results.append(path_result)

    # Only continue with further checks if path exists
    if path_result.passed:
        results.append(proj_validator.check_git_repository())
        results.append(proj_validator.check_pyproject_toml())
        c_code_result = proj_validator.check_c_code()
        results.append(c_code_result)
        results.append(proj_validator.check_typer_dependency())

        if check_mkdocs:
            results.append(proj_validator.check_mkdocs_yml())

        # Auto-install Doxygen if needed
        if (
            auto_install_doxygen
            and c_code_result.passed
            and c_code_result.value
            and "required" in c_code_result.value.lower()
        ):
            if not doxygen_result.passed:
                console.print("\n[yellow]C/C++ code detected but Doxygen not installed.[/yellow]")
                console.print("[blue]Attempting automatic Doxygen installation...[/blue]\n")

                success, message = DoxygenInstaller.download_and_install()

                if success:
                    # Re-check Doxygen
                    doxygen_result = sys_validator.check_doxygen()
                    # Update the result in the list
                    for i, r in enumerate(results):
                        if r.check_name == "Doxygen":
                            results[i] = doxygen_result
                            break
                    console.print(f"\n[green]:white_check_mark: {message}[/green]\n")
                else:
                    console.print(f"\n[yellow]:warning: {message}[/yellow]\n")
                    console.print("[yellow]Documentation will be generated without C/C++ API reference.[/yellow]\n")

    # Check if all required checks passed
    all_required_passed = all(r.passed or not r.required for r in results)

    return all_required_passed, results


# ============================================================================
# Core Functions (from generator.py)
# ============================================================================


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
        # Match lines like "url = <url>" with any leading whitespace
        pattern = r"^\s*url =\s(.*)$"
        for line in config_content.splitlines():
            if match := re.match(pattern, line):
                return match.group(1).strip()
        return None
    except (OSError, UnicodeDecodeError):
        return None


def convert_ssh_to_https(git_url: str) -> str:
    """Convert SSH git URL to HTTPS format.

    Args:
        git_url: Git URL in SSH format.

    Returns:
        HTTPS URL format.
    """
    ssh_protocol_match = re.match(r"^(?:ssh://)?git@([^:]+)(?::[0-9]+)?[:/](.+?)(?:\.git)?$", git_url)
    if ssh_protocol_match:
        host = ssh_protocol_match.group(1)
        path = ssh_protocol_match.group(2)
        return f"https://{host}/{path}"
    return git_url


def detect_github_url_base(repo_path: Path) -> str | None:
    """Detect GitHub Pages URL base from git remote.

    Args:
        repo_path: Path to repository.

    Returns:
        GitHub Pages URL base or None if not detected.
    """
    remote_url = get_git_remote_url(repo_path)
    if remote_url is None:
        return None

    # Parse SSH format: git@github.com:owner/repo.git
    ssh_match = re.match(r"^(?:ssh://)?git@github\.com[:/]([^/]+)/([^/]+?)(?:\.git)?$", remote_url)
    if ssh_match:
        owner = ssh_match.group(1)
        repo = ssh_match.group(2)
        return f"https://{owner}.github.io/{repo}/"

    # Parse HTTPS format: https://github.com/owner/repo.git
    https_match = re.match(r"^https://(?:[^@]+@)?github\.com/([^/]+)/([^/]+?)(?:\.git)?$", remote_url)
    if https_match:
        owner = https_match.group(1)
        repo = https_match.group(2)
        return f"https://{owner}.github.io/{repo}/"

    return None


def detect_gitlab_url_base(repo_path: Path) -> str | None:
    """Detect GitLab Pages URL base from git remote.

    Args:
        repo_path: Path to repository.

    Returns:
        GitLab Pages URL base or None if not detected.
    """
    remote_url = get_git_remote_url(repo_path)
    if remote_url is None:
        return None

    # Parse SSH format: git@gitlab.com:owner/repo.git
    ssh_match = re.match(r"^(?:ssh://)?git@gitlab\.com[:/]([^/]+)/([^/]+?)(?:\.git)?$", remote_url)
    if ssh_match:
        owner = ssh_match.group(1)
        repo = ssh_match.group(2)
        return f"https://{owner}.gitlab.io/{repo}/"

    # Parse HTTPS format: https://gitlab.com/owner/repo.git
    https_match = re.match(r"^https://(?:[^@]+@)?gitlab\.com/([^/]+)/([^/]+?)(?:\.git)?$", remote_url)
    if https_match:
        owner = https_match.group(1)
        repo = https_match.group(2)
        return f"https://{owner}.gitlab.io/{repo}/"

    return None


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
    remote_url = get_git_remote_url(repo_path)
    if remote_url:
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


def read_pyproject(repo_path: Path) -> dict[str, Any]:
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


def write_pyproject(repo_path: Path, config: dict[str, Any]) -> None:
    """Write pyproject.toml.

    Args:
        repo_path: Path to repository.
        config: Configuration dictionary to write.
    """
    pyproject_path = repo_path / "pyproject.toml"
    with open(pyproject_path, "wb") as f:
        tomli_w.dump(config, f)


def _contains_c_files(dir_path: Path, c_extensions: set[str]) -> bool:
    """Check if directory contains any C/C++ source files.

    Args:
        dir_path: Directory path to check.
        c_extensions: Set of file extensions to check (.c, .h, .cpp, etc.).

    Returns:
        True if directory contains at least one file with a C/C++ extension.
    """
    return any(file_path.suffix in c_extensions for file_path in dir_path.rglob("*"))


def detect_c_code(
    repo_path: Path, explicit_dirs: list[str] | None = None, pyproject: dict[str, Any] | None = None
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
    found_dirs: list[Path] = []

    # Priority 1: Explicit CLI option
    if explicit_dirs:
        for dir_str in explicit_dirs:
            dir_path = (repo_path / dir_str).resolve()
            if dir_path.exists() and dir_path.is_dir():
                # Verify directory contains C/C++ files
                if _contains_c_files(dir_path, c_extensions):
                    found_dirs.append(dir_path)
        if found_dirs:
            return found_dirs

    # Priority 2: Environment variable
    env_dirs = os.getenv("MKAPIDOCS_C_SOURCE_DIRS")
    if env_dirs:
        for dir_str in env_dirs.split(":"):
            dir_path = (repo_path / dir_str.strip()).resolve()
            if dir_path.exists() and dir_path.is_dir():
                if _contains_c_files(dir_path, c_extensions):
                    found_dirs.append(dir_path)
        if found_dirs:
            return found_dirs

    # Priority 3: pypis_delivery_service config
    if pyproject:
        pypis_config = pyproject.get("tool", {}).get("pypis_delivery_service", {})
        cmake_source_dir = pypis_config.get("cmake_source_dir")
        if cmake_source_dir:
            dir_path = (repo_path / cmake_source_dir).resolve()
            if not dir_path.exists():
                console.print(
                    f"[yellow]Warning: pypis_delivery_service cmake_source_dir '{cmake_source_dir}' "
                    f"does not exist, falling back to auto-detection[/yellow]"
                )
            elif not dir_path.is_dir():
                console.print(
                    f"[yellow]Warning: pypis_delivery_service cmake_source_dir '{cmake_source_dir}' "
                    f"is not a directory, falling back to auto-detection[/yellow]"
                )
            elif not _contains_c_files(dir_path, c_extensions):
                console.print(
                    f"[yellow]Warning: pypis_delivery_service cmake_source_dir '{cmake_source_dir}' "
                    f"contains no C/C++ files, falling back to auto-detection[/yellow]"
                )
            else:
                # Valid directory with C files
                return [dir_path]

    # Priority 4: Auto-detect via git ls-files
    try:
        result = subprocess.run(
            ["git", "ls-files"], cwd=repo_path, capture_output=True, text=True, check=True, timeout=10
        )
        # Find unique directories containing C/C++ files
        c_dirs: set[Path] = set()
        for line in result.stdout.strip().split("\n"):
            if not line:
                continue
            file_path = Path(line)
            if file_path.suffix in c_extensions:
                # Get the top-level directory of this file
                if len(file_path.parts) > 1:
                    c_dirs.add(repo_path / file_path.parts[0])

        if c_dirs:
            # Verify directories exist and contain C/C++ files
            for dir_path in sorted(c_dirs):
                if dir_path.exists() and dir_path.is_dir():
                    if _contains_c_files(dir_path, c_extensions):
                        found_dirs.append(dir_path)
            if found_dirs:
                return found_dirs

    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
        # Git not available or not a git repo - continue to fallback
        pass

    # Priority 5: Fallback to source/ directory
    source_dir = repo_path / "source"
    if source_dir.exists() and source_dir.is_dir():
        if _contains_c_files(source_dir, c_extensions):
            found_dirs.append(source_dir.resolve())

    return found_dirs


def detect_typer_dependency(pyproject: dict[str, Any]) -> bool:
    """Detect if project depends on Typer.

    Args:
        pyproject: Parsed pyproject.toml.

    Returns:
        True if typer found in dependencies.
    """
    dependencies = pyproject.get("project", {}).get("dependencies", [])
    return any(dep.strip().lower().startswith("typer") for dep in dependencies)


def detect_typer_cli_module(repo_path: Path, pyproject: dict[str, Any]) -> list[str]:
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
    import ast

    # Get project name and convert to package name
    project_name = pyproject.get("project", {}).get("name", repo_path.name)
    package_name = project_name.replace("-", "_")

    # Determine source paths from pyproject.toml
    source_paths = []

    # Check Hatch configuration
    hatch_wheel = pyproject.get("tool", {}).get("hatch", {}).get("build", {}).get("targets", {}).get("wheel", {})
    hatch_sources = hatch_wheel.get("sources", {})

    if hatch_sources:
        # Sources mapping exists (e.g., "packages/picod" = "picod")
        for source_path in hatch_sources:
            source_paths.append(repo_path / source_path)
    else:
        # Try common patterns
        potential_paths = [
            repo_path / "packages" / package_name,
            repo_path / "src" / package_name,
            repo_path / package_name,
        ]
        source_paths = [p for p in potential_paths if p.exists() and p.is_dir()]

    if not source_paths:
        return []

    # Collect all Typer CLI modules
    cli_modules = []

    # Search for Python files with Typer app
    for source_path in source_paths:
        for py_file in source_path.rglob("*.py"):
            # Skip test files
            if "test" in py_file.name or py_file.name.startswith("test_"):
                continue

            try:
                content = py_file.read_text(encoding="utf-8")

                # Quick text check first (optimization)
                if "typer" not in content.lower() or "Typer(" not in content:
                    continue

                # Parse AST to check for Typer app instantiation
                tree = ast.parse(content, filename=str(py_file))

                has_typer_import = False
                has_typer_app = False

                for node in ast.walk(tree):
                    # Check for typer imports
                    if isinstance(node, (ast.Import, ast.ImportFrom)):
                        if isinstance(node, ast.Import):
                            for alias in node.names:
                                if alias.name == "typer":
                                    has_typer_import = True
                        elif isinstance(node, ast.ImportFrom) and node.module == "typer":
                            has_typer_import = True

                    # Check for Typer() instantiation
                    if isinstance(node, ast.Call):
                        if (isinstance(node.func, ast.Name) and node.func.id == "Typer") or (
                            isinstance(node.func, ast.Attribute) and node.func.attr == "Typer"
                        ):
                            has_typer_app = True

                if has_typer_import and has_typer_app:
                    # Convert file path to module path
                    relative_path = py_file.relative_to(source_path)
                    module_parts = [*list(relative_path.parts[:-1]), relative_path.stem]
                    module_path = ".".join([package_name, *module_parts])
                    cli_modules.append(module_path)

            except (OSError, SyntaxError, UnicodeDecodeError):
                # Skip files that can't be read or parsed
                continue

    return cli_modules


def detect_private_registry(pyproject: dict[str, Any]) -> tuple[bool, str | None]:
    """Detect if project uses private registry from uv configuration.

    Args:
        pyproject: Parsed pyproject.toml.

    Returns:
        Tuple of (is_private_registry, registry_url).
    """
    tool_config = pyproject.get("tool", {})
    uv_config = tool_config.get("uv", {})

    uv_indexes = uv_config.get("index", [])
    if isinstance(uv_indexes, list) and len(uv_indexes) > 0:
        first_index = uv_indexes[0]
        if isinstance(first_index, dict) and "url" in first_index:
            return True, first_index["url"]

    return False, None


def update_ruff_config(pyproject: dict[str, Any]) -> dict[str, Any]:
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


# ============================================================================
# YAML Merge Infrastructure
# ============================================================================


@dataclass
class FileChange:
    """Record of a change made to a configuration file.

    Attributes:
        key_path: Dot-separated path to the key (e.g., "theme.name")
        action: Type of change (updated, added, preserved)
        old_value: Previous value (None if newly added)
        new_value: New value (None if preserved)
    """

    key_path: str
    action: str  # "updated", "added", "preserved"
    old_value: str | None = None
    new_value: str | None = None


def _display_file_changes(file_path: Path, changes: list[FileChange]) -> None:
    """Display a Rich table showing changes made to a configuration file.

    Args:
        file_path: Path to the file that was modified
        changes: List of FileChange records
    """
    if not changes:
        return

    table = Table(
        title=f":page_facing_up: Changes to {file_path.name}", box=box.MINIMAL_DOUBLE_HEAD, title_style="bold blue"
    )

    table.add_column("Key", style="cyan", no_wrap=True)
    table.add_column("Action", justify="center", no_wrap=True)
    table.add_column("Old Value", style="dim")
    table.add_column("New Value", style="green")

    for change in changes:
        # Format action with emoji
        if change.action == "updated":
            action_display = "[green]:white_check_mark:[/green] Updated"
        elif change.action == "added":
            action_display = "[green]:white_check_mark:[/green] Added"
        elif change.action == "preserved":
            action_display = "[yellow]:black_circle:[/yellow] Preserved"
        else:
            action_display = change.action

        # Format values
        old_val = str(change.old_value) if change.old_value is not None else ""
        new_val = str(change.new_value) if change.new_value is not None else ""

        # Truncate long values
        if len(old_val) > 50:
            old_val = old_val[:47] + "..."
        if len(new_val) > 50:
            new_val = new_val[:47] + "..."

        table.add_row(change.key_path, action_display, old_val, new_val)

    console.print(table)


def _merge_yaml_configs(
    existing_yaml: dict[str, Any],
    template_yaml: dict[str, Any],
    template_owned_keys: set[str],
    key_prefix: str = "",
    depth: int = 0,
    max_depth: int = 50,
) -> tuple[dict[str, Any], list[FileChange]]:
    """Recursively merge YAML configurations, preserving user customizations.

    Args:
        existing_yaml: Current YAML content from file
        template_yaml: New YAML content from template
        template_owned_keys: Set of key paths that template always controls
        key_prefix: Current key path for recursion (dot-separated)
        depth: Current recursion depth (internal parameter)
        max_depth: Maximum nesting depth to prevent stack overflow

    Returns:
        Tuple of (merged_yaml, list_of_changes)

    Raises:
        CLIError: If YAML structure conflicts prevent clean merge or depth exceeds limit
    """
    # Check recursion depth to prevent stack overflow
    if depth > max_depth:
        msg = (
            f"YAML structure exceeds maximum nesting depth ({max_depth}). "
            f"This may indicate a malformed configuration file or circular references."
        )
        raise CLIError(msg)

    merged: dict[str, Any] = {}
    changes: list[FileChange] = []

    # First, handle all template keys
    for key, template_value in template_yaml.items():
        current_path = f"{key_prefix}.{key}" if key_prefix else key
        existing_value = existing_yaml.get(key)

        # Check if this key is template-owned
        is_template_owned = any(
            current_path == owned_key or current_path.startswith(owned_key + ".") for owned_key in template_owned_keys
        )

        if is_template_owned:
            # Template controls this key - always update
            merged[key] = template_value
            if existing_value != template_value:
                if existing_value is None:
                    changes.append(FileChange(key_path=current_path, action="added", new_value=str(template_value)))
                else:
                    changes.append(
                        FileChange(
                            key_path=current_path,
                            action="updated",
                            old_value=str(existing_value),
                            new_value=str(template_value),
                        )
                    )
        elif isinstance(template_value, dict) and isinstance(existing_value, dict):
            # Recursively merge nested dicts
            merged_nested, nested_changes = _merge_yaml_configs(
                existing_value, template_value, template_owned_keys, current_path, depth + 1, max_depth
            )
            merged[key] = merged_nested
            changes.extend(nested_changes)
        elif existing_value is not None:
            # User has customized this - preserve it
            merged[key] = existing_value
            changes.append(
                FileChange(key_path=current_path, action="preserved", old_value=str(existing_value), new_value=None)
            )
        else:
            # New key from template, not template-owned
            merged[key] = template_value
            changes.append(FileChange(key_path=current_path, action="added", new_value=str(template_value)))

    # Now handle existing keys not in template (user additions)
    for key, existing_value in existing_yaml.items():
        if key not in merged:
            current_path = f"{key_prefix}.{key}" if key_prefix else key
            merged[key] = existing_value
            changes.append(
                FileChange(key_path=current_path, action="preserved", old_value=str(existing_value), new_value=None)
            )

    return merged, changes


def _merge_mkdocs_yaml(existing_path: Path, template_content: str) -> tuple[str, list[FileChange]]:
    """Merge existing mkdocs.yml with template, preserving user customizations.

    Args:
        existing_path: Path to existing mkdocs.yml
        template_content: Rendered template content

    Returns:
        Tuple of (merged_yaml_string, list_of_changes)

    Raises:
        CLIError: If YAML parsing fails or merge conflicts occur
    """
    # Read existing file text
    existing_text = existing_path.read_text()

    # Use UnsafeLoader to handle Python-specific YAML tags like !!python/name:
    # Security justification: This parses the user's own mkdocs.yml file from their project,
    # not untrusted external input. MkDocs configuration legitimately uses Python tags
    # (e.g., !!python/name:mermaid2.fence_mermaid_custom for custom fence handlers).
    # safe_load() cannot parse these tags, so UnsafeLoader is required.
    try:
        existing_yaml = yaml.load(existing_text, Loader=yaml.UnsafeLoader)  # noqa: S506
    except yaml.YAMLError as e:
        msg = f"Failed to parse existing {existing_path.name}: {e}"
        raise CLIError(msg) from e

    # Parse template - for Python tags, replace them with placeholders for structural parsing
    template_for_parsing = template_content
    if "!!python/name:" in template_content:
        # Replace Python tags with placeholders for parsing structure
        import re

        template_for_parsing = re.sub(r"!!python/name:\S+", '"__PYTHON_TAG_PLACEHOLDER__"', template_content)

    try:
        template_yaml = yaml.safe_load(template_for_parsing)
    except yaml.YAMLError as e:
        msg = f"Failed to parse template YAML: {e}"
        raise CLIError(msg) from e

    # Define template-owned keys for mkdocs.yml
    template_owned_keys = {
        "plugins.gen-files.scripts",
        "plugins.search",
        "plugins.mkdocstrings",
        "plugins.mermaid2",
        "plugins.termynal",
        "plugins.recently-updated",
        "plugins.literate-nav",
        "theme.name",
        "theme.palette",
        "markdown_extensions",
    }

    # Add site_url and repo_url if template provides them
    if template_yaml.get("site_url"):
        template_owned_keys.add("site_url")
    if template_yaml.get("repo_url"):
        template_owned_keys.add("repo_url")

    merged_yaml, changes = _merge_yaml_configs(existing_yaml, template_yaml, template_owned_keys)

    # Convert back to YAML string - use unsafe dump to preserve Python tags
    merged_content = yaml.dump(
        merged_yaml, default_flow_style=False, sort_keys=False, allow_unicode=True, Dumper=yaml.Dumper
    )

    return merged_content, changes


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
    env = Environment(keep_trailing_newline=True)
    template = env.from_string(MKDOCS_YML_TEMPLATE)

    # Convert absolute Path objects to relative string paths for template
    c_source_dirs_relative = [str(path.relative_to(repo_path)) for path in c_source_dirs]

    # Prepare CLI module information for template
    cli_modules_list = cli_modules if cli_modules else []
    cli_nav_items = []
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
        merged_content, changes = _merge_mkdocs_yaml(mkdocs_path, content)
        mkdocs_path.write_text(merged_content)
        _display_file_changes(mkdocs_path, changes)
    else:
        # New file - create fresh
        mkdocs_path.write_text(content)
        console.print(f"[green]:white_check_mark:[/green] Created {mkdocs_path.name}")


def create_github_actions(repo_path: Path) -> None:
    """Create .github/workflows/pages.yml for GitHub Pages deployment.

    Creates a fresh GitHub Actions workflow file. If the file exists, it will be
    overwritten with the template (no smart merge for GitHub Actions).

    Args:
        repo_path: Path to repository.
    """
    github_dir = repo_path / ".github" / "workflows"
    github_dir.mkdir(parents=True, exist_ok=True)

    content = GITHUB_ACTIONS_PAGES_TEMPLATE

    workflow_path = github_dir / "pages.yml"

    # Always write fresh - GitHub Actions workflows are simpler
    workflow_path.write_text(content)

    if workflow_path.exists():
        console.print(f"[green]:white_check_mark:[/green] Updated {workflow_path.name}")
    else:
        console.print(f"[green]:white_check_mark:[/green] Created {workflow_path.name}")


def create_gitlab_ci(repo_path: Path) -> None:
    """Create .gitlab/workflows/pages.gitlab-ci.yml for GitLab Pages deployment.

    Creates a fresh GitLab CI workflow file. If the file exists, it will be
    overwritten with the template.

    Args:
        repo_path: Path to repository.
    """
    gitlab_dir = repo_path / ".gitlab" / "workflows"
    gitlab_dir.mkdir(parents=True, exist_ok=True)

    content = GITLAB_CI_PAGES_TEMPLATE

    workflow_path = gitlab_dir / "pages.gitlab-ci.yml"

    # Always write fresh
    workflow_path.write_text(content)

    if workflow_path.exists():
        console.print(f"[green]:white_check_mark:[/green] Updated {workflow_path.name}")
    else:
        console.print(f"[green]:white_check_mark:[/green] Created {workflow_path.name}")


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

    env = Environment(keep_trailing_newline=True)
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

    index_path.write_text(content)


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

    env = Environment(keep_trailing_newline=True)
    package_name = project_name.replace("-", "_")

    # Python API
    python_template = env.from_string(PYTHON_API_MD_TEMPLATE)
    python_content = python_template.render(package_name=package_name)
    (generated_dir / "python-api.md").write_text(python_content)

    # C API - only create if C/C++ source directories detected
    if c_source_dirs:
        c_template = env.from_string(C_API_MD_TEMPLATE)
        c_content = c_template.render(project_name=project_name)
        (generated_dir / "c-api.md").write_text(c_content)

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
            (generated_dir / filename).write_text(cli_content)


def create_gen_files_script(repo_path: Path) -> None:
    """Create gen_ref_pages.py script for mkdocs-gen-files plugin.

    Args:
        repo_path: Path to repository.
    """
    target_script = repo_path / "docs" / "generated" / "gen_ref_pages.py"
    target_script.parent.mkdir(parents=True, exist_ok=True)
    target_script.write_text(GEN_REF_PAGES_PY)


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
    features = []
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
    (generated_dir / "index-features.md").write_text(features_content)

    # install-registry.md
    if has_private_registry and private_registry_url:
        registry_content = f"""## Private Registry

This package is published to a private registry:

```bash
uv pip install {project_name} --index-url {private_registry_url}
```
"""
    else:
        registry_content = ""

    (generated_dir / "install-registry.md").write_text(registry_content)


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
    if gitignore_path.exists():
        existing_content = gitignore_path.read_text()
        existing_lines = existing_content.splitlines()
    else:
        existing_content = ""
        existing_lines = []

    # Determine which entries need to be added
    missing_entries = []
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
        gitignore_path.write_text(existing_content)


def create_supporting_docs(
    repo_path: Path,
    project_name: str,
    pyproject: dict[str, Any],
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

    env = Environment(keep_trailing_newline=True)

    requires_python = pyproject.get("project", {}).get("requires-python", "3.11+")

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
        install_path.write_text(install_content)
    else:
        console.print(f"[yellow]  Preserving existing {install_path.name}[/yellow]")


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

    project_name = pyproject.get("project", {}).get("name", repo_path.name)
    description = pyproject.get("project", {}).get("description", "")
    license_info = pyproject.get("project", {}).get("license", {})
    license_name = license_info.get("text", "See LICENSE file")

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
    elif provider == CIProvider.GITLAB:
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
    else:
        raise ValueError(f"Unsupported provider: {provider}")

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
    create_supporting_docs(repo_path, project_name, pyproject, c_source_dirs_list, has_typer_cli, site_url)
    create_gen_files_script(repo_path)
    update_gitignore(repo_path, provider)

    # Add mkapidocs to target project's dev dependencies
    add_mkapidocs_to_target_project(repo_path)

    return provider


# ============================================================================
# Project Environment Integration
# ============================================================================


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
        with open(pyproject_path, "rb") as f:
            config = tomllib.load(f)

        # Get the path to mkapidocs (this package)
        # First try to find it in the current environment
        mkapidocs_path = Path(__file__).parent.parent.parent

        # Check if we're in a development environment or installed
        if (mkapidocs_path / "pyproject.toml").exists():
            # Development mode - use local path
            dep_spec = str(mkapidocs_path.absolute())
        else:
            # Installed mode - will need to use git URL or PyPI when available
            # For now, skip if not in dev mode
            console.print(
                "[yellow]:warning: mkapidocs not in development mode, skipping installation in target[/yellow]"
            )
            return

        # Initialize dependency-groups if it doesn't exist
        if "dependency-groups" not in config:
            config["dependency-groups"] = {}

        # Initialize dev group if it doesn't exist
        if "dev" not in config["dependency-groups"]:
            config["dependency-groups"]["dev"] = []

        # Convert to list if it's not already
        dev_deps = config["dependency-groups"]["dev"]
        if not isinstance(dev_deps, list):
            dev_deps = []
            config["dependency-groups"]["dev"] = dev_deps

        # Check if mkapidocs is already in dependencies
        has_mkapidocs = any(
            dep.startswith("mkapidocs") or (isinstance(dep, str) and "mkapidocs" in dep) for dep in dev_deps
        )

        if not has_mkapidocs:
            # Add mkapidocs with local path
            dev_deps.append(f"mkapidocs @ file://{dep_spec}")

            # Write updated pyproject.toml
            with open(pyproject_path, "wb") as f:
                tomli_w.dump(config, f)

            console.print(f"[green]:white_check_mark: Added mkapidocs to {repo_path}/pyproject.toml[/green]")

            # Run uv sync to install mkapidocs in target project
            uv_cmd = which("uv")
            if uv_cmd:
                console.print("[blue]Installing mkapidocs in target project environment...[/blue]")
                result = subprocess.run([uv_cmd, "sync"], cwd=repo_path, capture_output=True, text=True, check=False)
                if result.returncode == 0:
                    console.print(
                        "[green]:white_check_mark: Successfully installed mkapidocs in target project[/green]"
                    )
                else:
                    console.print(f"[yellow]:warning: Failed to sync dependencies: {result.stderr}[/yellow]")
            else:
                console.print("[yellow]:warning: uv command not found, skipping sync[/yellow]")
        else:
            console.print("[blue]:information: mkapidocs already in target project dependencies[/blue]")

    except Exception as e:
        console.print(f"[yellow]:warning: Failed to add mkapidocs to target project: {e}[/yellow]")


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
        with open(pyproject_path, "rb") as f:
            config = tomllib.load(f)

        dev_deps = config.get("dependency-groups", {}).get("dev", [])
        return any(dep.startswith("mkapidocs") or (isinstance(dep, str) and "mkapidocs" in dep) for dep in dev_deps)
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


# ============================================================================
# Builder Functions (from builder.py)
# ============================================================================


def get_source_paths_from_pyproject(repo_path: Path) -> list[Path]:
    """Extract source paths from pyproject.toml build configuration.

    Args:
        repo_path: Path to repository root.

    Returns:
        List of paths to add to PYTHONPATH.
    """
    pyproject_path = repo_path / "pyproject.toml"
    if not pyproject_path.exists():
        return []

    try:
        with open(pyproject_path, "rb") as f:
            config = tomllib.load(f)
    except (tomllib.TOMLDecodeError, OSError):
        return []

    paths = []

    # Check Hatch configuration
    hatch_wheel = config.get("tool", {}).get("hatch", {}).get("build", {}).get("targets", {}).get("wheel", {})

    # Check Hatch sources mapping (e.g., "packages/usb_powertools" = "usb_powertools")
    hatch_sources = hatch_wheel.get("sources", {})
    if hatch_sources:
        for source_path in hatch_sources:
            path = Path(source_path)
            if len(path.parts) > 1:
                paths.append(repo_path / path.parent)
            else:
                paths.append(repo_path)

    # Check Hatch packages list
    if not paths:
        hatch_packages = hatch_wheel.get("packages", [])
        for pkg_path in hatch_packages:
            path = Path(pkg_path)
            if len(path.parts) > 1:
                paths.append(repo_path / path.parent)
            else:
                paths.append(repo_path)

    # Check setuptools configuration
    if not paths:
        setuptools_where = (
            config.get("tool", {}).get("setuptools", {}).get("packages", {}).get("find", {}).get("where", [])
        )
        for where in setuptools_where if isinstance(setuptools_where, list) else [setuptools_where]:
            if where:
                paths.append(repo_path / where)

    return paths


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
    mkdocs_yml = target_path / "mkdocs.yml"
    if not mkdocs_yml.exists():
        msg = f"mkdocs.yml not found in {target_path}"
        raise FileNotFoundError(msg)

    # Generate gen_ref_pages.py just-in-time for this build
    gen_ref_script = target_path / "docs" / "generated" / "gen_ref_pages.py"
    gen_ref_script.parent.mkdir(parents=True, exist_ok=True)
    gen_ref_script.write_text(GEN_REF_PAGES_PY)

    # Get source paths and add to PYTHONPATH
    env = os.environ.copy()
    source_paths = get_source_paths_from_pyproject(target_path)
    if source_paths:
        existing_path = env.get("PYTHONPATH", "")
        paths_str = ":".join(str(p) for p in source_paths)
        env["PYTHONPATH"] = f"{paths_str}:{existing_path}" if existing_path else paths_str

    # Check if we should use target project's environment
    if is_mkapidocs_in_target_env(target_path) and not is_running_in_target_env():
        # Use target project's environment via uv run
        console.print("[blue]:rocket: Using target project's environment for build[/blue]")

        uv_cmd = which("uv")
        if not uv_cmd:
            msg = "uv command not found. Please install uv."
            raise FileNotFoundError(msg)

        # Set flag to prevent recursion
        env["MKAPIDOCS_INTERNAL_CALL"] = "1"

        # Build command: uv run mkapidocs build . [--strict] [--output-dir ...]
        cmd = [uv_cmd, "run", "mkapidocs", "build", "."]
        if strict:
            cmd.append("--strict")
        if output_dir:
            cmd.extend(["--output-dir", str(output_dir)])

        result = subprocess.run(cmd, cwd=target_path, env=env, capture_output=False, check=False)
        return result.returncode

    # If running internally (already in target env), call mkdocs directly
    if is_running_in_target_env():
        console.print("[blue]:zap: Running mkdocs directly (already in target environment)[/blue]")
        mkdocs_cmd = which("mkdocs")
        if mkdocs_cmd:
            cmd = [mkdocs_cmd, "build"]
            if strict:
                cmd.append("--strict")
            if output_dir:
                cmd.extend(["--site-dir", str(output_dir)])
            result = subprocess.run(cmd, cwd=target_path, env=env, capture_output=False, check=False)
            return result.returncode
        # If mkdocs not found, fall through to uvx fallback

    # Fallback to uvx with standalone plugin installation
    console.print("[blue]:wrench: Using standalone uvx environment for build[/blue]")

    uvx_cmd = which("uvx")
    if not uvx_cmd:
        msg = "uvx command not found. Please install uv."
        raise FileNotFoundError(msg)

    # Build comprehensive --with arguments for all mkdocs plugins
    plugins = [
        "mkdocs",
        "mkdocs-material",
        "mkdocs-gen-files",
        "mkdocs-literate-nav",
        "mkdocstrings[python]",
        "mkdocs-typer2",
        "mkdoxy",
        "mkdocs-mermaid2-plugin",
        "termynal",
        "mkdocs-recently-updated-docs",
    ]

    cmd = [uvx_cmd]
    for plugin in plugins:
        cmd.extend(["--with", plugin])
    cmd.extend(["--from", "mkdocs", "mkdocs", "build"])

    if strict:
        cmd.append("--strict")
    if output_dir:
        cmd.extend(["--site-dir", str(output_dir)])

    result = subprocess.run(cmd, cwd=target_path, env=env, capture_output=False, check=False)
    return result.returncode


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
    mkdocs_yml = target_path / "mkdocs.yml"
    if not mkdocs_yml.exists():
        msg = f"mkdocs.yml not found in {target_path}"
        raise FileNotFoundError(msg)

    # Generate gen_ref_pages.py just-in-time for serving
    gen_ref_script = target_path / "docs" / "generated" / "gen_ref_pages.py"
    gen_ref_script.parent.mkdir(parents=True, exist_ok=True)
    gen_ref_script.write_text(GEN_REF_PAGES_PY)

    # Get source paths and add to PYTHONPATH
    env = os.environ.copy()
    source_paths = get_source_paths_from_pyproject(target_path)
    if source_paths:
        existing_path = env.get("PYTHONPATH", "")
        paths_str = ":".join(str(p) for p in source_paths)
        env["PYTHONPATH"] = f"{paths_str}:{existing_path}" if existing_path else paths_str

    # Check if we should use target project's environment
    if is_mkapidocs_in_target_env(target_path) and not is_running_in_target_env():
        # Use target project's environment via uv run
        console.print("[blue]:rocket: Using target project's environment for serve[/blue]")

        uv_cmd = which("uv")
        if not uv_cmd:
            msg = "uv command not found. Please install uv."
            raise FileNotFoundError(msg)

        # Set flag to prevent recursion
        env["MKAPIDOCS_INTERNAL_CALL"] = "1"

        # Build command: uv run mkapidocs serve . [--host ...] [--port ...]
        cmd = [uv_cmd, "run", "mkapidocs", "serve", ".", "--host", host, "--port", str(port)]

        try:
            result = subprocess.run(cmd, cwd=target_path, env=env, capture_output=False, check=False)
        except KeyboardInterrupt:
            return 0
        else:
            return result.returncode

    # If running internally (already in target env), call mkdocs directly
    if is_running_in_target_env():
        console.print("[blue]:zap: Running mkdocs directly (already in target environment)[/blue]")
        mkdocs_cmd = which("mkdocs")
        if mkdocs_cmd:
            cmd = [mkdocs_cmd, "serve", "--dev-addr", f"{host}:{port}"]
            try:
                result = subprocess.run(cmd, cwd=target_path, env=env, capture_output=False, check=False)
            except KeyboardInterrupt:
                return 0
            else:
                return result.returncode
        # If mkdocs not found, fall through to uvx fallback

    # Fallback to uvx with standalone plugin installation
    console.print("[blue]:wrench: Using standalone uvx environment for serve[/blue]")

    uvx_cmd = which("uvx")
    if not uvx_cmd:
        msg = "uvx command not found. Please install uv."
        raise FileNotFoundError(msg)

    # Build comprehensive --with arguments for all mkdocs plugins
    plugins = [
        "mkdocs",
        "mkdocs-material",
        "mkdocs-gen-files",
        "mkdocs-literate-nav",
        "mkdocstrings[python]",
        "mkdocs-typer2",
        "mkdoxy",
        "mkdocs-mermaid2-plugin",
        "termynal",
        "mkdocs-recently-updated-docs",
    ]

    cmd = [uvx_cmd]
    for plugin in plugins:
        cmd.extend(["--with", plugin])
    cmd.extend(["--from", "mkdocs", "mkdocs", "serve", "--dev-addr", f"{host}:{port}"])

    try:
        result = subprocess.run(cmd, cwd=target_path, env=env, capture_output=False, check=False)
    except KeyboardInterrupt:
        return 0
    else:
        return result.returncode


# ============================================================================
# CLI Commands
# ============================================================================


@app.command()
def version() -> None:
    """Show version information."""
    display_message(
        "[bold cyan]mkapidocs[/bold cyan] version [bold green]1.0.0[/bold green]",
        MessageType.INFO,
        title="Version Information",
    )


@app.command()
def info() -> None:
    """Display package information and installation details."""
    info_text = """
[bold cyan]Package:[/bold cyan] python-docs-init
[bold cyan]Version:[/bold cyan] 1.0.0
[bold cyan]Summary:[/bold cyan] Automated documentation setup tool for Python projects
[bold cyan]License:[/bold cyan] Unlicense
[bold cyan]Python:[/bold cyan] >=3.11
"""
    display_message(info_text.strip(), MessageType.INFO, title="Package Information")


@app.command()
def setup(
    repo_path: Annotated[
        Path, typer.Argument(help="Path to Python repository to set up documentation for", resolve_path=True)
    ],
    provider: Annotated[
        str | None,
        typer.Option(
            "--provider",
            help="CI/CD provider: 'github' or 'gitlab' (auto-detected if not provided)",
            rich_help_panel="Configuration",
        ),
    ] = None,
    github_url_base: Annotated[
        str | None,
        typer.Option(
            "--github-url-base",
            help="Base URL for GitHub Pages (auto-detected from git remote if not provided)",
            rich_help_panel="Configuration",
        ),
    ] = None,
    c_source_dirs: Annotated[
        list[str] | None,
        typer.Option(
            "--c-source-dirs",
            help="Directories containing C/C++ source code (comma-separated, relative to repo root)",
            rich_help_panel="C/C++ Configuration",
        ),
    ] = None,
) -> None:
    """Set up MkDocs documentation for a Python repository.

    Args:
        repo_path: Path to the repository
        provider: CI/CD provider ('github' or 'gitlab')
        github_url_base: Base URL for GitHub Pages (deprecated, use --provider)
        c_source_dirs: Explicit C/C++ source directories (overrides auto-detection)
    """
    try:
        # Validate environment before setup
        console.print()
        all_passed, results = validate_environment(repo_path, check_mkdocs=False, auto_install_doxygen=True)
        display_validation_results(results, title="Pre-Setup Validation")
        console.print()

        if not all_passed:
            display_message(
                "Validation failed - please fix the issues above before continuing.",
                MessageType.ERROR,
                title="Validation Failed",
            )
            raise typer.Exit(1)

        # Parse provider argument
        ci_provider: CIProvider | None = None
        if provider:
            provider_lower = provider.lower()
            if provider_lower == "github":
                ci_provider = CIProvider.GITHUB
            elif provider_lower == "gitlab":
                ci_provider = CIProvider.GITLAB
            else:
                display_message(
                    f"Invalid provider '{provider}'. Must be 'github' or 'gitlab'.",
                    MessageType.ERROR,
                    title="Invalid Provider",
                )
                raise typer.Exit(1)

        display_message(
            f"Setting up documentation for [bold cyan]{repo_path}[/bold cyan]...",
            MessageType.INFO,
            title="Starting Setup",
        )

        ci_provider = setup_documentation(repo_path, ci_provider, github_url_base, c_source_dirs)

        # Display completion message with provider-specific instructions
        if ci_provider == CIProvider.GITHUB:
            next_steps_msg = (
                f"Documentation setup complete for [bold cyan]{repo_path.name}[/bold cyan]\n\n"
                f"Next steps:\n"
                f"  1. Preview docs locally: [bold]mkapidocs.py serve {repo_path}[/bold]\n"
                f"  2. Build docs: [bold]mkapidocs.py build {repo_path}[/bold]\n"
                f"  3. Commit and push changes to enable GitHub Pages"
            )
        elif ci_provider == CIProvider.GITLAB:
            next_steps_msg = (
                f"Documentation setup complete for [bold cyan]{repo_path.name}[/bold cyan]\n\n"
                f"Next steps:\n"
                f"  1. Preview docs locally: [bold]mkapidocs.py serve {repo_path}[/bold]\n"
                f"  2. Build docs: [bold]mkapidocs.py build {repo_path}[/bold]\n"
                f"  3. Commit and push changes to enable GitLab Pages"
            )
        else:
            # Should not happen if setup_documentation succeeded
            next_steps_msg = (
                f"Documentation setup complete for [bold cyan]{repo_path.name}[/bold cyan]\n\n"
                f"Next steps:\n"
                f"  1. Preview docs locally: [bold]mkapidocs.py serve {repo_path}[/bold]\n"
                f"  2. Build docs: [bold]mkapidocs.py build {repo_path}[/bold]\n"
                f"  3. Commit and push changes"
            )

        display_message(next_steps_msg, MessageType.SUCCESS, title="Setup Complete")

    except typer.Exit:
        # Re-raise typer.Exit to allow proper exit handling
        # (error message already displayed before raising Exit)
        raise
    except FileNotFoundError as e:
        handle_error(e, f"Repository setup failed: {e}")
    except ValueError as e:
        handle_error(e, str(e))
    except Exception as e:
        handle_error(e, f"An unexpected error occurred during setup: {e}")


@app.command()
def build(
    repo_path: Annotated[
        Path, typer.Argument(help="Path to Python repository to build documentation for", resolve_path=True)
    ],
    strict: Annotated[
        bool, typer.Option("--strict", help="Enable strict mode (warnings as errors)", rich_help_panel="Build Options")
    ] = False,
    output_dir: Annotated[
        Path | None,
        typer.Option("--output-dir", help="Custom output directory (default: site/)", rich_help_panel="Build Options"),
    ] = None,
) -> None:
    """Build documentation using uvx mkdocs with all required plugins.

    This command uses uvx to run mkdocs with all necessary plugins
    in an isolated environment, without requiring mkdocs to be installed
    in the target project.

    Args:
        repo_path: Path to the repository
        strict: Enable strict mode
        output_dir: Custom output directory
    """
    try:
        # Validate environment before build
        console.print()
        all_passed, results = validate_environment(repo_path, check_mkdocs=True, auto_install_doxygen=True)
        display_validation_results(results, title="Pre-Build Validation")
        console.print()

        if not all_passed:
            display_message(
                "Validation failed - please fix the issues above before building.",
                MessageType.ERROR,
                title="Validation Failed",
            )
            raise typer.Exit(1)

        display_message(
            f"Building documentation for [bold cyan]{repo_path}[/bold cyan]...",
            MessageType.INFO,
            title="Building Documentation",
        )

        exit_code = build_docs(repo_path, strict=strict, output_dir=output_dir)

        if exit_code == 0:
            output_path = output_dir or (repo_path / "site")
            display_message(
                f"Documentation built successfully in [bold cyan]{output_path}[/bold cyan]",
                MessageType.SUCCESS,
                title="Build Complete",
            )
        else:
            display_message(
                f"Documentation build failed with exit code {exit_code}", MessageType.ERROR, title="Build Failed"
            )
            raise typer.Exit(exit_code)

    except FileNotFoundError as e:
        handle_error(e, str(e))
        raise typer.Exit(1) from None
    except Exception as e:
        handle_error(e, f"Build failed: {e}")
        raise typer.Exit(1) from None


@app.command()
def serve(
    repo_path: Annotated[
        Path, typer.Argument(help="Path to Python repository to serve documentation for", resolve_path=True)
    ],
    host: Annotated[
        str, typer.Option("--host", help="Server host address", rich_help_panel="Server Options")
    ] = "127.0.0.1",
    port: Annotated[
        int, typer.Option("--port", help="Server port", min=1, max=65535, rich_help_panel="Server Options")
    ] = 8000,
) -> None:
    """Serve documentation with live preview using uvx mkdocs.

    This command uses uvx to run mkdocs serve with all necessary plugins
    in an isolated environment, without requiring mkdocs to be installed
    in the target project.

    Args:
        repo_path: Path to the repository
        host: Server host address
        port: Server port
    """
    try:
        # Validate environment before serving
        console.print()
        all_passed, results = validate_environment(repo_path, check_mkdocs=True, auto_install_doxygen=True)
        display_validation_results(results, title="Pre-Serve Validation")
        console.print()

        if not all_passed:
            display_message(
                "Validation failed - please fix the issues above before serving.",
                MessageType.ERROR,
                title="Validation Failed",
            )
            raise typer.Exit(1)

        display_message(
            f"Starting documentation server for [bold cyan]{repo_path}[/bold cyan]...\n"
            f"Server address: [bold cyan]http://{host}:{port}[/bold cyan]\n"
            f"Press Ctrl+C to stop",
            MessageType.INFO,
            title="Documentation Server",
        )

        exit_code = serve_docs(repo_path, host=host, port=port)

        if exit_code == 0:
            display_message("Server stopped", MessageType.INFO, title="Server Stopped")
        else:
            display_message(f"Server failed with exit code {exit_code}", MessageType.ERROR, title="Server Failed")
            raise typer.Exit(exit_code)

    except FileNotFoundError as e:
        handle_error(e, str(e))
        raise typer.Exit(1) from None
    except Exception as e:
        handle_error(e, f"Server failed: {e}")
        raise typer.Exit(1) from None


@app.callback()
def main(
    ctx: typer.Context, verbose: Annotated[bool, typer.Option("--verbose", "-v", help="Enable verbose output")] = False
) -> None:
    """Mkapidocs - Automated documentation setup tool."""
    if ctx.invoked_subcommand is None:
        console.print(ctx.get_help())
        raise typer.Exit(0)

    ctx.obj = {"verbose": verbose}


if __name__ == "__main__":
    app()
