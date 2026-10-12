"""Literal Parsers built into the compiler."""

from __future__ import annotations

import re
import string
from typing import TYPE_CHECKING, Final

from define.compiler import constants

if TYPE_CHECKING:
    from collections.abc import Callable

# Only the canonical spelling of each number is accepted: no leading zeros, no
# trailing zeros after the decimal point, and no -0.
_DECIMAL: Final = re.compile(r"(?!-0\Z)-?(?:0|[1-9][0-9]*)(?:\.[0-9]*[1-9])?")


class LiteralParseError(Exception):
    """Raised when a Literal Parser cannot parse a literal's content."""

    def __init__(self, reason: str, content_index: int):
        """Initialize with why parsing failed and the content character at fault."""
        super().__init__(reason)
        self.reason: str = reason
        self.content_index: int = content_index


def _parse_decimal_ascii(content: str) -> str:
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
    integer_start = 1 if content[0] == "-" else 0
    integer_part, _, fraction = content[integer_start:].partition(".")
    if len(integer_part) > 1 and integer_part[0] == "0":
        return LiteralParseError(
            "numbers are written without leading zeros", integer_start
        )
    if fraction and not fraction.strip("0"):
        return LiteralParseError(
            "whole numbers are written without a decimal point",
            integer_start + len(integer_part),
        )
    if fraction.endswith("0"):
        return LiteralParseError(
            "numbers are written without trailing zeros after the decimal point",
            last_index,
        )
    if content == "-0":
        return LiteralParseError("zero is written without a minus sign", 0)
    raise ValueError(f"valid decimal content was rejected: {content!r}")


_BOOLEANS: Final = frozenset({"true", "false"})


def _parse_boolean_ascii(content: str) -> str:
    if content in _BOOLEANS:
        return content
    if content.lower() in _BOOLEANS:
        for index, char in enumerate(content):
            if char.isupper():
                raise LiteralParseError("booleans are written in lowercase", index)
    raise LiteralParseError("a boolean is either true or false", 0)


# Binary values have no length, so leading zeros would give one value several
# spellings.
_BINARY: Final = re.compile(r"0|1[01]*")


def _binary_bits(content: str, start: int) -> str:
    bits = content[start:]
    if _BINARY.fullmatch(bits) is not None:
        return bits
    if not bits:
        raise LiteralParseError("there must be at least one bit", start)
    for index in range(start, len(content)):
        if content[index] not in "01":
            raise LiteralParseError("only the bits 0 and 1 are allowed", index)
    raise LiteralParseError("binary values are written without leading zeros", start)


def _parse_binary_ascii(content: str) -> str:
    return _binary_bits(content, 0)


def _binary_as_decimal(bits: str) -> str:
    # TODO: Convert binary literals longer than about 14,000 bits, which exceed
    # Python's limit on converting an int to a decimal string and so raise
    # ValueError.
    return str(int(bits, 2))


def _parse_binary_ascii_as_integer_ascii(content: str) -> str:
    sign = "-" if content.startswith("-") else ""
    bits = _binary_bits(content, len(sign))
    if sign and bits == "0":
        raise LiteralParseError("zero is written without a minus sign", 0)
    return sign + _binary_as_decimal(bits)


def _parse_binary_ascii_as_natural_ascii(content: str) -> str:
    if content.startswith("-"):
        raise LiteralParseError("negative numbers are not allowed", 0)
    return _binary_as_decimal(_parse_binary_ascii(content))


def _reject_negative(decimal: str):
    if decimal.startswith("-"):
        raise LiteralParseError("negative numbers are not allowed", 0)


def _reject_fraction(decimal: str):
    decimal_point = decimal.find(".")
    if decimal_point != -1:
        raise LiteralParseError("only whole numbers are allowed", decimal_point)


def _parse_decimal_ascii_as_binary_ascii(content: str) -> str:
    decimal = _parse_decimal_ascii(content)
    _reject_negative(decimal)
    _reject_fraction(decimal)
    # TODO: Convert decimal literals longer than 4300 digits, which exceed
    # Python's limit on converting a decimal string to an int and so raise
    # ValueError.
    return format(int(decimal), "b")


