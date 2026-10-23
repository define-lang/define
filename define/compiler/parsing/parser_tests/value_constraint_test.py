"""Value constraint parser tests."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from define.compiler import ast, name_types
from define.compiler.errors import parser_exceptions

if TYPE_CHECKING:
    from define.compiler.parsing.parser_tests.conftest import Parse


def test_value_constraint_short_name(parse: Parse):
    program = parse(
        "define the potential position<mv:define-lang.org:parser:/item> {\n"
        + "    it may only contain particles where {\n"
        + "        it has the value</number/natural>.\n"
        + "    }\n"
        + "}\n"
    )
    [definition] = program.definitions
    assert isinstance(definition, ast.PositionDefinition)
    assert (
        definition.typed_name.full_typed_name
        == "position<mv:define-lang.org:parser:/item>"
    )
    assert definition.constraints is not None
    assert definition.constraints.value_constraint is not None
    typed_name = definition.constraints.value_constraint
    assert typed_name.name_type == name_types.NameType.VALUE
    assert typed_name.location == ast.SourceLocation(
        line=3, column=20, end_line=3, end_column=41
    )
    name_content = typed_name.name_content
    assert name_content.location == ast.SourceLocation(
        line=3, column=26, end_line=3, end_column=40
    )
    assert name_content.fqun is None
    assert name_content.path.name == "/number/natural"
    assert name_content.path.location == ast.SourceLocation(
        line=3, column=26, end_line=3, end_column=40
    )


def test_value_constraint_full_name(parse: Parse):
    program = parse(
        "define the potential position<mv:define-lang.org:parser:/item> {\n"
        + "    it may only contain particles where {\n"
        + "        it has the value<standard:/number/natural>.\n"
        + "    }\n"
        + "}\n"
    )
    [definition] = program.definitions
    assert isinstance(definition, ast.PositionDefinition)
    assert (
        definition.typed_name.full_typed_name
        == "position<mv:define-lang.org:parser:/item>"
    )
    assert definition.constraints is not None
    assert definition.constraints.value_constraint is not None
    typed_name = definition.constraints.value_constraint
    assert typed_name.name_type == name_types.NameType.VALUE
    assert typed_name.location == ast.SourceLocation(
        line=3, column=20, end_line=3, end_column=50
    )
    name_content = typed_name.name_content
    assert name_content.location == ast.SourceLocation(
        line=3, column=26, end_line=3, end_column=49
    )
    assert name_content.fqun is not None
    assert name_content.fqun.canonical == "standard"
    assert name_content.fqun.location == ast.SourceLocation(
        line=3, column=26, end_line=3, end_column=33
    )
    assert name_content.path.name == "/number/natural"
    assert name_content.path.location == ast.SourceLocation(
        line=3, column=35, end_line=3, end_column=49
    )


def test_value_constraint_requires_global_name(parse: Parse):
    with pytest.raises(parser_exceptions.InvalidGlobalName) as error:
        _ = parse(
            "define the potential position<mv:define-lang.org:parser:/item> {\n"
            + "    it may only contain particles where {\n"
            + "        it has the value<rational>.\n"
            + "    }\n"
            + "}\n"
        )
    assert error.value.location.line == 3
    assert error.value.location.column == 26
    assert error.value.location.end_line == 3
    assert error.value.location.end_column == 33


def test_constraint_name_type_error_includes_value(parse: Parse):
    with pytest.raises(parser_exceptions.ExpectedConstraintNameType) as error:
        _ = parse(
            "define the potential position<mv:define-lang.org:parser:/item> {\n"
            + "    it may only contain particles where {\n"
            + "        it has the thing</number>.\n"
            + "    }\n"
            + "}\n"
        )
    assert error.value.location.line == 3
    assert error.value.location.column == 20
    assert error.value.location.end_line == 3
    assert error.value.location.end_column == 24
