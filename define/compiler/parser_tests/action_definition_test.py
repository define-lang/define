# pyright: reportUnusedCallResult=false
"""Action definition parser tests.

Follow parser test authoring rules in parser_tests/AGENTS.md.
"""

from define.compiler import parser, parser_exceptions
from define.compiler.parser_tests.test_helpers import get_tokens_by_type


def test_action_definition_parses(p: parser.Parser) -> None:
    tree = p.parse("define the potential action<standard:/path>.\n").tree
    assert tree is not None
    assert get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == ["standard:/path"]
    assert get_tokens_by_type(tree, "LOCAL_NAME_CONTENT") == []


def test_action_definition_missing_open_angle(p: parser.Parser) -> None:
    result = p.parse("define the potential actionstandard:/path>.\n")
    assert isinstance(result.exception, parser_exceptions.MissingOpenAngleBracket)
    assert str(result.exception.token) == "standard:/path"
    assert result.exception.column == 28


def test_action_definition_empty_name_content(p: parser.Parser) -> None:
    result = p.parse("define the potential action<>.\n")
    assert isinstance(result.exception, parser_exceptions.EmptyName)
    assert str(result.exception.token) == ">"
    assert result.exception.column == 29


def test_action_with_empty_inner_blocks(p: parser.Parser) -> None:
    tree = p.parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    it happens when {\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    ).tree
    assert tree is not None
    assert get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/my_action"
    ]
    assert get_tokens_by_type(tree, "LOCAL_NAME_CONTENT") == []


def test_action_with_local_position_definition(p: parser.Parser) -> None:
    tree = p.parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    define the position<my_pos>.\n"
        + "    it happens when {\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    ).tree
    assert tree is not None
    assert get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/my_action"
    ]
    assert get_tokens_by_type(tree, "LOCAL_NAME_CONTENT") == ["my_pos"]


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
    ).tree
    assert tree is not None
    assert get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/my_action",
        "/do_work",
    ]
    assert get_tokens_by_type(tree, "LOCAL_NAME_CONTENT") == ["my_pos"]


def test_action_with_multiple_local_position_definitions(p: parser.Parser) -> None:
    tree = p.parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    define the position<first_pos>.\n"
        + "    define the position<second_pos>.\n"
        + "    it happens when {\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    ).tree
    assert tree is not None
    assert get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/my_action"
    ]
    assert get_tokens_by_type(tree, "LOCAL_NAME_CONTENT") == [
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
    ).tree
    assert tree is not None
    assert get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/my_action",
        "/child",
    ]
    assert get_tokens_by_type(tree, "LOCAL_NAME_CONTENT") == [
        "first_pos",
        "second_pos",
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
    ).tree
    assert tree is not None
    assert get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/my_action"
    ]
    assert get_tokens_by_type(tree, "LOCAL_NAME_CONTENT") == ["my_pos"]


def test_action_block_with_full_fqun(p: parser.Parser) -> None:
    tree = p.parse(
        "define the potential action<mv:define-lang.org:parser:/some/path> {\n"
        + "    define the position<my_pos>.\n"
        + "    it happens when {\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    ).tree
    assert tree is not None
    assert get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/some/path"
    ]
    assert get_tokens_by_type(tree, "LOCAL_NAME_CONTENT") == ["my_pos"]


def test_action_block_comment_after_trigger_open(p: parser.Parser) -> None:
    tree = p.parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    it happens when { # comment\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    ).tree
    assert tree is not None
    assert get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/my_action"
    ]
    assert get_tokens_by_type(tree, "LOCAL_NAME_CONTENT") == []


def test_action_block_comment_after_action_close(p: parser.Parser) -> None:
    tree = p.parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    it happens when {\n"
        + "    } and it does {\n"
        + "    } # comment\n"
        + "}\n"
    ).tree
    assert tree is not None
    assert get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/my_action"
    ]
    assert get_tokens_by_type(tree, "LOCAL_NAME_CONTENT") == []


