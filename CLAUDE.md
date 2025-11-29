# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Required Skills

**The orchestrator must load the python3-development skill before working on any task.**

**The orchestrator must mention in the prompts provided to the sub-agents that the skills for mkdocs, hatchling, uv, and python3-development should be enabled before starting their task.**

## Project Overview

mkapidocs is a PEP 723 standalone script that automates MkDocs documentation setup for Python projects. It's designed to be self-contained with no installation required - dependencies are declared inline using PEP 723 script metadata and managed by uv.

## Architecture

### PEP 723 Standalone Script Model

The main executable is `mkapidocs.py` - a single Python script with inline dependency declarations. This architecture means:

- **No package structure**: There's no `src/` or traditional Python package layout
- **No setup.py/setup.cfg**: All metadata is in `pyproject.toml` for linting/testing only
- **uv execution**: Script runs via `#!/usr/bin/env -S uv --quiet run --active --script` shebang
- **Self-contained dependencies**: All dependencies declared in `# /// script` block at top of file

### Key Components

The script is organized into distinct functional sections (mkapidocs.py:1-2396):

1. **Template System** (lines 62-430): Inline Jinja2 templates for all generated files (mkdocs.yml, GitHub Actions, markdown docs, gen_ref_pages.py)
2. **Exception Classes** (lines 453-458): CLIError and BuildError for error handling
3. **Message Types** (lines 461-467): MessageType enum for display formatting
4. **Validation System** (lines 475-1090): Environment and project validation with DoxygenInstaller and SystemValidator classes
5. **Feature Detection** (lines 1093-1350): Git URL parsing, C/C++ code detection, Typer CLI detection, private registry detection
6. **YAML Merge System** (lines 1352-1550): Smart merging of mkdocs.yml preserving user customizations
7. **Content Generation** (lines 1552-1900): Functions that render templates and create documentation structure
8. **Build/Serve Commands** (lines 1970-2150): MkDocs integration for building and serving docs
9. **Typer CLI Commands** (lines 2152-2396): version, info, setup, build, serve commands

### Template Rendering Flow

1. Detect project features (C code, Typer CLI, private registry)
2. Read pyproject.toml metadata
3. Render Jinja2 templates with detected features
4. Write generated files to target project directory

## CLI Commands

All commands follow the pattern: `./mkapidocs.py <command> [args]`

- `version` - Show version information
- `info` - Display package metadata and installation details
- `setup <path> [--provider {github|gitlab}]` - Set up MkDocs documentation for a Python project
- `build <path>` - Build documentation to static site
- `serve <path>` - Serve documentation with live preview

### setup Command

The `setup` command configures MkDocs documentation and CI/CD workflows for your project.

**Provider Auto-Detection:**

1. First: Checks git remote URL for `github.com` or `gitlab.com`
2. Second: Checks filesystem for `.gitlab-ci.yml`, `.gitlab/`, or `.github/` directories
3. Third: Fails with error if provider cannot be determined

**Options:**

- `--provider {github|gitlab}` - Explicitly specify CI/CD provider (bypasses auto-detection)
- `--github-url-base <url>` - Override GitHub Pages URL (for backward compatibility)

**Examples:**

```bash
# Auto-detect provider from git remote or filesystem
./mkapidocs.py setup /path/to/project

# Explicitly use GitHub Actions
./mkapidocs.py setup /path/to/project --provider github

# Explicitly use GitLab CI
./mkapidocs.py setup /path/to/project --provider gitlab

# Other commands
./mkapidocs.py version
./mkapidocs.py build . --strict
./mkapidocs.py serve .
```

## Development Commands

### Prerequisites

Ensure mkdocs skill is enabled at task start (this repo uses MkDocs for its own docs).

### Linting and Formatting

```bash
# Run ruff linter
uv run ruff check mkapidocs.py

# Run ruff formatter
uv run ruff format mkapidocs.py

# Run mypy type checker
uv run mypy mkapidocs.py

# Run basedpyright type checker
uv run basedpyright mkapidocs.py
```

### Testing

No test suite exists yet. When adding tests, they should go in `tests/` directory.

### Running the Script

