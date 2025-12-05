"""Installation guide template."""

INSTALL_MD_TEMPLATE = """# Installation

This guide provides detailed installation instructions for {{ project_name }}.

## Prerequisites

- Python {{ requires_python if requires_python else "3.11+" }}
- uv package manager
- Git (for development installation)
{% if has_private_registry %}
- Registry credentials (for private registry access)
{% endif %}

## Quick Install

--8<-- "generated/install-command.md"

## Development Installation

For development work, clone the repository and install with all dependencies:

```bash
# Clone the repository
git clone {{ git_url if git_url else "REPOSITORY_URL" }}
cd {{ project_name }}

# Install with all dependencies
uv sync
```
{% if c_source_dirs %}

## Building C Extensions

This project includes C/C++ extensions. A C compiler is required:

**Linux/macOS:**
- GCC or Clang should be available by default
- Install build-essential on Ubuntu/Debian: `sudo apt install build-essential`

**Windows:**
- Install Microsoft Visual C++ Build Tools
- Or use MinGW-w64
{% endif %}

## Verification

Verify the installation:

```bash
# Check installed version
python -c "from importlib.metadata import version; print(version('{{ project_name }}'))"
{% if has_typer %}

# Display CLI help
{{ project_name }} --help
{% endif %}
```

## Troubleshooting

### Common Issues

**Import Error**

If you get an import error, ensure the package is installed in your active Python environment:

```bash
python -c "import {{ project_name.replace('-', '_') }}"
```

**Permission Error**

uv automatically manages virtual environments, so permission errors should not occur. If you encounter permission issues, ensure uv is properly installed:

```bash
# Verify uv installation
uv --version

# Add the package to your project
uv add {{ project_name }}
```
{% if c_source_dirs %}

**C Extension Build Failure**

If C extensions fail to build, ensure you have a working C compiler installed. See the "Building C Extensions" section above.
{% endif %}

## Uninstallation

To remove {{ project_name }} from your project:

```bash
uv remove {{ project_name }}
```

## Next Steps

- [API Reference](generated/python-api.md) - Explore the API documentation
{% if has_typer %}
- [CLI Reference](generated/cli-api.md) - Command-line interface documentation
{% endif %}
"""
