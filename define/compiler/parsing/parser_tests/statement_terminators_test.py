# pyright: reportUnusedCallResult=false
"""Statement terminator parser tests.

Follow parser test authoring rules in parser_tests/AGENTS.md.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from define.compiler import ast
from define.compiler.errors import diagnostics, parser_exceptions

if TYPE_CHECKING:
    from define.compiler.parsing.parser_tests.conftest import (
        Parse,
        ParseWithDiagnostics,
    )


def test_valid_terminator(parse: Parse):
    program = parse("define the potential position<mv:define-lang.org:parser:/path>.\n")
    [definition] = program.definitions
    assert isinstance(definition, ast.PositionDefinition)
    assert definition.location == ast.SourceLocation(
        line=1, column=1, end_line=1, end_column=63
    )
    assert definition.quality_assignment_block is None


def test_missing_terminator(parse: Parse):
    with pytest.raises(parser_exceptions.MissingTerminatorOrBrace) as exc_info:
        parse("define the potential position<standard:/path>\n")
    assert exc_info.value.location.line == 1
    assert exc_info.value.location.end_line == 1
    assert exc_info.value.location.column == 46
    assert exc_info.value.location.end_column == 46


def test_missing_newline_after_terminator(parse: Parse):
    with pytest.raises(parser_exceptions.MissingNewlineAtEof) as exc_info:
        parse("define the potential position<standard:/path>.")
    assert exc_info.value.location.line == 1
    assert exc_info.value.location.end_line == 1
    assert exc_info.value.location.column == 47
    assert exc_info.value.location.end_column == 47


def test_missing_newline_after_last_definition(parse: Parse):
    with pytest.raises(parser_exceptions.MissingNewlineAtEof) as exc_info:
        parse(
            "define the potential position<mv:define-lang.org:parser:/first>.\n"
            + "define the potential position<mv:define-lang.org:parser:/second>."
        )
    assert exc_info.value.location.line == 2
    assert exc_info.value.location.column == 66
    assert exc_info.value.location.end_line == 2
    assert exc_info.value.location.end_column == 66


def test_missing_newline_between_global_definitions(parse: Parse):
    with pytest.raises(parser_exceptions.MissingNewlineAfterTerminator) as exc_info:
        parse(
            "define the potential position<mv:define-lang.org:parser:/path>.define the potential action<mv:define-lang.org:parser:/path>.\n"
        )
    assert exc_info.value.location.line == 1
    assert exc_info.value.location.column == 64
    assert exc_info.value.location.end_line == 1
    assert exc_info.value.location.end_column == 64


def test_double_terminator(parse: Parse):
    with pytest.raises(parser_exceptions.MissingNewlineAfterTerminator) as exc_info:
        parse("define the potential position<mv:define-lang.org:parser:/path>..\n")
    assert exc_info.value.location.line == 1
    assert exc_info.value.location.end_line == 1
    assert exc_info.value.location.column == 64
    assert exc_info.value.location.end_column == 64


def test_comment_directly_after_terminator(parse: Parse):
    with pytest.raises(parser_exceptions.MissingSpaceBeforeComment) as exc_info:
        parse(
            "define the potential position<mv:define-lang.org:parser:/path>.# comment\n"
        )
    assert exc_info.value.location.line == 1
    assert exc_info.value.location.column == 63
    assert exc_info.value.location.end_line == 1
    assert exc_info.value.location.end_column == 64


def test_letter_after_terminator(parse: Parse):
    with pytest.raises(parser_exceptions.MissingNewlineAfterTerminator) as exc_info:
        parse("define the potential position<mv:define-lang.org:parser:/path>.x\n")
    assert exc_info.value.location.line == 1
    assert exc_info.value.location.column == 64
    assert exc_info.value.location.end_line == 1
    assert exc_info.value.location.end_column == 64


def test_spaces_and_letter_after_terminator(parse: Parse):
    with pytest.raises(parser_exceptions.MissingNewlineAfterTerminator) as exc_info:
        parse("define the potential position<mv:define-lang.org:parser:/path>.  x\n")
    assert exc_info.value.location.line == 1
    assert exc_info.value.location.column == 64
    assert exc_info.value.location.end_line == 1
    assert exc_info.value.location.end_column == 64


def test_non_ascii_character_after_terminator(parse: Parse):
    with pytest.raises(parser_exceptions.MissingNewlineAfterTerminator) as exc_info:
        parse("define the potential position<mv:define-lang.org:parser:/path>.é\n")
    assert exc_info.value.location.line == 1
    assert exc_info.value.location.column == 64
    assert exc_info.value.location.end_line == 1
    assert exc_info.value.location.end_column == 64


def test_space_before_terminator(parse: Parse):
    with pytest.raises(parser_exceptions.MissingCloseAngleBracket) as exc_info:
        parse("define the potential position<mv:my.domain.com:my_lib:/some_name .\n")
    assert exc_info.value.location.line == 1
    assert exc_info.value.location.column == 67
    assert exc_info.value.location.end_line == 1
    assert exc_info.value.location.end_column == 67
    assert exc_info.value.name == "mv:my.domain.com:my_lib:/some_name ."


def test_trailing_space_before_newline(parse_with_diagnostics: ParseWithDiagnostics):
    result = parse_with_diagnostics("define the potential position<standard:/path>. \n")
    assert result.exception is None
    assert result.program is not None
    assert result.diagnostics == [
        diagnostics.TrailingWhitespaceDiagnostic(
            location=ast.SourceLocation(
                line=1,
                column=47,
                end_line=1,
                end_column=47,
            )
        )
    ]


def test_several_trailing_spaces_before_newline(
    parse_with_diagnostics: ParseWithDiagnostics,
):
    result = parse_with_diagnostics(
        "define the potential position<mv:define-lang.org:parser:/path>.   \n"
    )
    assert result.exception is None
    assert result.program is not None
    assert result.diagnostics == [
        diagnostics.TrailingWhitespaceDiagnostic(
            location=ast.SourceLocation(
                line=1,
                column=64,
                end_line=1,
                end_column=66,
            )
        )
    ]


def test_trailing_space_at_end_of_source(parse_with_diagnostics: ParseWithDiagnostics):
    result = parse_with_diagnostics(
        "define the potential position<mv:define-lang.org:parser:/path>. "
    )
    assert result.diagnostics == [
        diagnostics.TrailingWhitespaceDiagnostic(
            location=ast.SourceLocation(line=1, column=64, end_line=1, end_column=64)
        ),
    ]
    assert isinstance(result.exception, parser_exceptions.MissingNewlineAtEof)
    assert result.exception.location == ast.SourceLocation(
        line=1, column=65, end_line=1, end_column=65
    )


def test_missing_terminator_after_typed_reference_in_quality_assignment(
    parse: Parse,
):
    with pytest.raises(parser_exceptions.MissingTerminator) as exc_info:
        parse(
            "define the potential position<my_lib:/hello/hello>.\n"
            + "define the potential position<my_lib:/sub/sub> {\n"
            + "    it may only contain particles where {\n"
            + "        it has the action<std:/path/sub>\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.location.line == 4
    assert exc_info.value.location.column == 41
    assert exc_info.value.location.end_line == 4
    assert exc_info.value.location.end_column == 41


def test_text_where_position_definition_terminator_belongs(parse: Parse):
    with pytest.raises(parser_exceptions.MissingTerminatorOrBrace) as exc_info:
        parse("define the potential position<mv:define-lang.org:parser:/path> x\n")
    assert exc_info.value.location.line == 1
    assert exc_info.value.location.column == 63
    assert exc_info.value.location.end_line == 1
    assert exc_info.value.location.end_column == 63


def test_text_after_encoding_quality_assignment_terminator(parse: Parse):
    with pytest.raises(parser_exceptions.MissingNewlineAfterTerminator) as error:
        _ = parse(
            "define the potential literal<mv:define-lang.org:parser:/decimal> {\n"
            + "    it has the encoding</decimal>.x\n"
            + "}\n"
        )
    assert error.value.location.line == 2
    assert error.value.location.column == 35
    assert error.value.location.end_line == 2
    assert error.value.location.end_column == 35


def test_text_after_value_definition_terminator(parse: Parse):
    with pytest.raises(parser_exceptions.MissingNewlineAfterTerminator) as error:
        _ = parse("define the potential value<standard:/number/natural>.x\n")
    assert error.value.location.line == 1
    assert error.value.location.column == 54
    assert error.value.location.end_line == 1
    assert error.value.location.end_column == 54


def test_text_after_value_setting_literal_terminator(parse: Parse):
    with pytest.raises(parser_exceptions.MissingNewlineAfterTerminator) as error:
        parse(
            "define the potential action<mv:define-lang.org:parser:/set_value> {\n"
            + "    it happens when {\n"
            + "        this particle is created.\n"
            + "    } and it does {\n"
            + '        set the value of position<dest> to literal</text>"a".x\n'
            + "    }\n}\n"
        )
    assert error.value.location.line == 5
    assert error.value.location.column == 62
    assert error.value.location.end_line == 5
    assert error.value.location.end_column == 62


def test_text_after_operation_execution_terminator(parse: Parse):
    with pytest.raises(parser_exceptions.MissingNewlineAfterTerminator) as error:
        parse(
            "define the operation<mv:define-lang.org:parser:/add> {\n"
            + "    it does {\n"
            + "        execute the operation</other>.x\n"
            + "    }\n"
            + "}\n"
        )
    assert error.value.location.line == 3
    assert error.value.location.column == 39
    assert error.value.location.end_line == 3
    assert error.value.location.end_column == 39
