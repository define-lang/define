# pyright: reportUnusedCallResult=false
"""Incomplete statement parser tests.

Follow parser test authoring rules in parser_tests/AGENTS.md.
"""

from define.compiler import parser, parser_exceptions


def test_empty_file(p: parser.Parser) -> None:
    result = p.parse("")
    assert isinstance(result.exception, parser_exceptions.ExpectedGlobalDefinition)
    assert result.exception.token == ""
    assert result.exception.line == 1
    assert result.exception.column == 1


def test_file_all_newlines(p: parser.Parser) -> None:
    result = p.parse("\n\n\n")
    assert isinstance(result.exception, parser_exceptions.ExpectedGlobalDefinition)
    assert result.exception.token == ""
    assert result.exception.line == 3
    assert result.exception.column == 1


def test_define_the_potential_incomplete_global_prefix(p: parser.Parser) -> None:
    result = p.parse("define the potential\n")
    assert isinstance(result.exception, parser_exceptions.ExpectedGlobalDefinition)
    assert result.exception.token == "define the potential"
    assert result.exception.line == 1
    assert result.exception.column == 1


def test_global_position_block_open_without_content(p: parser.Parser) -> None:
    result = p.parse(
        "define the potential position<mv:define-lang.org:parser:/path> {\n"
    )
    assert isinstance(
        result.exception, parser_exceptions.InvalidPositionDefinitionBlock
    )
    assert result.exception.token == ""
    assert result.exception.line == 1
    assert result.exception.column == 65


def test_global_action_block_open_without_content(p: parser.Parser) -> None:
    result = p.parse("define the potential action<mv:define-lang.org:parser:/path> {\n")
    assert isinstance(result.exception, parser_exceptions.InvalidActionDefinitionsBlock)
    assert result.exception.token == ""
    assert result.exception.line == 1
    assert result.exception.column == 63


def test_position_block_missing_required_clause(p: parser.Parser) -> None:
    result = p.parse(
        "define the potential position<mv:define-lang.org:parser:/path> {\n" + "}\n"
    )
    assert isinstance(
        result.exception, parser_exceptions.MissingPositionDefinitionContent
    )
    assert result.exception.token == "}"
    assert result.exception.line == 2
    assert result.exception.column == 1


def test_position_required_clause_missing_open_brace(p: parser.Parser) -> None:
    result = p.parse(
        "define the potential position<mv:define-lang.org:parser:/path> {\n"
        + "it may only contain dimension points where\n"
        + "}\n"
    )
    assert isinstance(result.exception, parser_exceptions.MissingOpenBrace)
    assert result.exception.token == "\n"
    assert result.exception.line == 2
    assert result.exception.column == 43


def test_action_block_missing_trigger_clause(p: parser.Parser) -> None:
    result = p.parse(
        "define the potential action<mv:define-lang.org:parser:/path> {\n" + "}\n"
    )
    assert isinstance(result.exception, parser_exceptions.MissingActionDefinitionSyntax)
    assert result.exception.token == "}"
    assert result.exception.line == 2
    assert result.exception.column == 1


def test_action_trigger_clause_missing_open_brace(p: parser.Parser) -> None:
    result = p.parse(
        "define the potential action<mv:define-lang.org:parser:/path> {\n"
        + "it happens when\n"
        + "}\n"
    )
    assert isinstance(result.exception, parser_exceptions.MissingOpenBrace)
    assert result.exception.token == "\n"
    assert result.exception.line == 2
    assert result.exception.column == 16


def test_action_missing_and_it_does_clause(p: parser.Parser) -> None:
    result = p.parse(
        "define the potential action<mv:define-lang.org:parser:/path> {\n"
        + "define the position<run>.\n"
        + "it happens when {\n"
        + "the position<run> has a dimension point.\n"
        + "}\n"
        + "}\n"
    )
    assert isinstance(result.exception, parser_exceptions.MissingActionStatementsBlock)
    assert result.exception.token == "\n"
    assert result.exception.line == 5
    assert result.exception.column == 2


def test_action_and_it_does_clause_missing_open_brace(p: parser.Parser) -> None:
    result = p.parse(
        "define the potential action<mv:define-lang.org:parser:/path> {\n"
        + "define the position<run>.\n"
        + "it happens when {\n"
        + "the position<run> has a dimension point.\n"
        + "} and it does\n"
        + "}\n"
    )
    assert isinstance(result.exception, parser_exceptions.MissingOpenBrace)
    assert result.exception.token == "\n"
    assert result.exception.line == 5
    assert result.exception.column == 14


