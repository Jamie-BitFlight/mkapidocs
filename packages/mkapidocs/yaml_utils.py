"""YAML utilities for mkapidocs.

Centralizes all YAML handling to ensure consistent formatting preservation
across the codebase. All YAML operations should go through this module.
"""

from __future__ import annotations

from contextlib import suppress
from dataclasses import dataclass
from io import StringIO
from pathlib import Path
from typing import cast

from rich import box
from rich.console import Console
from rich.table import Table
from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError
from ruamel.yaml.scalarstring import LiteralScalarString
from ruamel.yaml.util import load_yaml_guess_indent

# Initialize Rich console
console = Console()

# Re-export YAMLError for consumers that need to catch it
__all__ = ["YAMLError", "append_to_yaml_list", "load_yaml", "load_yaml_preserve_format", "merge_mkdocs_yaml"]


def load_yaml(content: str) -> dict[str, object] | None:
    """Load YAML content for read-only access.

    This is for cases where you just need to read YAML data without
    modifying and writing it back. Uses safe loading.

    Args:
        content: YAML content as string

    Returns:
        Parsed dictionary or None if content is not a valid dict
    """
    yaml = YAML(typ="safe")
    with suppress(YAMLError):
        data = yaml.load(content)
        if isinstance(data, dict):
            return cast(dict[str, object], data)
    return None


def load_yaml_from_path(path: Path) -> dict[str, object] | None:
    """Load YAML file for read-only access.

    Convenience wrapper around load_yaml() for file paths.

    Args:
        path: Path to YAML file

    Returns:
        Parsed dictionary or None if file doesn't exist or isn't valid YAML dict
    """
    if not path.exists():
        return None
    with suppress(OSError):
        content = path.read_text(encoding="utf-8")
        return load_yaml(content)
    return None


def load_yaml_preserve_format(path: Path) -> tuple[dict[str, object] | None, tuple[int, int, int]]:
    """Load YAML file preserving format metadata for round-trip editing.

    Use this when you need to modify and write back a YAML file while
    preserving its original formatting (indentation, comments, etc.).

    Args:
        path: Path to YAML file

    Returns:
        Tuple of (parsed_data, (mapping_indent, sequence_indent, offset))
        Returns (None, (2, 2, 0)) if file doesn't exist or isn't valid
    """
    default_indent = (2, 2, 0)
    if not path.exists():
        return None, default_indent

    try:
        content = path.read_text(encoding="utf-8")
    except OSError:
        return None, default_indent

    indent_settings = _detect_yaml_indentation(content)

    yaml = YAML()
    yaml.preserve_quotes = True
    yaml.indent(mapping=indent_settings[0], sequence=indent_settings[1], offset=indent_settings[2])  # pyright: ignore[reportAttributeAccessIssue]

    try:
        data = yaml.load(content)
        if isinstance(data, dict):
            return cast(dict[str, object], data), indent_settings
    except YAMLError:
        pass

    return None, default_indent


def _detect_yaml_indentation(content: str) -> tuple[int, int, int]:
    """Detect indentation settings from YAML content using ruamel.yaml.

    Uses ruamel.yaml's official load_yaml_guess_indent utility to determine
    the indentation style used in the file.

    Args:
        content: YAML file content as string

    Returns:
        Tuple of (mapping_indent, sequence_indent, offset) for ruamel.yaml.indent()
    """
    _, indent, block_seq_indent = load_yaml_guess_indent(content)

    # load_yaml_guess_indent returns:
    # - indent: the base indentation level (spaces per nesting level)
    # - block_seq_indent: spaces before the dash in block sequences (the offset)
    #
    # For yaml.indent(mapping=M, sequence=S, offset=O):
    # - mapping: spaces per nesting level for mappings
    # - sequence: spaces per nesting level for sequences
    # - offset: spaces before the dash (relative to parent)
    #
    # Examples:
    #   mkdocs.yml style (dash at same level as content):
    #     theme:
    #       features:
    #       - navigation.tabs
    #     Returns indent=2, block_seq_indent=0 -> mapping=2, sequence=2, offset=0
    #
    #   gitlab-ci.yml style (dash indented under parent):
    #     include:
    #       - local: "file.yml"
    #     Returns indent=4, block_seq_indent=2 -> mapping=2, sequence=2, offset=2
    mapping_indent = indent if indent is not None else 2
    offset = block_seq_indent if block_seq_indent is not None else 0

    # When offset > 0, the actual mapping indent is (indent - offset)
    # because indent includes the offset for sequence items
    if offset > 0:
        mapping_indent = indent - offset if indent else 2

    sequence_indent = mapping_indent

    return (mapping_indent, sequence_indent, offset)


