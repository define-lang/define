# pyright: reportUnusedCallResult=false
"""Block parsing tests.

Follow parser test authoring rules in parser_tests/AGENTS.md.
"""

import pytest

from define.compiler import parser_exceptions
from define.compiler.parser_tests.conftest import Parse
from define.compiler.parser_tests.test_helpers import get_tokens_by_type


def test_empty_block_on_position(parse: Parse) -> None:
    with pytest.raises(
        parser_exceptions.MissingPotentialPositionDefinitionContent
    ) as exc_info:
        parse("define the potential position<standard:/path> {\n}\n")
    assert str(exc_info.value.token) == "}"
    assert exc_info.value.line == 2
    assert exc_info.value.column == 1


def test_empty_block_on_action(parse: Parse) -> None:
    with pytest.raises(parser_exceptions.MissingActionDefinitionSyntax) as exc_info:
        parse("define the potential action<standard:/path> {\n}\n")
    assert str(exc_info.value.token) == "}"
    assert exc_info.value.line == 2
    assert exc_info.value.column == 1


def test_block_with_blank_lines(parse: Parse) -> None:
    tree = parse(
        "define the potential position<standard:/path> {\n"
        + "\n"
        + "    it may only contain dimension points where {\n"
        + "        it has the position</child>.\n"
        + "    }\n"
        + "\n"
        + "}\n"
    )
    assert get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == [
        "standard:/path",
        "/child",
    ]


def test_blank_line_between_constraint_requirement_and_close(parse: Parse) -> None:
    tree = parse(
        "define the potential position<mv:define-lang.org:parser:/path> {\n"
        + "    it may only contain dimension points where {\n"
        + "        it has the position</child>.\n"
        + "\n"
        + "    }\n"
        + "}\n"
    )
    assert get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/path",
        "/child",
    ]


def test_comment_line_between_constraint_requirement_and_close(
    parse: Parse,
) -> None:
    tree = parse(
        "define the potential position<mv:define-lang.org:parser:/path> {\n"
        + "    it may only contain dimension points where {\n"
        + "        it has the position</child>.\n"
        + "        # trailing note\n"
        + "    }\n"
        + "}\n"
    )
    assert get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/path",
        "/child",
    ]


def test_block_with_comment_inside(parse: Parse) -> None:
    tree = parse(
        "define the potential position<standard:/path> {\n"
        + "    # comment\n"
        + "    it may only contain dimension points where {\n"
        + "        it has the position</child>.\n"
        + "    }\n"
        + "}\n"
    )
    assert get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == [
        "standard:/path",
        "/child",
    ]


def test_block_with_comment_after_open(parse: Parse) -> None:
    tree = parse(
        "define the potential position<standard:/path> { # comment\n"
        + "    it may only contain dimension points where {\n"
        + "        it has the position</child>.\n"
        + "    }\n"
        + "}\n"
    )
    assert get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == [
        "standard:/path",
        "/child",
    ]


def test_block_with_comment_after_close(parse: Parse) -> None:
    tree = parse(
        "define the potential position<standard:/path> {\n"
        + "    it may only contain dimension points where {\n"
        + "        it has the position</child>.\n"
        + "    }\n"
        + "} # comment\n"
    )
    assert get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == [
        "standard:/path",
        "/child",
    ]


def test_block_with_full_fqun(parse: Parse) -> None:
    tree = parse(
        "define the potential position<my_mv:example.com:my_lib:/some/path> {\n"
        + "    it may only contain dimension points where {\n"
        + "        it has the action</some/action>.\n"
        + "    }\n"
        + "}\n"
    )
    assert get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == [
        "my_mv:example.com:my_lib:/some/path",
        "/some/action",
    ]


def test_multiple_definitions_with_blocks(parse: Parse) -> None:
    tree = parse(
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
    assert get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == [
        "standard:/first",
        "/first_child",
        "standard:/second",
        "/second_child",
    ]


def test_mixed_block_and_terminator(parse: Parse) -> None:
    tree = parse(
        "define the potential position<standard:/first>.\n"
        + "define the potential position<standard:/second> {\n"
        + "    it may only contain dimension points where {\n"
        + "        it has the action</do_work>.\n"
        + "    }\n"
        + "}\n"
    )
    assert get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == [
        "standard:/first",
        "standard:/second",
        "/do_work",
    ]


def test_missing_block_close(parse: Parse) -> None:
    with pytest.raises(
        parser_exceptions.InvalidPotentialPositionDefinitionBlock
    ) as exc_info:
        parse("define the potential position<standard:/path> {\n")
    assert exc_info.value.line == 1
    assert exc_info.value.column == 48


def test_missing_newline_after_block_open(parse: Parse) -> None:
    with pytest.raises(parser_exceptions.EmptyBlock) as exc_info:
        parse("define the potential position<standard:/path> {}\n")
    assert exc_info.value.line == 1
    assert exc_info.value.column == 48


def test_no_space_before_brace(parse: Parse) -> None:
    with pytest.raises(parser_exceptions.MissingWhitespaceBeforeBrace) as exc_info:
        parse("define the potential position<standard:/path>{\n")
    assert str(exc_info.value.token) == "{"
    assert exc_info.value.line == 1
    assert exc_info.value.column == 46


def test_missing_terminator_still_works(parse: Parse) -> None:
    with pytest.raises(parser_exceptions.MissingTerminatorOrBrace) as exc_info:
        parse("define the potential position<standard:/path>\n")
    assert exc_info.value.line == 1
    assert exc_info.value.column == 46


def test_missing_outer_block_close_with_inner_block_message(parse: Parse) -> None:
    with pytest.raises(parser_exceptions.MissingCloseBrace) as exc_info:
        parse(
            "define the potential action<standard:/path> {\n"
            + "    define the position<run>.\n"
            + "    it happens when {\n"
            + "        the position<run> has a dimension point.\n"
            + "    } and it does {\n"
            + "    }\n"
        )
    assert exc_info.value.line == 6
    assert exc_info.value.column == 6
    assert str(exc_info.value) == (
        "line 6, column 6\n    }\n     ^\nMissing a closing '}' somewhere in this block."
    )


def test_position_constraint_invalid_type_keyword(parse: Parse) -> None:
    with pytest.raises(parser_exceptions.ExpectedNameType) as exc_info:
        parse(
            "define the potential position<my_lib:/path> {\n"
            + "    it may only contain dimension points where {\n"
            + "        it has the osition<my_lib:/path>.\n"
            + "    }\n"
            + "}\n"
            + "define the potential position<my_lib:/path>.\n"
        )
    assert str(exc_info.value.token) == "osition<my_lib:/path"
    assert exc_info.value.line == 3
    assert exc_info.value.column == 20
