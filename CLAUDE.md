# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Required Skills

**The orchestrator must load the python3-development skill before working on any task.**

**The orchestrator must mention in the prompts provided to the sub-agents that the skills for mkdocs, hatchling, uv, and python3-development should be enabled before starting their task.**

## Project Overview

mkapidocs is an installable Python package that automates MkDocs documentation setup for Python projects. It supports both GitHub Pages and GitLab Pages deployment, with intelligent feature detection for C/C++ code and Typer CLI applications.

## Development Commands

### Setup

```bash
uv sync                          # Install all dependencies
uv run mkapidocs --help          # Verify installation
```

### Testing

```bash
uv run pytest                                          # All tests with coverage (≥70% required)
uv run pytest tests/test_cli_commands.py -v            # Single test file
uv run pytest tests/test_cli_commands.py::test_name -v # Single test function
uv run pytest -k "test_pattern" -v                     # Tests matching pattern
```

### Linting and Formatting

```bash
uv run ruff check packages/mkapidocs/     # Lint (auto-fixes enabled)
uv run ruff format packages/mkapidocs/    # Format
uv run mypy packages/mkapidocs/           # Type check (strict mode)
uv run basedpyright packages/mkapidocs/   # Type check (basic mode)
```

### Documentation

```bash
uv run mkapidocs build .    # Build static site to site/
uv run mkapidocs serve .    # Live preview at localhost:8000
```

### Debugging

```bash
uv run mkapidocs --verbose build .   # Verbose build output
uv run mkapidocs info                # Show package metadata
```

## Architecture

### Module Organization

Source lives in `packages/mkapidocs/`. Key modules:

- **cli.py** — Typer CLI entry point with commands: version, info, setup, build, serve
- **generator.py** — Content generation, CI/CD workflow creation, YAML merge orchestration (largest module)
- **builder.py** — Build/serve logic with target environment detection and uvx fallback
- **validators.py** — Environment and project validation, DoxygenInstaller
- **project_detection.py** — Feature detection: C code, Typer CLI, private registries, git remotes, CI provider
- **yaml_utils.py** — Smart YAML merging with ruamel.yaml (preserves formatting and user customizations)
- **models.py** — CIProvider/MessageType enums, Pydantic models (PyprojectConfig, GitLabCIConfig)
- **console.py** — Shared Rich console instance and display helpers
- **version.py** — VCS-based version via hatchling, fallback to importlib.metadata
- **templates/** — Jinja2 templates (mkdocs.yml.j2), static CI workflows (pages.yml, gitlab-ci.yml), markdown content templates (*_template.py)
- **resources/** — Runtime resources for target projects

### Target Project Environment Integration

For CLI documentation to render correctly, mkapidocs uses a two-phase execution model to ensure mkdocs-typer2 can import the target project's CLI module:

1. External call: `mkapidocs build /path/to/project`
2. Detects mkapidocs in target's dev deps → calls `uv run mkapidocs build .` with `MKAPIDOCS_INTERNAL_CALL=1`
3. Internal call: Detects `MKAPIDOCS_INTERNAL_CALL=1` → calls `mkdocs build` directly
4. mkdocs-typer2 imports CLI module successfully → full documentation generated

### Smart YAML Merge System

When `setup` runs on a project with existing mkdocs.yml, `yaml_utils.py` performs non-destructive merging:

- **Preserves**: Custom navigation, additional plugins, theme features, user-added markdown extensions, custom site metadata
- **Updates**: Plugin configurations (paths), core plugin list (adds feature-detected plugins), template-managed defaults

### Template Rendering Flow

1. `project_detection.py` detects features (C code, Typer CLI, private registry)
2. Read pyproject.toml metadata
3. Render Jinja2 templates with detected features as context
4. Write generated files to target project directory (not this package's directory)

### Provider Auto-Detection

CI provider detection in `project_detection.py`:

1. Check git remote URL for `github` or `gitlab` in domain (supports enterprise instances)
2. Check filesystem for `.gitlab-ci.yml`, `.gitlab/`, or `.github/` directories
3. Fail with error if provider cannot be determined

Override with `--provider github|gitlab`.

## Code Standards

- **Python**: >=3.11,<3.13 — uses modern syntax (`str | None`, `dict[str, Any]`)
- **Line length**: 120 characters
- **Docstrings**: Google-style, enforced by ruff
- **Type hints**: Required on all functions (mypy strict mode)
- **Quotes**: Double quotes
- **Build system**: hatchling with hatch-vcs (version from git tags)

### Key Imports

```python
from pathlib import Path                                  # Always use Path, not string paths
from mkapidocs.models import CIProvider, MessageType      # Enums (GITHUB/GITLAB, INFO/SUCCESS/WARNING/ERROR)
from mkapidocs.models import PyprojectConfig              # Pydantic model for pyproject.toml
from mkapidocs.yaml_utils import CLIError                 # User-facing error type
from mkapidocs.generator import display_message           # Rich panel output
from mkapidocs.console import console                     # Shared Rich console instance
```

## Conventional Commits

Format: `<type>[optional scope]: <description>`

Types: `feat` (MINOR bump), `fix`/`perf` (PATCH bump), `docs`, `style`, `refactor`, `test`, `build`, `ci`, `chore`, `revert`

Breaking changes: Add `!` after type (`feat!: ...`) or `BREAKING CHANGE:` footer (MAJOR bump).

## CI/CD

GitHub Actions (`.github/workflows/ci.yml`): test → lint → release (main only) → pages (main only)

The package generates CI workflows for target projects:

- **GitHub**: `.github/workflows/pages.yml` — checkout, setup-python, setup-uv, build, deploy to GitHub Pages
- **GitLab**: `.gitlab/workflows/pages.gitlab-ci.yml` — uv docker image, build, deploy to GitLab Pages

## Dependencies

Runtime dependencies (pyproject.toml):

- **CLI/Config**: typer, jinja2, tomlkit, python-dotenv, pydantic
- **HTTP/YAML**: httpx, ruamel.yaml
- **Docs**: mkdocs, mkdocs-material, mkdocstrings[python], mkdocs-typer2, mkdoxy, mkdocs-literate-nav, mkdocs-mermaid2-plugin, termynal

Dev dependencies in `[dependency-groups] dev`: mypy, basedpyright, pytest, pytest-cov, pytest-mock, ruff, python-semantic-release.
