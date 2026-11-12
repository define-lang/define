"""Parsing a global name that is not in Define source."""

from __future__ import annotations

from crates.source_rendering.python import rendering
from define.compiler import ast
from define.compiler.errors import syntax_errors
from define.compiler.parsing import parser


def _location(column: int, end_column: int) -> rendering.SourceLocation:
    return rendering.SourceLocation(
        line=3, column=column, end_line=3, end_column=end_column, file_path="c.defcl"
    )


def test_full_name_is_located_where_it_starts():
    name = parser.parse_global_name(b"mv:define-lang.org:parser:/a/b", "c.defcl", 3, 7)
    assert isinstance(name, ast.ReferenceGlobalNameContent)
    assert name.location == _location(7, 36)
    assert name.fqun is not None
    assert name.fqun.canonical == "mv:define-lang.org:parser"
    assert name.fqun.location == _location(7, 31)
    assert name.fqun.multiverse is not None
    assert name.fqun.multiverse.name == "mv"
    assert name.fqun.authority is not None
    assert name.fqun.authority.name == "define-lang.org"
    assert name.fqun.universe.name == "parser"
    assert name.path.name == "/a/b"
    assert name.path.location == _location(33, 36)


def test_short_name():
    name = parser.parse_global_name(b"/a/b", "c.defcl", 3, 7)
    assert isinstance(name, ast.ReferenceGlobalNameContent)
    assert name.location == _location(7, 10)
    assert name.fqun is None
    assert name.path.name == "/a/b"


def test_empty_name():
    assert parser.parse_global_name(b"", "c.defcl", 3, 7) == syntax_errors.EmptyName(
        location=_location(7, 7)
    )


def test_control_character():
    assert parser.parse_global_name(
        b"/a\x01b", "c.defcl", 3, 7
    ) == syntax_errors.ControlCharacterError(
        location=_location(9, 9), escaped_char="\\u{1}"
    )


def test_text_after_the_name():
    assert parser.parse_global_name(
        b"/a>b", "c.defcl", 3, 7
    ) == syntax_errors.InvalidGlobalName(location=_location(7, 8))


def test_control_character_in_text_that_is_not_a_global_name():
    assert parser.parse_global_name(
        b"a\x01", "c.defcl", 3, 7
    ) == syntax_errors.ControlCharacterError(
        location=_location(8, 8), escaped_char="\\u{1}"
    )
