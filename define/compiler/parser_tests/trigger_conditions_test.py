# pyright: reportUnusedCallResult=false
"""Trigger condition statement parser tests.

Follow parser test authoring rules in parser_tests/AGENTS.md.
"""

import pytest

from define.compiler import parser_exceptions
from define.compiler.parser_tests.conftest import Parse
from define.compiler.parser_tests.test_helpers import get_tokens_by_type


def test_trigger_condition_with_local_position(parse: Parse) -> None:
    tree = parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    define the position<my_pos>.\n"
        + "    it happens when {\n"
        + "        the position<my_pos> has a particle.\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    )
    assert get_tokens_by_type(tree, "LOCAL_NAME_CONTENT") == ["my_pos", "my_pos"]


def test_trigger_condition_with_comments(parse: Parse) -> None:
    tree = parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    define the position<run>.\n"
        + "    it happens when {\n"
        + "        # a comment\n"
        + "        the position<run> has a particle.\n"
        + "        # another comment\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    )
    assert get_tokens_by_type(tree, "LOCAL_NAME_CONTENT") == ["run", "run"]


def test_trigger_condition_with_blank_lines(parse: Parse) -> None:
    tree = parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    define the position<run>.\n"
        + "    it happens when {\n"
        + "\n"
        + "        the position<run> has a particle.\n"
        + "\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    )
    assert get_tokens_by_type(tree, "LOCAL_NAME_CONTENT") == ["run", "run"]


def test_chained_name_is_parse_error(parse: Parse) -> None:
    with pytest.raises(parser_exceptions.InvalidHasAParticleSyntax) as exc_info:
        parse(
            "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
            + "    define the position<run>.\n"
            + "    it happens when {\n"
            + "        the position<run>::position</other> has a particle.\n"
            + "    } and it does {\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.token == "::"
    assert exc_info.value.token.type == "CHAIN_SEPARATOR"
    assert exc_info.value.line == 4
    assert exc_info.value.column == 26


def test_global_name_is_parse_error(parse: Parse) -> None:
    with pytest.raises(parser_exceptions.InvalidLocalNameCharacter) as exc_info:
        parse(
            "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
            + "    it happens when {\n"
            + "        the position</some_pos> has a particle.\n"
            + "    } and it does {\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.line == 3
    assert exc_info.value.column == 22
    assert exc_info.value.char == "/"


def test_trigger_block_same_line_no_space(parse: Parse) -> None:
    with pytest.raises(parser_exceptions.EmptyBlock) as exc_info:
        parse(
            "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
            + "    define the position<run>.\n"
            + "    it happens when {} and it does {\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.token == "}"
    assert exc_info.value.token.type == "RBRACE"
    assert exc_info.value.line == 3
    assert exc_info.value.column == 22


def test_trigger_block_same_line_with_space(parse: Parse) -> None:
    with pytest.raises(parser_exceptions.MissingNewlineAfterOpenBrace) as exc_info:
        parse(
            "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
            + "    define the position<run>.\n"
            + "    it happens when { } and it does {\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.token == " "
    assert exc_info.value.token.type == "SPACE"
    assert exc_info.value.line == 3
    assert exc_info.value.column == 22


def test_trigger_block_closing_brace_same_line(parse: Parse) -> None:
    with pytest.raises(parser_exceptions.EmptyBlock) as exc_info:
        parse(
            "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
            + "    define the position<run>.\n"
            + "    it happens when {}\n"
            + "}\n"
        )
    assert exc_info.value.token == "}"
    assert exc_info.value.token.type == "RBRACE"
    assert exc_info.value.line == 3
    assert exc_info.value.column == 22


def test_empty_trigger_block_is_error(parse: Parse) -> None:
    with pytest.raises(parser_exceptions.MissingTriggerConditionContent) as exc_info:
        parse(
            "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
            + "    it happens when {\n"
            + "    } and it does {\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.token == "}"
    assert exc_info.value.token.type == "RBRACE"
    assert exc_info.value.line == 3
    assert exc_info.value.column == 5


def test_invalid_content_in_trigger_block(parse: Parse) -> None:
    with pytest.raises(parser_exceptions.InvalidTriggerConditionsBlock) as exc_info:
        parse(
            "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
            + "    define the position<run>.\n"
            + "    it happens when {\n"
            + "        nonsense\n"
            + "    } and it does {\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.token == "nonsense"
    assert exc_info.value.token.type == "LOCAL_NAME_CONTENT"
    assert exc_info.value.line == 4
    assert exc_info.value.column == 9


def test_missing_terminator_after_trigger_condition(parse: Parse) -> None:
    with pytest.raises(parser_exceptions.MissingTerminator) as exc_info:
        parse(
            "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
            + "    define the position<run>.\n"
            + "    it happens when {\n"
            + "        the position<run> has a particle\n"
            + "    } and it does {\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.token == "\n"
    assert exc_info.value.token.type == "NEWLINE"
    assert exc_info.value.line == 4
    assert exc_info.value.column == 41


def test_missing_space_before_has_a_particle(parse: Parse) -> None:
    with pytest.raises(parser_exceptions.InvalidHasAParticleSyntax) as exc_info:
        parse(
            "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
            + "    define the position<run>.\n"
            + "    it happens when {\n"
            + "        the position<run>has a particle.\n"
            + "    } and it does {\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.line == 4
    assert exc_info.value.column == 26


def test_missing_has_a_particle(parse: Parse) -> None:
    with pytest.raises(parser_exceptions.InvalidHasAParticleSyntax) as exc_info:
        parse(
            "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
            + "    define the position<run>.\n"
            + "    it happens when {\n"
            + "        the position<run>.\n"
            + "    } and it does {\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.token == "."
    assert exc_info.value.token.type == "DOT"
    assert exc_info.value.line == 4
    assert exc_info.value.column == 26
