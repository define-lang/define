# pyright: reportUnusedCallResult=false
"""Destructor condition statement parser tests.

Follow parser test authoring rules in parser_tests/AGENTS.md.
"""

import pytest

from define.compiler import parser_exceptions
from define.compiler.parser_tests.conftest import Parse
from define.compiler.parser_tests.test_helpers import get_tokens_by_type


def test_destructor_with_no_interface_positions(parse: Parse) -> None:
    tree = parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    it happens when {\n"
        + "        this particle is being destroyed.\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    )
    assert get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/my_action"
    ]
    assert get_tokens_by_type(tree, "LOCAL_NAME_CONTENT") == []
    assert get_tokens_by_type(tree, "DESTRUCTOR_STATEMENT") == [
        "this particle is being destroyed"
    ]


def test_destructor_with_comments(parse: Parse) -> None:
    tree = parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    it happens when {\n"
        + "        # a comment\n"
        + "        this particle is being destroyed.\n"
        + "        # another comment\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    )
    assert get_tokens_by_type(tree, "DESTRUCTOR_STATEMENT") == [
        "this particle is being destroyed"
    ]


def test_destructor_with_blank_lines(parse: Parse) -> None:
    tree = parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    it happens when {\n"
        + "\n"
        + "        this particle is being destroyed.\n"
        + "\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    )
    assert get_tokens_by_type(tree, "DESTRUCTOR_STATEMENT") == [
        "this particle is being destroyed"
    ]


def test_destructor_missing_terminator(parse: Parse) -> None:
    with pytest.raises(parser_exceptions.MissingTerminator) as exc_info:
        parse(
            "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
            + "    it happens when {\n"
            + "        this particle is being destroyed\n"
            + "    } and it does {\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.token == "\n"
    assert exc_info.value.token.type == "NEWLINE"
    assert exc_info.value.line == 3
    assert exc_info.value.column == 41


def test_destructor_followed_by_extra_content(parse: Parse) -> None:
    with pytest.raises(parser_exceptions.MissingTerminator) as exc_info:
        parse(
            "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
            + "    it happens when {\n"
            + "        this particle is being destroyed now.\n"
            + "    } and it does {\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.token == " "
    assert exc_info.value.token.type == "SPACE"
    assert exc_info.value.line == 3
    assert exc_info.value.column == 41


def test_trigger_condition_and_destructor_in_one_block(parse: Parse) -> None:
    with pytest.raises(parser_exceptions.MissingCloseBrace) as exc_info:
        parse(
            "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
            + "    define the position<run>.\n"
            + "    it happens when {\n"
            + "        the position<run> has a particle.\n"
            + "        this particle is being destroyed.\n"
            + "    } and it does {\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.token == "this particle is being destroyed"
    assert exc_info.value.token.type == "DESTRUCTOR_STATEMENT"
    assert exc_info.value.line == 5
    assert exc_info.value.column == 9


def test_destructor_as_action_statement(parse: Parse) -> None:
    with pytest.raises(parser_exceptions.InvalidActionStatementsBlock) as exc_info:
        parse(
            "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
            + "    define the position<run>.\n"
            + "    it happens when {\n"
            + "        the position<run> has a particle.\n"
            + "    } and it does {\n"
            + "        this particle is being destroyed.\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.token == "this particle is being destroyed"
    assert exc_info.value.token.type == "DESTRUCTOR_STATEMENT"
    assert exc_info.value.line == 6
    assert exc_info.value.column == 9


def test_destructor_at_top_level(parse: Parse) -> None:
    with pytest.raises(parser_exceptions.ExpectedGlobalDefinition) as exc_info:
        parse("this particle is being destroyed.\n")
    assert exc_info.value.token == "this particle is being destroyed"
    assert exc_info.value.token.type == "DESTRUCTOR_STATEMENT"
    assert exc_info.value.line == 1
    assert exc_info.value.column == 1


def test_truncated_destructor_phrase_in_trigger_block(parse: Parse) -> None:
    with pytest.raises(parser_exceptions.InvalidTriggerConditionsBlock) as exc_info:
        parse(
            "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
            + "    it happens when {\n"
            + "        this particle.\n"
            + "    } and it does {\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.token == "this"
    assert exc_info.value.token.type == "LOCAL_NAME_CONTENT"
    assert exc_info.value.line == 3
    assert exc_info.value.column == 9


def test_destructor_block_missing_and_it_does(parse: Parse) -> None:
    with pytest.raises(parser_exceptions.MissingActionStatementsBlock) as exc_info:
        parse(
            "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
            + "    it happens when {\n"
            + "        this particle is being destroyed.\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.token == "\n"
    assert exc_info.value.token.type == "NEWLINE"
    assert exc_info.value.line == 4
    assert exc_info.value.column == 6


def test_destructor_action_block_missing_close_brace(parse: Parse) -> None:
    with pytest.raises(parser_exceptions.MissingCloseBrace) as exc_info:
        parse(
            "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
            + "    it happens when {\n"
            + "        this particle is being destroyed.\n"
            + "    } and it does {\n"
            + "}\n"
        )
    assert exc_info.value.token == ""
    assert exc_info.value.line == 5
    assert exc_info.value.column == 2
