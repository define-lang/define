"""Tests for the Define AST transformer."""

from compiler import ast, parser
from compiler.transformer import DefineTransformer

_parser = parser.Parser()


def _parse_and_transform(source: str) -> ast.Program:
    tree = _parser.parse(source)
    transformer = DefineTransformer()
    return transformer.transform(tree)


def test_position_definition_transforms_to_program():
    program = _parse_and_transform("define the potential position<standard:/path>.\n")
    assert isinstance(program, ast.Program)
    assert len(program.definitions) == 1
    definition = program.definitions[0]
    assert isinstance(definition, ast.PositionDefinition)
    assert definition.name.fqun.universe == "standard"
    assert definition.name.path == ["path"]


def test_action_definition_transforms_to_program():
    program = _parse_and_transform("define the potential action<standard:/path>.\n")
    assert isinstance(program, ast.Program)
    assert len(program.definitions) == 1
    definition = program.definitions[0]
    assert isinstance(definition, ast.ActionDefinition)
    assert definition.name.fqun.universe == "standard"
    assert definition.name.path == ["path"]


def test_global_name_full_fqun():
    program = _parse_and_transform(
        "define the potential position<my_mv:example.com/org/repo:my_lib:/some/path>.\n"
    )
    name = program.definitions[0].name
    assert name.fqun.multiverse == "my_mv"
    assert name.fqun.universe == "my_lib"
    assert name.path == ["some", "path"]
    assert name.fqun.authority is not None
    assert name.fqun.authority.domain == "example.com"
    assert name.fqun.authority.path == ["org", "repo"]


def test_global_name_authority_universe():
    program = _parse_and_transform(
        "define the potential position<example.com:my_lib:/some/path>.\n"
    )
    name = program.definitions[0].name
    assert name.fqun.multiverse is None
    assert name.fqun.universe == "my_lib"
    assert name.path == ["some", "path"]
    assert name.fqun.authority is not None
    assert name.fqun.authority.domain == "example.com"
    assert name.fqun.authority.path == []


def test_global_name_universe_only():
    program = _parse_and_transform(
        "define the potential position<standard:/some/path>.\n"
    )
    name = program.definitions[0].name
    assert name.fqun.multiverse is None
    assert name.fqun.authority is None
    assert name.fqun.universe == "standard"
    assert name.path == ["some", "path"]
