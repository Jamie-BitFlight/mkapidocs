# Coding Conventions

**Analysis Date:** 2026-02-07

## Naming Patterns

**Files:**
- Module files: `snake_case.py` (e.g., `cli.py`, `generator.py`, `project_detection.py`)
- Test files: `test_*.py` (e.g., `test_cli_commands.py`, `test_feature_detection.py`)
- Template files: `*_template.py` (e.g., `c_api_md_template.py`, `cli_md_template.py`)

**Functions:**
- Use `snake_case` for function names
- Private functions: Prefix with `_` (e.g., `_find_git_root()`, `_contains_c_files()`)
- Functions with Typer decorators use `snake_case` (e.g., `setup()`, `build()`, `serve()`)

**Variables:**
- Use `snake_case` for all variables: `repo_path`, `mock_repo_path`, `is_installed`, `c_extensions`
- Local variables in functions: `snake_case`
- Module-level constants: `UPPER_CASE` (e.g., `MKDOCS_FILE = "mkdocs.yml"`, `CACHE_DIR`)

**Types:**
- Classes: `PascalCase` (e.g., `PyprojectConfig`, `ValidationResult`, `MessageType`, `CIProvider`)
- Enums: `PascalCase` class, `UPPER_CASE` members (e.g., `MessageType.ERROR`, `CIProvider.GITHUB`)
- Type aliases: `PascalCase` (e.g., `TomlPrimitive`, `TomlTable`, `GitLabIncludeEntry`)

## Code Style

**Formatting:**
- Tool: `ruff format` with `quote-style = "double"`
- Line length: 120 characters (enforced by ruff, E501 in ignore list for overflow)
- Import sorting: isort-style via ruff with `combine-as-imports = true`
- Indentation: 4 spaces (Python), 2 spaces (YAML, JSON, TOML)
- Line endings: LF only (`end_of_line = "lf"`)
- Final newline: Always include

**Linting:**
- Tool: `ruff check` with extensive rule set (preview mode enabled)
- Mode: Strict (auto-fixes enabled: `fix = true`, `unsafe-fixes = true`)
- Type checking: `mypy` in strict mode + `basedpyright` basic mode
- Max complexity: 12 (McCabe)

**Key rules enforced:**
- `ANN`: All functions must have type annotations (including return types)
- `D`: Google-style docstrings required (enforced by ruff pydocstyle)
- `E501`: Line length relaxed in tests only
- `S`: Security checks (disabled in tests)
- `T20`: No bare `print()` in source (allowed in tests and CI output)
- `F401`: Unused imports unfixable (must manually remove)

**Rules relaxed for tests** (in `**/tests/**`):
- Security checks disabled
- Docstring requirements relaxed
- Type annotations optional for test fixtures/methods
- Local imports acceptable in test helpers
- Private name imports allowed for testing internals
- `camelCase` allowed in test names when testing API fields

## Import Organization

**Order (using ruff isort):**

1. Future imports: `from __future__ import annotations`
2. Standard library: `from pathlib import Path`, `import sys`, `import os`
3. Third-party: `import typer`, `from pydantic import BaseModel`, `import httpx`
4. Local package: `from mkapidocs.cli import app`, `from mkapidocs.models import CIProvider`
5. TYPE_CHECKING imports: Wrapped in `if TYPE_CHECKING:` block

**Path Aliases:**
- No path aliases configured - always use full relative imports
- All imports are absolute from package root (e.g., `from mkapidocs.models import ...`)
- Example: `from mkapidocs.cli import app` not relative imports

**Example from `cli.py`:**
```python
from __future__ import annotations

from pathlib import Path
from typing import Annotated

import httpx
import typer
from rich.console import Console
from tomlkit.exceptions import TOMLKitError

from mkapidocs.builder import build_docs, is_running_in_target_env, serve_docs
from mkapidocs.generator import (
    console as generator_console,
    display_message,
    setup_documentation,
)
from mkapidocs.models import CIProvider, MessageType
from mkapidocs.validators import (
    console as validators_console,
    display_validation_results,
    validate_environment,
)
```

## Error Handling

**Patterns:**
- Custom exception: `YAMLError` from `ruamel.yaml` (re-exported in `yaml_utils.py`)
- Catch specific exceptions, never bare `except:`
- Use `suppress()` from contextlib for intentionally ignored exceptions (see `yaml_utils.py`)
- Raise `FileNotFoundError` when files don't exist (e.g., `read_pyproject()`)
- Raise `ValueError` for invalid values/parameters
- Raise `RuntimeError` for operational errors (e.g., missing build dependencies)
- Raise `typer.Exit(1)` to signal CLI error with exit code 1

**Example from `cli.py`:**
```python
def handle_error(error: Exception, user_message: str | None = None) -> None:
    """Handle and display errors in a user-friendly way."""
    error_msg = user_message or str(error)
    display_message(error_msg, MessageType.ERROR)
    raise typer.Exit(1)

# In setup command:
try:
    result = setup_documentation(repo_path, ci_provider, effective_site_url, c_source_dirs)
except FileNotFoundError as e:
    handle_error(e, f"Repository setup failed: {e}")
except ValueError as e:
    handle_error(e, str(e))
except TOMLKitError as e:
    handle_error(e, f"Failed to parse pyproject.toml: {e}")
except YAMLError as e:
    handle_error(e, f"Failed to parse YAML configuration: {e}")
except httpx.RequestError as e:
    handle_error(e, f"Network request failed (GitLab API): {e}")
except OSError as e:
    handle_error(e, f"File system error: {e}")
```

