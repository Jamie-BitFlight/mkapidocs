# Installation

This guide provides detailed installation instructions for mkapidocs.

## Prerequisites

- Python >=3.11,<3.13
- [uv](https://docs.astral.sh/uv/) package manager
- Git (for URL auto-detection and CI provider detection)

## Quick Install

Add mkapidocs as a dev dependency to your project:

```bash
uv add --dev mkapidocs
```

Then run commands via `uv run`:

```bash
uv run mkapidocs setup .
uv run mkapidocs build .
uv run mkapidocs serve .
```

## Install from Git

For the latest unreleased version, install directly from the repository:

```bash
uv add --dev "mkapidocs @ git+https://github.com/Jamie-BitFlight/mkapidocs.git"
```

## Use with uvx (Standalone)

For quick usage without adding to your project:

```bash
uvx mkapidocs --help
uvx mkapidocs setup /path/to/project
```

Or for the latest unreleased version:

```bash
uvx --from "git+https://github.com/Jamie-BitFlight/mkapidocs.git" mkapidocs setup /path/to/project
```

## Development Installation

For development work, clone the repository and install with all dependencies:

```bash
git clone https://github.com/Jamie-BitFlight/mkapidocs
cd mkapidocs
uv sync
```

## Uninstallation

To remove mkapidocs from your project:

```bash
uv remove mkapidocs
```
