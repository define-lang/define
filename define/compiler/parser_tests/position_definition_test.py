# pyright: reportUnusedCallResult=false
"""Position definition parser tests.

Follow parser test authoring rules in parser_tests/AGENTS.md.
"""

from define.compiler import parser, parser_exceptions
from define.compiler.parser_tests.test_helpers import get_tokens_by_type


def test_position_definition_parses(p: parser.Parser) -> None:
    result = p.parse(
        "define the potential position<mv:define-lang.org:parser:/path>.\n"
    )
    assert result.diagnostics == []
    assert result.tree is not None
    assert get_tokens_by_type(result.tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/path"
    ]
    assert get_tokens_by_type(result.tree, "LOCAL_NAME_CONTENT") == []


def test_position_definition_with_local_style_name_is_global_terminal(
    p: parser.Parser,
) -> None:
    result = p.parse("define the potential position<foo>.\n")
    assert result.diagnostics == []
    assert result.tree is not None
    assert get_tokens_by_type(result.tree, "GLOBAL_NAME_CONTENT") == ["foo"]
    assert get_tokens_by_type(result.tree, "LOCAL_NAME_CONTENT") == []


def test_position_definition_missing_open_angle(p: parser.Parser) -> None:
    result = p.parse("define the potential positionstandard:/path>.\n")
    assert result.diagnostics == []
    assert isinstance(result.exception, parser_exceptions.MissingOpenAngleBracket)
    assert str(result.exception.token) == "standard:/path"
    assert result.exception.line == 1
    assert result.exception.column == 30
    assert result.exception.name == "standard:/path"


def test_position_definition_empty_name_content(p: parser.Parser) -> None:
    result = p.parse("define the potential position<>.\n")
    assert result.diagnostics == []
    assert isinstance(result.exception, parser_exceptions.EmptyName)
    assert str(result.exception.token) == ">"
    assert result.exception.line == 1
    assert result.exception.column == 31


def test_position_definition_with_constraint_block(p: parser.Parser) -> None:
    result = p.parse(
        "define the potential position<mv:define-lang.org:parser:/path> {\n"
        + "    it may only contain dimension points where {\n"
        + "        it has the position</child>.\n"
        + "    }\n"
        + "}\n"
    )
    assert result.diagnostics == []
    assert result.tree is not None
    assert get_tokens_by_type(result.tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/path",
        "/child",
    ]
    assert get_tokens_by_type(result.tree, "LOCAL_NAME_CONTENT") == []


def test_position_definition_with_multiple_requirements(p: parser.Parser) -> None:
    result = p.parse(
        "define the potential position<mv:define-lang.org:parser:/path> {\n"
        + "    it may only contain dimension points where {\n"
        + "        it has the position</first>.\n"
        + "        it has the action</second>.\n"
        + "    }\n"
        + "}\n"
    )
    assert result.diagnostics == []
    assert result.tree is not None
    assert get_tokens_by_type(result.tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/path",
        "/first",
        "/second",
    ]
    assert get_tokens_by_type(result.tree, "LOCAL_NAME_CONTENT") == []


def test_position_definition_block_requires_content(p: parser.Parser) -> None:
    result = p.parse(
        "define the potential position<mv:define-lang.org:parser:/path> {\n}\n"
    )
    assert isinstance(
        result.exception, parser_exceptions.MissingPotentialPositionDefinitionContent
    )
    assert str(result.exception.token) == "}"
    assert result.exception.line == 2
    assert result.exception.column == 1


def test_position_constraint_block_requires_requirements(p: parser.Parser) -> None:
    result = p.parse(
        "define the potential position<mv:define-lang.org:parser:/path> {\n"
        + "    it may only contain dimension points where {\n"
        + "    }\n"
        + "}\n"
    )
    assert isinstance(
        result.exception, parser_exceptions.MissingPositionConstraintContent
    )
    assert str(result.exception.token) == "}"
    assert result.exception.line == 3
    assert result.exception.column == 5


def test_position_constraint_block_with_invalid_statement_then_more_definitions(
    p: parser.Parser,
) -> None:
    result = p.parse(
        "define the potential position<my_lib:/path>.\n"
        + "define the potential position<my_lib:/path> {\n"
        + "it may only contain dimension points where {\n"
        + "t has the position<my_lib:/path>.\n"
        + "}\n"
        + "}\n"
        + "define the potential position<my_lib:/path>.\n"
    )
    assert isinstance(
        result.exception, parser_exceptions.InvalidPositionConstraintBlock
    )
    assert str(result.exception.token).startswith("t has the")
    assert result.exception.line == 4
    assert result.exception.column == 1