def test_action_block_no_indentation(p: parser.Parser) -> None:
    tree = p.parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "it happens when {\n"
        + "} and it does {\n"
        + "}\n"
        + "}\n"
    ).tree
    assert tree is not None
    assert get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/my_action"
    ]
    assert get_tokens_by_type(tree, "LOCAL_NAME_CONTENT") == []


def test_action_block_blank_lines_in_trigger_block(p: parser.Parser) -> None:
    tree = p.parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    it happens when {\n"
        + "\n"
        + "\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    ).tree
    assert tree is not None
    assert get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/my_action"
    ]
    assert get_tokens_by_type(tree, "LOCAL_NAME_CONTENT") == []


def test_action_block_blank_lines_in_action_block(p: parser.Parser) -> None:
    tree = p.parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    it happens when {\n"
        + "    } and it does {\n"
        + "\n"
        + "\n"
        + "    }\n"
        + "}\n"
    ).tree
    assert tree is not None
    assert get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/my_action"
    ]
    assert get_tokens_by_type(tree, "LOCAL_NAME_CONTENT") == []


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
    ).tree
    assert tree is not None
    assert get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/my_action"
    ]
    assert get_tokens_by_type(tree, "LOCAL_NAME_CONTENT") == ["inner_pos"]


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
    ).tree
    assert tree is not None
    assert get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/my_action"
    ]
    assert get_tokens_by_type(tree, "LOCAL_NAME_CONTENT") == [
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
    ).tree
    assert tree is not None
    assert get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/my_action"
    ]
    assert get_tokens_by_type(tree, "LOCAL_NAME_CONTENT") == [
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
    ).tree
    assert tree is not None
    assert get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/first",
        "mv:define-lang.org:parser:/second",
    ]
    assert get_tokens_by_type(tree, "LOCAL_NAME_CONTENT") == ["my_pos"]


def test_action_block_missing_trigger_block(p: parser.Parser) -> None:
    result = p.parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    define the position<my_pos>.\n"
        + "}\n"
    )
    assert isinstance(result.exception, parser_exceptions.MissingActionDefinitionSyntax)
    assert str(result.exception.token) == "}"
    assert result.exception.line == 3
    assert result.exception.column == 1


def test_global_position_definition_not_allowed_in_action_definition_block(
    p: parser.Parser,
) -> None:
    result = p.parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    define the potential position<mv:define-lang.org:parser:/inner_pos>.\n"
        + "    it happens when {\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    )
    assert isinstance(
        result.exception, parser_exceptions.GlobalDefinitionInLocalContext
    )
    assert str(result.exception.token).startswith("define the potential position<")
    assert result.exception.line == 2
    assert result.exception.column == 5


def test_global_position_definition_not_allowed_in_action_statements_block(
    p: parser.Parser,
) -> None:
    result = p.parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    it happens when {\n"
        + "    } and it does {\n"
        + "        define the potential position<mv:define-lang.org:parser:/inner_pos>.\n"
        + "    }\n"
        + "}\n"
    )
    assert isinstance(
        result.exception, parser_exceptions.GlobalDefinitionInLocalContext
    )
    assert str(result.exception.token).startswith("define the potential position<")
    assert result.exception.line == 4
    assert result.exception.column == 9


def test_action_block_missing_action_statements_block(p: parser.Parser) -> None:
    result = p.parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    it happens when {\n"
        + "    }\n"
        + "}\n"
    )
    assert isinstance(result.exception, parser_exceptions.MissingActionStatementsBlock)
    assert str(result.exception.token) == "\n"
    assert result.exception.line == 3
    assert result.exception.column == 6


