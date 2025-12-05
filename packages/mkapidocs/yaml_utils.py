"""YAML utilities for mkapidocs.

Centralizes all YAML handling to ensure consistent formatting preservation
across the codebase. All YAML operations should go through this module.
"""

from __future__ import annotations

import re
from contextlib import suppress
from dataclasses import dataclass
from io import StringIO
from typing import TYPE_CHECKING, cast

from rich import box
from rich.console import Console
from rich.measure import Measurement
from rich.table import Table
from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap, CommentedSeq
from ruamel.yaml.error import YAMLError
from ruamel.yaml.scalarstring import LiteralScalarString, ScalarString
from ruamel.yaml.util import load_yaml_guess_indent

if TYPE_CHECKING:
    from pathlib import Path

# Index position for post-value comments in ruamel.yaml comment lists.
# Comment lists follow the format: [pre, side, post, end]
# Position 2 is where trailing blank lines and post-value comments are stored.
_COMMENT_POST_VALUE_INDEX = 2

# Initialize Rich console
console = Console()

# Re-export YAMLError for consumers that need to catch it
__all__ = [
    "YAMLError",
    "append_to_yaml_list",
    "load_yaml",
    "load_yaml_preserve_format",
    "merge_mkdocs_yaml",
]


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
            return cast("dict[str, object]", data)
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


def load_yaml_preserve_format(
    path: Path,
) -> tuple[dict[str, object] | None, tuple[int, int, int]]:
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
    yaml.indent(
        mapping=indent_settings[0],
        sequence=indent_settings[1],
        offset=indent_settings[2],
    )

    try:
        data = yaml.load(content)
        if isinstance(data, dict):
            return cast("dict[str, object]", data), indent_settings
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
    # - indent: total indentation for sequence item content (from parent to content after dash)
    # - block_seq_indent: spaces before the dash (the offset from parent to dash)
    #
    # For yaml.indent(mapping=M, sequence=S, offset=O):
    # - mapping: spaces per nesting level for mappings (parent key to child key)
    # - sequence: spaces for content within sequence items (controls dict keys under list items)
    # - offset: spaces before the dash (relative to parent)
    #
    # Examples:
    #   mkdocs.yml style (offset=0, content at dash+2):
    #     theme:
    #       features:
    #       - navigation.tabs      # dash at column 6, content at 8
    #     Returns indent=2, block_seq_indent=0
    #     -> mapping=2, sequence=2, offset=0
    #
    #   python_picotool style (offset=2, content at dash+2):
    #     palette:
    #       - scheme: default      # dash at column 4, content at 6
    #         primary: indigo      # continuation at column 6
    #     Returns indent=4, block_seq_indent=2
    #     -> mapping=2, sequence=4, offset=2
    #
    # The key insight: 'sequence' parameter controls indentation of dict keys
    # WITHIN a list item, so it should be the full indent value (not mapping_indent)
    offset = block_seq_indent if block_seq_indent is not None else 0
    sequence_indent = indent if indent is not None else 2

    # mapping_indent is the basic nesting level for dict keys
    # When offset > 0, mapping = indent - offset
    mapping_indent = (
        indent - offset
        if offset > 0 and indent
        else indent
        if indent is not None
        else 2
    )

    return (mapping_indent, sequence_indent, offset)


def _preserve_scalar_style(
    value: CommentedSeq | CommentedMap | ScalarString,
) -> CommentedSeq | CommentedMap | ScalarString:
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


