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
