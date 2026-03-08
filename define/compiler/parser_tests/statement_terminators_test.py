# pyright: reportUnusedCallResult=false
"""Statement terminator parser tests.

Follow parser test authoring rules in parser_tests/AGENTS.md.
"""

from define.compiler import parser, parser_exceptions
from define.compiler.parser_tests.test_helpers import get_tokens_by_type


def test_valid_terminator(p: parser.Parser) -> None:
    result = p.parse(
        "define the potential position<mv:define-lang.org:parser:/path>.\n"
    )
    assert result.diagnostics == []
    assert result.tree is not None
    assert get_tokens_by_type(result.tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/path"
    ]


def test_missing_terminator(p: parser.Parser) -> None:
    result = p.parse("define the potential position<standard:/path>\n")
    assert result.diagnostics == []
    assert isinstance(result.exception, parser_exceptions.MissingTerminatorOrBrace)
    assert str(result.exception.token) == "\n"
    assert result.exception.line == 1
    assert result.exception.column == 46


def test_missing_newline_after_terminator(p: parser.Parser) -> None:
    result = p.parse("define the potential position<standard:/path>.")
    assert result.diagnostics == []
    assert isinstance(result.exception, parser_exceptions.MissingNewlineAtEof)
    assert str(result.exception.token) == ""
    assert result.exception.line == 1
    assert result.exception.column == 46


def test_space_before_terminator(p: parser.Parser) -> None:
    result = p.parse(
        "define the potential position<mv:my.domain.com:my_lib:/some_name .\n"
    )
    assert result.diagnostics == []
    assert isinstance(result.exception, parser_exceptions.MissingCloseAngleBracket)
    assert str(result.exception.token) == "\n"
    assert result.exception.line == 1
    assert result.exception.column == 67
    assert result.exception.name == "mv:my.domain.com:my_lib:/some_name ."


def test_trailing_space_before_newline(p: parser.Parser) -> None:
    result = p.parse("define the potential position<standard:/path>. \n")
    assert result.diagnostics == []
    assert isinstance(result.exception, parser_exceptions.TrailingWhitespaceError)
    assert result.exception.char == " "
    assert result.exception.line == 1
    assert result.exception.column == 47


def test_missing_terminator_after_typed_reference_in_position_constraint(
    p: parser.Parser,
) -> None:
    result = p.parse(
        "define the potential position<my_lib:/hello/hello>.\n"
        + "define the potential position<my_lib:/sub/sub> {\n"
        + "    it may only contain dimension points where {\n"
        + "        it has the action<std:/path/sub>\n"
        + "    }\n"
        + "}\n"
    )
    assert result.diagnostics == []
    assert isinstance(result.exception, parser_exceptions.MissingTerminator)
    assert str(result.exception.token) == "\n"
    assert result.exception.line == 4
    assert result.exception.column == 41
