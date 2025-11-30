"""YAML merging utilities for mkapidocs."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import cast

import yaml
from rich import box
from rich.console import Console
from rich.table import Table

# Initialize Rich console
console = Console()


class CLIError(Exception):
    """Base exception for CLI errors."""


@dataclass
class FileChange:
    """Record of a change made to a configuration file.

    Attributes:
        key_path: Dot-separated path to the key (e.g., "theme.name")
        action: Type of change (updated, added, preserved)
        old_value: Previous value (None if newly added)
        new_value: New value (None if preserved)
    """

    key_path: str
    action: str  # "updated", "added", "preserved"
    old_value: str | None = None
    new_value: str | None = None


def display_file_changes(file_path: Path, changes: list[FileChange]) -> None:
    """Display a Rich table showing changes made to a configuration file.

    Args:
        file_path: Path to the file that was modified
        changes: List of FileChange records
    """
    if not changes:
        return

    table = Table(
        title=f":page_facing_up: Changes to {file_path.name}", box=box.MINIMAL_DOUBLE_HEAD, title_style="bold blue"
    )

    table.add_column("Key", style="cyan", no_wrap=True)
    table.add_column("Action", justify="center", no_wrap=True)
    table.add_column("Old Value", style="dim")
    table.add_column("New Value", style="green")

    for change in changes:
        # Format action with emoji
        if change.action == "updated":
            action_display = "[green]:white_check_mark:[/green] Updated"
        elif change.action == "added":
            action_display = "[green]:white_check_mark:[/green] Added"
        elif change.action == "preserved":
            action_display = "[yellow]:black_circle:[/yellow] Preserved"
        else:
            action_display = change.action

        # Format values
        old_val = str(change.old_value) if change.old_value is not None else ""
        new_val = str(change.new_value) if change.new_value is not None else ""

        # Truncate long values
        if len(old_val) > 50:
            old_val = old_val[:47] + "..."
        if len(new_val) > 50:
            new_val = new_val[:47] + "..."

        table.add_row(change.key_path, action_display, old_val, new_val)

    console.print(table)


def _merge_yaml_configs(
    existing_yaml: dict[str, object],
    template_yaml: dict[str, object],
    template_owned_keys: set[str],
    key_prefix: str = "",
    depth: int = 0,
    max_depth: int = 50,
) -> tuple[dict[str, object], list[FileChange]]:
    """Recursively merge YAML configurations, preserving user customizations.

    Args:
        existing_yaml: Current YAML content from file
        template_yaml: New YAML content from template
        template_owned_keys: Set of key paths that template always controls
        key_prefix: Current key path for recursion (dot-separated)
        depth: Current recursion depth (internal parameter)
        max_depth: Maximum nesting depth to prevent stack overflow

    Returns:
        Tuple of (merged_yaml, list_of_changes)

    Raises:
        CLIError: If YAML structure conflicts prevent clean merge or depth exceeds limit
    """
    # Check recursion depth to prevent stack overflow
    if depth > max_depth:
        msg = (
            f"YAML structure exceeds maximum nesting depth ({max_depth}). "
            f"This may indicate a malformed configuration file or circular references."
        )
        raise CLIError(msg)

    merged: dict[str, object] = {}
    changes: list[FileChange] = []

    # First, handle all template keys
    for key, template_value in template_yaml.items():
        current_path = f"{key_prefix}.{key}" if key_prefix else key
        existing_value = existing_yaml.get(key)

        # Check if this key is template-owned
        is_template_owned = any(
            current_path == owned_key or current_path.startswith(owned_key + ".") for owned_key in template_owned_keys
        )

        if is_template_owned:
            # Template controls this key - always update
            merged[key] = template_value
            if existing_value != template_value:
                if existing_value is None:
                    changes.append(FileChange(key_path=current_path, action="added", new_value=str(template_value)))
                else:
                    changes.append(
                        FileChange(
                            key_path=current_path,
                            action="updated",
                            old_value=str(existing_value),
                            new_value=str(template_value),
                        )
                    )
        elif isinstance(template_value, dict) and isinstance(existing_value, dict):
            # Recursively merge nested dicts - cast to known types after isinstance check
            existing_dict = cast(dict[str, object], existing_value)
            template_dict = cast(dict[str, object], template_value)
            merged_nested, nested_changes = _merge_yaml_configs(
                existing_dict, template_dict, template_owned_keys, current_path, depth + 1, max_depth
            )
            merged[key] = merged_nested
            changes.extend(nested_changes)
        elif existing_value is not None:
            # User has customized this - preserve it
            merged[key] = existing_value
            existing_str = str(existing_value) if existing_value is not None else ""
            changes.append(
                FileChange(key_path=current_path, action="preserved", old_value=existing_str, new_value=None)
            )
        else:
            # New key from template, not template-owned
            merged[key] = template_value
            # isinstance narrowing creates Unknown type that propagates to str()
            template_str = str(template_value) if template_value is not None else ""  # pyright: ignore[reportUnknownArgumentType]
            changes.append(FileChange(key_path=current_path, action="added", new_value=template_str))

    # Now handle existing keys not in template (user additions)
    for key, existing_value in existing_yaml.items():
        if key not in merged:
            current_path = f"{key_prefix}.{key}" if key_prefix else key
            merged[key] = existing_value
            changes.append(
                FileChange(key_path=current_path, action="preserved", old_value=str(existing_value), new_value=None)
            )

    return merged, changes


def merge_mkdocs_yaml(existing_path: Path, template_content: str) -> tuple[str, list[FileChange]]:
    """Merge existing mkdocs.yml with template, preserving user customizations.

    Args:
        existing_path: Path to existing mkdocs.yml
        template_content: Rendered template content

    Returns:
        Tuple of (merged_yaml_string, list_of_changes)

    Raises:
        CLIError: If YAML parsing fails or merge conflicts occur
    """
    # Read existing file text
    existing_text = existing_path.read_text()

    # Use UnsafeLoader to handle Python-specific YAML tags like !!python/name:
    # Security justification: This parses the user's own mkdocs.yml file from their project,
    # not untrusted external input. MkDocs configuration legitimately uses Python tags
    # (e.g., !!python/name:mermaid2.fence_mermaid_custom for custom fence handlers).
    # safe_load() cannot parse these tags, so UnsafeLoader is required.
    try:
        # yaml.load returns Any - assign to object type to satisfy type checker
        existing_yaml_raw: object = yaml.load(existing_text, Loader=yaml.UnsafeLoader)  # noqa: S506  # pyright: ignore[reportAny]
        # Cast to dict for type safety after type check
        existing_yaml: dict[str, object] = (
            cast(dict[str, object], existing_yaml_raw) if isinstance(existing_yaml_raw, dict) else {}
        )
    except yaml.YAMLError as e:
        msg = f"Failed to parse existing {existing_path.name}: {e}"
        raise CLIError(msg) from e

    # Parse template - for Python tags, replace them with placeholders for structural parsing
    template_for_parsing = template_content
    if "!!python/name:" in template_content:
        # Replace Python tags with placeholders for parsing structure
        import re

        template_for_parsing = re.sub(r"!!python/name:\S+", '"__PYTHON_TAG_PLACEHOLDER__"', template_content)

    try:
        # yaml.safe_load returns Any - assign to object type to satisfy type checker
        template_yaml_raw: object = yaml.safe_load(template_for_parsing)  # pyright: ignore[reportAny]
        # Cast to dict for type safety after type check
        template_yaml: dict[str, object] = (
            cast(dict[str, object], template_yaml_raw) if isinstance(template_yaml_raw, dict) else {}
        )
    except yaml.YAMLError as e:
        msg = f"Failed to parse template YAML: {e}"
        raise CLIError(msg) from e

    # Define template-owned keys for mkdocs.yml
    template_owned_keys = {
        "plugins.gen-files.scripts",
        "plugins.search",
        "plugins.mkdocstrings",
        "plugins.mermaid2",
        "plugins.termynal",
        "plugins.recently-updated",
        "plugins.literate-nav",
        "theme.name",
        "theme.palette",
        "markdown_extensions",
    }

    # Add site_url and repo_url if template provides them
    if template_yaml.get("site_url"):
        template_owned_keys.add("site_url")
    if template_yaml.get("repo_url"):
        template_owned_keys.add("repo_url")

    merged_yaml, changes = _merge_yaml_configs(existing_yaml, template_yaml, template_owned_keys)

    # Convert back to YAML string - use unsafe dump to preserve Python tags
    merged_content = yaml.dump(
        merged_yaml, default_flow_style=False, sort_keys=False, allow_unicode=True, Dumper=yaml.Dumper
    )

    return merged_content, changes
