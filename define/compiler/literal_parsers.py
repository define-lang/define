"""Literal Parsers built into the compiler."""

from __future__ import annotations

import re
import string
from typing import TYPE_CHECKING, Final

from define.compiler import constants

if TYPE_CHECKING:
    from collections.abc import Callable

_DECIMAL: Final = re.compile(r"-?[0-9]+(?:\.[0-9]+)?")


class LiteralParseError(Exception):
    """Raised when a Literal Parser cannot parse a literal's content."""

    def __init__(self, reason: str, content_index: int):
        """Initialize with why parsing failed and the content character at fault."""
        super().__init__(reason)
        self.reason: str = reason
        self.content_index: int = content_index


def _parse_decimal_ascii(content: str) -> str:
    # TODO: Canonicalize decimal literals so that equal numbers always have
    # identical values.
    if _DECIMAL.fullmatch(content) is None:
        raise _decimal_error(content)
    return content


def _decimal_error(content: str) -> LiteralParseError:
    # Only invalid content reaches this, so it favors clear errors over speed.
    if not content:
        return LiteralParseError("there must be at least one digit", 0)
    has_decimal_point = False
    for index, char in enumerate(content):
        previous_is_digit = index > 0 and content[index - 1] in string.digits
        if char in string.digits:
            continue
        if char == "+" and index == 0:
            return LiteralParseError("positive numbers are written without a +", index)
        if char == "-":
            if index != 0:
                return LiteralParseError(
                    "a minus sign may only appear at the start", index
                )
        elif char == ".":
            if has_decimal_point:
                return LiteralParseError(
                    "a number may have only one decimal point", index
                )
            if not previous_is_digit:
                return LiteralParseError(
                    "there must be a digit before the decimal point", index
                )
            has_decimal_point = True
        elif char.isdigit():
            return LiteralParseError("only the digits 0 through 9 are allowed", index)
        else:
            return LiteralParseError(f"'{char}' is not allowed in a number", index)
    last_index = len(content) - 1
    if content[last_index] == "-":
        return LiteralParseError(
            "there must be a digit after the minus sign", last_index
        )
    if content[last_index] == ".":
        return LiteralParseError(
            "there must be a digit after the decimal point", last_index
        )
    raise ValueError(f"valid decimal content was rejected: {content!r}")


# Keyed by the Potential Literal's encoding and then the value's encoding.
LITERAL_PARSERS: Final[dict[tuple[str, str], Callable[[str], str]]] = {
    (
        constants.DECIMAL_ASCII_ENCODING,
        constants.DECIMAL_ASCII_ENCODING,
    ): _parse_decimal_ascii,
}
