"""Tests for the Define AST transformer."""

from define.compiler import ast, parser
from define.compiler.transformer import DefineTransformer

_parser = parser.Parser()


def _parse_and_transform(source: str) -> ast.Program:
    tree = _parser.parse(source)
    transformer = DefineTransformer()
    return transformer.transform(tree)


def test_position_definition_transforms_to_program():
    program = _parse_and_transform("define the potential position<standard:/path>.\n")
    assert isinstance(program, ast.Program)
    assert program.position.line == 1
    assert program.position.column == 1
    assert len(program.definitions) == 1
    definition = program.definitions[0]
    assert isinstance(definition, ast.PositionDefinition)
    assert definition.position.line == 1
    assert definition.position.column == 1
    assert definition.name.fqun.universe.name == "standard"
    assert definition.name.fqun.universe.position.line == 1
    assert definition.name.fqun.universe.position.column == 31
    assert definition.name.path == ["path"]
    assert definition.name.position.line == 1
    assert definition.name.position.column == 31


def test_action_definition_transforms_to_program():
    program = _parse_and_transform("define the potential action<standard:/path>.\n")
    assert isinstance(program, ast.Program)
    assert len(program.definitions) == 1
    definition = program.definitions[0]
    assert isinstance(definition, ast.ActionDefinition)
    assert definition.position.line == 1
    assert definition.name.fqun.universe.name == "standard"
    assert definition.name.path == ["path"]


def test_global_name_full_fqun():
    program = _parse_and_transform(
        "define the potential position<my_mv:example.com/org/repo:my_lib:/some/path>.\n"
    )
    name = program.definitions[0].name
    assert name.fqun.multiverse is not None
    assert name.fqun.multiverse.name == "my_mv"
    assert name.fqun.multiverse.position.line == 1
    assert name.fqun.multiverse.position.column == 31
    assert name.fqun.universe.name == "my_lib"
    assert name.fqun.universe.position.line == 1
    assert name.fqun.universe.position.column == 58
    assert name.path == ["some", "path"]
    assert name.fqun.authority is not None
    assert name.fqun.authority.domain == "example.com"
    assert name.fqun.authority.path == ["org", "repo"]
    assert name.fqun.authority.position.line == 1
    assert name.fqun.authority.position.column == 37


def test_global_name_authority_universe():
    program = _parse_and_transform(
        "define the potential position<example.com:my_lib:/some/path>.\n"
    )
    name = program.definitions[0].name
    assert name.fqun.multiverse is None
    assert name.fqun.universe.name == "my_lib"
    assert name.fqun.universe.position.line == 1
    assert name.fqun.universe.position.column == 43
    assert name.path == ["some", "path"]
    assert name.fqun.authority is not None
    assert name.fqun.authority.domain == "example.com"
    assert name.fqun.authority.path == []
    assert name.fqun.authority.position.line == 1


def test_global_name_universe_only():
    program = _parse_and_transform(
        "define the potential position<standard:/some/path>.\n"
    )
    name = program.definitions[0].name
    assert name.fqun.multiverse is None
    assert name.fqun.authority is None
    assert name.fqun.universe.name == "standard"
    assert name.fqun.universe.position.line == 1
    assert name.fqun.universe.position.column == 31
    assert name.fqun.position.line == 1
    assert name.fqun.position.column == 31
    assert name.path == ["some", "path"]


def test_multiple_definitions_position_and_action():
    program = _parse_and_transform(
        "define the potential position<standard:/pos>.\n"
        + "define the potential action<standard:/act>.\n"
    )
    assert len(program.definitions) == 2
    assert isinstance(program.definitions[0], ast.PositionDefinition)
    assert isinstance(program.definitions[1], ast.ActionDefinition)
    assert program.definitions[0].name.path == ["pos"]
    assert program.definitions[1].name.path == ["act"]
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
    assert definition.definition_block.action_statements is not None


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
