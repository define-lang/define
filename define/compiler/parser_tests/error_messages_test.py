# pyright: reportUnusedCallResult=false
"""Parser error message tests.

Follow parser test authoring rules in parser_tests/AGENTS.md.
"""

import pathlib

from define.compiler import parser, parser_exceptions


def test_error_message_without_path(p: parser.Parser) -> None:
    result = p.parse("\ufeffdefine the potential position<standard:/path>.\n")
    assert result.diagnostics == []
    assert isinstance(result.exception, parser_exceptions.ByteOrderMarkError)
    assert result.exception.line == 1
    assert result.exception.column == 1
    assert str(result.exception) == (
        "line 1, column 1\n"
        "\\ufeffdefine the potential position<standard:\n"
        "^\n"
        "UTF-8 Byte Order Marks (\\ufeff) are not allowed in Define source code files."
    )


def test_error_message_with_path(p: parser.Parser) -> None:
    result = p.parse(
        "\ufeffdefine the potential position<standard:/path>.\n",
        file_path=pathlib.PurePosixPath("test.def"),
    )
    assert result.diagnostics == []
    assert isinstance(result.exception, parser_exceptions.ByteOrderMarkError)
    assert result.exception.line == 1
    assert result.exception.column == 1
    assert str(result.exception) == (
        'File "test.def", line 1, column 1\n'
        "\\ufeffdefine the potential position<standard:\n"
        "^\n"
        "UTF-8 Byte Order Marks (\\ufeff) are not allowed in Define source code files."
    )


def test_char_error_message(p: parser.Parser) -> None:
    result = p.parse("define the potential position<standard:/path>.\r\n")
    assert result.diagnostics == []
    assert isinstance(result.exception, parser_exceptions.CarriageReturnError)
    assert result.exception.line == 1
    assert result.exception.column == 47
    assert str(result.exception) == (
        "line 1, column 47\n"
        " the potential position<standard:/path>.\\r\n"
        "                                        ^\n"
        "Carriage return character (\\r) is not allowed."
    )


def test_char_error_message_with_path(p: parser.Parser) -> None:
    result = p.parse(
        "define the potential position<standard:/path>.\r\n",
        file_path=pathlib.PurePosixPath("test.def"),
    )
    assert result.diagnostics == []
    assert isinstance(result.exception, parser_exceptions.CarriageReturnError)
    assert result.exception.line == 1
    assert result.exception.column == 47
    assert str(result.exception) == (
        'File "test.def", line 1, column 47\n'
        " the potential position<standard:/path>.\\r\n"
        "                                        ^\n"
        "Carriage return character (\\r) is not allowed."
    )


def test_token_error_message(p: parser.Parser) -> None:
    result = p.parse("define the potential position<standard:/path>\n")
    assert result.diagnostics == []
    assert isinstance(result.exception, parser_exceptions.MissingTerminatorOrBrace)
    assert result.exception.line == 1
    assert result.exception.column == 46
    assert str(result.exception) == (
        "line 1, column 46\n"
        "e the potential position<standard:/path>\n"
        "                                        ^\n"
        "This statement must end with a '.' or a single space followed by '{'"
    )


def test_error_message_for_indented_code_in_action_block(p: parser.Parser) -> None:
    result = p.parse(
        "define the potential action<mv:define-lang.org:parser:/act> {\n"
        + "    define the position<run>.\n"
        + "    define the position<local_name.\n"
        + "    it happens when {\n"
        + "        the position<run> has a dimension point.\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    )
    assert result.diagnostics == []
    assert isinstance(result.exception, parser_exceptions.MissingCloseAngleBracket)
    assert result.exception.line == 3
    assert result.exception.column == 36
    assert str(result.exception) == (
        "line 3, column 36\n"
        "    define the position<local_name.\n"
        "                                   ^\n"
        "Missing '>' on this name: local_name."
    )
