# pyright: reportUnusedCallResult=false
"""Indentation diagnostic parser tests.

Follow parser test authoring rules in parser_tests/AGENTS.md.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from define.compiler import ast
from define.compiler.errors import diagnostics, parser_exceptions

if TYPE_CHECKING:
    from define.compiler.parsing.parser_tests.conftest import (
        NativeParseWithDiagnostics,
    )


def test_over_indented_requirement(
    native_parse_with_diagnostics: NativeParseWithDiagnostics,
):
    result = native_parse_with_diagnostics(
        "define the potential position<mv:define-lang.org:parser:/path> {\n"
        + "    it may only contain particles where {\n"
        + "          it has the position</child>.\n"
        + "    }\n"
        + "}\n"
    )
    assert result.exception is None
    assert result.program is not None
    assert result.diagnostics == [
        diagnostics.IncorrectIndentationDiagnostic(
            location=ast.SourceLocation(line=3, column=1, end_line=3, end_column=10),
            expected_indent=8,
            actual_indent=10,
        )
    ]


def test_under_indented_requirement(
    native_parse_with_diagnostics: NativeParseWithDiagnostics,
):
    result = native_parse_with_diagnostics(
        "define the potential position<mv:define-lang.org:parser:/path> {\n"
        + "    it may only contain particles where {\n"
        + "      it has the position</child>.\n"
        + "    }\n"
        + "}\n"
    )
    assert result.exception is None
    assert result.program is not None
    assert result.diagnostics == [
        diagnostics.IncorrectIndentationDiagnostic(
            location=ast.SourceLocation(line=3, column=1, end_line=3, end_column=6),
            expected_indent=8,
            actual_indent=6,
        )
    ]


def test_block_contents_are_indented_from_their_opener_as_written(
    native_parse_with_diagnostics: NativeParseWithDiagnostics,
):
    result = native_parse_with_diagnostics(
        "define the potential position<mv:define-lang.org:parser:/path> {\n"
        + "  it may only contain particles where {\n"
        + "        it has the position</child>.\n"
        + "    }\n"
        + "}\n"
    )
    assert result.exception is None
    assert result.program is not None
    assert result.diagnostics == [
        diagnostics.IncorrectIndentationDiagnostic(
            location=ast.SourceLocation(line=2, column=1, end_line=2, end_column=2),
            expected_indent=4,
            actual_indent=2,
        ),
        diagnostics.IncorrectIndentationDiagnostic(
            location=ast.SourceLocation(line=3, column=1, end_line=3, end_column=8),
            expected_indent=6,
            actual_indent=8,
        ),
        diagnostics.IncorrectIndentationDiagnostic(
            location=ast.SourceLocation(line=4, column=1, end_line=4, end_column=4),
            expected_indent=2,
            actual_indent=4,
        ),
    ]


def test_under_indented_constraint_block_close(
    native_parse_with_diagnostics: NativeParseWithDiagnostics,
):
    result = native_parse_with_diagnostics(
        "define the potential position<mv:define-lang.org:parser:/path> {\n"
        + "    it may only contain particles where {\n"
        + "        it has the position</child>.\n"
        + "  }\n"
        + "}\n"
    )
    assert result.exception is None
    assert result.program is not None
    assert result.diagnostics == [
        diagnostics.IncorrectIndentationDiagnostic(
            location=ast.SourceLocation(line=4, column=1, end_line=4, end_column=2),
            expected_indent=4,
            actual_indent=2,
        )
    ]


def test_indented_definition_block_close(
    native_parse_with_diagnostics: NativeParseWithDiagnostics,
):
    result = native_parse_with_diagnostics(
        "define the potential position<mv:define-lang.org:parser:/path> {\n"
        + "    it may only contain particles where {\n"
        + "        it has the position</child>.\n"
        + "    }\n"
        + " }\n"
    )
    assert result.exception is None
    assert result.program is not None
    assert result.diagnostics == [
        diagnostics.IncorrectIndentationDiagnostic(
            location=ast.SourceLocation(line=5, column=1, end_line=5, end_column=1),
            expected_indent=0,
            actual_indent=1,
        )
    ]


def test_under_indented_comment_in_block(
    native_parse_with_diagnostics: NativeParseWithDiagnostics,
):
    result = native_parse_with_diagnostics(
        "define the potential position<mv:define-lang.org:parser:/path> {\n"
        + "   # note\n"
        + "    it may only contain particles where {\n"
        + "        it has the position</child>.\n"
        + "    }\n"
        + "}\n"
    )
    assert result.exception is None
    assert result.program is not None
    assert result.diagnostics == [
        diagnostics.IncorrectIndentationDiagnostic(
            location=ast.SourceLocation(line=2, column=1, end_line=2, end_column=3),
            expected_indent=4,
            actual_indent=3,
        )
    ]


def test_unindented_comment_in_block(
    native_parse_with_diagnostics: NativeParseWithDiagnostics,
):
    result = native_parse_with_diagnostics(
        "define the potential position<mv:define-lang.org:parser:/path> {\n"
        + "# note\n"
        + "    it may only contain particles where {\n"
        + "        it has the position</child>.\n"
        + "    }\n"
        + "}\n"
    )
    assert result.exception is None
    assert result.program is not None
    assert result.diagnostics == [
        diagnostics.IncorrectIndentationDiagnostic(
            location=ast.SourceLocation(line=2, column=1, end_line=2, end_column=1),
            expected_indent=4,
            actual_indent=0,
        )
    ]


def test_under_indented_non_ascii_comment_in_block(
    native_parse_with_diagnostics: NativeParseWithDiagnostics,
):
    result = native_parse_with_diagnostics(
        "define the potential position<mv:define-lang.org:parser:/path> {\n"
        + "   # café\n"
        + "    it may only contain particles where {\n"
        + "        it has the position</child>.\n"
        + "    }\n"
        + "}\n"
    )
    assert result.exception is None
    assert result.program is not None
    assert result.diagnostics == [
        diagnostics.IncorrectIndentationDiagnostic(
            location=ast.SourceLocation(line=2, column=1, end_line=2, end_column=3),
            expected_indent=4,
            actual_indent=3,
        )
    ]


def test_indented_top_level_comment(
    native_parse_with_diagnostics: NativeParseWithDiagnostics,
):
    result = native_parse_with_diagnostics(
        "  # note\ndefine the potential position<mv:define-lang.org:parser:/path>.\n"
    )
    assert result.exception is None
    assert result.program is not None
    assert result.diagnostics == [
        diagnostics.IncorrectIndentationDiagnostic(
            location=ast.SourceLocation(line=1, column=1, end_line=1, end_column=2),
            expected_indent=0,
            actual_indent=2,
        )
    ]


def test_indentation_diagnostic_before_syntax_error(
    native_parse_with_diagnostics: NativeParseWithDiagnostics,
):
    result = native_parse_with_diagnostics(
        "define the potential position<mv:define-lang.org:parser:/path> {\n"
        + "  it may only contain particles where {\n"
        + "      it has the position</child>\n"
        + "  }\n"
        + "}\n"
    )
    assert result.program is None
    assert isinstance(result.exception, parser_exceptions.MissingTerminator)
    assert result.exception.location == ast.SourceLocation(
        line=3, column=34, end_line=3, end_column=34
    )
    assert result.diagnostics == [
        diagnostics.IncorrectIndentationDiagnostic(
            location=ast.SourceLocation(line=2, column=1, end_line=2, end_column=2),
            expected_indent=4,
            actual_indent=2,
        )
    ]
