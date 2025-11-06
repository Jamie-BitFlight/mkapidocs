# mkapidocs

Automated documentation setup tool for Python projects using MkDocs and GitHub Pages.

This is a PEP 723 standalone script that sets up comprehensive MkDocs documentation for Python repositories with auto-detection of features like C/C++ code and Typer CLI interfaces.

## What It Does

mkapidocs automatically:

- Detects project features (C/C++ code, Typer CLI, private registries)
- Generates MkDocs configuration with Material theme
- Creates documentation structure with API references
- Sets up GitHub Actions workflow for GitHub Pages
- Configures docstring linting with ruff
- Generates automated API documentation pages
- Creates supporting docs (installation, quick start, contributing, etc.)

## Requirements

### System Requirements

- Python 3.11 or higher
- [uv](https://docs.astral.sh/uv/) package manager
- Git (optional, for automatic GitHub URL detection)

Install uv if not already installed:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### Target Project Requirements

The Python project you want to generate documentation for must have:

- A `pyproject.toml` file with project metadata (name, description, version, etc.)
- Proper Python package structure for API documentation
- Git repository (optional, but recommended for GitHub Pages URL auto-detection)

## Installation

This is a PEP 723 standalone script that does not require installation. Simply download and run it.

### Download and Run

```bash
# Clone the repository
git clone https://github.com/Jamie-BitFlight/mkapidocs.git
cd mkapidocs

# Make script executable (if needed)
chmod +x mkapidocs

# Run from this directory
./mkapidocs --help
```

Or download just the script:

```bash
# Download the standalone script
curl -O https://raw.githubusercontent.com/Jamie-BitFlight/mkapidocs/main/mkapidocs
chmod +x mkapidocs

# Run from anywhere
./mkapidocs --help
```

## Usage

The script can be run from any location. The working directory does not matter - you provide the target project path as an argument.

### Basic Commands

```bash
# Show help
./mkapidocs --help

# Show version
./mkapidocs version

# Show package information
./mkapidocs info
```

### Setting Up Documentation

Initialize or update documentation for a Python project:

```bash
# Auto-detect GitHub Pages URL from git remote
./mkapidocs setup /path/to/your/project

# Specify custom GitHub Pages base URL
./mkapidocs setup /path/to/your/project --github-url-base https://your-username.github.io/repo-name/
```

Example with real paths:

```bash
# Setup docs for a project in your home directory
./mkapidocs setup ~/repos/my-python-project

# Setup docs for a project in the current directory
./mkapidocs setup .

# Setup docs with explicit GitHub URL
./mkapidocs setup ~/repos/my-project --github-url-base https://mycompany.github.io/my-project/
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
7. Creates .github/workflows/pages.yml for GitHub Pages deployment
8. Adds docstring linting rules to ruff configuration

### Building Documentation

Build static documentation site:

```bash
# Build documentation (output to site/ directory)
./mkapidocs build /path/to/your/project

# Build with strict mode (warnings as errors)
./mkapidocs build /path/to/your/project --strict

# Build to custom output directory
./mkapidocs build /path/to/your/project --output-dir /path/to/output
```

Example:

```bash
# Build docs for project in current directory
./mkapidocs build .

# Build docs with strict checking
./mkapidocs build ~/repos/my-project --strict

# Build to custom directory
./mkapidocs build ~/repos/my-project --output-dir ~/docs-build
```

### Serving Documentation

Start local documentation server with live reload:

```bash
# Serve on default address (127.0.0.1:8000)
./mkapidocs serve /path/to/your/project

# Serve on custom host and port
./mkapidocs serve /path/to/your/project --host 0.0.0.0 --port 8080
```

Example:

```bash
# Serve docs locally
./mkapidocs serve ~/repos/my-project

# Access at http://127.0.0.1:8000
# Press Ctrl+C to stop

# Serve on all interfaces for network access
./mkapidocs serve ~/repos/my-project --host 0.0.0.0 --port 9000
```

## How It Works

This script uses PEP 723 inline script metadata for a self-contained Python script. Dependencies are declared inline and managed by uv, so:

- **No installation required** - Just download and execute
- **No dependency conflicts** - uv manages an isolated environment
- **Works anywhere** - Provide target project path as argument
- **Proper imports** - Runs MkDocs commands in your project context for API documentation

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
└── .github/
    └── workflows/
        └── pages.yml                   # GitHub Pages workflow
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

4. **Git Remote**: Extracts GitHub Pages URL from git remote
   - Supports SSH and HTTPS formats (git@github.com:user/repo.git or https://github.com/user/repo.git)
   - Auto-generates site_url for mkdocs.yml

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
- **recently-updated**: Show recently updated pages

## Complete Workflow Example

```bash
# 1. Download or clone the script
git clone https://github.com/Jamie-BitFlight/mkapidocs.git
cd mkapidocs

# 2. Setup documentation for your project
./mkapidocs setup ~/repos/my-awesome-project

# 3. Preview locally
./mkapidocs serve ~/repos/my-awesome-project
# Visit http://127.0.0.1:8000

# 4. Build for production
./mkapidocs build ~/repos/my-awesome-project --strict

# 5. Commit and push (GitLab Pages will auto-deploy)
cd ~/repos/my-awesome-project
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

## GitHub Pages Deployment

After running setup and pushing to GitHub, the .github/workflows/pages.yml workflow will:

1. Check out the code
2. Set up Python 3.11 and install uv
3. Run `uvx mkapidocs build . --strict`
4. Upload the site/ directory as a GitHub Pages artifact
5. Deploy to GitHub Pages

The documentation will be available at:

- https://your-username.github.io/repo-name/

**Note:** You need to enable GitHub Pages in your repository settings and configure it to deploy from GitHub Actions.

## Customization

After setup, you can customize:

- **mkdocs.yml**: Modify theme, add plugins, customize navigation
- **docs/** files: Edit or add documentation pages
- **docs/generated/**: These files are always regenerated - don't edit manually

### Safe to Re-run

After customizing `mkdocs.yml`, you can safely run `setup` again:

```bash
./mkapidocs setup /path/to/your/project
```

The smart merge system will:

- ✅ Preserve your custom navigation structure
- ✅ Preserve your extra plugins and theme features
- ✅ Preserve your additional configuration (`extra`, custom extensions, etc.)
- ✅ Update only template-owned settings (plugin paths, core plugins)
- ✅ Show you a table of what changed

Your customizations are safe!

## Troubleshooting

### Script won't execute

```bash
# Ensure script is executable
chmod +x mkapidocs

# Check uv is installed
uv --version
```

### mkdocs.yml not found

The build and serve commands require mkdocs.yml to exist. Run setup first:

```bash
./mkapidocs setup /path/to/project
```

### GitHub URL detection fails

If git remote is not configured or in unexpected format:

```bash
# Provide explicit URL
./mkapidocs setup /path/to/project --github-url-base https://your-username.github.io/repo-name/
```

### Module import errors during build

The script automatically detects source paths from pyproject.toml and adds them to PYTHONPATH. This allows mkdocstrings to import your package for API documentation generation.

Ensure your target project's pyproject.toml has correct build configuration:

```toml
# For Hatch (recommended)
[tool.hatch.build.targets.wheel]
packages = ["src/mypackage"]
# Or with sources mapping
sources = {"packages/mypackage" = "mypackage"}

# For setuptools
[tool.setuptools.packages.find]
where = ["src"]
```

If your package is in a non-standard location, the build command may fail to import it. Verify your build configuration matches your actual package structure.

## License

Unlicense

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests and linting
5. Submit a merge request

## Links

- Repository: https://github.com/Jamie-BitFlight/mkapidocs
- Issue Tracker: https://github.com/Jamie-BitFlight/mkapidocs/issues