def test_action_block_missing_outer_close(p: parser.Parser) -> None:
    result = p.parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    it happens when {\n"
        + "    } and it does {\n"
        + "    }\n"
    )
    assert isinstance(result.exception, parser_exceptions.MissingCloseBrace)
    assert str(result.exception.token) == ""
    assert result.exception.line == 4
    assert result.exception.column == 6


def test_action_block_extra_space_before_brace(p: parser.Parser) -> None:
    result = p.parse(
        "define the potential action<mv:define-lang.org:parser:/path>  {\n"
        + "    it happens when {\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    )
    assert isinstance(result.exception, parser_exceptions.MissingTerminatorOrBrace)
    assert result.exception.line == 1
    assert result.exception.column == 61


def test_action_block_no_newline_after_open_brace(p: parser.Parser) -> None:
    result = p.parse(
        "define the potential action<mv:define-lang.org:parser:/path> {}\n"
    )
    assert isinstance(result.exception, parser_exceptions.EmptyBlock)
    assert str(result.exception.token) == "}"
    assert result.exception.line == 1
    assert result.exception.column == 63


def test_action_block_missing_newline_after_outer_open_brace(p: parser.Parser) -> None:
    result = p.parse(
        "define the potential action<mv:define-lang.org:parser:/path> { it happens when {\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    )
    assert isinstance(result.exception, parser_exceptions.MissingNewlineAfterOpenBrace)
    assert str(result.exception.token) == " it happens when {"
    assert result.exception.line == 1
    assert result.exception.column == 63


def test_action_block_missing_newline_after_inner_close(p: parser.Parser) -> None:
    result = p.parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    it happens when {\n"
        + "    } and it does {\n"
        + "    }}\n"
    )
    assert isinstance(result.exception, parser_exceptions.MissingNewlineAfterCloseBrace)
    assert str(result.exception.token) == "}"
    assert result.exception.line == 4
    assert result.exception.column == 6


def test_trigger_and_action_on_wrong_line(p: parser.Parser) -> None:
    result = p.parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    it happens when {\n"
        + "    }\n"
        + "    and it does {\n"
        + "    }\n"
        + "}\n"
    )
    assert isinstance(result.exception, parser_exceptions.MissingActionStatementsBlock)
    assert str(result.exception.token) == "\n"
    assert result.exception.line == 3
    assert result.exception.column == 6


def test_local_position_after_trigger_and_action(p: parser.Parser) -> None:
    result = p.parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    it happens when {\n"
        + "    } and it does {\n"
        + "    }\n"
        + "    define the position<late_pos>.\n"
        + "}\n"
    )
    assert isinstance(
        result.exception, parser_exceptions.InvalidPositionDefinitionLocationInAction
    )
    assert str(result.exception.token) == "define the position"
    assert result.exception.line == 5
    assert result.exception.column == 5


def test_second_trigger_and_action_block_pair_not_allowed(p: parser.Parser) -> None:
    result = p.parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    it happens when {\n"
        + "    } and it does {\n"
        + "    }\n"
        + "    it happens when {\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    )
    assert isinstance(result.exception, parser_exceptions.MissingCloseBrace)
    assert result.exception.token == "it happens when"
    assert result.exception.line == 5
    assert result.exception.column == 5


def test_missing_close_brace_followed_by_global_definition(p: parser.Parser) -> None:
    result = p.parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    it happens when {\n"
        + "    } and it does {\n"
        + "    }\n"
        + "define the potential position<mv:define-lang.org:parser:/my_action>.\n"
    )
    assert isinstance(result.exception, parser_exceptions.MissingCloseBrace)
    assert str(result.exception.token) == "define the potential position"
    assert result.exception.line == 5
    assert result.exception.column == 1


def test_action_statements_block_invalid_statement(p: parser.Parser) -> None:
    result = p.parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    it happens when {\n"
        + "    } and it does {\n"
        + "        nonsense\n"
        + "    }\n"
        + "}\n"
    )
    assert isinstance(result.exception, parser_exceptions.InvalidActionStatementsBlock)
    assert str(result.exception.token) == "nonsense"
    assert result.exception.line == 4
    assert result.exception.column == 9


def test_action_statements_block_with_create_dimension_point_local_position(
    p: parser.Parser,
) -> None:
    tree = p.parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    it happens when {\n"
        + "    } and it does {\n"
        + "        create a dimension point in position<run>.\n"
        + "    }\n"
        + "}\n"
    ).tree
    assert tree is not None
    assert get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/my_action"
    ]
    assert get_tokens_by_type(tree, "LOCAL_NAME_CONTENT") == ["run"]


def test_action_statements_block_with_create_dimension_point_short_global_position(
    p: parser.Parser,
) -> None:
    tree = p.parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    it happens when {\n"
        + "    } and it does {\n"
        + "        create a dimension point in position</run>.\n"
        + "    }\n"
        + "}\n"
    ).tree
    assert tree is not None
    assert get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/my_action",
        "/run",
    ]
    assert get_tokens_by_type(tree, "LOCAL_NAME_CONTENT") == []


def test_action_statements_block_with_create_dimension_point_full_global_position(
    p: parser.Parser,
) -> None:
    tree = p.parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    it happens when {\n"
        + "    } and it does {\n"
        + "        create a dimension point in position<mv:define-lang.org:parser:/run>.\n"
        + "    }\n"
        + "}\n"
    ).tree
    assert tree is not None
    assert get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/my_action",
        "mv:define-lang.org:parser:/run",
    ]
    assert get_tokens_by_type(tree, "LOCAL_NAME_CONTENT") == []


