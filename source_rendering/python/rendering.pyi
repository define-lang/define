from pathlib import PurePosixPath
from typing import final

@final
class SourceLocation:
    def __new__(
        cls,
        *,
        line: int,
        column: int,
        end_line: int,
        end_column: int,
        file_path: PurePosixPath | None = None,
    ) -> SourceLocation: ...
    @property
    def line(self) -> int: ...
    @property
    def column(self) -> int: ...
    @property
    def end_line(self) -> int: ...
    @property
    def end_column(self) -> int: ...
    @property
    def file_path(self) -> PurePosixPath | None: ...
    def render(self, source_line: str | None) -> str: ...
