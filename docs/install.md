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
uv sync
```

## Verification

Verify the installation:

```bash
# Check installed version
python -c "from importlib.metadata import version; print(version('mkapidocs'))"


# Display CLI help (Typer CLI provides --help automatically)

mkapidocs --help


```

## Uninstallation

To uninstall the CLI tool:

```bash
uv tool uninstall mkapidocs
```

To remove from your project dependencies:

```bash
uv remove mkapidocs
```

## Next Steps

- [Python API Reference](generated/python-api.md) - Explore the Python API documentation

- [CLI Reference](generated/cli-api.md) - Command-line interface documentation
