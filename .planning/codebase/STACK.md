# Technology Stack

**Analysis Date:** 2026-02-07

## Languages

**Primary:**
- Python 3.11, 3.12 - Full codebase written in Python with modern syntax (3.11+ required)

**Secondary:**
- YAML - MkDocs and CI/CD configuration
- Jinja2 templates - Documentation templates (mkdocs.yml.j2)
- Markdown - Documentation content and templates

## Runtime

**Environment:**
- Python >=3.11,<3.13
- Unix-like systems (Linux, macOS), Windows support for Doxygen installation

**Package Manager:**
- uv - Modern Python package manager, replacement for pip/pip-tools
- Lockfile: `uv.lock` (present)

## Frameworks

**Core:**
- Typer 0.19.2+ - CLI framework for command-line interface (`packages/mkapidocs/cli.py`)
- Jinja2 3.1.6+ - Template rendering for mkdocs.yml and documentation templates

**Documentation Generation:**
- MkDocs 1.6.0+ - Static site generator
- mkdocs-material 9.5.0+ - Material Design theme
- mkdocstrings[python] 0.26.0+ - Python docstring extraction and rendering
- mkdocs-typer2 0.1.0+ - Typer CLI documentation generation
- mkdoxy 1.2.3+ - C/C++ API reference generation using Doxygen
- mkdocs-literate-nav 0.6.1+ - Custom navigation from markdown comments
- mkdocs-mermaid2-plugin 1.1.1+ - Diagram support
- termynal 0.12.1+ - Terminal session playback in docs

**Configuration & Data Handling:**
- tomlkit 0.12.0+ - TOML parsing/writing with formatting preservation
- ruamel.yaml 0.18.0+ - YAML handling with comment and structure preservation
- pydantic 2.12.2+ - Data validation and settings management
- python-dotenv 1.1.1+ - Environment variable loading

**HTTP & Networking:**
- httpx 0.28.1+ - Modern async-capable HTTP client for API calls

**UI/Output:**
- Rich - Terminal formatting and progress display (via Typer dependency)

## Key Dependencies

**Critical:**
- Typer - CLI framework, enables mkapidocs command-line interface
- Jinja2 - Template rendering for dynamic documentation configuration
- pydantic - Configuration validation and parsing
- httpx - GitHub/GitLab API integration for release fetching and Pages URL detection
- ruamel.yaml - YAML preservation (preserves user comments and formatting when updating configs)

**Infrastructure:**
- hatchling 1.28.0+ - Build backend
- hatch-vcs - VCS-based version detection from git tags
- tomlkit - TOML file manipulation while preserving formatting
- python-dotenv - Environment variable support for configuration

## Configuration

**Environment:**
- `.env.example` - Template with optional configuration variables:
  - `DEBUG` - Development mode flag
  - `PACKAGE_INDEX_URL` - Custom Python package registry
  - `GITLAB_TOKEN` - Optional GitLab authentication token for Pages URL detection

**Build:**
- `pyproject.toml` - PEP 518/517/621 compliant configuration containing:
  - Build system: hatchling with hatch-vcs
  - Dependencies: runtime and dev groups
  - Tool configurations: ruff, mypy, basedpyright, pytest, semantic-release
- `hatch.toml`-style config embedded in pyproject.toml with `[tool.hatch.version]` using VCS source

**Code Quality:**
- `.editorconfig` - Editor formatting rules (line endings, indentation)
- `.markdownlint-cli2.jsonc` - Markdown linting configuration
- `.pre-commit-hooks.yaml` - Pre-commit hook definitions
- `.pre-commit-config.yaml` - Pre-commit framework configuration

## Linting & Formatting

**Formatter:**
- ruff format - Unified formatter (replaces black)
- Line length: 120 characters
- Quote style: Double quotes
- Line ending: LF
- Docstring formatting enabled (docstring-code-format)

**Linter:**
- ruff check - Comprehensive linting (replaces flake8, isort, and multiple plugins)
- Extensive ruleset: 70+ rules enabled (A, ANN, ASYNC, B, BLE, C4, D, DOC, E, F, I, N, PERF, PT, etc.)
- Auto-fixes enabled by default (unsafe-fixes also allowed)
- Configuration: `tool.ruff` in pyproject.toml
- Per-file ignores for tests (relaxed security, docstring, type annotation requirements)

**Type Checking:**
- mypy 1.18.2+ - Strict mode enabled (`strict = true`)
- basedpyright 1.21.1+ - Alternative type checker (basic mode)
- Type hints required on all functions

## Testing

**Framework:**
- pytest 8.4.2+ - Test runner
- pytest-cov 7.0.0+ - Coverage reporting
- pytest-mock 3.14.0+ - Mocking support
- Config: `pyproject.toml [tool.pytest.ini_options]`
- Coverage requirement: ≥70% (`fail_under = 70`)

**Run Commands:**
```bash
uv run pytest                    # All tests with coverage
uv run pytest tests/ -v          # Verbose output
uv run pytest -k pattern -v      # Pattern matching
uv run pytest --cov=packages/mkapidocs --cov-report=html  # HTML coverage report
```

## CI/CD

**Platform:** GitHub Actions (`.github/workflows/`)
- **ci.yml**: Test on all commits, lint, semantic-release, pages deployment
  - Test: Python 3.11, pytest with coverage upload to Codecov
  - Lint: ruff, mypy (continue-on-error), basedpyright (continue-on-error)
  - Release: python-semantic-release on main branch pushes only
  - Pages: Deploy generated documentation to GitHub Pages

**Release Management:**
- python-semantic-release 9.0.0+ - Automated semantic versioning
- Version source: Git tags via hatch-vcs
- Conventional Commits format required
- Version written to: `pyproject.toml:project.version`

## Version Management

**Mechanism:** hatch-vcs with git tags
- Version computed from latest git tag (format: v{version})
- Fallback to importlib.metadata if hatchling unavailable (production environments)
- Version file: `packages/mkapidocs/version.py` computes `__version__`

## Platform Requirements

**Development:**
- Python 3.11 or 3.12
- Git (for version detection)
- uv package manager (for dependency management)
- Optional: Doxygen (auto-installed on Linux/Windows or via package manager on macOS)

**Production:**
- Python 3.11 or 3.12
- Git (for version detection)
- uv (for running documentation generation)
- Optional: Docker (for GitLab CI pipelines)

---

*Stack analysis: 2026-02-07*
