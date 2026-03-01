# pyright: reportUnusedCallResult=false
"""Incomplete statement parser tests.

Follow parser test authoring rules in parser_tests/AGENTS.md.
"""

import pytest

from define.compiler import parser, parser_exceptions


def test_empty_file(p: parser.Parser) -> None:
    with pytest.raises(parser_exceptions.ExpectedGlobalDefinition) as exc_info:
        p.parse("")
    assert exc_info.value.token == ""
    assert exc_info.value.line == 1
    assert exc_info.value.column == 1


def test_file_all_newlines(p: parser.Parser) -> None:
    with pytest.raises(parser_exceptions.ExpectedGlobalDefinition) as exc_info:
        p.parse("\n\n\n")
    assert exc_info.value.token == ""
    assert exc_info.value.line == 3
    assert exc_info.value.column == 1


def test_define_the_potential_incomplete_global_prefix(p: parser.Parser) -> None:
    with pytest.raises(parser_exceptions.ExpectedGlobalDefinition) as exc_info:
        p.parse("define the potential\n")
    assert exc_info.value.token == "define the potential"
    assert exc_info.value.line == 1
    assert exc_info.value.column == 1


def test_global_position_block_open_without_content(p: parser.Parser) -> None:
    with pytest.raises(parser_exceptions.InvalidPositionDefinitionBlock) as exc_info:
        p.parse("define the potential position<mv:define-lang.org:parser:/path> {\n")
    assert exc_info.value.token == ""
    assert exc_info.value.line == 1
    assert exc_info.value.column == 65


def test_global_action_block_open_without_content(p: parser.Parser) -> None:
    with pytest.raises(parser_exceptions.InvalidActionDefinitionsBlock) as exc_info:
        p.parse("define the potential action<mv:define-lang.org:parser:/path> {\n")
    assert exc_info.value.token == ""
    assert exc_info.value.line == 1
    assert exc_info.value.column == 63


def test_position_block_missing_required_clause(p: parser.Parser) -> None:
    with pytest.raises(parser_exceptions.MissingPositionDefinitionContent) as exc_info:
        p.parse(
            "define the potential position<mv:define-lang.org:parser:/path> {\n" + "}\n"
        )
    assert exc_info.value.token == "}"
    assert exc_info.value.line == 2
    assert exc_info.value.column == 1


def test_position_required_clause_missing_open_brace(p: parser.Parser) -> None:
    with pytest.raises(parser_exceptions.MissingOpenBrace) as exc_info:
        p.parse(
            "define the potential position<mv:define-lang.org:parser:/path> {\n"
            + "it may only contain dimension points where\n"
            + "}\n"
        )
    assert exc_info.value.token == "\n"
    assert exc_info.value.line == 2
    assert exc_info.value.column == 43


def test_action_block_missing_trigger_clause(p: parser.Parser) -> None:
    with pytest.raises(parser_exceptions.MissingActionDefinitionSyntax) as exc_info:
        p.parse(
            "define the potential action<mv:define-lang.org:parser:/path> {\n" + "}\n"
        )
    assert exc_info.value.token == "}"
    assert exc_info.value.line == 2
    assert exc_info.value.column == 1


def test_action_trigger_clause_missing_open_brace(p: parser.Parser) -> None:
    with pytest.raises(parser_exceptions.MissingOpenBrace) as exc_info:
        p.parse(
            "define the potential action<mv:define-lang.org:parser:/path> {\n"
            + "it happens when\n"
            + "}\n"
        )
    assert exc_info.value.token == "\n"
    assert exc_info.value.line == 2
    assert exc_info.value.column == 16


def test_action_missing_and_it_does_clause(p: parser.Parser) -> None:
    with pytest.raises(parser_exceptions.MissingActionStatementsBlock) as exc_info:
        p.parse(
            "define the potential action<mv:define-lang.org:parser:/path> {\n"
            + "it happens when {\n"
            + "}\n"
            + "}\n"
        )
    assert exc_info.value.token == "\n"
    assert exc_info.value.line == 3
    assert exc_info.value.column == 2


