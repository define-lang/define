# pyright: reportUnusedCallResult=false
"""Operation Statements Block parser tests."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from define.compiler.errors import parser_exceptions
from define.compiler.parsing.parser_tests.test_helpers import get_tokens_by_type

if TYPE_CHECKING:
    from define.compiler.parsing.parser_tests.conftest import Parse


_OPERATION_PREFIX = (
    "define the operation<mv:define-lang.org:parser:/add> {\n" + "    it does {\n"
)

_OPERATION_SUFFIX = "    }\n}\n"


def test_encoding_operation_execution(parse: Parse):
    tree = parse(
        _OPERATION_PREFIX
        + "        execute the encoding operation.\n"
        + _OPERATION_SUFFIX
    )
    assert get_tokens_by_type(tree, "EXECUTE_THE_ENCODING_OPERATION") == [
        "execute the encoding operation"
    ]


def test_operation_execution_without_arguments(parse: Parse):
    tree = parse(
        _OPERATION_PREFIX
        + "        execute the operation</other>.\n"
        + _OPERATION_SUFFIX
    )
    assert get_tokens_by_type(tree, "EXECUTE_THE") == ["execute the"]
    assert get_tokens_by_type(tree, "OPERATION") == ["operation"]
    assert get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/add",
        "/other",
    ]


def test_operation_execution_with_arguments(parse: Parse):
    tree = parse(
        _OPERATION_PREFIX
        + "        execute the operation<mv:define-lang.org:parser:/other> {\n"
        + "            with view<a> looking at view<left>.\n"
        + "            with view<b> looking at position<p>.\n"
        + "            with view<c> looking at position</global>::position<child>.\n"
        + '            with view<d> looking at literal</number>"12".\n'
        + "        }\n"
        + _OPERATION_SUFFIX
    )
    assert get_tokens_by_type(tree, "WITH") == ["with", "with", "with", "with"]
    assert get_tokens_by_type(tree, "VIEW") == ["view", "view", "view", "view", "view"]
    assert get_tokens_by_type(tree, "POSITION_OR_ACTION") == [
        "position",
        "position",
        "position",
    ]
    assert get_tokens_by_type(tree, "LOCAL_NAME_CONTENT") == [
        "a",
        "left",
        "b",
        "p",
        "c",
        "child",
        "d",
    ]
    assert get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/add",
        "mv:define-lang.org:parser:/other",
        "/global",
        "/number",
    ]
    assert get_tokens_by_type(tree, "LITERAL_CONTENT") == ["12"]


def test_multiple_statements_comments_and_blank_lines(parse: Parse):
    tree = parse(
        _OPERATION_PREFIX
        + "\n"
        + "        execute the operation</first>. # comment\n"
        + "\n"
        + "        execute the operation</second> { # comment\n"
        + "\n"
        + "            with view<a> looking at view<p>. # comment\n"
        + "\n"
        + "        } # comment\n"
        + "\n"
        + "        execute the encoding operation. # comment\n"
        + "\n"
        + _OPERATION_SUFFIX
    )
    assert get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/add",
        "/first",
        "/second",
    ]


def test_requires_statement(parse: Parse):
    with pytest.raises(parser_exceptions.InvalidOperationStatementsBlock) as error:
        parse(_OPERATION_PREFIX + _OPERATION_SUFFIX)
    assert error.value.location.line == 3
    assert error.value.location.column == 5
    assert error.value.token == "}"


def test_disallows_action_statement(parse: Parse):
    with pytest.raises(parser_exceptions.InvalidOperationStatementsBlock) as error:
        parse(
            _OPERATION_PREFIX
            + "        create a particle in position<p>.\n"
            + _OPERATION_SUFFIX
        )
    assert error.value.location.line == 3
    assert error.value.location.column == 9
    assert error.value.token == "create a particle in"


def test_disallows_action_statement_after_first_statement(parse: Parse):
    with pytest.raises(parser_exceptions.InvalidOperationStatementsBlock) as error:
        parse(
            _OPERATION_PREFIX
            + "        execute the encoding operation.\n"
            + "        create a particle in position<p>.\n"
            + _OPERATION_SUFFIX
        )
    assert error.value.location.line == 4
    assert error.value.location.column == 9
    assert error.value.token == "create a particle in"


def test_encoding_operation_requires_terminator(parse: Parse):
    with pytest.raises(parser_exceptions.MissingTerminator) as error:
        parse(
            _OPERATION_PREFIX
            + "        execute the encoding operation\n"
            + _OPERATION_SUFFIX
        )
    assert error.value.location.line == 3
    assert error.value.location.column == 39
    assert error.value.token == "\n"


def test_operation_execution_requires_terminator_or_block(parse: Parse):
    with pytest.raises(parser_exceptions.MissingTerminatorOrBrace) as error:
        parse(
            _OPERATION_PREFIX
            + "        execute the operation</other>\n"
            + _OPERATION_SUFFIX
        )
    assert error.value.location.line == 3
    assert error.value.location.column == 38
    assert error.value.token == "\n"


def test_operation_requires_global_name(parse: Parse):
    with pytest.raises(parser_exceptions.InvalidGlobalName) as error:
        parse(
            _OPERATION_PREFIX
            + "        execute the operation<other>.\n"
            + _OPERATION_SUFFIX
        )
    assert error.value.location.line == 3
    assert error.value.location.column == 31
    assert error.value.token == "other"


def test_operation_requires_open_angle_bracket(parse: Parse):
    with pytest.raises(parser_exceptions.MissingOpenAngleBracket) as error:
        parse(
            _OPERATION_PREFIX
            + "        execute the operation /other.\n"
            + _OPERATION_SUFFIX
        )
    assert error.value.location.line == 3
    assert error.value.location.column == 30
    assert error.value.token == " "


def test_operation_name_type_cannot_be_position(parse: Parse):
    with pytest.raises(parser_exceptions.ExpectedOperation) as error:
        parse(
            _OPERATION_PREFIX
            + "        execute the position</other>.\n"
            + _OPERATION_SUFFIX
        )
    assert error.value.location.line == 3
    assert error.value.location.column == 21
    assert error.value.token == "position"


def test_operation_name_type_cannot_be_action(parse: Parse):
    with pytest.raises(parser_exceptions.ExpectedOperation) as error:
        parse(
            _OPERATION_PREFIX
            + "        execute the action</other>.\n"
            + _OPERATION_SUFFIX
        )
    assert error.value.location.line == 3
    assert error.value.location.column == 21
    assert error.value.token == "action"


def test_arguments_block_requires_argument(parse: Parse):
    with pytest.raises(parser_exceptions.InvalidOperationArgumentsBlock) as error:
        parse(
            _OPERATION_PREFIX
            + "        execute the operation</other> {\n"
            + "        }\n"
            + _OPERATION_SUFFIX
        )
    assert error.value.location.line == 4
    assert error.value.location.column == 9
    assert error.value.token == "}"


def test_argument_requires_terminator(parse: Parse):
    with pytest.raises(parser_exceptions.MissingTerminator) as error:
        parse(
            _OPERATION_PREFIX
            + "        execute the operation</other> {\n"
            + "            with view<a> looking at view<p>\n"
            + "        }\n"
            + _OPERATION_SUFFIX
        )
    assert error.value.location.line == 4
    assert error.value.location.column == 44
    assert error.value.token == "\n"


def test_argument_requires_local_view_name(parse: Parse):
    with pytest.raises(parser_exceptions.InvalidLocalNameCharacter) as error:
        parse(
            _OPERATION_PREFIX
            + "        execute the operation</other> {\n"
            + "            with view</a> looking at view<p>.\n"
            + "        }\n"
            + _OPERATION_SUFFIX
        )
    assert error.value.location.line == 4
    assert error.value.location.column == 23
    assert error.value.char == "/"


def test_argument_requires_view_name_type(parse: Parse):
    with pytest.raises(parser_exceptions.ExpectedView) as error:
        parse(
            _OPERATION_PREFIX
            + "        execute the operation</other> {\n"
            + "            with position<a> looking at view<p>.\n"
            + "        }\n"
            + _OPERATION_SUFFIX
        )
    assert error.value.location.line == 4
    assert error.value.location.column == 18
    assert error.value.token == "position"


def test_argument_requires_looking_at(parse: Parse):
    with pytest.raises(parser_exceptions.InvalidOperationArgumentSyntax) as error:
        parse(
            _OPERATION_PREFIX
            + "        execute the operation</other> {\n"
            + "            with view<a> position<p>.\n"
            + "        }\n"
            + _OPERATION_SUFFIX
        )
    assert error.value.location.line == 4
    assert error.value.location.column == 26
    assert error.value.token == "position"


def test_operation_missing_space_after_execute_the(parse: Parse):
    with pytest.raises(parser_exceptions.MissingWhitespace) as error:
        parse(
            _OPERATION_PREFIX
            + "        execute theoperation</other>.\n"
            + _OPERATION_SUFFIX
        )
    assert error.value.location.line == 3
    assert error.value.location.column == 20
    assert error.value.token == "operation"


def test_operation_extra_space_after_execute_the(parse: Parse):
    with pytest.raises(parser_exceptions.ExtraWhitespace) as error:
        parse(
            _OPERATION_PREFIX
            + "        execute the  operation</other>.\n"
            + _OPERATION_SUFFIX
        )
    assert error.value.location.line == 3
    assert error.value.location.column == 21
    assert error.value.token == " "


def test_argument_missing_space_after_with(parse: Parse):
    with pytest.raises(parser_exceptions.MissingWhitespace) as error:
        parse(
            _OPERATION_PREFIX
            + "        execute the operation</other> {\n"
            + "            withview<a> looking at view<p>.\n"
            + "        }\n"
            + _OPERATION_SUFFIX
        )
    assert error.value.location.line == 4
    assert error.value.location.column == 17
    assert error.value.token == "view"


def test_argument_extra_space_after_with(parse: Parse):
    with pytest.raises(parser_exceptions.ExtraWhitespace) as error:
        parse(
            _OPERATION_PREFIX
            + "        execute the operation</other> {\n"
            + "            with  view<a> looking at view<p>.\n"
            + "        }\n"
            + _OPERATION_SUFFIX
        )
    assert error.value.location.line == 4
    assert error.value.location.column == 18
    assert error.value.token == " "


def test_argument_missing_space_before_looking_at(parse: Parse):
    with pytest.raises(parser_exceptions.MissingWhitespace) as error:
        parse(
            _OPERATION_PREFIX
            + "        execute the operation</other> {\n"
            + "            with view<a>looking at view<p>.\n"
            + "        }\n"
            + _OPERATION_SUFFIX
        )
    assert error.value.location.line == 4
    assert error.value.location.column == 25
    assert error.value.token == "looking at"


def test_argument_extra_space_before_looking_at(parse: Parse):
    with pytest.raises(parser_exceptions.ExtraWhitespace) as error:
        parse(
            _OPERATION_PREFIX
            + "        execute the operation</other> {\n"
            + "            with view<a>  looking at view<p>.\n"
            + "        }\n"
            + _OPERATION_SUFFIX
        )
    assert error.value.location.line == 4
    assert error.value.location.column == 26
    assert error.value.token == " "


def test_argument_missing_space_after_looking_at(parse: Parse):
    with pytest.raises(parser_exceptions.MissingWhitespace) as error:
        parse(
            _OPERATION_PREFIX
            + "        execute the operation</other> {\n"
            + "            with view<a> looking atview<p>.\n"
            + "        }\n"
            + _OPERATION_SUFFIX
        )
    assert error.value.location.line == 4
    assert error.value.location.column == 36
    assert error.value.token == "view"


def test_argument_extra_space_after_looking_at(parse: Parse):
    with pytest.raises(parser_exceptions.ExtraWhitespace) as error:
        parse(
            _OPERATION_PREFIX
            + "        execute the operation</other> {\n"
            + "            with view<a> looking at  view<p>.\n"
            + "        }\n"
            + _OPERATION_SUFFIX
        )
    assert error.value.location.line == 4
    assert error.value.location.column == 37
    assert error.value.token == " "


def test_argument_view_cannot_be_chained(parse: Parse):
    with pytest.raises(parser_exceptions.MissingTerminator) as error:
        parse(
            _OPERATION_PREFIX
            + "        execute the operation</other> {\n"
            + "            with view<a> looking at view<p>::position<q>.\n"
            + "        }\n"
            + _OPERATION_SUFFIX
        )
    assert error.value.location.line == 4
    assert error.value.location.column == 44
    assert error.value.token == "::"


def test_argument_cannot_look_at_value(parse: Parse):
    with pytest.raises(parser_exceptions.ExpectedValueSource) as error:
        parse(
            _OPERATION_PREFIX
            + "        execute the operation</other> {\n"
            + "            with view<a> looking at value<b>.\n"
            + "        }\n"
            + _OPERATION_SUFFIX
        )
    assert error.value.location.line == 4
    assert error.value.location.column == 37
    assert error.value.token == "value"
