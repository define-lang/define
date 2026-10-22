# pyright: reportUnusedCallResult=false
"""Move particle statement parser tests.

Follow parser test authoring rules in parser_tests/AGENTS.md.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from define.compiler import ast, name_types

if TYPE_CHECKING:
    from define.compiler.parsing.parser_tests.conftest import NativeParse


def test_action_statements_block_with_move_particle_local_positions(
    native_parse: NativeParse,
):
    program = native_parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    define the position<run>.\n"
        + "    it happens when {\n"
        + "        the position<run> has a particle.\n"
        + "    } and it does {\n"
        + "        move the particle in position<source> to position<dest>.\n"
        + "    }\n"
        + "}\n"
    )
    [definition] = program.definitions
    assert isinstance(definition, ast.ActionDefinition)
    [statement] = definition.action_statements.statements
    assert isinstance(statement, ast.MoveParticleStatement)
    [source] = statement.source_position.typed_names
    assert isinstance(source, ast.LocalTypedNameReference)
    assert source.name_type == name_types.NameType.POSITION
    assert source.name_content.name == "source"
    assert statement.source_position.location == ast.SourceLocation(
        line=6, column=30, end_line=6, end_column=45
    )
    [dest] = statement.target_position.typed_names
    assert isinstance(dest, ast.LocalTypedNameReference)
    assert dest.name_type == name_types.NameType.POSITION
    assert dest.name_content.name == "dest"
    assert statement.target_position.location == ast.SourceLocation(
        line=6, column=50, end_line=6, end_column=63
    )


def test_action_statements_block_with_move_particle_short_global_positions(
    native_parse: NativeParse,
):
    program = native_parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    define the position<run>.\n"
        + "    it happens when {\n"
        + "        the position<run> has a particle.\n"
        + "    } and it does {\n"
        + "        move the particle in position</source> to position</dest>.\n"
        + "    }\n"
        + "}\n"
    )
    [definition] = program.definitions
    assert isinstance(definition, ast.ActionDefinition)
    [statement] = definition.action_statements.statements
    assert isinstance(statement, ast.MoveParticleStatement)
    [source] = statement.source_position.typed_names
    assert isinstance(source, ast.GlobalTypedNameReference)
    assert source.name_type == name_types.NameType.POSITION
    assert source.name_content.fqun is None
    assert source.name_content.path.name == "/source"
    assert statement.source_position.location == ast.SourceLocation(
        line=6, column=30, end_line=6, end_column=46
    )
    [dest] = statement.target_position.typed_names
    assert isinstance(dest, ast.GlobalTypedNameReference)
    assert dest.name_type == name_types.NameType.POSITION
    assert dest.name_content.fqun is None
    assert dest.name_content.path.name == "/dest"
    assert statement.target_position.location == ast.SourceLocation(
        line=6, column=51, end_line=6, end_column=65
    )


def test_action_statements_block_with_move_particle_full_global_positions(
    native_parse: NativeParse,
):
    program = native_parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    define the position<run>.\n"
        + "    it happens when {\n"
        + "        the position<run> has a particle.\n"
        + "    } and it does {\n"
        + "        move the particle in position<mv:define-lang.org:parser:/source> to position<mv:define-lang.org:parser:/dest>.\n"
        + "    }\n"
        + "}\n"
    )
    [definition] = program.definitions
    assert isinstance(definition, ast.ActionDefinition)
    [statement] = definition.action_statements.statements
    assert isinstance(statement, ast.MoveParticleStatement)
    [source] = statement.source_position.typed_names
    assert isinstance(source, ast.GlobalTypedNameReference)
    assert source.name_type == name_types.NameType.POSITION
    source_fqun = source.name_content.fqun
    assert source_fqun is not None
    assert source_fqun.multiverse is not None
    assert source_fqun.multiverse.name == "mv"
    assert source_fqun.authority is not None
    assert source_fqun.authority.name == "define-lang.org"
    assert source_fqun.universe.name == "parser"
    assert source.name_content.path.name == "/source"
    assert statement.source_position.location == ast.SourceLocation(
        line=6, column=30, end_line=6, end_column=72
    )
    [dest] = statement.target_position.typed_names
    assert isinstance(dest, ast.GlobalTypedNameReference)
    assert dest.name_type == name_types.NameType.POSITION
    dest_fqun = dest.name_content.fqun
    assert dest_fqun is not None
    assert dest_fqun.multiverse is not None
    assert dest_fqun.multiverse.name == "mv"
    assert dest_fqun.authority is not None
    assert dest_fqun.authority.name == "define-lang.org"
    assert dest_fqun.universe.name == "parser"
    assert dest.name_content.path.name == "/dest"
    assert statement.target_position.location == ast.SourceLocation(
        line=6, column=77, end_line=6, end_column=117
    )


def test_action_statements_block_with_move_particle_chained_source(
    native_parse: NativeParse,
):
    program = native_parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    define the position<run>.\n"
        + "    it happens when {\n"
        + "        the position<run> has a particle.\n"
        + "    } and it does {\n"
        + "        move the particle in position<src>::action</deposit>::position<inner> to position<dest>.\n"
        + "    }\n"
        + "}\n"
    )
    [definition] = program.definitions
    assert isinstance(definition, ast.ActionDefinition)
    [statement] = definition.action_statements.statements
    assert isinstance(statement, ast.MoveParticleStatement)
    [src, deposit, inner] = statement.source_position.typed_names
    assert isinstance(src, ast.LocalTypedNameReference)
    assert src.name_type == name_types.NameType.POSITION
    assert src.name_content.name == "src"
    assert isinstance(deposit, ast.GlobalTypedNameReference)
    assert deposit.name_type == name_types.NameType.ACTION
    assert deposit.name_content.fqun is None
    assert deposit.name_content.path.name == "/deposit"
    assert isinstance(inner, ast.LocalTypedNameReference)
    assert inner.name_type == name_types.NameType.POSITION
    assert inner.name_content.name == "inner"
    assert statement.source_position.location == ast.SourceLocation(
        line=6, column=30, end_line=6, end_column=77
    )
    [dest] = statement.target_position.typed_names
    assert isinstance(dest, ast.LocalTypedNameReference)
    assert dest.name_type == name_types.NameType.POSITION
    assert dest.name_content.name == "dest"
    assert statement.target_position.location == ast.SourceLocation(
        line=6, column=82, end_line=6, end_column=95
    )


def test_action_statements_block_with_move_particle_chained_destination(
    native_parse: NativeParse,
):
    program = native_parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    define the position<run>.\n"
        + "    it happens when {\n"
        + "        the position<run> has a particle.\n"
        + "    } and it does {\n"
        + "        move the particle in position<src> to position<dest>::action</deposit>::position<inner>.\n"
        + "    }\n"
        + "}\n"
    )
    [definition] = program.definitions
    assert isinstance(definition, ast.ActionDefinition)
    [statement] = definition.action_statements.statements
    assert isinstance(statement, ast.MoveParticleStatement)
    [src] = statement.source_position.typed_names
    assert isinstance(src, ast.LocalTypedNameReference)
    assert src.name_type == name_types.NameType.POSITION
    assert src.name_content.name == "src"
    assert statement.source_position.location == ast.SourceLocation(
        line=6, column=30, end_line=6, end_column=42
    )
    [dest, deposit, inner] = statement.target_position.typed_names
    assert isinstance(dest, ast.LocalTypedNameReference)
    assert dest.name_type == name_types.NameType.POSITION
    assert dest.name_content.name == "dest"
    assert isinstance(deposit, ast.GlobalTypedNameReference)
    assert deposit.name_type == name_types.NameType.ACTION
    assert deposit.name_content.fqun is None
    assert deposit.name_content.path.name == "/deposit"
    assert isinstance(inner, ast.LocalTypedNameReference)
    assert inner.name_type == name_types.NameType.POSITION
    assert inner.name_content.name == "inner"
    assert statement.target_position.location == ast.SourceLocation(
        line=6, column=47, end_line=6, end_column=95
    )


def test_action_statements_block_with_move_particle_both_chained(
    native_parse: NativeParse,
):
    program = native_parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    define the position<run>.\n"
        + "    it happens when {\n"
        + "        the position<run> has a particle.\n"
        + "    } and it does {\n"
        + "        move the particle in position<src>::action</a1> to position<dest>::action</a2>.\n"
        + "    }\n"
        + "}\n"
    )
    [definition] = program.definitions
    assert isinstance(definition, ast.ActionDefinition)
    [statement] = definition.action_statements.statements
    assert isinstance(statement, ast.MoveParticleStatement)
    [src, a1] = statement.source_position.typed_names
    assert isinstance(src, ast.LocalTypedNameReference)
    assert src.name_type == name_types.NameType.POSITION
    assert src.name_content.name == "src"
    assert isinstance(a1, ast.GlobalTypedNameReference)
    assert a1.name_type == name_types.NameType.ACTION
    assert a1.name_content.fqun is None
    assert a1.name_content.path.name == "/a1"
    assert statement.source_position.location == ast.SourceLocation(
        line=6, column=30, end_line=6, end_column=55
    )
    [dest, a2] = statement.target_position.typed_names
    assert isinstance(dest, ast.LocalTypedNameReference)
    assert dest.name_type == name_types.NameType.POSITION
    assert dest.name_content.name == "dest"
    assert isinstance(a2, ast.GlobalTypedNameReference)
    assert a2.name_type == name_types.NameType.ACTION
    assert a2.name_content.fqun is None
    assert a2.name_content.path.name == "/a2"
    assert statement.target_position.location == ast.SourceLocation(
        line=6, column=60, end_line=6, end_column=86
    )


def test_action_statements_block_with_mixed_create_and_move_statements(
    native_parse: NativeParse,
):
    program = native_parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    define the position<run>.\n"
        + "    it happens when {\n"
        + "        the position<run> has a particle.\n"
        + "    } and it does {\n"
        + "        create a particle in position<run>.\n"
        + "        move the particle in position<run> to position<done>.\n"
        + "    }\n"
        + "}\n"
    )
    [definition] = program.definitions
    assert isinstance(definition, ast.ActionDefinition)
    [create_statement, move_statement] = definition.action_statements.statements
    assert isinstance(create_statement, ast.CreateParticleStatement)
    assert create_statement.location == ast.SourceLocation(
        line=6, column=9, end_line=6, end_column=43
    )
    assert isinstance(move_statement, ast.MoveParticleStatement)
    assert move_statement.location == ast.SourceLocation(
        line=7, column=9, end_line=7, end_column=61
    )


def test_action_statements_block_with_move_particle_mixed_local_and_global(
    native_parse: NativeParse,
):
    program = native_parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    define the position<run>.\n"
        + "    it happens when {\n"
        + "        the position<run> has a particle.\n"
        + "    } and it does {\n"
        + "        move the particle in position<local_src> to position</global_dest>.\n"
        + "    }\n"
        + "}\n"
    )
    [definition] = program.definitions
    assert isinstance(definition, ast.ActionDefinition)
    [statement] = definition.action_statements.statements
    assert isinstance(statement, ast.MoveParticleStatement)
    [local_src] = statement.source_position.typed_names
    assert isinstance(local_src, ast.LocalTypedNameReference)
    assert local_src.name_type == name_types.NameType.POSITION
    assert local_src.name_content.name == "local_src"
    assert statement.source_position.location == ast.SourceLocation(
        line=6, column=30, end_line=6, end_column=48
    )
    [global_dest] = statement.target_position.typed_names
    assert isinstance(global_dest, ast.GlobalTypedNameReference)
    assert global_dest.name_type == name_types.NameType.POSITION
    assert global_dest.name_content.fqun is None
    assert global_dest.name_content.path.name == "/global_dest"
    assert statement.target_position.location == ast.SourceLocation(
        line=6, column=53, end_line=6, end_column=74
    )