def test_action_statements_block_with_create_dimension_point_chain(
    p: parser.Parser,
) -> None:
    tree = p.parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    it happens when {\n"
        + "    } and it does {\n"
        + "        create a dimension point in position<to>::action</deposit>::position<run>.\n"
        + "    }\n"
        + "}\n"
    ).tree
    assert tree is not None
    assert get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/my_action",
        "/deposit",
    ]
    assert get_tokens_by_type(tree, "LOCAL_NAME_CONTENT") == ["to", "run"]


def test_action_statements_block_with_create_dimension_point_short_global_chain(
    p: parser.Parser,
) -> None:
    tree = p.parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    it happens when {\n"
        + "    } and it does {\n"
        + "        create a dimension point in position</to>::action</deposit>::position</run>.\n"
        + "    }\n"
        + "}\n"
    ).tree
    assert tree is not None
    assert get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/my_action",
        "/to",
        "/deposit",
        "/run",
    ]
    assert get_tokens_by_type(tree, "LOCAL_NAME_CONTENT") == []


def test_action_statements_block_with_create_dimension_point_any_typed_chain(
    p: parser.Parser,
) -> None:
    tree = p.parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    it happens when {\n"
        + "    } and it does {\n"
        + "        create a dimension point in action</start>::position<mid>::action</end>.\n"
        + "    }\n"
        + "}\n"
    ).tree
    assert tree is not None
    assert get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/my_action",
        "/start",
        "/end",
    ]
    assert get_tokens_by_type(tree, "LOCAL_NAME_CONTENT") == ["mid"]


def test_action_statements_block_with_mixed_statements_and_multiple_create_dimension_points(
    p: parser.Parser,
) -> None:
    tree = p.parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    it happens when {\n"
        + "    } and it does {\n"
        + "        define the position<inner_pos>.\n"
        + "        create a dimension point in position<inner_pos>.\n"
        + "        create a dimension point in position</global_run>::action</deposit>::position<inner_pos>.\n"
        + "    }\n"
        + "}\n"
    ).tree
    assert tree is not None
    assert get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/my_action",
        "/global_run",
        "/deposit",
    ]
    assert get_tokens_by_type(tree, "LOCAL_NAME_CONTENT") == [
        "inner_pos",
        "inner_pos",
        "inner_pos",
    ]
