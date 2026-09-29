# pyright: reportUnusedCallResult=false
"""Value operation definition parser tests."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from define.compiler.errors import parser_exceptions
from define.compiler.parsing.parser_tests.test_helpers import get_tokens_by_type

if TYPE_CHECKING:
    from define.compiler.parsing.parser_tests.conftest import Parse


def test_operation_definition(parse: Parse):
    tree = parse(
        "define the operation<mv:define-lang.org:parser:/add> {\n"
        + "    it does {\n"
        + "        execute the encoding operation.\n"
        + "    }\n"
        + "}\n"
    )
    assert get_tokens_by_type(tree, "DEFINE_THE_OPERATION") == ["define the operation"]
    assert get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/add"
    ]
    assert get_tokens_by_type(tree, "IT_DOES") == ["it does"]


def test_operation_definition_with_views(parse: Parse):
    tree = parse(
        "define the operation<mv:define-lang.org:parser:/add> {\n"
        + "    define the view<left> {\n"
        + "        it is read.\n"
        + "        it may only contain particles where {\n"
        + "            it has the value</number>.\n"
        + "        }\n"
        + "    }\n"
        + "    define the view<right> {\n"
        + "        it is read.\n"
        + "        it may only contain particles where {\n"
        + "            it has the value</number>.\n"
        + "        }\n"
        + "    }\n"
        + "    it does {\n"
        + "        execute the encoding operation.\n"
        + "    }\n"
        + "}\n"
    )
    assert get_tokens_by_type(tree, "LOCAL_NAME_CONTENT") == ["left", "right"]
    assert get_tokens_by_type(tree, "DEFINE_THE_VIEW") == [
        "define the view",
        "define the view",
    ]


def test_comments_and_blank_lines(parse: Parse):
    tree = parse(
        "define the operation<mv:define-lang.org:parser:/add> { # comment\n"
        + "\n"
        + "    # comment\n"
        + "    define the view<left> { # comment\n"
        + "\n"
        + "        it is read. # comment\n"
        + "\n"
        + "        it may only contain particles where { # comment\n"
        + "\n"
        + "            it has the value</number>. # comment\n"
        + "\n"
        + "        } # comment\n"
        + "\n"
        + "    } # comment\n"
        + "\n"
        + "    it does { # comment\n"
        + "\n"
        + "        execute the encoding operation. # comment\n"
        + "\n"
        + "    } # comment\n"
        + "\n"
        + "} # comment\n"
    )
    assert get_tokens_by_type(tree, "LOCAL_NAME_CONTENT") == ["left"]
    assert get_tokens_by_type(tree, "EXECUTE_THE_ENCODING_OPERATION") == [
        "execute the encoding operation"
    ]


def test_between_other_definitions(parse: Parse):
    tree = parse(
        "define the potential value<mv:define-lang.org:parser:/number>.\n"
        + "define the operation<mv:define-lang.org:parser:/add> {\n"
        + "    it does {\n"
        + "        execute the encoding operation.\n"
        + "    }\n"
        + "}\n"
        + "define the encoding<mv:define-lang.org:parser:/decimal>.\n"
    )
    assert get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/number",
        "mv:define-lang.org:parser:/add",
        "mv:define-lang.org:parser:/decimal",
    ]


def test_requires_global_name(parse: Parse):
    with pytest.raises(parser_exceptions.InvalidGlobalName) as error:
        parse(
            "define the operation<add> {\n"
            + "    it does {\n"
            + "        execute the encoding operation.\n"
            + "    }\n"
            + "}\n"
        )
    assert error.value.location.line == 1
    assert error.value.location.column == 22
    assert error.value.token == "add"


def test_requires_block(parse: Parse):
    with pytest.raises(parser_exceptions.MissingOpenBrace) as error:
        parse("define the operation<mv:define-lang.org:parser:/add>.\n")
    assert error.value.location.line == 1
    assert error.value.location.column == 53
    assert error.value.token == "."


def test_requires_operation_statements_block(parse: Parse):
    with pytest.raises(parser_exceptions.InvalidOperationDefinitionBlock) as error:
        parse("define the operation<mv:define-lang.org:parser:/add> {\n}\n")
    assert error.value.location.line == 2
    assert error.value.location.column == 1
    assert error.value.token == "}"


def test_requires_operation_statements_block_after_views(parse: Parse):
    with pytest.raises(parser_exceptions.InvalidOperationDefinitionBlock) as error:
        parse(
            "define the operation<mv:define-lang.org:parser:/add> {\n"
            + "    define the view<left> {\n"
            + "        it is read.\n"
            + "        it may only contain particles where {\n"
            + "            it has the value</number>.\n"
            + "        }\n"
            + "    }\n"
            + "}\n"
        )
    assert error.value.location.line == 8
    assert error.value.location.column == 1
    assert error.value.token == "}"


def test_disallows_local_position_definition(parse: Parse):
    with pytest.raises(parser_exceptions.InvalidOperationDefinitionBlock) as error:
        parse(
            "define the operation<mv:define-lang.org:parser:/add> {\n"
            + "    define the position<p>.\n"
            + "    it does {\n"
            + "        execute the encoding operation.\n"
            + "    }\n"
            + "}\n"
        )
    assert error.value.location.line == 2
    assert error.value.location.column == 5
    assert error.value.token == "define the position"


def test_disallows_view_after_operation_statements_block(parse: Parse):
    with pytest.raises(parser_exceptions.MissingCloseBrace) as error:
        parse(
            "define the operation<mv:define-lang.org:parser:/add> {\n"
            + "    it does {\n"
            + "        execute the encoding operation.\n"
            + "    }\n"
            + "    define the view<left> {\n"
            + "        it is read.\n"
            + "        it may only contain particles where {\n"
            + "            it has the value</number>.\n"
            + "        }\n"
            + "    }\n"
            + "}\n"
        )
    assert error.value.location.line == 5
    assert error.value.location.column == 5
    assert error.value.token == "define the view"


def test_disallows_second_operation_statements_block(parse: Parse):
    with pytest.raises(parser_exceptions.MissingCloseBrace) as error:
        parse(
            "define the operation<mv:define-lang.org:parser:/add> {\n"
            + "    it does {\n"
            + "        execute the encoding operation.\n"
            + "    }\n"
            + "    it does {\n"
            + "        execute the encoding operation.\n"
            + "    }\n"
            + "}\n"
        )
    assert error.value.location.line == 5
    assert error.value.location.column == 5
    assert error.value.token == "it does"


def test_missing_close_brace_at_eof(parse: Parse):
    with pytest.raises(parser_exceptions.MissingCloseBrace) as error:
        parse(
            "define the operation<mv:define-lang.org:parser:/add> {\n"
            + "    it does {\n"
            + "        execute the encoding operation.\n"
            + "    }\n"
        )
    assert error.value.location.line == 4
    assert error.value.location.column == 6
    assert error.value.token == ""


def test_operation_statements_block_extra_whitespace(parse: Parse):
    with pytest.raises(parser_exceptions.ExtraWhitespace) as error:
        parse(
            "define the operation<mv:define-lang.org:parser:/add> {\n"
            + "    it does  {\n"
            + "        execute the encoding operation.\n"
            + "    }\n"
            + "}\n"
        )
    assert error.value.location.line == 2
    assert error.value.location.column == 12
    assert error.value.token == " "


def test_disallows_local_context(parse: Parse):
    with pytest.raises(parser_exceptions.InvalidActionStatementsBlock) as error:
        parse(
            "define the potential action<mv:define-lang.org:parser:/test> {\n"
            + "    it happens when {\n"
            + "        this particle is created.\n"
            + "    } and it does {\n"
            + "        define the operation<mv:define-lang.org:parser:/add> {\n"
            + "            it does {\n"
            + "                execute the encoding operation.\n"
            + "            }\n"
            + "        }\n"
            + "    }\n"
            + "}\n"
        )
    assert error.value.location.line == 5
    assert error.value.location.column == 9
    assert error.value.token == "define the operation"
