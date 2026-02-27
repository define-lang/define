"""Tests for the Define AST transformer."""

from pathlib import Path

from define.compiler import ast, parser
from define.compiler.transformer import DefineTransformer

_parser = parser.Parser()


def _parse_and_transform(source: str) -> ast.Program:
    tree = _parser.parse(source)
    return DefineTransformer().transform(tree)


def _require_fqun(name: ast.GlobalNameContent) -> ast.Fqun:
    assert name.fqun is not None
    return name.fqun


def test_position_definition_transforms_to_program():
    program = _parse_and_transform("define the potential position<standard:/path>.\n")
    assert isinstance(program, ast.Program)
    assert program.position.line == 1
    assert program.position.column == 1
    assert len(program.definitions) == 1
    definition = program.definitions[0]
    assert isinstance(definition, ast.PositionDefinition)
    fqun = _require_fqun(definition.name)
    assert definition.position.line == 1
    assert definition.position.column == 1
    assert fqun.universe.name == "standard"
    assert fqun.universe.position.line == 1
    assert fqun.universe.position.column == 31
    assert definition.name.path.relative_path == Path("path")
    assert definition.name.path.name == "/path"
    assert definition.name.path.position.line == 1
    assert definition.name.path.position.column == 40
    assert definition.name.position.line == 1
    assert definition.name.position.column == 31


def test_action_definition_transforms_to_program():
    program = _parse_and_transform("define the potential action<standard:/path>.\n")
    assert isinstance(program, ast.Program)
    assert len(program.definitions) == 1
    definition = program.definitions[0]
    assert isinstance(definition, ast.ActionDefinition)
    fqun = _require_fqun(definition.name)
    assert definition.position.line == 1
    assert fqun.universe.name == "standard"
    assert definition.name.path.relative_path == Path("path")


def test_global_name_full_fqun():
    program = _parse_and_transform(
        "define the potential position<my_mv:example.com:my_lib:/some/path>.\n"
    )
    name = program.definitions[0].name
    fqun = _require_fqun(name)
    assert fqun.multiverse is not None
    assert fqun.multiverse.name == "my_mv"
    assert fqun.multiverse.position.line == 1
    assert fqun.multiverse.position.column == 31
    assert fqun.universe.name == "my_lib"
    assert fqun.universe.position.line == 1
    assert fqun.universe.position.column == 49
    assert name.path.relative_path == Path("some/path")
    assert fqun.authority is not None
    assert fqun.authority.name == "example.com"
    assert fqun.authority.position.line == 1
    assert fqun.authority.position.column == 37


def test_global_name_authority_universe():
    program = _parse_and_transform(
        "define the potential position<example.com:my_lib:/some/path>.\n"
    )
    name = program.definitions[0].name
    fqun = _require_fqun(name)
    assert fqun.multiverse is None
    assert fqun.universe.name == "my_lib"
    assert fqun.universe.position.line == 1
    assert fqun.universe.position.column == 43
    assert name.path.relative_path == Path("some/path")
    assert fqun.authority is not None
    assert fqun.authority.name == "example.com"
    assert fqun.authority.position.line == 1


def test_global_name_authority_with_path_universe():
    program = _parse_and_transform(
        "define the potential position<example.com/org/repo:my_lib:/some/path>.\n"
    )
    name = program.definitions[0].name
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
    name = program.definitions[0].name
    fqun = _require_fqun(name)
    assert fqun.multiverse is None
    assert fqun.authority is None
    assert fqun.universe.name == "standard"
    assert fqun.universe.position.line == 1
    assert fqun.universe.position.column == 31
    assert fqun.position.line == 1
    assert fqun.position.column == 31
    assert name.path.relative_path == Path("some/path")


def test_multiple_definitions_position_and_action():
    program = _parse_and_transform(
        "define the potential position<standard:/pos>.\n"
        + "define the potential action<standard:/act>.\n"
    )
    assert len(program.definitions) == 2
    assert isinstance(program.definitions[0], ast.PositionDefinition)
    assert isinstance(program.definitions[1], ast.ActionDefinition)
    assert program.definitions[0].name.path.relative_path == Path("pos")
    assert program.definitions[1].name.path.relative_path == Path("act")
    assert program.definitions[0].position.line == 1
    assert program.definitions[1].position.line == 2


