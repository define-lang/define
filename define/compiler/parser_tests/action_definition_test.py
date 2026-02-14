# pyright: reportUnusedCallResult=false
"""Action definition parser tests.

Follow parser test authoring rules in parser_tests/AGENTS.md.
"""

import pytest

from define.compiler import parser, parser_exceptions
from define.compiler.parser_tests.test_helpers import get_tokens_by_type


def test_action_definition_parses(p: parser.Parser) -> None:
    tree = p.parse("define the potential action<standard:/path>.\n")
    assert get_tokens_by_type(tree, "NAME_CONTENT") == ["standard:/path"]


def test_action_definition_missing_open_angle(p: parser.Parser) -> None:
    with pytest.raises(parser_exceptions.MissingOpenAngleBracketError) as exc_info:
        p.parse("define the potential actionstandard:/path>.\n")
    assert str(exc_info.value.token) == "standard:/path"
    assert exc_info.value.column == 28


def test_action_definition_empty_name_content(p: parser.Parser) -> None:
    with pytest.raises(parser_exceptions.EmptyNameError) as exc_info:
        p.parse("define the potential action<>.\n")
    assert str(exc_info.value.token) == ">"
    assert exc_info.value.column == 29


def test_action_with_empty_inner_blocks(p: parser.Parser) -> None:
    tree = p.parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    it happens when {\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    )
    assert get_tokens_by_type(tree, "NAME_CONTENT") == [
        "mv:define-lang.org:parser:/my_action"
    ]


def test_action_with_local_position_definition(p: parser.Parser) -> None:
    tree = p.parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    define the position<my_pos>.\n"
        + "    it happens when {\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    )
    assert get_tokens_by_type(tree, "NAME_CONTENT") == [
        "mv:define-lang.org:parser:/my_action",
        "my_pos",
    ]


