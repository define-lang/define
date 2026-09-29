"""Find the characters that the spec's Invisible Characters rule forbids."""

from __future__ import annotations

import bisect
import re
import typing

from define.compiler import ast
from define.compiler.errors import parser_exceptions
from define.compiler.parsing import (
    invisible_characters_data,
    parser_error_classification,
)

if typing.TYPE_CHECKING:
    import pathlib

_LAST_BMP_CODE_POINT = 0xFFFF
_JOINERS = "\u200c\u200d"
_VARIATION_SELECTORS = "\ufe0e\ufe0f"
# The grammar allows direction marks only in comments.
_DIRECTION_MARKS = "\u061c\u200e\u200f"


def _ranges_class(ranges: list[tuple[int, int]]) -> str:
    return "".join(f"\\U{start:08x}-\\U{end:08x}" for start, end in ranges)


_BMP_RANGES: list[tuple[int, int]] = []
_ASTRAL_RANGES: list[tuple[int, int]] = []
for _start, _end in invisible_characters_data.INVISIBLE_RANGES:
    if _start <= _LAST_BMP_CODE_POINT:
        _BMP_RANGES.append((_start, min(_end, _LAST_BMP_CODE_POINT)))
    if _end > _LAST_BMP_CODE_POINT:
        _ASTRAL_RANGES.append((max(_start, _LAST_BMP_CODE_POINT + 1), _end))
_ASTRAL_STARTS = [start for start, _ in _ASTRAL_RANGES]

_VISIBLE = (
    "[^\\x00-\\x20\\x7f"
    + _ranges_class(_BMP_RANGES)
    + _ranges_class(_ASTRAL_RANGES)
    + _JOINERS
    + _VARIATION_SELECTORS
    + _DIRECTION_MARKS
    + "]"
)
# The regular expression engine checks a class of BMP characters with a fast
# bitmap, but checks a class with astral characters one range at a time, which
# made searching over 100 times slower. So astral characters are only
# candidates here, and _is_invisible_astral decides them.
_CANDIDATE = re.compile(
    f"[{_ranges_class(_BMP_RANGES)}]"
    # A variation selector must follow a visible character.
    + f"|[{_VARIATION_SELECTORS}](?<!{_VISIBLE}[{_VARIATION_SELECTORS}])"
    # A joiner must follow a visible character or a variation selector, and
    # must come before a visible character.
    + f"|[{_JOINERS}](?<!{_VISIBLE}[{_JOINERS}])(?<![{_VARIATION_SELECTORS}][{_JOINERS}])"
    + f"|[{_JOINERS}](?!{_VISIBLE})"
    + f"|[\\U{_LAST_BMP_CODE_POINT + 1:08x}-\\U0010ffff]"
)


def _is_invisible_astral(code_point: int) -> bool:
    range_index = bisect.bisect_right(_ASTRAL_STARTS, code_point) - 1
    return range_index >= 0 and code_point <= _ASTRAL_RANGES[range_index][1]


def first_forbidden_index(source: str) -> int | None:
    """Return the index of the first character in ``source`` that the rule forbids, if any."""
    # Every forbidden character is outside ASCII, and checking for that is
    # much faster than searching.
    if source.isascii():
        return None
    position = 0
    while (match := _CANDIDATE.search(source, position)) is not None:
        code_point = ord(source[match.start()])
        if code_point <= _LAST_BMP_CODE_POINT or _is_invisible_astral(code_point):
            return match.start()
        position = match.end()
    return None


def check(source: str, file_path: pathlib.PurePosixPath | None):
    """Raise a syntax error if ``source`` has a character that the Invisible Characters rule forbids."""
    index = first_forbidden_index(source)
    if index is None:
        return
    char = source[index]
    line = source.count("\n", 0, index) + 1
    column = index - source.rfind("\n", 0, index)
    location = ast.SourceLocation(
        line=line,
        column=column,
        end_line=line,
        end_column=column + 1,
        file_path=file_path,
    )
    char_class = parser_error_classification.classify_invalid_char(char)
    # The more specific classes describe characters that are invalid anywhere.
    if char_class is None or char_class is parser_exceptions.InvalidCharacterError:
        raise parser_exceptions.InvisibleCharacterError(location, char)
    raise char_class(location, char)
