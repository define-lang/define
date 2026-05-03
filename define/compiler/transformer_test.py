"""Tests for the Define AST transformer."""

from pathlib import Path

from define.compiler import ast, parser
from define.compiler.transformer import DefineTransformer

_parser = parser.Parser()


def _parse_and_transform(source: str) -> ast.Program:
    result = _parser.parse(source)
    assert result.diagnostics == []
    assert result.tree is not None
    return DefineTransformer().transform(result.tree)


def _require_fqun(name: ast.GlobalNameContent) -> ast.Fqun:
    assert name.fqun is not None
    return name.fqun


def test_position_definition_transforms_to_program():
    program = _parse_and_transform("define the potential position<standard:/path>.\n")
    assert isinstance(program, ast.Program)
    assert program.location.line == 1
    assert program.location.column == 1
    assert len(program.definitions) == 1
    definition = program.definitions[0]
    assert isinstance(definition, ast.PositionDefinition)
    fqun = _require_fqun(definition.typed_name.name_content)
    assert definition.location.line == 1
    assert definition.location.column == 1
    assert fqun.universe.name == "standard"
    assert fqun.universe.location.line == 1
    assert fqun.universe.location.column == 31
    assert definition.typed_name.name_content.path.relative_path == Path("path")
    assert definition.typed_name.name_content.path.name == "/path"
    assert definition.typed_name.name_content.path.location.line == 1
    assert definition.typed_name.name_content.path.location.column == 40
    assert definition.typed_name.name_content.location.line == 1
    assert definition.typed_name.name_content.location.column == 31
    assert definition.typed_name.location == ast.SourceLocation(
        line=1, column=22, end_line=1, end_column=46
    )


def test_action_definition_transforms_to_program():
    program = _parse_and_transform(
        "define the potential action<standard:/path> {\n"
        + "    define the position<_noop>.\n"
        + "    it happens when {\n"
        + "        the position<_noop> has a dimension point.\n"
        + "    } and it does {\n"
        + "        define the position<__noop>.\n"
        + "        create a dimension point in position<__noop>.\n"
        + "    }\n"
        + "}\n"
    )
    assert isinstance(program, ast.Program)
    assert len(program.definitions) == 1
    definition = program.definitions[0]
    assert isinstance(definition, ast.ActionDefinition)
    fqun = _require_fqun(definition.typed_name.name_content)
    assert definition.location.line == 1
    assert fqun.universe.name == "standard"
    assert definition.typed_name.name_content.path.relative_path == Path("path")
    assert definition.typed_name.location == ast.SourceLocation(
        line=1, column=22, end_line=1, end_column=44
    )


