"""Template for CLI reference documentation."""

CLI_MD_TEMPLATE = """# CLI Reference

Command-line interface documentation for {{ project_name }}.

## Commands

<!-- prettier-ignore -->
::: mkdocs-typer2
    :module: {{ cli_module }}
    :name: {{ package_name }}
"""
