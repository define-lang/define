# pyright: reportUnusedCallResult=false
"""Literal source parser tests for Value Setting Statements."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from define.compiler import ast, name_types
from define.compiler.errors import diagnostics, parser_exceptions

if TYPE_CHECKING:
    from define.compiler.parsing.parser_tests.conftest import (
        Parse,
        ParseWithDiagnostics,
    )


_ACTION_PREFIX = (
    "define the potential action<mv:define-lang.org:parser:/set_value> {\n"
    + "    it happens when {\n"
    + "        this particle is created.\n"
    + "    } and it does {\n"
)


def _only_literal(program: ast.Program) -> ast.Literal:
    [definition] = program.definitions
    assert isinstance(definition, ast.ActionDefinition)
    [statement] = definition.action_statements.statements
    assert isinstance(statement, ast.ValueSettingStatement)
    assert isinstance(statement.source, ast.Literal)
    return statement.source


def test_literal_source(parse: Parse):
    literal = _only_literal(
        parse(
            _ACTION_PREFIX
            + '        set the value of position<dest> to literal</decimal>"123".\n'
            + "    }\n}\n"
        )
    )
    assert literal.content == "123"
    potential_literal = literal.potential_literal
    assert potential_literal.name_type == name_types.NameType.LITERAL
    assert potential_literal.name_content.fqun is None
    assert potential_literal.name_content.path.name == "/decimal"
    assert potential_literal.location == ast.SourceLocation(
        line=5, column=44, end_line=5, end_column=60
    )
    assert literal.location == ast.SourceLocation(
        line=5, column=44, end_line=5, end_column=65
    )


def test_literal_full_global_name(parse: Parse):
    literal = _only_literal(
        parse(
            _ACTION_PREFIX
            + '        set the value of position<dest>::position<child> to literal<mv:define-lang.org:parser:/text>"hello".\n'
            + "    }\n}\n"
        )
    )
    assert literal.content == "hello"
    fqun = literal.potential_literal.name_content.fqun
    assert fqun is not None
    assert fqun.multiverse is not None
    assert fqun.multiverse.name == "mv"
    assert fqun.authority is not None
    assert fqun.authority.name == "define-lang.org"
    assert fqun.universe.name == "parser"
    assert literal.potential_literal.name_content.path.name == "/text"
    assert literal.location == ast.SourceLocation(
        line=5, column=61, end_line=5, end_column=107
    )


def test_literal_empty_content(parse: Parse):
    literal = _only_literal(
        parse(
            _ACTION_PREFIX
            + '        set the value of position<dest> to literal</text>"".\n'
            + "    }\n}\n"
        )
    )
    assert literal.content == ""
    assert literal.location == ast.SourceLocation(
        line=5, column=44, end_line=5, end_column=59
    )


def test_literal_spaces_comments_unicode_and_escapes(parse: Parse):
    literal = _only_literal(
        parse(
            _ACTION_PREFIX
            + '        set the value of position<dest> to literal</text>" # Hello 世界 < {} . > : \\" \\\\ \\n ". # comment\n'
            + "    }\n}\n"
        )
    )
    assert literal.content == ' # Hello 世界 < {} . > : " \\ \n '
    assert literal.location == ast.SourceLocation(
        line=5, column=44, end_line=5, end_column=91
    )


def test_literal_starts_with_comment_character(parse: Parse):
    literal = _only_literal(
        parse(
            _ACTION_PREFIX
            + '        set the value of position<dest> to literal</text>"#content". # comment\n'
            + "    }\n}\n"
        )
    )
    assert literal.content == "#content"
    assert literal.location == ast.SourceLocation(
        line=5, column=44, end_line=5, end_column=67
    )


def test_literal_brace_before_comment_character(parse: Parse):
    program = parse(
        _ACTION_PREFIX
        + '        set the value of position<dest> to literal</text>" {#content".\n'
        + '        set the value of position<dest> to literal</text>"next".\n'
        + "    }\n}\n"
    )
    [definition] = program.definitions
    assert isinstance(definition, ast.ActionDefinition)
    [first, second] = definition.action_statements.statements
    assert isinstance(first, ast.ValueSettingStatement)
    assert isinstance(first.source, ast.Literal)
    assert first.source.content == " {#content"
    assert isinstance(second, ast.ValueSettingStatement)
    assert isinstance(second.source, ast.Literal)
    assert second.source.content == "next"


def test_comment_after_literal_with_escaped_quote_brace_and_hash(
    parse: Parse,
):
    literal = _only_literal(
        parse(
            _ACTION_PREFIX
            + '        set the value of position<dest> to literal</text>"a\\" {#b\\\\". # comment\n'
            + "    }\n}\n"
        )
    )
    assert literal.content == 'a" {#b\\'


def test_comment_after_literal_containing_angle_brackets(parse: Parse):
    literal = _only_literal(
        parse(
            _ACTION_PREFIX
            + '        set the value of position<dest> to literal</text>"< # >". # comment\n'
            + "    }\n}\n"
        )
    )
    assert literal.content == "< # >"


def test_literal_unknown_escape_is_invalid(parse: Parse):
    with pytest.raises(parser_exceptions.InvalidLiteralEscape) as error:
        parse(
            _ACTION_PREFIX
            + '        set the value of position<dest> to literal</text>"bad\\t".\n'
            + "    }\n}\n"
        )
    assert error.value.char == "t"
    assert error.value.location.line == 5
    assert error.value.location.column == 63
    assert error.value.location.end_line == 5
    assert error.value.location.end_column == 63


def test_literal_unknown_escape_of_non_ascii_character(parse: Parse):
    with pytest.raises(parser_exceptions.InvalidLiteralEscape) as error:
        parse(
            _ACTION_PREFIX
            + '        set the value of position<dest> to literal</text>"aé\\é".\n'
            + "    }\n}\n"
        )
    assert error.value.char == "é"
    assert error.value.location.line == 5
    assert error.value.location.column == 62
    assert error.value.location.end_line == 5
    assert error.value.location.end_column == 62


def test_literal_newline(parse: Parse):
    with pytest.raises(parser_exceptions.MissingLiteralContentEnd) as error:
        parse(
            _ACTION_PREFIX
            + '        set the value of position<dest> to literal</text>"a\nb".\n'
            + "    }\n}\n"
        )
    assert error.value.location.line == 5
    assert error.value.location.column == 60
    assert error.value.location.end_line == 5
    assert error.value.location.end_column == 60


def test_literal_target_is_invalid(parse: Parse):
    with pytest.raises(parser_exceptions.ExpectedPositionOrAction) as error:
        parse(
            _ACTION_PREFIX
            + '        set the value of literal</text>"a" to position<dest>.\n'
            + "    }\n}\n"
        )
    assert error.value.location.line == 5
    assert error.value.location.column == 26
    assert error.value.location.end_line == 5
    assert error.value.location.end_column == 32


def test_literal_missing_global_name(parse: Parse):
    with pytest.raises(parser_exceptions.InvalidGlobalName) as error:
        parse(
            _ACTION_PREFIX
            + '        set the value of position<dest> to literal<text>"abc".\n'
            + "    }\n}\n"
        )
    assert error.value.location.line == 5
    assert error.value.location.column == 52
    assert error.value.location.end_line == 5
    assert error.value.location.end_column == 55


def test_literal_empty_name(parse: Parse):
    with pytest.raises(parser_exceptions.EmptyName) as error:
        parse(
            _ACTION_PREFIX
            + '        set the value of position<dest> to literal<>"abc".\n'
            + "    }\n}\n"
        )
    assert error.value.location.line == 5
    assert error.value.location.column == 52
    assert error.value.location.end_line == 5
    assert error.value.location.end_column == 52


def test_literal_missing_open_angle_bracket(parse: Parse):
    with pytest.raises(parser_exceptions.MissingOpenAngleBracket) as error:
        parse(
            _ACTION_PREFIX
            + '        set the value of position<dest> to literal/text>"abc".\n'
            + "    }\n}\n"
        )
    assert error.value.location.line == 5
    assert error.value.location.column == 51
    assert error.value.location.end_line == 5
    assert error.value.location.end_column == 51


def test_literal_missing_close_angle_bracket(parse: Parse):
    with pytest.raises(parser_exceptions.MissingCloseAngleBracket) as error:
        parse(
            _ACTION_PREFIX
            + '        set the value of position<dest> to literal</text"abc".\n'
            + "    }\n}\n"
        )
    assert error.value.location.line == 5
    assert error.value.location.column == 63
    assert error.value.location.end_line == 5
    assert error.value.location.end_column == 63
    assert error.value.name == '/text"abc".'


def test_literal_missing_open_quote(parse: Parse):
    with pytest.raises(parser_exceptions.MissingLiteralContentStart) as error:
        parse(
            _ACTION_PREFIX
            + "        set the value of position<dest> to literal</text>.\n"
            + "    }\n}\n"
        )
    assert error.value.location.line == 5
    assert error.value.location.column == 58
    assert error.value.location.end_line == 5
    assert error.value.location.end_column == 58


def test_literal_unquoted_content(parse: Parse):
    with pytest.raises(parser_exceptions.MissingLiteralContentStart) as error:
        parse(
            _ACTION_PREFIX
            + "        set the value of position<dest> to literal</foo>5.\n"
            + "    }\n}\n"
        )
    assert error.value.location.line == 5
    assert error.value.location.column == 57
    assert error.value.location.end_line == 5
    assert error.value.location.end_column == 57


def test_literal_missing_close_quote(parse: Parse):
    with pytest.raises(parser_exceptions.MissingLiteralContentEnd) as error:
        parse(
            _ACTION_PREFIX
            + '        set the value of position<dest> to literal</text>"abc.\n'
            + "    }\n}\n"
        )
    assert error.value.location.line == 5
    assert error.value.location.column == 63
    assert error.value.location.end_line == 5
    assert error.value.location.end_column == 63


def test_literal_content_starting_with_slash(parse: Parse):
    literal = _only_literal(
        parse(
            _ACTION_PREFIX
            + '        set the value of position<dest> to literal</text>"/0".\n'
            + "    }\n}\n"
        )
    )
    assert literal.content == "/0"


def test_literal_cannot_be_child_of_position(parse: Parse):
    with pytest.raises(parser_exceptions.ExpectedPositionOrAction) as error:
        parse(
            _ACTION_PREFIX
            + '        set the value of position<dest> to position<parent>::literal</text>"abc".\n'
            + "    }\n}\n"
        )
    assert error.value.location.line == 5
    assert error.value.location.column == 62
    assert error.value.location.end_line == 5
    assert error.value.location.end_column == 68


def test_literal_cannot_start_position_reference(parse: Parse):
    with pytest.raises(parser_exceptions.MissingTerminator) as error:
        parse(
            _ACTION_PREFIX
            + '        set the value of position<dest> to literal</text>"a"::position<child>.\n'
            + "    }\n}\n"
        )
    assert error.value.location.line == 5
    assert error.value.location.column == 61
    assert error.value.location.end_line == 5
    assert error.value.location.end_column == 61


def test_literal_without_terminator_gets_a_diagnostic(
    parse_with_diagnostics: ParseWithDiagnostics,
):
    result = parse_with_diagnostics(
        _ACTION_PREFIX
        + '        set the value of position<dest> to literal</text>"a"\n'
        + "    }\n}\n"
    )
    assert result.exception is None
    assert result.diagnostics == [
        diagnostics.MissingTerminatorAtEndOfLineDiagnostic(
            location=ast.SourceLocation(line=5, column=61, end_line=5, end_column=61)
        )
    ]
    assert result.program is not None
    [definition] = result.program.definitions
    assert isinstance(definition, ast.ActionDefinition)
    [statement] = definition.action_statements.statements
    assert isinstance(statement, ast.ValueSettingStatement)
    assert statement.location == ast.SourceLocation(
        line=5, column=9, end_line=5, end_column=60
    )


def test_literal_old_syntax_is_invalid(parse: Parse):
    with pytest.raises(parser_exceptions.MissingLiteralContentStart) as error:
        parse(
            _ACTION_PREFIX
            + "        set the value of position<dest> to literal</text:abc>.\n"
            + "    }\n}\n"
        )
    assert error.value.location.line == 5
    assert error.value.location.column == 62
    assert error.value.location.end_line == 5
    assert error.value.location.end_column == 62


def test_literal_escape_at_end_of_line(parse: Parse):
    with pytest.raises(parser_exceptions.MissingLiteralContentEnd) as error:
        parse(
            _ACTION_PREFIX
            + '        set the value of position<dest> to literal</text>"ab\\\n'
            + "    }\n}\n"
        )
    assert error.value.location.line == 5
    assert error.value.location.column == 62
    assert error.value.location.end_line == 5
    assert error.value.location.end_column == 62


def test_literal_escape_at_end_of_source(parse: Parse):
    with pytest.raises(parser_exceptions.MissingLiteralContentEnd) as error:
        parse(
            _ACTION_PREFIX
            + '        set the value of position<dest> to literal</text>"ab\\'
        )
    assert error.value.location.line == 5
    assert error.value.location.column == 62
    assert error.value.location.end_line == 5
    assert error.value.location.end_column == 62


def test_literal_with_escape_and_non_ascii_character(parse: Parse):
    literal = _only_literal(
        parse(
            _ACTION_PREFIX
            + '        set the value of position<dest> to literal</text>"é\\"x".\n'
            + "    }\n}\n"
        )
    )
    assert literal.content == 'é"x'
    assert literal.location == ast.SourceLocation(
        line=5, column=44, end_line=5, end_column=63
    )


def test_literal_missing_close_quote_after_escape(parse: Parse):
    with pytest.raises(parser_exceptions.MissingLiteralContentEnd) as error:
        parse(
            _ACTION_PREFIX
            + '        set the value of position<dest> to literal</text>"a\\"b\n'
            + "    }\n}\n"
        )
    assert error.value.location.line == 5
    assert error.value.location.column == 63
    assert error.value.location.end_line == 5
    assert error.value.location.end_column == 63


def test_no_space_between_to_and_literal(parse: Parse):
    with pytest.raises(parser_exceptions.MissingWhitespace) as error:
        parse(
            _ACTION_PREFIX
            + '        set the value of position<dest> toliteral</text>"a".\n'
            + "    }\n}\n"
        )
    assert error.value.location.line == 5
    assert error.value.location.column == 43
    assert error.value.location.end_line == 5
    assert error.value.location.end_column == 49
