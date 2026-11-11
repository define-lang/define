# pyright: reportUnusedCallResult=false
"""View Setting Statement parser tests."""

from __future__ import annotations

from typing import TYPE_CHECKING

from crates.source_rendering.python import rendering
from define.compiler import ast, name_types
from define.compiler.errors import syntax_errors

if TYPE_CHECKING:
    from define.compiler.parsing.parser_tests.conftest import (
        Parse,
        ParseSyntaxError,
    )


_OPERATION_PREFIX = (
    "define the operation<mv:define-lang.org:parser:/add> {\n" + "    it does {\n"
)

_OPERATION_SUFFIX = "    }\n}\n"


def _operation_statements(
    program: ast.Program,
) -> tuple[ast.OperationStatement, ...]:
    [definition] = program.definitions
    assert isinstance(definition, ast.ValueOperationDefinition)
    return definition.operation_statements.statements


def test_view_setting(parse: Parse):
    [statement] = _operation_statements(
        parse(
            _OPERATION_PREFIX
            + "        set the value of view<target> from view<source>.\n"
            + _OPERATION_SUFFIX
        )
    )
    assert isinstance(statement, ast.ViewSettingStatement)
    assert statement.target.name_type == name_types.NameType.VIEW
    assert statement.target.name_content.name == "target"
    assert statement.target.location == rendering.SourceLocation(
        line=3, column=26, end_line=3, end_column=37
    )
    assert statement.source.name_type == name_types.NameType.VIEW
    assert statement.source.name_content.name == "source"
    assert statement.source.location == rendering.SourceLocation(
        line=3, column=44, end_line=3, end_column=55
    )
    assert statement.location == rendering.SourceLocation(
        line=3, column=9, end_line=3, end_column=56
    )


def test_among_other_operation_statements(parse: Parse):
    [first, second, third] = _operation_statements(
        parse(
            _OPERATION_PREFIX
            + "        execute the logical_operation</and> {\n"
            + "            with view<a> looking at view<p>.\n"
            + "        }\n"
            + "        set the value of view<p> from view<q>. # comment\n"
            + "\n"
            + "        execute the operation</first>.\n"
            + _OPERATION_SUFFIX
        )
    )
    assert isinstance(first, ast.LogicalOperationExecutionStatement)
    assert isinstance(second, ast.ViewSettingStatement)
    assert second.location == rendering.SourceLocation(
        line=6, column=9, end_line=6, end_column=46
    )
    assert isinstance(third, ast.OperationExecutionStatement)


def test_source_disallows_literal(parse_syntax_error: ParseSyntaxError):
    error = parse_syntax_error(
        _OPERATION_PREFIX
        + '        set the value of view<target> from literal</number>"12".\n'
        + _OPERATION_SUFFIX
    )
    assert isinstance(error, syntax_errors.LiteralInViewSetting)
    assert error.location.line == 3
    assert error.location.column == 44
    assert error.location.end_line == 3
    assert error.location.end_column == 50


def test_source_word_starting_with_literal(parse_syntax_error: ParseSyntaxError):
    error = parse_syntax_error(
        _OPERATION_PREFIX
        + "        set the value of view<target> from literally<p>.\n"
        + _OPERATION_SUFFIX
    )
    assert isinstance(error, syntax_errors.ExpectedView)
    assert error.location.line == 3
    assert error.location.column == 44
    assert error.location.end_line == 3
    assert error.location.end_column == 52


def test_source_cannot_be_position(parse_syntax_error: ParseSyntaxError):
    error = parse_syntax_error(
        _OPERATION_PREFIX
        + "        set the value of view<target> from position<p>.\n"
        + _OPERATION_SUFFIX
    )
    assert isinstance(error, syntax_errors.ExpectedView)
    assert error.location.line == 3
    assert error.location.column == 44
    assert error.location.end_line == 3
    assert error.location.end_column == 51


