# mkapidocs

Automated documentation setup tool for Python projects using MkDocs with GitHub Pages or GitLab Pages deployment.

mkapidocs is a Python package that sets up comprehensive MkDocs documentation for Python repositories with auto-detection of features like C/C++ code and Typer CLI interfaces.

## What It Does

mkapidocs automatically:

- Detects project features (C/C++ code, Typer CLI, private registries)
- Generates MkDocs configuration with Material theme
- Creates documentation structure with API references
- Sets up CI/CD workflow for GitHub Pages or GitLab Pages
- Configures docstring linting with ruff
- Generates automated API documentation pages
- Creates supporting docs (installation, quick start, contributing, etc.)

## Requirements

### System Requirements

- Python 3.11 or higher
- [uv](https://docs.astral.sh/uv/) package manager
- Git (optional, for automatic URL detection and provider auto-detection)

Install uv if not already installed:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### Target Project Requirements

The Python project you want to generate documentation for must have:

- A `pyproject.toml` file with project metadata (name, description, version, etc.)
- Proper Python package structure for API documentation
- Git repository (recommended for URL auto-detection and CI provider detection)

## Installation

```bash
uv add --dev mkapidocs
```

See [Installation Guide](docs/install.md) for more options.

## Usage

### Basic Commands

```bash
# Show help
mkapidocs --help

# Show version
mkapidocs version

# Show package information
mkapidocs info
```

### Setting Up Documentation

Initialize or update documentation for a Python project:

```bash
# Auto-detect CI provider from git remote or filesystem (current directory)
mkapidocs setup

# Specify a path explicitly
mkapidocs setup /path/to/your/project

# Explicitly use GitHub Actions
mkapidocs setup /path/to/your/project --provider github

# Explicitly use GitLab CI
mkapidocs setup /path/to/your/project --provider gitlab

# Explicitly specify the Pages URL (useful for enterprise GitLab)
mkapidocs setup /path/to/your/project --site-url https://mygroup.pages.gitlab.example.com/myproject
```

**Provider Auto-Detection:**

1. Checks git remote URL for `github` or `gitlab` word in the domain (supports enterprise instances)
2. Checks filesystem for `.gitlab-ci.yml`, `.gitlab/`, or `.github/` directories
3. Fails with error if provider cannot be determined (use `--provider` flag)

**Site URL Detection (GitLab):**

For GitLab projects, mkapidocs can query the GitLab GraphQL API to get the actual Pages URL:

```bash
# Set GITLAB_TOKEN for API-based URL detection (requires read_api scope)
GITLAB_TOKEN=glpat-xxx mkapidocs setup /path/to/project
```

- If Pages is deployed, the exact URL is retrieved from the API
- If Pages is not yet deployed, a heuristic URL is used as a placeholder
- Use `--site-url` to explicitly specify the URL and bypass all detection

Example with real paths:

```bash
# Setup docs for a project in your home directory
mkapidocs setup ~/repos/my-python-project

# Setup docs for a project in the current directory (default)
mkapidocs setup

# Setup docs with explicit provider
mkapidocs setup ~/repos/my-project --provider gitlab

# Enterprise GitLab with explicit URL
mkapidocs setup ~/repos/my-project --site-url https://team.pages.gitlab.corp.com/my-project
```

**Important:** The `setup` command is non-destructive and safe to run multiple times:

- **First run:** Creates all documentation files and infrastructure
- **Subsequent runs:** Uses smart YAML merge to preserve your customizations
- **Updates only:** Template-owned settings (plugin paths, core configuration)
- **Preserves:** Your custom navigation, extra plugins, theme features, and additional configuration

After running setup, you'll see a table showing exactly what was added, updated, or preserved.

This command:

1. Reads pyproject.toml to extract project metadata
2. Detects C/C++ code in source/ directory
3. Detects Typer CLI dependency
4. Detects private registry configuration
5. Creates or updates mkdocs.yml with all necessary plugins
6. Creates docs/ directory with documentation pages
7. Creates CI workflow for GitHub Pages or GitLab Pages deployment
8. Adds docstring linting rules to ruff configuration

### Building Documentation

Build static documentation site:

```bash
# Build documentation (output to site/ directory)
mkapidocs build /path/to/your/project

# Build with strict mode (warnings as errors)
mkapidocs build /path/to/your/project --strict

# Build to custom output directory
mkapidocs build /path/to/your/project --output-dir /path/to/output
```

Example:

```bash
# Build docs for project in current directory (default)
mkapidocs build

# Build docs with strict checking
mkapidocs build ~/repos/my-project --strict

# Build to custom directory
mkapidocs build ~/repos/my-project --output-dir ~/docs-build
```

### Serving Documentation

Start local documentation server with live reload:

```bash
# Serve on default address (127.0.0.1:8000)
mkapidocs serve /path/to/your/project

# Serve on custom host and port
mkapidocs serve /path/to/your/project --host 0.0.0.0 --port 8080
```

Example:

```bash
# Serve docs locally (current directory)
mkapidocs serve

# Access at http://127.0.0.1:8000
# Press Ctrl+C to stop

# Serve on all interfaces for network access
mkapidocs serve ~/repos/my-project --host 0.0.0.0 --port 9000
```

## CLI Documentation for Typer Apps

For projects with Typer CLI applications, mkapidocs uses the mkdocs-typer2 plugin to generate CLI documentation. This requires importing your CLI module, which means all your project's dependencies must be available.

**Recommended approach:** Add mkapidocs as a dev dependency in your project:

```bash
uv add --dev mkapidocs
```

Then run build/serve from within your project:

```bash
uv run mkapidocs build .
uv run mkapidocs serve .
```

This ensures mkdocs-typer2 can import your CLI module with all dependencies available, resulting in complete CLI documentation with all commands, arguments, and docstrings.

## Documentation Structure Created

After running setup, your project will have:

```
your-project/
├── mkdocs.yml                          # MkDocs configuration
├── docs/
│   ├── index.md                        # Homepage (preserved on re-run)
│   ├── about.md                        # Auto-generated from README.md
│   ├── install.md                      # Installation guide (preserved on re-run)
│   ├── quick-start-guide.md            # Quick start
│   ├── contributing.md                 # Contributing guide
│   ├── publishing.md                   # Publishing guide
│   └── generated/                      # Auto-generated content (always regenerated)
│       ├── gen_ref_pages.py            # API reference generation script
│       ├── index-features.md           # Feature list
│       ├── install-registry.md         # Private registry instructions (if detected)
│       ├── python-api.md               # Python API reference
│       ├── c-api.md                    # C API reference (if C code detected)
│       └── cli-api.md                  # CLI reference (if Typer detected)
└── .github/                            # For GitHub provider
    └── workflows/
        └── pages.yml                   # GitHub Pages workflow
# OR
└── .gitlab/                            # For GitLab provider
    └── workflows/
        └── pages.gitlab-ci.yml         # GitLab Pages workflow
```

**Preserved on re-run:** `index.md`, `install.md`, and user customizations in `mkdocs.yml`
**Always regenerated:** Everything in `docs/generated/` directory

## Features Detected

The script auto-detects:

1. **C/C++ Code**: Looks for .c, .h, .cpp, .hpp files in source/ directory

   - Adds mkdoxy plugin for Doxygen documentation
   - Creates C API reference page

2. **Typer CLI**: Checks for typer dependency in pyproject.toml

   - Adds mkdocs-typer2 plugin
   - Creates CLI reference page

3. **Private Registry**: Checks for [tool.uv.index] in pyproject.toml

   - Adds installation instructions with --index flag
   - Documents registry configuration

4. **Git Remote**: Extracts Pages URL from git remote
   - Supports SSH and HTTPS formats
   - Auto-generates site_url for mkdocs.yml
   - Detects GitHub vs GitLab for CI provider selection

## MkDocs Plugins Included

The script configures MkDocs with:

- **mkdocs-material**: Material Design theme
- **mkdocs-gen-files**: Generate API reference pages
- **mkdocs-literate-nav**: Navigation from SUMMARY.md
- **mkdocstrings**: Python API documentation with Google-style docstrings
- **mkdocs-typer2**: Typer CLI documentation (if detected)
- **mkdoxy**: C/C++ Doxygen documentation (if detected)
- **mermaid2**: Mermaid diagrams
- **termynal**: Terminal animations

## Complete Workflow Example

```bash
# 1. Add mkapidocs to your project
cd ~/repos/my-awesome-project
uv add --dev mkapidocs

# 2. Setup documentation
uv run mkapidocs setup

# 3. Preview locally
uv run mkapidocs serve
# Visit http://127.0.0.1:8000

# 4. Build for production
uv run mkapidocs build --strict

# 5. Commit and push (CI will auto-deploy)
git add .
git commit -m "Add MkDocs documentation"
git push
```

## Pre-Commit Hook

mkapidocs can automatically regenerate documentation on every commit using pre-commit hooks. This keeps your docs in sync with code changes without manual intervention.

### Setup

Add to your project's `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: https://github.com/Jamie-BitFlight/mkapidocs
    rev: v1.0.0 # Use latest version tag
    hooks:
      - id: mkapidocs-regen
```

This hook:

- Triggers when Python files, `pyproject.toml`, or `mkdocs.yml` change
- Runs `mkapidocs setup` to regenerate documentation
- Adds updated docs to the commit automatically
- **Safe to run:** Uses smart merge to preserve your customizations

### First Time Setup

```bash
# Install pre-commit if not already installed
uv tool install pre-commit

# Install the hooks
pre-commit install

# Test it
pre-commit run --all-files
```

### What Happens on Commit

When you commit changes to Python files:

1. Pre-commit runs `mkapidocs setup`
2. Detects project features (C code, Typer CLI, etc.)
3. Regenerates `docs/generated/` content
4. Updates mkdocs.yml if needed (preserving your customizations)
5. Stages updated documentation files
6. Commit proceeds with updated docs included

**Note:** The hook ID is `mkapidocs-regen` for backward compatibility, but it runs the `setup` command (which is non-destructive).

## CI/CD Deployment

### GitHub Pages

After running setup with GitHub provider and pushing to GitHub, the `.github/workflows/pages.yml` workflow will:

1. Check out the code
2. Set up Python 3.11 and install uv
3. Run `mkapidocs build . --strict`
4. Upload the site/ directory as a GitHub Pages artifact
5. Deploy to GitHub Pages

The documentation will be available at: `https://your-username.github.io/repo-name/`

**Note:** Enable GitHub Pages in your repository settings and configure it to deploy from GitHub Actions.

### GitLab Pages

After running setup with GitLab provider and pushing to GitLab, the `pages` job in `.gitlab/workflows/pages.gitlab-ci.yml` will:

1. Use the `ghcr.io/astral-sh/uv:python3.11` image
2. Run `uv run mkapidocs build . --strict`
3. Deploy the public/ directory to GitLab Pages

The documentation will be available at: `https://your-username.gitlab.io/repo-name/`

**Note:** If you already have a `pages` job in your root `.gitlab-ci.yml`, mkapidocs will skip creating a new workflow and warn you to update your existing job.

## Customization

After setup, you can customize:

- **mkdocs.yml**: Modify theme, add plugins, customize navigation
- **docs/** files: Edit or add documentation pages
- **docs/generated/**: These files are always regenerated - don't edit manually

### Safe to Re-run

After customizing `mkdocs.yml`, you can safely run `setup` again:

```bash
mkapidocs setup /path/to/your/project
```

The smart merge system will:

- ✅ Preserve your custom navigation structure
- ✅ Preserve your extra plugins and theme features
- ✅ Preserve your additional configuration (`extra`, custom extensions, etc.)
- ✅ Update only template-owned settings (plugin paths, core plugins)
- ✅ Show you a table of what changed

Your customizations are safe!

## Project Structure

```
mkapidocs/
├── packages/
│   └── mkapidocs/           # Main package
│       ├── __init__.py
│       ├── cli.py           # Typer CLI application
│       └── ...
├── tests/                   # Test suite
├── pyproject.toml           # Package configuration
└── README.md
```

## Troubleshooting

### CLI documentation is empty

If CLI documentation shows headers but no commands, ensure mkapidocs is installed as a dev dependency in your target project:

```bash
cd /path/to/your/project
uv add --dev mkapidocs
uv run mkapidocs build .
```

This allows mkdocs-typer2 to import your CLI module with all dependencies available.

### mkdocs.yml not found

The build and serve commands require mkdocs.yml to exist. Run setup first:

```bash
mkapidocs setup /path/to/project
```

### Provider detection fails

If git remote is not configured or the provider cannot be determined:

```bash
# Explicitly specify the provider
mkapidocs setup /path/to/project --provider github
mkapidocs setup /path/to/project --provider gitlab
```

### Module import errors during build

The script automatically detects source paths from pyproject.toml and adds them to PYTHONPATH. This allows mkdocstrings to import your package for API documentation generation.

Ensure your target project's pyproject.toml has correct build configuration:

```toml
# For Hatch (recommended)
[tool.hatch.build.targets.wheel]
packages = ["packages/mypackage"]
# Or with sources mapping
sources = {"packages/mypackage" = "mypackage"}

# For setuptools
[tool.setuptools.packages.find]
where = ["src"]
```

If your package is in a non-standard location, the build command may fail to import it. Verify your build configuration matches your actual package structure.

### Pre-commit check-yaml fails on mkdocs.yml

If you use pre-commit with the `check-yaml` hook, it may fail on mkdocs.yml with an error like:

```
could not determine a constructor for the tag 'tag:yaml.org,2002:python/name:mermaid2.fence_mermaid_custom'
```

This happens because mkapidocs generates mkdocs.yml with Python-specific YAML tags (`!!python/name:`) for the mermaid2 plugin. Add the `--unsafe` flag to allow these tags:

```yaml
# In your .pre-commit-config.yaml
- repo: https://github.com/pre-commit/pre-commit-hooks
  rev: v5.0.0
  hooks:
    - id: check-yaml
      args: [--unsafe] # Allow Python tags in mkdocs.yml
```

## License

Unlicense

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests and linting
5. Submit a pull request

## Links

- Repository: https://github.com/Jamie-BitFlight/mkapidocs
- Issue Tracker: https://github.com/Jamie-BitFlight/mkapidocs/issues