def _copy_comment_attributes(source: object, target: object) -> None:
    """Copy ruamel.yaml comment attributes from source to target.

    This preserves blank lines, comments, and formatting metadata when
    replacing a value in a CommentedMap/CommentedSeq. Safely handles
    any value types - non-commented values are silently skipped.

    Args:
        source: Original value with potential comment attributes
        target: New value to copy comments to
    """
    # Both must have comment attributes (ca) - silently skip scalar values
    if not hasattr(source, "ca") or not hasattr(target, "ca"):
        return

    # After hasattr check, we know these are CommentedMap or CommentedSeq
    source_commented = cast("CommentedSeq | CommentedMap", source)
    target_commented = cast("CommentedSeq | CommentedMap", target)
    source_ca = source_commented.ca
    target_ca = target_commented.ca

    # Copy the main comment
    if source_ca.comment:
        target_ca.comment = source_ca.comment

    # For sequences, recursively copy item comments if lengths match
    if (
        isinstance(source, list)
        and isinstance(target, list)
        and len(source) == len(target)
    ):
        for _i, (src_item, tgt_item) in enumerate(zip(source, target, strict=False)):
            _copy_comment_attributes(src_item, tgt_item)

    # For dicts, copy comments for matching keys
    if isinstance(source, dict) and isinstance(target, dict):
        for key in source:
            if key in target:
                # Copy key-level comments
                if key in source_ca.items and key not in target_ca.items:
                    target_ca.items[key] = source_ca.items[key]
                # Recursively copy nested value comments
                _copy_comment_attributes(source[key], target[key])


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


def _get_table_width(table: Table) -> int:
    """Get the natural width of a table using a temporary wide console.

    Args:
        table: The Rich table to measure.

    Returns:
        The width in characters needed to display the table.
    """
    temp_console = Console(width=9999)
    measurement = Measurement.get(temp_console, temp_console.options, table)
    return int(measurement.maximum)


def display_file_changes(file_path: Path, changes: list[FileChange]) -> None:
    """Display a Rich table showing changes made to a configuration file.

    Only displays rows for actual changes (added/updated). Preserved rows
    are filtered out. If no actual changes occurred, nothing is displayed.

    Args:
        file_path: Path to the file that was modified.
        changes: List of FileChange records.
    """
    # Filter to only actual changes (not preserved)
    actual_changes = [c for c in changes if c.action in {"added", "updated"}]

    # No actual changes - nothing to display
    if not actual_changes:
        return

    table = Table(
        title=f":page_facing_up: Changes to {file_path.name}",
        box=box.MINIMAL_DOUBLE_HEAD,
        title_style="bold blue",
    )

    table.add_column("Key", style="cyan", no_wrap=True)
    table.add_column("Action", justify="center", no_wrap=True)
    table.add_column("Old Value", style="dim", no_wrap=True)
    table.add_column("New Value", style="green", no_wrap=True)

    for change in actual_changes:
        # Format action with emoji
        if change.action == "updated":
            action_display = "[green]:white_check_mark:[/green] Updated"
        else:  # added
            action_display = "[green]:white_check_mark:[/green] Added"

        # Format values - no truncation
        old_val = str(change.old_value) if change.old_value is not None else ""
        new_val = str(change.new_value) if change.new_value is not None else ""

        table.add_row(change.key_path, action_display, old_val, new_val)

    # Set table width to natural size and print
    table_width = _get_table_width(table)
    table.width = table_width
    console.print(table, crop=False, overflow="ignore", no_wrap=True, soft_wrap=True)


def _is_template_owned_key(current_path: str, template_owned_keys: set[str]) -> bool:
    """Check if a key path is controlled by the template.

    Returns:
        True if the current_path matches or is a child of any template-owned key.
    """
    return any(
        current_path == owned_key or current_path.startswith(owned_key + ".")
        for owned_key in template_owned_keys
    )


def _handle_template_owned_key(
    existing_yaml: dict[str, CommentedMap | CommentedSeq | ScalarString],
    key: str,
    current_path: str,
    existing_value: CommentedSeq | CommentedMap | ScalarString | None,
    template_value: CommentedSeq | CommentedMap | ScalarString,
) -> FileChange | None:
    """Handle a template-owned key update, preserving comments.

    Returns:
        FileChange record if value changed, None otherwise.
    """
    change = None
    if existing_value != template_value:
        if existing_value is None:
            change = FileChange(
                key_path=current_path, action="added", new_value=str(template_value)
            )
        else:
            change = FileChange(
                key_path=current_path,
                action="updated",
                old_value=str(existing_value),
                new_value=str(template_value),
            )
    new_value = _preserve_scalar_style(template_value)
    if existing_value is not None:
        _copy_comment_attributes(existing_value, new_value)
    existing_yaml[key] = new_value
    return change


