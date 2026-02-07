# Codebase Structure

**Analysis Date:** 2026-02-07

## Directory Layout

```
mkapidocs/
├── packages/mkapidocs/          # Python package source
│   ├── __init__.py              # Package init, exports __version__
│   ├── cli.py                   # Typer CLI entry point (515 lines)
│   ├── generator.py             # Core generation logic (1751 lines)
│   ├── builder.py               # Build/serve logic (472 lines)
│   ├── validators.py            # Environment validation (729 lines)
│   ├── project_detection.py     # Feature detection (264 lines)
│   ├── yaml_utils.py            # YAML handling (664 lines)
│   ├── models.py                # Pydantic models (343 lines)
│   ├── console.py               # Rich console helpers (65 lines)
│   ├── version.py               # Version via hatchling
│   └── templates/               # Template content
│       ├── __init__.py          # Template exports
│       ├── mkdocs.yml.j2        # MkDocs config template (Jinja2)
│       ├── pages.yml            # GitHub Actions workflow
│       ├── gitlab-ci.yml        # GitLab CI workflow
│       ├── index_md_template.py # Index page template
│       ├── install_md_template.py # Installation page template
│       ├── cli_md_template.py   # CLI docs page template
│       ├── python_api_md_template.py # Python API page template
│       └── c_api_md_template.py # C API page template
├── tests/                       # Test suite
│   ├── conftest.py              # Pytest fixtures
│   ├── test_cli_commands.py     # CLI command tests
│   ├── test_build_serve.py      # Build/serve tests
│   ├── test_feature_detection.py # Feature detection tests
│   ├── test_validation_system.py # Validation tests
│   ├── test_template_rendering.py # Template tests
│   ├── test_workflow_conflict.py # CI workflow tests
│   ├── test_gitlab_ci_update.py # GitLab CI tests
│   ├── test_auto_install.py     # Auto-install tests
│   ├── test_cli_utils.py        # CLI utility tests
│   └── test_pyproject_functions.py # pyproject.toml tests
├── docs/                        # MkDocs site source
│   └── generated/               # Generated documentation
├── .github/                     # GitHub Actions workflows
│   └── workflows/
│       └── ci.yml               # CI pipeline
├── pyproject.toml               # Package configuration
├── mkdocs.yml                   # MkDocs configuration
├── CLAUDE.md                    # Development guidelines
├── README.md                    # Project overview
└── .planning/codebase/          # GSD planning documents
    ├── ARCHITECTURE.md
    └── STRUCTURE.md
```

## Directory Purposes

**packages/mkapidocs/:**
- Purpose: Main Python package with all runnable code
- Contains: CLI entry point, core logic, models, utilities
- Key files: cli.py (entry point), generator.py (largest, orchestrates setup)

**packages/mkapidocs/templates/:**
- Purpose: Template content for generated files
- Contains: Python modules with content strings, Jinja2 config, static CI workflows
- Key files: mkdocs.yml.j2 (primary config template), pages.yml (GitHub workflow), gitlab-ci.yml (GitLab workflow)

**tests/:**
- Purpose: Test suite with >70% coverage requirement
- Contains: Unit and integration tests organized by module
- Run with: `uv run pytest`

**docs/:**
- Purpose: MkDocs site source for this project's documentation
- Contains: docs/generated/ (auto-generated API reference)
- Build with: `uv run mkapidocs build .`

**.github/workflows/:**
- Purpose: GitHub Actions CI/CD
- Contains: ci.yml with test → lint → release → pages jobs

## Key File Locations

**Entry Points:**
- `packages/mkapidocs/cli.py`: Main CLI entry point (Typer app)
- `packages/mkapidocs/__init__.py`: Package exports (__version__)

**Configuration:**
- `pyproject.toml`: Package metadata, dependencies, tool configs
- `mkdocs.yml`: This project's MkDocs configuration
- `pyproject.toml [tool.ruff]`: Linting/formatting config
- `pyproject.toml [tool.mypy]`: Type checking config

**Core Logic:**
- `packages/mkapidocs/generator.py`: setup_documentation(), file creation functions
- `packages/mkapidocs/project_detection.py`: Feature detection and git parsing
- `packages/mkapidocs/builder.py`: Two-phase execution, mkdocs build/serve
- `packages/mkapidocs/validators.py`: Environment validation, Doxygen installer

**Models and Utilities:**
- `packages/mkapidocs/models.py`: PyprojectConfig, CIProvider, GitLabCIConfig
- `packages/mkapidocs/yaml_utils.py`: YAML loading, merging, file changes display
- `packages/mkapidocs/console.py`: Shared Rich console helpers
- `packages/mkapidocs/version.py`: Version from git tags via hatchling

**Templates:**
- `packages/mkapidocs/templates/mkdocs.yml.j2`: MkDocs config (rendered with feature flags)
- `packages/mkapidocs/templates/pages.yml`: GitHub Actions workflow (written as-is)
- `packages/mkapidocs/templates/gitlab-ci.yml`: GitLab CI workflow (written as-is)
- `packages/mkapidocs/templates/*_md_template.py`: Markdown page content

