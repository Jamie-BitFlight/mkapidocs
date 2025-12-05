"""Template for the index.md page."""

INDEX_MD_TEMPLATE = """# {{ project_name }}

{{ description }}

--8<-- "generated/index-features.md"

## Quick Start

--8<-- "generated/install-command.md"

--8<-- "generated/install-registry.md"

For detailed installation instructions, see the [Installation Guide](install.md).

## License

{{ license }}
"""
