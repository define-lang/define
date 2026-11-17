"""Parsing a fully qualified universe name that is not in Define source."""

from __future__ import annotations

from crates.source_rendering.python import rendering
from define.compiler import ast
from define.compiler.errors import syntax_errors
from define.compiler.parsing import parser


def _location(column: int, end_column: int) -> rendering.SourceLocation:
    return rendering.SourceLocation(
        line=3, column=column, end_line=3, end_column=end_column, file_path="c.defcl"
    )


def test_three_components():
    fqun = parser.parse_fqun(b"mv:define-lang.org:parser", "c.defcl", 3, 7)
    assert isinstance(fqun, ast.Fqun)
    assert fqun.canonical == "mv:define-lang.org:parser"
    assert fqun.location == _location(7, 31)
    assert fqun.multiverse is not None
    assert fqun.multiverse.name == "mv"
    assert fqun.multiverse.location == _location(7, 8)
    assert fqun.authority is not None
    assert fqun.authority.name == "define-lang.org"
    assert fqun.authority.location == _location(10, 24)
    assert fqun.universe.name == "parser"
    assert fqun.universe.location == _location(26, 31)


def test_two_components():
    fqun = parser.parse_fqun(b"define-lang.org:parser", "c.defcl", 3, 7)
    assert isinstance(fqun, ast.Fqun)
    assert fqun.canonical == "define-lang.org:parser"
    assert fqun.location == _location(7, 28)
    assert fqun.multiverse is None
    assert fqun.authority is not None
    assert fqun.authority.name == "define-lang.org"
    assert fqun.universe.name == "parser"
    assert fqun.universe.location == _location(23, 28)


def test_one_component():
    fqun = parser.parse_fqun(b"standard", "c.defcl", 3, 7)
    assert isinstance(fqun, ast.Fqun)
    assert fqun.canonical == "standard"
    assert fqun.location == _location(7, 14)
    assert fqun.multiverse is None
    assert fqun.authority is None
    assert fqun.universe.name == "standard"


def test_too_many_components():
    assert parser.parse_fqun(
        b"a:b:c:d", "c.defcl", 3, 7
    ) == syntax_errors.FqunHasTooManyComponents(location=_location(7, 13))


def test_authority_with_path_segment():
    fqun = parser.parse_fqun(b"define-lang.org/a:parser", "c.defcl", 3, 7)
    assert isinstance(fqun, ast.Fqun)
    assert fqun.authority is not None
    assert fqun.authority.name == "define-lang.org/a"
    assert fqun.universe.name == "parser"


def test_text_after_the_name():
    assert parser.parse_fqun(
        b"define-lang.org:parser>a", "c.defcl", 3, 7
    ) == syntax_errors.InvalidFqun(location=_location(7, 28))


def test_space():
    assert parser.parse_fqun(
        b"define-lang.org:my parser", "c.defcl", 3, 7
    ) == syntax_errors.FqunContainsSpace(location=_location(25, 25))


def test_empty_name():
    assert parser.parse_fqun(b"", "c.defcl", 3, 7) == syntax_errors.EmptyName(
        location=_location(7, 7)
    )


def test_control_character():
    assert parser.parse_fqun(
        b"define-lang.org:a\x01b", "c.defcl", 3, 7
    ) == syntax_errors.ControlCharacterError(
        location=_location(24, 24), escaped_char="\\u{1}"
    )


def test_control_character_before_space():
    assert parser.parse_fqun(
        b"define-lang.org:a\x01 b", "c.defcl", 3, 7
    ) == syntax_errors.ControlCharacterError(
        location=_location(24, 24), escaped_char="\\u{1}"
    )


def test_control_character_with_too_many_components():
    assert parser.parse_fqun(
        b"a:b:c:d\x01", "c.defcl", 3, 7
    ) == syntax_errors.ControlCharacterError(
        location=_location(14, 14), escaped_char="\\u{1}"
    )