## Logging

**Framework:** `Rich` library for console output (no traditional logging framework)

**Key abstractions:**
- Shared console: `from mkapidocs.console import console` (single instance)
- Display function: `from mkapidocs.generator import display_message` with `MessageType` enum
- Message types: `MessageType.ERROR`, `MessageType.SUCCESS`, `MessageType.INFO`, `MessageType.WARNING`

**Patterns:**
- Use `display_message(msg, MessageType.INFO, title="Title")` for structured output
- Rich Panels with styled borders for user-facing messages
- Tables with `console.print(table)` for formatted data
- Never use bare `print()` in source code (only in tests allowed)
- Suppress output with `--quiet` flag (sets `console.quiet = True` globally)

**Example from `generator.py`:**
```python
def display_message(
    message: str, message_type: MessageType = MessageType.INFO, title: str | None = None
) -> None:
    """Display a formatted message panel."""
    color, default_title = message_type.value
    panel_title = title or default_title

    panel = Panel.fit(
        message,
        title=f"[bold {color}]{panel_title}[/bold {color}]",
        border_style=color,
        padding=(1, 2),
    )
    console.print(panel)
```

## Comments

**When to Comment:**
- Comments are minimal - code should be self-documenting
- Internal comments explain WHY, not WHAT
- Test functions always include structured comments: "Tests:", "How:", "Why:"

**Docstrings (Google-style, enforced by ruff D):**
- Required on all functions, classes, and modules
- Single-line docstring for simple functions: `"""Short description."""`
- Multi-line for complex functions with Args, Returns, Raises sections

**Example from `project_detection.py`:**
```python
def read_pyproject(repo_path: Path) -> PyprojectConfig:
    """Read and parse pyproject.toml into typed configuration.

    Args:
        repo_path: Path to repository.

    Returns:
        Parsed and validated pyproject.toml configuration.

    Raises:
        FileNotFoundError: If pyproject.toml does not exist.
    """
```

## Function Design

**Size:**
- Prefer small, focused functions
- Max complexity: 12 (McCabe score enforced by ruff)
- Large modules split logical concerns (e.g., `generator.py` is largest at ~400 lines)

**Parameters:**
- Use type hints on all parameters
- Prefer positional parameters for required arguments
- Use `Annotated` from typing for Typer CLI parameters with rich help text
- Group related parameters near each other

**Return Values:**
- Always specify return type hint (even `-> None` for functions with no return)
- Use `| None` for optional returns (union syntax from `from __future__ import annotations`)
- Return specific types, never generic `object` or `Any` unless unavoidable

**Example from `validators.py`:**
```python
@classmethod
def is_installed(cls) -> tuple[bool, str | None]:
    """Check if Doxygen is installed and get version.

    Returns:
        Tuple of (is_installed, version_string)
    """
    doxygen_path = which("doxygen")
    if not doxygen_path:
        return False, None
```

## Module Design

**Exports:**
- Explicitly declare `__all__` in modules with public API (e.g., `yaml_utils.py`)
- Private functions prefixed with `_` not listed in `__all__`
- Re-export important exceptions at module level

**Barrel Files:**
- `templates/__init__.py` exports all template constants
- `__init__.py` at package root is minimal

**Data Models:**
- Use Pydantic `BaseModel` for config validation and parsing
- Use `@dataclass` for simple data holders (e.g., `ValidationResult`, `GitLabCIConfig`)
- Type aliases for complex TOML types (see `models.py`: `TomlPrimitive`, `TomlTable`, etc.)

**Example from `yaml_utils.py` (explicit exports):**
```python
__all__ = [
    "YAMLError",
    "append_to_yaml_list",
    "load_yaml",
    "load_yaml_preserve_format",
    "merge_mkdocs_yaml",
]
```

## Special Patterns

**pathlib.Path Usage:**
- Always use `Path` from `pathlib`, never string paths
- Use `Path.cwd()` for current directory, `Path.home()` for home
- `.resolve()` to normalize paths with `..` and symlinks
- `.relative_to()` for computing relative paths
- Use `/` operator for path concatenation: `repo_path / "mkdocs.yml"`

**Conditional Logic:**
- Prefer `match` statements over if/elif chains (Python 3.10+ syntax used in `cli.py`)
- Example from `_validate_provider()`:
```python
match provider.lower():
    case "github":
        return CIProvider.GITHUB
    case "gitlab":
        return CIProvider.GITLAB
    case _:
        handle_error()
```

**Type Hints:**
- Use `| None` instead of `Optional[]` (requires `from __future__ import annotations`)
- Use `from typing import TYPE_CHECKING, cast` for complex type operations
- Forward references as strings only in base class definitions

---

*Convention analysis: 2026-02-07*
