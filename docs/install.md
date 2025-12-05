# Installation

This guide provides detailed installation instructions for mkapidocs.

## Prerequisites

- Python &gt;=3.11,&lt;3.13
- uv package manager
- Git (for development installation)

## Quick Install

--8<-- "generated/install-command.md"

## Development Installation

For development work, clone the repository and install with all dependencies:

```bash
# Clone the repository
git clone https://github.com/Jamie-BitFlight/mkapidocs
cd mkapidocs

# Install with all dependencies
uv sync --all-extras

# Or install specific extras
uv sync --extra dev
```

## Verification

Verify the installation:

```bash
# Check installed version
python -c "from importlib.metadata import version; print(version('mkapidocs'))"


# Display CLI help
mkapidocs --help

```

## Troubleshooting

### Common Issues

**Import Error**

If you get an import error, ensure the package is installed in your active Python environment:

```bash
python -c "import mkapidocs"
```

**Permission Error**

uv automatically manages virtual environments, so permission errors should not occur. If you encounter permission issues, ensure uv is properly installed:

```bash
# Verify uv installation
uv --version

# Add the package to your project
uv add mkapidocs
```

## Uninstallation

To remove mkapidocs from your project:

```bash
uv remove mkapidocs
```

## Next Steps

- [API Reference](generated/python-api.md) - Explore the API documentation

- [CLI Reference](generated/cli-api.md) - Command-line interface documentation
