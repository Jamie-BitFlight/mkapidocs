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

This project includes C/C++ extensions. Ensure you have a working C/C++ compiler installed for your operating system.
{% endif %}

## Verification

Verify the installation:

```bash
# Check installed version
python -c "from importlib.metadata import version; print(version('{{ project_name }}'))"
{% if has_typer and script_names %}

# Display CLI help (Typer CLI provides --help automatically)
{% for cmd in script_names %}
{{ cmd }} --help
{% endfor %}
{% endif %}
```



## Uninstallation
{% if has_scripts %}

To uninstall the CLI tool:

```bash
uv tool uninstall {{ project_name }}
```
{% endif %}

To remove from your project dependencies:

```bash
uv remove {{ project_name }}
```

## Next Steps

- [Python API Reference](generated/python-api.md) - Explore the Python API documentation
{% if c_source_dirs %}
- [C/C++ API Reference](generated/c-api.md) - C/C++ API documentation
{% endif %}
{% if has_typer %}
- [CLI Reference](generated/cli-api.md) - Command-line interface documentation
{% endif %}
"""
