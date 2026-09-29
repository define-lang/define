"""Source text for formatting diagnostics."""

from __future__ import annotations

import functools
import hashlib
import typing
from pathlib import Path

if typing.TYPE_CHECKING:
    from pathlib import PurePosixPath

    from define.compiler import ast


def source_digest(source: bytes) -> bytes:
    """Return the digest that shows whether a source file is unchanged."""
    return hashlib.sha256(source).digest()


def _format_location_header(location: ast.SourceLocation) -> str:
    """Format a source location as a human-readable string."""
    if location.file_path is not None:
        return f'File "{location.file_path}", line {location.line}, column {location.column}'
    return f"line {location.line}, column {location.column}"


@typing.final
class SourceMap:
    """Finds the source lines that diagnostic locations point at.

    A file is read only when a location in it is formatted, and a file whose
    content changed after it was validated has no source lines.
    """

    def __init__(
        self,
        file_digests: dict[PurePosixPath, bytes],
        in_memory_source: str | None,
    ):
        """Initialize with each validated file's digest and any source validated without a file."""
        self._file_digests = file_digests
        self._in_memory_source = in_memory_source
        self._file_lines: dict[PurePosixPath, list[str] | None] = {}

    def format_location(self, location: ast.SourceLocation) -> str:
        """Format a location with its source line and a caret under its column."""
        header = _format_location_header(location)
        lines = self._source_lines(location.file_path)
        if lines is None:
            return header
        line_index = location.line - 1
        source_line = lines[line_index] if 0 <= line_index < len(lines) else ""
        caret_line = " " * (location.column - 1) + "^"
        return f"{header}\n{source_line}\n{caret_line}"

    @functools.cached_property
    def _in_memory_lines(self) -> list[str] | None:
        if self._in_memory_source is None:
            return None
        return self._in_memory_source.splitlines()

    def _source_lines(self, file_path: PurePosixPath | None) -> list[str] | None:
        # Locations in the in-memory source are the only ones without a file.
        if file_path is None:
            return self._in_memory_lines
        if file_path not in self._file_lines:
            self._file_lines[file_path] = self._read_lines(file_path)
        return self._file_lines[file_path]

    def _read_lines(self, file_path: PurePosixPath) -> list[str] | None:
        digest = self._file_digests[file_path]
        try:
            source = Path(file_path).read_bytes()
        except FileNotFoundError:
            return None
        # A file can change between validation and formatting, for example when
        # it is saved during a long compile. Its new text would put the caret
        # under the wrong code, so a changed file shows no source lines.
        if source_digest(source) != digest:
            return None
        return source.decode("utf-8").splitlines()
