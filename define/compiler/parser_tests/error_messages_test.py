# pyright: reportUnusedCallResult=false
"""Parser error message tests.

Follow parser test authoring rules in parser_tests/AGENTS.md.
"""

import pytest

from define.compiler import parser, parser_exceptions


def test_error_message_without_path(p: parser.Parser) -> None:
    with pytest.raises(parser_exceptions.ByteOrderMarkError) as exc_info:
        p.parse("\ufeffdefine the potential position<standard:/path>.\n")
    assert str(exc_info.value) == (
        "line 1, column 1\n"
        "\\ufeffdefine the potential position<standard:\n"
        "^\n"
        "UTF-8 Byte Order Marks (\\ufeff) are not allowed in Define source code files."
    )


def test_error_message_with_path(p: parser.Parser) -> None:
    with pytest.raises(parser_exceptions.ByteOrderMarkError) as exc_info:
        p.parse(
            "\ufeffdefine the potential position<standard:/path>.\n",
            file_path="test.def",
        )
    assert str(exc_info.value) == (
        'File "test.def", line 1, column 1\n'
        "\\ufeffdefine the potential position<standard:\n"
        "^\n"
        "UTF-8 Byte Order Marks (\\ufeff) are not allowed in Define source code files."
    )


def test_char_error_message(p: parser.Parser) -> None:
    with pytest.raises(parser_exceptions.CarriageReturnError) as exc_info:
        p.parse("define the potential position<standard:/path>.\r\n")
    assert str(exc_info.value) == (
        "line 1, column 47\n"
        " the potential position<standard:/path>.\\r\n"
        "                                        ^\n"
        "Carriage return character (\\r) is not allowed."
    )


def test_token_error_message(p: parser.Parser) -> None:
    with pytest.raises(parser_exceptions.MissingTerminator) as exc_info:
        p.parse("define the potential position<standard:/path>\n")
    assert str(exc_info.value) == (
        "line 1, column 46\n"
        "e the potential position<standard:/path>\n"
        "                                        ^\n"
        "Statements must end with a '.' or a single space followed by '{'"
    )


def test_error_message_for_indented_code_in_action_block(p: parser.Parser) -> None:
    with pytest.raises(parser_exceptions.MissingCloseAngleBracket) as exc_info:
        p.parse(
            "define the potential action<mv:define-lang.org:parser:/act> {\n"
            + "    define the position<local_name.\n"
            + "    it happens when {\n"
            + "    } and it does {\n"
            + "    }\n"
            + "}\n"
        )
    assert str(exc_info.value) == (
        "line 2, column 36\n"
        "    define the position<local_name.\n"
        "                                   ^\n"
        "Missing '>' on this name: local_name."
    )