def test_position_definition_rejects_multiple_constraint_blocks(
    p: parser.Parser,
) -> None:
    result = p.parse(
        "define the potential position<mv:define-lang.org:parser:/path> {\n"
        + "    it may only contain dimension points where {\n"
        + "        it has the position</first>.\n"
        + "    }\n"
        + "    it may only contain dimension points where {\n"
        + "        it has the action</second>.\n"
        + "    }\n"
        + "}\n"
    )
    assert result.diagnostics == []
    assert isinstance(
        result.exception,
        parser_exceptions.InvalidPotentialPositionDefinitionBlock,
    )
    assert str(result.exception.token).startswith("it may only contain")
    assert result.exception.line == 5
    assert result.exception.column == 5


def test_second_constraint_block_after_close_on_same_line(
    p: parser.Parser,
) -> None:
    result = p.parse(
        "define the potential position<mv:define-lang.org:parser:/path> {\n"
        + "    it may only contain dimension points where {\n"
        + "        it has the position</first>.\n"
        + "    }    it may only contain dimension points where {\n"
        + "        it has the action</second>.\n"
        + "    }\n"
        + "}\n"
    )
    assert result.diagnostics == []
    assert isinstance(result.exception, parser_exceptions.MissingNewlineAfterCloseBrace)
    assert result.exception.token.type == "LOCAL_NAME_CONTENT"
    assert str(result.exception.token).startswith("    it may only contain")
    assert result.exception.line == 4
    assert result.exception.column == 6


def test_second_constraint_block_on_requirement_line(
    p: parser.Parser,
) -> None:
    result = p.parse(
        "define the potential position<mv:define-lang.org:parser:/path> {\n"
        + "    it may only contain dimension points where {\n"
        + "        it has the position</first>.    it may only contain dimension points where {\n"
        + "        it has the action</second>.\n"
        + "    }\n"
        + "}\n"
    )
    assert result.diagnostics == []
    assert isinstance(result.exception, parser_exceptions.MissingNewlineAfterTerminator)
    assert result.exception.token.type == "LOCAL_NAME_CONTENT"
    assert str(result.exception.token).startswith("    it may only contain")
    assert result.exception.line == 3
    assert result.exception.column == 37