def test_action_and_it_does_clause_missing_open_brace(p: parser.Parser) -> None:
    with pytest.raises(parser_exceptions.MissingOpenBrace) as exc_info:
        p.parse(
            "define the potential action<mv:define-lang.org:parser:/path> {\n"
            + "it happens when {\n"
            + "} and it does\n"
            + "}\n"
        )
    assert exc_info.value.token == "\n"
    assert exc_info.value.line == 3
    assert exc_info.value.column == 14


def test_action_and_it_does_block_missing_close_brace(p: parser.Parser) -> None:
    with pytest.raises(parser_exceptions.MissingCloseBrace) as exc_info:
        p.parse(
            "define the potential action<mv:define-lang.org:parser:/path> {\n"
            + "it happens when {\n"
            + "} and it does {\n"
            + "}\n"
        )
    assert exc_info.value.token == ""
    assert exc_info.value.line == 4
    assert exc_info.value.column == 2


def test_local_position_keyword_without_name_in_action_definition_block(
    p: parser.Parser,
) -> None:
    with pytest.raises(parser_exceptions.MissingOpenAngleBracket) as exc_info:
        p.parse(
            "define the potential action<mv:define-lang.org:parser:/path> {\n"
            + "define the position\n"
            + "it happens when {\n"
            + "} and it does {\n"
            + "}\n"
            + "}\n"
        )
    assert exc_info.value.token == "\n"
    assert exc_info.value.line == 2
    assert exc_info.value.column == 20


def test_local_position_keyword_without_name_in_action_statements_block(
    p: parser.Parser,
) -> None:
    with pytest.raises(parser_exceptions.MissingOpenAngleBracket) as exc_info:
        p.parse(
            "define the potential action<mv:define-lang.org:parser:/path> {\n"
            + "it happens when {\n"
            + "} and it does {\n"
            + "define the position\n"
            + "}\n"
            + "}\n"
        )
    assert exc_info.value.token == "\n"
    assert exc_info.value.line == 4
    assert exc_info.value.column == 20


def test_global_position_keyword_without_name(p: parser.Parser) -> None:
    with pytest.raises(parser_exceptions.MissingOpenAngleBracket) as exc_info:
        p.parse("define the potential position\n")
    assert exc_info.value.token == "\n"
    assert exc_info.value.line == 1
    assert exc_info.value.column == 30


def test_position_requirement_missing_name(p: parser.Parser) -> None:
    with pytest.raises(parser_exceptions.MissingOpenAngleBracket) as exc_info:
        p.parse(
            "define the potential position<mv:define-lang.org:parser:/path> {\n"
            + "it may only contain dimension points where {\n"
            + "it has the position\n"
            + "}\n"
            + "}\n"
        )
    assert exc_info.value.token == "\n"
    assert exc_info.value.line == 3
    assert exc_info.value.column == 20


def test_position_requirement_missing_name_after_type(p: parser.Parser) -> None:
    with pytest.raises(parser_exceptions.MissingOpenAngleBracket) as exc_info:
        p.parse(
            "define the potential position<mv:define-lang.org:parser:/path> {\n"
            + "it may only contain dimension points where {\n"
            + "it has the position.\n"
            + "}\n"
            + "}\n"
        )
    assert exc_info.value.token == "."
    assert exc_info.value.line == 3
    assert exc_info.value.column == 20


def test_position_requirement_name_starts_and_then_newline(p: parser.Parser) -> None:
    with pytest.raises(parser_exceptions.EmptyName) as exc_info:
        p.parse(
            "define the potential position<mv:define-lang.org:parser:/path> {\n"
            + "it may only contain dimension points where {\n"
            + "it has the position<\n"
            + "/path>.\n"
            + "}\n"
            + "}\n"
        )
    assert exc_info.value.token == "\n"
    assert exc_info.value.line == 3
    assert exc_info.value.column == 21


