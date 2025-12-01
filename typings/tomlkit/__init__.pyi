# Type stubs for tomlkit
# TOML spec v1.0.0 types - https://toml.io/en/v1.0.0

from datetime import date, datetime, time
from typing import IO, TypeAlias

# TOML primitives
TomlPrimitive: TypeAlias = str | int | float | bool | date | time | datetime

# TOML arrays are homogeneous (same type per array)
TomlArray: TypeAlias = (
    list[str]
    | list[int]
    | list[float]
    | list[bool]
    | list[date]
    | list[time]
    | list[datetime]
    | list["TomlTable"]
    | list["TomlArray"]
)

# TOML values
TomlValue: TypeAlias = TomlPrimitive | TomlArray | "TomlTable"

# TOML table (dict with string keys)
TomlTable: TypeAlias = dict[str, TomlValue]

# tomlkit.load accepts text mode file (IO[str]), not binary
def load(fp: IO[str]) -> TomlTable: ...
def loads(s: str) -> TomlTable: ...
def dump(data: TomlTable, fp: IO[str]) -> None: ...
def dumps(data: TomlTable) -> str: ...