def test_source_is_not_a_word(parse_syntax_error: ParseSyntaxError):
    error = parse_syntax_error(
        _OPERATION_PREFIX
        + '        set the value of view<target> from "12".\n'
        + _OPERATION_SUFFIX
    )
    assert isinstance(error, syntax_errors.ExpectedView)
    assert error.location.line == 3
    assert error.location.column == 44
    assert error.location.end_line == 3
    assert error.location.end_column == 47


def test_target_cannot_be_position(parse_syntax_error: ParseSyntaxError):
    error = parse_syntax_error(
        _OPERATION_PREFIX
        + "        set the value of position<p> from view<source>.\n"
        + _OPERATION_SUFFIX
    )
    assert isinstance(error, syntax_errors.ExpectedView)
    assert error.location.line == 3
    assert error.location.column == 26
    assert error.location.end_line == 3
    assert error.location.end_column == 33


def test_target_cannot_be_literal(parse_syntax_error: ParseSyntaxError):
    error = parse_syntax_error(
        _OPERATION_PREFIX
        + '        set the value of literal</number>"12" from view<source>.\n'
        + _OPERATION_SUFFIX
    )
    assert isinstance(error, syntax_errors.ExpectedView)
    assert error.location.line == 3
    assert error.location.column == 26
    assert error.location.end_line == 3
    assert error.location.end_column == 32


def test_target_requires_local_view_name(parse_syntax_error: ParseSyntaxError):
    error = parse_syntax_error(
        _OPERATION_PREFIX
        + "        set the value of view</target> from view<source>.\n"
        + _OPERATION_SUFFIX
    )
    assert isinstance(error, syntax_errors.GlobalNameWhereLocalNameExpected)
    assert error.location.line == 3
    assert error.location.column == 31
    assert error.location.end_line == 3
    assert error.location.end_column == 37


def test_source_requires_local_view_name(parse_syntax_error: ParseSyntaxError):
    error = parse_syntax_error(
        _OPERATION_PREFIX
        + "        set the value of view<target> from view</source>.\n"
        + _OPERATION_SUFFIX
    )
    assert isinstance(error, syntax_errors.GlobalNameWhereLocalNameExpected)
    assert error.location.line == 3
    assert error.location.column == 49
    assert error.location.end_line == 3
    assert error.location.end_column == 55


def test_requires_from(parse_syntax_error: ParseSyntaxError):
    error = parse_syntax_error(
        _OPERATION_PREFIX
        + "        set the value of view<target> view<source>.\n"
        + _OPERATION_SUFFIX
    )
    assert isinstance(error, syntax_errors.InvalidViewSettingStatementSyntax)
    assert error.location.line == 3
    assert error.location.column == 39
    assert error.location.end_line == 3
    assert error.location.end_column == 42


def test_ends_after_target(parse_syntax_error: ParseSyntaxError):
    error = parse_syntax_error(
        _OPERATION_PREFIX
        + "        set the value of view<target>\n"
        + _OPERATION_SUFFIX
    )
    assert isinstance(error, syntax_errors.InvalidViewSettingStatementSyntax)
    assert error.location.line == 3
    assert error.location.column == 38
    assert error.location.end_line == 3
    assert error.location.end_column == 38


def test_ends_after_set_the_value_of(parse_syntax_error: ParseSyntaxError):
    error = parse_syntax_error(
        _OPERATION_PREFIX + "        set the value of\n" + _OPERATION_SUFFIX
    )
    assert isinstance(error, syntax_errors.ExpectedView)
    assert error.location.line == 3
    assert error.location.column == 25
    assert error.location.end_line == 3
    assert error.location.end_column == 25


def test_ends_after_from(parse_syntax_error: ParseSyntaxError):
    error = parse_syntax_error(
        _OPERATION_PREFIX
        + "        set the value of view<target> from\n"
        + _OPERATION_SUFFIX
    )
    assert isinstance(error, syntax_errors.ExpectedView)
    assert error.location.line == 3
    assert error.location.column == 43
    assert error.location.end_line == 3
    assert error.location.end_column == 43


