# GitHub Copilot Instructions for mkapidocs

## Repository Overview

**mkapidocs** automates MkDocs documentation setup for Python projects with GitHub/GitLab Pages deployment. Detects features (C/C++, Typer CLI, private registries) and generates docs infrastructure.

**Stack:** Python 3.11+ | hatchling | uv | 178 tests | 71% coverage | typer, mkdocs, jinja2, pydantic

## Prerequisites

**ALWAYS install uv first:** `python3 -m pip install uv && export PATH="$HOME/.local/bin:$PATH"`

## Essential Commands

### Setup (Run First)
```bash
uv sync                          # ~60s, installs 94 packages
uv run mkapidocs --help          # Verify installation
```

### Testing (REQUIRED before changes)
```bash
uv run pytest --cov              # ~3s, 178 tests, 71% coverage (≥70% required)
uv run pytest tests/test_cli_commands.py -v  # Single file
```
**Expected:** 178 pass, 71% coverage, emoji output normal

### Linting (Before Committing)
```bash
uv run ruff check .              # Auto-fixes issues
uv run ruff format .             # Format code
uv run mypy packages/mkapidocs/  # ~6s, expect 0 errors (optional)
```

### Documentation
```bash
uv run mkapidocs build .         # ~3s, outputs to site/
uv run mkapidocs serve .         # Live preview at :8000
```
**Expected:** unpkg.com warning normal (no internet), Doxygen warning normal

## Architecture

**Main Modules** (packages/mkapidocs/):
- `cli.py` (162 lines) - Typer CLI entry point
- `generator.py` (632 lines) - Template rendering, CI/CD setup (most complex)
- `builder.py` (161 lines) - Build/serve with environment detection
- `validators.py` (267 lines) - Environment/project validation
- `yaml_utils.py` (226 lines) - Smart YAML merge (preserves user customizations)
- `models.py` - Pydantic models, enums
- `templates/` - Jinja2 templates (mkdocs.yml.j2), workflows (pages.yml, gitlab-ci.yml), markdown templates

**Config:** pyproject.toml (hatchling, Python >=3.11,<3.13, line length 120, coverage ≥70%)

## CI/CD (.github/workflows/ci.yml)

**Jobs:** test (~30s), lint (~20s), release (main only), pages (main only)
**Triggers:** Push to main, all PRs
**Common Failures:**
- Coverage <70%: Add tests
- Ruff errors: Run `uv run ruff check .` locally
- Build failure: Check template syntax

## Code Standards

**Style:** 120 char lines | Type hints required (mypy strict) | Google docstrings | Double quotes
**Modern syntax:** `dict[str, Any]`, `str | None` (not `Dict`, `Optional`)
**Naming:** `snake_case` functions, `PascalCase` classes, `UPPER_SNAKE` constants

**Key Patterns:**
```python
from pathlib import Path                  # ALWAYS absolute paths
from mkapidocs.models import CLIError     # User-facing errors
from mkapidocs.console import display_message, MessageType
```

## Development Workflow

**Adding Features:** (1) Write tests first (2) Implement (3) Update templates if needed (4) Test & lint (5) Update README for user-facing changes

**Modifying Templates:** In `packages/mkapidocs/templates/` - Jinja2 (.j2), static YAML, or Python (*_template.py). After changes: `uv run mkapidocs setup . && uv run mkapidocs build .`

**Debugging:** `uv run mkapidocs --verbose build .` or `uv run mkapidocs info`

## Critical Behaviors

**YAML Merge (yaml_utils.py):** Preserves user nav/plugins/theme. Updates only plugin paths & core list. Never removes user content.

**Environment Detection:** For Typer apps, detects dev dependency → runs `uv run mkapidocs build .` with `MKAPIDOCS_INTERNAL_CALL=1` to prevent recursion.

**Git Detection:** Auto-detects GitHub/GitLab from remote URL (SSH/HTTPS). Falls back to filesystem (`.github/`/`.gitlab/`). Override with `--provider`.

**Doxygen:** Auto-installs only on Linux x86_64. Others: manual install required.

## Pre-Commit Checklist

```bash
uv run ruff check . && uv run ruff format .  # Lint & format
uv run pytest --cov                          # Test (178 pass, ≥70% coverage)
uv run mkapidocs build .                     # Verify docs build
git status                                   # Check changed files
```
**Required:** Tests pass, coverage ≥70%, ruff clean, docs build

## Commit Convention

**Format:** `<type>: <description>` | **Types:** feat, fix, docs, test, refactor, ci, chore
**Example:** `feat(cli): add --quiet flag` | **Breaking:** Add `!` after type

## Resources

**README.md** (user docs) | **CLAUDE.md** (technical detail) | **tests/README.md** (test info)

These instructions are tested and verified. Trust them unless proven incorrect.
