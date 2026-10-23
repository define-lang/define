# pyright: reportUnusedCallResult=false
"""Typed global-name reference parser tests.

Follow parser test authoring rules in parser_tests/AGENTS.md.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from define.compiler import ast, name_types
from define.compiler.errors import parser_exceptions

if TYPE_CHECKING:
    from define.compiler.parsing.parser_tests.conftest import Parse


def test_typed_global_name_reference_short_position_name(parse: Parse):
    program = parse(
        "define the potential position<mv:define-lang.org:parser:/root> {\n"
        + "    it may only contain particles where {\n"
        + "        it has the position</child>.\n"
        + "    }\n"
        + "}\n"
    )
    [definition] = program.definitions
    assert isinstance(definition, ast.PositionDefinition)
    assert (
        definition.typed_name.full_typed_name
        == "position<mv:define-lang.org:parser:/root>"
    )
    assert definition.constraints is not None
    [requirement] = definition.constraints.requirements
    typed_name = requirement.typed_global_name
    assert typed_name.name_type == name_types.NameType.POSITION
    assert typed_name.enclosing_fqun is definition.typed_name.name_content.fqun
    assert typed_name.full_typed_name == "position<mv:define-lang.org:parser:/child>"
    assert typed_name.location == ast.SourceLocation(
        line=3, column=20, end_line=3, end_column=35
    )
    name_content = typed_name.name_content
    assert name_content.location == ast.SourceLocation(
        line=3, column=29, end_line=3, end_column=34
    )
    assert name_content.fqun is None
    assert name_content.path.name == "/child"
    assert name_content.path.location == ast.SourceLocation(
        line=3, column=29, end_line=3, end_column=34
    )


def test_typed_global_name_reference_short_action_name(parse: Parse):
    program = parse(
        "define the potential position<mv:define-lang.org:parser:/root> {\n"
        + "    it may only contain particles where {\n"
        + "        it has the action</do_work>.\n"
        + "    }\n"
        + "}\n"
    )
    [definition] = program.definitions
    assert isinstance(definition, ast.PositionDefinition)
    assert (
        definition.typed_name.full_typed_name
        == "position<mv:define-lang.org:parser:/root>"
    )
    assert definition.constraints is not None
    [requirement] = definition.constraints.requirements
    typed_name = requirement.typed_global_name
    assert typed_name.name_type == name_types.NameType.ACTION
    assert typed_name.enclosing_fqun is definition.typed_name.name_content.fqun
    assert typed_name.full_typed_name == "action<mv:define-lang.org:parser:/do_work>"
    assert typed_name.location == ast.SourceLocation(
        line=3, column=20, end_line=3, end_column=35
    )
    name_content = typed_name.name_content
    assert name_content.location == ast.SourceLocation(
        line=3, column=27, end_line=3, end_column=34
    )
    assert name_content.fqun is None
    assert name_content.path.name == "/do_work"
    assert name_content.path.location == ast.SourceLocation(
        line=3, column=27, end_line=3, end_column=34
    )


def test_typed_global_name_reference_full_name(parse: Parse):
    program = parse(
        "define the potential position<mv:define-lang.org:parser:/root> {\n"
        + "    it may only contain particles where {\n"
        + "        it has the action<mv:define-lang.org:parser:/do_work>.\n"
        + "    }\n"
        + "}\n"
    )
    [definition] = program.definitions
    assert isinstance(definition, ast.PositionDefinition)
    assert (
        definition.typed_name.full_typed_name
        == "position<mv:define-lang.org:parser:/root>"
    )
    assert definition.constraints is not None
    [requirement] = definition.constraints.requirements
    typed_name = requirement.typed_global_name
    assert typed_name.name_type == name_types.NameType.ACTION
    assert typed_name.enclosing_fqun is definition.typed_name.name_content.fqun
    assert typed_name.full_typed_name == "action<mv:define-lang.org:parser:/do_work>"
    assert typed_name.location == ast.SourceLocation(
        line=3, column=20, end_line=3, end_column=61
    )
    name_content = typed_name.name_content
    assert name_content.location == ast.SourceLocation(
        line=3, column=27, end_line=3, end_column=60
    )
    assert name_content.fqun is not None
    assert name_content.fqun.canonical == "mv:define-lang.org:parser"
    assert name_content.fqun.location == ast.SourceLocation(
        line=3, column=27, end_line=3, end_column=51
    )
    assert name_content.path.name == "/do_work"
    assert name_content.path.location == ast.SourceLocation(
        line=3, column=53, end_line=3, end_column=60
    )


def test_typed_global_name_reference_local_style_name_is_global_terminal(
    parse: Parse,
):
    with pytest.raises(parser_exceptions.InvalidGlobalName) as exc_info:
        parse(
            "define the potential position<mv:define-lang.org:parser:/root> {\n"
            + "    it may only contain particles where {\n"
            + "        it has the position<foo>.\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.location.line == 3
    assert exc_info.value.location.column == 29
    assert exc_info.value.location.end_line == 3
    assert exc_info.value.location.end_column == 31
