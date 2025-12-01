# Type stubs for ruamel.yaml
# Only types what mkapidocs uses

from io import StringIO
from pathlib import Path
from typing import IO, Literal

class YAML:
    preserve_quotes: bool

    def __init__(
        self,
        *,
        typ: Literal["rt", "safe", "unsafe", "base"] | list[str] | None = None,
        pure: bool = False,
        output: IO[str] | None = None,
        plug_ins: list[str] | None = None,
    ) -> None: ...
    def load(self, stream: str | bytes | IO[str] | IO[bytes] | Path) -> dict[str, object] | list[object] | None: ...
    def dump(self, data: object, stream: IO[str] | Path | None = None) -> str | None: ...
