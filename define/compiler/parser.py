"""Parser for Define language statements."""

from __future__ import annotations

import typing
from dataclasses import dataclass, field
from functools import cached_property

from define.compiler import diagnostics as diagnostics_mod
from define.compiler import (
    indentation_validator,
    parser_error_classification,
    parser_exceptions,
    transformer,
)
from define.compiler.lark import lark_standalone

if typing.TYPE_CHECKING:
    import pathlib

    from define.compiler import ast

type ParseException = (
    parser_exceptions.DefineSyntaxError | lark_standalone.UnexpectedInput
)


@dataclass
class ParseResult:
    """Result of parsing Define source code into a Lark parse tree."""

    tree: lark_standalone.Tree[lark_standalone.Token] | None
    diagnostics: list[diagnostics_mod.Diagnostic] = field(default_factory=list)
    exception: ParseException | None = None


@dataclass
class ParseAndTransformResult:
    """Result of parsing Define source code directly into an AST Program."""

    program: ast.Program | None
    diagnostics: list[diagnostics_mod.Diagnostic] = field(default_factory=list)
    exception: ParseException | None = None


class Parser:
    """Parser for Define language source code."""

    _transformer: transformer.DefineTransformer

    def __init__(self):
        """Initialize the parser with the Define grammar."""
        # This needs to be constructed eagerly to avoid race conditions
        # accidentally constructing two different transformers (which have
        # thread-local state).
        self._transformer = transformer.DefineTransformer()

    @cached_property
    def _parse_only_lark(self) -> lark_standalone.Lark:
        """A transformer-less Lark that produces a raw parse tree."""
        return lark_standalone.Lark_StandAlone()

    @cached_property
    def _transforming_lark(self) -> lark_standalone.Lark:
        """A Lark that builds the AST inline as it parses."""
        return lark_standalone.Lark_StandAlone(transformer=self._transformer)

    def parse(
        self, source: str, file_path: pathlib.PurePosixPath | None = None
    ) -> ParseResult:
        """Parse Define source code into a raw parse tree.

        file_path is only used for error messages.
        """
        return self._do_parse(self._parse_only_lark, source, file_path)

    def parse_and_transform(
        self, source: str, file_path: pathlib.PurePosixPath | None = None
    ) -> ParseAndTransformResult:
        """Parse Define source code directly into an AST Program.

        This is significantly faster than parsing and transforming separately.

        file_path is used for both error messages and AST source locations.
        """
        self._transformer.set_file_path(file_path)
        result = self._do_parse(self._transforming_lark, source, file_path)
        # Lark with a transformer attached actually returns ast.Program where lark's
        # signature promises a Tree, so result.tree actually holds the Program.
        program = typing.cast("ast.Program", typing.cast("object", result.tree))
        return ParseAndTransformResult(
            program=program,
            diagnostics=result.diagnostics,
            exception=result.exception,
        )

    def _do_parse(
        self,
        lark: lark_standalone.Lark,
        source: str,
        file_path: pathlib.PurePosixPath | None,
    ) -> ParseResult:
        """Run a Lark instance and collect its tree, diagnostics, and error."""
        tree: lark_standalone.Tree[lark_standalone.Token] | None = None
        exception: ParseException | None = None
        try:
            tree = self._run_lark_parser(lark, source, file_path)
        except (
            lark_standalone.UnexpectedInput,
            parser_exceptions.DefineSyntaxError,
        ) as e:
            exception = e
        diags = self._indentation_diagnostics(source, exception, file_path)
        return ParseResult(tree=tree, diagnostics=diags, exception=exception)

    def _run_lark_parser(
        self,
        lark: lark_standalone.Lark,
        source: str,
        file_path: pathlib.PurePosixPath | None,
    ) -> lark_standalone.Tree[lark_standalone.Token]:
        """Run the actual Lark parser, raising DefineSyntaxError exceptions."""
        try:
            return lark.parse(source)
        except lark_standalone.UnexpectedCharacters as e:
            parser_error_classification.raise_character_error(e, source, file_path)
            raise
        except lark_standalone.UnexpectedToken as e:
            parser_error_classification.raise_token_error(e, source, file_path)
            raise

    def _indentation_diagnostics(
        self,
        source: str,
        exception: ParseException | None,
        file_path: pathlib.PurePosixPath | None,
    ) -> list[diagnostics_mod.Diagnostic]:
        stop_before_line = (
            exception.line if exception is not None else None  # pragma: no mutate
        )
        return indentation_validator.validate_indentation(
            source, stop_before_line, file_path=file_path
        )
