# pyright: reportUnusedCallResult=false
"""Statement terminator parser tests.

Follow parser test authoring rules in parser_tests/AGENTS.md.
"""

import pytest

from define.compiler import parser_exceptions
from define.compiler.parser_tests.conftest import Parse
from define.compiler.parser_tests.test_helpers import get_tokens_by_type


def test_valid_terminator(parse: Parse) -> None:
    tree = parse("define the potential position<mv:define-lang.org:parser:/path>.\n")
    assert get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/path"
    ]


def test_missing_terminator(parse: Parse) -> None:
    with pytest.raises(parser_exceptions.MissingTerminatorOrBrace) as exc_info:
        parse("define the potential position<standard:/path>\n")
    assert str(exc_info.value.token) == "\n"
    assert exc_info.value.line == 1
    assert exc_info.value.column == 46


def test_missing_newline_after_terminator(parse: Parse) -> None:
    with pytest.raises(parser_exceptions.MissingNewlineAtEof) as exc_info:
        parse("define the potential position<standard:/path>.")
    assert str(exc_info.value.token) == ""
    assert exc_info.value.line == 1
    assert exc_info.value.column == 46


def test_space_before_terminator(parse: Parse) -> None:
    with pytest.raises(parser_exceptions.MissingCloseAngleBracket) as exc_info:
        parse("define the potential position<mv:my.domain.com:my_lib:/some_name .\n")
    assert str(exc_info.value.token) == "\n"
    assert exc_info.value.line == 1
    assert exc_info.value.column == 67
    assert exc_info.value.name == "mv:my.domain.com:my_lib:/some_name ."


def test_trailing_space_before_newline(parse: Parse) -> None:
    with pytest.raises(parser_exceptions.TrailingWhitespaceError) as exc_info:
        parse("define the potential position<standard:/path>. \n")
    assert exc_info.value.char == " "
    assert exc_info.value.line == 1
    assert exc_info.value.column == 47


def test_missing_terminator_after_typed_reference_in_position_constraint(
    parse: Parse,
) -> None:
    with pytest.raises(parser_exceptions.MissingTerminator) as exc_info:
        parse(
            "define the potential position<my_lib:/hello/hello>.\n"
            + "define the potential position<my_lib:/sub/sub> {\n"
            + "    it may only contain particles where {\n"
            + "        it has the action<std:/path/sub>\n"
            + "    }\n"
            + "}\n"
        )
    assert str(exc_info.value.token) == "\n"
    assert exc_info.value.line == 4
    assert exc_info.value.column == 41
