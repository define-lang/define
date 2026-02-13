# pyright: reportUnusedCallResult=false
"""Position definition parser tests.

Follow parser test authoring rules in parser_tests/AGENTS.md.
"""

import pytest

from define.compiler import parser, parser_exceptions
from define.compiler.parser_tests.test_helpers import get_tokens_by_type


def test_position_definition_parses(p: parser.Parser) -> None:
    tree = p.parse("define the potential position<mv:define-lang.org:parser:/path>.\n")
    assert get_tokens_by_type(tree, "MULTIVERSE_NAME") == ["mv"]
    assert get_tokens_by_type(tree, "AUTHORITY_DOMAIN") == ["define-lang.org"]
    assert get_tokens_by_type(tree, "UNIVERSE_NAME") == ["parser"]
    assert get_tokens_by_type(tree, "PATH_SEGMENT") == ["path"]


def test_position_definition_with_constraint_block(p: parser.Parser) -> None:
    tree = p.parse(
        "define the potential position<mv:define-lang.org:parser:/path> {\n"
        + "    it may only contain dimension points where {\n"
        + "        it has the position</child>.\n"
        + "    }\n"
        + "}\n"
    )
    assert get_tokens_by_type(tree, "PATH_SEGMENT") == ["path", "child"]


def test_position_definition_with_multiple_requirements(p: parser.Parser) -> None:
    tree = p.parse(
        "define the potential position<mv:define-lang.org:parser:/path> {\n"
        + "    it may only contain dimension points where {\n"
        + "        it has the position</first>.\n"
        + "        it has the action</second>.\n"
        + "    }\n"
        + "}\n"
    )
    assert get_tokens_by_type(tree, "PATH_SEGMENT") == ["path", "first", "second"]


def test_position_definition_block_requires_constraint_block(p: parser.Parser) -> None:
    with pytest.raises(parser_exceptions.EmptyBlockTerminatorError) as exc_info:
        p.parse("define the potential position<mv:define-lang.org:parser:/path> {\n}\n")
    assert str(exc_info.value.token) == "}"
    assert exc_info.value.line == 2
    assert exc_info.value.column == 1


def test_position_constraint_block_requires_requirements(p: parser.Parser) -> None:
    with pytest.raises(parser_exceptions.EmptyBlockTerminatorError) as exc_info:
        p.parse(
            "define the potential position<mv:define-lang.org:parser:/path> {\n"
            + "    it may only contain dimension points where {\n"
            + "    }\n"
            + "}\n"
        )
    assert str(exc_info.value.token) == "}"
    assert exc_info.value.line == 3
    assert exc_info.value.column == 5


def test_position_definition_rejects_multiple_constraint_blocks(
    p: parser.Parser,
) -> None:
    with pytest.raises(
        parser_exceptions.MultiplePositionConstraintBlocksError
    ) as exc_info:
        p.parse(
            "define the potential position<mv:define-lang.org:parser:/path> {\n"
            + "    it may only contain dimension points where {\n"
            + "        it has the position</first>.\n"
            + "    }\n"
            + "    it may only contain dimension points where {\n"
            + "        it has the action</second>.\n"
            + "    }\n"
            + "}\n"
        )
    assert str(exc_info.value.token) == "it"
    assert exc_info.value.line == 5
    assert exc_info.value.column == 5


def test_action_definition_block_with_mixed_local_position_forms(
    p: parser.Parser,
) -> None:
    tree = p.parse(
        "define the potential action<mv:define-lang.org:parser:/act> {\n"
        + "    define the position<empty_pos>.\n"
        + "    define the position<constrained_pos> {\n"
        + "        it may only contain dimension points where {\n"
        + "            it has the position</child>.\n"
        + "        }\n"
        + "    }\n"
        + "    it happens when {\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    )
    assert get_tokens_by_type(tree, "LOCAL_NAME") == ["empty_pos", "constrained_pos"]
    assert get_tokens_by_type(tree, "PATH_SEGMENT") == ["act", "child"]


def test_action_definition_block_with_multiple_local_block_positions(
    p: parser.Parser,
) -> None:
    tree = p.parse(
        "define the potential action<mv:define-lang.org:parser:/act> {\n"
        + "    define the position<first_pos> {\n"
        + "        it may only contain dimension points where {\n"
        + "            it has the position</first_child>.\n"
        + "        }\n"
        + "    }\n"
        + "    define the position<second_pos> {\n"
        + "        it may only contain dimension points where {\n"
        + "            it has the action</second_child>.\n"
        + "        }\n"
        + "    }\n"
        + "    it happens when {\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    )
    assert get_tokens_by_type(tree, "LOCAL_NAME") == ["first_pos", "second_pos"]
    assert get_tokens_by_type(tree, "PATH_SEGMENT") == [
        "act",
        "first_child",
        "second_child",
    ]


def test_action_statements_block_with_mixed_local_position_forms(
    p: parser.Parser,
) -> None:
    tree = p.parse(
        "define the potential action<mv:define-lang.org:parser:/act> {\n"
        + "    it happens when {\n"
        + "    } and it does {\n"
        + "        define the position<empty_inner>.\n"
        + "        define the position<constrained_inner> {\n"
        + "            it may only contain dimension points where {\n"
        + "                it has the action</inner_action>.\n"
        + "            }\n"
        + "        }\n"
        + "    }\n"
        + "}\n"
    )
    assert get_tokens_by_type(tree, "LOCAL_NAME") == [
        "empty_inner",
        "constrained_inner",
    ]
    assert get_tokens_by_type(tree, "PATH_SEGMENT") == ["act", "inner_action"]


def test_action_statements_block_with_multiple_local_block_positions(
    p: parser.Parser,
) -> None:
    tree = p.parse(
        "define the potential action<mv:define-lang.org:parser:/act> {\n"
        + "    it happens when {\n"
        + "    } and it does {\n"
        + "        define the position<first_inner> {\n"
        + "            it may only contain dimension points where {\n"
        + "                it has the position</first_child>.\n"
        + "            }\n"
        + "        }\n"
        + "        define the position<second_inner> {\n"
        + "            it may only contain dimension points where {\n"
        + "                it has the action</second_child>.\n"
        + "            }\n"
        + "        }\n"
        + "    }\n"
        + "}\n"
    )
    assert get_tokens_by_type(tree, "LOCAL_NAME") == ["first_inner", "second_inner"]
    assert get_tokens_by_type(tree, "PATH_SEGMENT") == [
        "act",
        "first_child",
        "second_child",
    ]
