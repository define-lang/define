"""Parser for Define language statements."""

from __future__ import annotations

import typing
from dataclasses import dataclass, field

from define.compiler import diagnostics as diagnostics_mod
from define.compiler import (
    indentation_validator,
    parser_error_classification,
    parser_exceptions,
)
from define.compiler.lark import lark_standalone

if typing.TYPE_CHECKING:
    import pathlib

UnexpectedInput = lark_standalone.UnexpectedInput

type ParseException = (
    parser_exceptions.DefineSyntaxError | lark_standalone.UnexpectedInput
)


@dataclass
class ParseResult:
    """Result of parsing Define source code."""

    tree: lark_standalone.Tree[lark_standalone.Token] | None
    diagnostics: list[diagnostics_mod.Diagnostic] = field(default_factory=list)
    exception: ParseException | None = None


class Parser:
    """Parser for Define language source code."""

    _lark: lark_standalone.Lark

    def __init__(self):
        """Initialize the parser with the Define grammar."""
        self._lark = lark_standalone.Lark_StandAlone()

    def parse(
        self, source: str, file_path: pathlib.PurePosixPath | None = None
    ) -> ParseResult:
        """Parse Define source code and return a ParseResult.

        file_path is only used for error messages.
        """
        stop_before_line: int | None = None
        exception: ParseException | None = None
        tree: lark_standalone.Tree[lark_standalone.Token] | None = None

        try:
            tree = self._do_parse(source, file_path)
        except lark_standalone.UnexpectedInput as e:  # pragma: no mutate
            stop_before_line = e.line  # pragma: no mutate
            exception = e  # pragma: no mutate
        except parser_exceptions.DefineSyntaxError as e:
            stop_before_line = e.line
            exception = e

        diags = indentation_validator.validate_indentation(
            source, stop_before_line, file_path=file_path
        )
        return ParseResult(tree=tree, diagnostics=diags, exception=exception)

    def _do_parse(
        self, source: str, file_path: pathlib.PurePosixPath | None
    ) -> lark_standalone.Tree[lark_standalone.Token]:
        """Run the Lark parser with error classification."""
        try:
            return self._lark.parse(source)
        except lark_standalone.UnexpectedToken as e:
            parser_error_classification.raise_token_error(e, source, file_path)
            raise
