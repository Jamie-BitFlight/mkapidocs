# External Integrations

**Analysis Date:** 2026-02-07

## APIs & External Services

**GitHub:**
- GitHub API (releases endpoint) - Doxygen binary release fetching
  - SDK/Client: httpx
  - URL: `https://api.github.com/repos/doxygen/doxygen/releases/latest`
  - Auth: None required (public API with rate limits)
  - Usage: `packages/mkapidocs/validators.py` - DoxygenInstaller class fetches and auto-installs Doxygen
  - Method: REST API for release assets

**GitLab:**
- GitLab GraphQL API - Pages deployment URL detection
  - SDK/Client: httpx
  - Auth: Optional GITLAB_TOKEN environment variable (read_api scope sufficient)
  - Usage: `packages/mkapidocs/generator.py` - query_gitlab_pages_url function
  - Query: Retrieves project Pages deployment URL via GraphQL
  - Purpose: Auto-detect site URL for GitLab Pages deployment without manual configuration
  - Fallback: Git remote parsing if token unavailable or API fails

## Data Storage

**Databases:**
- None - mkapidocs is stateless and does not persist data

**File Storage:**
- Local filesystem only - All operations are file-based within target repository
- Generated files in target project:
  - `mkdocs.yml` - Documentation configuration
  - `docs/` directory - Documentation content
  - `.github/workflows/pages.yml` - GitHub Actions workflow (if GitHub)
  - `.gitlab-ci.yml` - GitLab CI configuration (if GitLab)
  - `.gitlab/workflows/` - GitLab CI workflows (if GitLab)

**Caching:**
- Doxygen binaries: `~/.cache/doxygen-binaries/` - User home directory cache
- Installation: `~/.local/bin/` - User local binaries directory
- Implementation: `packages/mkapidocs/validators.py` - DoxygenInstaller class manages cache lifecycle

## Authentication & Identity

**Auth Provider:**
- Custom (environment variable based)
- No centralized auth provider

**Configuration:**
- `GITLAB_TOKEN` environment variable - Optional GitLab Personal Access Token
  - Scope: `read_api` (minimal required scope for Pages URL detection)
  - Usage: GitLab GraphQL API authentication in `packages/mkapidocs/generator.py`
  - Fallback: Unauthenticated API call (may hit rate limits or fail if repository is private)
  - Optional: If not provided, mkapidocs falls back to parsing git remote URL

- `PACKAGE_INDEX_URL` environment variable - Optional custom Python package index
  - Usage: Passed to uv for package installation in target environments
  - Default: Official PyPI if not set

## External Dependencies Detection

**Package Analysis:**
- Private Python package registry detection - `packages/mkapidocs/project_detection.py`
- Typer CLI dependency detection - Checks for `typer` in project dependencies
- C/C++ source code detection - Scans specified directories for .c, .cpp, .h, .hpp files

## Monitoring & Observability

**Error Tracking:**
- None (application does not integrate with external error tracking services)

**Logs:**
- Console-based output via Rich library
- No persistent logging
- Optional verbose output flag in CLI

## CI/CD & Deployment

**Hosting:**
- GitHub Pages - Deployment target for GitHub repositories
- GitLab Pages - Deployment target for GitLab repositories

**CI Pipeline:**
- GitHub Actions (`.github/workflows/ci.yml`)
  - Test stage: Runs pytest, uploads coverage to Codecov
  - Lint stage: Runs ruff, mypy, basedpyright
  - Release stage: Runs python-semantic-release, publishes to GitHub Releases
  - Pages stage: Builds and deploys documentation to GitHub Pages

**Generated CI/CD Workflows:**
- GitHub Pages: `.github/workflows/pages.yml` - Checkout, Python setup, uv setup, build, deploy
- GitLab Pages: `.gitlab/workflows/pages.gitlab-ci.yml` - Docker image, build, deploy

## Environment Configuration

**Required env vars for mkapidocs operation:**
- None (all required configuration is auto-detected or provided via CLI flags)

**Optional env vars:**
- `GITLAB_TOKEN` - GitLab authentication (for Pages URL detection)
- `PACKAGE_INDEX_URL` - Custom Python package registry
- `DEBUG` - Development mode flag (from .env.example)
- `MKAPIDOCS_INTERNAL_CALL` - Internal flag (set by mkapidocs itself, not user-configurable)
- `MKAPIDOCS_C_SOURCE_DIRS` - Alternative method to specify C source directories via environment

**Secrets location:**
- `.env` file (not committed to repo, created from `.env.example`)
- Secrets passed via environment variables in CI/CD pipelines
- GitHub: Secrets configured in repository settings
- GitLab: CI/CD variables configured in project settings

## Webhooks & Callbacks

**Incoming:**
- None - mkapidocs does not expose any webhook endpoints

**Outgoing:**
- GitHub Pages deployment - Automatic via GitHub Actions
- GitLab Pages deployment - Automatic via GitLab CI

## External Tool Dependencies

**Command-line Tools:**
- git - Required for repository detection and version detection
- doxygen - Optional (auto-installed if C/C++ code detected and C_API generation enabled)
  - Platform-specific installation:
    - Linux: Auto-downloads and extracts binary from GitHub releases
    - Windows: Auto-downloads installer executable (manual installation recommended)
    - macOS: User must install via Homebrew: `brew install doxygen`

**Dynamic Installation:**
- `uv run` - Used to dynamically install MkDocs and plugins in target project environment
- uvx - Used as fallback for running mkdocs without permanent installation

## Network Connectivity Requirements

**For mkapidocs setup/build:**
- None required (can work offline)

**For Doxygen auto-installation (when C code detected):**
- GitHub API access to fetch releases (github.com/doxygen/doxygen)
- Network timeout: 30 seconds for release data fetch, 300 seconds for binary download

**For GitLab Pages URL detection:**
- GitLab instance API access (gitlab.com or enterprise instance)
- Network timeout: 10 seconds for GraphQL query
- Optional: Falls back to git remote parsing if API unavailable

**For CI/CD deployment:**
- GitHub Actions/GitLab CI has network access to PyPI and documentation site

---

*Integration audit: 2026-02-07*
