# pyright: reportUnusedCallResult=false
"""Block parsing tests.

Follow parser test authoring rules in parser_tests/AGENTS.md.
"""

from define.compiler import parser, parser_exceptions
from define.compiler.parser_tests.test_helpers import get_tokens_by_type


def test_empty_block_on_position(p: parser.Parser) -> None:
    result = p.parse("define the potential position<standard:/path> {\n}\n")
    assert isinstance(
        result.exception, parser_exceptions.MissingPositionDefinitionContent
    )
    assert str(result.exception.token) == "}"
    assert result.exception.line == 2
    assert result.exception.column == 1


def test_empty_block_on_action(p: parser.Parser) -> None:
    result = p.parse("define the potential action<standard:/path> {\n}\n")
    assert result.diagnostics == []
    assert isinstance(result.exception, parser_exceptions.MissingActionDefinitionSyntax)
    assert str(result.exception.token) == "}"
    assert result.exception.line == 2
    assert result.exception.column == 1


def test_block_with_blank_lines(p: parser.Parser) -> None:
    result = p.parse(
        "define the potential position<standard:/path> {\n"
        + "\n"
        + "    it may only contain dimension points where {\n"
        + "        it has the position</child>.\n"
        + "    }\n"
        + "\n"
        + "}\n"
    )
    assert result.diagnostics == []
    assert result.tree is not None
    assert get_tokens_by_type(result.tree, "GLOBAL_NAME_CONTENT") == [
        "standard:/path",
        "/child",
    ]


def test_block_with_comment_inside(p: parser.Parser) -> None:
    result = p.parse(
        "define the potential position<standard:/path> {\n"
        + "    # comment\n"
        + "    it may only contain dimension points where {\n"
        + "        it has the position</child>.\n"
        + "    }\n"
        + "}\n"
    )
    assert result.diagnostics == []
    assert result.tree is not None
    assert get_tokens_by_type(result.tree, "GLOBAL_NAME_CONTENT") == [
        "standard:/path",
        "/child",
    ]


def test_block_with_comment_after_open(p: parser.Parser) -> None:
    result = p.parse(
        "define the potential position<standard:/path> { # comment\n"
        + "    it may only contain dimension points where {\n"
        + "        it has the position</child>.\n"
        + "    }\n"
        + "}\n"
    )
    assert result.diagnostics == []
    assert result.tree is not None
    assert get_tokens_by_type(result.tree, "GLOBAL_NAME_CONTENT") == [
        "standard:/path",
        "/child",
    ]


def test_block_with_comment_after_close(p: parser.Parser) -> None:
    result = p.parse(
        "define the potential position<standard:/path> {\n"
        + "    it may only contain dimension points where {\n"
        + "        it has the position</child>.\n"
        + "    }\n"
        + "} # comment\n"
    )
    assert result.diagnostics == []
    assert result.tree is not None
    assert get_tokens_by_type(result.tree, "GLOBAL_NAME_CONTENT") == [
        "standard:/path",
        "/child",
    ]


def test_block_with_full_fqun(p: parser.Parser) -> None:
    result = p.parse(
        "define the potential position<my_mv:example.com:my_lib:/some/path> {\n"
        + "    it may only contain dimension points where {\n"
        + "        it has the action</some/action>.\n"
        + "    }\n"
        + "}\n"
    )
    assert result.diagnostics == []
    assert result.tree is not None
    assert get_tokens_by_type(result.tree, "GLOBAL_NAME_CONTENT") == [
        "my_mv:example.com:my_lib:/some/path",
        "/some/action",
    ]


def test_multiple_definitions_with_blocks(p: parser.Parser) -> None:
    result = p.parse(
        "define the potential position<standard:/first> {\n"
        + "    it may only contain dimension points where {\n"
        + "        it has the position</first_child>.\n"
        + "    }\n"
        + "}\n"
        + "define the potential position<standard:/second> {\n"
        + "    it may only contain dimension points where {\n"
        + "        it has the position</second_child>.\n"
        + "    }\n"
        + "}\n"
    )
    assert result.diagnostics == []
    assert result.tree is not None
    assert get_tokens_by_type(result.tree, "GLOBAL_NAME_CONTENT") == [
        "standard:/first",
        "/first_child",
        "standard:/second",
        "/second_child",
    ]


def test_mixed_block_and_terminator(p: parser.Parser) -> None:
    result = p.parse(
        "define the potential position<standard:/first>.\n"
        + "define the potential position<standard:/second> {\n"
        + "    it may only contain dimension points where {\n"
        + "        it has the action</do_work>.\n"
        + "    }\n"
        + "}\n"
    )
    assert result.diagnostics == []
    assert result.tree is not None
    assert get_tokens_by_type(result.tree, "GLOBAL_NAME_CONTENT") == [
        "standard:/first",
        "standard:/second",
        "/do_work",
    ]


def test_missing_block_close(p: parser.Parser) -> None:
    result = p.parse("define the potential position<standard:/path> {\n")
    assert isinstance(
        result.exception, parser_exceptions.InvalidPositionDefinitionBlock
    )
    assert result.exception.line == 1
    assert result.exception.column == 48


def test_missing_newline_after_block_open(p: parser.Parser) -> None:
    result = p.parse("define the potential position<standard:/path> {}\n")
    assert result.diagnostics == []
    assert isinstance(result.exception, parser_exceptions.EmptyBlock)
    assert result.exception.line == 1
    assert result.exception.column == 48


def test_no_space_before_brace(p: parser.Parser) -> None:
    result = p.parse("define the potential position<standard:/path>{\n")
    assert result.diagnostics == []
    assert isinstance(result.exception, parser_exceptions.MissingWhitespaceBeforeBrace)
    assert str(result.exception.token) == "{"
    assert result.exception.line == 1
    assert result.exception.column == 46


def test_missing_terminator_still_works(p: parser.Parser) -> None:
    result = p.parse("define the potential position<standard:/path>\n")
    assert result.diagnostics == []
    assert isinstance(result.exception, parser_exceptions.MissingTerminatorOrBrace)
    assert result.exception.line == 1
    assert result.exception.column == 46


def test_missing_outer_block_close_with_inner_block_message(p: parser.Parser) -> None:
    result = p.parse(
        "define the potential action<standard:/path> {\n"
        + "    define the position<run>.\n"
        + "    it happens when {\n"
        + "        the position<run> has a dimension point.\n"
        + "    } and it does {\n"
        + "    }\n"
    )
    assert result.diagnostics == []
    assert isinstance(result.exception, parser_exceptions.MissingCloseBrace)
    assert result.exception.line == 6
    assert result.exception.column == 6
    assert str(result.exception) == (
        "line 6, column 6\n    }\n     ^\nMissing a closing '}' somewhere in this block."
    )


def test_position_constraint_invalid_type_keyword(p: parser.Parser) -> None:
    result = p.parse(
        "define the potential position<my_lib:/path> {\n"
        + "    it may only contain dimension points where {\n"
        + "        it has the osition<my_lib:/path>.\n"
        + "    }\n"
        + "}\n"
        + "define the potential position<my_lib:/path>.\n"
    )
    assert result.diagnostics == []
    assert isinstance(result.exception, parser_exceptions.ExpectedNameType)
    assert str(result.exception.token) == "osition<my_lib:/path"
    assert result.exception.line == 3
    assert result.exception.column == 20
