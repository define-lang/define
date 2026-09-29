# pyright: reportUnusedCallResult=false
"""Operation Execution Statement parser tests within Action Statements Blocks."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from define.compiler.errors import parser_exceptions
from define.compiler.parsing.parser_tests.test_helpers import get_tokens_by_type

if TYPE_CHECKING:
    from define.compiler.parsing.parser_tests.conftest import Parse


_ACTION_PREFIX = (
    "define the potential action<mv:define-lang.org:parser:/run> {\n"
    + "    define the position<p>.\n"
    + "    it happens when {\n"
    + "        the position<p> has a particle.\n"
    + "    } and it does {\n"
)

_ACTION_SUFFIX = "    }\n}\n"


def test_operation_execution_without_arguments(parse: Parse):
    tree = parse(
        _ACTION_PREFIX + "        execute the operation</add>.\n" + _ACTION_SUFFIX
    )
    assert get_tokens_by_type(tree, "EXECUTE_THE") == ["execute the"]
    assert get_tokens_by_type(tree, "OPERATION") == ["operation"]
    assert get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/run",
        "/add",
    ]


def test_operation_execution_with_arguments(parse: Parse):
    tree = parse(
        _ACTION_PREFIX
        + "        execute the operation<mv:define-lang.org:parser:/add> {\n"
        + "            with view<a> looking at position<p>.\n"
        + "            with view<b> looking at position</global>::position<child>.\n"
        + '            with view<c> looking at literal</number>"12".\n'
        + "        }\n"
        + _ACTION_SUFFIX
    )
    assert get_tokens_by_type(tree, "WITH") == ["with", "with", "with"]
    assert get_tokens_by_type(tree, "VIEW") == ["view", "view", "view"]
    assert get_tokens_by_type(tree, "LOCAL_NAME_CONTENT") == [
        "p",
        "p",
        "a",
        "p",
        "b",
        "child",
        "c",
    ]
    assert get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/run",
        "mv:define-lang.org:parser:/add",
        "/global",
        "/number",
    ]
    assert get_tokens_by_type(tree, "LITERAL_CONTENT") == ["12"]


def test_operation_execution_among_action_statements(parse: Parse):
    tree = parse(
        _ACTION_PREFIX
        + "        define the position<q>.\n"
        + "\n"
        + "        create a particle in position<q>.\n"
        + "        execute the operation</add> { # comment\n"
        + "\n"
        + "            with view<a> looking at position<q>. # comment\n"
        + "\n"
        + "        } # comment\n"
        + "\n"
        + "        execute the operation</clear>. # comment\n"
        + "        destroy the particle in position<q>.\n"
        + _ACTION_SUFFIX
    )
    assert get_tokens_by_type(tree, "EXECUTE_THE") == ["execute the", "execute the"]
    assert get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/run",
        "/add",
        "/clear",
    ]


def test_disallows_encoding_operation_execution(parse: Parse):
    with pytest.raises(parser_exceptions.InvalidActionStatementsBlock) as error:
        parse(
            _ACTION_PREFIX
            + "        execute the encoding operation.\n"
            + _ACTION_SUFFIX
        )
    assert error.value.location.line == 6
    assert error.value.location.column == 9
    assert error.value.token == "execute the encoding operation"


def test_operation_execution_requires_terminator_or_block(parse: Parse):
    with pytest.raises(parser_exceptions.MissingTerminatorOrBrace) as error:
        parse(_ACTION_PREFIX + "        execute the operation</add>\n" + _ACTION_SUFFIX)
    assert error.value.location.line == 6
    assert error.value.location.column == 36
    assert error.value.token == "\n"


def test_operation_name_type_cannot_be_position(parse: Parse):
    with pytest.raises(parser_exceptions.ExpectedOperation) as error:
        parse(_ACTION_PREFIX + "        execute the position</add>.\n" + _ACTION_SUFFIX)
    assert error.value.location.line == 6
    assert error.value.location.column == 21
    assert error.value.token == "position"


def test_operation_missing_space_after_execute_the(parse: Parse):
    with pytest.raises(parser_exceptions.MissingWhitespace) as error:
        parse(_ACTION_PREFIX + "        execute theoperation</add>.\n" + _ACTION_SUFFIX)
    assert error.value.location.line == 6
    assert error.value.location.column == 20
    assert error.value.token == "operation"


def test_arguments_block_requires_argument(parse: Parse):
    with pytest.raises(parser_exceptions.InvalidOperationArgumentsBlock) as error:
        parse(
            _ACTION_PREFIX
            + "        execute the operation</add> {\n"
            + "        }\n"
            + _ACTION_SUFFIX
        )
    assert error.value.location.line == 7
    assert error.value.location.column == 9
    assert error.value.token == "}"


def test_arguments_block_disallows_action_statement(parse: Parse):
    with pytest.raises(parser_exceptions.InvalidOperationArgumentsBlock) as error:
        parse(
            _ACTION_PREFIX
            + "        execute the operation</add> {\n"
            + "            create a particle in position<p>.\n"
            + "        }\n"
            + _ACTION_SUFFIX
        )
    assert error.value.location.line == 7
    assert error.value.location.column == 13
    assert error.value.token == "create a particle in"


def test_arguments_block_disallows_action_statement_after_first_argument(
    parse: Parse,
):
    with pytest.raises(parser_exceptions.InvalidOperationArgumentsBlock) as error:
        parse(
            _ACTION_PREFIX
            + "        execute the operation</add> {\n"
            + "            with view<a> looking at position<p>.\n"
            + "            create a particle in position<p>.\n"
            + "        }\n"
            + _ACTION_SUFFIX
        )
    assert error.value.location.line == 8
    assert error.value.location.column == 13
    assert error.value.token == "create a particle in"


def test_argument_cannot_look_at_value(parse: Parse):
    with pytest.raises(parser_exceptions.ExpectedValueSource) as error:
        parse(
            _ACTION_PREFIX
            + "        execute the operation</add> {\n"
            + "            with view<a> looking at value<b>.\n"
            + "        }\n"
            + _ACTION_SUFFIX
        )
    assert error.value.location.line == 7
    assert error.value.location.column == 37
    assert error.value.token == "value"