def _merge_yaml_in_place(
    existing_yaml: dict[str, CommentedMap | CommentedSeq | ScalarString],
    template_yaml: dict[str, CommentedMap | CommentedSeq | ScalarString],
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
    if depth > max_depth:
        msg = (
            f"YAML structure exceeds maximum nesting depth ({max_depth}). "
            f"This may indicate a malformed configuration file or circular references."
        )
        raise CLIError(msg)

    changes: list[FileChange] = []

    for key, template_value in template_yaml.items():
        current_path = f"{key_prefix}.{key}" if key_prefix else key
        existing_value = existing_yaml.get(key)

        if _is_template_owned_key(current_path, template_owned_keys):
            change = _handle_template_owned_key(
                existing_yaml, key, current_path, existing_value, template_value
            )
            if change:
                changes.append(change)
        elif isinstance(template_value, dict) and isinstance(existing_value, dict):
            existing_dict = existing_value
            template_dict = template_value
            nested_changes = _merge_yaml_in_place(
                existing_dict,
                template_dict,
                template_owned_keys,
                current_path,
                depth + 1,
                max_depth,
            )
            changes.extend(nested_changes)
        elif existing_value is not None:
            changes.append(
                FileChange(
                    key_path=current_path,
                    action="preserved",
                    old_value=str(existing_value),
                    new_value=None,
                )
            )
        else:
            existing_yaml[key] = _preserve_scalar_style(template_value)
            template_str = str(template_value) if template_value is not None else ""
            changes.append(
                FileChange(
                    key_path=current_path, action="added", new_value=template_str
                )
            )

    # Record existing keys not in template (user additions) - already preserved, just log them
    for key, existing_value in existing_yaml.items():
        if key not in template_yaml:
            current_path = f"{key_prefix}.{key}" if key_prefix else key
            changes.append(
                FileChange(
                    key_path=current_path,
                    action="preserved",
                    old_value=str(existing_value),
                    new_value=None,
                )
            )

    return changes


def merge_mkdocs_yaml(
    existing_path: Path, template_content: str
) -> tuple[str, list[FileChange]]:
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
    existing_text = existing_path.read_text(encoding="utf-8")

    # Detect and preserve original indentation style
    mapping_indent, sequence_indent, offset = _detect_yaml_indentation(existing_text)

    # Initialize ruamel.yaml with detected indentation
    yaml = YAML()
    yaml.preserve_quotes = True
    yaml.indent(mapping=mapping_indent, sequence=sequence_indent, offset=offset)

    try:
        # ruamel.yaml load returns CommentedMap which acts like a dict
        existing_yaml = yaml.load(existing_text)
    except YAMLError as e:
        msg = f"Failed to parse existing {existing_path.name}: {e}"
        raise CLIError(msg) from e

    # Parse template - for Python tags, replace them with placeholders for structural parsing
    template_for_parsing = template_content
    if "!!python/name:" in template_content:
        # Replace Python tags with placeholders for parsing structure
        template_for_parsing = re.sub(
            r"!!python/name:\S+", '"__PYTHON_TAG_PLACEHOLDER__"', template_content
        )

    try:
        # Use safe_load for template as it's generated by us and we want standard dicts
        yaml_safe = YAML(typ="safe")
        template_yaml = yaml_safe.load(template_for_parsing)
    except YAMLError as e:
        msg = f"Failed to parse template YAML: {e}"
        raise CLIError(msg) from e

    # Define template-owned keys for mkdocs.yml
    # Note: markdown_extensions and theme.palette are NOT template-owned because:
    # 1. Users often customize them (colors, icons, custom_fences)
    # 2. They can contain Python tags that can't be safely round-tripped
    # 3. Replacing deeply nested structures loses comment/blank-line metadata
    template_owned_keys = {
        "plugins.gen-files.scripts",
        "plugins.search",
        "plugins.mkdocstrings",
        "plugins.mermaid2",
        "plugins.termynal",
        "plugins.literate-nav",
        "theme.name",
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


def _extract_trailing_comment(
    existing_list: CommentedSeq, last_idx: int
) -> CommentedSeq | None:
    """Extract trailing comment from the last item of a CommentedSeq.

    Handles two cases:
    1. ScalarString - comment stored on list.ca.items[index]
    2. CommentedMap - comment stored inside item.ca.items[key]

    Returns:
        The comment list [pre, side, post, end] if found, None otherwise.
        Always returns a 4-element list for consistency.
    """
    # Case 1: ScalarString - comment stored on list.ca.items[index]
    if isinstance(existing_list, CommentedSeq) and last_idx in existing_list.ca.items:
        return CommentedSeq(existing_list.ca.items.pop(last_idx))

    # Case 2: CommentedMap - comment stored inside item.ca.items[key]
    last_item = existing_list[last_idx]
    if isinstance(last_item, CommentedMap):
        for item_key in list(last_item.ca.items.keys()):
            comment_list = last_item.ca.items[item_key]
            # Check if post-value comment exists (where blank lines go)
            if (
                comment_list
                and len(comment_list) > _COMMENT_POST_VALUE_INDEX
                and comment_list[_COMMENT_POST_VALUE_INDEX] is not None
            ):
                trailing = comment_list[_COMMENT_POST_VALUE_INDEX]
                comment_list[_COMMENT_POST_VALUE_INDEX] = None
                # Return as full comment list for consistency
                return CommentedSeq([None, None, trailing, None])
    return None


def _apply_trailing_comment(
    existing_list: CommentedSeq, new_idx: int, comment_list: list[object]
) -> None:
    """Apply a trailing comment to the new last item of a CommentedSeq.

    Args:
        existing_list: The CommentedSeq being modified
        new_idx: Index of the newly appended item
        comment_list: The 4-element comment list [pre, side, post, end]
    """
    new_item = existing_list[new_idx]
    if isinstance(new_item, CommentedMap):
        # For dict items, add post-value comment to the first key
        trailing_token = (
            comment_list[_COMMENT_POST_VALUE_INDEX]
            if len(comment_list) > _COMMENT_POST_VALUE_INDEX
            else None
        )
        for item_key in new_item:
            if item_key not in new_item.ca.items:
                new_item.ca.items[item_key] = [None, None, None, None]
            new_item.ca.items[item_key][_COMMENT_POST_VALUE_INDEX] = trailing_token
            break
    elif isinstance(existing_list, CommentedSeq):
        # For plain values, add full comment list to list's ca.items
        existing_list.ca.items[new_idx] = comment_list


def append_to_yaml_list(file_path: Path, key: str, value: str | dict[str, str]) -> bool:
    """Append a value to a list in a YAML file, preserving formatting.

    Modifies the file in place, preserving all existing formatting, comments,
    and indentation by using ruamel.yaml's round-trip mode.

    Args:
        file_path: Path to the YAML file
        key: Top-level key containing the list (e.g., "include")
        value: Value to append (string or dictionary)

    Returns:
        True if successfully modified and saved, False if file structure invalid
    """
    content = file_path.read_text(encoding="utf-8")

    # Detect and preserve original indentation style
    mapping_indent, sequence_indent, offset = _detect_yaml_indentation(content)

    yaml = YAML()
    yaml.preserve_quotes = True
    yaml.indent(mapping=mapping_indent, sequence=sequence_indent, offset=offset)

    raw_config = yaml.load(content)

    if not isinstance(raw_config, dict):
        return False

    # Prepare value for insertion
    item_to_append = CommentedMap(value) if isinstance(value, dict) else value

    # Modify in place to preserve formatting metadata
    existing_value = raw_config.get(key)

    if existing_value is None:
        # No existing key - create new CommentedSeq
        raw_config[key] = CommentedSeq([item_to_append])
    elif isinstance(existing_value, CommentedSeq):
        # Append to existing list, moving trailing blank line to new item
        last_idx = len(existing_value) - 1
        trailing_comment = _extract_trailing_comment(existing_value, last_idx)
        existing_value.append(item_to_append)
        if trailing_comment is not None:
            _apply_trailing_comment(
                existing_value, len(existing_value) - 1, list(trailing_comment)
            )
    else:
        # Single entry - convert to list while preserving the original entry
        raw_config[key] = CommentedSeq([existing_value, item_to_append])

    stream = StringIO()
    yaml.dump(raw_config, stream)
    _ = file_path.write_text(stream.getvalue(), encoding="utf-8")
    return True