def test_position_requirement_missing_space_after_it_has_the(p: parser.Parser) -> None:
    with pytest.raises(parser_exceptions.MissingWhitespace) as exc_info:
        p.parse(
            "define the potential action<example.com:my_lib:/path> {\n"
            + "it happens when {\n"
            + "} and it does {\n"
            + "}\n"
            + "}\n"
            + "define the potential position<my_lib:/path> {\n"
            + "it may only contain dimension points where {\n"
            + "it has theposition<my_lib:/path>.\n"
            + "}\n"
            + "}\n"
            + "define the potential position<my_lib:/path>.\n"
        )
    assert exc_info.value.token == "position<my_lib:/path"
    assert exc_info.value.line == 8
    assert exc_info.value.column == 11


def test_create_dimension_point_missing_reference(
    p: parser.Parser,
) -> None:
    # TODO: I don't love this error classification here, it's not as clear
    # as it could be.
    with pytest.raises(parser_exceptions.InvalidActionStatementsBlock) as exc_info:
        p.parse(
            "define the potential action<mv:define-lang.org:parser:/path> {\n"
            + "it happens when {\n"
            + "} and it does {\n"
            + "create a dimension point in.\n"
            + "}\n"
            + "}\n"
        )
    assert exc_info.value.line == 4
    assert exc_info.value.column == 1


def test_create_dimension_point_reference_missing_name_after_chain_separator(
    p: parser.Parser,
) -> None:
    with pytest.raises(parser_exceptions.ExpectedNameType) as exc_info:
        p.parse(
            "define the potential action<mv:define-lang.org:parser:/path> {\n"
            + "it happens when {\n"
            + "} and it does {\n"
            + "create a dimension point in position<foo>::.\n"
            + "}\n"
            + "}\n"
        )
    assert exc_info.value.token == "."
    assert exc_info.value.line == 4
    assert exc_info.value.column == 44


def test_create_dimension_point_reference_chain_separator_then_newline(
    p: parser.Parser,
) -> None:
    with pytest.raises(parser_exceptions.ExpectedNameType) as exc_info:
        p.parse(
            "define the potential action<mv:define-lang.org:parser:/path> {\n"
            + "it happens when {\n"
            + "} and it does {\n"
            + "create a dimension point in position<foo>::\n"
            + "}\n"
            + "}\n"
        )
    assert exc_info.value.token == "\n"
    assert exc_info.value.line == 4
    assert exc_info.value.column == 44


def test_create_dimension_point_reference_single_colon_then_newline(
    p: parser.Parser,
) -> None:
    with pytest.raises(
        parser_exceptions.ExpectedChainSeparatorOrTerminator
    ) as exc_info:
        p.parse(
            "define the potential action<mv:define-lang.org:parser:/path> {\n"
            + "it happens when {\n"
            + "} and it does {\n"
            + "create a dimension point in position<foo>:\n"
            + "}\n"
            + "}\n"
        )
    assert exc_info.value.token == ":"
    assert exc_info.value.token.type == "GLOBAL_NAME_CONTENT"
    assert exc_info.value.line == 4
    assert exc_info.value.column == 42


def test_name_content_forbids_double_colon_in_create_reference(
    p: parser.Parser,
) -> None:
    with pytest.raises(parser_exceptions.MissingCloseAngleBracket) as exc_info:
        p.parse(
            "define the potential action<mv:define-lang.org:parser:/path> {\n"
            + "it happens when {\n"
            + "} and it does {\n"
            + "create a dimension point in position</foo::bar>.\n"
            + "}\n"
            + "}\n"
        )
    assert exc_info.value.token == "::"
    assert str(exc_info.value.name) == "/foo"
    assert exc_info.value.line == 4
    assert exc_info.value.column == 42


def test_name_chain_invalid_item(
    p: parser.Parser,
) -> None:
    with pytest.raises(parser_exceptions.ExpectedNameType) as exc_info:
        p.parse(
            "define the potential action<mv:define-lang.org:parser:/path> {\n"
            + "it happens when {\n"
            + "} and it does {\n"
            + "create a dimension point in position<foo>::a\n"
            + "}\n"
            + "}\n"
        )
    assert exc_info.value.token == "a"
    assert exc_info.value.line == 4
    assert exc_info.value.column == 44


