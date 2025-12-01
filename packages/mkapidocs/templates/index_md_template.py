"""Template for the index.md page."""

INDEX_MD_TEMPLATE = """# {{ project_name }}

{{ description }}

--8<-- "generated/index-features.md"

## Quick Start

```bash
uv pip install {{ project_name }}
```

--8<-- "generated/install-registry.md"

For detailed installation instructions, see the [Installation Guide](install.md).

## Recently Updated

<!-- RECENTLY_UPDATED_DOCS -->

## License

{{ license }}
"""