def test_missing_space_after_from(parse_syntax_error: ParseSyntaxError):
    error = parse_syntax_error(
        _OPERATION_PREFIX
        + "        set the value of view<target> fromview<source>.\n"
        + _OPERATION_SUFFIX
    )
    assert isinstance(error, syntax_errors.MissingWhitespace)
    assert error.location.line == 3
    assert error.location.column == 43
    assert error.location.end_line == 3
    assert error.location.end_column == 46


def test_extra_space_after_from(parse_syntax_error: ParseSyntaxError):
    error = parse_syntax_error(
        _OPERATION_PREFIX
        + "        set the value of view<target> from  view<source>.\n"
        + _OPERATION_SUFFIX
    )
    assert isinstance(error, syntax_errors.ExtraWhitespace)
    assert error.location.line == 3
    assert error.location.column == 43
    assert error.location.end_line == 3
    assert error.location.end_column == 44


def test_extra_space_in_set_the_value_of(parse_syntax_error: ParseSyntaxError):
    error = parse_syntax_error(
        _OPERATION_PREFIX
        + "        set the  value of view<target> from view<source>.\n"
        + _OPERATION_SUFFIX
    )
    assert isinstance(error, syntax_errors.ExtraWhitespace)
    assert error.location.line == 3
    assert error.location.column == 16
    assert error.location.end_line == 3
    assert error.location.end_column == 17


def test_followed_by_text(parse_syntax_error: ParseSyntaxError):
    error = parse_syntax_error(
        _OPERATION_PREFIX
        + "        set the value of view<target> from view<source> extra.\n"
        + _OPERATION_SUFFIX
    )
    assert isinstance(error, syntax_errors.MissingTerminator)
    assert error.location.line == 3
    assert error.location.column == 56
    assert error.location.end_line == 3
    assert error.location.end_column == 56


def test_encoding_operation_view_setting(parse: Parse):
    [definition] = parse(
        "define the encoding_operation<mv:define-lang.org:parser:/add> {\n"
        + "    it does {\n"
        + "        set the value of view<target> from view<source>.\n"
        + "    }\n"
        + "}\n"
    ).definitions
    assert isinstance(definition, ast.EncodingOperationDefinition)
    [statement] = definition.operation_statements.statements
    assert isinstance(statement, ast.ViewSettingStatement)
    assert statement.target.name_content.name == "target"
    assert statement.source.name_content.name == "source"
    assert statement.location == rendering.SourceLocation(
        line=3, column=9, end_line=3, end_column=56
    )


def test_action_disallows_view_setting(parse_syntax_error: ParseSyntaxError):
    error = parse_syntax_error(
        "define the potential action<mv:define-lang.org:parser:/act> {\n"
        + "    it happens when {\n"
        + "        this particle is created.\n"
        + "    } and it does {\n"
        + "        set the value of view<target> from view<source>.\n"
        + "    }\n"
        + "}\n"
    )
    assert isinstance(error, syntax_errors.ExpectedPositionOrAction)
    assert error.location.line == 5
    assert error.location.column == 26
    assert error.location.end_line == 5
    assert error.location.end_column == 29


def test_extra_space_after_set_the_value_of(parse_syntax_error: ParseSyntaxError):
    error = parse_syntax_error(
        _OPERATION_PREFIX
        + "        set the value of  view<target> from view<source>.\n"
        + _OPERATION_SUFFIX
    )
    assert isinstance(error, syntax_errors.ExtraWhitespace)
    assert error.location.line == 3
    assert error.location.column == 25
    assert error.location.end_line == 3
    assert error.location.end_column == 26


def test_missing_space_before_literal_source(parse_syntax_error: ParseSyntaxError):
    error = parse_syntax_error(
        _OPERATION_PREFIX
        + '        set the value of view<target> fromliteral</number>"12".\n'
        + _OPERATION_SUFFIX
    )
    assert isinstance(error, syntax_errors.InvalidViewSettingStatementSyntax)
    assert error.location.line == 3
    assert error.location.column == 39
    assert error.location.end_line == 3
    assert error.location.end_column == 49
