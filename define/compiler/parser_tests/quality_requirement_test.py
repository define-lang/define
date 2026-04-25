# pyright: reportUnusedCallResult=false
"""Quality Requirement Statement parser tests.

Follow parser test authoring rules in parser_tests/AGENTS.md.
"""

import pytest

from define.compiler import parser_exceptions
from define.compiler.parser_tests.conftest import Parse
from define.compiler.parser_tests.test_helpers import get_tokens_by_type

# --- Successful parses ---


def test_qrs_in_potential_position_before_constraint_block(parse: Parse) -> None:
    tree = parse(
        "define the potential position<mv:define-lang.org:parser:/path> {\n"
        + "    this dimension point must have the position</required>.\n"
        + "    it may only contain dimension points where {\n"
        + "        it has the position</child>.\n"
        + "    }\n"
        + "}\n"
    )
    assert get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/path",
        "/required",
        "/child",
    ]


def test_qrs_in_potential_position_before_init_block_only(parse: Parse) -> None:
    tree = parse(
        "define the potential position<mv:define-lang.org:parser:/path> {\n"
        + "    this dimension point must have the position</required>.\n"
        + "    after it is assigned {\n"
        + "        create a dimension point in position</other>.\n"
        + "    }\n"
        + "}\n"
    )
    assert get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/path",
        "/required",
        "/other",
    ]


def test_qrs_in_potential_position_before_constraint_and_init(parse: Parse) -> None:
    tree = parse(
        "define the potential position<mv:define-lang.org:parser:/path> {\n"
        + "    this dimension point must have the position</required>.\n"
        + "    it may only contain dimension points where {\n"
        + "        it has the position</child>.\n"
        + "    }\n"
        + "    after it is assigned {\n"
        + "        create a dimension point in position</other>.\n"
        + "    }\n"
        + "}\n"
    )
    assert get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/path",
        "/required",
        "/child",
        "/other",
    ]


def test_multiple_qrs_in_potential_position(parse: Parse) -> None:
    tree = parse(
        "define the potential position<mv:define-lang.org:parser:/path> {\n"
        + "    this dimension point must have the position</first>.\n"
        + "    this dimension point must have the action</second>.\n"
        + "    this dimension point must have the position</third>.\n"
        + "    it may only contain dimension points where {\n"
        + "        it has the position</child>.\n"
        + "    }\n"
        + "}\n"
    )
    assert get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/path",
        "/first",
        "/second",
        "/third",
        "/child",
    ]


def test_qrs_with_position_name_type(parse: Parse) -> None:
    tree = parse(
        "define the potential position<mv:define-lang.org:parser:/path> {\n"
        + "    this dimension point must have the position</required>.\n"
        + "    it may only contain dimension points where {\n"
        + "        it has the position</child>.\n"
        + "    }\n"
        + "}\n"
    )
    assert get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/path",
        "/required",
        "/child",
    ]


def test_qrs_with_action_name_type(parse: Parse) -> None:
    tree = parse(
        "define the potential position<mv:define-lang.org:parser:/path> {\n"
        + "    this dimension point must have the action</required>.\n"
        + "    it may only contain dimension points where {\n"
        + "        it has the position</child>.\n"
        + "    }\n"
        + "}\n"
    )
    assert get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/path",
        "/required",
        "/child",
    ]


def test_qrs_with_various_fqun_forms(parse: Parse) -> None:
    tree = parse(
        "define the potential position<mv:define-lang.org:parser:/path> {\n"
        + "    this dimension point must have the position<mv:example.com:my_lib:/full>.\n"
        + "    this dimension point must have the position<example.com:my_lib:/short_mv>.\n"
        + "    this dimension point must have the position<standard:/std>.\n"
        + "    this dimension point must have the position</local>.\n"
        + "    it may only contain dimension points where {\n"
        + "        it has the position</child>.\n"
        + "    }\n"
        + "}\n"
    )
    assert get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/path",
        "mv:example.com:my_lib:/full",
        "example.com:my_lib:/short_mv",
        "standard:/std",
        "/local",
        "/child",
    ]


