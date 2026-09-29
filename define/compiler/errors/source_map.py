"""Source text for formatting diagnostics and syntax errors."""

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


_CODE_INDENTATION = "    "


def escape_invisible(text: str) -> str:
    """Replace non-printable characters with their Python escape sequences."""
    characters: list[str] = []
    for character in text:
        if character.isprintable():
            characters.append(character)
        else:
            characters.append(repr(character)[1:-1])
    return "".join(characters)


def _format_location_with_source_line(
    location: ast.SourceLocation,
    source_line: str | None,
    *,
    escape_invisible_characters: bool = False,
) -> str:
    """Format a location with its source line, underlined with carets.

    A location with no source line is formatted without one.
    """
    if location.file_path is not None:
        header = f'File "{location.file_path}", line {location.line}, column {location.column}'
    else:
        header = f"line {location.line}, column {location.column}"
    if source_line is None:
        return header
    # Only our own indentation should show, not the source's, unless the
    # location is in that indentation.
    code = source_line.lstrip(" ")
    indentation = len(source_line) - len(code)
    if location.column - 1 < indentation:
        code = source_line
        indentation = 0
    start = location.column - 1 - indentation
    # A span that continues onto later lines is underlined to the end of its
    # first line, so that the context stays one line long.
    if location.end_line == location.line:
        end = location.end_column - 1 - indentation
    else:
        end = len(code)
    if escape_invisible_characters:
        # Escaped characters are wider, so the underline moves with them.
        start = len(escape_invisible(code[:start]))
        end = len(escape_invisible(code[:end]))
        code = escape_invisible(code)
    underline = "^" * max(end - start, 1)
    code_line = f"{_CODE_INDENTATION}{code}" if code else ""
    return f"{header}\n{code_line}\n{_CODE_INDENTATION}{' ' * start}{underline}"


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

    def format_location(
        self, location: ast.SourceLocation, *, escape_invisible_characters: bool = False
    ) -> str:
        """Format a location with its source code, underlined with carets."""
        lines = self._source_lines(location.file_path)
        if lines is None:
            return _format_location_with_source_line(location, None)
        line_index = location.line - 1
        source_line = lines[line_index] if 0 <= line_index < len(lines) else ""
        return _format_location_with_source_line(
            location,
            source_line,
            escape_invisible_characters=escape_invisible_characters,
        )

    @functools.cached_property
    def _in_memory_lines(self) -> list[str] | None:
        if self._in_memory_source is None:
            return None
        # The parser numbers lines by newlines only, unlike str.splitlines, which
        # also splits at characters such as form feeds and line separators.
        return self._in_memory_source.split("\n")

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