def test_action_and_it_does_block_missing_close_brace(p: parser.Parser) -> None:
    result = p.parse(
        "define the potential action<mv:define-lang.org:parser:/path> {\n"
        + "define the position<run>.\n"
        + "it happens when {\n"
        + "the position<run> has a dimension point.\n"
        + "} and it does {\n"
        + "}\n"
    )
    assert isinstance(result.exception, parser_exceptions.MissingCloseBrace)
    assert result.exception.token == ""
    assert result.exception.line == 6
    assert result.exception.column == 2


def test_local_position_keyword_without_name_in_action_definition_block(
    p: parser.Parser,
) -> None:
    result = p.parse(
        "define the potential action<mv:define-lang.org:parser:/path> {\n"
        + "define the position<run>.\n"
        + "define the position\n"
        + "it happens when {\n"
        + "the position<run> has a dimension point.\n"
        + "} and it does {\n"
        + "}\n"
        + "}\n"
    )
    assert isinstance(result.exception, parser_exceptions.MissingOpenAngleBracket)
    assert result.exception.token == "\n"
    assert result.exception.line == 3
    assert result.exception.column == 20


def test_local_position_keyword_without_name_in_action_statements_block(
    p: parser.Parser,
) -> None:
    result = p.parse(
        "define the potential action<mv:define-lang.org:parser:/path> {\n"
        + "define the position<run>.\n"
        + "it happens when {\n"
        + "the position<run> has a dimension point.\n"
        + "} and it does {\n"
        + "define the position\n"
        + "}\n"
        + "}\n"
    )
    assert isinstance(result.exception, parser_exceptions.MissingOpenAngleBracket)
    assert result.exception.token == "\n"
    assert result.exception.line == 6
    assert result.exception.column == 20


def test_global_position_keyword_without_name(p: parser.Parser) -> None:
    result = p.parse("define the potential position\n")
    assert isinstance(result.exception, parser_exceptions.MissingOpenAngleBracket)
    assert result.exception.token == "\n"
    assert result.exception.line == 1
    assert result.exception.column == 30


def test_position_requirement_missing_name(p: parser.Parser) -> None:
    result = p.parse(
        "define the potential position<mv:define-lang.org:parser:/path> {\n"
        + "it may only contain dimension points where {\n"
        + "it has the position\n"
        + "}\n"
        + "}\n"
    )
    assert isinstance(result.exception, parser_exceptions.MissingOpenAngleBracket)
    assert result.exception.token == "\n"
    assert result.exception.line == 3
    assert result.exception.column == 20


def test_position_requirement_missing_name_after_type(p: parser.Parser) -> None:
    result = p.parse(
        "define the potential position<mv:define-lang.org:parser:/path> {\n"
        + "it may only contain dimension points where {\n"
        + "it has the position.\n"
        + "}\n"
        + "}\n"
    )
    assert isinstance(result.exception, parser_exceptions.MissingOpenAngleBracket)
    assert result.exception.token == "."
    assert result.exception.line == 3
    assert result.exception.column == 20


def test_position_requirement_name_starts_and_then_newline(p: parser.Parser) -> None:
    result = p.parse(
        "define the potential position<mv:define-lang.org:parser:/path> {\n"
        + "it may only contain dimension points where {\n"
        + "it has the position<\n"
        + "/path>.\n"
        + "}\n"
        + "}\n"
    )
    assert isinstance(result.exception, parser_exceptions.EmptyName)
    assert result.exception.token == "\n"
    assert result.exception.line == 3
    assert result.exception.column == 21


