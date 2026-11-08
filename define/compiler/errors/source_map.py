"""Source text for formatting diagnostics and syntax errors."""

from __future__ import annotations

import functools
import hashlib
import typing
import unicodedata
from pathlib import Path

if typing.TYPE_CHECKING:
    from pathlib import PurePosixPath

    from define.compiler.data_structures import define_path
    from source_rendering.python import rendering


def source_digest(source: bytes) -> bytes:
    """Return the digest that shows whether a source file is unchanged."""
    return hashlib.sha256(source).digest()


def describe_invisible_character(character: str) -> str:
    """Return the character's code point and, when Unicode names it, its name."""
    code_point = f"U+{ord(character):04X}"
    name = unicodedata.name(character, "")
    return f"{code_point} {name}" if name else code_point


@typing.final
class SourceMap:
    """Finds the source lines that diagnostic locations point at.

    A file is read only when a location in it is formatted, and a file whose
    content changed after it was validated has no source lines.
    """

    def __init__(
        self,
        file_digests: dict[define_path.DefinePath, bytes],
        in_memory_source: str | None,
    ):
        """Initialize with each validated file's digest and any source validated without a file."""
        self._file_digests_by_define_path = file_digests
        self._in_memory_source = in_memory_source
        self._file_lines: dict[PurePosixPath, list[str] | None] = {}

    def format_location(self, location: rendering.SourceLocation) -> str:
        """Format a location with its source code, underlined with carets."""
        lines = self._source_lines(location.file_path)
        if lines is None:
            return location.render(None)
        line_index = location.line - 1
        source_line = lines[line_index] if 0 <= line_index < len(lines) else ""
        return location.render(source_line)

    @functools.cached_property
    def _in_memory_lines(self) -> list[str] | None:
        if self._in_memory_source is None:
            return None
        # The parser numbers lines by newlines only, unlike str.splitlines, which
        # also splits at characters such as form feeds and line separators.
        return self._in_memory_source.split("\n")

    @functools.cached_property
    def _file_digests(self) -> dict[PurePosixPath, bytes]:
        # Diagnostic locations name their files by PurePosixPath, so finding a
        # file's digest needs a table keyed that way. Converting every file's
        # path takes noticeable time in a program with many files, and most
        # compiles report no diagnostics, so the table is built only when the
        # first location is formatted.
        file_digests: dict[PurePosixPath, bytes] = {}
        for file_path, digest in self._file_digests_by_define_path.items():
            file_digests[file_path.as_posix_path()] = digest
        return file_digests

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
        # A file that is not valid UTF-8 is reported as a syntax error, and its
        # invalid bytes show as replacement characters.
        return source.decode("utf-8", errors="replace").split("\n")
