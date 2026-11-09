# pyright: reportUnusedCallResult=false
"""Parser error message tests.

Follow parser test authoring rules in parser_tests/AGENTS.md.

Message format tests exist only for complex diagnostics, such as multi-line
messages or messages with many fields. Behavioral tests cover simple ones.
"""

from __future__ import annotations

import textwrap
from typing import TYPE_CHECKING

from define.compiler.errors import diagnostics, syntax_errors
from source_rendering.python import rendering

if TYPE_CHECKING:
    from define.compiler.parsing.parser_tests.conftest import (
        ParseSyntaxError,
        ParseWithDiagnostics,
    )


def _format(error: syntax_errors.DefineSyntaxError, source: str) -> str:
    return error.format(rendering.SourceMap(in_memory_source=source))


def test_empty_source_error_message(parse_syntax_error: ParseSyntaxError):
    error = parse_syntax_error("")
    assert isinstance(error, syntax_errors.ExpectedGlobalDefinition)
    assert error.location.line == 1
    assert error.location.column == 1
    assert error.location.end_line == 1
    assert error.location.end_column == 1
    assert _format(error, "") == textwrap.dedent("""\
        line 1, column 1

            ^
        Expected a global definition, one of:
            - define the potential position
            - define the potential action

        Or less commonly:
            - define the potential value
            - define the potential literal
            - define the encoding
            - define the operation
            - define the encoding_operation
            - define the logical_operation""")


def test_error_message_without_path(parse_syntax_error: ParseSyntaxError):
    error = parse_syntax_error("\ufeffdefine the potential position<standard:/path>.\n")
    assert isinstance(error, syntax_errors.ByteOrderMarkError)
    assert error.location.line == 1
    assert error.location.column == 1
    assert error.location.end_line == 1
    assert error.location.end_column == 1
    assert (
        _format(error, "\ufeffdefine the potential position<standard:/path>.\n")
        == textwrap.dedent("""\
        line 1, column 1
            \\u{feff}define the potential position<standard:/path>.
            ^^^^^^^^
        UTF-8 Byte Order Marks (\\u{feff}) are not allowed in Define source code files.""")
    )


def test_char_error_message(parse_syntax_error: ParseSyntaxError):
    error = parse_syntax_error("define the potential position<standard:/path>.\r\n")
    assert isinstance(error, syntax_errors.CarriageReturnError)
    assert error.location.line == 1
    assert error.location.column == 47
    assert error.location.end_line == 1
    assert error.location.end_column == 47
    assert _format(
        error, "define the potential position<standard:/path>.\r\n"
    ) == textwrap.dedent("""\
        line 1, column 47
            define the potential position<standard:/path>.\\r
                                                          ^^
        Carriage return character (\\r) is not allowed.""")


def test_token_error_message(parse_syntax_error: ParseSyntaxError):
    error = parse_syntax_error("define the potential position<standard:/path>\n")
    assert isinstance(error, syntax_errors.MissingTerminatorOrBrace)
    assert error.location.line == 1
    assert error.location.column == 46
    assert error.location.end_line == 1
    assert error.location.end_column == 46
    assert _format(
        error, "define the potential position<standard:/path>\n"
    ) == textwrap.dedent("""\
        line 1, column 46
            define the potential position<standard:/path>
                                                         ^
        This statement must end with a '.' or a single space followed by '{'""")


def test_error_message_for_indented_code_in_action_block(
    parse_syntax_error: ParseSyntaxError,
):
    error = parse_syntax_error(
        "define the potential action<mv:define-lang.org:parser:/act> {\n"
        + "    define the position<run>.\n"
        + "    define the position<local_name.\n"
        + "    it happens when {\n"
        + "        the position<run> has a particle.\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    )
    assert isinstance(error, syntax_errors.MissingCloseAngleBracket)
    assert error.location.line == 3
    assert error.location.column == 36
    assert error.location.end_line == 3
    assert error.location.end_column == 36
    assert _format(
        error,
        "define the potential action<mv:define-lang.org:parser:/act> {\n"
        + "    define the position<run>.\n"
        + "    define the position<local_name.\n",
    ) == textwrap.dedent("""\
        line 3, column 36
            define the position<local_name.
                                           ^
        Missing '>' on this name: local_name.""")


def test_invisible_character_error_message(parse_syntax_error: ParseSyntaxError):
    error = parse_syntax_error(
        "define the potential position<mv:define-lang.org:parser:/path>.\u200b\n"
    )
    assert isinstance(error, syntax_errors.InvisibleCharacterError)
    assert error.location.line == 1
    assert error.location.column == 64
    assert error.location.end_line == 1
    assert error.location.end_column == 64
    assert _format(
        error,
        "define the potential position<mv:define-lang.org:parser:/path>.\u200b\n",
    ) == (
        "line 1, column 64\n"
        + "    define the potential position<mv:define-lang.org:parser:/path>.\\u{200b}\n"
        + "                                                                   ^^^^^^^^\n"
        + "Invisible character U+200B ZERO WIDTH SPACE is not allowed here."
    )


def test_control_character_in_comment_diagnostic_message(
    parse_with_diagnostics: ParseWithDiagnostics,
):
    source = (
        "# a\x01b\n"
        + "define the potential position<mv:define-lang.org:parser:/path>.\n"
    )
    result = parse_with_diagnostics(source)
    [diagnostic] = result.diagnostics
    assert isinstance(diagnostic, diagnostics.ControlCharacterInCommentDiagnostic)
    assert diagnostic.format(
        rendering.SourceMap(in_memory_source=source)
    ) == textwrap.dedent("""\
        line 1, column 4
            # a\\u{1}b
               ^^^^^
        comments may not have the control character \\u{1}""")


def test_invisible_character_in_comment_diagnostic_message(
    parse_with_diagnostics: ParseWithDiagnostics,
):
    source = (
        "# a\u200bb\n"
        + "define the potential position<mv:define-lang.org:parser:/path>.\n"
    )
    result = parse_with_diagnostics(source)
    [diagnostic] = result.diagnostics
    assert isinstance(diagnostic, diagnostics.InvisibleCharacterInCommentDiagnostic)
    assert diagnostic.format(
        rendering.SourceMap(in_memory_source=source)
    ) == textwrap.dedent("""\
        line 1, column 4
            # a\\u{200b}b
               ^^^^^^^^
        comments may not have the invisible character U+200B ZERO WIDTH SPACE""")