def test_position_requirement_missing_space_after_it_has_the(p: parser.Parser) -> None:
    result = p.parse(
        "define the potential action<example.com:my_lib:/path> {\n"
        + "define the position<run>.\n"
        + "it happens when {\n"
        + "the position<run> has a dimension point.\n"
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
    assert isinstance(result.exception, parser_exceptions.MissingWhitespace)
    assert result.exception.token == "position<my_lib:/path"
    assert result.exception.line == 10
    assert result.exception.column == 11


def test_create_dimension_point_missing_reference(
    p: parser.Parser,
) -> None:
    # TODO: I don't love this error classification here, it's not as clear
    # as it could be.
    result = p.parse(
        "define the potential action<mv:define-lang.org:parser:/path> {\n"
        + "define the position<run>.\n"
        + "it happens when {\n"
        + "the position<run> has a dimension point.\n"
        + "} and it does {\n"
        + "create a dimension point in.\n"
        + "}\n"
        + "}\n"
    )
    assert isinstance(result.exception, parser_exceptions.InvalidActionStatementsBlock)
    assert result.exception.line == 6
    assert result.exception.column == 1


def test_create_dimension_point_reference_missing_name_after_chain_separator(
    p: parser.Parser,
) -> None:
    result = p.parse(
        "define the potential action<mv:define-lang.org:parser:/path> {\n"
        + "define the position<run>.\n"
        + "it happens when {\n"
        + "the position<run> has a dimension point.\n"
        + "} and it does {\n"
        + "create a dimension point in position<foo>::.\n"
        + "}\n"
        + "}\n"
    )
    assert isinstance(result.exception, parser_exceptions.ExpectedNameType)
    assert result.exception.token == "."
    assert result.exception.line == 6
    assert result.exception.column == 44


def test_create_dimension_point_reference_chain_separator_then_newline(
    p: parser.Parser,
) -> None:
    result = p.parse(
        "define the potential action<mv:define-lang.org:parser:/path> {\n"
        + "define the position<run>.\n"
        + "it happens when {\n"
        + "the position<run> has a dimension point.\n"
        + "} and it does {\n"
        + "create a dimension point in position<foo>::\n"
        + "}\n"
        + "}\n"
    )
    assert isinstance(result.exception, parser_exceptions.ExpectedNameType)
    assert result.exception.token == "\n"
    assert result.exception.line == 6
    assert result.exception.column == 44


def test_create_dimension_point_reference_single_colon_then_newline(
    p: parser.Parser,
) -> None:
    result = p.parse(
        "define the potential action<mv:define-lang.org:parser:/path> {\n"
        + "define the position<run>.\n"
        + "it happens when {\n"
        + "the position<run> has a dimension point.\n"
        + "} and it does {\n"
        + "create a dimension point in position<foo>:\n"
        + "}\n"
        + "}\n"
    )
    assert isinstance(
        result.exception, parser_exceptions.ExpectedChainSeparatorOrTerminator
    )
    assert result.exception.token == ":"
    assert result.exception.token.type == "GLOBAL_NAME_CONTENT"
    assert result.exception.line == 6
    assert result.exception.column == 42


def test_name_content_forbids_double_colon_in_create_reference(
    p: parser.Parser,
) -> None:
    result = p.parse(
        "define the potential action<mv:define-lang.org:parser:/path> {\n"
        + "define the position<run>.\n"
        + "it happens when {\n"
        + "the position<run> has a dimension point.\n"
        + "} and it does {\n"
        + "create a dimension point in position</foo::bar>.\n"
        + "}\n"
        + "}\n"
    )
    assert isinstance(result.exception, parser_exceptions.MissingCloseAngleBracket)
    assert result.exception.token == "::"
    assert str(result.exception.name) == "/foo"
    assert result.exception.line == 6
    assert result.exception.column == 42


def test_name_chain_invalid_item(
    p: parser.Parser,
) -> None:
    result = p.parse(
        "define the potential action<mv:define-lang.org:parser:/path> {\n"
        + "define the position<run>.\n"
        + "it happens when {\n"
        + "the position<run> has a dimension point.\n"
        + "} and it does {\n"
        + "create a dimension point in position<foo>::a\n"
        + "}\n"
        + "}\n"
    )
    assert isinstance(result.exception, parser_exceptions.ExpectedNameType)
    assert result.exception.token == "a"
    assert result.exception.line == 6
    assert result.exception.column == 44


def test_move_dimension_point_missing_source_reference(
    p: parser.Parser,
) -> None:
    result = p.parse(
        "define the potential action<mv:define-lang.org:parser:/path> {\n"
        + "    define the position<run>.\n"
        + "    it happens when {\n"
        + "        the position<run> has a dimension point.\n"
        + "    } and it does {\n"
        + "        move the dimension point in.\n"
        + "    }\n"
        + "}\n"
    )
    assert isinstance(result.exception, parser_exceptions.InvalidActionStatementsBlock)
    assert result.exception.token == "move the dimension point in."
    assert result.exception.token.type == "LOCAL_NAME_CONTENT"
    assert result.exception.line == 6
    assert result.exception.column == 9


def test_move_dimension_point_missing_to_keyword(
    p: parser.Parser,
) -> None:
    result = p.parse(
        "define the potential action<mv:define-lang.org:parser:/path> {\n"
        + "    define the position<run>.\n"
        + "    it happens when {\n"
        + "        the position<run> has a dimension point.\n"
        + "    } and it does {\n"
        + "        move the dimension point in position<src> position<dest>.\n"
        + "    }\n"
        + "}\n"
    )
    assert isinstance(result.exception, parser_exceptions.InvalidMoveStatementSyntax)
    assert result.exception.token == " position<dest"
    assert result.exception.token.type == "LOCAL_NAME_CONTENT"
    assert result.exception.line == 6
    assert result.exception.column == 50


def test_move_dimension_point_missing_destination_reference(
    p: parser.Parser,
) -> None:
    result = p.parse(
        "define the potential action<mv:define-lang.org:parser:/path> {\n"
        + "    define the position<run>.\n"
        + "    it happens when {\n"
        + "        the position<run> has a dimension point.\n"
        + "    } and it does {\n"
        + "        move the dimension point in position<src> to.\n"
        + "    }\n"
        + "}\n"
    )
    assert isinstance(result.exception, parser_exceptions.InvalidMoveStatementSyntax)
    assert result.exception.token == " to."
    assert result.exception.token.type == "LOCAL_NAME_CONTENT"
    assert result.exception.line == 6
    assert result.exception.column == 50


def test_move_dimension_point_chain_separator_after_source_then_terminator(
    p: parser.Parser,
) -> None:
    result = p.parse(
        "define the potential action<mv:define-lang.org:parser:/path> {\n"
        + "    define the position<run>.\n"
        + "    it happens when {\n"
        + "        the position<run> has a dimension point.\n"
        + "    } and it does {\n"
        + "        move the dimension point in position<foo>::.\n"
        + "    }\n"
        + "}\n"
    )
    assert isinstance(result.exception, parser_exceptions.ExpectedNameType)
    assert result.exception.token == "."
    assert result.exception.token.type == "LOCAL_NAME_CONTENT"
    assert result.exception.line == 6
    assert result.exception.column == 52


def test_move_dimension_point_chain_separator_after_source_then_newline(
    p: parser.Parser,
) -> None:
    result = p.parse(
        "define the potential action<mv:define-lang.org:parser:/path> {\n"
        + "    define the position<run>.\n"
        + "    it happens when {\n"
        + "        the position<run> has a dimension point.\n"
        + "    } and it does {\n"
        + "        move the dimension point in position<foo>::\n"
        + "    }\n"
        + "}\n"
    )
    assert isinstance(result.exception, parser_exceptions.ExpectedNameType)
    assert result.exception.token == "\n"
    assert result.exception.token.type == "NEWLINE"
    assert result.exception.line == 6
    assert result.exception.column == 52


def test_move_dimension_point_chain_separator_after_destination_then_terminator(
    p: parser.Parser,
) -> None:
    result = p.parse(
        "define the potential action<mv:define-lang.org:parser:/path> {\n"
        + "    define the position<run>.\n"
        + "    it happens when {\n"
        + "        the position<run> has a dimension point.\n"
        + "    } and it does {\n"
        + "        move the dimension point in position<src> to position<dest>::.\n"
        + "    }\n"
        + "}\n"
    )
    assert isinstance(result.exception, parser_exceptions.ExpectedNameType)
    assert result.exception.token == "."
    assert result.exception.token.type == "LOCAL_NAME_CONTENT"
    assert result.exception.line == 6
    assert result.exception.column == 70


def test_move_dimension_point_chain_separator_after_destination_then_newline(
    p: parser.Parser,
) -> None:
    result = p.parse(
        "define the potential action<mv:define-lang.org:parser:/path> {\n"
        + "    define the position<run>.\n"
        + "    it happens when {\n"
        + "        the position<run> has a dimension point.\n"
        + "    } and it does {\n"
        + "        move the dimension point in position<src> to position<dest>::\n"
        + "    }\n"
        + "}\n"
    )
    assert isinstance(result.exception, parser_exceptions.ExpectedNameType)
    assert result.exception.token == "\n"
    assert result.exception.token.type == "NEWLINE"
    assert result.exception.line == 6
    assert result.exception.column == 70


def test_move_dimension_point_single_colon_after_source(
    p: parser.Parser,
) -> None:
    result = p.parse(
        "define the potential action<mv:define-lang.org:parser:/path> {\n"
        + "    define the position<run>.\n"
        + "    it happens when {\n"
        + "        the position<run> has a dimension point.\n"
        + "    } and it does {\n"
        + "        move the dimension point in position<foo>:\n"
        + "    }\n"
        + "}\n"
    )
    assert isinstance(result.exception, parser_exceptions.InvalidMoveStatementSyntax)
    assert result.exception.token == ":"
    assert result.exception.token.type == "GLOBAL_NAME_CONTENT"
    assert result.exception.line == 6
    assert result.exception.column == 50


def test_move_dimension_point_single_colon_after_destination(
    p: parser.Parser,
) -> None:
    result = p.parse(
        "define the potential action<mv:define-lang.org:parser:/path> {\n"
        + "    define the position<run>.\n"
        + "    it happens when {\n"
        + "        the position<run> has a dimension point.\n"
        + "    } and it does {\n"
        + "        move the dimension point in position<src> to position<dest>:\n"
        + "    }\n"
        + "}\n"
    )
    assert isinstance(
        result.exception, parser_exceptions.ExpectedChainSeparatorOrTerminator
    )
    assert result.exception.token == ":"
    assert result.exception.token.type == "GLOBAL_NAME_CONTENT"
    assert result.exception.line == 6
    assert result.exception.column == 68


def test_move_dimension_point_no_space_before_to(
    p: parser.Parser,
) -> None:
    result = p.parse(
        "define the potential action<mv:define-lang.org:parser:/path> {\n"
        + "    define the position<run>.\n"
        + "    it happens when {\n"
        + "        the position<run> has a dimension point.\n"
        + "    } and it does {\n"
        + "        move the dimension point in position<src>to position<dest>.\n"
        + "    }\n"
        + "}\n"
    )
    assert isinstance(result.exception, parser_exceptions.InvalidMoveStatementSyntax)
    assert result.exception.token == "to position<dest"
    assert result.exception.token.type == "LOCAL_NAME_CONTENT"
    assert result.exception.line == 6
    assert result.exception.column == 50


def test_move_dimension_point_no_space_after_to(
    p: parser.Parser,
) -> None:
    result = p.parse(
        "define the potential action<mv:define-lang.org:parser:/path> {\n"
        + "    define the position<run>.\n"
        + "    it happens when {\n"
        + "        the position<run> has a dimension point.\n"
        + "    } and it does {\n"
        + "        move the dimension point in position<src> toposition<dest>.\n"
        + "    }\n"
        + "}\n"
    )
    assert isinstance(result.exception, parser_exceptions.InvalidMoveStatementSyntax)
    assert result.exception.token == " toposition<dest"
    assert result.exception.token.type == "LOCAL_NAME_CONTENT"
    assert result.exception.line == 6
    assert result.exception.column == 50


def test_move_dimension_point_missing_terminator_after_destination(
    p: parser.Parser,
) -> None:
    result = p.parse(
        "define the potential action<mv:define-lang.org:parser:/path> {\n"
        + "    define the position<run>.\n"
        + "    it happens when {\n"
        + "        the position<run> has a dimension point.\n"
        + "    } and it does {\n"
        + "        move the dimension point in position<src> to position<dest>\n"
        + "    }\n"
        + "}\n"
    )
    assert isinstance(
        result.exception, parser_exceptions.ExpectedChainSeparatorOrTerminator
    )
    assert result.exception.token == "\n"
    assert result.exception.token.type == "NEWLINE"
    assert result.exception.line == 6
    assert result.exception.column == 68


def test_move_keyword_then_newline(
    p: parser.Parser,
) -> None:
    result = p.parse(
        "define the potential action<mv:define-lang.org:parser:/path> {\n"
        + "    define the position<run>.\n"
        + "    it happens when {\n"
        + "        the position<run> has a dimension point.\n"
        + "    } and it does {\n"
        + "        move\n"
        + "    }\n"
        + "}\n"
    )
    assert isinstance(result.exception, parser_exceptions.InvalidActionStatementsBlock)
    assert result.exception.token == "move"
    assert result.exception.token.type == "LOCAL_NAME_CONTENT"
    assert result.exception.line == 6
    assert result.exception.column == 9


def test_move_dimension_point_in_space_dot(
    p: parser.Parser,
) -> None:
    result = p.parse(
        "define the potential action<mv:define-lang.org:parser:/path> {\n"
        + "    define the position<run>.\n"
        + "    it happens when {\n"
        + "        the position<run> has a dimension point.\n"
        + "    } and it does {\n"
        + "        move the dimension point in .\n"
        + "    }\n"
        + "}\n"
    )
    assert isinstance(result.exception, parser_exceptions.ExpectedNameType)
    assert result.exception.token == "."
    assert result.exception.token.type == "LOCAL_NAME_CONTENT"
    assert result.exception.line == 6
    assert result.exception.column == 37