```bash
# Direct execution (uses shebang)
./mkapidocs.py --help

# Via uv (alternative)
uv run mkapidocs.py --help

# Test on example project
./mkapidocs.py setup /path/to/test/project
```

### Building This Project's Documentation

```bash
# Serve docs locally
./mkapidocs.py serve .

# Build static site
./mkapidocs.py build .
```

### Pre-commit Hooks

The project uses pre-commit for automated quality checks. The configuration includes:

- **mkapidocs-regen**: Runs `./mkapidocs.py setup .` to regenerate documentation when Python files, pyproject.toml, or mkdocs.yml change
- **Standard hooks**: trailing-whitespace, end-of-file-fixer, check-yaml, check-json, check-toml
- **Ruff**: Python linting and formatting
- **Mypy/Basedpyright**: Type checking with PEP 723 dependency installation
- **Shellcheck**: Shell script linting
- **Prettier**: YAML/JSON/Markdown formatting
- **shfmt**: Shell script formatting

Note: The `install-pep723-deps` hook extracts dependencies from PEP 723 script blocks and installs them before type checking.

## Important Implementation Details

### Git URL Detection (lines 1093-1173)

The script extracts GitHub Pages URLs from git remotes. It handles:

- SSH format: `git@github.com:user/repo.git`
- HTTPS format: `https://github.com/user/repo.git`
- Converts to GitHub Pages URL format: `https://user.github.io/repo/`

### Source Path Detection (lines 1760-1814)

The `get_source_paths_from_pyproject()` function extracts package locations from pyproject.toml to set PYTHONPATH for mkdocstrings. It checks:

- `[tool.hatch.build.targets.wheel]` with `packages` or `sources` mapping
- `[tool.setuptools.packages.find]` with `where` key
- Falls back to `src/` if no explicit configuration

### Doxygen Installer (lines 492-658)

For C/C++ documentation, the script can download and install Doxygen if not present:

- Downloads from official GitHub releases
- Verifies SHA256 checksum
- Extracts to `~/.local/bin/`
- Platform-specific (Linux x86_64 only currently)

### CLI Module Detection (lines 1237-1329)

For Typer CLI apps, the script attempts to find the CLI entry point by:

1. Checking `[project.scripts]` for entry points
2. Parsing entry point format `module:app_object`
3. Falling back to common patterns if not found

## MkDocs Configuration Strategy

The generated mkdocs.yml is feature-conditional:

- Base plugins always included: search, mkdocstrings (Python), mermaid2, termynal, recently-updated
- Conditional plugins based on detection:
  - `mkdocs-typer2` if Typer dependency found
  - `mkdoxy` if C/C++ files found in source/
  - `gen-files` and `literate-nav` for auto-generated API docs

## Smart YAML Merge System

A critical feature is the non-destructive mkdocs.yml merging system that preserves user customizations:

### How It Works

When `setup` is run on a project that already has mkdocs.yml:

1. **Load existing config**: Parse current user configuration
2. **Generate new template**: Render fresh template from features
3. **Smart merge**: Preserve user values while updating template-managed sections
4. **Display changes**: Show table of added/updated/preserved settings

### What Gets Preserved

- Custom navigation structure
- Additional plugins beyond template defaults
- Custom theme features
- Extra configuration sections
- User-added markdown extensions
- Custom site metadata

### What Gets Updated

- Plugin configurations (e.g., mkdocstrings handlers paths)
- Core plugin list (adds new feature-detected plugins)
- Template-managed default values

This allows users to customize their docs and safely re-run setup to pick up new features or template improvements.

## GitHub Actions Integration

Generated `.github/workflows/pages.yml` uses:

- `actions/checkout@v4` for code checkout
- `actions/setup-python@v5` for Python 3.11 setup
- `astral-sh/setup-uv@v4` for uv installation
- Runs `./mkapidocs.py build . --strict` to build documentation
- `actions/upload-pages-artifact@v3` and `actions/deploy-pages@v4` for GitHub Pages deployment
- Deploys to GitHub Pages on pushes to main branch only

## Validation System

Before setup, the script validates:

1. **System requirements**: Python version, uv installation, mkdocs availability
2. **Project requirements**: pyproject.toml exists, has required metadata
3. **Optional requirements**: Doxygen for C code (offers to install), git for URL detection

Validation results displayed in rich tables with pass/fail/warning status.

## Error Handling Strategy

- Validation errors: Display detailed results table, exit before making changes
- Build/serve errors: Capture subprocess output, display with rich formatting
- User-facing errors: Use custom MessageType enum (INFO, SUCCESS, WARNING, ERROR) with rich panels
- Technical errors: Raise CLIError or BuildError with context

## File Generation Pattern

All content generation functions follow this pattern:

1. Check if target file/directory exists
2. Render Jinja2 template with context variables
3. Write to target project (not this script's directory)
4. Display success message with rich formatting

## Working with Templates

Templates are inline string constants (lines 62-430). To modify:

1. Find template constant (e.g., `MKDOCS_YML_TEMPLATE`)
2. Edit Jinja2 syntax directly in the constant
3. Template variables come from feature detection functions
4. Test by running setup on a sample project

## Code Quality Standards

- Python 3.11+ required (uses modern type hints with `|` unions)
- Google-style docstrings enforced by ruff
- Type hints required on all functions (mypy strict mode)
- Line length: 120 characters
- No suppression of linting errors without fixing root cause

## Conventional Commits

This project follows the [Conventional Commits v1.0.0](https://www.conventionalcommits.org/en/v1.0.0/) specification for commit messages.

### Format

```
<type>[optional scope]: <description>

[optional body]

[optional footer(s)]
```

### Core Types (from spec)

- **feat**: introduces new functionality (triggers MINOR version bump in semantic versioning)
- **fix**: addresses bugs in the codebase (triggers PATCH version bump)

### Additional Types (allowed but not in core spec)

- **docs**: documentation only changes
- **style**: code style changes (formatting, whitespace)
- **refactor**: code changes that neither fix bugs nor add features
- **perf**: performance improvements
- **test**: adding or correcting tests
- **build**: changes to build system or dependencies
- **ci**: changes to CI configuration
- **chore**: other changes that don't modify src or test files

### Breaking Changes

Breaking changes trigger MAJOR version bumps and can be indicated in two ways:

1. Add `!` after type/scope: `feat!: change API response format`
2. Add footer: `BREAKING CHANGE: detailed description of breaking change`

### Rules from Specification

- Type is **mandatory** and must be followed by colon and space
- Description **must immediately follow** the colon and space
- Description is typically lowercase (not mandated by spec)
- No period at end of description (convention, not mandated)
- Body **must begin one blank line after** the description
- Footer(s) may be provided one blank line after body
- `BREAKING CHANGE` **must be uppercase** in footer
- All other elements are case-insensitive

### Examples

```
feat: add user authentication support

feat(api): add pagination to list endpoints

fix: correct timezone handling in date calculations

docs: update installation instructions in README

refactor!: simplify error handling

BREAKING CHANGE: error responses now use standardized format
```

## PEP 723 Development Pattern

The script uses PEP 723 inline script metadata, which affects the development workflow:

### Dependencies

All runtime dependencies are declared in the `# /// script` block at the top of the mkapidocs.py file (lines 2-15). These include:

- typer: CLI framework
- jinja2: Template rendering
- tomli-w: TOML writing
- python-dotenv: Environment variables
- pydantic: Data validation
- rich: Terminal formatting
- httpx: HTTP client for Doxygen downloads
- pyyaml: YAML parsing/writing

Development dependencies (linting, testing) are in pyproject.toml's `[dependency-groups]`.

### Type Checking Workflow

Type checkers (mypy, basedpyright) need access to PEP 723 dependencies:

1. Pre-commit hook `install-pep723-deps` extracts dependencies from script block
2. Runs `uv export --script mkapidocs.py | uv pip install -r -` to install them
3. Then mypy/basedpyright can resolve imports during type checking

### Running Type Checkers Manually

```bash
# Ensure PEP 723 deps are installed first
uv export --script mkapidocs.py | uv pip install -r -

# Then run type checkers
uv run mypy mkapidocs.py
uv run basedpyright mkapidocs.py
```
