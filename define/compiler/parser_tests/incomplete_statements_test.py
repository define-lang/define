# pyright: reportUnusedCallResult=false
"""Incomplete statement parser tests.

Follow parser test authoring rules in parser_tests/AGENTS.md.
"""

import pytest

from define.compiler import parser_exceptions
from define.compiler.parser_tests.conftest import Parse
from define.compiler.parser_tests.test_helpers import get_tokens_by_type


def test_empty_file(parse: Parse) -> None:
    with pytest.raises(parser_exceptions.ExpectedGlobalDefinition) as exc_info:
        parse("")
    assert exc_info.value.token == ""
    assert exc_info.value.line == 1
    assert exc_info.value.column == 1


def test_file_all_newlines(parse: Parse) -> None:
    with pytest.raises(parser_exceptions.ExpectedGlobalDefinition) as exc_info:
        parse("\n\n\n")
    assert exc_info.value.token == ""
    assert exc_info.value.line == 3
    assert exc_info.value.column == 1


def test_define_the_potential_incomplete_global_prefix(parse: Parse) -> None:
    with pytest.raises(parser_exceptions.ExpectedGlobalDefinition) as exc_info:
        parse("define the potential\n")
    assert exc_info.value.token == "define"
    assert exc_info.value.line == 1
    assert exc_info.value.column == 1


def test_bare_colon_at_top_level(parse: Parse) -> None:
    with pytest.raises(parser_exceptions.ExpectedGlobalDefinition) as exc_info:
        parse(":\n")
    assert exc_info.value.token == ":"
    assert exc_info.value.token.type == "INVALID"
    assert exc_info.value.line == 1
    assert exc_info.value.column == 1


def test_bare_slash_at_top_level(parse: Parse) -> None:
    with pytest.raises(parser_exceptions.ExpectedGlobalDefinition) as exc_info:
        parse("/\n")
    assert exc_info.value.token == "/"
    assert exc_info.value.token.type == "INVALID"
    assert exc_info.value.line == 1
    assert exc_info.value.column == 1


def test_bare_colon_between_definitions(parse: Parse) -> None:
    with pytest.raises(parser_exceptions.ExpectedGlobalDefinition) as exc_info:
        parse("define the potential position<standard:/path>.\n" + ":\n")
    assert exc_info.value.token == ":"
    assert exc_info.value.token.type == "INVALID"
    assert exc_info.value.line == 2
    assert exc_info.value.column == 1


def test_bare_slash_between_definitions(parse: Parse) -> None:
    with pytest.raises(parser_exceptions.ExpectedGlobalDefinition) as exc_info:
        parse("define the potential position<standard:/path>.\n" + "/\n")
    assert exc_info.value.token == "/"
    assert exc_info.value.token.type == "INVALID"
    assert exc_info.value.line == 2
    assert exc_info.value.column == 1


