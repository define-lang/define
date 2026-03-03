# pyright: reportUnusedCallResult=false
"""Extra whitespace parser tests.

Follow parser test authoring rules in parser_tests/AGENTS.md.
"""

from define.compiler import parser, parser_exceptions


def test_file_all_spaces(p: parser.Parser) -> None:
    result = p.parse("   ")
    assert isinstance(result.exception, parser_exceptions.TrailingWhitespaceError)
    assert str(result.exception.char) == "   "
    assert result.exception.column == 1


def test_file_spaces_and_newlines_only(p: parser.Parser) -> None:
    result = p.parse(" \n  \n ")
    assert isinstance(result.exception, parser_exceptions.TrailingWhitespaceError)
    assert str(result.exception.char) == " "
    assert result.exception.column == 1


def test_extra_space_after_define_in_position_definition(p: parser.Parser) -> None:
    result = p.parse(
        "define  the potential position<mv:define-lang.org:parser:/path>.\n"
    )
    assert isinstance(result.exception, parser_exceptions.ExtraWhitespace)
    assert result.exception.token.startswith("define  the potential position<")
    assert result.exception.column == 1


def test_extra_space_after_the_in_position_definition(p: parser.Parser) -> None:
    result = p.parse(
        "define the  potential position<mv:define-lang.org:parser:/path>.\n"
    )
    assert isinstance(result.exception, parser_exceptions.ExtraWhitespace)
    assert result.exception.token.startswith("define the  potential position<")
    assert result.exception.column == 1


def test_extra_space_after_potential_in_position_definition(
    p: parser.Parser,
) -> None:
    result = p.parse(
        "define the potential  position<mv:define-lang.org:parser:/path>.\n"
    )
    assert isinstance(result.exception, parser_exceptions.ExtraWhitespace)
    assert result.exception.token.startswith("define the potential  position<")
    assert result.exception.column == 1


def test_extra_space_after_potential_in_action_definition(p: parser.Parser) -> None:
    result = p.parse("define the potential  action<mv:define-lang.org:parser:/path>.\n")
    assert isinstance(result.exception, parser_exceptions.ExtraWhitespace)
    assert result.exception.token.startswith("define the potential  action<")
    assert result.exception.column == 1


def test_extra_space_in_local_position_definition_in_action_block(
    p: parser.Parser,
) -> None:
    result = p.parse(
        "define the potential action<mv:define-lang.org:parser:/path> {\n"
        + "define the position<run>.\n"
        + "define  the position<my_pos>.\n"
        + "it happens when {\n"
        + "the position<run> has a dimension point.\n"
        + "} and it does {\n"
        + "}\n"
        + "}\n"
    )
    assert isinstance(result.exception, parser_exceptions.ExtraWhitespace)
    assert result.exception.token.startswith("define  the position<")
    assert result.exception.line == 3
    assert result.exception.column == 1


def test_extra_space_in_trigger_clause_in_action_block(p: parser.Parser) -> None:
    result = p.parse(
        "define the potential action<mv:define-lang.org:parser:/path> {\n"
        + "define the position<run>.\n"
        + "it happens  when {\n"
        + "the position<run> has a dimension point.\n"
        + "} and it does {\n"
        + "}\n"
        + "}\n"
    )
    assert isinstance(result.exception, parser_exceptions.ExtraWhitespace)
    assert result.exception.token.startswith("it happens  when {")
    assert result.exception.line == 3
    assert result.exception.column == 1


def test_extra_space_in_and_it_does_clause_in_action_block(p: parser.Parser) -> None:
    result = p.parse(
        "define the potential action<mv:define-lang.org:parser:/path> {\n"
        + "define the position<run>.\n"
        + "it happens when {\n"
        + "the position<run> has a dimension point.\n"
        + "}  and it does {\n"
        + "}\n"
        + "}\n"
    )
    assert isinstance(result.exception, parser_exceptions.ExtraWhitespace)
    assert result.exception.token.startswith("  and it does {")
    assert result.exception.line == 5
    assert result.exception.column == 2


def test_extra_space_after_and_it_does_before_open_brace(p: parser.Parser) -> None:
    result = p.parse(
        "define the potential action<mv:define-lang.org:parser:/path> {\n"
        + "define the position<run>.\n"
        + "it happens when {\n"
        + "the position<run> has a dimension point.\n"
        + "} and it does  {\n"
        + "}\n"
        + "}\n"
    )
    assert isinstance(result.exception, parser_exceptions.MissingOpenBrace)
    assert str(result.exception.token) == "  {"
    assert result.exception.line == 5
    assert result.exception.column == 14


def test_extra_space_before_local_name_in_position_requirement_statement(
    p: parser.Parser,
) -> None:
    result = p.parse(
        "define the potential position<mv:define-lang.org:parser:/path> {\n"
        + "it may only contain dimension points where {\n"
        + "it has the position  </child>.\n"
        + "}\n"
        + "}\n"
    )
    assert isinstance(result.exception, parser_exceptions.MissingOpenAngleBracket)
    assert result.exception.token.startswith("  </child")
    assert result.exception.line == 3
    assert result.exception.column == 20
