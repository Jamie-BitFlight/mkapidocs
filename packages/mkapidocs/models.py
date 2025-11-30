"""Data models for mkapidocs."""

from __future__ import annotations

from enum import Enum
from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict, Field


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
    requires_python: str | None = Field(None, alias="requires-python")
    dependencies: list[str] = Field(default_factory=list)
    license: str | dict[str, str] | None = None


class PyprojectConfig(BaseModel):
    """Complete pyproject.toml configuration.

    Includes PEP 621 [project] table and tool-specific configurations.
    """

    project: ProjectConfig
    tool: dict[str, Any] = Field(default_factory=dict)

    @property
    def uv_index(self) -> list[dict[str, str]]:
        """Get UV index configuration."""
        uv = self.tool.get("uv", {})
        if isinstance(uv, dict):
            index = uv.get("index", [])
            if isinstance(index, list):
                return [i for i in index if isinstance(i, dict)]
        return []

    @property
    def ruff_lint_select(self) -> list[str]:
        """Get Ruff lint select configuration."""
        ruff = self.tool.get("ruff", {})
        if isinstance(ruff, dict):
            lint = ruff.get("lint", {})
            if isinstance(lint, dict):
                select = lint.get("select", [])
                if isinstance(select, list):
                    return [s for s in select if isinstance(s, str)]
        return []

    @property
    def cmake_source_dir(self) -> str | None:
        """Get pypis_delivery_service cmake_source_dir."""
        pds = self.tool.get("pypis_delivery_service", {})
        if isinstance(pds, dict):
            return pds.get("cmake_source_dir")
        return None

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> PyprojectConfig:
        """Create PyprojectConfig from raw TOML dictionary.

        Args:
            data: Raw dictionary from tomllib.load()

        Returns:
            Parsed and validated PyprojectConfig

        Raises:
            ValueError: If required fields are missing or invalid
        """
        return cls.model_validate(data)

    def to_dict(self) -> dict[str, object]:
        """Convert to dictionary suitable for tomli_w.dump().

        Returns:
            Dictionary with proper TOML types
        """
        return self.model_dump(by_alias=True, exclude_none=True, mode="python")
