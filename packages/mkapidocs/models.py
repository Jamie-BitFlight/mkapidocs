"""Data models for mkapidocs."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time
from enum import Enum
from typing import TYPE_CHECKING, ClassVar, TypeAlias, cast

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

from mkapidocs.yaml_utils import append_to_yaml_list, load_yaml_from_path

if TYPE_CHECKING:
    from pathlib import Path

# TOML spec v1.0.0 types - https://toml.io/en/v1.0.0
# These mirror the types in typings/tomlkit/__init__.pyi
# Use string form to avoid runtime evaluation issues with forward references
TomlPrimitive: TypeAlias = str | int | float | bool | date | time | datetime
TomlArray: TypeAlias = "list[str] | list[int] | list[float] | list[bool] | list[date] | list[time] | list[datetime] | list[TomlTable] | list[TomlArray]"
TomlValue: TypeAlias = "TomlPrimitive | TomlArray | TomlTable"
TomlTable: TypeAlias = "dict[str, TomlValue]"


class MessageType(Enum):
    """Message types with associated display styles."""

    ERROR = ("red", "Error")
    SUCCESS = ("green", "Success")
    INFO = ("blue", "Info")
    WARNING = ("yellow", "Warning")


class CIProvider(Enum):
    """CI/CD provider types."""

    GITHUB = "github"
    GITLAB = "gitlab"


class ProjectConfig(BaseModel):
    """PEP 621 [project] table configuration.

    See: https://peps.python.org/pep-0621/
    """

    model_config: ClassVar[ConfigDict] = ConfigDict(populate_by_name=True)

    name: str
    version: str | None = None
    description: str | None = None
    requires_python: str | None = Field(default=None, alias="requires-python")
    dependencies: list[str] = Field(default_factory=list)
    license: str | dict[str, str] | None = None
    scripts: dict[str, str] = Field(default_factory=dict)


class PyprojectConfig(BaseModel):
    """Complete pyproject.toml configuration.

    Includes PEP 621 [project] table and tool-specific configurations.
    """

    project: ProjectConfig
    # Use object for Pydantic (avoids recursion with TomlValue)
    # Actual TOML values are: str, int, float, bool, date, time, datetime, list, dict
    tool: dict[str, object] = Field(default_factory=dict)

    @property
    def tool_typed(self) -> TomlTable:
        """Get tool table with proper TOML typing for external code."""
        return cast("TomlTable", self.tool)

    @property
    def uv_index(self) -> list[dict[str, TomlValue]]:
        """Get UV index configuration."""
        uv = self.tool.get("uv", {})
        if not isinstance(uv, dict):
            return []
        uv_table = cast("dict[str, object]", uv)
        index = uv_table.get("index", [])
        if not isinstance(index, list):
            return []
        index_list = cast("list[object]", index)
        return [
            cast("dict[str, TomlValue]", item)
            for item in index_list
            if isinstance(item, dict)
        ]

    @property
    def ruff_lint_select(self) -> list[str]:
        """Get Ruff lint select configuration."""
        ruff = self.tool.get("ruff", {})
        if not isinstance(ruff, dict):
            return []
        ruff_table = cast("dict[str, object]", ruff)
        lint = ruff_table.get("lint", {})
        if not isinstance(lint, dict):
            return []
        lint_table = cast("dict[str, object]", lint)
        select = lint_table.get("select", [])
        if not isinstance(select, list):
            return []
        select_list = cast("list[object]", select)
        return [s for s in select_list if isinstance(s, str)]

    @property
    def cmake_source_dir(self) -> str | None:
        """Get pypis_delivery_service cmake_source_dir."""
        pds = self.tool.get("pypis_delivery_service", {})
        if not isinstance(pds, dict):
            return None
        pds_table = cast("dict[str, object]", pds)
        val = pds_table.get("cmake_source_dir")
        if isinstance(val, str):
            return val
        return None

    @property
    def has_scripts(self) -> bool:
        """Check if project defines CLI scripts in [project.scripts]."""
        return bool(self.project.scripts)

    @property
    def script_names(self) -> list[str]:
        """Get CLI command names from [project.scripts]."""
        return list(self.project.scripts.keys())

    @classmethod
    def from_dict(cls, data: TomlTable) -> PyprojectConfig:
        """Create PyprojectConfig from raw TOML dictionary.

        Args:
            data: Raw dictionary from tomlkit.load()

        Returns:
            Parsed and validated PyprojectConfig

        Raises:
            ValueError: If required fields are missing or invalid
        """
        return cls.model_validate(data)

    def to_dict(self) -> TomlTable:
        """Convert to dictionary suitable for tomlkit.dump().

        Returns:
            Dictionary with proper TOML types
        """
        return cast(
            "TomlTable",
            self.model_dump(by_alias=True, exclude_none=True, mode="python"),
        )


# GitLab CI include entry models
# See: https://docs.gitlab.com/ee/ci/yaml/#include


class GitLabIncludeLocal(BaseModel):
    """GitLab CI include entry with local path.

    Example:
        include:
          - local: '/templates/.gitlab-ci-template.yml'
    """

    local: str


class GitLabIncludeRemote(BaseModel):
    """GitLab CI include entry with remote URL.

    Example:
        include:
          - remote: 'https://gitlab.com/example-project/-/raw/main/.gitlab-ci.yml'
    """

    remote: str


class GitLabIncludeTemplate(BaseModel):
    """GitLab CI include entry with GitLab template.

    Example:
        include:
          - template: 'Auto-DevOps.gitlab-ci.yml'
    """

    template: str


class GitLabIncludeProject(BaseModel):
    """GitLab CI include entry from another project.

    Example:
        include:
          - project: 'my-group/my-project'
            ref: main
            file: '/templates/.gitlab-ci-template.yml'
    """

    project: str
    file: str | list[str]
    ref: str | None = None


class GitLabIncludeComponent(BaseModel):
    """GitLab CI include entry for CI/CD component.

    Example:
        include:
          - component: '$CI_SERVER_FQDN/my-org/security-components/secret-detection@1.0'
    """

    component: str


# GitLab CI include can be:
# - A string path (defaults to local or remote based on format)
# - A dict with one of: local, remote, template, project, or component
GitLabIncludeEntry = (
    str
    | GitLabIncludeLocal
    | GitLabIncludeRemote
    | GitLabIncludeTemplate
    | GitLabIncludeProject
    | GitLabIncludeComponent
)

# GitLab CI include value can be a single entry or a list of entries
GitLabIncludeValue = GitLabIncludeEntry | list[GitLabIncludeEntry]

# TypeAdapter for validating GitLab CI include from raw YAML data (handles both single and list)
GitLabIncludeAdapter: TypeAdapter[GitLabIncludeValue] = TypeAdapter(GitLabIncludeValue)


# Type aliases for raw YAML data (before Pydantic validation)
GitLabIncludeEntryRaw = str | dict[str, str | list[str] | None]
GitLabIncludeValueRaw = GitLabIncludeEntryRaw | list[GitLabIncludeEntryRaw]


@dataclass
class GitLabCIConfig:
    """GitLab CI configuration from .gitlab-ci.yml.

    Provides typed access to the `include` field. Other fields are stored in `extra`.

    Example:
        config = GitLabCIConfig.load(Path(".gitlab-ci.yml"))
        if config:
            for entry in config.include_list:
                ...
    """

    include: GitLabIncludeValueRaw | None = None
    stages: list[str] | None = None
    extra: dict[str, object] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> GitLabCIConfig:
        """Create GitLabCIConfig from a dictionary (e.g., ruamel.yaml output).

        Args:
            data: Dictionary from yaml.load(), typically a CommentedMap.

        Returns:
            GitLabCIConfig instance with typed fields.
        """
        # Make a copy to avoid mutating the original
        data_copy = dict(data)
        raw_include = data_copy.pop("include", None)
        raw_stages = data_copy.pop("stages", None)

        stages: list[str] | None = None
        if isinstance(raw_stages, list):
            stages = [str(s) for s in raw_stages]

        return cls(
            include=cast("GitLabIncludeValueRaw | None", raw_include),
            stages=stages,
            extra=data_copy,
        )

    @classmethod
    def load(cls, path: Path) -> GitLabCIConfig | None:
        """Load GitLab CI config from a YAML file.

        Args:
            path: Path to .gitlab-ci.yml file.

        Returns:
            GitLabCIConfig if file contains valid YAML dict, None otherwise.
        """
        data = load_yaml_from_path(path)
        if data is not None:
            return cls.from_dict(data)
        return None

    @classmethod
    def add_include_and_save(cls, path: Path, include_entry: dict[str, str]) -> bool:
        """Add an include entry to a GitLab CI file and save.

        Preserves existing YAML formatting and comments.

        Args:
            path: Path to .gitlab-ci.yml file.
            include_entry: Include entry to add (e.g., {"local": "path/to/file.yml"}).

        Returns:
            True if successfully modified and saved, False if file structure invalid.
        """
        return append_to_yaml_list(path, "include", include_entry)

    @classmethod
    def add_stage_and_save(cls, path: Path, stage: str) -> bool:
        """Add a stage to a GitLab CI file and save.

        Preserves existing YAML formatting and comments.

        Args:
            path: Path to .gitlab-ci.yml file.
            stage: Stage name to add (e.g., "deploy").

        Returns:
            True if successfully modified and saved, False if file structure invalid.
        """
        return append_to_yaml_list(path, "stages", stage)

    @property
    def include_list(self) -> list[GitLabIncludeEntryRaw]:
        """Get include as a list, normalizing single entries.

        Returns:
            List of include entries (empty if no includes).
        """
        if self.include is None:
            return []
        if isinstance(self.include, list):
            return self.include
        return [self.include]