def test_qrs_in_action_before_local_position(parse: Parse) -> None:
    tree = parse(
        "define the potential action<mv:define-lang.org:parser:/act> {\n"
        + "    this dimension point must have the position</required>.\n"
        + "    define the position<run>.\n"
        + "    it happens when {\n"
        + "        the position<run> has a dimension point.\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    )
    assert get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/act",
        "/required",
    ]
    assert get_tokens_by_type(tree, "LOCAL_NAME_CONTENT") == ["run", "run"]


def test_qrs_in_action_with_no_local_positions(parse: Parse) -> None:
    tree = parse(
        "define the potential action<mv:define-lang.org:parser:/act> {\n"
        + "    this dimension point must have the position</required>.\n"
        + "    it happens when {\n"
        + "        the position<some_local> has a dimension point.\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    )
    assert get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/act",
        "/required",
    ]


def test_multiple_qrs_in_action_before_multiple_local_positions(parse: Parse) -> None:
    tree = parse(
        "define the potential action<mv:define-lang.org:parser:/act> {\n"
        + "    this dimension point must have the position</first>.\n"
        + "    this dimension point must have the action</second>.\n"
        + "    define the position<run>.\n"
        + "    define the position<other>.\n"
        + "    it happens when {\n"
        + "        the position<run> has a dimension point.\n"
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


def test_qrs_with_comments_and_blank_lines(parse: Parse) -> None:
    tree = parse(
        "define the potential position<mv:define-lang.org:parser:/path> {\n"
        + "    # leading comment\n"
        + "    this dimension point must have the position</first>.\n"
        + "\n"
        + "    # between QRS\n"
        + "    this dimension point must have the action</second>.\n"
        + "\n"
        + "    it may only contain dimension points where {\n"
        + "        it has the position</child>.\n"
        + "    }\n"
        + "}\n"
    )
    assert get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/path",
        "/first",
        "/second",
        "/child",
    ]


# --- Statement-level syntax errors ---