def _preserve_scalar_style(value: object) -> object:
    r"""Convert values to appropriate ruamel.yaml scalar types to preserve formatting.

    Strings containing newlines are converted to LiteralScalarString so they
    render as block scalars (|) instead of quoted strings with \\n escapes.

    Args:
        value: Any value to potentially convert

    Returns:
        The value, possibly wrapped in a ruamel.yaml scalar type
    """
    if isinstance(value, str) and "\n" in value:
        return LiteralScalarString(value)
    return value


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


def _merge_yaml_in_place(
    existing_yaml: dict[str, object],
    template_yaml: dict[str, object],
    template_owned_keys: set[str],
    key_prefix: str = "",
    depth: int = 0,
    max_depth: int = 50,
) -> list[FileChange]:
    """Merge template into existing YAML in place, preserving formatting metadata.

    Modifies existing_yaml directly to preserve ruamel.yaml's CommentedMap
    structure and round-trip formatting (indentation, comments, etc.).

    Args:
        existing_yaml: Current YAML content from file (modified in place)
        template_yaml: New YAML content from template
        template_owned_keys: Set of key paths that template always controls
        key_prefix: Current key path for recursion (dot-separated)
        depth: Current recursion depth (internal parameter)
        max_depth: Maximum nesting depth to prevent stack overflow

    Returns:
        List of FileChange records describing modifications made

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

    changes: list[FileChange] = []

    # Process template keys - add or update in existing_yaml
    for key, template_value in template_yaml.items():
        current_path = f"{key_prefix}.{key}" if key_prefix else key
        existing_value = existing_yaml.get(key)

        # Check if this key is template-owned
        is_template_owned = any(
            current_path == owned_key or current_path.startswith(owned_key + ".") for owned_key in template_owned_keys
        )

        if is_template_owned:
            # Template controls this key - always update
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
            existing_yaml[key] = _preserve_scalar_style(template_value)
        elif isinstance(template_value, dict) and isinstance(existing_value, dict):
            # Recursively merge nested dicts in place
            existing_dict = cast(dict[str, object], existing_value)
            template_dict = cast(dict[str, object], template_value)
            nested_changes = _merge_yaml_in_place(
                existing_dict, template_dict, template_owned_keys, current_path, depth + 1, max_depth
            )
            changes.extend(nested_changes)
        elif existing_value is not None:
            # User has customized this - preserve it (no modification needed)
            existing_str = str(existing_value)
            changes.append(
                FileChange(key_path=current_path, action="preserved", old_value=existing_str, new_value=None)
            )
        else:
            # New key from template, not template-owned - add it
            existing_yaml[key] = _preserve_scalar_style(template_value)
            template_str = str(template_value) if template_value is not None else ""
            changes.append(FileChange(key_path=current_path, action="added", new_value=template_str))

    # Record existing keys not in template (user additions) - already preserved, just log them
    for key in existing_yaml:
        if key not in template_yaml:
            current_path = f"{key_prefix}.{key}" if key_prefix else key
            existing_value = existing_yaml[key]
            changes.append(
                FileChange(key_path=current_path, action="preserved", old_value=str(existing_value), new_value=None)
            )

    return changes


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

    # Detect and preserve original indentation style
    mapping_indent, sequence_indent, offset = _detect_yaml_indentation(existing_text)

    # Initialize ruamel.yaml with detected indentation
    yaml = YAML()
    yaml.preserve_quotes = True
    yaml.indent(mapping=mapping_indent, sequence=sequence_indent, offset=offset)  # pyright: ignore[reportAttributeAccessIssue]

    try:
        # ruamel.yaml load returns CommentedMap which acts like a dict
        existing_yaml_raw = yaml.load(existing_text)
        existing_yaml: dict[str, object] = existing_yaml_raw if isinstance(existing_yaml_raw, dict) else {}
    except YAMLError as e:
        msg = f"Failed to parse existing {existing_path.name}: {e}"
        raise CLIError(msg) from e

    # Parse template - for Python tags, replace them with placeholders for structural parsing
    template_for_parsing = template_content
    if "!!python/name:" in template_content:
        # Replace Python tags with placeholders for parsing structure
        import re

        template_for_parsing = re.sub(r"!!python/name:\S+", '"__PYTHON_TAG_PLACEHOLDER__"', template_content)

    try:
        # Use safe_load for template as it's generated by us and we want standard dicts
        yaml_safe = YAML(typ="safe")
        template_yaml_raw = yaml_safe.load(template_for_parsing)
        template_yaml: dict[str, object] = template_yaml_raw if isinstance(template_yaml_raw, dict) else {}
    except YAMLError as e:
        msg = f"Failed to parse template YAML: {e}"
        raise CLIError(msg) from e

    # Define template-owned keys for mkdocs.yml
    template_owned_keys = {
        "plugins.gen-files.scripts",
        "plugins.search",
        "plugins.mkdocstrings",
        "plugins.mermaid2",
        "plugins.termynal",
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

    # Merge in place to preserve ruamel.yaml's CommentedMap formatting
    changes = _merge_yaml_in_place(existing_yaml, template_yaml, template_owned_keys)

    # Dump the modified CommentedMap - preserves original indentation and structure
    stream = StringIO()
    yaml.dump(existing_yaml, stream)
    merged_content = stream.getvalue()

    return merged_content, changes


def append_to_yaml_list(file_path: Path, key: str, value: dict[str, str]) -> bool:
    """Append a value to a list in a YAML file, preserving formatting.

    Modifies the file in place, preserving all existing formatting, comments,
    and indentation by using ruamel.yaml's round-trip mode.

    Args:
        file_path: Path to the YAML file
        key: Top-level key containing the list (e.g., "include")
        value: Dictionary value to append to the list

    Returns:
        True if successfully modified and saved, False if file structure invalid
    """
    from ruamel.yaml.comments import CommentedMap, CommentedSeq

    content = file_path.read_text(encoding="utf-8")

    # Detect and preserve original indentation style
    mapping_indent, sequence_indent, offset = _detect_yaml_indentation(content)

    yaml = YAML()
    yaml.preserve_quotes = True
    yaml.indent(mapping=mapping_indent, sequence=sequence_indent, offset=offset)  # pyright: ignore[reportAttributeAccessIssue]

    raw_config = yaml.load(content)

    if not isinstance(raw_config, dict):
        return False

    # Modify in place to preserve formatting metadata
    existing_value = raw_config.get(key)

    if existing_value is None:
        # No existing key - create new CommentedSeq
        raw_config[key] = CommentedSeq([CommentedMap(value)])
    elif isinstance(existing_value, list):
        # Append to existing list in place (preserves CommentedSeq formatting)
        existing_value.append(CommentedMap(value))
    else:
        # Single entry - convert to list while preserving the original entry
        raw_config[key] = CommentedSeq([existing_value, CommentedMap(value)])

    stream = StringIO()
    yaml.dump(raw_config, stream)
    _ = file_path.write_text(stream.getvalue(), encoding="utf-8")
    return True