def test_move_dimension_point_missing_source_reference(
    p: parser.Parser,
) -> None:
    with pytest.raises(parser_exceptions.InvalidActionStatementsBlock) as exc_info:
        p.parse(
            "define the potential action<mv:define-lang.org:parser:/path> {\n"
            + "    it happens when {\n"
            + "    } and it does {\n"
            + "        move the dimension point in.\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.token == "move the dimension point in."
    assert exc_info.value.token.type == "LOCAL_NAME_CONTENT"
    assert exc_info.value.line == 4
    assert exc_info.value.column == 9


def test_move_dimension_point_missing_to_keyword(
    p: parser.Parser,
) -> None:
    with pytest.raises(parser_exceptions.InvalidMoveStatementSyntax) as exc_info:
        p.parse(
            "define the potential action<mv:define-lang.org:parser:/path> {\n"
            + "    it happens when {\n"
            + "    } and it does {\n"
            + "        move the dimension point in position<src> position<dest>.\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.token == " position<dest"
    assert exc_info.value.token.type == "LOCAL_NAME_CONTENT"
    assert exc_info.value.line == 4
    assert exc_info.value.column == 50


def test_move_dimension_point_missing_destination_reference(
    p: parser.Parser,
) -> None:
    with pytest.raises(parser_exceptions.InvalidMoveStatementSyntax) as exc_info:
        p.parse(
            "define the potential action<mv:define-lang.org:parser:/path> {\n"
            + "    it happens when {\n"
            + "    } and it does {\n"
            + "        move the dimension point in position<src> to.\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.token == " to."
    assert exc_info.value.token.type == "LOCAL_NAME_CONTENT"
    assert exc_info.value.line == 4
    assert exc_info.value.column == 50


def test_move_dimension_point_chain_separator_after_source_then_terminator(
    p: parser.Parser,
) -> None:
    with pytest.raises(parser_exceptions.ExpectedNameType) as exc_info:
        p.parse(
            "define the potential action<mv:define-lang.org:parser:/path> {\n"
            + "    it happens when {\n"
            + "    } and it does {\n"
            + "        move the dimension point in position<foo>::.\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.token == "."
    assert exc_info.value.token.type == "LOCAL_NAME_CONTENT"
    assert exc_info.value.line == 4
    assert exc_info.value.column == 52


def test_move_dimension_point_chain_separator_after_source_then_newline(
    p: parser.Parser,
) -> None:
    with pytest.raises(parser_exceptions.ExpectedNameType) as exc_info:
        p.parse(
            "define the potential action<mv:define-lang.org:parser:/path> {\n"
            + "    it happens when {\n"
            + "    } and it does {\n"
            + "        move the dimension point in position<foo>::\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.token == "\n"
    assert exc_info.value.token.type == "NEWLINE"
    assert exc_info.value.line == 4
    assert exc_info.value.column == 52


def test_move_dimension_point_chain_separator_after_destination_then_terminator(
    p: parser.Parser,
) -> None:
    with pytest.raises(parser_exceptions.ExpectedNameType) as exc_info:
        p.parse(
            "define the potential action<mv:define-lang.org:parser:/path> {\n"
            + "    it happens when {\n"
            + "    } and it does {\n"
            + "        move the dimension point in position<src> to position<dest>::.\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.token == "."
    assert exc_info.value.token.type == "LOCAL_NAME_CONTENT"
    assert exc_info.value.line == 4
    assert exc_info.value.column == 70


def test_move_dimension_point_chain_separator_after_destination_then_newline(
    p: parser.Parser,
) -> None:
    with pytest.raises(parser_exceptions.ExpectedNameType) as exc_info:
        p.parse(
            "define the potential action<mv:define-lang.org:parser:/path> {\n"
            + "    it happens when {\n"
            + "    } and it does {\n"
            + "        move the dimension point in position<src> to position<dest>::\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.token == "\n"
    assert exc_info.value.token.type == "NEWLINE"
    assert exc_info.value.line == 4
    assert exc_info.value.column == 70


def test_move_dimension_point_single_colon_after_source(
    p: parser.Parser,
) -> None:
    with pytest.raises(parser_exceptions.InvalidMoveStatementSyntax) as exc_info:
        p.parse(
            "define the potential action<mv:define-lang.org:parser:/path> {\n"
            + "    it happens when {\n"
            + "    } and it does {\n"
            + "        move the dimension point in position<foo>:\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.token == ":"
    assert exc_info.value.token.type == "GLOBAL_NAME_CONTENT"
    assert exc_info.value.line == 4
    assert exc_info.value.column == 50


def test_move_dimension_point_single_colon_after_destination(
    p: parser.Parser,
) -> None:
    with pytest.raises(
        parser_exceptions.ExpectedChainSeparatorOrTerminator
    ) as exc_info:
        p.parse(
            "define the potential action<mv:define-lang.org:parser:/path> {\n"
            + "    it happens when {\n"
            + "    } and it does {\n"
            + "        move the dimension point in position<src> to position<dest>:\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.token == ":"
    assert exc_info.value.token.type == "GLOBAL_NAME_CONTENT"
    assert exc_info.value.line == 4
    assert exc_info.value.column == 68


def test_move_dimension_point_no_space_before_to(
    p: parser.Parser,
) -> None:
    with pytest.raises(parser_exceptions.InvalidMoveStatementSyntax) as exc_info:
        p.parse(
            "define the potential action<mv:define-lang.org:parser:/path> {\n"
            + "    it happens when {\n"
            + "    } and it does {\n"
            + "        move the dimension point in position<src>to position<dest>.\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.token == "to position<dest"
    assert exc_info.value.token.type == "LOCAL_NAME_CONTENT"
    assert exc_info.value.line == 4
    assert exc_info.value.column == 50


def test_move_dimension_point_no_space_after_to(
    p: parser.Parser,
) -> None:
    with pytest.raises(parser_exceptions.InvalidMoveStatementSyntax) as exc_info:
        p.parse(
            "define the potential action<mv:define-lang.org:parser:/path> {\n"
            + "    it happens when {\n"
            + "    } and it does {\n"
            + "        move the dimension point in position<src> toposition<dest>.\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.token == " toposition<dest"
    assert exc_info.value.token.type == "LOCAL_NAME_CONTENT"
    assert exc_info.value.line == 4
    assert exc_info.value.column == 50


def test_move_dimension_point_missing_terminator_after_destination(
    p: parser.Parser,
) -> None:
    with pytest.raises(
        parser_exceptions.ExpectedChainSeparatorOrTerminator
    ) as exc_info:
        p.parse(
            "define the potential action<mv:define-lang.org:parser:/path> {\n"
            + "    it happens when {\n"
            + "    } and it does {\n"
            + "        move the dimension point in position<src> to position<dest>\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.token == "\n"
    assert exc_info.value.token.type == "NEWLINE"
    assert exc_info.value.line == 4
    assert exc_info.value.column == 68


def test_move_keyword_then_newline(
    p: parser.Parser,
) -> None:
    with pytest.raises(parser_exceptions.InvalidActionStatementsBlock) as exc_info:
        p.parse(
            "define the potential action<mv:define-lang.org:parser:/path> {\n"
            + "    it happens when {\n"
            + "    } and it does {\n"
            + "        move\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.token == "move"
    assert exc_info.value.token.type == "LOCAL_NAME_CONTENT"
    assert exc_info.value.line == 4
    assert exc_info.value.column == 9


def test_move_dimension_point_in_space_dot(
    p: parser.Parser,
) -> None:
    with pytest.raises(parser_exceptions.ExpectedNameType) as exc_info:
        p.parse(
            "define the potential action<mv:define-lang.org:parser:/path> {\n"
            + "    it happens when {\n"
            + "    } and it does {\n"
            + "        move the dimension point in .\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.token == "."
    assert exc_info.value.token.type == "LOCAL_NAME_CONTENT"
    assert exc_info.value.line == 4
    assert exc_info.value.column == 37
