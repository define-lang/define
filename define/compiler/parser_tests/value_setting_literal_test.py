# pyright: reportUnusedCallResult=false
"""Literal source parser tests for Value Setting Statements."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from define.compiler import parser_exceptions
from define.compiler.parser_tests.test_helpers import get_tokens_by_type

if TYPE_CHECKING:
    from define.compiler.parser_tests.conftest import Parse


_ACTION_PREFIX = (
    "define the potential action<mv:define-lang.org:parser:/set_value> {\n"
    + "    it happens when {\n"
    + "        this particle is created.\n"
    + "    } and it does {\n"
)


def test_literal_source(parse: Parse):
    tree = parse(
        _ACTION_PREFIX
        + '        set the value of position<dest> to literal</decimal>"123".\n'
        + "    }\n}\n"
    )
    assert get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/set_value",
        "/decimal",
    ]
    assert get_tokens_by_type(tree, "LITERAL_CONTENT") == ["123"]


def test_literal_full_global_name(parse: Parse):
    tree = parse(
        _ACTION_PREFIX
        + '        set the value of position<dest>::position<child> to literal<mv:define-lang.org:parser:/text>"hello".\n'
        + "    }\n}\n"
    )
    assert get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/set_value",
        "mv:define-lang.org:parser:/text",
    ]
    assert get_tokens_by_type(tree, "LITERAL_CONTENT") == ["hello"]


def test_literal_empty_content(parse: Parse):
    tree = parse(
        _ACTION_PREFIX
        + '        set the value of position<dest> to literal</text>"".\n'
        + "    }\n}\n"
    )
    assert get_tokens_by_type(tree, "LITERAL_CONTENT") == []


def test_literal_spaces_comments_unicode_and_escapes(parse: Parse):
    tree = parse(
        _ACTION_PREFIX
        + '        set the value of position<dest> to literal</text>" # Hello 世界 < {} . > : \\" \\\\ \\n ". # comment\n'
        + "    }\n}\n"
    )
    assert get_tokens_by_type(tree, "LITERAL_CONTENT") == [
        ' # Hello 世界 < {} . > : \\" \\\\ \\n '
    ]


def test_literal_starts_with_comment_character(parse: Parse):
    tree = parse(
        _ACTION_PREFIX
        + '        set the value of position<dest> to literal</text>"#content". # comment\n'
        + "    }\n}\n"
    )
    assert get_tokens_by_type(tree, "LITERAL_CONTENT") == ["#content"]


def test_literal_brace_before_comment_character(parse: Parse):
    tree = parse(
        _ACTION_PREFIX
        + '        set the value of position<dest> to literal</text>" {#content".\n'
        + '        set the value of position<dest> to literal</text>"next".\n'
        + "    }\n}\n"
    )
    assert get_tokens_by_type(tree, "LITERAL_CONTENT") == [" {#content", "next"]


def test_literal_raw_escapes_are_preserved(parse: Parse):
    tree = parse(
        _ACTION_PREFIX
        + '        set the value of position<dest> to literal</text>"bad\\t".\n'
        + "    }\n}\n"
    )
    assert get_tokens_by_type(tree, "LITERAL_CONTENT") == ["bad\\t"]


def test_literal_newline(parse: Parse):
    with pytest.raises(parser_exceptions.InvalidLiteralSyntax) as error:
        parse(
            _ACTION_PREFIX
            + '        set the value of position<dest> to literal</text>"a\nb".\n'
            + "    }\n}\n"
        )
    assert error.value.line == 5
    assert error.value.column == 60
    assert error.value.token == "\n"


def test_literal_target_is_invalid(parse: Parse):
    with pytest.raises(parser_exceptions.ExpectedPositionOrAction) as error:
        parse(
            _ACTION_PREFIX
            + '        set the value of literal</text>"a" to position<dest>.\n'
            + "    }\n}\n"
        )
    assert error.value.line == 5
    assert error.value.column == 26
    assert error.value.token == "literal"


def test_literal_missing_global_name(parse: Parse):
    with pytest.raises(parser_exceptions.InvalidGlobalName) as error:
        parse(
            _ACTION_PREFIX
            + '        set the value of position<dest> to literal<text>"abc".\n'
            + "    }\n}\n"
        )
    assert error.value.line == 5
    assert error.value.column == 52
    assert error.value.token == "text"


def test_literal_empty_name(parse: Parse):
    with pytest.raises(parser_exceptions.EmptyName) as error:
        parse(
            _ACTION_PREFIX
            + '        set the value of position<dest> to literal<>"abc".\n'
            + "    }\n}\n"
        )
    assert error.value.line == 5
    assert error.value.column == 52
    assert error.value.token == ">"


def test_literal_missing_open_angle_bracket(parse: Parse):
    with pytest.raises(parser_exceptions.MissingOpenAngleBracket) as error:
        parse(
            _ACTION_PREFIX
            + '        set the value of position<dest> to literal/text>"abc".\n'
            + "    }\n}\n"
        )
    assert error.value.line == 5
    assert error.value.column == 51
    assert error.value.token == "/text"


def test_literal_missing_close_angle_bracket(parse: Parse):
    with pytest.raises(parser_exceptions.MissingCloseAngleBracket) as error:
        parse(
            _ACTION_PREFIX
            + '        set the value of position<dest> to literal</text"abc".\n'
            + "    }\n}\n"
        )
    assert error.value.line == 5
    assert error.value.column == 63
    assert error.value.token == "\n"
    assert error.value.name == '/text"abc".'


def test_literal_missing_open_quote(parse: Parse):
    with pytest.raises(parser_exceptions.InvalidLiteralSyntax) as error:
        parse(
            _ACTION_PREFIX
            + "        set the value of position<dest> to literal</text>.\n"
            + "    }\n}\n"
        )
    assert error.value.line == 5
    assert error.value.column == 58
    assert error.value.token == "."


def test_literal_unquoted_content(parse: Parse):
    with pytest.raises(parser_exceptions.InvalidLiteralSyntax) as error:
        parse(
            _ACTION_PREFIX
            + "        set the value of position<dest> to literal</foo>5.\n"
            + "    }\n}\n"
        )
    assert error.value.line == 5
    assert error.value.column == 57
    assert error.value.token == "5."


def test_literal_missing_close_quote(parse: Parse):
    with pytest.raises(parser_exceptions.InvalidLiteralSyntax) as error:
        parse(
            _ACTION_PREFIX
            + '        set the value of position<dest> to literal</text>"abc.\n'
            + "    }\n}\n"
        )
    assert error.value.line == 5
    assert error.value.column == 63
    assert error.value.token == "\n"


def test_literal_content_starting_with_slash(parse: Parse):
    tree = parse(
        _ACTION_PREFIX
        + '        set the value of position<dest> to literal</text>"/0".\n'
        + "    }\n}\n"
    )
    assert get_tokens_by_type(tree, "LITERAL_CONTENT") == ["/0"]


def test_literal_cannot_be_child_of_position(parse: Parse):
    with pytest.raises(parser_exceptions.ExpectedPositionOrAction) as error:
        parse(
            _ACTION_PREFIX
            + '        set the value of position<dest> to position<parent>::literal</text>"abc".\n'
            + "    }\n}\n"
        )
    assert error.value.line == 5
    assert error.value.column == 62
    assert error.value.token == "literal"


def test_literal_cannot_start_position_reference(parse: Parse):
    with pytest.raises(parser_exceptions.MissingTerminator) as error:
        parse(
            _ACTION_PREFIX
            + '        set the value of position<dest> to literal</text>"a"::position<child>.\n'
            + "    }\n}\n"
        )
    assert error.value.line == 5
    assert error.value.column == 61
    assert error.value.token == "::"


def test_literal_missing_terminator(parse: Parse):
    with pytest.raises(parser_exceptions.MissingTerminator) as error:
        parse(
            _ACTION_PREFIX
            + '        set the value of position<dest> to literal</text>"a"\n'
            + "    }\n}\n"
        )
    assert error.value.line == 5
    assert error.value.column == 61
    assert error.value.token == "\n"


def test_literal_old_syntax_is_invalid(parse: Parse):
    with pytest.raises(parser_exceptions.InvalidLiteralSyntax) as error:
        parse(
            _ACTION_PREFIX
            + "        set the value of position<dest> to literal</text:abc>.\n"
            + "    }\n}\n"
        )
    assert error.value.line == 5
    assert error.value.column == 62
    assert error.value.token == "."