def test_action_definition_block_with_mixed_local_position_forms(
    p: parser.Parser,
) -> None:
    result = p.parse(
        "define the potential action<mv:define-lang.org:parser:/act> {\n"
        + "    define the position<run>.\n"
        + "    define the position<empty_pos>.\n"
        + "    define the position<constrained_pos> {\n"
        + "        it may only contain dimension points where {\n"
        + "            it has the position</child>.\n"
        + "        }\n"
        + "    }\n"
        + "    it happens when {\n"
        + "        the position<run> has a dimension point.\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    )
    assert result.diagnostics == []
    assert result.tree is not None
    assert get_tokens_by_type(result.tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/act",
        "/child",
    ]
    assert get_tokens_by_type(result.tree, "LOCAL_NAME_CONTENT") == [
        "run",
        "empty_pos",
        "constrained_pos",
        "run",
    ]


def test_action_definition_block_with_multiple_local_block_positions(
    p: parser.Parser,
) -> None:
    result = p.parse(
        "define the potential action<mv:define-lang.org:parser:/act> {\n"
        + "    define the position<run>.\n"
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
        + "        the position<run> has a dimension point.\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    )
    assert result.diagnostics == []
    assert result.tree is not None
    assert get_tokens_by_type(result.tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/act",
        "/first_child",
        "/second_child",
    ]
    assert get_tokens_by_type(result.tree, "LOCAL_NAME_CONTENT") == [
        "run",
        "first_pos",
        "second_pos",
        "run",
    ]


def test_action_statements_block_with_mixed_local_position_forms(
    p: parser.Parser,
) -> None:
    result = p.parse(
        "define the potential action<mv:define-lang.org:parser:/act> {\n"
        + "    define the position<run>.\n"
        + "    it happens when {\n"
        + "        the position<run> has a dimension point.\n"
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
    assert result.diagnostics == []
    assert result.tree is not None
    assert get_tokens_by_type(result.tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/act",
        "/inner_action",
    ]
    assert get_tokens_by_type(result.tree, "LOCAL_NAME_CONTENT") == [
        "run",
        "run",
        "empty_inner",
        "constrained_inner",
    ]


def test_action_statements_block_with_multiple_local_block_positions(
    p: parser.Parser,
) -> None:
    result = p.parse(
        "define the potential action<mv:define-lang.org:parser:/act> {\n"
        + "    define the position<run>.\n"
        + "    it happens when {\n"
        + "        the position<run> has a dimension point.\n"
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
    assert result.diagnostics == []
    assert result.tree is not None
    assert get_tokens_by_type(result.tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/act",
        "/first_child",
        "/second_child",
    ]
    assert get_tokens_by_type(result.tree, "LOCAL_NAME_CONTENT") == [
        "run",
        "run",
        "first_inner",
        "second_inner",
    ]


def test_position_definition_with_init_block_only(p: parser.Parser) -> None:
    result = p.parse(
        "define the potential position<standard:/path> {\n"
        + "    after it is assigned {\n"
        + "        create a dimension point in position</other>.\n"
        + "    }\n"
        + "}\n"
    )
    assert result.diagnostics == []
    assert result.tree is not None
    assert get_tokens_by_type(result.tree, "GLOBAL_NAME_CONTENT") == [
        "standard:/path",
        "/other",
    ]


def test_position_definition_with_constraint_and_init_block(p: parser.Parser) -> None:
    result = p.parse(
        "define the potential position<standard:/path> {\n"
        + "    it may only contain dimension points where {\n"
        + "        it has the position</child>.\n"
        + "    }\n"
        + "    after it is assigned {\n"
        + "        create a dimension point in position</other>.\n"
        + "    }\n"
        + "}\n"
    )
    assert result.diagnostics == []
    assert result.tree is not None
    assert get_tokens_by_type(result.tree, "GLOBAL_NAME_CONTENT") == [
        "standard:/path",
        "/child",
        "/other",
    ]


def test_init_block_with_create_statement(p: parser.Parser) -> None:
    result = p.parse(
        "define the potential position<standard:/path> {\n"
        + "    after it is assigned {\n"
        + "        create a dimension point in this position.\n"
        + "    }\n"
        + "}\n"
    )
    assert result.diagnostics == []
    assert result.tree is not None
    assert get_tokens_by_type(result.tree, "THIS_POSITION") == ["this position"]


def test_init_block_with_move_statement(p: parser.Parser) -> None:
    result = p.parse(
        "define the potential position<standard:/path> {\n"
        + "    after it is assigned {\n"
        + "        move the dimension point in position</source> to this position.\n"
        + "    }\n"
        + "}\n"
    )
    assert result.diagnostics == []
    assert result.tree is not None
    assert get_tokens_by_type(result.tree, "THIS_POSITION") == ["this position"]
    assert get_tokens_by_type(result.tree, "GLOBAL_NAME_CONTENT") == [
        "standard:/path",
        "/source",
    ]


def test_init_block_with_local_position_definition(p: parser.Parser) -> None:
    result = p.parse(
        "define the potential position<standard:/path> {\n"
        + "    after it is assigned {\n"
        + "        define the position<inner>.\n"
        + "    }\n"
        + "}\n"
    )
    assert result.diagnostics == []
    assert result.tree is not None
    assert get_tokens_by_type(result.tree, "LOCAL_NAME_CONTENT") == ["inner"]


def test_init_block_with_this_position_in_create(p: parser.Parser) -> None:
    result = p.parse(
        "define the potential position<standard:/path> {\n"
        + "    after it is assigned {\n"
        + "        create a dimension point in this position.\n"
        + "    }\n"
        + "}\n"
    )
    assert result.diagnostics == []
    assert result.tree is not None
    assert get_tokens_by_type(result.tree, "THIS_POSITION") == ["this position"]


def test_init_block_with_multiple_statements(p: parser.Parser) -> None:
    result = p.parse(
        "define the potential position<standard:/path> {\n"
        + "    after it is assigned {\n"
        + "        create a dimension point in this position.\n"
        + "        move the dimension point in position</source> to position</dest>.\n"
        + "        define the position<inner>.\n"
        + "    }\n"
        + "}\n"
    )
    assert result.diagnostics == []
    assert result.tree is not None
    assert get_tokens_by_type(result.tree, "THIS_POSITION") == ["this position"]
    assert get_tokens_by_type(result.tree, "GLOBAL_NAME_CONTENT") == [
        "standard:/path",
        "/source",
        "/dest",
    ]
    assert get_tokens_by_type(result.tree, "LOCAL_NAME_CONTENT") == ["inner"]


def test_empty_init_block(p: parser.Parser) -> None:
    result = p.parse(
        "define the potential position<standard:/path> {\n"
        + "    after it is assigned {\n"
        + "    }\n"
        + "}\n"
    )
    assert result.diagnostics == []
    assert result.tree is not None


def test_init_block_with_comments_and_blank_lines(p: parser.Parser) -> None:
    result = p.parse(
        "define the potential position<standard:/path> {\n"
        + "    after it is assigned {\n"
        + "        # a comment\n"
        + "\n"
        + "        create a dimension point in this position.\n"
        + "\n"
        + "    }\n"
        + "}\n"
    )
    assert result.diagnostics == []
    assert result.tree is not None


def test_init_block_before_constraint_block_fails(p: parser.Parser) -> None:
    result = p.parse(
        "define the potential position<standard:/path> {\n"
        + "    after it is assigned {\n"
        + "        create a dimension point in this position.\n"
        + "    }\n"
        + "    it may only contain dimension points where {\n"
        + "        it has the position</child>.\n"
        + "    }\n"
        + "}\n"
    )
    assert isinstance(result.exception, parser_exceptions.MissingCloseBrace)


def test_multiple_init_blocks_fails(p: parser.Parser) -> None:
    result = p.parse(
        "define the potential position<standard:/path> {\n"
        + "    after it is assigned {\n"
        + "        create a dimension point in this position.\n"
        + "    }\n"
        + "    after it is assigned {\n"
        + "        create a dimension point in this position.\n"
        + "    }\n"
        + "}\n"
    )
    assert isinstance(result.exception, parser_exceptions.MissingCloseBrace)
    assert str(result.exception.token) == "after it is assigned"
    assert result.exception.token.type == "AFTER_IT_IS_ASSIGNED"
    assert result.exception.line == 5
    assert result.exception.column == 5


def test_invalid_content_in_init_block(p: parser.Parser) -> None:
    result = p.parse(
        "define the potential position<standard:/path> {\n"
        + "    after it is assigned {\n"
        + "        nonsense here\n"
        + "    }\n"
        + "}\n"
    )
    assert isinstance(result.exception, parser_exceptions.InvalidActionStatementsBlock)
    assert str(result.exception.token) == "nonsense here"
    assert result.exception.token.type == "LOCAL_NAME_CONTENT"
    assert result.exception.line == 3
    assert result.exception.column == 9


def test_empty_potential_position_block(p: parser.Parser) -> None:
    result = p.parse("define the potential position<standard:/path> {\n}\n")
    assert isinstance(
        result.exception, parser_exceptions.MissingPotentialPositionDefinitionContent
    )
    assert str(result.exception.token) == "}"
    assert result.exception.line == 2
    assert result.exception.column == 1


def test_invalid_content_in_potential_position_block(p: parser.Parser) -> None:
    result = p.parse(
        "define the potential position<standard:/path> {\n"
        + "    nonsense here\n"
        + "}\n"
    )
    assert isinstance(
        result.exception, parser_exceptions.InvalidPotentialPositionDefinitionBlock
    )


def test_empty_local_position_definition_block(p: parser.Parser) -> None:
    result = p.parse(
        "define the potential action<standard:/act> {\n"
        + "    define the position<bad> {\n"
        + "    }\n"
        + "    it happens when {\n"
        + "        the position<bad> has a dimension point.\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    )
    assert isinstance(
        result.exception, parser_exceptions.MissingPositionDefinitionContent
    )
    assert str(result.exception.token) == "}"
    assert result.exception.line == 3
    assert result.exception.column == 5


def test_invalid_content_in_local_position_definition_block(p: parser.Parser) -> None:
    result = p.parse(
        "define the potential action<standard:/act> {\n"
        + "    define the position<bad> {\n"
        + "        nonsense here\n"
        + "    }\n"
        + "    it happens when {\n"
        + "        the position<bad> has a dimension point.\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    )
    assert isinstance(
        result.exception, parser_exceptions.InvalidPositionDefinitionBlock
    )
