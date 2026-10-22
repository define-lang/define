"""Value type definition parser tests."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from define.compiler import ast, name_types
from define.compiler.errors import parser_exceptions

if TYPE_CHECKING:
    from define.compiler.parsing.parser_tests.conftest import NativeParse


def test_value_definition(native_parse: NativeParse):
    program = native_parse(
        "define the potential value<mv:define-lang.org:parser:/number/natural>.\n"
    )
    [definition] = program.definitions
    assert isinstance(definition, ast.ValueDefinition)
    assert definition.typed_name.name_type == name_types.NameType.VALUE
    assert definition.typed_name.name_content.path.name == "/number/natural"
    assert definition.typed_name.location == ast.SourceLocation(
        line=1, column=22, end_line=1, end_column=69
    )
    assert definition.location == ast.SourceLocation(
        line=1, column=1, end_line=1, end_column=70
    )


def test_value_definition_requires_global_name(native_parse: NativeParse):
    with pytest.raises(parser_exceptions.InvalidGlobalName) as error:
        _ = native_parse("define the potential value<rational>.\n")
    assert error.value.location.line == 1
    assert error.value.location.column == 28
    assert error.value.location.end_line == 1
    assert error.value.location.end_column == 35


def test_value_definition_requires_terminator(native_parse: NativeParse):
    with pytest.raises(parser_exceptions.MissingTerminator) as error:
        _ = native_parse("define the potential value<standard:/number/natural>\n")
    assert error.value.location.line == 1
    assert error.value.location.column == 53
    assert error.value.location.end_line == 1
    assert error.value.location.end_column == 53


def test_value_definition_disallows_block(native_parse: NativeParse):
    with pytest.raises(parser_exceptions.MissingTerminator) as error:
        _ = native_parse("define the potential value<standard:/number/natural> {\n}\n")
    assert error.value.location.line == 1
    assert error.value.location.column == 53
    assert error.value.location.end_line == 1
    assert error.value.location.end_column == 53
