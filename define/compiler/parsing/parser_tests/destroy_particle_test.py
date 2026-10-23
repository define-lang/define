# pyright: reportUnusedCallResult=false
"""Destroy particle statement parser tests.

Follow parser test authoring rules in parser_tests/AGENTS.md.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from define.compiler import ast, name_types

if TYPE_CHECKING:
    from define.compiler.parsing.parser_tests.conftest import Parse


def test_action_statements_block_with_destroy_particle_local_position(
    parse: Parse,
):
    program = parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    define the position<run>.\n"
        + "    it happens when {\n"
        + "        the position<run> has a particle.\n"
        + "    } and it does {\n"
        + "        destroy the particle in position<run>.\n"
        + "    }\n"
        + "}\n"
    )
    [definition] = program.definitions
    assert isinstance(definition, ast.ActionDefinition)
    [statement] = definition.action_statements.statements
    assert isinstance(statement, ast.DestroyParticleStatement)
    [run] = statement.target_position.typed_names
    assert isinstance(run, ast.LocalTypedNameReference)
    assert run.name_type == name_types.NameType.POSITION
    assert run.name_content.name == "run"
    assert statement.target_position.location == ast.SourceLocation(
        line=6, column=33, end_line=6, end_column=45
    )


def test_action_statements_block_with_destroy_particle_short_global_position(
    parse: Parse,
):
    program = parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    define the position<run>.\n"
        + "    it happens when {\n"
        + "        the position<run> has a particle.\n"
        + "    } and it does {\n"
        + "        destroy the particle in position</run>.\n"
        + "    }\n"
        + "}\n"
    )
    [definition] = program.definitions
    assert isinstance(definition, ast.ActionDefinition)
    [statement] = definition.action_statements.statements
    assert isinstance(statement, ast.DestroyParticleStatement)
    [run] = statement.target_position.typed_names
    assert isinstance(run, ast.GlobalTypedNameReference)
    assert run.name_type == name_types.NameType.POSITION
    assert run.name_content.fqun is None
    assert run.name_content.path.name == "/run"
    assert statement.target_position.location == ast.SourceLocation(
        line=6, column=33, end_line=6, end_column=46
    )


def test_action_statements_block_with_destroy_particle_full_global_position(
    parse: Parse,
):
    program = parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    define the position<run>.\n"
        + "    it happens when {\n"
        + "        the position<run> has a particle.\n"
        + "    } and it does {\n"
        + "        destroy the particle in position<mv:define-lang.org:parser:/run>.\n"
        + "    }\n"
        + "}\n"
    )
    [definition] = program.definitions
    assert isinstance(definition, ast.ActionDefinition)
    [statement] = definition.action_statements.statements
    assert isinstance(statement, ast.DestroyParticleStatement)
    [run] = statement.target_position.typed_names
    assert isinstance(run, ast.GlobalTypedNameReference)
    assert run.name_type == name_types.NameType.POSITION
    fqun = run.name_content.fqun
    assert fqun is not None
    assert fqun.multiverse is not None
    assert fqun.multiverse.name == "mv"
    assert fqun.authority is not None
    assert fqun.authority.name == "define-lang.org"
    assert fqun.universe.name == "parser"
    assert run.name_content.path.name == "/run"
    assert statement.target_position.location == ast.SourceLocation(
        line=6, column=33, end_line=6, end_column=72
    )


def test_action_statements_block_with_destroy_particle_chained_position(
    parse: Parse,
):
    program = parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    define the position<run>.\n"
        + "    it happens when {\n"
        + "        the position<run> has a particle.\n"
        + "    } and it does {\n"
        + "        destroy the particle in position<to>::action</deposit>::position<run>.\n"
        + "    }\n"
        + "}\n"
    )
    [definition] = program.definitions
    assert isinstance(definition, ast.ActionDefinition)
    [statement] = definition.action_statements.statements
    assert isinstance(statement, ast.DestroyParticleStatement)
    [to, deposit, run] = statement.target_position.typed_names
    assert isinstance(to, ast.LocalTypedNameReference)
    assert to.name_type == name_types.NameType.POSITION
    assert to.name_content.name == "to"
    assert isinstance(deposit, ast.GlobalTypedNameReference)
    assert deposit.name_type == name_types.NameType.ACTION
    assert deposit.name_content.fqun is None
    assert deposit.name_content.path.name == "/deposit"
    assert isinstance(run, ast.LocalTypedNameReference)
    assert run.name_type == name_types.NameType.POSITION
    assert run.name_content.name == "run"
    assert statement.target_position.location == ast.SourceLocation(
        line=6, column=33, end_line=6, end_column=77
    )


def test_action_statements_block_with_destroy_particle_short_global_chain(
    parse: Parse,
):
    program = parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    define the position<run>.\n"
        + "    it happens when {\n"
        + "        the position<run> has a particle.\n"
        + "    } and it does {\n"
        + "        destroy the particle in position</to>::action</deposit>::position</run>.\n"
        + "    }\n"
        + "}\n"
    )
    [definition] = program.definitions
    assert isinstance(definition, ast.ActionDefinition)
    [statement] = definition.action_statements.statements
    assert isinstance(statement, ast.DestroyParticleStatement)
    [to, deposit, run] = statement.target_position.typed_names
    assert isinstance(to, ast.GlobalTypedNameReference)
    assert to.name_type == name_types.NameType.POSITION
    assert to.name_content.fqun is None
    assert to.name_content.path.name == "/to"
    assert isinstance(deposit, ast.GlobalTypedNameReference)
    assert deposit.name_type == name_types.NameType.ACTION
    assert deposit.name_content.fqun is None
    assert deposit.name_content.path.name == "/deposit"
    assert isinstance(run, ast.GlobalTypedNameReference)
    assert run.name_type == name_types.NameType.POSITION
    assert run.name_content.fqun is None
    assert run.name_content.path.name == "/run"
    assert statement.target_position.location == ast.SourceLocation(
        line=6, column=33, end_line=6, end_column=79
    )


def test_action_statements_block_with_destroy_particle_any_typed_chain(
    parse: Parse,
):
    program = parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    define the position<run>.\n"
        + "    it happens when {\n"
        + "        the position<run> has a particle.\n"
        + "    } and it does {\n"
        + "        destroy the particle in action</start>::position<mid>::action</end>.\n"
        + "    }\n"
        + "}\n"
    )
    [definition] = program.definitions
    assert isinstance(definition, ast.ActionDefinition)
    [statement] = definition.action_statements.statements
    assert isinstance(statement, ast.DestroyParticleStatement)
    [start, mid, end] = statement.target_position.typed_names
    assert isinstance(start, ast.GlobalTypedNameReference)
    assert start.name_type == name_types.NameType.ACTION
    assert start.name_content.fqun is None
    assert start.name_content.path.name == "/start"
    assert isinstance(mid, ast.LocalTypedNameReference)
    assert mid.name_type == name_types.NameType.POSITION
    assert mid.name_content.name == "mid"
    assert isinstance(end, ast.GlobalTypedNameReference)
    assert end.name_type == name_types.NameType.ACTION
    assert end.name_content.fqun is None
    assert end.name_content.path.name == "/end"
    assert statement.target_position.location == ast.SourceLocation(
        line=6, column=33, end_line=6, end_column=75
    )


def test_action_statements_block_with_mixed_create_move_and_destroy_statements(
    parse: Parse,
):
    program = parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    define the position<run>.\n"
        + "    it happens when {\n"
        + "        the position<run> has a particle.\n"
        + "    } and it does {\n"
        + "        create a particle in position<run>.\n"
        + "        move the particle in position<run> to position<done>.\n"
        + "        destroy the particle in position<done>.\n"
        + "    }\n"
        + "}\n"
    )
    [definition] = program.definitions
    assert isinstance(definition, ast.ActionDefinition)
    [create_statement, move_statement, destroy_statement] = (
        definition.action_statements.statements
    )
    assert isinstance(create_statement, ast.CreateParticleStatement)
    assert create_statement.location == ast.SourceLocation(
        line=6, column=9, end_line=6, end_column=43
    )
    assert isinstance(move_statement, ast.MoveParticleStatement)
    assert move_statement.location == ast.SourceLocation(
        line=7, column=9, end_line=7, end_column=61
    )
    assert isinstance(destroy_statement, ast.DestroyParticleStatement)
    assert destroy_statement.location == ast.SourceLocation(
        line=8, column=9, end_line=8, end_column=47
    )


def test_action_statements_block_with_mixed_statements_and_multiple_destroy_particles(
    parse: Parse,
):
    program = parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    define the position<run>.\n"
        + "    it happens when {\n"
        + "        the position<run> has a particle.\n"
        + "    } and it does {\n"
        + "        define the position<inner_pos>.\n"
        + "        destroy the particle in position<inner_pos>.\n"
        + "        destroy the particle in position</global_run>::action</deposit>::position<inner_pos>.\n"
        + "    }\n"
        + "}\n"
    )
    [definition] = program.definitions
    assert isinstance(definition, ast.ActionDefinition)
    [position_definition, local_destroy, chained_destroy] = (
        definition.action_statements.statements
    )
    assert isinstance(position_definition, ast.LocalPositionDefinition)
    assert position_definition.location == ast.SourceLocation(
        line=6, column=9, end_line=6, end_column=39
    )
    assert isinstance(local_destroy, ast.DestroyParticleStatement)
    assert local_destroy.location == ast.SourceLocation(
        line=7, column=9, end_line=7, end_column=52
    )
    assert isinstance(chained_destroy, ast.DestroyParticleStatement)
    assert chained_destroy.location == ast.SourceLocation(
        line=8, column=9, end_line=8, end_column=93
    )


def test_action_statements_block_with_destroy_particle_mixed_local_and_global(
    parse: Parse,
):
    program = parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    define the position<run>.\n"
        + "    it happens when {\n"
        + "        the position<run> has a particle.\n"
        + "    } and it does {\n"
        + "        destroy the particle in position<local_pos>::action</global_act>::position<inner>.\n"
        + "    }\n"
        + "}\n"
    )
    [definition] = program.definitions
    assert isinstance(definition, ast.ActionDefinition)
    [statement] = definition.action_statements.statements
    assert isinstance(statement, ast.DestroyParticleStatement)
    [local_pos, global_act, inner] = statement.target_position.typed_names
    assert isinstance(local_pos, ast.LocalTypedNameReference)
    assert local_pos.name_type == name_types.NameType.POSITION
    assert local_pos.name_content.name == "local_pos"
    assert isinstance(global_act, ast.GlobalTypedNameReference)
    assert global_act.name_type == name_types.NameType.ACTION
    assert global_act.name_content.fqun is None
    assert global_act.name_content.path.name == "/global_act"
    assert isinstance(inner, ast.LocalTypedNameReference)
    assert inner.name_type == name_types.NameType.POSITION
    assert inner.name_content.name == "inner"
    assert statement.target_position.location == ast.SourceLocation(
        line=6, column=33, end_line=6, end_column=89
    )
