"""Encoding definition parser tests."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from define.compiler import ast, name_types
from define.compiler.errors import parser_exceptions

if TYPE_CHECKING:
    from define.compiler.parsing.parser_tests.conftest import Parse


def test_encoding_definition(parse: Parse):
    program = parse("define the encoding<mv:define-lang.org:parser:/number/natural>.\n")
    [definition] = program.definitions
    assert isinstance(definition, ast.EncodingDefinition)
    assert definition.typed_name.name_type == name_types.NameType.ENCODING
    assert definition.typed_name.name_content.path.name == "/number/natural"
    assert definition.typed_name.location == ast.SourceLocation(
        line=1, column=12, end_line=1, end_column=62
    )
    assert definition.location == ast.SourceLocation(
        line=1, column=1, end_line=1, end_column=63
    )


def test_encoding_definition_requires_global_name(parse: Parse):
    with pytest.raises(parser_exceptions.InvalidGlobalName) as error:
        _ = parse("define the encoding<rational>.\n")
    assert error.value.location.line == 1
    assert error.value.location.column == 21
    assert error.value.location.end_line == 1
    assert error.value.location.end_column == 28


def test_encoding_definition_requires_terminator(parse: Parse):
    with pytest.raises(parser_exceptions.MissingTerminator) as error:
        _ = parse("define the encoding<standard:/number/natural>\n")
    assert error.value.location.line == 1
    assert error.value.location.column == 46
    assert error.value.location.end_line == 1
    assert error.value.location.end_column == 46


def test_encoding_definition_disallows_block(parse: Parse):
    with pytest.raises(parser_exceptions.MissingTerminator) as error:
        _ = parse("define the encoding<standard:/number/natural> {\n}\n")
    assert error.value.location.line == 1
    assert error.value.location.column == 46
    assert error.value.location.end_line == 1
    assert error.value.location.end_column == 46


def test_encoding_definition_disallows_potential(parse: Parse):
    with pytest.raises(parser_exceptions.ExpectedGlobalDefinition) as error:
        _ = parse("define the potential encoding<mv:define-lang.org:parser:/utf8>.\n")
    assert error.value.location.line == 1
    assert error.value.location.column == 1
    assert error.value.location.end_line == 1
    assert error.value.location.end_column == 63


def test_encoding_definition_disallows_local_context(parse: Parse):
    with pytest.raises(parser_exceptions.InvalidActionStatementsBlock) as error:
        _ = parse(
            "define the potential action<mv:define-lang.org:parser:/test> {\n"
            + "    it happens when {\n"
            + "        this particle is created.\n"
            + "    } and it does {\n"
            + "        define the encoding<mv:define-lang.org:parser:/utf8>.\n"
            + "    }\n"
            + "}\n"
        )
    assert error.value.location.line == 5
    assert error.value.location.column == 9
    assert error.value.location.end_line == 5
    assert error.value.location.end_column == 61


def test_encoding_in_quality_assignments(parse: Parse):
    program = parse(
        "define the potential position<mv:define-lang.org:parser:/test> {\n"
        + "    it may only contain particles where {\n"
        + "        it has the encoding</utf8>.\n"
        + "    }\n"
        + "}\n"
    )
    [definition] = program.definitions
    assert isinstance(definition, ast.PositionDefinition)
    assert (
        definition.typed_name.full_typed_name
        == "position<mv:define-lang.org:parser:/test>"
    )
    assert definition.quality_assignment_block is not None
    [quality_assignment] = definition.quality_assignment_block.statements
    assert quality_assignment.location == ast.SourceLocation(
        line=3, column=9, end_line=3, end_column=35
    )
    typed_name = quality_assignment.typed_global_name
    assert typed_name.name_type == name_types.NameType.ENCODING
    assert typed_name.location == ast.SourceLocation(
        line=3, column=20, end_line=3, end_column=34
    )
    assert typed_name.name_content.fqun is None
    assert typed_name.name_content.path.name == "/utf8"
    assert typed_name.name_content.path.location == ast.SourceLocation(
        line=3, column=29, end_line=3, end_column=33
    )