def test_close_angle_colon_in_action_statements_block(parse: Parse) -> None:
    with pytest.raises(parser_exceptions.InvalidActionStatementsBlock) as exc_info:
        parse(
            "define the potential action<mv:define-lang.org:parser:/path> {\n"
            + "    define the position<run>.\n"
            + "    it happens when {\n"
            + "        the position<run> has a dimension point.\n"
            + "    } and it does {\n"
            + "        >:\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.line == 6
    assert exc_info.value.column == 9


def test_missing_open_angle_with_close_angle_colon(parse: Parse) -> None:
    with pytest.raises(parser_exceptions.MissingOpenAngleBracket) as exc_info:
        parse(
            "define the potential action<mv:define-lang.org:parser:/path> {\n"
            + "    define the position<run>.\n"
            + "    it happens when {\n"
            + "        the position<run> has a dimension point.\n"
            + "    } and it does {\n"
            + "        define the positionrun>:\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.token == "run"
    assert exc_info.value.name == "run"
    assert exc_info.value.line == 6
    assert exc_info.value.column == 28


def test_global_position_block_open_without_content(parse: Parse) -> None:
    with pytest.raises(
        parser_exceptions.InvalidPotentialPositionDefinitionBlock
    ) as exc_info:
        parse("define the potential position<mv:define-lang.org:parser:/path> {\n")
    assert exc_info.value.token == ""
    assert exc_info.value.line == 1
    assert exc_info.value.column == 65


def test_global_action_block_open_without_content(parse: Parse) -> None:
    with pytest.raises(parser_exceptions.InvalidActionDefinitionsBlock) as exc_info:
        parse("define the potential action<mv:define-lang.org:parser:/path> {\n")
    assert exc_info.value.token == ""
    assert exc_info.value.line == 1
    assert exc_info.value.column == 63


def test_position_block_missing_required_clause(parse: Parse) -> None:
    with pytest.raises(
        parser_exceptions.MissingPotentialPositionDefinitionContent
    ) as exc_info:
        parse(
            "define the potential position<mv:define-lang.org:parser:/path> {\n" + "}\n"
        )
    assert exc_info.value.token == "}"
    assert exc_info.value.line == 2
    assert exc_info.value.column == 1


def test_position_required_clause_missing_open_brace(parse: Parse) -> None:
    with pytest.raises(parser_exceptions.MissingOpenBrace) as exc_info:
        parse(
            "define the potential position<mv:define-lang.org:parser:/path> {\n"
            + "it may only contain dimension points where\n"
            + "}\n"
        )
    assert exc_info.value.token == "\n"
    assert exc_info.value.line == 2
    assert exc_info.value.column == 43


def test_action_block_missing_trigger_clause(parse: Parse) -> None:
    with pytest.raises(parser_exceptions.MissingActionDefinitionSyntax) as exc_info:
        parse(
            "define the potential action<mv:define-lang.org:parser:/path> {\n" + "}\n"
        )
    assert exc_info.value.token == "}"
    assert exc_info.value.line == 2
    assert exc_info.value.column == 1


def test_action_trigger_clause_missing_open_brace(parse: Parse) -> None:
    with pytest.raises(parser_exceptions.MissingOpenBrace) as exc_info:
        parse(
            "define the potential action<mv:define-lang.org:parser:/path> {\n"
            + "it happens when\n"
            + "}\n"
        )
    assert exc_info.value.token == "\n"
    assert exc_info.value.line == 2
    assert exc_info.value.column == 16


def test_action_missing_and_it_does_clause(parse: Parse) -> None:
    with pytest.raises(parser_exceptions.MissingActionStatementsBlock) as exc_info:
        parse(
            "define the potential action<mv:define-lang.org:parser:/path> {\n"
            + "    define the position<run>.\n"
            + "    it happens when {\n"
            + "        the position<run> has a dimension point.\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.token == "\n"
    assert exc_info.value.line == 5
    assert exc_info.value.column == 6


def test_action_and_it_does_clause_missing_open_brace(parse: Parse) -> None:
    with pytest.raises(parser_exceptions.MissingOpenBrace) as exc_info:
        parse(
            "define the potential action<mv:define-lang.org:parser:/path> {\n"
            + "    define the position<run>.\n"
            + "    it happens when {\n"
            + "        the position<run> has a dimension point.\n"
            + "    } and it does\n"
            + "}\n"
        )
    assert exc_info.value.token == "\n"
    assert exc_info.value.line == 5
    assert exc_info.value.column == 18


def test_action_and_it_does_block_missing_close_brace(parse: Parse) -> None:
    with pytest.raises(parser_exceptions.MissingCloseBrace) as exc_info:
        parse(
            "define the potential action<mv:define-lang.org:parser:/path> {\n"
            + "    define the position<run>.\n"
            + "    it happens when {\n"
            + "        the position<run> has a dimension point.\n"
            + "    } and it does {\n"
            + "}\n"
        )
    assert exc_info.value.token == ""
    assert exc_info.value.line == 6
    assert exc_info.value.column == 2


def test_local_position_keyword_without_name_in_action_definition_block(
    parse: Parse,
) -> None:
    with pytest.raises(parser_exceptions.MissingOpenAngleBracket) as exc_info:
        parse(
            "define the potential action<mv:define-lang.org:parser:/path> {\n"
            + "    define the position<run>.\n"
            + "    define the position\n"
            + "    it happens when {\n"
            + "        the position<run> has a dimension point.\n"
            + "    } and it does {\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.token == "\n"
    assert exc_info.value.line == 3
    assert exc_info.value.column == 24
    assert exc_info.value.name == "\n"


def test_local_position_keyword_without_name_in_action_statements_block(
    parse: Parse,
) -> None:
    with pytest.raises(parser_exceptions.MissingOpenAngleBracket) as exc_info:
        parse(
            "define the potential action<mv:define-lang.org:parser:/path> {\n"
            + "    define the position<run>.\n"
            + "    it happens when {\n"
            + "        the position<run> has a dimension point.\n"
            + "    } and it does {\n"
            + "        define the position\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.token == "\n"
    assert exc_info.value.line == 6
    assert exc_info.value.column == 28
    assert exc_info.value.name == "\n"


def test_global_position_keyword_without_name(parse: Parse) -> None:
    with pytest.raises(parser_exceptions.MissingOpenAngleBracket) as exc_info:
        parse("define the potential position\n")
    assert exc_info.value.token == "\n"
    assert exc_info.value.line == 1
    assert exc_info.value.column == 30
    assert exc_info.value.name == "\n"


def test_position_requirement_missing_name(parse: Parse) -> None:
    with pytest.raises(parser_exceptions.MissingOpenAngleBracket) as exc_info:
        parse(
            "define the potential position<mv:define-lang.org:parser:/path> {\n"
            + "    it may only contain dimension points where {\n"
            + "        it has the position\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.token == "\n"
    assert exc_info.value.line == 3
    assert exc_info.value.column == 28
    assert exc_info.value.name == "\n"


def test_position_requirement_missing_name_after_type(parse: Parse) -> None:
    with pytest.raises(parser_exceptions.MissingOpenAngleBracket) as exc_info:
        parse(
            "define the potential position<mv:define-lang.org:parser:/path> {\n"
            + "    it may only contain dimension points where {\n"
            + "        it has the position.\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.token == "."
    assert exc_info.value.line == 3
    assert exc_info.value.column == 28
    assert exc_info.value.name == "."


def test_position_requirement_missing_name_after_type_with_space(
    parse: Parse,
) -> None:
    with pytest.raises(parser_exceptions.MissingOpenAngleBracket) as exc_info:
        parse(
            "define the potential position<mv:define-lang.org:parser:/path> {\n"
            + "    it may only contain dimension points where {\n"
            + "        it has the position .\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.token == " "
    assert exc_info.value.token.type == "SPACE"
    assert exc_info.value.line == 3
    assert exc_info.value.column == 28
    assert exc_info.value.name == " "


def test_position_requirement_name_starts_and_then_newline(parse: Parse) -> None:
    with pytest.raises(parser_exceptions.EmptyName) as exc_info:
        parse(
            "define the potential position<mv:define-lang.org:parser:/path> {\n"
            + "    it may only contain dimension points where {\n"
            + "        it has the position<\n"
            + "        /path>.\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.token == "\n"
    assert exc_info.value.line == 3
    assert exc_info.value.column == 29


def test_position_requirement_missing_space_after_it_has_the(parse: Parse) -> None:
    with pytest.raises(parser_exceptions.MissingWhitespace) as exc_info:
        parse(
            "define the potential action<example.com:my_lib:/path> {\n"
            + "    define the position<run>.\n"
            + "    it happens when {\n"
            + "        the position<run> has a dimension point.\n"
            + "    } and it does {\n"
            + "    }\n"
            + "}\n"
            + "define the potential position<my_lib:/path> {\n"
            + "    it may only contain dimension points where {\n"
            + "        it has theposition<my_lib:/path>.\n"
            + "    }\n"
            + "}\n"
            + "define the potential position<my_lib:/path>.\n"
        )
    assert exc_info.value.token == "position"
    assert exc_info.value.token.type == "NAME_TYPE"
    assert exc_info.value.line == 10
    assert exc_info.value.column == 19


def test_create_dimension_point_missing_reference(
    parse: Parse,
) -> None:
    # TODO: I don't love this error classification here, it's not as clear
    # as it could be.
    with pytest.raises(parser_exceptions.InvalidActionStatementsBlock) as exc_info:
        parse(
            "define the potential action<mv:define-lang.org:parser:/path> {\n"
            + "    define the position<run>.\n"
            + "    it happens when {\n"
            + "        the position<run> has a dimension point.\n"
            + "    } and it does {\n"
            + "        create a dimension point in.\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.line == 6
    assert exc_info.value.column == 9


def test_create_dimension_point_reference_missing_name_after_chain_separator(
    parse: Parse,
) -> None:
    with pytest.raises(parser_exceptions.ExpectedNameType) as exc_info:
        parse(
            "define the potential action<mv:define-lang.org:parser:/path> {\n"
            + "    define the position<run>.\n"
            + "    it happens when {\n"
            + "        the position<run> has a dimension point.\n"
            + "    } and it does {\n"
            + "        create a dimension point in position<foo>::.\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.token == "."
    assert exc_info.value.line == 6
    assert exc_info.value.column == 52


def test_create_dimension_point_reference_chain_separator_then_newline(
    parse: Parse,
) -> None:
    with pytest.raises(parser_exceptions.ExpectedNameType) as exc_info:
        parse(
            "define the potential action<mv:define-lang.org:parser:/path> {\n"
            + "    define the position<run>.\n"
            + "    it happens when {\n"
            + "        the position<run> has a dimension point.\n"
            + "    } and it does {\n"
            + "        create a dimension point in position<foo>::\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.token == "\n"
    assert exc_info.value.line == 6
    assert exc_info.value.column == 52


def test_create_dimension_point_reference_single_colon_then_newline(
    parse: Parse,
) -> None:
    with pytest.raises(
        parser_exceptions.ExpectedChainSeparatorOrTerminator
    ) as exc_info:
        parse(
            "define the potential action<mv:define-lang.org:parser:/path> {\n"
            + "    define the position<run>.\n"
            + "    it happens when {\n"
            + "        the position<run> has a dimension point.\n"
            + "    } and it does {\n"
            + "        create a dimension point in position<foo>:\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.token == ":"
    assert exc_info.value.token.type == "INVALID"
    assert exc_info.value.line == 6
    assert exc_info.value.column == 50


def test_create_dimension_point_reference_single_slash_then_newline(
    parse: Parse,
) -> None:
    with pytest.raises(
        parser_exceptions.ExpectedChainSeparatorOrTerminator
    ) as exc_info:
        parse(
            "define the potential action<mv:define-lang.org:parser:/path> {\n"
            + "    define the position<run>.\n"
            + "    it happens when {\n"
            + "        the position<run> has a dimension point.\n"
            + "    } and it does {\n"
            + "        create a dimension point in position<foo>/\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.token == "/"
    assert exc_info.value.token.type == "INVALID"
    assert exc_info.value.line == 6
    assert exc_info.value.column == 50


def test_double_colon_in_create_reference_parses_as_global_name(
    parse: Parse,
) -> None:
    tree = parse(
        "define the potential action<mv:define-lang.org:parser:/path> {\n"
        + "    define the position<run>.\n"
        + "    it happens when {\n"
        + "        the position<run> has a dimension point.\n"
        + "    } and it does {\n"
        + "        create a dimension point in position</foo::bar>.\n"
        + "    }\n"
        + "}\n"
    )
    assert get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/path",
        "/foo::bar",
    ]


def test_destroy_dimension_point_missing_reference(
    parse: Parse,
) -> None:
    with pytest.raises(parser_exceptions.InvalidActionStatementsBlock) as exc_info:
        parse(
            "define the potential action<mv:define-lang.org:parser:/path> {\n"
            + "    define the position<run>.\n"
            + "    it happens when {\n"
            + "        the position<run> has a dimension point.\n"
            + "    } and it does {\n"
            + "        destroy the dimension point in.\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.line == 6
    assert exc_info.value.column == 9


def test_destroy_dimension_point_reference_missing_name_after_chain_separator(
    parse: Parse,
) -> None:
    with pytest.raises(parser_exceptions.ExpectedNameType) as exc_info:
        parse(
            "define the potential action<mv:define-lang.org:parser:/path> {\n"
            + "    define the position<run>.\n"
            + "    it happens when {\n"
            + "        the position<run> has a dimension point.\n"
            + "    } and it does {\n"
            + "        destroy the dimension point in position<foo>::.\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.token == "."
    assert exc_info.value.line == 6
    assert exc_info.value.column == 55


def test_destroy_dimension_point_reference_chain_separator_then_newline(
    parse: Parse,
) -> None:
    with pytest.raises(parser_exceptions.ExpectedNameType) as exc_info:
        parse(
            "define the potential action<mv:define-lang.org:parser:/path> {\n"
            + "    define the position<run>.\n"
            + "    it happens when {\n"
            + "        the position<run> has a dimension point.\n"
            + "    } and it does {\n"
            + "        destroy the dimension point in position<foo>::\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.token == "\n"
    assert exc_info.value.line == 6
    assert exc_info.value.column == 55


def test_destroy_dimension_point_reference_single_colon_then_newline(
    parse: Parse,
) -> None:
    with pytest.raises(
        parser_exceptions.ExpectedChainSeparatorOrTerminator
    ) as exc_info:
        parse(
            "define the potential action<mv:define-lang.org:parser:/path> {\n"
            + "    define the position<run>.\n"
            + "    it happens when {\n"
            + "        the position<run> has a dimension point.\n"
            + "    } and it does {\n"
            + "        destroy the dimension point in position<foo>:\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.token == ":"
    assert exc_info.value.token.type == "INVALID"
    assert exc_info.value.line == 6
    assert exc_info.value.column == 53


def test_double_colon_in_destroy_reference_parses_as_global_name(
    parse: Parse,
) -> None:
    tree = parse(
        "define the potential action<mv:define-lang.org:parser:/path> {\n"
        + "    define the position<run>.\n"
        + "    it happens when {\n"
        + "        the position<run> has a dimension point.\n"
        + "    } and it does {\n"
        + "        destroy the dimension point in position</foo::bar>.\n"
        + "    }\n"
        + "}\n"
    )
    assert get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/path",
        "/foo::bar",
    ]


def test_name_chain_invalid_item(
    parse: Parse,
) -> None:
    with pytest.raises(parser_exceptions.ExpectedNameType) as exc_info:
        parse(
            "define the potential action<mv:define-lang.org:parser:/path> {\n"
            + "    define the position<run>.\n"
            + "    it happens when {\n"
            + "        the position<run> has a dimension point.\n"
            + "    } and it does {\n"
            + "        create a dimension point in position<foo>::a\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.token == "a"
    assert exc_info.value.line == 6
    assert exc_info.value.column == 52


def test_move_dimension_point_missing_source_reference(
    parse: Parse,
) -> None:
    with pytest.raises(parser_exceptions.InvalidActionStatementsBlock) as exc_info:
        parse(
            "define the potential action<mv:define-lang.org:parser:/path> {\n"
            + "    define the position<run>.\n"
            + "    it happens when {\n"
            + "        the position<run> has a dimension point.\n"
            + "    } and it does {\n"
            + "        move the dimension point in.\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.token == "move"
    assert exc_info.value.token.type == "LOCAL_NAME_CONTENT"
    assert exc_info.value.line == 6
    assert exc_info.value.column == 9


def test_move_dimension_point_missing_to_keyword(
    parse: Parse,
) -> None:
    with pytest.raises(parser_exceptions.InvalidMoveStatementSyntax) as exc_info:
        parse(
            "define the potential action<mv:define-lang.org:parser:/path> {\n"
            + "    define the position<run>.\n"
            + "    it happens when {\n"
            + "        the position<run> has a dimension point.\n"
            + "    } and it does {\n"
            + "        move the dimension point in position<src> position<dest>.\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.token == " "
    assert exc_info.value.token.type == "SPACE"
    assert exc_info.value.line == 6
    assert exc_info.value.column == 50


def test_move_dimension_point_missing_destination_reference(
    parse: Parse,
) -> None:
    with pytest.raises(parser_exceptions.InvalidMoveStatementSyntax) as exc_info:
        parse(
            "define the potential action<mv:define-lang.org:parser:/path> {\n"
            + "    define the position<run>.\n"
            + "    it happens when {\n"
            + "        the position<run> has a dimension point.\n"
            + "    } and it does {\n"
            + "        move the dimension point in position<src> to.\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.token == " "
    assert exc_info.value.token.type == "SPACE"
    assert exc_info.value.line == 6
    assert exc_info.value.column == 50


def test_move_dimension_point_chain_separator_after_source_then_terminator(
    parse: Parse,
) -> None:
    with pytest.raises(parser_exceptions.ExpectedNameType) as exc_info:
        parse(
            "define the potential action<mv:define-lang.org:parser:/path> {\n"
            + "    define the position<run>.\n"
            + "    it happens when {\n"
            + "        the position<run> has a dimension point.\n"
            + "    } and it does {\n"
            + "        move the dimension point in position<foo>::.\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.token == "."
    assert exc_info.value.token.type == "DOT"
    assert exc_info.value.line == 6
    assert exc_info.value.column == 52


def test_move_dimension_point_chain_separator_after_source_then_newline(
    parse: Parse,
) -> None:
    with pytest.raises(parser_exceptions.ExpectedNameType) as exc_info:
        parse(
            "define the potential action<mv:define-lang.org:parser:/path> {\n"
            + "    define the position<run>.\n"
            + "    it happens when {\n"
            + "        the position<run> has a dimension point.\n"
            + "    } and it does {\n"
            + "        move the dimension point in position<foo>::\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.token == "\n"
    assert exc_info.value.token.type == "NEWLINE"
    assert exc_info.value.line == 6
    assert exc_info.value.column == 52


def test_move_dimension_point_chain_separator_after_destination_then_terminator(
    parse: Parse,
) -> None:
    with pytest.raises(parser_exceptions.ExpectedNameType) as exc_info:
        parse(
            "define the potential action<mv:define-lang.org:parser:/path> {\n"
            + "    define the position<run>.\n"
            + "    it happens when {\n"
            + "        the position<run> has a dimension point.\n"
            + "    } and it does {\n"
            + "        move the dimension point in position<src> to position<dest>::.\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.token == "."
    assert exc_info.value.token.type == "DOT"
    assert exc_info.value.line == 6
    assert exc_info.value.column == 70


def test_move_dimension_point_chain_separator_after_destination_then_newline(
    parse: Parse,
) -> None:
    with pytest.raises(parser_exceptions.ExpectedNameType) as exc_info:
        parse(
            "define the potential action<mv:define-lang.org:parser:/path> {\n"
            + "    define the position<run>.\n"
            + "    it happens when {\n"
            + "        the position<run> has a dimension point.\n"
            + "    } and it does {\n"
            + "        move the dimension point in position<src> to position<dest>::\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.token == "\n"
    assert exc_info.value.token.type == "NEWLINE"
    assert exc_info.value.line == 6
    assert exc_info.value.column == 70


def test_move_dimension_point_single_colon_after_source(
    parse: Parse,
) -> None:
    with pytest.raises(parser_exceptions.InvalidMoveStatementSyntax) as exc_info:
        parse(
            "define the potential action<mv:define-lang.org:parser:/path> {\n"
            + "    define the position<run>.\n"
            + "    it happens when {\n"
            + "        the position<run> has a dimension point.\n"
            + "    } and it does {\n"
            + "        move the dimension point in position<foo>:\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.token == ":"
    assert exc_info.value.token.type == "INVALID"
    assert exc_info.value.line == 6
    assert exc_info.value.column == 50


def test_move_dimension_point_single_colon_after_destination(
    parse: Parse,
) -> None:
    with pytest.raises(
        parser_exceptions.ExpectedChainSeparatorOrTerminator
    ) as exc_info:
        parse(
            "define the potential action<mv:define-lang.org:parser:/path> {\n"
            + "    define the position<run>.\n"
            + "    it happens when {\n"
            + "        the position<run> has a dimension point.\n"
            + "    } and it does {\n"
            + "        move the dimension point in position<src> to position<dest>:\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.token == ":"
    assert exc_info.value.token.type == "INVALID"
    assert exc_info.value.line == 6
    assert exc_info.value.column == 68


def test_move_dimension_point_no_space_before_to(
    parse: Parse,
) -> None:
    with pytest.raises(parser_exceptions.InvalidMoveStatementSyntax) as exc_info:
        parse(
            "define the potential action<mv:define-lang.org:parser:/path> {\n"
            + "    define the position<run>.\n"
            + "    it happens when {\n"
            + "        the position<run> has a dimension point.\n"
            + "    } and it does {\n"
            + "        move the dimension point in position<src>to position<dest>.\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.token == "to"
    assert exc_info.value.token.type == "LOCAL_NAME_CONTENT"
    assert exc_info.value.line == 6
    assert exc_info.value.column == 50


def test_move_dimension_point_no_space_after_to(
    parse: Parse,
) -> None:
    with pytest.raises(parser_exceptions.InvalidMoveStatementSyntax) as exc_info:
        parse(
            "define the potential action<mv:define-lang.org:parser:/path> {\n"
            + "    define the position<run>.\n"
            + "    it happens when {\n"
            + "        the position<run> has a dimension point.\n"
            + "    } and it does {\n"
            + "        move the dimension point in position<src> toposition<dest>.\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.token == " "
    assert exc_info.value.token.type == "SPACE"
    assert exc_info.value.line == 6
    assert exc_info.value.column == 50


def test_move_dimension_point_missing_terminator_after_destination(
    parse: Parse,
) -> None:
    with pytest.raises(
        parser_exceptions.ExpectedChainSeparatorOrTerminator
    ) as exc_info:
        parse(
            "define the potential action<mv:define-lang.org:parser:/path> {\n"
            + "    define the position<run>.\n"
            + "    it happens when {\n"
            + "        the position<run> has a dimension point.\n"
            + "    } and it does {\n"
            + "        move the dimension point in position<src> to position<dest>\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.token == "\n"
    assert exc_info.value.token.type == "NEWLINE"
    assert exc_info.value.line == 6
    assert exc_info.value.column == 68


def test_move_dimension_point_missing_close_angle_bracket_before_to(
    parse: Parse,
) -> None:
    with pytest.raises(parser_exceptions.MissingCloseAngleBracket) as exc_info:
        parse(
            "define the potential action<mv:define-lang.org:parser:/path> {\n"
            + "    define the position<run>.\n"
            + "    it happens when {\n"
            + "        the position<run> has a dimension point.\n"
            + "    } and it does {\n"
            + "        move the dimension point in position<from_pos to position<to_pos>.\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.token == " to "
    assert exc_info.value.token.type == "TO"
    assert exc_info.value.line == 6
    assert exc_info.value.column == 54


def test_move_keyword_then_newline(
    parse: Parse,
) -> None:
    with pytest.raises(parser_exceptions.InvalidActionStatementsBlock) as exc_info:
        parse(
            "define the potential action<mv:define-lang.org:parser:/path> {\n"
            + "    define the position<run>.\n"
            + "    it happens when {\n"
            + "        the position<run> has a dimension point.\n"
            + "    } and it does {\n"
            + "        move\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.token == "move"
    assert exc_info.value.token.type == "LOCAL_NAME_CONTENT"
    assert exc_info.value.line == 6
    assert exc_info.value.column == 9


def test_move_dimension_point_in_space_dot(
    parse: Parse,
) -> None:
    with pytest.raises(parser_exceptions.ExpectedNameType) as exc_info:
        parse(
            "define the potential action<mv:define-lang.org:parser:/path> {\n"
            + "    define the position<run>.\n"
            + "    it happens when {\n"
            + "        the position<run> has a dimension point.\n"
            + "    } and it does {\n"
            + "        move the dimension point in .\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.token == "."
    assert exc_info.value.token.type == "DOT"
    assert exc_info.value.line == 6
    assert exc_info.value.column == 37
