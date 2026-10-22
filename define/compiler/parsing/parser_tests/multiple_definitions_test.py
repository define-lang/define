# pyright: reportUnusedCallResult=false
"""Multiple definition parser tests.

Follow parser test authoring rules in parser_tests/AGENTS.md.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from define.compiler import ast, name_types

if TYPE_CHECKING:
    from define.compiler.parsing.parser_tests.conftest import NativeParse


def test_multiple_position_definitions(native_parse: NativeParse):
    program = native_parse(
        "define the potential position<example.com:my_lib:/first>.\n"
        + "define the potential position<example.com:my_lib:/second>.\n"
    )
    [first, second] = program.definitions
    assert isinstance(first, ast.PositionDefinition)
    assert first.typed_name.full_typed_name == "position<example.com:my_lib:/first>"
    assert first.location == ast.SourceLocation(
        line=1, column=1, end_line=1, end_column=57
    )
    assert isinstance(second, ast.PositionDefinition)
    assert second.typed_name.full_typed_name == "position<example.com:my_lib:/second>"
    assert second.location == ast.SourceLocation(
        line=2, column=1, end_line=2, end_column=58
    )


def test_multiple_action_definitions(native_parse: NativeParse):
    program = native_parse(
        "define the potential action<my_mv:example.com:my_lib:/first> {\n"
        + "    define the position<_noop>.\n"
        + "    it happens when {\n"
        + "        the position<_noop> has a particle.\n"
        + "    } and it does {\n"
        + "        define the position<__noop>.\n"
        + "        create a particle in position<__noop>.\n"
        + "    }\n"
        + "}\n"
        + "define the potential action<my_mv:example.com:my_lib:/second> {\n"
        + "    define the position<_noop>.\n"
        + "    it happens when {\n"
        + "        the position<_noop> has a particle.\n"
        + "    } and it does {\n"
        + "        define the position<__noop>.\n"
        + "        create a particle in position<__noop>.\n"
        + "    }\n"
        + "}\n"
    )
    [first, second] = program.definitions
    assert isinstance(first, ast.ActionDefinition)
    assert first.typed_name.name_type == name_types.NameType.ACTION
    assert first.typed_name.name_content.path.name == "/first"
    assert first.location == ast.SourceLocation(
        line=1, column=1, end_line=9, end_column=1
    )
    assert isinstance(second, ast.ActionDefinition)
    assert second.typed_name.name_type == name_types.NameType.ACTION
    assert second.typed_name.name_content.path.name == "/second"
    assert second.location == ast.SourceLocation(
        line=10, column=1, end_line=18, end_column=1
    )


def test_mixed_position_and_action_definitions(native_parse: NativeParse):
    program = native_parse(
        "define the potential position<example.com:my_lib:/pos>.\n"
        + "define the potential action<my_mv:example.com:my_lib:/act> {\n"
        + "    define the position<_noop>.\n"
        + "    it happens when {\n"
        + "        the position<_noop> has a particle.\n"
        + "    } and it does {\n"
        + "        define the position<__noop>.\n"
        + "        create a particle in position<__noop>.\n"
        + "    }\n"
        + "}\n"
    )
    [position_definition, action_definition] = program.definitions
    assert isinstance(position_definition, ast.PositionDefinition)
    assert position_definition.typed_name.name_type == name_types.NameType.POSITION
    assert position_definition.typed_name.name_content.path.name == "/pos"
    assert position_definition.location == ast.SourceLocation(
        line=1, column=1, end_line=1, end_column=55
    )
    assert isinstance(action_definition, ast.ActionDefinition)
    assert action_definition.typed_name.name_type == name_types.NameType.ACTION
    assert action_definition.typed_name.name_content.path.name == "/act"
    assert action_definition.location == ast.SourceLocation(
        line=2, column=1, end_line=10, end_column=1
    )


def test_definitions_separated_by_blank_lines(native_parse: NativeParse):
    program = native_parse(
        "define the potential position<standard:/first>.\n"
        + "\n"
        + "define the potential position<example.com:my_lib:/second>.\n"
    )
    [first, second] = program.definitions
    assert isinstance(first, ast.PositionDefinition)
    assert first.typed_name.full_typed_name == "position<standard:/first>"
    assert first.location == ast.SourceLocation(
        line=1, column=1, end_line=1, end_column=47
    )
    assert isinstance(second, ast.PositionDefinition)
    assert second.typed_name.full_typed_name == "position<example.com:my_lib:/second>"
    assert second.location == ast.SourceLocation(
        line=3, column=1, end_line=3, end_column=58
    )


def test_definitions_separated_by_comments(native_parse: NativeParse):
    program = native_parse(
        "define the potential position<my_mv:example.com:my_lib:/first>.\n"
        + "# a comment between definitions\n"
        + "define the potential position<my_mv:example.com:my_lib:/second>.\n"
    )
    [first, second] = program.definitions
    assert isinstance(first, ast.PositionDefinition)
    assert (
        first.typed_name.full_typed_name == "position<my_mv:example.com:my_lib:/first>"
    )
    assert first.location == ast.SourceLocation(
        line=1, column=1, end_line=1, end_column=63
    )
    assert isinstance(second, ast.PositionDefinition)
    assert (
        second.typed_name.full_typed_name
        == "position<my_mv:example.com:my_lib:/second>"
    )
    assert second.location == ast.SourceLocation(
        line=3, column=1, end_line=3, end_column=64
    )
