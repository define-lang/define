# pyright: reportUnusedCallResult=false
"""Parser error message tests.

Follow parser test authoring rules in parser_tests/AGENTS.md.
"""

import pathlib

import pytest

from define.compiler import parser_exceptions
from define.compiler.parser_tests.conftest import Parse


def test_error_message_without_path(parse: Parse) -> None:
    with pytest.raises(parser_exceptions.ByteOrderMarkError) as exc_info:
        parse("\ufeffdefine the potential position<standard:/path>.\n")
    assert exc_info.value.line == 1
    assert exc_info.value.column == 1
    assert str(exc_info.value) == (
        "line 1, column 1\n"
        "\\ufeffdefine the potential position<standard:\n"
        "^\n"
        "UTF-8 Byte Order Marks (\\ufeff) are not allowed in Define source code files."
    )


def test_error_message_with_path(parse: Parse) -> None:
    with pytest.raises(parser_exceptions.ByteOrderMarkError) as exc_info:
        parse(
            "\ufeffdefine the potential position<standard:/path>.\n",
            file_path=pathlib.PurePosixPath("test.dfn"),
        )
    assert exc_info.value.line == 1
    assert exc_info.value.column == 1
    assert str(exc_info.value) == (
        'File "test.dfn", line 1, column 1\n'
        "\\ufeffdefine the potential position<standard:\n"
        "^\n"
        "UTF-8 Byte Order Marks (\\ufeff) are not allowed in Define source code files."
    )


def test_char_error_message(parse: Parse) -> None:
    with pytest.raises(parser_exceptions.CarriageReturnError) as exc_info:
        parse("define the potential position<standard:/path>.\r\n")
    assert exc_info.value.line == 1
    assert exc_info.value.column == 47
    assert str(exc_info.value) == (
        "line 1, column 47\n"
        " the potential position<standard:/path>.\\r\n"
        "                                        ^\n"
        "Carriage return character (\\r) is not allowed."
    )


def test_char_error_message_with_path(parse: Parse) -> None:
    with pytest.raises(parser_exceptions.CarriageReturnError) as exc_info:
        parse(
            "define the potential position<standard:/path>.\r\n",
            file_path=pathlib.PurePosixPath("test.dfn"),
        )
    assert exc_info.value.line == 1
    assert exc_info.value.column == 47
    assert str(exc_info.value) == (
        'File "test.dfn", line 1, column 47\n'
        " the potential position<standard:/path>.\\r\n"
        "                                        ^\n"
        "Carriage return character (\\r) is not allowed."
    )


def test_token_error_message(parse: Parse) -> None:
    with pytest.raises(parser_exceptions.MissingTerminatorOrBrace) as exc_info:
        parse("define the potential position<standard:/path>\n")
    assert exc_info.value.line == 1
    assert exc_info.value.column == 46
    assert str(exc_info.value) == (
        "line 1, column 46\n"
        "e the potential position<standard:/path>\n"
        "                                        ^\n"
        "This statement must end with a '.' or a single space followed by '{'"
    )


def test_error_message_for_indented_code_in_action_block(parse: Parse) -> None:
    with pytest.raises(parser_exceptions.MissingCloseAngleBracket) as exc_info:
        parse(
            "define the potential action<mv:define-lang.org:parser:/act> {\n"
            + "    define the position<run>.\n"
            + "    define the position<local_name.\n"
            + "    it happens when {\n"
            + "        the position<run> has a dimension point.\n"
            + "    } and it does {\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.line == 3
    assert exc_info.value.column == 36
    assert str(exc_info.value) == (
        "line 3, column 36\n"
        "    define the position<local_name.\n"
        "                                   ^\n"
        "Missing '>' on this name: local_name."
    )
