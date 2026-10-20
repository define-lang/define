"""Compares the Lark parser with the parser in parser.rs on the same source."""

# TODO: Remove this module, and its calls in the parse helpers for tests, once
# the parser in parser.rs replaces the Lark parser.

from __future__ import annotations

import enum
import typing

import msgspec

from define.compiler.errors import parser_exceptions
from define.compiler.parsing import parser
from define.compiler.parsing.native import native_parser

if typing.TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import PurePosixPath

_LARK_PARSER = parser.Parser()


class Agreement(enum.Enum):
    """How the two parsers agreed about a source."""

    SAME_PROGRAM = enum.auto()
    BOTH_REJECTED = enum.auto()
    NOT_YET_SUPPORTED = enum.auto()
    """The parser in parser.rs does not support the source yet."""


class ParsersDisagreeError(AssertionError):
    """Raised when the two parsers disagree about a source."""


def native_parse(
    source: str, file_path: PurePosixPath | None = None
) -> native_parser.ParseResult:
    """Parse source into an AST Program with the parser in parser.rs."""
    # A lone surrogate in source becomes invalid UTF-8, as it would be in a
    # file, instead of failing to encode.
    return native_parser.parse(source.encode(errors="surrogatepass"), file_path)


def native_parse_where_lark_is_wrong(
    source: str, file_path: PurePosixPath | None = None
) -> native_parser.ParseResult:
    """Parse source with the parser in parser.rs, for a source the Lark parser accepts by mistake.

    Raises:
        ParsersDisagreeError: The Lark parser no longer accepts the source.
    """
    lark_result = _LARK_PARSER.parse_and_transform(source, file_path=file_path)
    if lark_result.exception is not None or lark_result.diagnostics:
        raise ParsersDisagreeError(f"the Lark parser no longer accepts {source!r}")
    return native_parse(source, file_path)


def compare(source: str, file_path: PurePosixPath | None = None) -> Agreement:
    """Parse source with both parsers and return how they agreed.

    Raises:
        ParsersDisagreeError: One parser accepts the source and the other rejects
            it, or both accept it and produce different programs or diagnostics.
    """
    lark_result = _LARK_PARSER.parse_and_transform(source, file_path=file_path)
    lark_accepts = lark_result.exception is None
    try:
        native_result = native_parse(source, file_path)
    except NotImplementedError:
        return Agreement.NOT_YET_SUPPORTED
    error = native_result.exception
    if isinstance(error, parser_exceptions.ExpectedGlobalDefinition):
        # TODO: Remove this once the parser in parser.rs supports every kind of
        # global definition. Until then, it reports every other kind as
        # ExpectedGlobalDefinition.
        if lark_accepts:
            return Agreement.NOT_YET_SUPPORTED
        return Agreement.BOTH_REJECTED
    if error is not None:
        if lark_accepts:
            raise ParsersDisagreeError(
                f"only the Lark parser accepts {source!r}: {error}"
            ) from error
        return Agreement.BOTH_REJECTED
    if not lark_accepts:
        raise ParsersDisagreeError(
            f"only the parser in parser.rs accepts {source!r}: {lark_result.exception}"
        )
    differences = _differences(
        lark_result.program, native_result.program, "program"
    ) + _differences(lark_result.diagnostics, native_result.diagnostics, "diagnostics")
    if differences:
        raise ParsersDisagreeError(
            f"the parsers produce different results for {source!r}:\n"
            + "\n".join(differences)
        )
    return Agreement.SAME_PROGRAM


def _differences(lark_value: object, native_value: object, path: str) -> list[str]:
    """Return a description of each difference between two values, compared field by field.

    AST nodes compare by identity, so `==` on them never finds two separate
    programs equal.
    """
    if type(lark_value) is not type(native_value):
        return [f"{path}: {lark_value!r} != {native_value!r}"]
    if isinstance(lark_value, msgspec.Struct):
        differences: list[str] = []
        for field in lark_value.__struct_fields__:
            differences.extend(
                _differences(
                    typing.cast("object", getattr(lark_value, field)),
                    typing.cast("object", getattr(native_value, field)),
                    f"{path}.{field}",
                )
            )
        return differences
    if isinstance(lark_value, tuple | list) and isinstance(native_value, tuple | list):
        lark_items = typing.cast("Sequence[object]", lark_value)
        native_items = typing.cast("Sequence[object]", native_value)
        if len(lark_items) != len(native_items):
            return [f"{path}: {len(lark_items)} items != {len(native_items)} items"]
        differences = []
        for index, (lark_item, native_item) in enumerate(
            zip(lark_items, native_items, strict=True)
        ):
            differences.extend(_differences(lark_item, native_item, f"{path}[{index}]"))
        return differences
    if isinstance(lark_value, dict) and isinstance(native_value, dict):
        lark_entries = typing.cast("dict[object, object]", lark_value)
        native_entries = typing.cast("dict[object, object]", native_value)
        if lark_entries.keys() != native_entries.keys():
            return [f"{path}: keys {lark_entries.keys()} != {native_entries.keys()}"]
        differences = []
        for key, lark_item in lark_entries.items():
            differences.extend(
                _differences(lark_item, native_entries[key], f"{path}[{key!r}]")
            )
        return differences
    if lark_value != native_value:
        return [f"{path}: {lark_value!r} != {native_value!r}"]
    return []