def test_qrs_missing_open_angle_at_eol(parse: Parse) -> None:
    with pytest.raises(parser_exceptions.MissingOpenAngleBracket) as exc_info:
        parse(
            "define the potential position<mv:define-lang.org:parser:/path> {\n"
            + "    this dimension point must have the position\n"
            + "    it may only contain dimension points where {\n"
            + "        it has the position</child>.\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.token == "\n"
    assert exc_info.value.line == 2
    assert exc_info.value.column == 48
    assert exc_info.value.name == "\n"


def test_qrs_missing_open_angle_with_terminator(parse: Parse) -> None:
    with pytest.raises(parser_exceptions.MissingOpenAngleBracket) as exc_info:
        parse(
            "define the potential position<mv:define-lang.org:parser:/path> {\n"
            + "    this dimension point must have the position.\n"
            + "    it may only contain dimension points where {\n"
            + "        it has the position</child>.\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.token == "."
    assert exc_info.value.line == 2
    assert exc_info.value.column == 48
    assert exc_info.value.name == "."


def test_qrs_missing_open_angle_with_trailing_space(parse: Parse) -> None:
    with pytest.raises(parser_exceptions.MissingOpenAngleBracket) as exc_info:
        parse(
            "define the potential position<mv:define-lang.org:parser:/path> {\n"
            + "    this dimension point must have the position .\n"
            + "    it may only contain dimension points where {\n"
            + "        it has the position</child>.\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.token == " "
    assert exc_info.value.token.type == "SPACE"
    assert exc_info.value.line == 2
    assert exc_info.value.column == 48
    assert exc_info.value.name == " "


def test_qrs_empty_name(parse: Parse) -> None:
    with pytest.raises(parser_exceptions.EmptyName) as exc_info:
        parse(
            "define the potential position<mv:define-lang.org:parser:/path> {\n"
            + "    this dimension point must have the position<>.\n"
            + "    it may only contain dimension points where {\n"
            + "        it has the position</child>.\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.token == ">"
    assert exc_info.value.line == 2
    assert exc_info.value.column == 49


def test_qrs_newline_inside_name(parse: Parse) -> None:
    with pytest.raises(parser_exceptions.EmptyName) as exc_info:
        parse(
            "define the potential position<mv:define-lang.org:parser:/path> {\n"
            + "    this dimension point must have the position<\n"
            + "        /required>.\n"
            + "    it may only contain dimension points where {\n"
            + "        it has the position</child>.\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.token == "\n"
    assert exc_info.value.line == 2
    assert exc_info.value.column == 49


def test_qrs_missing_close_angle(parse: Parse) -> None:
    with pytest.raises(parser_exceptions.MissingCloseAngleBracket) as exc_info:
        parse(
            "define the potential position<mv:define-lang.org:parser:/path> {\n"
            + "    this dimension point must have the position</required.\n"
            + "    it may only contain dimension points where {\n"
            + "        it has the position</child>.\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.line == 2
    assert exc_info.value.column == 59


def test_qrs_missing_terminator(parse: Parse) -> None:
    with pytest.raises(parser_exceptions.MissingTerminator) as exc_info:
        parse(
            "define the potential position<mv:define-lang.org:parser:/path> {\n"
            + "    this dimension point must have the position</required>\n"
            + "    it may only contain dimension points where {\n"
            + "        it has the position</child>.\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.line == 2
    assert exc_info.value.column == 59


def test_qrs_missing_newline_after_terminator(parse: Parse) -> None:
    with pytest.raises(parser_exceptions.MissingNewlineAfterTerminator) as exc_info:
        parse(
            "define the potential position<mv:define-lang.org:parser:/path> {\n"
            + "    this dimension point must have the position</required>.    this dimension point must have the position</other>.\n"
            + "    it may only contain dimension points where {\n"
            + "        it has the position</child>.\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.token.type == "SPACE"
    assert exc_info.value.token == " "
    assert exc_info.value.line == 2
    assert exc_info.value.column == 60


def test_qrs_missing_space_after_keyword(parse: Parse) -> None:
    with pytest.raises(parser_exceptions.MissingWhitespace) as exc_info:
        parse(
            "define the potential position<mv:define-lang.org:parser:/path> {\n"
            + "    this dimension point must have theposition</required>.\n"
            + "    it may only contain dimension points where {\n"
            + "        it has the position</child>.\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.token == "position"
    assert exc_info.value.token.type == "NAME_TYPE"
    assert exc_info.value.line == 2
    assert exc_info.value.column == 39


def test_qrs_extra_space_after_keyword(parse: Parse) -> None:
    with pytest.raises(parser_exceptions.ExpectedNameType) as exc_info:
        parse(
            "define the potential position<mv:define-lang.org:parser:/path> {\n"
            + "    this dimension point must have the  position</required>.\n"
            + "    it may only contain dimension points where {\n"
            + "        it has the position</child>.\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.line == 2
    assert exc_info.value.column == 40


def test_qrs_local_name_where_global_required(parse: Parse) -> None:
    with pytest.raises(parser_exceptions.InvalidGlobalName) as exc_info:
        parse(
            "define the potential position<mv:define-lang.org:parser:/path> {\n"
            + "    this dimension point must have the position<foo>.\n"
            + "    it may only contain dimension points where {\n"
            + "        it has the position</child>.\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.token == "foo"
    assert exc_info.value.token.type == "LOCAL_NAME_CONTENT"
    assert exc_info.value.line == 2
    assert exc_info.value.column == 49


def test_qrs_chained_name_not_allowed(parse: Parse) -> None:
    with pytest.raises(parser_exceptions.MissingTerminator) as exc_info:
        parse(
            "define the potential position<mv:define-lang.org:parser:/path> {\n"
            + "    this dimension point must have the position</a>::position</b>.\n"
            + "    it may only contain dimension points where {\n"
            + "        it has the position</child>.\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.line == 2
    assert exc_info.value.column == 52


# --- Block-level placement errors ---


def test_qrs_after_constraint_block_in_potential_position(parse: Parse) -> None:
    with pytest.raises(parser_exceptions.QualityRequirementInWrongLocation) as exc_info:
        parse(
            "define the potential position<mv:define-lang.org:parser:/path> {\n"
            + "    it may only contain dimension points where {\n"
            + "        it has the position</child>.\n"
            + "    }\n"
            + "    this dimension point must have the position</required>.\n"
            + "}\n"
        )
    assert exc_info.value.token == "this dimension point must have the"
    assert exc_info.value.token.type == "THIS_DIMENSION_POINT_MUST_HAVE_THE"
    assert exc_info.value.line == 5
    assert exc_info.value.column == 5


def test_qrs_after_init_block_in_potential_position(parse: Parse) -> None:
    with pytest.raises(parser_exceptions.QualityRequirementInWrongLocation) as exc_info:
        parse(
            "define the potential position<mv:define-lang.org:parser:/path> {\n"
            + "    after it is assigned {\n"
            + "        create a dimension point in position</other>.\n"
            + "    }\n"
            + "    this dimension point must have the position</required>.\n"
            + "}\n"
        )
    assert exc_info.value.token == "this dimension point must have the"
    assert exc_info.value.token.type == "THIS_DIMENSION_POINT_MUST_HAVE_THE"
    assert exc_info.value.line == 5
    assert exc_info.value.column == 5


def test_qrs_between_constraint_and_init_block(parse: Parse) -> None:
    with pytest.raises(parser_exceptions.QualityRequirementInWrongLocation) as exc_info:
        parse(
            "define the potential position<mv:define-lang.org:parser:/path> {\n"
            + "    it may only contain dimension points where {\n"
            + "        it has the position</child>.\n"
            + "    }\n"
            + "    this dimension point must have the position</required>.\n"
            + "    after it is assigned {\n"
            + "        create a dimension point in position</other>.\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.token == "this dimension point must have the"
    assert exc_info.value.token.type == "THIS_DIMENSION_POINT_MUST_HAVE_THE"
    assert exc_info.value.line == 5
    assert exc_info.value.column == 5


def test_qrs_after_local_position_in_action_block(parse: Parse) -> None:
    with pytest.raises(parser_exceptions.QualityRequirementInWrongLocation) as exc_info:
        parse(
            "define the potential action<mv:define-lang.org:parser:/act> {\n"
            + "    define the position<run>.\n"
            + "    this dimension point must have the position</required>.\n"
            + "    it happens when {\n"
            + "        the position<run> has a dimension point.\n"
            + "    } and it does {\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.token == "this dimension point must have the"
    assert exc_info.value.token.type == "THIS_DIMENSION_POINT_MUST_HAVE_THE"
    assert exc_info.value.line == 3
    assert exc_info.value.column == 5


def test_qrs_after_trigger_conditions_block_in_action(parse: Parse) -> None:
    with pytest.raises(parser_exceptions.QualityRequirementInWrongLocation) as exc_info:
        parse(
            "define the potential action<mv:define-lang.org:parser:/act> {\n"
            + "    define the position<run>.\n"
            + "    it happens when {\n"
            + "        the position<run> has a dimension point.\n"
            + "    } and it does {\n"
            + "        this dimension point must have the position</required>.\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.token == "this dimension point must have the"
    assert exc_info.value.token.type == "THIS_DIMENSION_POINT_MUST_HAVE_THE"
    assert exc_info.value.line == 6
    assert exc_info.value.column == 9


def test_qrs_inside_position_constraint_block(parse: Parse) -> None:
    with pytest.raises(parser_exceptions.QualityRequirementInWrongLocation) as exc_info:
        parse(
            "define the potential position<mv:define-lang.org:parser:/path> {\n"
            + "    it may only contain dimension points where {\n"
            + "        it has the position</child>.\n"
            + "        this dimension point must have the position</required>.\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.token == "this dimension point must have the"
    assert exc_info.value.token.type == "THIS_DIMENSION_POINT_MUST_HAVE_THE"
    assert exc_info.value.line == 4
    assert exc_info.value.column == 9


def test_qrs_inside_position_initialization_block(parse: Parse) -> None:
    with pytest.raises(parser_exceptions.QualityRequirementInWrongLocation) as exc_info:
        parse(
            "define the potential position<mv:define-lang.org:parser:/path> {\n"
            + "    after it is assigned {\n"
            + "        this dimension point must have the position</required>.\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.token == "this dimension point must have the"
    assert exc_info.value.token.type == "THIS_DIMENSION_POINT_MUST_HAVE_THE"
    assert exc_info.value.line == 3
    assert exc_info.value.column == 9


def test_qrs_inside_action_statements_block(parse: Parse) -> None:
    with pytest.raises(parser_exceptions.QualityRequirementInWrongLocation) as exc_info:
        parse(
            "define the potential action<mv:define-lang.org:parser:/act> {\n"
            + "    define the position<run>.\n"
            + "    it happens when {\n"
            + "        the position<run> has a dimension point.\n"
            + "    } and it does {\n"
            + "        this dimension point must have the position</required>.\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.token == "this dimension point must have the"
    assert exc_info.value.token.type == "THIS_DIMENSION_POINT_MUST_HAVE_THE"
    assert exc_info.value.line == 6
    assert exc_info.value.column == 9


def test_qrs_inside_trigger_conditions_block(parse: Parse) -> None:
    with pytest.raises(parser_exceptions.QualityRequirementInWrongLocation) as exc_info:
        parse(
            "define the potential action<mv:define-lang.org:parser:/act> {\n"
            + "    define the position<run>.\n"
            + "    it happens when {\n"
            + "        this dimension point must have the position</required>.\n"
            + "    } and it does {\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.token == "this dimension point must have the"
    assert exc_info.value.token.type == "THIS_DIMENSION_POINT_MUST_HAVE_THE"
    assert exc_info.value.line == 4
    assert exc_info.value.column == 9


def test_qrs_inside_local_position_definition_constraint_block(parse: Parse) -> None:
    with pytest.raises(parser_exceptions.QualityRequirementInWrongLocation) as exc_info:
        parse(
            "define the potential action<mv:define-lang.org:parser:/act> {\n"
            + "    define the position<inner> {\n"
            + "        it may only contain dimension points where {\n"
            + "            this dimension point must have the position</required>.\n"
            + "        }\n"
            + "    }\n"
            + "    it happens when {\n"
            + "        the position<inner> has a dimension point.\n"
            + "    } and it does {\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.token == "this dimension point must have the"
    assert exc_info.value.token.type == "THIS_DIMENSION_POINT_MUST_HAVE_THE"
    assert exc_info.value.line == 4
    assert exc_info.value.column == 13


def test_qrs_at_global_scope(parse: Parse) -> None:
    with pytest.raises(parser_exceptions.ExpectedGlobalDefinition) as exc_info:
        parse(
            "this dimension point must have the position</required>.\n"
            + "define the potential position<mv:define-lang.org:parser:/path>.\n"
        )
    assert exc_info.value.token == "this dimension point must have the"
    assert exc_info.value.token.type == "THIS_DIMENSION_POINT_MUST_HAVE_THE"
    assert exc_info.value.line == 1
    assert exc_info.value.column == 1


# --- Block content errors ---


def test_qrs_only_in_potential_position_block(parse: Parse) -> None:
    with pytest.raises(
        parser_exceptions.MissingPotentialPositionDefinitionContent
    ) as exc_info:
        parse(
            "define the potential position<mv:define-lang.org:parser:/path> {\n"
            + "    this dimension point must have the position</required>.\n"
            + "}\n"
        )
    assert exc_info.value.token == "}"
    assert exc_info.value.line == 3
    assert exc_info.value.column == 1


def test_qrs_only_in_action_definition_block(parse: Parse) -> None:
    with pytest.raises(parser_exceptions.MissingActionDefinitionSyntax) as exc_info:
        parse(
            "define the potential action<mv:define-lang.org:parser:/act> {\n"
            + "    this dimension point must have the position</required>.\n"
            + "}\n"
        )
    assert exc_info.value.token == "}"
    assert exc_info.value.line == 3
    assert exc_info.value.column == 1
