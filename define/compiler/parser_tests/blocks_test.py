# pyright: reportUnusedCallResult=false
"""Block parsing tests.

Follow parser test authoring rules in parser_tests/AGENTS.md.
"""

import pytest

from define.compiler import parser, parser_exceptions
from define.compiler.parser_tests.test_helpers import get_tokens_by_type


def test_empty_block_on_position(p: parser.Parser) -> None:
    with pytest.raises(parser_exceptions.MissingPositionDefinitionContent) as exc_info:
        p.parse("define the potential position<standard:/path> {\n}\n")
    assert str(exc_info.value.token) == "}"
    assert exc_info.value.line == 2
    assert exc_info.value.column == 1


def test_empty_block_on_action(p: parser.Parser) -> None:
    with pytest.raises(parser_exceptions.MissingActionDefinitionSyntax) as exc_info:
        p.parse("define the potential action<standard:/path> {\n}\n")
    assert str(exc_info.value.token) == "}"
    assert exc_info.value.line == 2
    assert exc_info.value.column == 1


def test_block_with_blank_lines(p: parser.Parser) -> None:
    tree = p.parse(
        "define the potential position<standard:/path> {\n"
        + "\n"
        + "it may only contain dimension points where {\n"
        + "it has the position</child>.\n"
        + "}\n"
        + "\n"
        + "}\n"
    )
    assert get_tokens_by_type(tree, "NAME_CONTENT") == ["standard:/path", "/child"]


def test_block_with_comment_inside(p: parser.Parser) -> None:
    tree = p.parse(
        "define the potential position<standard:/path> {\n"
        + "# comment\n"
        + "it may only contain dimension points where {\n"
        + "it has the position</child>.\n"
        + "}\n"
        + "}\n"
    )
    assert get_tokens_by_type(tree, "NAME_CONTENT") == ["standard:/path", "/child"]


def test_block_with_comment_after_open(p: parser.Parser) -> None:
    tree = p.parse(
        "define the potential position<standard:/path> { # comment\n"
        + "it may only contain dimension points where {\n"
        + "it has the position</child>.\n"
        + "}\n"
        + "}\n"
    )
    assert get_tokens_by_type(tree, "NAME_CONTENT") == ["standard:/path", "/child"]


def test_block_with_comment_after_close(p: parser.Parser) -> None:
    tree = p.parse(
        "define the potential position<standard:/path> {\n"
        + "it may only contain dimension points where {\n"
        + "it has the position</child>.\n"
        + "}\n"
        + "} # comment\n"
    )
    assert get_tokens_by_type(tree, "NAME_CONTENT") == ["standard:/path", "/child"]


def test_block_with_full_fqun(p: parser.Parser) -> None:
    tree = p.parse(
        "define the potential position<my_mv:example.com:my_lib:/some/path> {\n"
        + "it may only contain dimension points where {\n"
        + "it has the action</some/action>.\n"
        + "}\n"
        + "}\n"
    )
    assert get_tokens_by_type(tree, "NAME_CONTENT") == [
        "my_mv:example.com:my_lib:/some/path",
        "/some/action",
    ]


def test_multiple_definitions_with_blocks(p: parser.Parser) -> None:
    tree = p.parse(
        "define the potential position<standard:/first> {\n"
        + "it may only contain dimension points where {\n"
        + "it has the position</first_child>.\n"
        + "}\n"
        + "}\n"
        + "define the potential position<standard:/second> {\n"
        + "it may only contain dimension points where {\n"
        + "it has the position</second_child>.\n"
        + "}\n"
        + "}\n"
    )
    assert get_tokens_by_type(tree, "NAME_CONTENT") == [
        "standard:/first",
        "/first_child",
        "standard:/second",
        "/second_child",
    ]


def test_mixed_block_and_terminator(p: parser.Parser) -> None:
    tree = p.parse(
        "define the potential position<standard:/first>.\n"
        + "define the potential position<standard:/second> {\n"
        + "it may only contain dimension points where {\n"
        + "it has the action</do_work>.\n"
        + "}\n"
        + "}\n"
    )
    assert get_tokens_by_type(tree, "NAME_CONTENT") == [
        "standard:/first",
        "standard:/second",
        "/do_work",
    ]


def test_missing_block_close(p: parser.Parser) -> None:
    with pytest.raises(parser_exceptions.InvalidPositionDefinitionBlock) as exc_info:
        p.parse("define the potential position<standard:/path> {\n")
    assert exc_info.value.line == 1
    assert exc_info.value.column == 48


def test_missing_newline_after_block_open(p: parser.Parser) -> None:
    with pytest.raises(parser_exceptions.EmptyBlock) as exc_info:
        p.parse("define the potential position<standard:/path> {}\n")
    assert exc_info.value.line == 1
    assert exc_info.value.column == 48


def test_no_space_before_brace(p: parser.Parser) -> None:
    with pytest.raises(parser_exceptions.MissingWhitespaceBeforeBrace) as exc_info:
        p.parse("define the potential position<standard:/path>{\n")
    assert str(exc_info.value.token) == "{"


def test_missing_terminator_still_works(p: parser.Parser) -> None:
    with pytest.raises(parser_exceptions.MissingTerminator) as exc_info:
        p.parse("define the potential position<standard:/path>\n")
    assert exc_info.value.line == 1
    assert exc_info.value.column == 46


def test_missing_outer_block_close_with_inner_block_message(p: parser.Parser) -> None:
    with pytest.raises(parser_exceptions.MissingCloseBrace) as exc_info:
        p.parse(
            "define the potential action<standard:/path> {\n"
            + "it happens when {\n"
            + "} and it does {\n"
            + "}\n"
        )
    assert str(exc_info.value) == (
        "line 4, column 2\n}\n ^\nMissing a closing '}' somewhere in this block."
    )
