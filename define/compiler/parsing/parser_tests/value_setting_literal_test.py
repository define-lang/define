# pyright: reportUnusedCallResult=false
"""Literal source parser tests for Value Setting Statements."""

from __future__ import annotations

from typing import TYPE_CHECKING

from crates.source_rendering.python import rendering
from define.compiler import ast, name_types
from define.compiler.errors import diagnostics, syntax_errors

if TYPE_CHECKING:
    from define.compiler.parsing.parser_tests.conftest import (
        Parse,
        ParseSyntaxError,
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
            + '        set the value of position<dest> from literal</decimal>"123".\n'
            + "    }\n}\n"
        )
    )
    assert literal.content == "123"
    potential_literal = literal.potential_literal
    assert potential_literal.name_type == name_types.NameType.LITERAL
    assert potential_literal.name_content.fqun is None
    assert potential_literal.name_content.path.name == "/decimal"
    assert potential_literal.location == rendering.SourceLocation(
        line=5, column=46, end_line=5, end_column=62
    )
    assert literal.location == rendering.SourceLocation(
        line=5, column=46, end_line=5, end_column=67
    )


def test_literal_full_global_name(parse: Parse):
    literal = _only_literal(
        parse(
            _ACTION_PREFIX
            + '        set the value of position<dest>::position<child> from literal<mv:define-lang.org:parser:/text>"hello".\n'
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
    assert literal.location == rendering.SourceLocation(
        line=5, column=63, end_line=5, end_column=109
    )


def test_literal_empty_content(parse: Parse):
    literal = _only_literal(
        parse(
            _ACTION_PREFIX
            + '        set the value of position<dest> from literal</text>"".\n'
            + "    }\n}\n"
        )
    )
    assert literal.content == ""
    assert literal.location == rendering.SourceLocation(
        line=5, column=46, end_line=5, end_column=61
    )


def test_literal_spaces_comments_unicode_and_escapes(parse: Parse):
    literal = _only_literal(
        parse(
            _ACTION_PREFIX
            + '        set the value of position<dest> from literal</text>" # Hello 世界 < {} . > : \\" \\\\ \\n ". # comment\n'
            + "    }\n}\n"
        )
    )
    assert literal.content == ' # Hello 世界 < {} . > : " \\ \n '
    assert literal.location == rendering.SourceLocation(
        line=5, column=46, end_line=5, end_column=93
    )


def test_literal_starts_with_comment_character(parse: Parse):
    literal = _only_literal(
        parse(
            _ACTION_PREFIX
            + '        set the value of position<dest> from literal</text>"#content". # comment\n'
            + "    }\n}\n"
        )
    )
    assert literal.content == "#content"
    assert literal.location == rendering.SourceLocation(
        line=5, column=46, end_line=5, end_column=69
    )


def test_literal_brace_before_comment_character(parse: Parse):
    program = parse(
        _ACTION_PREFIX
        + '        set the value of position<dest> from literal</text>" {#content".\n'
        + '        set the value of position<dest> from literal</text>"next".\n'
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
            + '        set the value of position<dest> from literal</text>"a\\" {#b\\\\". # comment\n'
            + "    }\n}\n"
        )
    )
    assert literal.content == 'a" {#b\\'


def test_comment_after_literal_containing_angle_brackets(parse: Parse):
    literal = _only_literal(
        parse(
            _ACTION_PREFIX
            + '        set the value of position<dest> from literal</text>"< # >". # comment\n'
            + "    }\n}\n"
        )
    )
    assert literal.content == "< # >"


def test_literal_unknown_escape_is_invalid(parse_syntax_error: ParseSyntaxError):
    error = parse_syntax_error(
        _ACTION_PREFIX
        + '        set the value of position<dest> from literal</text>"bad\\t".\n'
        + "    }\n}\n"
    )
    assert isinstance(error, syntax_errors.InvalidLiteralEscape)
    assert error.char == "t"
    assert error.location.line == 5
    assert error.location.column == 65
    assert error.location.end_line == 5
    assert error.location.end_column == 65


def test_literal_unknown_escape_of_non_ascii_character(
    parse_syntax_error: ParseSyntaxError,
):
    error = parse_syntax_error(
        _ACTION_PREFIX
        + '        set the value of position<dest> from literal</text>"aé\\é".\n'
        + "    }\n}\n"
    )
    assert isinstance(error, syntax_errors.InvalidLiteralEscape)
    assert error.char == "é"
    assert error.location.line == 5
    assert error.location.column == 64
    assert error.location.end_line == 5
    assert error.location.end_column == 64


def test_literal_newline(parse_syntax_error: ParseSyntaxError):
    error = parse_syntax_error(
        _ACTION_PREFIX
        + '        set the value of position<dest> from literal</text>"a\nb".\n'
        + "    }\n}\n"
    )
    assert isinstance(error, syntax_errors.MissingLiteralContentEnd)
    assert error.location.line == 5
    assert error.location.column == 62
    assert error.location.end_line == 5
    assert error.location.end_column == 62


def test_literal_target_is_invalid(parse_syntax_error: ParseSyntaxError):
    error = parse_syntax_error(
        _ACTION_PREFIX
        + '        set the value of literal</text>"a" from position<dest>.\n'
        + "    }\n}\n"
    )
    assert isinstance(error, syntax_errors.ExpectedPositionOrAction)
    assert error.location.line == 5
    assert error.location.column == 26
    assert error.location.end_line == 5
    assert error.location.end_column == 32


def test_literal_missing_global_name(parse_syntax_error: ParseSyntaxError):
    error = parse_syntax_error(
        _ACTION_PREFIX
        + '        set the value of position<dest> from literal<text>"abc".\n'
        + "    }\n}\n"
    )
    assert isinstance(error, syntax_errors.InvalidGlobalName)
    assert error.location.line == 5
    assert error.location.column == 54
    assert error.location.end_line == 5
    assert error.location.end_column == 57


def test_literal_empty_name(parse_syntax_error: ParseSyntaxError):
    error = parse_syntax_error(
        _ACTION_PREFIX
        + '        set the value of position<dest> from literal<>"abc".\n'
        + "    }\n}\n"
    )
    assert isinstance(error, syntax_errors.EmptyName)
    assert error.location.line == 5
    assert error.location.column == 54
    assert error.location.end_line == 5
    assert error.location.end_column == 54


def test_literal_missing_open_angle_bracket(parse_syntax_error: ParseSyntaxError):
    error = parse_syntax_error(
        _ACTION_PREFIX
        + '        set the value of position<dest> from literal/text>"abc".\n'
        + "    }\n}\n"
    )
    assert isinstance(error, syntax_errors.MissingOpenAngleBracket)
    assert error.location.line == 5
    assert error.location.column == 53
    assert error.location.end_line == 5
    assert error.location.end_column == 53


def test_literal_missing_close_angle_bracket(parse_syntax_error: ParseSyntaxError):
    error = parse_syntax_error(
        _ACTION_PREFIX
        + '        set the value of position<dest> from literal</text"abc".\n'
        + "    }\n}\n"
    )
    assert isinstance(error, syntax_errors.MissingCloseAngleBracket)
    assert error.location.line == 5
    assert error.location.column == 65
    assert error.location.end_line == 5
    assert error.location.end_column == 65
    assert error.name == '/text"abc".'


def test_literal_missing_open_quote(parse_syntax_error: ParseSyntaxError):
    error = parse_syntax_error(
        _ACTION_PREFIX
        + "        set the value of position<dest> from literal</text>.\n"
        + "    }\n}\n"
    )
    assert isinstance(error, syntax_errors.MissingLiteralContentStart)
    assert error.location.line == 5
    assert error.location.column == 60
    assert error.location.end_line == 5
    assert error.location.end_column == 60


def test_literal_unquoted_content(parse_syntax_error: ParseSyntaxError):
    error = parse_syntax_error(
        _ACTION_PREFIX
        + "        set the value of position<dest> from literal</foo>5.\n"
        + "    }\n}\n"
    )
    assert isinstance(error, syntax_errors.MissingLiteralContentStart)
    assert error.location.line == 5
    assert error.location.column == 59
    assert error.location.end_line == 5
    assert error.location.end_column == 59


def test_literal_missing_close_quote(parse_syntax_error: ParseSyntaxError):
    error = parse_syntax_error(
        _ACTION_PREFIX
        + '        set the value of position<dest> from literal</text>"abc.\n'
        + "    }\n}\n"
    )
    assert isinstance(error, syntax_errors.MissingLiteralContentEnd)
    assert error.location.line == 5
    assert error.location.column == 65
    assert error.location.end_line == 5
    assert error.location.end_column == 65


def test_literal_content_starting_with_slash(parse: Parse):
    literal = _only_literal(
        parse(
            _ACTION_PREFIX
            + '        set the value of position<dest> from literal</text>"/0".\n'
            + "    }\n}\n"
        )
    )
    assert literal.content == "/0"


def test_literal_cannot_be_child_of_position(parse_syntax_error: ParseSyntaxError):
    error = parse_syntax_error(
        _ACTION_PREFIX
        + '        set the value of position<dest> from position<parent>::literal</text>"abc".\n'
        + "    }\n}\n"
    )
    assert isinstance(error, syntax_errors.ExpectedPositionOrAction)
    assert error.location.line == 5
    assert error.location.column == 64
    assert error.location.end_line == 5
    assert error.location.end_column == 70


def test_literal_cannot_start_position_reference(parse_syntax_error: ParseSyntaxError):
    error = parse_syntax_error(
        _ACTION_PREFIX
        + '        set the value of position<dest> from literal</text>"a"::position<child>.\n'
        + "    }\n}\n"
    )
    assert isinstance(error, syntax_errors.MissingTerminator)
    assert error.location.line == 5
    assert error.location.column == 63
    assert error.location.end_line == 5
    assert error.location.end_column == 63


def test_literal_without_terminator_gets_a_diagnostic(
    parse_with_diagnostics: ParseWithDiagnostics,
):
    result = parse_with_diagnostics(
        _ACTION_PREFIX
        + '        set the value of position<dest> from literal</text>"a"\n'
        + "    }\n}\n"
    )
    assert result.syntax_error is None
    assert result.diagnostics == [
        diagnostics.MissingTerminatorAtEndOfLineDiagnostic(
            location=rendering.SourceLocation(
                line=5, column=63, end_line=5, end_column=63
            )
        )
    ]
    assert result.program is not None
    [definition] = result.program.definitions
    assert isinstance(definition, ast.ActionDefinition)
    [statement] = definition.action_statements.statements
    assert isinstance(statement, ast.ValueSettingStatement)
    assert statement.location == rendering.SourceLocation(
        line=5, column=9, end_line=5, end_column=62
    )


def test_literal_old_syntax_is_invalid(parse_syntax_error: ParseSyntaxError):
    error = parse_syntax_error(
        _ACTION_PREFIX
        + "        set the value of position<dest> from literal</text:abc>.\n"
        + "    }\n}\n"
    )
    assert isinstance(error, syntax_errors.MissingLiteralContentStart)
    assert error.location.line == 5
    assert error.location.column == 64
    assert error.location.end_line == 5
    assert error.location.end_column == 64


def test_literal_escape_at_end_of_line(parse_syntax_error: ParseSyntaxError):
    error = parse_syntax_error(
        _ACTION_PREFIX
        + '        set the value of position<dest> from literal</text>"ab\\\n'
        + "    }\n}\n"
    )
    assert isinstance(error, syntax_errors.MissingLiteralContentEnd)
    assert error.location.line == 5
    assert error.location.column == 64
    assert error.location.end_line == 5
    assert error.location.end_column == 64


def test_literal_escape_at_end_of_source(parse_syntax_error: ParseSyntaxError):
    error = parse_syntax_error(
        _ACTION_PREFIX
        + '        set the value of position<dest> from literal</text>"ab\\'
    )
    assert isinstance(error, syntax_errors.MissingLiteralContentEnd)
    assert error.location.line == 5
    assert error.location.column == 64
    assert error.location.end_line == 5
    assert error.location.end_column == 64


def test_literal_with_escape_and_non_ascii_character(parse: Parse):
    literal = _only_literal(
        parse(
            _ACTION_PREFIX
            + '        set the value of position<dest> from literal</text>"é\\"x".\n'
            + "    }\n}\n"
        )
    )
    assert literal.content == 'é"x'
    assert literal.location == rendering.SourceLocation(
        line=5, column=46, end_line=5, end_column=65
    )


def test_literal_missing_close_quote_after_escape(parse_syntax_error: ParseSyntaxError):
    error = parse_syntax_error(
        _ACTION_PREFIX
        + '        set the value of position<dest> from literal</text>"a\\"b\n'
        + "    }\n}\n"
    )
    assert isinstance(error, syntax_errors.MissingLiteralContentEnd)
    assert error.location.line == 5
    assert error.location.column == 65
    assert error.location.end_line == 5
    assert error.location.end_column == 65


def test_no_space_between_from_and_literal(parse_syntax_error: ParseSyntaxError):
    error = parse_syntax_error(
        _ACTION_PREFIX
        + '        set the value of position<dest> fromliteral</text>"a".\n'
        + "    }\n}\n"
    )
    assert isinstance(error, syntax_errors.MissingWhitespace)
    assert error.location.line == 5
    assert error.location.column == 45
    assert error.location.end_line == 5
    assert error.location.end_column == 51
