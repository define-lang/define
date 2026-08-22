# pyright: reportUnusedCallResult=false
"""Quality Implication Statement parser tests.

Follow parser test authoring rules in parser_tests/AGENTS.md.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from define.compiler import parser_exceptions
from define.compiler.parser_tests.test_helpers import get_tokens_by_type

if TYPE_CHECKING:
    from define.compiler.parser_tests.conftest import Parse

# --- Successful parses ---


def test_implication_in_potential_position_before_constraint_block(
    parse: Parse,
) -> None:
    tree = parse(
        "define the potential position<mv:define-lang.org:parser:/path> {\n"
        + "    it also assigns the position</required>.\n"
        + "    it may only contain particles where {\n"
        + "        it has the position</implied>.\n"
        + "    }\n"
        + "}\n"
    )
    assert get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/path",
        "/required",
        "/implied",
    ]


def test_multiple_implications_in_potential_position(parse: Parse) -> None:
    tree = parse(
        "define the potential position<mv:define-lang.org:parser:/path> {\n"
        + "    it also assigns the position</first>.\n"
        + "    it also assigns the action</second>.\n"
        + "    it also assigns the position</third>.\n"
        + "    it may only contain particles where {\n"
        + "        it has the position</implied>.\n"
        + "    }\n"
        + "}\n"
    )
    assert get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/path",
        "/first",
        "/second",
        "/third",
        "/implied",
    ]


def test_implication_with_position_name_type(parse: Parse) -> None:
    tree = parse(
        "define the potential position<mv:define-lang.org:parser:/path> {\n"
        + "    it also assigns the position</required>.\n"
        + "    it may only contain particles where {\n"
        + "        it has the position</implied>.\n"
        + "    }\n"
        + "}\n"
    )
    assert get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/path",
        "/required",
        "/implied",
    ]


def test_implication_with_action_name_type(parse: Parse) -> None:
    tree = parse(
        "define the potential position<mv:define-lang.org:parser:/path> {\n"
        + "    it also assigns the action</required>.\n"
        + "    it may only contain particles where {\n"
        + "        it has the position</implied>.\n"
        + "    }\n"
        + "}\n"
    )
    assert get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/path",
        "/required",
        "/implied",
    ]


def test_implication_with_various_fqun_forms(parse: Parse) -> None:
    tree = parse(
        "define the potential position<mv:define-lang.org:parser:/path> {\n"
        + "    it also assigns the position<mv:example.com:my_lib:/full>.\n"
        + "    it also assigns the position<example.com:my_lib:/short_mv>.\n"
        + "    it also assigns the position<standard:/std>.\n"
        + "    it also assigns the position</local>.\n"
        + "    it may only contain particles where {\n"
        + "        it has the position</implied>.\n"
        + "    }\n"
        + "}\n"
    )
    assert get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/path",
        "mv:example.com:my_lib:/full",
        "example.com:my_lib:/short_mv",
        "standard:/std",
        "/local",
        "/implied",
    ]


def test_implication_in_action_before_local_position(parse: Parse) -> None:
    tree = parse(
        "define the potential action<mv:define-lang.org:parser:/act> {\n"
        + "    it also assigns the position</required>.\n"
        + "    define the position<run>.\n"
        + "    it happens when {\n"
        + "        the position<run> has a particle.\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    )
    assert get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/act",
        "/required",
    ]
    assert get_tokens_by_type(tree, "LOCAL_NAME_CONTENT") == ["run", "run"]


def test_implication_in_action_with_no_local_positions(parse: Parse) -> None:
    tree = parse(
        "define the potential action<mv:define-lang.org:parser:/act> {\n"
        + "    it also assigns the position</required>.\n"
        + "    it happens when {\n"
        + "        the position<some_local> has a particle.\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    )
    assert get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/act",
        "/required",
    ]


def test_multiple_implications_in_action_before_multiple_local_positions(
    parse: Parse,
) -> None:
    tree = parse(
        "define the potential action<mv:define-lang.org:parser:/act> {\n"
        + "    it also assigns the position</first>.\n"
        + "    it also assigns the action</second>.\n"
        + "    define the position<run>.\n"
        + "    define the position<other>.\n"
        + "    it happens when {\n"
        + "        the position<run> has a particle.\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    )
    assert get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/act",
        "/first",
        "/second",
    ]
    assert get_tokens_by_type(tree, "LOCAL_NAME_CONTENT") == ["run", "other", "run"]


def test_implication_with_comments_and_blank_lines(parse: Parse) -> None:
    tree = parse(
        "define the potential position<mv:define-lang.org:parser:/path> {\n"
        + "    # leading comment\n"
        + "    it also assigns the position</first>.\n"
        + "\n"
        + "    # between implications\n"
        + "    it also assigns the action</second>.\n"
        + "\n"
        + "    it may only contain particles where {\n"
        + "        it has the position</implied>.\n"
        + "    }\n"
        + "}\n"
    )
    assert get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/path",
        "/first",
        "/second",
        "/implied",
    ]


# --- Statement-level syntax errors ---


def test_implication_missing_open_angle_at_eol(parse: Parse) -> None:
    with pytest.raises(parser_exceptions.MissingOpenAngleBracket) as exc_info:
        parse(
            "define the potential position<mv:define-lang.org:parser:/path> {\n"
            + "    it also assigns the position\n"
            + "    it may only contain particles where {\n"
            + "        it has the position</implied>.\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.token == "\n"
    assert exc_info.value.line == 2
    assert exc_info.value.column == 33
    assert exc_info.value.name == "\n"


def test_implication_missing_open_angle_with_terminator(parse: Parse) -> None:
    with pytest.raises(parser_exceptions.MissingOpenAngleBracket) as exc_info:
        parse(
            "define the potential position<mv:define-lang.org:parser:/path> {\n"
            + "    it also assigns the position.\n"
            + "    it may only contain particles where {\n"
            + "        it has the position</implied>.\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.token == "."
    assert exc_info.value.line == 2
    assert exc_info.value.column == 33
    assert exc_info.value.name == "."


def test_implication_missing_open_angle_with_trailing_space(parse: Parse) -> None:
    with pytest.raises(parser_exceptions.MissingOpenAngleBracket) as exc_info:
        parse(
            "define the potential position<mv:define-lang.org:parser:/path> {\n"
            + "    it also assigns the position .\n"
            + "    it may only contain particles where {\n"
            + "        it has the position</implied>.\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.token == " "
    assert exc_info.value.token.type == "SPACE"
    assert exc_info.value.line == 2
    assert exc_info.value.column == 33
    assert exc_info.value.name == " "


def test_implication_empty_name(parse: Parse) -> None:
    with pytest.raises(parser_exceptions.EmptyName) as exc_info:
        parse(
            "define the potential position<mv:define-lang.org:parser:/path> {\n"
            + "    it also assigns the position<>.\n"
            + "    it may only contain particles where {\n"
            + "        it has the position</implied>.\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.token == ">"
    assert exc_info.value.line == 2
    assert exc_info.value.column == 34


def test_implication_newline_inside_name(parse: Parse) -> None:
    with pytest.raises(parser_exceptions.EmptyName) as exc_info:
        parse(
            "define the potential position<mv:define-lang.org:parser:/path> {\n"
            + "    it also assigns the position<\n"
            + "        /required>.\n"
            + "    it may only contain particles where {\n"
            + "        it has the position</implied>.\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.token == "\n"
    assert exc_info.value.line == 2
    assert exc_info.value.column == 34


def test_implication_missing_close_angle(parse: Parse) -> None:
    with pytest.raises(parser_exceptions.MissingCloseAngleBracket) as exc_info:
        parse(
            "define the potential position<mv:define-lang.org:parser:/path> {\n"
            + "    it also assigns the position</required.\n"
            + "    it may only contain particles where {\n"
            + "        it has the position</implied>.\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.line == 2
    assert exc_info.value.column == 44


def test_implication_missing_terminator(parse: Parse) -> None:
    with pytest.raises(parser_exceptions.MissingTerminator) as exc_info:
        parse(
            "define the potential position<mv:define-lang.org:parser:/path> {\n"
            + "    it also assigns the position</required>\n"
            + "    it may only contain particles where {\n"
            + "        it has the position</implied>.\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.line == 2
    assert exc_info.value.column == 44


def test_implication_missing_newline_after_terminator(parse: Parse) -> None:
    with pytest.raises(parser_exceptions.MissingNewlineAfterTerminator) as exc_info:
        parse(
            "define the potential position<mv:define-lang.org:parser:/path> {\n"
            + "    it also assigns the position</required>.    it also assigns the position</other>.\n"
            + "    it may only contain particles where {\n"
            + "        it has the position</implied>.\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.token.type == "SPACE"
    assert exc_info.value.token == " "
    assert exc_info.value.line == 2
    assert exc_info.value.column == 45


def test_implication_missing_space_after_keyword(parse: Parse) -> None:
    with pytest.raises(parser_exceptions.MissingWhitespace) as exc_info:
        parse(
            "define the potential position<mv:define-lang.org:parser:/path> {\n"
            + "    it also assigns theposition</required>.\n"
            + "    it may only contain particles where {\n"
            + "        it has the position</implied>.\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.token == "position"
    assert exc_info.value.token.type == "NAME_TYPE"
    assert exc_info.value.line == 2
    assert exc_info.value.column == 24


def test_implication_extra_space_after_keyword(parse: Parse) -> None:
    with pytest.raises(parser_exceptions.ExpectedNameType) as exc_info:
        parse(
            "define the potential position<mv:define-lang.org:parser:/path> {\n"
            + "    it also assigns the  position</required>.\n"
            + "    it may only contain particles where {\n"
            + "        it has the position</implied>.\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.line == 2
    assert exc_info.value.column == 25


def test_implication_local_name_where_global_required(parse: Parse) -> None:
    with pytest.raises(parser_exceptions.InvalidGlobalName) as exc_info:
        parse(
            "define the potential position<mv:define-lang.org:parser:/path> {\n"
            + "    it also assigns the position<foo>.\n"
            + "    it may only contain particles where {\n"
            + "        it has the position</implied>.\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.token == "foo"
    assert exc_info.value.token.type == "LOCAL_NAME_CONTENT"
    assert exc_info.value.line == 2
    assert exc_info.value.column == 34


def test_implication_chained_name_not_allowed(parse: Parse) -> None:
    with pytest.raises(parser_exceptions.MissingTerminator) as exc_info:
        parse(
            "define the potential position<mv:define-lang.org:parser:/path> {\n"
            + "    it also assigns the position</a>::position</b>.\n"
            + "    it may only contain particles where {\n"
            + "        it has the position</implied>.\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.line == 2
    assert exc_info.value.column == 37


# --- Block-level placement errors ---


def test_implication_after_constraint_block_in_potential_position(parse: Parse) -> None:
    with pytest.raises(parser_exceptions.QualityImplicationInWrongLocation) as exc_info:
        parse(
            "define the potential position<mv:define-lang.org:parser:/path> {\n"
            + "    it may only contain particles where {\n"
            + "        it has the position</implied>.\n"
            + "    }\n"
            + "    it also assigns the position</required>.\n"
            + "}\n"
        )
    assert exc_info.value.token == "it also assigns the"
    assert exc_info.value.token.type == "IT_ALSO_ASSIGNS_THE"
    assert exc_info.value.line == 5
    assert exc_info.value.column == 5


def test_implication_after_local_position_in_action_block(parse: Parse) -> None:
    with pytest.raises(parser_exceptions.QualityImplicationInWrongLocation) as exc_info:
        parse(
            "define the potential action<mv:define-lang.org:parser:/act> {\n"
            + "    define the position<run>.\n"
            + "    it also assigns the position</required>.\n"
            + "    it happens when {\n"
            + "        the position<run> has a particle.\n"
            + "    } and it does {\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.token == "it also assigns the"
    assert exc_info.value.token.type == "IT_ALSO_ASSIGNS_THE"
    assert exc_info.value.line == 3
    assert exc_info.value.column == 5


def test_implication_after_trigger_conditions_block_in_action(parse: Parse) -> None:
    with pytest.raises(parser_exceptions.QualityImplicationInWrongLocation) as exc_info:
        parse(
            "define the potential action<mv:define-lang.org:parser:/act> {\n"
            + "    define the position<run>.\n"
            + "    it happens when {\n"
            + "        the position<run> has a particle.\n"
            + "    } and it does {\n"
            + "        it also assigns the position</required>.\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.token == "it also assigns the"
    assert exc_info.value.token.type == "IT_ALSO_ASSIGNS_THE"
    assert exc_info.value.line == 6
    assert exc_info.value.column == 9


def test_implication_inside_position_constraint_block(parse: Parse) -> None:
    with pytest.raises(parser_exceptions.QualityImplicationInWrongLocation) as exc_info:
        parse(
            "define the potential position<mv:define-lang.org:parser:/path> {\n"
            + "    it may only contain particles where {\n"
            + "        it has the position</implied>.\n"
            + "        it also assigns the position</required>.\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.token == "it also assigns the"
    assert exc_info.value.token.type == "IT_ALSO_ASSIGNS_THE"
    assert exc_info.value.line == 4
    assert exc_info.value.column == 9


def test_implication_inside_action_statements_block(parse: Parse) -> None:
    with pytest.raises(parser_exceptions.QualityImplicationInWrongLocation) as exc_info:
        parse(
            "define the potential action<mv:define-lang.org:parser:/act> {\n"
            + "    define the position<run>.\n"
            + "    it happens when {\n"
            + "        the position<run> has a particle.\n"
            + "    } and it does {\n"
            + "        it also assigns the position</required>.\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.token == "it also assigns the"
    assert exc_info.value.token.type == "IT_ALSO_ASSIGNS_THE"
    assert exc_info.value.line == 6
    assert exc_info.value.column == 9


def test_implication_inside_trigger_conditions_block(parse: Parse) -> None:
    with pytest.raises(parser_exceptions.QualityImplicationInWrongLocation) as exc_info:
        parse(
            "define the potential action<mv:define-lang.org:parser:/act> {\n"
            + "    define the position<run>.\n"
            + "    it happens when {\n"
            + "        it also assigns the position</required>.\n"
            + "    } and it does {\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.token == "it also assigns the"
    assert exc_info.value.token.type == "IT_ALSO_ASSIGNS_THE"
    assert exc_info.value.line == 4
    assert exc_info.value.column == 9


def test_implication_inside_local_position_definition_constraint_block(
    parse: Parse,
) -> None:
    with pytest.raises(parser_exceptions.QualityImplicationInWrongLocation) as exc_info:
        parse(
            "define the potential action<mv:define-lang.org:parser:/act> {\n"
            + "    define the position<inner> {\n"
            + "        it may only contain particles where {\n"
            + "            it also assigns the position</required>.\n"
            + "        }\n"
            + "    }\n"
            + "    it happens when {\n"
            + "        the position<inner> has a particle.\n"
            + "    } and it does {\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.token == "it also assigns the"
    assert exc_info.value.token.type == "IT_ALSO_ASSIGNS_THE"
    assert exc_info.value.line == 4
    assert exc_info.value.column == 13


def test_implication_at_global_scope(parse: Parse) -> None:
    with pytest.raises(parser_exceptions.ExpectedGlobalDefinition) as exc_info:
        parse(
            "it also assigns the position</required>.\n"
            + "define the potential position<mv:define-lang.org:parser:/path>.\n"
        )
    assert exc_info.value.token == "it also assigns the"
    assert exc_info.value.token.type == "IT_ALSO_ASSIGNS_THE"
    assert exc_info.value.line == 1
    assert exc_info.value.column == 1


# --- Block content errors ---


def test_implication_only_in_potential_position_block(parse: Parse) -> None:
    with pytest.raises(
        parser_exceptions.MissingPotentialPositionDefinitionContent
    ) as exc_info:
        parse(
            "define the potential position<mv:define-lang.org:parser:/path> {\n"
            + "    it also assigns the position</required>.\n"
            + "}\n"
        )
    assert exc_info.value.token == "}"
    assert exc_info.value.line == 3
    assert exc_info.value.column == 1


def test_implication_only_in_action_definition_block(parse: Parse) -> None:
    with pytest.raises(parser_exceptions.MissingActionDefinitionSyntax) as exc_info:
        parse(
            "define the potential action<mv:define-lang.org:parser:/act> {\n"
            + "    it also assigns the position</required>.\n"
            + "}\n"
        )
    assert exc_info.value.token == "}"
    assert exc_info.value.line == 3
    assert exc_info.value.column == 1
