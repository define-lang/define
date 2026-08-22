# pyright: reportUnusedCallResult=false
"""Position definition parser tests.

Follow parser test authoring rules in parser_tests/AGENTS.md.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from define.compiler import parser_exceptions
from define.compiler.parser_tests.test_helpers import get_tokens_by_type

if TYPE_CHECKING:
    from define.compiler.parser_tests.conftest import Parse


def test_position_definition_parses(parse: Parse) -> None:
    tree = parse("define the potential position<mv:define-lang.org:parser:/path>.\n")
    assert get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/path"
    ]
    assert get_tokens_by_type(tree, "LOCAL_NAME_CONTENT") == []


def test_position_definition_with_local_style_name_is_global_terminal(
    parse: Parse,
) -> None:
    with pytest.raises(parser_exceptions.InvalidGlobalName) as exc_info:
        parse("define the potential position<foo>.\n")
    assert exc_info.value.token == "foo"
    assert exc_info.value.token.type == "LOCAL_NAME_CONTENT"
    assert exc_info.value.line == 1
    assert exc_info.value.column == 31


def test_position_definition_missing_open_angle(parse: Parse) -> None:
    with pytest.raises(parser_exceptions.MissingOpenAngleBracket) as exc_info:
        parse("define the potential positionstandard:/path>.\n")
    assert str(exc_info.value.token) == "standard:/path"
    assert exc_info.value.line == 1
    assert exc_info.value.column == 30
    assert exc_info.value.name == "standard:/path"


def test_position_definition_space_instead_of_open_angle(parse: Parse) -> None:
    with pytest.raises(parser_exceptions.MissingOpenAngleBracket) as exc_info:
        parse("define the potential position mv:define-lang.org:parser:/path>.\n")
    assert exc_info.value.token == " "
    assert exc_info.value.token.type == "SPACE"
    assert exc_info.value.name == " "
    assert exc_info.value.line == 1
    assert exc_info.value.column == 30


def test_position_definition_with_control_character(parse: Parse) -> None:
    with pytest.raises(parser_exceptions.ExpectedGlobalDefinition) as exc_info:
        parse("define the potential \x00position<mv:define-lang.org:parser:/path>.\n")
    assert exc_info.value.token == "define"
    assert exc_info.value.token.type == "LOCAL_NAME_CONTENT"
    assert exc_info.value.line == 1
    assert exc_info.value.column == 1


def test_position_definition_with_empty_global_path(parse: Parse) -> None:
    with pytest.raises(parser_exceptions.InvalidGlobalName) as exc_info:
        parse("define the potential position<mv:define-lang.org:parser:>.\n")
    assert exc_info.value.token == "mv"
    assert exc_info.value.token.type == "LOCAL_NAME_CONTENT"
    assert exc_info.value.line == 1
    assert exc_info.value.column == 31


def test_position_definition_with_global_path_missing_leading_slash(
    parse: Parse,
) -> None:
    with pytest.raises(parser_exceptions.InvalidGlobalName) as exc_info:
        parse("define the potential position<mv:define-lang.org:parser:path>.\n")
    assert exc_info.value.token == "mv"
    assert exc_info.value.token.type == "LOCAL_NAME_CONTENT"
    assert exc_info.value.line == 1
    assert exc_info.value.column == 31


def test_position_definition_empty_name_content(parse: Parse) -> None:
    with pytest.raises(parser_exceptions.EmptyName) as exc_info:
        parse("define the potential position<>.\n")
    assert str(exc_info.value.token) == ">"
    assert exc_info.value.line == 1
    assert exc_info.value.column == 31


def test_position_definition_empty_name_at_eof(parse: Parse) -> None:
    with pytest.raises(parser_exceptions.EmptyName) as exc_info:
        parse("define the potential position<")
    assert exc_info.value.token.type == "$END"
    assert exc_info.value.line == 1
    assert exc_info.value.column == 30


def test_position_definition_with_constraint_block(parse: Parse) -> None:
    tree = parse(
        "define the potential position<mv:define-lang.org:parser:/path> {\n"
        + "    it may only contain particles where {\n"
        + "        it has the position</child>.\n"
        + "    }\n"
        + "}\n"
    )
    assert get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/path",
        "/child",
    ]
    assert get_tokens_by_type(tree, "LOCAL_NAME_CONTENT") == []


def test_position_definition_with_multiple_requirements(parse: Parse) -> None:
    tree = parse(
        "define the potential position<mv:define-lang.org:parser:/path> {\n"
        + "    it may only contain particles where {\n"
        + "        it has the position</first>.\n"
        + "        it has the action</second>.\n"
        + "    }\n"
        + "}\n"
    )
    assert get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/path",
        "/first",
        "/second",
    ]
    assert get_tokens_by_type(tree, "LOCAL_NAME_CONTENT") == []


def test_position_definition_block_requires_content(parse: Parse) -> None:
    with pytest.raises(
        parser_exceptions.MissingPotentialPositionDefinitionContent
    ) as exc_info:
        parse("define the potential position<mv:define-lang.org:parser:/path> {\n}\n")
    assert str(exc_info.value.token) == "}"
    assert exc_info.value.line == 2
    assert exc_info.value.column == 1


def test_position_constraint_block_requires_requirements(parse: Parse) -> None:
    with pytest.raises(parser_exceptions.MissingPositionConstraintContent) as exc_info:
        parse(
            "define the potential position<mv:define-lang.org:parser:/path> {\n"
            + "    it may only contain particles where {\n"
            + "    }\n"
            + "}\n"
        )
    assert str(exc_info.value.token) == "}"
    assert exc_info.value.line == 3
    assert exc_info.value.column == 5


def test_position_constraint_block_with_invalid_statement_then_more_definitions(
    parse: Parse,
) -> None:
    with pytest.raises(parser_exceptions.InvalidPositionConstraintBlock) as exc_info:
        parse(
            "define the potential position<my_lib:/path>.\n"
            + "define the potential position<my_lib:/path> {\n"
            + "    it may only contain particles where {\n"
            + "        t has the position<my_lib:/path>.\n"
            + "    }\n"
            + "}\n"
            + "define the potential position<my_lib:/path>.\n"
        )
    assert str(exc_info.value.token) == "t"
    assert exc_info.value.line == 4
    assert exc_info.value.column == 9


def test_position_definition_rejects_multiple_constraint_blocks(
    parse: Parse,
) -> None:
    with pytest.raises(parser_exceptions.MissingCloseBrace) as exc_info:
        parse(
            "define the potential position<mv:define-lang.org:parser:/path> {\n"
            + "    it may only contain particles where {\n"
            + "        it has the position</first>.\n"
            + "    }\n"
            + "    it may only contain particles where {\n"
            + "        it has the action</second>.\n"
            + "    }\n"
            + "}\n"
        )
    assert str(exc_info.value.token).startswith("it may only contain")
    assert exc_info.value.line == 5
    assert exc_info.value.column == 5


def test_second_constraint_block_after_close_on_same_line(
    parse: Parse,
) -> None:
    with pytest.raises(parser_exceptions.MissingNewlineAfterCloseBrace) as exc_info:
        parse(
            "define the potential position<mv:define-lang.org:parser:/path> {\n"
            + "    it may only contain particles where {\n"
            + "        it has the position</first>.\n"
            + "    }    it may only contain particles where {\n"
            + "        it has the action</second>.\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.token.type == "SPACE"
    assert str(exc_info.value.token) == " "
    assert exc_info.value.line == 4
    assert exc_info.value.column == 6


def test_second_constraint_block_on_requirement_line(
    parse: Parse,
) -> None:
    with pytest.raises(parser_exceptions.MissingNewlineAfterTerminator) as exc_info:
        parse(
            "define the potential position<mv:define-lang.org:parser:/path> {\n"
            + "    it may only contain particles where {\n"
            + "        it has the position</first>.    it may only contain particles where {\n"
            + "        it has the action</second>.\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.token.type == "SPACE"
    assert str(exc_info.value.token) == " "
    assert exc_info.value.line == 3
    assert exc_info.value.column == 37


def test_action_definition_block_with_mixed_local_position_forms(
    parse: Parse,
) -> None:
    tree = parse(
        "define the potential action<mv:define-lang.org:parser:/act> {\n"
        + "    define the position<run>.\n"
        + "    define the position<empty_pos>.\n"
        + "    define the position<constrained_pos> {\n"
        + "        it may only contain particles where {\n"
        + "            it has the position</child>.\n"
        + "        }\n"
        + "    }\n"
        + "    it happens when {\n"
        + "        the position<run> has a particle.\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    )
    assert get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/act",
        "/child",
    ]
    assert get_tokens_by_type(tree, "LOCAL_NAME_CONTENT") == [
        "run",
        "empty_pos",
        "constrained_pos",
        "run",
    ]


def test_action_definition_block_with_multiple_local_block_positions(
    parse: Parse,
) -> None:
    tree = parse(
        "define the potential action<mv:define-lang.org:parser:/act> {\n"
        + "    define the position<run>.\n"
        + "    define the position<first_pos> {\n"
        + "        it may only contain particles where {\n"
        + "            it has the position</first_child>.\n"
        + "        }\n"
        + "    }\n"
        + "    define the position<second_pos> {\n"
        + "        it may only contain particles where {\n"
        + "            it has the action</second_child>.\n"
        + "        }\n"
        + "    }\n"
        + "    it happens when {\n"
        + "        the position<run> has a particle.\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    )
    assert get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/act",
        "/first_child",
        "/second_child",
    ]
    assert get_tokens_by_type(tree, "LOCAL_NAME_CONTENT") == [
        "run",
        "first_pos",
        "second_pos",
        "run",
    ]


def test_action_statements_block_with_mixed_local_position_forms(
    parse: Parse,
) -> None:
    tree = parse(
        "define the potential action<mv:define-lang.org:parser:/act> {\n"
        + "    define the position<run>.\n"
        + "    it happens when {\n"
        + "        the position<run> has a particle.\n"
        + "    } and it does {\n"
        + "        define the position<empty_inner>.\n"
        + "        define the position<constrained_inner> {\n"
        + "            it may only contain particles where {\n"
        + "                it has the action</inner_action>.\n"
        + "            }\n"
        + "        }\n"
        + "    }\n"
        + "}\n"
    )
    assert get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/act",
        "/inner_action",
    ]
    assert get_tokens_by_type(tree, "LOCAL_NAME_CONTENT") == [
        "run",
        "run",
        "empty_inner",
        "constrained_inner",
    ]


def test_action_statements_block_with_multiple_local_block_positions(
    parse: Parse,
) -> None:
    tree = parse(
        "define the potential action<mv:define-lang.org:parser:/act> {\n"
        + "    define the position<run>.\n"
        + "    it happens when {\n"
        + "        the position<run> has a particle.\n"
        + "    } and it does {\n"
        + "        define the position<first_inner> {\n"
        + "            it may only contain particles where {\n"
        + "                it has the position</first_child>.\n"
        + "            }\n"
        + "        }\n"
        + "        define the position<second_inner> {\n"
        + "            it may only contain particles where {\n"
        + "                it has the action</second_child>.\n"
        + "            }\n"
        + "        }\n"
        + "    }\n"
        + "}\n"
    )
    assert get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/act",
        "/first_child",
        "/second_child",
    ]
    assert get_tokens_by_type(tree, "LOCAL_NAME_CONTENT") == [
        "run",
        "run",
        "first_inner",
        "second_inner",
    ]


def test_empty_potential_position_block(parse: Parse) -> None:
    with pytest.raises(
        parser_exceptions.MissingPotentialPositionDefinitionContent
    ) as exc_info:
        parse("define the potential position<standard:/path> {\n}\n")
    assert str(exc_info.value.token) == "}"
    assert exc_info.value.line == 2
    assert exc_info.value.column == 1


def test_invalid_content_in_potential_position_block(parse: Parse) -> None:
    with pytest.raises(
        parser_exceptions.InvalidPotentialPositionDefinitionBlock
    ) as exc_info:
        parse(
            "define the potential position<standard:/path> {\n"
            + "    nonsense here\n"
            + "}\n"
        )
    assert str(exc_info.value.token) == "nonsense"
    assert exc_info.value.token.type == "LOCAL_NAME_CONTENT"
    assert exc_info.value.line == 2
    assert exc_info.value.column == 5


def test_empty_local_position_definition_block(parse: Parse) -> None:
    with pytest.raises(parser_exceptions.MissingPositionDefinitionContent) as exc_info:
        parse(
            "define the potential action<standard:/act> {\n"
            + "    define the position<bad> {\n"
            + "    }\n"
            + "    it happens when {\n"
            + "        the position<bad> has a particle.\n"
            + "    } and it does {\n"
            + "    }\n"
            + "}\n"
        )
    assert str(exc_info.value.token) == "}"
    assert exc_info.value.line == 3
    assert exc_info.value.column == 5


def test_invalid_content_in_local_position_definition_block(parse: Parse) -> None:
    with pytest.raises(parser_exceptions.InvalidPositionDefinitionBlock) as exc_info:
        parse(
            "define the potential action<standard:/act> {\n"
            + "    define the position<bad> {\n"
            + "        nonsense here\n"
            + "    }\n"
            + "    it happens when {\n"
            + "        the position<bad> has a particle.\n"
            + "    } and it does {\n"
            + "    }\n"
            + "}\n"
        )
    assert str(exc_info.value.token) == "nonsense"
    assert exc_info.value.token.type == "LOCAL_NAME_CONTENT"
    assert exc_info.value.line == 3
    assert exc_info.value.column == 9
