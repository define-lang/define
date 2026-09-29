# pyright: reportUnusedCallResult=false
"""Encoding Operation definition parser tests."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from define.compiler.errors import parser_exceptions
from define.compiler.parsing.parser_tests.test_helpers import get_tokens_by_type

if TYPE_CHECKING:
    from define.compiler.parsing.parser_tests.conftest import Parse


_ENCODING_OPERATION_PREFIX = (
    "define the encoding_operation<mv:define-lang.org:parser:/add> {\n"
    + "    it does {\n"
)

_ENCODING_OPERATION_SUFFIX = "    }\n}\n"


def test_encoding_operation_definition(parse: Parse):
    tree = parse(
        "define the encoding_operation<mv:define-lang.org:parser:/add> {\n"
        + "    it does {\n"
        + "        execute the computer operation.\n"
        + "    }\n"
        + "}\n"
    )
    assert get_tokens_by_type(tree, "DEFINE_THE_ENCODING_OPERATION") == [
        "define the encoding_operation"
    ]
    assert get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/add"
    ]
    assert get_tokens_by_type(tree, "IT_DOES") == ["it does"]
    assert get_tokens_by_type(tree, "EXECUTE_THE_COMPUTER_OPERATION") == [
        "execute the computer operation"
    ]


def test_encoding_operation_definition_with_views(parse: Parse):
    tree = parse(
        "define the encoding_operation<mv:define-lang.org:parser:/add> {\n"
        + "    define the view<left> {\n"
        + "        it is read.\n"
        + "        it may only contain particles where {\n"
        + "            it has the encoding</decimal>.\n"
        + "        }\n"
        + "    }\n"
        + "    define the view<right> {\n"
        + "        it is written.\n"
        + "        it may only contain particles where {\n"
        + "            it has the encoding</decimal>.\n"
        + "        }\n"
        + "    }\n"
        + "    it does {\n"
        + "        execute the computer operation.\n"
        + "    }\n"
        + "}\n"
    )
    assert get_tokens_by_type(tree, "LOCAL_NAME_CONTENT") == ["left", "right"]
    assert get_tokens_by_type(tree, "DEFINE_THE_VIEW") == [
        "define the view",
        "define the view",
    ]


def test_encoding_operation_execution_without_arguments(parse: Parse):
    tree = parse(
        _ENCODING_OPERATION_PREFIX
        + "        execute the encoding_operation</other>.\n"
        + _ENCODING_OPERATION_SUFFIX
    )
    assert get_tokens_by_type(tree, "EXECUTE_THE") == ["execute the"]
    assert get_tokens_by_type(tree, "ENCODING_OPERATION") == ["encoding_operation"]
    assert get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/add",
        "/other",
    ]


def test_encoding_operation_execution_with_arguments(parse: Parse):
    tree = parse(
        _ENCODING_OPERATION_PREFIX
        + "        execute the encoding_operation<mv:define-lang.org:parser:/other> {\n"
        + "            with view<a> looking at view<left>.\n"
        + "            with view<b> looking at position<p>.\n"
        + '            with view<c> looking at literal</number>"12".\n'
        + "        }\n"
        + _ENCODING_OPERATION_SUFFIX
    )
    assert get_tokens_by_type(tree, "ENCODING_OPERATION") == ["encoding_operation"]
    assert get_tokens_by_type(tree, "WITH") == ["with", "with", "with"]
    assert get_tokens_by_type(tree, "LOCAL_NAME_CONTENT") == [
        "a",
        "left",
        "b",
        "p",
        "c",
    ]
    assert get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/add",
        "mv:define-lang.org:parser:/other",
        "/number",
    ]
    assert get_tokens_by_type(tree, "LITERAL_CONTENT") == ["12"]


def test_multiple_statements_comments_and_blank_lines(parse: Parse):
    tree = parse(
        "define the encoding_operation<mv:define-lang.org:parser:/add> { # comment\n"
        + "\n"
        + "    # comment\n"
        + "    define the view<left> { # comment\n"
        + "\n"
        + "        it is read. # comment\n"
        + "\n"
        + "        it may only contain particles where { # comment\n"
        + "\n"
        + "            it has the encoding</decimal>. # comment\n"
        + "\n"
        + "        } # comment\n"
        + "\n"
        + "    } # comment\n"
        + "\n"
        + "    it does { # comment\n"
        + "\n"
        + "        execute the encoding_operation</first>. # comment\n"
        + "\n"
        + "        execute the encoding_operation</second> { # comment\n"
        + "\n"
        + "            with view<a> looking at view<left>. # comment\n"
        + "\n"
        + "        } # comment\n"
        + "\n"
        + "        execute the computer operation. # comment\n"
        + "\n"
        + "    } # comment\n"
        + "\n"
        + "} # comment\n"
    )
    assert get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/add",
        "/decimal",
        "/first",
        "/second",
    ]
    assert get_tokens_by_type(tree, "EXECUTE_THE_COMPUTER_OPERATION") == [
        "execute the computer operation"
    ]


def test_between_other_definitions(parse: Parse):
    tree = parse(
        "define the operation<mv:define-lang.org:parser:/add> {\n"
        + "    it does {\n"
        + "        execute the encoding operation.\n"
        + "    }\n"
        + "}\n"
        + "define the encoding_operation<mv:define-lang.org:parser:/add_decimal> {\n"
        + "    it does {\n"
        + "        execute the computer operation.\n"
        + "    }\n"
        + "}\n"
        + "define the encoding<mv:define-lang.org:parser:/decimal>.\n"
    )
    assert get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/add",
        "mv:define-lang.org:parser:/add_decimal",
        "mv:define-lang.org:parser:/decimal",
    ]


def test_requires_global_name(parse: Parse):
    with pytest.raises(parser_exceptions.InvalidGlobalName) as error:
        parse(
            "define the encoding_operation<add> {\n"
            + "    it does {\n"
            + "        execute the computer operation.\n"
            + "    }\n"
            + "}\n"
        )
    assert error.value.location.line == 1
    assert error.value.location.column == 31
    assert error.value.token == "add"


def test_requires_block(parse: Parse):
    with pytest.raises(parser_exceptions.MissingOpenBrace) as error:
        parse("define the encoding_operation<mv:define-lang.org:parser:/add>.\n")
    assert error.value.location.line == 1
    assert error.value.location.column == 62
    assert error.value.token == "."


def test_requires_operation_statements_block(parse: Parse):
    with pytest.raises(parser_exceptions.InvalidOperationDefinitionBlock) as error:
        parse("define the encoding_operation<mv:define-lang.org:parser:/add> {\n}\n")
    assert error.value.location.line == 2
    assert error.value.location.column == 1
    assert error.value.token == "}"


def test_disallows_local_position_definition(parse: Parse):
    with pytest.raises(parser_exceptions.InvalidOperationDefinitionBlock) as error:
        parse(
            "define the encoding_operation<mv:define-lang.org:parser:/add> {\n"
            + "    define the position<p>.\n"
            + "    it does {\n"
            + "        execute the computer operation.\n"
            + "    }\n"
            + "}\n"
        )
    assert error.value.location.line == 2
    assert error.value.location.column == 5
    assert error.value.token == "define the position"


def test_requires_statement(parse: Parse):
    with pytest.raises(
        parser_exceptions.InvalidEncodingOperationStatementsBlock
    ) as error:
        parse(_ENCODING_OPERATION_PREFIX + _ENCODING_OPERATION_SUFFIX)
    assert error.value.location.line == 3
    assert error.value.location.column == 5
    assert error.value.token == "}"


def test_disallows_action_statement(parse: Parse):
    with pytest.raises(
        parser_exceptions.InvalidEncodingOperationStatementsBlock
    ) as error:
        parse(
            _ENCODING_OPERATION_PREFIX
            + "        create a particle in position<p>.\n"
            + _ENCODING_OPERATION_SUFFIX
        )
    assert error.value.location.line == 3
    assert error.value.location.column == 9
    assert error.value.token == "create a particle in"


def test_disallows_action_statement_after_first_statement(parse: Parse):
    with pytest.raises(
        parser_exceptions.InvalidEncodingOperationStatementsBlock
    ) as error:
        parse(
            _ENCODING_OPERATION_PREFIX
            + "        execute the computer operation.\n"
            + "        create a particle in position<p>.\n"
            + _ENCODING_OPERATION_SUFFIX
        )
    assert error.value.location.line == 4
    assert error.value.location.column == 9
    assert error.value.token == "create a particle in"


def test_disallows_encoding_operation_statement(parse: Parse):
    with pytest.raises(
        parser_exceptions.InvalidEncodingOperationStatementsBlock
    ) as error:
        parse(
            _ENCODING_OPERATION_PREFIX
            + "        execute the encoding operation.\n"
            + _ENCODING_OPERATION_SUFFIX
        )
    assert error.value.location.line == 3
    assert error.value.location.column == 9
    assert error.value.token == "execute the encoding operation"


def test_disallows_value_operation_execution(parse: Parse):
    with pytest.raises(parser_exceptions.ExpectedEncodingOperation) as error:
        parse(
            _ENCODING_OPERATION_PREFIX
            + "        execute the operation</other>.\n"
            + _ENCODING_OPERATION_SUFFIX
        )
    assert error.value.location.line == 3
    assert error.value.location.column == 21
    assert error.value.token == "operation"


def test_encoding_operation_name_type_cannot_be_position(parse: Parse):
    with pytest.raises(parser_exceptions.ExpectedEncodingOperation) as error:
        parse(
            _ENCODING_OPERATION_PREFIX
            + "        execute the position</other>.\n"
            + _ENCODING_OPERATION_SUFFIX
        )
    assert error.value.location.line == 3
    assert error.value.location.column == 21
    assert error.value.token == "position"


def test_encoding_operation_extra_space_after_execute_the(parse: Parse):
    with pytest.raises(parser_exceptions.ExtraWhitespace) as error:
        parse(
            _ENCODING_OPERATION_PREFIX
            + "        execute the  encoding_operation</other>.\n"
            + _ENCODING_OPERATION_SUFFIX
        )
    assert error.value.location.line == 3
    assert error.value.location.column == 21
    assert error.value.token == " "


def test_computer_operation_requires_terminator(parse: Parse):
    with pytest.raises(parser_exceptions.MissingTerminator) as error:
        parse(
            _ENCODING_OPERATION_PREFIX
            + "        execute the computer operation\n"
            + _ENCODING_OPERATION_SUFFIX
        )
    assert error.value.location.line == 3
    assert error.value.location.column == 39
    assert error.value.token == "\n"


def test_encoding_operation_execution_requires_terminator_or_block(parse: Parse):
    with pytest.raises(parser_exceptions.MissingTerminatorOrBrace) as error:
        parse(
            _ENCODING_OPERATION_PREFIX
            + "        execute the encoding_operation</other>\n"
            + _ENCODING_OPERATION_SUFFIX
        )
    assert error.value.location.line == 3
    assert error.value.location.column == 47
    assert error.value.token == "\n"


def test_encoding_operation_execution_requires_global_name(parse: Parse):
    with pytest.raises(parser_exceptions.InvalidGlobalName) as error:
        parse(
            _ENCODING_OPERATION_PREFIX
            + "        execute the encoding_operation<other>.\n"
            + _ENCODING_OPERATION_SUFFIX
        )
    assert error.value.location.line == 3
    assert error.value.location.column == 40
    assert error.value.token == "other"


def test_arguments_block_requires_argument(parse: Parse):
    with pytest.raises(parser_exceptions.InvalidOperationArgumentsBlock) as error:
        parse(
            _ENCODING_OPERATION_PREFIX
            + "        execute the encoding_operation</other> {\n"
            + "        }\n"
            + _ENCODING_OPERATION_SUFFIX
        )
    assert error.value.location.line == 4
    assert error.value.location.column == 9
    assert error.value.token == "}"


def test_value_operation_disallows_computer_operation(parse: Parse):
    with pytest.raises(parser_exceptions.InvalidOperationStatementsBlock) as error:
        parse(
            "define the operation<mv:define-lang.org:parser:/add> {\n"
            + "    it does {\n"
            + "        execute the computer operation.\n"
            + "    }\n"
            + "}\n"
        )
    assert error.value.location.line == 3
    assert error.value.location.column == 9
    assert error.value.token == "execute the computer operation"


def test_value_operation_disallows_encoding_operation_execution(parse: Parse):
    with pytest.raises(parser_exceptions.ExpectedOperation) as error:
        parse(
            "define the operation<mv:define-lang.org:parser:/add> {\n"
            + "    it does {\n"
            + "        execute the encoding_operation</other>.\n"
            + "    }\n"
            + "}\n"
        )
    assert error.value.location.line == 3
    assert error.value.location.column == 21
    assert error.value.token == "encoding_operation"


def test_action_disallows_encoding_operation_execution(parse: Parse):
    with pytest.raises(parser_exceptions.ExpectedOperation) as error:
        parse(
            "define the potential action<mv:define-lang.org:parser:/test> {\n"
            + "    it happens when {\n"
            + "        this particle is created.\n"
            + "    } and it does {\n"
            + "        execute the encoding_operation</other>.\n"
            + "    }\n"
            + "}\n"
        )
    assert error.value.location.line == 5
    assert error.value.location.column == 21
    assert error.value.token == "encoding_operation"


def test_disallows_local_context(parse: Parse):
    with pytest.raises(parser_exceptions.InvalidActionStatementsBlock) as error:
        parse(
            "define the potential action<mv:define-lang.org:parser:/test> {\n"
            + "    it happens when {\n"
            + "        this particle is created.\n"
            + "    } and it does {\n"
            + "        define the encoding_operation<mv:define-lang.org:parser:/add> {\n"
            + "            it does {\n"
            + "                execute the computer operation.\n"
            + "            }\n"
            + "        }\n"
            + "    }\n"
            + "}\n"
        )
    assert error.value.location.line == 5
    assert error.value.location.column == 9
    assert error.value.token == "define the encoding_operation"


def test_computer_operation_is_not_a_global_definition(parse: Parse):
    with pytest.raises(parser_exceptions.ExpectedGlobalDefinition) as error:
        parse("execute the computer operation.\n")
    assert error.value.location.line == 1
    assert error.value.location.column == 1
    assert error.value.token == "execute the computer operation"
