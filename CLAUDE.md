# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Required Skills

**The orchestrator must load the python3-development skill before working on any task.**

**The orchestrator must mention in the prompts provided to the sub-agents that the skills for mkdocs, hatchling, uv, and python3-development should be enabled before starting their task.**

## Project Overview

mkapidocs is an installable Python package that automates MkDocs documentation setup for Python projects. It supports both GitHub Pages and GitLab Pages deployment, with intelligent feature detection for C/C++ code and Typer CLI applications.

## Architecture

### Package Structure

The project follows standard Python package layout with hatchling build system:

```
mkapidocs/
├── packages/
│   └── mkapidocs/           # Main package
│       ├── __init__.py      # Package init with version
│       ├── cli.py           # Typer CLI entry point
│       ├── builder.py       # Build/serve logic with environment detection
│       ├── generator.py     # Content generation and CI/CD setup
│       ├── validators.py    # Environment and project validation
│       ├── models.py        # Pydantic models and enums
│       ├── yaml_utils.py    # YAML merge utilities
│       ├── version.py       # Version string
│       ├── templates/       # Jinja2 and static templates
│       │   ├── mkdocs.yml.j2        # MkDocs config template
│       │   ├── pages.yml            # GitHub Actions workflow
│       │   ├── gitlab-ci.yml        # GitLab CI workflow
│       │   └── *_template.py        # Markdown content templates
│       └── resources/       # Runtime resources
│           └── gen_ref_pages.py     # API docs generation script
├── tests/                   # Test suite
├── pyproject.toml           # Package configuration
└── README.md
```

### Key Components

The package is organized into separate modules:

- **cli.py**: Typer CLI entry point with commands (version, info, setup, build, serve)
- **generator.py**: Content generation, CI/CD workflow creation, feature detection, YAML merge system
- **builder.py**: Build/serve logic with target environment detection and uvx fallback
- **validators.py**: Environment and project validation with DoxygenInstaller
- **models.py**: CIProvider enum, MessageType enum, Pydantic models
- **yaml_utils.py**: Smart YAML merging utilities
- **templates/**: Jinja2 templates and static workflow files
- **resources/**: Runtime resources (gen_ref_pages.py copied to target projects)

### Template Rendering Flow

1. Detect project features (C code, Typer CLI, private registry)
2. Read pyproject.toml metadata
3. Render Jinja2 templates with detected features
4. Write generated files to target project directory

### Target Project Environment Integration

For CLI documentation to render correctly, mkapidocs detects when it's installed as a dev dependency in the target project and runs `mkdocs build` directly within that environment. This allows mkdocs-typer2 to import the target project's CLI module with all dependencies available.

The flow is:

1. External call: `mkapidocs build /path/to/project`
2. Detects mkapidocs in target's dev deps → calls `uv run mkapidocs build .` with `MKAPIDOCS_INTERNAL_CALL=1`
3. Internal call: Detects `MKAPIDOCS_INTERNAL_CALL=1` → calls `mkdocs build` directly
4. mkdocs-typer2 imports CLI module successfully → full documentation generated

## CLI Commands

All commands follow the pattern: `mkapidocs <command> [args]` or `uv run mkapidocs <command> [args]`

- `version` - Show version information
- `info` - Display package metadata and installation details
- `setup <path> [--provider {github|gitlab}] [--site-url URL]` - Set up MkDocs documentation for a Python project
- `build <path> [--strict] [--output-dir PATH]` - Build documentation to static site
- `serve <path> [--host HOST] [--port PORT]` - Serve documentation with live preview

### setup Command

The `setup` command configures MkDocs documentation and CI/CD workflows for your project.

**Provider Auto-Detection:**

1. First: Checks git remote URL for `github` or `gitlab` word in the domain (supports enterprise instances)
2. Second: Checks filesystem for `.gitlab-ci.yml`, `.gitlab/`, or `.github/` directories
3. Third: Fails with error if provider cannot be determined

**Site URL Detection (GitLab):**

For GitLab projects, mkapidocs can query the GitLab GraphQL API to get the actual Pages URL:

1. Set `GITLAB_TOKEN` or `CI_JOB_TOKEN` environment variable (requires `read_api` scope)
2. If Pages is deployed, the exact URL is retrieved from the API
3. If Pages is not yet deployed, a heuristic URL is used as a placeholder

**Options:**

- `--provider {github|gitlab}` - Explicitly specify CI/CD provider (bypasses auto-detection)
- `--site-url URL` - Explicitly specify the Pages URL (bypasses all URL detection)
- `--c-source-dirs DIRS` - Directories containing C/C++ source code (comma-separated)
- `--quiet, -q` - Suppress output (only show errors)

**Examples:**

```bash
# Auto-detect provider from git remote or filesystem
mkapidocs setup /path/to/project

# Explicitly use GitHub Actions
mkapidocs setup /path/to/project --provider github

# Explicitly use GitLab CI
mkapidocs setup /path/to/project --provider gitlab

# Explicitly specify the Pages URL (useful for enterprise GitLab)
mkapidocs setup /path/to/project --site-url https://mygroup.pages.gitlab.example.com/myproject

# With GITLAB_TOKEN for API-based URL detection
GITLAB_TOKEN=glpat-xxx mkapidocs setup /path/to/project

# Other commands
mkapidocs version
mkapidocs build . --strict
mkapidocs serve .
```

## Development Commands

### Prerequisites

Ensure mkdocs skill is enabled at task start (this repo uses MkDocs for its own docs).

### Linting and Formatting

```bash
# Run ruff linter
uv run ruff check packages/mkapidocs/

# Run ruff formatter
uv run ruff format packages/mkapidocs/

# Run mypy type checker
uv run mypy packages/mkapidocs/

# Run basedpyright type checker
uv run basedpyright packages/mkapidocs/
```

### Testing

```bash
# Run tests with coverage
uv run pytest

# Run specific test file
uv run pytest tests/test_cli_commands.py -v
```

### Running the Package

```bash
# Via uv run
uv run mkapidocs --help

# Test on example project
uv run mkapidocs setup /path/to/test/project
```

### Building This Project's Documentation

```bash
# Serve docs locally
uv run mkapidocs serve .

# Build static site
uv run mkapidocs build .
```

### Pre-commit Hooks

The project uses pre-commit for automated quality checks. The configuration includes:

- **mkapidocs-regen**: Runs `mkapidocs setup .` to regenerate documentation when Python files, pyproject.toml, or mkdocs.yml change
- **Standard hooks**: trailing-whitespace, end-of-file-fixer, check-yaml, check-json, check-toml
- **Ruff**: Python linting and formatting
- **Mypy/Basedpyright**: Type checking
- **Shellcheck**: Shell script linting
- **Prettier**: YAML/JSON/Markdown formatting

## Important Implementation Details

### Git URL Detection

The package extracts Pages URLs from git remotes. It handles:

- SSH format: `git@github.com:user/repo.git` or `git@gitlab.com:user/repo.git`
- HTTPS format: `https://github.com/user/repo.git` or `https://gitlab.com/user/repo.git`
- Converts to Pages URL format: `https://user.github.io/repo/` or `https://user.gitlab.io/repo/`

### Source Path Detection

The `get_source_paths_from_pyproject()` function extracts package locations from pyproject.toml to set PYTHONPATH for mkdocstrings. It checks:

- `[tool.hatch.build.targets.wheel]` with `packages` or `sources` mapping
- `[tool.setuptools.packages.find]` with `where` key
- Falls back to `src/` if no explicit configuration

### Doxygen Installer

For C/C++ documentation, the package can download and install Doxygen if not present:

- Downloads from official GitHub releases
- Verifies SHA256 checksum
- Extracts to `~/.local/bin/`
- Platform-specific (Linux x86_64 only currently)

### CLI Module Detection

For Typer CLI apps, the package attempts to find the CLI entry point by:

1. Checking `[project.scripts]` for entry points
2. Parsing entry point format `module:app_object`
3. Falling back to common patterns if not found

## MkDocs Configuration Strategy

The generated mkdocs.yml is feature-conditional:

- Base plugins always included: search, mkdocstrings (Python), mermaid2, termynal
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

## CI/CD Integration

### GitHub Actions

Creates `.github/workflows/pages.yml` with:

- `actions/checkout@v4` for code checkout
- `actions/setup-python@v5` for Python 3.11 setup
- `astral-sh/setup-uv@v4` for uv installation
- Runs `uv run mkapidocs build . --strict` to build documentation
- `actions/upload-pages-artifact@v3` and `actions/deploy-pages@v4` for GitHub Pages deployment
- Deploys to GitHub Pages on pushes to main branch only

### GitLab CI

Creates `.gitlab/workflows/pages.gitlab-ci.yml` with a `pages` job:

- Uses `ghcr.io/astral-sh/uv:python3.11` image
- Runs `uv run mkapidocs build . --strict`
- Deploys public/ directory to GitLab Pages
- Runs only on default branch

**Note:** Before creating the workflow, `create_gitlab_ci()` checks if `.gitlab-ci.yml` already has a `pages` job. If found, it skips creation and warns the user to update their existing job to use mkapidocs.

## Validation System

Before setup, the package validates:

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
3. Write to target project (not this package's directory)
4. Display success message with rich formatting

## Working with Templates

Templates are stored in `packages/mkapidocs/templates/`:

- **mkdocs.yml.j2**: Jinja2 template for MkDocs configuration
- **pages.yml**: Static GitHub Actions workflow template
- **gitlab-ci.yml**: Static GitLab CI workflow template
- **\*\_template.py**: Python modules with markdown content templates

To modify:

1. Edit the appropriate template file in `packages/mkapidocs/templates/`
2. For Jinja2 templates (.j2), template variables come from feature detection in `generator.py`
3. Test by running `uv run mkapidocs setup` on a sample project

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

## Dependencies

Runtime dependencies are declared in `[project] dependencies` in pyproject.toml:

- typer: CLI framework
- jinja2: Template rendering
- tomli-w: TOML writing
- python-dotenv: Environment variables
- pydantic: Data validation
- rich: Terminal formatting
- httpx: HTTP client for Doxygen downloads
- pyyaml: YAML parsing/writing
- mkdocs + plugins: Documentation generation

Development dependencies are in `[dependency-groups] dev`.