def test_local_position_definition_transforms_to_program():
    program = _parse_and_transform(
        "define the potential action<standard:/path> {\n"
        + "    define the position<_pp>.\n"
        + "    it happens when {\n"
        + "        the position<_pp> has a dimension point.\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    )
    definition = program.definitions[0]
    assert isinstance(definition, ast.ActionDefinition)
    assert len(definition.interface_positions) == 1
    local_def = definition.interface_positions[0]
    assert local_def.typed_name.name_content.location == ast.SourceLocation(
        line=2, column=25, end_line=2, end_column=28
    )
    assert local_def.typed_name.location == ast.SourceLocation(
        line=2, column=16, end_line=2, end_column=29
    )


def test_global_name_full_fqun():
    program = _parse_and_transform(
        "define the potential position<my_mv:example.com:my_lib:/some/path>.\n"
    )
    name = program.definitions[0].typed_name.name_content
    fqun = _require_fqun(name)
    assert fqun.multiverse is not None
    assert fqun.multiverse.name == "my_mv"
    assert fqun.multiverse.location.line == 1
    assert fqun.multiverse.location.column == 31
    assert fqun.universe.name == "my_lib"
    assert fqun.universe.location.line == 1
    assert fqun.universe.location.column == 49
    assert name.path.relative_path == Path("some/path")
    assert fqun.authority is not None
    assert fqun.authority.name == "example.com"
    assert fqun.authority.location.line == 1
    assert fqun.authority.location.column == 37


def test_global_name_authority_universe():
    program = _parse_and_transform(
        "define the potential position<example.com:my_lib:/some/path>.\n"
    )
    name = program.definitions[0].typed_name.name_content
    fqun = _require_fqun(name)
    assert fqun.multiverse is None
    assert fqun.universe.name == "my_lib"
    assert fqun.universe.location.line == 1
    assert fqun.universe.location.column == 43
    assert name.path.relative_path == Path("some/path")
    assert fqun.authority is not None
    assert fqun.authority.name == "example.com"
    assert fqun.authority.location.line == 1


def test_global_name_authority_with_path_universe():
    program = _parse_and_transform(
        "define the potential position<example.com/org/repo:my_lib:/some/path>.\n"
    )
    name = program.definitions[0].typed_name.name_content
    fqun = _require_fqun(name)
    assert fqun.multiverse is None
    assert fqun.universe.name == "my_lib"
    assert name.path.relative_path == Path("some/path")
    assert fqun.authority is not None
    assert fqun.authority.name == "example.com/org/repo"


def test_global_name_universe_only():
    program = _parse_and_transform(
        "define the potential position<standard:/some/path>.\n"
    )
    name = program.definitions[0].typed_name.name_content
    fqun = _require_fqun(name)
    assert fqun.multiverse is None
    assert fqun.authority is None
    assert fqun.universe.name == "standard"
    assert fqun.universe.location.line == 1
    assert fqun.universe.location.column == 31
    assert fqun.location.line == 1
    assert fqun.location.column == 31
    assert name.path.relative_path == Path("some/path")


def test_multiple_definitions_position_and_action():
    program = _parse_and_transform(
        "define the potential position<standard:/pos>.\n"
        + "define the potential action<standard:/act> {\n"
        + "    define the position<_noop>.\n"
        + "    it happens when {\n"
        + "        the position<_noop> has a dimension point.\n"
        + "    } and it does {\n"
        + "        define the position<__noop>.\n"
        + "        create a dimension point in position<__noop>.\n"
        + "    }\n"
        + "}\n"
    )
    assert len(program.definitions) == 2
    assert isinstance(program.definitions[0], ast.PositionDefinition)
    assert isinstance(program.definitions[1], ast.ActionDefinition)
    assert program.definitions[0].typed_name.name_content.path.relative_path == Path(
        "pos"
    )
    assert program.definitions[1].typed_name.name_content.path.relative_path == Path(
        "act"
    )
    assert program.definitions[0].location.line == 1
    assert program.definitions[1].location.line == 2


def test_action_definition_block_transforms():
    program = _parse_and_transform(
        "define the potential action<standard:/path> {\n"
        + "    define the position<run>.\n"
        + "    it happens when {\n"
        + "        the position<run> has a dimension point.\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    )
    definition = program.definitions[0]
    assert isinstance(definition, ast.ActionDefinition)
    assert len(definition.interface_positions) == 1
    assert definition.interface_positions[0].typed_name.name_content.name == "run"
    assert definition.trigger_conditions is not None
    assert definition.action_statements.statements == []


def test_action_definition_block_with_interface_position():
    program = _parse_and_transform(
        "define the potential action<standard:/path> {\n"
        + "    define the position<my_pos>.\n"
        + "    it happens when {\n"
        + "        the position<my_pos> has a dimension point.\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    )
    definition = program.definitions[0]
    assert isinstance(definition, ast.ActionDefinition)
    assert len(definition.interface_positions) == 1
    assert definition.interface_positions[0].typed_name.name_content.name == "my_pos"


def test_action_definition_block_with_multiple_interface_positions():
    program = _parse_and_transform(
        "define the potential action<standard:/path> {\n"
        + "    define the position<first_pos>.\n"
        + "    define the position<second_pos>.\n"
        + "    it happens when {\n"
        + "        the position<first_pos> has a dimension point.\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    )
    definition = program.definitions[0]
    assert isinstance(definition, ast.ActionDefinition)
    assert len(definition.interface_positions) == 2
    assert definition.interface_positions[0].typed_name.name_content.name == "first_pos"
    assert (
        definition.interface_positions[1].typed_name.name_content.name == "second_pos"
    )


def test_action_definition_block_source_positions():
    program = _parse_and_transform(
        "define the potential action<standard:/path> {\n"
        + "    define the position<run>.\n"
        + "    it happens when {\n"
        + "        the position<run> has a dimension point.\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    )
    definition = program.definitions[0]
    assert isinstance(definition, ast.ActionDefinition)
    assert definition.location.line == 1
    assert definition.trigger_conditions.location.line == 3
    assert definition.action_statements.location.line == 5
    assert definition.action_statements.statements == []


def test_action_definition_block_interface_position_source_position():
    program = _parse_and_transform(
        "define the potential action<standard:/path> {\n"
        + "    define the position<my_pos>.\n"
        + "    it happens when {\n"
        + "        the position<my_pos> has a dimension point.\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    )
    definition = program.definitions[0]
    assert isinstance(definition, ast.ActionDefinition)
    local_def = definition.interface_positions[0]
    assert local_def.location.line == 2
    assert local_def.location.column == 5


def test_action_definition_block_with_action_statement_local_definition():
    program = _parse_and_transform(
        "define the potential action<standard:/path> {\n"
        + "    define the position<run>.\n"
        + "    it happens when {\n"
        + "        the position<run> has a dimension point.\n"
        + "    } and it does {\n"
        + "        define the position<inner_pos>.\n"
        + "    }\n"
        + "}\n"
    )
    definition = program.definitions[0]
    assert isinstance(definition, ast.ActionDefinition)
    assert len(definition.action_statements.statements) == 1
    local_def = definition.action_statements.statements[0]
    assert isinstance(local_def, ast.LocalPositionDefinition)
    assert local_def.typed_name.name_content.name == "inner_pos"
    assert local_def.location.line == 6
    assert local_def.location.column == 9


def test_action_definition_block_with_multiple_action_statement_local_definitions():
    program = _parse_and_transform(
        "define the potential action<standard:/path> {\n"
        + "    define the position<run>.\n"
        + "    it happens when {\n"
        + "        the position<run> has a dimension point.\n"
        + "    } and it does {\n"
        + "        define the position<first_inner>.\n"
        + "        define the position<second_inner>.\n"
        + "    }\n"
        + "}\n"
    )
    definition = program.definitions[0]
    assert isinstance(definition, ast.ActionDefinition)
    assert len(definition.action_statements.statements) == 2
    first_local_def = definition.action_statements.statements[0]
    second_local_def = definition.action_statements.statements[1]
    assert isinstance(first_local_def, ast.LocalPositionDefinition)
    assert isinstance(second_local_def, ast.LocalPositionDefinition)
    assert first_local_def.typed_name.name_content.name == "first_inner"
    assert second_local_def.typed_name.name_content.name == "second_inner"
    assert first_local_def.location.line == 6
    assert second_local_def.location.line == 7


def test_position_definition_with_constraints_block_transforms():
    program = _parse_and_transform(
        "define the potential position<standard:/path> {\n"
        + "    it may only contain dimension points where {\n"
        + "        it has the position</child>.\n"
        + "        it has the action</other>.\n"
        + "    }\n"
        + "}\n"
    )
    definition = program.definitions[0]
    assert isinstance(definition, ast.PositionDefinition)
    assert definition.constraints is not None
    assert len(definition.constraints.requirements) == 2
    first_requirement = definition.constraints.requirements[0]
    second_requirement = definition.constraints.requirements[1]
    assert first_requirement.typed_global_name.name_type == ast.NameType.POSITION
    assert second_requirement.typed_global_name.name_type == ast.NameType.ACTION
    assert first_requirement.typed_global_name.name_content.fqun is None
    assert first_requirement.typed_global_name.name_content.path.relative_path == Path(
        "child"
    )
    assert second_requirement.typed_global_name.name_content.path.relative_path == Path(
        "other"
    )
    assert definition.constraints.location.line == 2
    assert first_requirement.location.line == 3
    assert second_requirement.location.line == 4


def test_create_dimension_point_with_local_position():
    program = _parse_and_transform(
        "define the potential action<standard:/path> {\n"
        + "    define the position<run>.\n"
        + "    it happens when {\n"
        + "        the position<run> has a dimension point.\n"
        + "    } and it does {\n"
        + "        create a dimension point in position<run>.\n"
        + "    }\n"
        + "}\n"
    )
    definition = program.definitions[0]
    assert isinstance(definition, ast.ActionDefinition)
    assert len(definition.action_statements.statements) == 1
    stmt = definition.action_statements.statements[0]
    assert isinstance(stmt, ast.CreateDimensionPointStatement)
    assert len(stmt.target_position.typed_names) == 1
    ref = stmt.target_position.typed_names[0]
    assert isinstance(ref, ast.LocalTypedNameReference)
    assert ref.name_type == ast.NameType.POSITION
    assert ref.name_content.name == "run"


def test_create_dimension_point_with_short_global_position():
    program = _parse_and_transform(
        "define the potential action<standard:/path> {\n"
        + "    define the position<run>.\n"
        + "    it happens when {\n"
        + "        the position<run> has a dimension point.\n"
        + "    } and it does {\n"
        + "        create a dimension point in position</run>.\n"
        + "    }\n"
        + "}\n"
    )
    definition = program.definitions[0]
    assert isinstance(definition, ast.ActionDefinition)
    stmt = definition.action_statements.statements[0]
    assert isinstance(stmt, ast.CreateDimensionPointStatement)
    ref = stmt.target_position.typed_names[0]
    assert isinstance(ref, ast.GlobalTypedNameReference)
    assert ref.name_type == ast.NameType.POSITION
    assert ref.name_content.fqun is None
    assert ref.name_content.path.name == "/run"


def test_create_dimension_point_with_full_fqun_position():
    program = _parse_and_transform(
        "define the potential action<standard:/path> {\n"
        + "    define the position<run>.\n"
        + "    it happens when {\n"
        + "        the position<run> has a dimension point.\n"
        + "    } and it does {\n"
        + "        create a dimension point in position<mv:define-lang.org:parser:/run>.\n"
        + "    }\n"
        + "}\n"
    )
    definition = program.definitions[0]
    assert isinstance(definition, ast.ActionDefinition)
    stmt = definition.action_statements.statements[0]
    assert isinstance(stmt, ast.CreateDimensionPointStatement)
    ref = stmt.target_position.typed_names[0]
    assert isinstance(ref, ast.GlobalTypedNameReference)
    assert ref.name_type == ast.NameType.POSITION
    fqun = ref.name_content.fqun
    assert fqun is not None
    assert fqun.multiverse is not None
    assert fqun.multiverse.name == "mv"
    assert fqun.authority is not None
    assert fqun.authority.name == "define-lang.org"
    assert fqun.universe.name == "parser"
    assert ref.name_content.path.name == "/run"


def test_chained_position_reference_with_local_names():
    program = _parse_and_transform(
        "define the potential action<standard:/path> {\n"
        + "    define the position<run>.\n"
        + "    it happens when {\n"
        + "        the position<run> has a dimension point.\n"
        + "    } and it does {\n"
        + "        create a dimension point in position<to>::action<deposit>::position<run>.\n"
        + "    }\n"
        + "}\n"
    )
    definition = program.definitions[0]
    assert isinstance(definition, ast.ActionDefinition)
    stmt = definition.action_statements.statements[0]
    assert isinstance(stmt, ast.CreateDimensionPointStatement)
    chain = stmt.target_position.typed_names
    assert len(chain) == 3
    assert isinstance(chain[0], ast.LocalTypedNameReference)
    assert chain[0].name_type == ast.NameType.POSITION
    assert chain[0].name_content.name == "to"
    assert isinstance(chain[1], ast.LocalTypedNameReference)
    assert chain[1].name_type == ast.NameType.ACTION
    assert chain[1].name_content.name == "deposit"
    assert isinstance(chain[2], ast.LocalTypedNameReference)
    assert chain[2].name_type == ast.NameType.POSITION
    assert chain[2].name_content.name == "run"


def test_chained_position_reference_with_global_names():
    program = _parse_and_transform(
        "define the potential action<standard:/path> {\n"
        + "    define the position<run>.\n"
        + "    it happens when {\n"
        + "        the position<run> has a dimension point.\n"
        + "    } and it does {\n"
        + "        create a dimension point in position</to>::action</deposit>::position</run>.\n"
        + "    }\n"
        + "}\n"
    )
    definition = program.definitions[0]
    assert isinstance(definition, ast.ActionDefinition)
    stmt = definition.action_statements.statements[0]
    assert isinstance(stmt, ast.CreateDimensionPointStatement)
    chain = stmt.target_position.typed_names
    assert len(chain) == 3
    assert isinstance(chain[0], ast.GlobalTypedNameReference)
    assert chain[0].name_content.path.name == "/to"
    assert isinstance(chain[1], ast.GlobalTypedNameReference)
    assert chain[1].name_content.path.name == "/deposit"
    assert isinstance(chain[2], ast.GlobalTypedNameReference)
    assert chain[2].name_content.path.name == "/run"


def test_chained_position_reference_mixed_types():
    program = _parse_and_transform(
        "define the potential action<standard:/path> {\n"
        + "    define the position<run>.\n"
        + "    it happens when {\n"
        + "        the position<run> has a dimension point.\n"
        + "    } and it does {\n"
        + "        create a dimension point in action</start>::position<mid>::action</end>.\n"
        + "    }\n"
        + "}\n"
    )
    definition = program.definitions[0]
    assert isinstance(definition, ast.ActionDefinition)
    stmt = definition.action_statements.statements[0]
    assert isinstance(stmt, ast.CreateDimensionPointStatement)
    chain = stmt.target_position.typed_names
    assert len(chain) == 3
    assert isinstance(chain[0], ast.GlobalTypedNameReference)
    assert chain[0].name_type == ast.NameType.ACTION
    assert chain[0].name_content.path.name == "/start"
    assert isinstance(chain[1], ast.LocalTypedNameReference)
    assert chain[1].name_type == ast.NameType.POSITION
    assert chain[1].name_content.name == "mid"
    assert isinstance(chain[2], ast.GlobalTypedNameReference)
    assert chain[2].name_type == ast.NameType.ACTION
    assert chain[2].name_content.path.name == "/end"


def test_mixed_action_statements():
    program = _parse_and_transform(
        "define the potential action<standard:/path> {\n"
        + "    define the position<run>.\n"
        + "    it happens when {\n"
        + "        the position<run> has a dimension point.\n"
        + "    } and it does {\n"
        + "        define the position<inner_pos>.\n"
        + "        create a dimension point in position<run>.\n"
        + "        create a dimension point in position</other>.\n"
        + "    }\n"
        + "}\n"
    )
    definition = program.definitions[0]
    assert isinstance(definition, ast.ActionDefinition)
    stmts = definition.action_statements.statements
    assert len(stmts) == 3
    assert isinstance(stmts[0], ast.LocalPositionDefinition)
    assert stmts[0].typed_name.name_content.name == "inner_pos"
    assert isinstance(stmts[1], ast.CreateDimensionPointStatement)
    assert isinstance(stmts[2], ast.CreateDimensionPointStatement)


def test_move_dimension_point_with_local_positions():
    program = _parse_and_transform(
        "define the potential action<standard:/path> {\n"
        + "    define the position<run>.\n"
        + "    it happens when {\n"
        + "        the position<run> has a dimension point.\n"
        + "    } and it does {\n"
        + "        move the dimension point in position<source> to position<dest>.\n"
        + "    }\n"
        + "}\n"
    )
    definition = program.definitions[0]
    assert isinstance(definition, ast.ActionDefinition)
    assert len(definition.action_statements.statements) == 1
    stmt = definition.action_statements.statements[0]
    assert isinstance(stmt, ast.MoveDimensionPointStatement)
    assert len(stmt.source_position.typed_names) == 1
    from_ref = stmt.source_position.typed_names[0]
    assert isinstance(from_ref, ast.LocalTypedNameReference)
    assert from_ref.name_type == ast.NameType.POSITION
    assert from_ref.name_content.name == "source"
    assert len(stmt.target_position.typed_names) == 1
    to_ref = stmt.target_position.typed_names[0]
    assert isinstance(to_ref, ast.LocalTypedNameReference)
    assert to_ref.name_type == ast.NameType.POSITION
    assert to_ref.name_content.name == "dest"


def test_move_dimension_point_with_short_global_positions():
    program = _parse_and_transform(
        "define the potential action<standard:/path> {\n"
        + "    define the position<run>.\n"
        + "    it happens when {\n"
        + "        the position<run> has a dimension point.\n"
        + "    } and it does {\n"
        + "        move the dimension point in position</source> to position</dest>.\n"
        + "    }\n"
        + "}\n"
    )
    definition = program.definitions[0]
    assert isinstance(definition, ast.ActionDefinition)
    stmt = definition.action_statements.statements[0]
    assert isinstance(stmt, ast.MoveDimensionPointStatement)
    from_ref = stmt.source_position.typed_names[0]
    assert isinstance(from_ref, ast.GlobalTypedNameReference)
    assert from_ref.name_type == ast.NameType.POSITION
    assert from_ref.name_content.fqun is None
    assert from_ref.name_content.path.name == "/source"
    to_ref = stmt.target_position.typed_names[0]
    assert isinstance(to_ref, ast.GlobalTypedNameReference)
    assert to_ref.name_type == ast.NameType.POSITION
    assert to_ref.name_content.fqun is None
    assert to_ref.name_content.path.name == "/dest"


def test_move_dimension_point_with_full_fqun_positions():
    program = _parse_and_transform(
        "define the potential action<standard:/path> {\n"
        + "    define the position<run>.\n"
        + "    it happens when {\n"
        + "        the position<run> has a dimension point.\n"
        + "    } and it does {\n"
        + "        move the dimension point in position<mv:authority.com:universe:/source> to position<mv:authority.com:universe:/dest>.\n"
        + "    }\n"
        + "}\n"
    )
    definition = program.definitions[0]
    assert isinstance(definition, ast.ActionDefinition)
    stmt = definition.action_statements.statements[0]
    assert isinstance(stmt, ast.MoveDimensionPointStatement)
    from_ref = stmt.source_position.typed_names[0]
    assert isinstance(from_ref, ast.GlobalTypedNameReference)
    assert from_ref.name_content.fqun is not None
    assert from_ref.name_content.fqun.canonical == "mv:authority.com:universe"
    assert from_ref.name_content.path.name == "/source"
    to_ref = stmt.target_position.typed_names[0]
    assert isinstance(to_ref, ast.GlobalTypedNameReference)
    assert to_ref.name_content.fqun is not None
    assert to_ref.name_content.fqun.canonical == "mv:authority.com:universe"
    assert to_ref.name_content.path.name == "/dest"


def test_move_dimension_point_with_chained_source():
    program = _parse_and_transform(
        "define the potential action<standard:/path> {\n"
        + "    define the position<run>.\n"
        + "    it happens when {\n"
        + "        the position<run> has a dimension point.\n"
        + "    } and it does {\n"
        + "        move the dimension point in position<src>::action<deposit>::position<inner> to position<dest>.\n"
        + "    }\n"
        + "}\n"
    )
    definition = program.definitions[0]
    assert isinstance(definition, ast.ActionDefinition)
    stmt = definition.action_statements.statements[0]
    assert isinstance(stmt, ast.MoveDimensionPointStatement)
    assert len(stmt.source_position.typed_names) == 3
    assert isinstance(stmt.source_position.typed_names[0], ast.LocalTypedNameReference)
    assert stmt.source_position.typed_names[0].name_content.name == "src"
    assert isinstance(stmt.source_position.typed_names[1], ast.LocalTypedNameReference)
    assert stmt.source_position.typed_names[1].name_type == ast.NameType.ACTION
    assert stmt.source_position.typed_names[1].name_content.name == "deposit"
    assert isinstance(stmt.source_position.typed_names[2], ast.LocalTypedNameReference)
    assert stmt.source_position.typed_names[2].name_content.name == "inner"
    assert len(stmt.target_position.typed_names) == 1
    assert isinstance(stmt.target_position.typed_names[0], ast.LocalTypedNameReference)
    assert stmt.target_position.typed_names[0].name_content.name == "dest"


def test_move_dimension_point_with_chained_destination():
    program = _parse_and_transform(
        "define the potential action<standard:/path> {\n"
        + "    define the position<run>.\n"
        + "    it happens when {\n"
        + "        the position<run> has a dimension point.\n"
        + "    } and it does {\n"
        + "        move the dimension point in position<src> to position<dest>::action<deposit>::position<inner>.\n"
        + "    }\n"
        + "}\n"
    )
    definition = program.definitions[0]
    assert isinstance(definition, ast.ActionDefinition)
    stmt = definition.action_statements.statements[0]
    assert isinstance(stmt, ast.MoveDimensionPointStatement)
    assert len(stmt.source_position.typed_names) == 1
    assert isinstance(stmt.source_position.typed_names[0], ast.LocalTypedNameReference)
    assert stmt.source_position.typed_names[0].name_content.name == "src"
    assert len(stmt.target_position.typed_names) == 3
    assert isinstance(stmt.target_position.typed_names[0], ast.LocalTypedNameReference)
    assert stmt.target_position.typed_names[0].name_content.name == "dest"
    assert isinstance(stmt.target_position.typed_names[1], ast.LocalTypedNameReference)
    assert stmt.target_position.typed_names[1].name_type == ast.NameType.ACTION
    assert stmt.target_position.typed_names[1].name_content.name == "deposit"
    assert isinstance(stmt.target_position.typed_names[2], ast.LocalTypedNameReference)
    assert stmt.target_position.typed_names[2].name_content.name == "inner"


def test_mixed_action_statements_with_move():
    program = _parse_and_transform(
        "define the potential action<standard:/path> {\n"
        + "    define the position<run>.\n"
        + "    it happens when {\n"
        + "        the position<run> has a dimension point.\n"
        + "    } and it does {\n"
        + "        create a dimension point in position<run>.\n"
        + "        move the dimension point in position<source> to position<dest>.\n"
        + "        define the position<inner_pos>.\n"
        + "    }\n"
        + "}\n"
    )
    definition = program.definitions[0]
    assert isinstance(definition, ast.ActionDefinition)
    stmts = definition.action_statements.statements
    assert len(stmts) == 3
    assert isinstance(stmts[0], ast.CreateDimensionPointStatement)
    assert isinstance(stmts[1], ast.MoveDimensionPointStatement)
    assert isinstance(stmts[2], ast.LocalPositionDefinition)


def test_destroy_dimension_point_with_local_position():
    program = _parse_and_transform(
        "define the potential action<standard:/path> {\n"
        + "    define the position<run>.\n"
        + "    it happens when {\n"
        + "        the position<run> has a dimension point.\n"
        + "    } and it does {\n"
        + "        destroy the dimension point in position<run>.\n"
        + "    }\n"
        + "}\n"
    )
    definition = program.definitions[0]
    assert isinstance(definition, ast.ActionDefinition)
    assert len(definition.action_statements.statements) == 1
    stmt = definition.action_statements.statements[0]
    assert isinstance(stmt, ast.DestroyDimensionPointStatement)
    assert len(stmt.target_position.typed_names) == 1
    target_ref = stmt.target_position.typed_names[0]
    assert isinstance(target_ref, ast.LocalTypedNameReference)
    assert target_ref.name_type == ast.NameType.POSITION
    assert target_ref.name_content.name == "run"


def test_destroy_dimension_point_with_short_global_position():
    program = _parse_and_transform(
        "define the potential action<standard:/path> {\n"
        + "    define the position<run>.\n"
        + "    it happens when {\n"
        + "        the position<run> has a dimension point.\n"
        + "    } and it does {\n"
        + "        destroy the dimension point in position</run>.\n"
        + "    }\n"
        + "}\n"
    )
    definition = program.definitions[0]
    assert isinstance(definition, ast.ActionDefinition)
    stmt = definition.action_statements.statements[0]
    assert isinstance(stmt, ast.DestroyDimensionPointStatement)
    target_ref = stmt.target_position.typed_names[0]
    assert isinstance(target_ref, ast.GlobalTypedNameReference)
    assert target_ref.name_type == ast.NameType.POSITION
    assert target_ref.name_content.fqun is None
    assert target_ref.name_content.path.name == "/run"


def test_destroy_dimension_point_with_full_fqun_position():
    program = _parse_and_transform(
        "define the potential action<standard:/path> {\n"
        + "    define the position<run>.\n"
        + "    it happens when {\n"
        + "        the position<run> has a dimension point.\n"
        + "    } and it does {\n"
        + "        destroy the dimension point in position<mv:authority.com:universe:/target>.\n"
        + "    }\n"
        + "}\n"
    )
    definition = program.definitions[0]
    assert isinstance(definition, ast.ActionDefinition)
    stmt = definition.action_statements.statements[0]
    assert isinstance(stmt, ast.DestroyDimensionPointStatement)
    target_ref = stmt.target_position.typed_names[0]
    assert isinstance(target_ref, ast.GlobalTypedNameReference)
    assert target_ref.name_content.fqun is not None
    assert target_ref.name_content.fqun.canonical == "mv:authority.com:universe"
    assert target_ref.name_content.path.name == "/target"


def test_destroy_dimension_point_with_chained_position():
    program = _parse_and_transform(
        "define the potential action<standard:/path> {\n"
        + "    define the position<run>.\n"
        + "    it happens when {\n"
        + "        the position<run> has a dimension point.\n"
        + "    } and it does {\n"
        + "        destroy the dimension point in position<src>::action<deposit>::position<inner>.\n"
        + "    }\n"
        + "}\n"
    )
    definition = program.definitions[0]
    assert isinstance(definition, ast.ActionDefinition)
    stmt = definition.action_statements.statements[0]
    assert isinstance(stmt, ast.DestroyDimensionPointStatement)
    assert len(stmt.target_position.typed_names) == 3
    assert isinstance(stmt.target_position.typed_names[0], ast.LocalTypedNameReference)
    assert stmt.target_position.typed_names[0].name_content.name == "src"
    assert isinstance(stmt.target_position.typed_names[1], ast.LocalTypedNameReference)
    assert stmt.target_position.typed_names[1].name_type == ast.NameType.ACTION
    assert stmt.target_position.typed_names[1].name_content.name == "deposit"
    assert isinstance(stmt.target_position.typed_names[2], ast.LocalTypedNameReference)
    assert stmt.target_position.typed_names[2].name_content.name == "inner"


def test_mixed_action_statements_with_destroy():
    program = _parse_and_transform(
        "define the potential action<standard:/path> {\n"
        + "    define the position<run>.\n"
        + "    it happens when {\n"
        + "        the position<run> has a dimension point.\n"
        + "    } and it does {\n"
        + "        create a dimension point in position<run>.\n"
        + "        destroy the dimension point in position<run>.\n"
        + "        define the position<inner_pos>.\n"
        + "        move the dimension point in position<source> to position<dest>.\n"
        + "    }\n"
        + "}\n"
    )
    definition = program.definitions[0]
    assert isinstance(definition, ast.ActionDefinition)
    stmts = definition.action_statements.statements
    assert len(stmts) == 4
    assert isinstance(stmts[0], ast.CreateDimensionPointStatement)
    assert isinstance(stmts[1], ast.DestroyDimensionPointStatement)
    assert isinstance(stmts[2], ast.LocalPositionDefinition)
    assert isinstance(stmts[3], ast.MoveDimensionPointStatement)


def test_action_definition_block_with_constrained_interface_position():
    program = _parse_and_transform(
        "define the potential action<standard:/path> {\n"
        + "    define the position<my_pos> {\n"
        + "        it may only contain dimension points where {\n"
        + "            it has the action</child>.\n"
        + "        }\n"
        + "    }\n"
        + "    it happens when {\n"
        + "        the position<my_pos> has a dimension point.\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    )
    definition = program.definitions[0]
    assert isinstance(definition, ast.ActionDefinition)
    local_def = definition.interface_positions[0]
    assert local_def.constraints is not None
    assert len(local_def.constraints.requirements) == 1
    requirement = local_def.constraints.requirements[0]
    assert requirement.typed_global_name.name_type == ast.NameType.ACTION
    assert requirement.typed_global_name.name_content.path.relative_path == Path(
        "child"
    )
    assert local_def.location.line == 2
    assert local_def.constraints.location.line == 3
    assert requirement.location.line == 4


def test_trigger_condition_statement_transforms_local_position():
    program = _parse_and_transform(
        "define the potential action<standard:/path> {\n"
        + "    define the position<run>.\n"
        + "    it happens when {\n"
        + "        the position<run> has a dimension point.\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    )
    definition = program.definitions[0]
    assert isinstance(definition, ast.ActionDefinition)
    assert len(definition.trigger_conditions.conditions) == 1
    condition = definition.trigger_conditions.conditions[0]
    assert isinstance(condition, ast.TriggerConditionStatement)
    assert isinstance(condition.typed_name, ast.LocalTypedNameReference)
    assert condition.typed_name.name_type == ast.NameType.POSITION
    assert condition.typed_name.name_content.name == "run"


def test_trigger_condition_statement_source_positions():
    program = _parse_and_transform(
        "define the potential action<standard:/path> {\n"
        + "    define the position<run>.\n"
        + "    it happens when {\n"
        + "        the position<run> has a dimension point.\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    )
    definition = program.definitions[0]
    assert isinstance(definition, ast.ActionDefinition)
    assert len(definition.trigger_conditions.conditions) == 1
    condition = definition.trigger_conditions.conditions[0]
    assert condition.location.line == 4
    assert condition.location.column == 9


def test_position_definition_with_init_block_only():
    program = _parse_and_transform(
        "define the potential position<standard:/path> {\n"
        + "    after it is assigned {\n"
        + "        create a dimension point in position</other>.\n"
        + "    }\n"
        + "}\n"
    )
    definition = program.definitions[0]
    assert isinstance(definition, ast.PositionDefinition)
    assert definition.constraints is None
    assert definition.initialization is not None
    assert len(definition.initialization.statements) == 1
    stmt = definition.initialization.statements[0]
    assert isinstance(stmt, ast.CreateDimensionPointStatement)


def test_position_definition_with_constraints_and_init_block():
    program = _parse_and_transform(
        "define the potential position<standard:/path> {\n"
        + "    it may only contain dimension points where {\n"
        + "        it has the position</child>.\n"
        + "    }\n"
        + "    after it is assigned {\n"
        + "        create a dimension point in position</other>.\n"
        + "    }\n"
        + "}\n"
    )
    definition = program.definitions[0]
    assert isinstance(definition, ast.PositionDefinition)
    assert definition.constraints is not None
    assert len(definition.constraints.requirements) == 1
    assert definition.initialization is not None
    assert len(definition.initialization.statements) == 1
    stmt = definition.initialization.statements[0]
    assert isinstance(stmt, ast.CreateDimensionPointStatement)


def test_init_block_with_create_statement():
    program = _parse_and_transform(
        "define the potential position<standard:/path> {\n"
        + "    after it is assigned {\n"
        + "        create a dimension point in position</other>.\n"
        + "    }\n"
        + "}\n"
    )
    definition = program.definitions[0]
    assert isinstance(definition, ast.PositionDefinition)
    assert definition.initialization is not None
    stmt = definition.initialization.statements[0]
    assert isinstance(stmt, ast.CreateDimensionPointStatement)
    ref = stmt.target_position.typed_names[0]
    assert isinstance(ref, ast.GlobalTypedNameReference)
    assert ref.name_content.path.name == "/other"


def test_init_block_with_move_statement():
    program = _parse_and_transform(
        "define the potential position<standard:/path> {\n"
        + "    after it is assigned {\n"
        + "        move the dimension point in position</source> to position</dest>.\n"
        + "    }\n"
        + "}\n"
    )
    definition = program.definitions[0]
    assert isinstance(definition, ast.PositionDefinition)
    assert definition.initialization is not None
    stmt = definition.initialization.statements[0]
    assert isinstance(stmt, ast.MoveDimensionPointStatement)
    from_ref = stmt.source_position.typed_names[0]
    assert isinstance(from_ref, ast.GlobalTypedNameReference)
    assert from_ref.name_content.path.name == "/source"
    to_ref = stmt.target_position.typed_names[0]
    assert isinstance(to_ref, ast.GlobalTypedNameReference)
    assert to_ref.name_content.path.name == "/dest"


def test_init_block_with_local_position_definition():
    program = _parse_and_transform(
        "define the potential position<standard:/path> {\n"
        + "    after it is assigned {\n"
        + "        define the position<inner>.\n"
        + "    }\n"
        + "}\n"
    )
    definition = program.definitions[0]
    assert isinstance(definition, ast.PositionDefinition)
    assert definition.initialization is not None
    stmt = definition.initialization.statements[0]
    assert isinstance(stmt, ast.LocalPositionDefinition)
    assert stmt.typed_name.name_content.name == "inner"


def test_init_block_with_multiple_statements():
    program = _parse_and_transform(
        "define the potential position<standard:/path> {\n"
        + "    after it is assigned {\n"
        + "        create a dimension point in position</path>.\n"
        + "        move the dimension point in position</source> to position</dest>.\n"
        + "        define the position<inner>.\n"
        + "    }\n"
        + "}\n"
    )
    definition = program.definitions[0]
    assert isinstance(definition, ast.PositionDefinition)
    assert definition.initialization is not None
    stmts = definition.initialization.statements
    assert len(stmts) == 3
    assert isinstance(stmts[0], ast.CreateDimensionPointStatement)
    assert isinstance(stmts[1], ast.MoveDimensionPointStatement)
    assert isinstance(stmts[2], ast.LocalPositionDefinition)


def test_empty_init_block():
    program = _parse_and_transform(
        "define the potential position<standard:/path> {\n"
        + "    after it is assigned {\n"
        + "    }\n"
        + "}\n"
    )
    definition = program.definitions[0]
    assert isinstance(definition, ast.PositionDefinition)
    assert definition.initialization is not None
    assert definition.initialization.statements == []


def test_init_block_source_positions():
    program = _parse_and_transform(
        "define the potential position<standard:/path> {\n"
        + "    after it is assigned {\n"
        + "        create a dimension point in position</other>.\n"
        + "    }\n"
        + "}\n"
    )
    definition = program.definitions[0]
    assert isinstance(definition, ast.PositionDefinition)
    assert definition.initialization is not None
    assert definition.initialization.location.line == 2
    stmt = definition.initialization.statements[0]
    assert isinstance(stmt, ast.CreateDimensionPointStatement)
    assert stmt.location.line == 3
    assert stmt.location.column == 9


def test_position_definition_quality_implications_default_empty():
    program = _parse_and_transform("define the potential position<standard:/path>.\n")
    definition = program.definitions[0]
    assert isinstance(definition, ast.PositionDefinition)
    assert definition.quality_implications == []


def test_position_definition_with_quality_implications():
    program = _parse_and_transform(
        "define the potential position<standard:/path> {\n"
        + "    it also assigns the position</a>.\n"
        + "    it also assigns the action</b>.\n"
        + "    it may only contain dimension points where {\n"
        + "        it has the position</child>.\n"
        + "    }\n"
        + "}\n"
    )
    definition = program.definitions[0]
    assert isinstance(definition, ast.PositionDefinition)
    assert len(definition.quality_implications) == 2
    first = definition.quality_implications[0]
    second = definition.quality_implications[1]
    assert isinstance(first, ast.QualityImplicationStatement)
    assert isinstance(second, ast.QualityImplicationStatement)
    assert first.typed_global_name.name_type == ast.NameType.POSITION
    assert first.typed_global_name.name_content.path.relative_path == Path("a")
    assert second.typed_global_name.name_type == ast.NameType.ACTION
    assert second.typed_global_name.name_content.path.relative_path == Path("b")
    assert first.location.line == 2
    assert second.location.line == 3
    assert definition.constraints is not None
    assert len(definition.constraints.requirements) == 1


def test_position_definition_with_quality_implications_and_init_block():
    program = _parse_and_transform(
        "define the potential position<standard:/path> {\n"
        + "    it also assigns the position</a>.\n"
        + "    after it is assigned {\n"
        + "        create a dimension point in position</other>.\n"
        + "    }\n"
        + "}\n"
    )
    definition = program.definitions[0]
    assert isinstance(definition, ast.PositionDefinition)
    assert len(definition.quality_implications) == 1
    assert definition.constraints is None
    assert definition.initialization is not None


def test_action_definition_quality_implications_default_empty():
    program = _parse_and_transform(
        "define the potential action<standard:/path> {\n"
        + "    define the position<_noop>.\n"
        + "    it happens when {\n"
        + "        the position<_noop> has a dimension point.\n"
        + "    } and it does {\n"
        + "        define the position<__noop>.\n"
        + "        create a dimension point in position<__noop>.\n"
        + "    }\n"
        + "}\n"
    )
    definition = program.definitions[0]
    assert isinstance(definition, ast.ActionDefinition)
    assert definition.quality_implications == []


def test_action_definition_with_quality_implications():
    program = _parse_and_transform(
        "define the potential action<standard:/path> {\n"
        + "    it also assigns the position</a>.\n"
        + "    it also assigns the action</b>.\n"
        + "    define the position<run>.\n"
        + "    it happens when {\n"
        + "        the position<run> has a dimension point.\n"
        + "    } and it does {\n"
        + "        create a dimension point in position<run>.\n"
        + "    }\n"
        + "}\n"
    )
    definition = program.definitions[0]
    assert isinstance(definition, ast.ActionDefinition)
    assert len(definition.quality_implications) == 2
    first = definition.quality_implications[0]
    second = definition.quality_implications[1]
    assert isinstance(first, ast.QualityImplicationStatement)
    assert isinstance(second, ast.QualityImplicationStatement)
    assert first.typed_global_name.name_type == ast.NameType.POSITION
    assert first.typed_global_name.name_content.path.relative_path == Path("a")
    assert second.typed_global_name.name_type == ast.NameType.ACTION
    assert second.typed_global_name.name_content.path.relative_path == Path("b")
    assert first.location.line == 2
    assert second.location.line == 3
    assert len(definition.interface_positions) == 1
    assert definition.interface_positions[0].typed_name.name_content.name == "run"
    assert len(definition.trigger_conditions.conditions) == 1
    assert len(definition.action_statements.statements) == 1


def test_enclosing_fqun_set_on_global_reference():
    program = _parse_and_transform(
        "define the potential position<standard:/path> {\n"
        + "    it may only contain dimension points where {\n"
        + "        it has the position</child>.\n"
        + "    }\n"
        + "}\n"
    )
    definition = program.definitions[0]
    assert isinstance(definition, ast.PositionDefinition)
    assert definition.constraints is not None
    requirement = definition.constraints.requirements[0]
    assert (
        requirement.typed_global_name.enclosing_fqun.canonical
        == definition.typed_name.name_content.fqun.canonical
    )


def test_enclosing_fqun_dispatched_per_definition():
    program = _parse_and_transform(
        "define the potential position<my_mv:example.com:lib_a:/pos_a> {\n"
        + "    it may only contain dimension points where {\n"
        + "        it has the position</child>.\n"
        + "    }\n"
        + "}\n"
        + "define the potential position<my_mv:example.com:lib_b:/pos_b> {\n"
        + "    it may only contain dimension points where {\n"
        + "        it has the position</other>.\n"
        + "    }\n"
        + "}\n"
    )
    assert len(program.definitions) == 2
    first = program.definitions[0]
    second = program.definitions[1]
    assert isinstance(first, ast.PositionDefinition)
    assert isinstance(second, ast.PositionDefinition)
    assert first.constraints is not None
    assert second.constraints is not None
    first_ref = first.constraints.requirements[0].typed_global_name
    second_ref = second.constraints.requirements[0].typed_global_name
    assert first_ref.enclosing_fqun.canonical == "my_mv:example.com:lib_a"
    assert second_ref.enclosing_fqun.canonical == "my_mv:example.com:lib_b"


def test_enclosing_fqun_independent_of_reference_own_fqun():
    program = _parse_and_transform(
        "define the potential position<standard:/path> {\n"
        + "    it may only contain dimension points where {\n"
        + "        it has the position<other.com:other_lib:/elsewhere>.\n"
        + "    }\n"
        + "}\n"
    )
    definition = program.definitions[0]
    assert isinstance(definition, ast.PositionDefinition)
    assert definition.constraints is not None
    typed_ref = definition.constraints.requirements[0].typed_global_name
    assert typed_ref.name_content.fqun is not None
    assert typed_ref.name_content.fqun.canonical == "other.com:other_lib"
    assert typed_ref.enclosing_fqun.canonical == "standard"


def test_enclosing_fqun_on_every_segment_of_chained_reference():
    program = _parse_and_transform(
        "define the potential action<standard:/path> {\n"
        + "    define the position<run>.\n"
        + "    it happens when {\n"
        + "        the position<run> has a dimension point.\n"
        + "    } and it does {\n"
        + "        create a dimension point in position</a>::action</b>::position</c>.\n"
        + "    }\n"
        + "}\n"
    )
    definition = program.definitions[0]
    assert isinstance(definition, ast.ActionDefinition)
    stmt = definition.action_statements.statements[0]
    assert isinstance(stmt, ast.CreateDimensionPointStatement)
    expected = definition.typed_name.name_content.fqun.canonical
    chain = stmt.target_position.typed_names
    assert len(chain) == 3
    for segment in chain:
        assert isinstance(segment, ast.GlobalTypedNameReference)
        assert segment.enclosing_fqun.canonical == expected
