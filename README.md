# Python Documentation Init

Automated documentation setup tool for Python projects using MkDocs and GitLab Pages.

This is a PEP 723 standalone script that sets up comprehensive MkDocs documentation for Python repositories with auto-detection of features like C/C++ code and Typer CLI interfaces.

## What It Does

python-docs-init automatically:

- Detects project features (C/C++ code, Typer CLI, private registries)
- Generates MkDocs configuration with Material theme
- Creates documentation structure with API references
- Sets up GitLab Pages workflow
- Configures docstring linting with ruff
- Generates automated API documentation pages
- Creates supporting docs (installation, quick start, contributing, etc.)

## Requirements

### System Requirements

- Python 3.11 or higher
- [uv](https://docs.astral.sh/uv/) package manager
- Git (optional, for automatic GitLab URL detection)

Install uv if not already installed:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### Target Project Requirements

The Python project you want to generate documentation for must have:

- A `pyproject.toml` file with project metadata (name, description, version, etc.)
- Proper Python package structure for API documentation
- Git repository (optional, but recommended for GitLab Pages URL auto-detection)

## Installation

This is a PEP 723 standalone script that does not require installation. Simply download and run it.

### Download and Run

```bash
# Clone the repository
git clone https://github.com/Jamie-BitFlight/python-docs-init.git
cd python-docs-init

# Make script executable (if needed)
chmod +x python-docs-init

# Run from this directory
./python-docs-init --help
```

Or download just the script:

```bash
# Download the standalone script
curl -O https://raw.githubusercontent.com/Jamie-BitFlight/python-docs-init/main/python-docs-init
chmod +x python-docs-init

# Run from anywhere
./python-docs-init --help
```

## Usage

The script can be run from any location. The working directory does not matter - you provide the target project path as an argument.

### Basic Commands

```bash
# Show help
./python-docs-init --help

# Show version
./python-docs-init version

# Show package information
./python-docs-init info
```

### Setting Up Documentation

Initialize documentation for a Python project:

```bash
# Auto-detect GitLab Pages URL from git remote
./python-docs-init setup /path/to/your/project

# Specify custom GitLab Pages base URL
./python-docs-init setup /path/to/your/project --gitlab-url-base https://your-org.gitlab.io/group/
```

Example with real paths:

```bash
# Setup docs for a project in your home directory
./python-docs-init setup ~/repos/my-python-project

# Setup docs for a project in the current directory
./python-docs-init setup .

# Setup docs with explicit GitLab URL
./python-docs-init setup ~/repos/my-project --gitlab-url-base https://mycompany.gitlab.io/team/
```

This command:

1. Reads pyproject.toml to extract project metadata
2. Detects C/C++ code in source/ directory
3. Detects Typer CLI dependency
4. Detects private registry configuration
5. Creates mkdocs.yml with all necessary plugins
6. Creates docs/ directory with documentation pages
7. Creates .gitlab/workflows/pages.gitlab-ci.yml for GitLab Pages
8. Adds docstring linting rules to ruff configuration

### Building Documentation

Build static documentation site:

```bash
# Build documentation (output to site/ directory)
./python-docs-init build /path/to/your/project

# Build with strict mode (warnings as errors)
./python-docs-init build /path/to/your/project --strict

# Build to custom output directory
./python-docs-init build /path/to/your/project --output-dir /path/to/output
```

Example:

```bash
# Build docs for project in current directory
./python-docs-init build .

# Build docs with strict checking
./python-docs-init build ~/repos/my-project --strict

# Build to custom directory
./python-docs-init build ~/repos/my-project --output-dir ~/docs-build
```

### Serving Documentation

Start local documentation server with live reload:

```bash
# Serve on default address (127.0.0.1:8000)
./python-docs-init serve /path/to/your/project

# Serve on custom host and port
./python-docs-init serve /path/to/your/project --host 0.0.0.0 --port 8080
```

Example:

```bash
# Serve docs locally
./python-docs-init serve ~/repos/my-project

# Access at http://127.0.0.1:8000
# Press Ctrl+C to stop

# Serve on all interfaces for network access
./python-docs-init serve ~/repos/my-project --host 0.0.0.0 --port 9000
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
├── mkdocs.yml                    # MkDocs configuration
├── gen_ref_pages.py              # Auto-generated API reference script
├── docs/
│   ├── index.md                  # Homepage
│   ├── about.md                  # From README.md
│   ├── install.md                # Installation guide
│   ├── quick-start-guide.md      # Quick start
│   ├── contributing.md           # Contributing guide
│   ├── publishing.md             # Publishing guide
│   └── reference/
│       ├── python.md             # Python API reference
│       ├── c.md                  # C API reference (if C code detected)
│       └── cli.md                # CLI reference (if Typer detected)
└── .gitlab/
    └── workflows/
        └── pages.gitlab-ci.yml   # GitLab Pages workflow
```

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

4. **Git Remote**: Extracts GitLab Pages URL from git remote
   - Supports SSH and HTTPS formats
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
git clone https://github.com/Jamie-BitFlight/python-docs-init.git
cd python-docs-init

# 2. Setup documentation for your project
./python-docs-init setup ~/repos/my-awesome-project

# 3. Preview locally
./python-docs-init serve ~/repos/my-awesome-project
# Visit http://127.0.0.1:8000

# 4. Build for production
./python-docs-init build ~/repos/my-awesome-project --strict

# 5. Commit and push (GitLab Pages will auto-deploy)
cd ~/repos/my-awesome-project
git add .
git commit -m "Add MkDocs documentation"
git push
```

## GitLab Pages Deployment

After running setup and pushing to GitLab, the .gitlab/workflows/pages.gitlab-ci.yml workflow will:

1. Install uv in a Python 3.11 container
2. Run `uvx python-docs-init build . --strict`
3. Move site/ to public/
4. Deploy to GitLab Pages

The documentation will be available at:

- https://your-org.gitlab.io/group/project-name/

## Customization

After setup, you can customize:

- **mkdocs.yml**: Modify theme, plugins, navigation
- **docs/** files: Edit generated documentation pages
- **gen_ref_pages.py**: Customize API reference generation

## Troubleshooting

### Script won't execute

```bash
# Ensure script is executable
chmod +x python-docs-init

# Check uv is installed
uv --version
```

### mkdocs.yml not found

The build and serve commands require mkdocs.yml to exist. Run setup first:

```bash
./python-docs-init setup /path/to/project
```

### GitLab URL detection fails

If git remote is not configured or in unexpected format:

```bash
# Provide explicit URL
./python-docs-init setup /path/to/project --gitlab-url-base https://your-org.gitlab.io/group/
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

- Repository: https://github.com/Jamie-BitFlight/python-docs-init
- Issue Tracker: https://github.com/Jamie-BitFlight/python-docs-init/issues