def _parse_decimal_ascii_as_integer_ascii(content: str) -> str:
    decimal = _parse_decimal_ascii(content)
    _reject_fraction(decimal)
    return decimal


def _parse_decimal_ascii_as_natural_ascii(content: str) -> str:
    decimal = _parse_decimal_ascii(content)
    _reject_negative(decimal)
    _reject_fraction(decimal)
    return decimal


def _parse_utf8_as_scalar_utf8(content: str) -> str:
    if not content:
        raise LiteralParseError("there must be exactly one scalar", 0)
    if len(content) > 1:
        raise LiteralParseError("there must be exactly one scalar", 1)
    return content


# Code points have no length, so leading zeros would give one code point
# several spellings.
_CODE_POINT_ASCII: Final = re.compile(r"0|[1-9A-F][0-9A-F]*")
_HEX_DIGITS: Final = frozenset(string.digits + "ABCDEF")


def _parse_code_point_ascii_as_scalar_utf8(content: str) -> str:
    if _CODE_POINT_ASCII.fullmatch(content) is None:
        raise _code_point_ascii_error(content)
    code_point = int(content, 16)
    if code_point > 0x10FFFF:
        raise LiteralParseError("code points end at 10FFFF", 0)
    if 0xD800 <= code_point <= 0xDFFF:
        raise LiteralParseError("surrogates are not scalars", 0)
    return chr(code_point)


def _code_point_ascii_error(content: str) -> LiteralParseError:
    # Only invalid content reaches this, so it favors clear errors over speed.
    if not content:
        return LiteralParseError("there must be at least one hex digit", 0)
    for index, char in enumerate(content):
        if char in _HEX_DIGITS:
            continue
        if char in "abcdef":
            return LiteralParseError("hex digits are written in uppercase", index)
        return LiteralParseError(f"'{char}' is not allowed in a code point", index)
    return LiteralParseError("code points are written without leading zeros", 0)


# Keyed by the Potential Literal's encoding and then the value's encoding.
LITERAL_PARSERS: Final[dict[tuple[str, str], Callable[[str], str]]] = {
    (
        constants.BINARY_ASCII_ENCODING,
        constants.BINARY_ASCII_ENCODING,
    ): _parse_binary_ascii,
    (
        constants.BINARY_ASCII_ENCODING,
        constants.DECIMAL_ASCII_ENCODING,
    ): _parse_binary_ascii_as_integer_ascii,
    (
        constants.BINARY_ASCII_ENCODING,
        constants.INTEGER_ASCII_ENCODING,
    ): _parse_binary_ascii_as_integer_ascii,
    (
        constants.BINARY_ASCII_ENCODING,
        constants.NATURAL_ASCII_ENCODING,
    ): _parse_binary_ascii_as_natural_ascii,
    (
        constants.BOOLEAN_ASCII_ENCODING,
        constants.BOOLEAN_ASCII_ENCODING,
    ): _parse_boolean_ascii,
    (
        constants.CODE_POINT_ASCII_ENCODING,
        constants.SCALAR_UTF8_ENCODING,
    ): _parse_code_point_ascii_as_scalar_utf8,
    (
        constants.DECIMAL_ASCII_ENCODING,
        constants.BINARY_ASCII_ENCODING,
    ): _parse_decimal_ascii_as_binary_ascii,
    (
        constants.DECIMAL_ASCII_ENCODING,
        constants.DECIMAL_ASCII_ENCODING,
    ): _parse_decimal_ascii,
    (
        constants.DECIMAL_ASCII_ENCODING,
        constants.INTEGER_ASCII_ENCODING,
    ): _parse_decimal_ascii_as_integer_ascii,
    (
        constants.DECIMAL_ASCII_ENCODING,
        constants.NATURAL_ASCII_ENCODING,
    ): _parse_decimal_ascii_as_natural_ascii,
    (
        constants.UTF8_ENCODING,
        constants.SCALAR_UTF8_ENCODING,
    ): _parse_utf8_as_scalar_utf8,
}
