"""Syntax validation for Define Configuration Language (DCL) files."""

from __future__ import annotations

from functools import cached_property
from typing import TYPE_CHECKING

from defcl.python import exceptions as dcl_exceptions
from defcl.python.lark import lark_standalone

if TYPE_CHECKING:
    import os

_TOKEN_ERROR_EXAMPLES: dict[type[dcl_exceptions.DclTokenError], list[str]] = {
    dcl_exceptions.MissingColonError: [
        'a: {\n    b "x"\n}',
        "a {\n    b: 1\n}",
    ],
    dcl_exceptions.BooleanNotSupportedError: [
        "a: {\n    b: true\n}",
        "a: {\n    b: false\n}",
    ],
    dcl_exceptions.InvalidEnumCaseError: [
        "a: {\n    b: active\n}",
        "a: {\n    b: Active\n}",
    ],
    dcl_exceptions.InvalidFieldNameTokenError: [
        "a: {\n    Foo: 1\n}",
        "a: {\n    1a: 1\n}",
    ],
    dcl_exceptions.InvalidNumberFormatError: [
        "a: {\n    b: 0x1A\n}",
        "a: {\n    b: 007\n}",
        "a: {\n    b: 1e5\n}",
        "a: {\n    b: 1.5e-2\n}",
        "a: {\n    b: 1.5f\n}",
        "a: {\n    b: 1.5F\n}",
    ],
    dcl_exceptions.InvalidSeparatorError: [
        "a: {\n    b: 1,\n}",
    ],
    dcl_exceptions.ScalarAtToplevelError: [
        'a: "value"',
        "a: 1",
    ],
}

_CHAR_ERROR_EXAMPLES: dict[type[dcl_exceptions.DclCharError], list[str]] = {
    dcl_exceptions.InvalidFieldNameError: [
        "a: {\n    _b: 1\n}",
        "a: {\n    a__b: 1\n}",
        "a: {\n    a_: 1\n}",
        "a: {\n    a_1: 1\n}",
        "a: {\n    a-b: 1\n}",
        "a: {\n    a.b: 1\n}",
    ],
    dcl_exceptions.SingleQuotesNotAllowedError: [
        "a: {\n    b: 'x'\n}",
    ],
    dcl_exceptions.UnterminatedStringError: [
        'a: {\n    b: "hello\nworld"\n}',
    ],
    dcl_exceptions.InvalidNumberFormatCharError: [
        "a: {\n    b: .5\n}",
        "a: {\n    b: 1.\n}",
        "a: {\n    b: +5\n}",
        "a: {\n    b: - 5\n}",
    ],
    dcl_exceptions.InvalidSeparatorCharError: [
        "a: {\n    b: 1;\n}",
    ],
    dcl_exceptions.TabNotAllowedError: [
        "a: {\n\tb: 1\n}",
    ],
    dcl_exceptions.CarriageReturnNotAllowedError: [
        "a: {\r\n    b: 1\n}",
    ],
    dcl_exceptions.AngleBracketsNotAllowedError: [
        "a: <\n    b: 1\n>",
    ],
    dcl_exceptions.ByteOrderMarkError: [
        "\ufeffa: {\n    b: 1\n}",
    ],
}

_CHAR_ERRORS: dict[str, type[dcl_exceptions.DclCharError]] = {
    "'": dcl_exceptions.SingleQuotesNotAllowedError,
    "\t": dcl_exceptions.TabNotAllowedError,
    "\r": dcl_exceptions.CarriageReturnNotAllowedError,
    "<": dcl_exceptions.AngleBracketsNotAllowedError,
    ";": dcl_exceptions.InvalidSeparatorCharError,
    '"': dcl_exceptions.UnterminatedStringError,
    "\ufeff": dcl_exceptions.ByteOrderMarkError,
    "+": dcl_exceptions.InvalidNumberFormatCharError,
    "_": dcl_exceptions.InvalidFieldNameError,
}

_VALUE_POSITION_CHAR_ERRORS: dict[str, type[dcl_exceptions.DclCharError]] = {
    "-": dcl_exceptions.InvalidNumberFormatCharError,
    ".": dcl_exceptions.InvalidNumberFormatCharError,
}

_FIELD_POSITION_CHAR_ERRORS: dict[str, type[dcl_exceptions.DclCharError]] = {
    "-": dcl_exceptions.InvalidFieldNameError,
    ".": dcl_exceptions.InvalidFieldNameError,
}


class Parser:
    """Parser for DCL files using Lark."""

    @cached_property
    def _parser(self) -> lark_standalone.Lark:
        return lark_standalone.Lark_StandAlone()

    def _classify_char_error(
        self, e: lark_standalone.UnexpectedCharacters
    ) -> type[dcl_exceptions.DclCharError] | None:
        """Classify a character error using direct lookup and example matching."""
        char_class = _CHAR_ERRORS.get(e.char)
        if char_class is not None:
            return char_class

        if e.char in _VALUE_POSITION_CHAR_ERRORS:
            prev_token = e.token_history[-1] if e.token_history else None
            if prev_token is not None and prev_token.type in (
                "COLON",
                "INTEGER",
                "FLOAT",
            ):
                return _VALUE_POSITION_CHAR_ERRORS[e.char]
            return _FIELD_POSITION_CHAR_ERRORS[e.char]

        return e.match_examples(
            self._parser.parse,
            _CHAR_ERROR_EXAMPLES,
        )

    def _classify_token_error(
        self, e: lark_standalone.UnexpectedToken
    ) -> type[dcl_exceptions.DclTokenError] | None:
        """Classify a token error using pattern matching and example matching."""
        if e.token.type == "RBRACE" and e.token_history:
            prev = e.token_history[-1]
            if prev.type == "FIELD_NAME":
                val = str(prev)
                if val in ("f", "d", "l") or (val[0] == "e" and val[1:].isdigit()):
                    return dcl_exceptions.InvalidNumberFormatError

        return e.match_examples(
            self._parser.parse,
            _TOKEN_ERROR_EXAMPLES,
        )

    def parse(
        self, text: str, path_name: str | os.PathLike[str] | None = None
    ) -> lark_standalone.Tree[lark_standalone.Token]:
        """Parse DCL text and return the parse tree.

        path_name is only used for error messages.
        """
        try:
            tree = self._parser.parse(text)
            if text and text[-1] != "\n":
                raise dcl_exceptions.MissingTrailingNewlineError(path_name)
        except lark_standalone.UnexpectedCharacters as e:
            exc_class = self._classify_char_error(e)
            if exc_class is not None:
                raise exc_class(
                    e.get_context(text), e.line, e.column, e.char, path_name
                ) from e
            raise
        except lark_standalone.UnexpectedToken as e:
            exc_class = self._classify_token_error(e)
            if exc_class is not None:
                raise exc_class(
                    e.get_context(text), e.line, e.column, e.token, path_name
                ) from e
            raise
        return tree

    def parse_file(
        self, path: str | os.PathLike[str]
    ) -> lark_standalone.Tree[lark_standalone.Token]:
        """Parse a DCL file and return the parse tree."""
        with open(path, encoding="utf-8", newline="") as f:
            return self.parse(f.read(), path_name=path)