def test_action_with_constrained_local_position_definition(p: parser.Parser) -> None:
    tree = p.parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    define the position<my_pos> {\n"
        + "        it may only contain dimension points where {\n"
        + "            it has the action</do_work>.\n"
        + "        }\n"
        + "    }\n"
        + "    it happens when {\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    )
    assert get_tokens_by_type(tree, "NAME_CONTENT") == [
        "mv:define-lang.org:parser:/my_action",
        "my_pos",
        "/do_work",
    ]


def test_action_with_multiple_local_position_definitions(p: parser.Parser) -> None:
    tree = p.parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    define the position<first_pos>.\n"
        + "    define the position<second_pos>.\n"
        + "    it happens when {\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    )
    assert get_tokens_by_type(tree, "NAME_CONTENT") == [
        "mv:define-lang.org:parser:/my_action",
        "first_pos",
        "second_pos",
    ]


def test_action_with_mixed_local_position_definition_forms(p: parser.Parser) -> None:
    tree = p.parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    define the position<first_pos>.\n"
        + "    define the position<second_pos> {\n"
        + "        it may only contain dimension points where {\n"
        + "            it has the position</child>.\n"
        + "        }\n"
        + "    }\n"
        + "    it happens when {\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    )
    assert get_tokens_by_type(tree, "NAME_CONTENT") == [
        "mv:define-lang.org:parser:/my_action",
        "first_pos",
        "second_pos",
        "/child",
    ]


def test_action_block_with_comments_and_blank_lines(p: parser.Parser) -> None:
    tree = p.parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    define the position<my_pos>.\n"
        + "\n"
        + "    # a comment\n"
        + "    it happens when {\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    )
    assert get_tokens_by_type(tree, "NAME_CONTENT") == [
        "mv:define-lang.org:parser:/my_action",
        "my_pos",
    ]


def test_action_block_with_full_fqun(p: parser.Parser) -> None:
    tree = p.parse(
        "define the potential action<mv:define-lang.org:parser:/some/path> {\n"
        + "    define the position<my_pos>.\n"
        + "    it happens when {\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    )
    assert get_tokens_by_type(tree, "NAME_CONTENT") == [
        "mv:define-lang.org:parser:/some/path",
        "my_pos",
    ]


def test_action_block_comment_after_trigger_open(p: parser.Parser) -> None:
    tree = p.parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    it happens when { # comment\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    )
    assert get_tokens_by_type(tree, "NAME_CONTENT") == [
        "mv:define-lang.org:parser:/my_action"
    ]


def test_action_block_comment_after_action_close(p: parser.Parser) -> None:
    tree = p.parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    it happens when {\n"
        + "    } and it does {\n"
        + "    } # comment\n"
        + "}\n"
    )
    assert get_tokens_by_type(tree, "NAME_CONTENT") == [
        "mv:define-lang.org:parser:/my_action"
    ]


def test_action_block_no_indentation(p: parser.Parser) -> None:
    tree = p.parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "it happens when {\n"
        + "} and it does {\n"
        + "}\n"
        + "}\n"
    )
    assert get_tokens_by_type(tree, "NAME_CONTENT") == [
        "mv:define-lang.org:parser:/my_action"
    ]


def test_action_block_blank_lines_in_trigger_block(p: parser.Parser) -> None:
    tree = p.parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    it happens when {\n"
        + "\n"
        + "\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    )
    assert get_tokens_by_type(tree, "NAME_CONTENT") == [
        "mv:define-lang.org:parser:/my_action"
    ]


def test_action_block_blank_lines_in_action_block(p: parser.Parser) -> None:
    tree = p.parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    it happens when {\n"
        + "    } and it does {\n"
        + "\n"
        + "\n"
        + "    }\n"
        + "}\n"
    )
    assert get_tokens_by_type(tree, "NAME_CONTENT") == [
        "mv:define-lang.org:parser:/my_action"
    ]


def test_action_block_with_local_position_definition_in_action_statements(
    p: parser.Parser,
) -> None:
    tree = p.parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    it happens when {\n"
        + "    } and it does {\n"
        + "        define the position<inner_pos>.\n"
        + "    }\n"
        + "}\n"
    )
    assert get_tokens_by_type(tree, "NAME_CONTENT") == [
        "mv:define-lang.org:parser:/my_action",
        "inner_pos",
    ]


def test_action_block_with_multiple_local_position_definitions_in_action_statements(
    p: parser.Parser,
) -> None:
    tree = p.parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    it happens when {\n"
        + "    } and it does {\n"
        + "        define the position<first_inner>.\n"
        + "        define the position<second_inner>.\n"
        + "    }\n"
        + "}\n"
    )
    assert get_tokens_by_type(tree, "NAME_CONTENT") == [
        "mv:define-lang.org:parser:/my_action",
        "first_inner",
        "second_inner",
    ]


def test_action_block_with_local_position_definitions_inside_and_outside_action_statements(
    p: parser.Parser,
) -> None:
    tree = p.parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    define the position<outer_pos>.\n"
        + "    it happens when {\n"
        + "    } and it does {\n"
        + "        define the position<inner_pos>.\n"
        + "    }\n"
        + "}\n"
    )
    assert get_tokens_by_type(tree, "NAME_CONTENT") == [
        "mv:define-lang.org:parser:/my_action",
        "outer_pos",
        "inner_pos",
    ]


def test_two_action_definitions_in_same_file(p: parser.Parser) -> None:
    tree = p.parse(
        "define the potential action<mv:define-lang.org:parser:/first> {\n"
        + "    it happens when {\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
        + "define the potential action<mv:define-lang.org:parser:/second> {\n"
        + "    define the position<my_pos>.\n"
        + "    it happens when {\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    )
    assert get_tokens_by_type(tree, "NAME_CONTENT") == [
        "mv:define-lang.org:parser:/first",
        "mv:define-lang.org:parser:/second",
        "my_pos",
    ]


def test_action_block_missing_trigger_block(p: parser.Parser) -> None:
    with pytest.raises(parser_exceptions.EmptyBlockTerminatorError) as exc_info:
        p.parse(
            "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
            + "    define the position<my_pos>.\n"
            + "}\n"
        )
    assert str(exc_info.value.token) == "}"
    assert exc_info.value.line == 3
    assert exc_info.value.column == 1


def test_global_position_definition_not_allowed_in_action_definition_block(
    p: parser.Parser,
) -> None:
    with pytest.raises(parser_exceptions.GlobalPositionInLocalScopeError) as exc_info:
        p.parse(
            "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
            + "    define the potential position<mv:define-lang.org:parser:/inner_pos>.\n"
            + "    it happens when {\n"
            + "    } and it does {\n"
            + "    }\n"
            + "}\n"
        )
    assert str(exc_info.value.token).startswith("define the potential position<")
    assert exc_info.value.line == 2
    assert exc_info.value.column == 5


def test_global_position_definition_not_allowed_in_action_statements_block(
    p: parser.Parser,
) -> None:
    with pytest.raises(parser_exceptions.GlobalPositionInLocalScopeError) as exc_info:
        p.parse(
            "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
            + "    it happens when {\n"
            + "    } and it does {\n"
            + "        define the potential position<mv:define-lang.org:parser:/inner_pos>.\n"
            + "    }\n"
            + "}\n"
        )
    assert str(exc_info.value.token).startswith("define the potential position<")
    assert exc_info.value.line == 4
    assert exc_info.value.column == 9


def test_action_block_missing_action_statements_block(p: parser.Parser) -> None:
    with pytest.raises(parser_exceptions.MissingActionStatementsBlockError) as exc_info:
        p.parse(
            "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
            + "    it happens when {\n"
            + "    }\n"
            + "}\n"
        )
    assert str(exc_info.value.token) == "\n"
    assert exc_info.value.line == 3
    assert exc_info.value.column == 6


def test_action_block_missing_outer_close(p: parser.Parser) -> None:
    with pytest.raises(parser_exceptions.MissingBlockCloseError) as exc_info:
        p.parse(
            "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
            + "    it happens when {\n"
            + "    } and it does {\n"
            + "    }\n"
        )
    assert str(exc_info.value.token) == ""
    assert exc_info.value.line == 4
    assert exc_info.value.column == 6


def test_action_block_extra_space_before_brace(p: parser.Parser) -> None:
    with pytest.raises(parser_exceptions.UnexpectedWhitespaceError) as exc_info:
        p.parse(
            "define the potential action<mv:define-lang.org:parser:/path>  {\n"
            + "    it happens when {\n"
            + "    } and it does {\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.line == 1
    assert exc_info.value.column == 61


def test_action_block_no_newline_after_open_brace(p: parser.Parser) -> None:
    with pytest.raises(parser_exceptions.MissingNewlineAfterBlockOpenError) as exc_info:
        p.parse("define the potential action<mv:define-lang.org:parser:/path> {}\n")
    assert str(exc_info.value.token) == "}"
    assert exc_info.value.line == 1
    assert exc_info.value.column == 63


def test_action_block_missing_newline_after_inner_close(p: parser.Parser) -> None:
    with pytest.raises(
        parser_exceptions.MissingNewlineAfterBlockCloseError
    ) as exc_info:
        p.parse(
            "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
            + "    it happens when {\n"
            + "    } and it does {\n"
            + "    }}\n"
        )
    assert str(exc_info.value.token) == "}"
    assert exc_info.value.line == 4
    assert exc_info.value.column == 6


def test_trigger_and_action_on_wrong_line(p: parser.Parser) -> None:
    with pytest.raises(parser_exceptions.MissingActionStatementsBlockError) as exc_info:
        p.parse(
            "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
            + "    it happens when {\n"
            + "    }\n"
            + "    and it does {\n"
            + "    }\n"
            + "}\n"
        )
    assert str(exc_info.value.token) == "\n"
    assert exc_info.value.line == 3
    assert exc_info.value.column == 6


def test_local_position_after_trigger_and_action(p: parser.Parser) -> None:
    with pytest.raises(parser_exceptions.LocalPositionAfterTriggerError) as exc_info:
        p.parse(
            "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
            + "    it happens when {\n"
            + "    } and it does {\n"
            + "    }\n"
            + "    define the position<late_pos>.\n"
            + "}\n"
        )
    assert str(exc_info.value.token) == "define the position"
    assert exc_info.value.line == 5
    assert exc_info.value.column == 5


def test_missing_close_brace_followed_by_global_definition(p: parser.Parser) -> None:
    with pytest.raises(parser_exceptions.MissingBlockCloseError) as exc_info:
        p.parse(
            "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
            + "    it happens when {\n"
            + "    } and it does {\n"
            + "    }\n"
            + "define the potential position<mv:define-lang.org:parser:/my_action>.\n"
        )
    assert str(exc_info.value.token) == "define the potential position"
    assert exc_info.value.line == 5
    assert exc_info.value.column == 1