def test_action_definition_terminator_has_no_block():
    program = _parse_and_transform("define the potential action<standard:/path>.\n")
    definition = program.definitions[0]
    assert isinstance(definition, ast.ActionDefinition)
    assert definition.definition_block is None


def test_action_definition_block_transforms():
    program = _parse_and_transform(
        "define the potential action<standard:/path> {\n"
        + "    it happens when {\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    )
    definition = program.definitions[0]
    assert isinstance(definition, ast.ActionDefinition)
    assert definition.definition_block is not None
    assert definition.definition_block.local_definitions == []
    assert definition.definition_block.trigger_conditions is not None
    assert definition.definition_block.action_statements.statements == []


def test_action_definition_block_with_local_definition():
    program = _parse_and_transform(
        "define the potential action<standard:/path> {\n"
        + "    define the position<my_pos>.\n"
        + "    it happens when {\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    )
    definition = program.definitions[0]
    assert isinstance(definition, ast.ActionDefinition)
    assert definition.definition_block is not None
    assert len(definition.definition_block.local_definitions) == 1
    assert definition.definition_block.local_definitions[0].local_name.name == "my_pos"


def test_action_definition_block_with_multiple_local_definitions():
    program = _parse_and_transform(
        "define the potential action<standard:/path> {\n"
        + "    define the position<first_pos>.\n"
        + "    define the position<second_pos>.\n"
        + "    it happens when {\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    )
    definition = program.definitions[0]
    assert isinstance(definition, ast.ActionDefinition)
    assert definition.definition_block is not None
    assert len(definition.definition_block.local_definitions) == 2
    assert (
        definition.definition_block.local_definitions[0].local_name.name == "first_pos"
    )
    assert (
        definition.definition_block.local_definitions[1].local_name.name == "second_pos"
    )


def test_action_definition_block_source_positions():
    program = _parse_and_transform(
        "define the potential action<standard:/path> {\n"
        + "    it happens when {\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    )
    definition = program.definitions[0]
    assert isinstance(definition, ast.ActionDefinition)
    block = definition.definition_block
    assert block is not None
    assert block.position.line == 1
    assert block.trigger_conditions.position.line == 2
    assert block.action_statements.position.line == 3
    assert block.action_statements.statements == []


def test_action_definition_block_local_definition_source_position():
    program = _parse_and_transform(
        "define the potential action<standard:/path> {\n"
        + "    define the position<my_pos>.\n"
        + "    it happens when {\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    )
    definition = program.definitions[0]
    assert isinstance(definition, ast.ActionDefinition)
    block = definition.definition_block
    assert block is not None
    local_def = block.local_definitions[0]
    assert local_def.position.line == 2
    assert local_def.position.column == 5


def test_action_definition_block_with_action_statement_local_definition():
    program = _parse_and_transform(
        "define the potential action<standard:/path> {\n"
        + "    it happens when {\n"
        + "    } and it does {\n"
        + "        define the position<inner_pos>.\n"
        + "    }\n"
        + "}\n"
    )
    definition = program.definitions[0]
    assert isinstance(definition, ast.ActionDefinition)
    block = definition.definition_block
    assert block is not None
    assert len(block.action_statements.statements) == 1
    local_def = block.action_statements.statements[0]
    assert isinstance(local_def, ast.LocalPositionDefinition)
    assert local_def.local_name.name == "inner_pos"
    assert local_def.position.line == 4
    assert local_def.position.column == 9


def test_action_definition_block_with_multiple_action_statement_local_definitions():
    program = _parse_and_transform(
        "define the potential action<standard:/path> {\n"
        + "    it happens when {\n"
        + "    } and it does {\n"
        + "        define the position<first_inner>.\n"
        + "        define the position<second_inner>.\n"
        + "    }\n"
        + "}\n"
    )
    definition = program.definitions[0]
    assert isinstance(definition, ast.ActionDefinition)
    block = definition.definition_block
    assert block is not None
    assert len(block.action_statements.statements) == 2
    first_local_def = block.action_statements.statements[0]
    second_local_def = block.action_statements.statements[1]
    assert isinstance(first_local_def, ast.LocalPositionDefinition)
    assert isinstance(second_local_def, ast.LocalPositionDefinition)
    assert first_local_def.local_name.name == "first_inner"
    assert second_local_def.local_name.name == "second_inner"
    assert first_local_def.position.line == 4
    assert second_local_def.position.line == 5


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
    assert first_requirement.typed_global_name.type_name == ast.TypeName.POSITION
    assert second_requirement.typed_global_name.type_name == ast.TypeName.ACTION
    assert first_requirement.typed_global_name.name_content.fqun is None
    assert first_requirement.typed_global_name.name_content.path.relative_path == Path(
        "child"
    )
    assert second_requirement.typed_global_name.name_content.path.relative_path == Path(
        "other"
    )
    assert definition.constraints.position.line == 2
    assert first_requirement.position.line == 3
    assert second_requirement.position.line == 4


def test_create_dimension_point_with_local_position():
    program = _parse_and_transform(
        "define the potential action<standard:/path> {\n"
        + "    it happens when {\n"
        + "    } and it does {\n"
        + "        create a dimension point in position<run>.\n"
        + "    }\n"
        + "}\n"
    )
    definition = program.definitions[0]
    assert isinstance(definition, ast.ActionDefinition)
    block = definition.definition_block
    assert block is not None
    assert len(block.action_statements.statements) == 1
    stmt = block.action_statements.statements[0]
    assert isinstance(stmt, ast.CreateDimensionPointStatement)
    assert len(stmt.position_reference.chain) == 1
    ref = stmt.position_reference.chain[0]
    assert isinstance(ref, ast.TypedLocalNameReference)
    assert ref.type_name == ast.TypeName.POSITION
    assert ref.name_content.name == "run"


def test_create_dimension_point_with_short_global_position():
    program = _parse_and_transform(
        "define the potential action<standard:/path> {\n"
        + "    it happens when {\n"
        + "    } and it does {\n"
        + "        create a dimension point in position</run>.\n"
        + "    }\n"
        + "}\n"
    )
    definition = program.definitions[0]
    assert isinstance(definition, ast.ActionDefinition)
    block = definition.definition_block
    assert block is not None
    stmt = block.action_statements.statements[0]
    assert isinstance(stmt, ast.CreateDimensionPointStatement)
    ref = stmt.position_reference.chain[0]
    assert isinstance(ref, ast.TypedGlobalNameReference)
    assert ref.type_name == ast.TypeName.POSITION
    assert ref.name_content.fqun is None
    assert ref.name_content.path.name == "/run"


def test_create_dimension_point_with_full_fqun_position():
    program = _parse_and_transform(
        "define the potential action<standard:/path> {\n"
        + "    it happens when {\n"
        + "    } and it does {\n"
        + "        create a dimension point in position<mv:define-lang.org:parser:/run>.\n"
        + "    }\n"
        + "}\n"
    )
    definition = program.definitions[0]
    assert isinstance(definition, ast.ActionDefinition)
    block = definition.definition_block
    assert block is not None
    stmt = block.action_statements.statements[0]
    assert isinstance(stmt, ast.CreateDimensionPointStatement)
    ref = stmt.position_reference.chain[0]
    assert isinstance(ref, ast.TypedGlobalNameReference)
    assert ref.type_name == ast.TypeName.POSITION
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
        + "    it happens when {\n"
        + "    } and it does {\n"
        + "        create a dimension point in position<to>::action<deposit>::position<run>.\n"
        + "    }\n"
        + "}\n"
    )
    definition = program.definitions[0]
    assert isinstance(definition, ast.ActionDefinition)
    block = definition.definition_block
    assert block is not None
    stmt = block.action_statements.statements[0]
    assert isinstance(stmt, ast.CreateDimensionPointStatement)
    chain = stmt.position_reference.chain
    assert len(chain) == 3
    assert isinstance(chain[0], ast.TypedLocalNameReference)
    assert chain[0].type_name == ast.TypeName.POSITION
    assert chain[0].name_content.name == "to"
    assert isinstance(chain[1], ast.TypedLocalNameReference)
    assert chain[1].type_name == ast.TypeName.ACTION
    assert chain[1].name_content.name == "deposit"
    assert isinstance(chain[2], ast.TypedLocalNameReference)
    assert chain[2].type_name == ast.TypeName.POSITION
    assert chain[2].name_content.name == "run"


def test_chained_position_reference_with_global_names():
    program = _parse_and_transform(
        "define the potential action<standard:/path> {\n"
        + "    it happens when {\n"
        + "    } and it does {\n"
        + "        create a dimension point in position</to>::action</deposit>::position</run>.\n"
        + "    }\n"
        + "}\n"
    )
    definition = program.definitions[0]
    assert isinstance(definition, ast.ActionDefinition)
    block = definition.definition_block
    assert block is not None
    stmt = block.action_statements.statements[0]
    assert isinstance(stmt, ast.CreateDimensionPointStatement)
    chain = stmt.position_reference.chain
    assert len(chain) == 3
    assert isinstance(chain[0], ast.TypedGlobalNameReference)
    assert chain[0].name_content.path.name == "/to"
    assert isinstance(chain[1], ast.TypedGlobalNameReference)
    assert chain[1].name_content.path.name == "/deposit"
    assert isinstance(chain[2], ast.TypedGlobalNameReference)
    assert chain[2].name_content.path.name == "/run"


def test_chained_position_reference_mixed_types():
    program = _parse_and_transform(
        "define the potential action<standard:/path> {\n"
        + "    it happens when {\n"
        + "    } and it does {\n"
        + "        create a dimension point in action</start>::position<mid>::action</end>.\n"
        + "    }\n"
        + "}\n"
    )
    definition = program.definitions[0]
    assert isinstance(definition, ast.ActionDefinition)
    block = definition.definition_block
    assert block is not None
    stmt = block.action_statements.statements[0]
    assert isinstance(stmt, ast.CreateDimensionPointStatement)
    chain = stmt.position_reference.chain
    assert len(chain) == 3
    assert isinstance(chain[0], ast.TypedGlobalNameReference)
    assert chain[0].type_name == ast.TypeName.ACTION
    assert chain[0].name_content.path.name == "/start"
    assert isinstance(chain[1], ast.TypedLocalNameReference)
    assert chain[1].type_name == ast.TypeName.POSITION
    assert chain[1].name_content.name == "mid"
    assert isinstance(chain[2], ast.TypedGlobalNameReference)
    assert chain[2].type_name == ast.TypeName.ACTION
    assert chain[2].name_content.path.name == "/end"


def test_mixed_action_statements():
    program = _parse_and_transform(
        "define the potential action<standard:/path> {\n"
        + "    it happens when {\n"
        + "    } and it does {\n"
        + "        define the position<inner_pos>.\n"
        + "        create a dimension point in position<run>.\n"
        + "        create a dimension point in position</other>.\n"
        + "    }\n"
        + "}\n"
    )
    definition = program.definitions[0]
    assert isinstance(definition, ast.ActionDefinition)
    block = definition.definition_block
    assert block is not None
    stmts = block.action_statements.statements
    assert len(stmts) == 3
    assert isinstance(stmts[0], ast.LocalPositionDefinition)
    assert stmts[0].local_name.name == "inner_pos"
    assert isinstance(stmts[1], ast.CreateDimensionPointStatement)
    assert isinstance(stmts[2], ast.CreateDimensionPointStatement)


def test_action_definition_block_with_constrained_local_definition():
    program = _parse_and_transform(
        "define the potential action<standard:/path> {\n"
        + "    define the position<my_pos> {\n"
        + "        it may only contain dimension points where {\n"
        + "            it has the action</child>.\n"
        + "        }\n"
        + "    }\n"
        + "    it happens when {\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    )
    definition = program.definitions[0]
    assert isinstance(definition, ast.ActionDefinition)
    block = definition.definition_block
    assert block is not None
    local_def = block.local_definitions[0]
    assert local_def.constraints is not None
    assert len(local_def.constraints.requirements) == 1
    requirement = local_def.constraints.requirements[0]
    assert requirement.typed_global_name.type_name == ast.TypeName.ACTION
    assert requirement.typed_global_name.name_content.path.relative_path == Path(
        "child"
    )
    assert local_def.position.line == 2
    assert local_def.constraints.position.line == 3
    assert requirement.position.line == 4