**Testing:**
- `tests/conftest.py`: Fixtures for temp directories, mock repos, git setup
- `tests/test_cli_commands.py`: CLI command tests
- `tests/test_build_serve.py`: Build/serve execution tests

## Naming Conventions

**Files:**
- Modules: `snake_case.py` (e.g., `project_detection.py`, `yaml_utils.py`)
- Templates: `*_template.py` for content (e.g., `install_md_template.py`), `.j2` for Jinja2 (e.g., `mkdocs.yml.j2`)
- Tests: `test_*.py` (e.g., `test_cli_commands.py`)
- Workflows: `*.yml` for CI files (e.g., `pages.yml`)

**Directories:**
- Package: `packages/mkapidocs/` (supports monorepo structure)
- Submodules: Descriptive names (e.g., `templates/`)
- Tests: `tests/` at root level
- Generated: `docs/generated/` for auto-generated content

**Functions/Classes:**
- Functions: `snake_case` (e.g., `detect_c_code()`, `setup_documentation()`)
- Classes: `PascalCase` (e.g., `PyprojectConfig`, `ValidationResult`, `DoxygenInstaller`)
- Private functions: `_snake_case` prefix (e.g., `_detect_c_code_from_explicit()`)
- Constants: `UPPER_SNAKE_CASE` (e.g., `GITHUB_ACTIONS_PAGES_TEMPLATE`)

## Where to Add New Code

**New Feature (e.g., add Sphinx support):**
- Primary code: `packages/mkapidocs/generator.py` (add `create_sphinx_config()` function)
- Detection: `packages/mkapidocs/project_detection.py` (add `detect_sphinx_dependency()`)
- Validation: `packages/mkapidocs/validators.py` (add validation checks if needed)
- Templates: `packages/mkapidocs/templates/` (add template files)
- Tests: `tests/test_*.py` (add comprehensive test coverage)

**New CLI Command (e.g., `mkapidocs validate`):**
- Handler: `packages/mkapidocs/cli.py` (add `@app.command()` decorated function)
- Logic: New module or extend existing (e.g., `packages/mkapidocs/validators.py`)
- Tests: `tests/test_cli_commands.py`

**New Detection Function:**
- Implementation: `packages/mkapidocs/project_detection.py`
- Model updates: `packages/mkapidocs/models.py` if new data types needed
- Usage: Called from `generator.py` in `_detect_features()`
- Tests: `tests/test_feature_detection.py`

**New Validator:**
- Implementation: `packages/mkapidocs/validators.py`
- Called from: `validators.validate_environment()`
- Returns: `ValidationResult` dataclass
- Tests: `tests/test_validation_system.py`

**New Template:**
- Location: `packages/mkapidocs/templates/`
- Registration: Export in `packages/mkapidocs/templates/__init__.py`
- Usage: Reference in `generator.py` creation functions
- Tests: `tests/test_template_rendering.py`

**Utilities/Helpers:**
- Shared YAML ops: `packages/mkapidocs/yaml_utils.py`
- Shared display: `packages/mkapidocs/console.py`
- New module if needed: `packages/mkapidocs/new_module.py` (follow naming conventions)

## Special Directories

**packages/mkapidocs/templates/:**
- Purpose: Template content for generated files in target projects
- Generated: No (committed to repo)
- Committed: Yes (part of package distribution)
- Content types: Python modules with string constants, Jinja2 templates, static YAML

**tests/:**
- Purpose: Test suite with ≥70% coverage requirement
- Generated: No (manually written)
- Committed: Yes (critical for quality)
- Structure: Parallel to src with `test_*.py` files

**docs/generated/:**
- Purpose: Auto-generated API documentation
- Generated: Yes (via `mkdocs build`)
- Committed: No (in .gitignore)
- Updated: During documentation build

**.planning/codebase/:**
- Purpose: GSD mapping documents
- Generated: Yes (via `/gsd:map-codebase`)
- Committed: Yes (tracked in git)
- Contents: ARCHITECTURE.md, STRUCTURE.md, CONVENTIONS.md, TESTING.md, CONCERNS.md

## File Creation Pattern (in setup flow)

Target project's directory structure after `mkapidocs setup`:

```
target-project/
├── mkdocs.yml                   # Created if missing, merged if exists
├── docs/
│   ├── index.md                 # Created if missing
│   ├── installation.md          # Created if missing
│   ├── cli.md                   # Created if no Typer
│   ├── api/
│   │   ├── python.md            # Created if missing
│   │   └── c.md                 # Created if C code detected
│   └── generated/
│       └── (auto-generated API docs)
├── .github/workflows/
│   └── pages.yml                # Created (GitHub only)
├── .gitlab/
│   └── workflows/
│       └── pages.gitlab-ci.yml  # Created (GitLab only)
├── .gitlab-ci.yml               # Updated if exists (GitLab only)
└── .gitignore                   # Updated to add site/

```

---

*Structure analysis: 2026-02-07*
