import textwrap

from compiler.prototype import ast
from compiler.prototype.parser import Parser
from compiler.prototype.transformer import DefineTransformer

# Shared parser instance to avoid rebuilding the Lark parser for each test
_parser = Parser()


def _strip(text: str) -> str:
    return textwrap.dedent(text).lstrip("\n")


def _parse_and_transform(source: str) -> ast.Program:
    """Parse source and transform to AST."""
    tree = _parser.parse(source)
    transformer = DefineTransformer()
    return transformer.transform(tree)


# Basic Transformations


def test_start_transforms_to_program():
    source = _strip(
        """
        AbstractUniverse:
            Foo is a Bar.
        """
    )
    program = _parse_and_transform(source)
    assert isinstance(program, ast.Program)
    assert len(program.universes) == 1


def test_universe_section_transforms_to_universe_block():
    source = _strip(
        """
        AbstractUniverse:
            Foo is a Bar.
        """
    )
    program = _parse_and_transform(source)
    assert len(program.universes) == 1
    universe = program.universes[0]
    assert universe.name == "AbstractUniverse"
    assert len(universe.statements) == 1


def test_compiler_type_declaration():
    source = _strip(
        """
        AbstractUniverse:
            Number is.
        """
    )
    program = _parse_and_transform(source)
    universe = program.get_abstract_universe()
    assert len(universe.statements) == 1
    decl = universe.statements[0]
    assert isinstance(decl, ast.CompilerTypeDeclaration)
    assert decl.type_name == "Number"


def test_type_declaration():
    source = _strip(
        """
        AbstractUniverse:
            Foo is a Bar.
        """
    )
    program = _parse_and_transform(source)
    universe = program.get_abstract_universe()
    statements = universe.get_statements_by_type(ast.TypeDeclaration)
    assert len(statements) == 1
    decl = statements[0]
    assert decl.type_name == "Foo"
    assert decl.parent_type == "Bar"


def test_property_declaration():
    source = _strip(
        """
        AbstractUniverse:
            Foo has a Bar named baz.
        """
    )
    program = _parse_and_transform(source)
    universe = program.get_abstract_universe()
    statements = universe.get_statements_by_type(ast.PropertyDeclaration)
    assert len(statements) == 1
    decl = statements[0]
    assert decl.type_name == "Foo"
    assert decl.property_type == "Bar"
    assert decl.property_name == "baz"


# Entity Creation


def test_entity_creation_with_properties():
    source = _strip(
        """
        AbstractUniverse:
            Creator creates a Thing named instance:
                string_prop: "Hello, world!"
                number_prop: 42
                reference_prop: Owner's property
        """
    )
    program = _parse_and_transform(source)
    universe = program.get_abstract_universe()
    statements = universe.get_statements_by_type(ast.EntityCreation)
    assert len(statements) == 1
    entity = statements[0]
    assert entity.creator == "Creator"
    assert entity.type_name == "Thing"
    assert entity.entity_name == "instance"
    assert len(entity.properties) == 3

    # Verify string literal property
    string_prop = entity.properties[0]
    assert string_prop.name == "string_prop"
    assert isinstance(string_prop.value, ast.StringLiteral)
    assert string_prop.value.raw_value == '"Hello, world!"'

    # Verify number literal property
    number_prop = entity.properties[1]
    assert number_prop.name == "number_prop"
    assert isinstance(number_prop.value, ast.NumberLiteral)
    assert number_prop.value.raw_value == "42"

    # Verify property/entity reference property
    reference_prop = entity.properties[2]
    assert reference_prop.name == "reference_prop"
    assert isinstance(reference_prop.value, ast.PropertyOrEntityReference)
    assert reference_prop.value.owner == "Owner"
    assert reference_prop.value.property_name == "property"


def test_entity_creation_without_properties():
    source = _strip(
        """
        AbstractUniverse:
            Creator creates a Thing named instance.
        """
    )
    program = _parse_and_transform(source)
    universe = program.get_abstract_universe()
    statements = universe.get_statements_by_type(ast.EntityCreation)
    assert len(statements) == 1
    entity = statements[0]
    assert entity.creator == "Creator"
    assert entity.type_name == "Thing"
    assert entity.entity_name == "instance"
    assert len(entity.properties) == 0


# Knowledge Statements


def test_knowledge_statement():
    source = _strip(
        """
        PhysicalUniverse:
            Foo knows Bar's baz.
        """
    )
    program = _parse_and_transform(source)
    universe = program.get_physical_universe()
    statements = universe.get_statements_by_type(ast.KnowledgeStatement)
    assert len(statements) == 1
    stmt = statements[0]
    assert stmt.knower == "Foo"
    assert stmt.owner == "Bar"
    assert stmt.entity_name == "baz"


# Action Declarations


def test_action_declaration_without_parameters():
    source = _strip(
        """
        PhysicalUniverse:
            Actor can Act:
                Actor makes Owner's target Do Owner's arg.
        """
    )
    program = _parse_and_transform(source)
    universe = program.get_physical_universe()
    statements = universe.get_statements_by_type(ast.ActionDeclaration)
    assert len(statements) == 1
    action = statements[0]
    assert action.type_name == "Actor"
    assert action.action_name == "Act"
    assert len(action.parameters) == 0
    assert len(action.body) == 1


def test_action_declaration_with_multiple_parameters():
    source = _strip(
        """
        PhysicalUniverse:
            T can Act using a Arg named first, a Arg named second:
                T makes Owner's target Do Owner's arg1, Owner's arg2.
        """
    )
    program = _parse_and_transform(source)
    universe = program.get_physical_universe()
    statements = universe.get_statements_by_type(ast.ActionDeclaration)
    assert len(statements) == 1
    action = statements[0]
    assert action.type_name == "T"
    assert action.action_name == "Act"
    assert len(action.parameters) == 2
    assert action.parameters[0].param_type == "Arg"
    assert action.parameters[0].param_name == "first"
    assert action.parameters[1].param_type == "Arg"
    assert action.parameters[1].param_name == "second"
    assert len(action.body) == 1


def test_action_declaration_with_one_parameter():
    source = _strip(
        """
        PhysicalUniverse:
            T can Act using a Arg named first:
                T makes Owner's target Do Owner's arg1, Owner's arg2.
        """
    )
    program = _parse_and_transform(source)
    universe = program.get_physical_universe()
    statements = universe.get_statements_by_type(ast.ActionDeclaration)
    assert len(statements) == 1
    action = statements[0]
    assert action.type_name == "T"
    assert action.action_name == "Act"
    assert len(action.parameters) == 1
    assert action.parameters[0].param_type == "Arg"
    assert action.parameters[0].param_name == "first"
    assert len(action.body) == 1


def test_action_body():
    source = _strip(
        """
        PhysicalUniverse:
            Actor can Act:
                Actor makes Owner's target Do Owner's arg1, Owner's arg2.
                Actor makes Owner's target Do Owner's arg3, Owner's arg4.
        """
    )
    program = _parse_and_transform(source)
    universe = program.get_physical_universe()
    statements = universe.get_statements_by_type(ast.ActionDeclaration)
    action = statements[0]
    assert len(action.body) == 2
    assert all(isinstance(e, ast.ActionExecution) for e in action.body)


# Action Executions


def test_action_execution_without_arguments():
    source = _strip(
        """
        PhysicalUniverse:
            Actor makes Owner's target Do Owner's arg.
        """
    )
    program = _parse_and_transform(source)
    universe = program.get_physical_universe()
    statements = universe.get_statements_by_type(ast.ActionExecution)
    assert len(statements) == 1
    exec_stmt = statements[0]
    assert exec_stmt.actor == "Actor"
    assert exec_stmt.target.owner == "Owner"
    assert exec_stmt.target.property_name == "target"
    assert exec_stmt.action_name == "Do"
    assert len(exec_stmt.arguments) == 1
    arg = exec_stmt.arguments[0]
    assert isinstance(arg, ast.PropertyOrEntityReference)
    assert arg.owner == "Owner"
    assert arg.property_name == "arg"


def test_action_execution_with_arguments():
    source = _strip(
        """
        PhysicalUniverse:
            Actor makes Owner's target Do Owner's arg, "hello", 42.
        """
    )
    program = _parse_and_transform(source)
    universe = program.get_physical_universe()
    statements = universe.get_statements_by_type(ast.ActionExecution)
    assert len(statements) == 1
    exec_stmt = statements[0]
    assert len(exec_stmt.arguments) == 3

    # First argument: property reference
    arg1 = exec_stmt.arguments[0]
    assert isinstance(arg1, ast.PropertyOrEntityReference)
    assert arg1.owner == "Owner"
    assert arg1.property_name == "arg"

    # Second argument: string literal
    arg2 = exec_stmt.arguments[1]
    assert isinstance(arg2, ast.StringLiteral)
    assert arg2.raw_value == '"hello"'

    # Third argument: number literal
    arg3 = exec_stmt.arguments[2]
    assert isinstance(arg3, ast.NumberLiteral)
    assert arg3.raw_value == "42"


def test_action_execution_with_single_argument():
    source = _strip(
        """
        PhysicalUniverse:
            Actor makes Owner's target Do "single".
        """
    )
    program = _parse_and_transform(source)
    universe = program.get_physical_universe()
    statements = universe.get_statements_by_type(ast.ActionExecution)
    assert len(statements) == 1
    exec_stmt = statements[0]
    assert exec_stmt.actor == "Actor"
    assert exec_stmt.target.owner == "Owner"
    assert exec_stmt.target.property_name == "target"
    assert exec_stmt.action_name == "Do"
    assert len(exec_stmt.arguments) == 1
    arg = exec_stmt.arguments[0]
    assert isinstance(arg, ast.StringLiteral)
    assert arg.raw_value == '"single"'


# Integration Tests


def test_full_program_transformation():
    source = _strip(
        """
        AbstractUniverse:
            Source is a ViewPoint.
            Source creates a String named helloWorld:
                value: "Hello, world!"

        PhysicalUniverse:
            Machine is a Computer.
            Machine knows Source's helloWorld.
            Machine makes Machine's terminal Output Source's helloWorld.
        """
    )
    program = _parse_and_transform(source)
    assert isinstance(program, ast.Program)
    assert len(program.universes) == 2

    abstract = program.get_abstract_universe()
    assert len(abstract.statements) == 2
    assert isinstance(abstract.statements[0], ast.TypeDeclaration)
    assert isinstance(abstract.statements[1], ast.EntityCreation)

    physical = program.get_physical_universe()
    assert len(physical.statements) == 3
    assert isinstance(physical.statements[0], ast.TypeDeclaration)
    assert isinstance(physical.statements[1], ast.KnowledgeStatement)
    assert isinstance(physical.statements[2], ast.ActionExecution)


def test_multiple_statements_in_universe():
    source = _strip(
        """
        AbstractUniverse:
            Number is.
            Source is a ViewPoint.
            Source has a String named value.
            Source creates a String named helloWorld:
                value: "Hello, world!"
        """
    )
    program = _parse_and_transform(source)
    universe = program.get_abstract_universe()
    assert len(universe.statements) == 4
    assert isinstance(universe.statements[0], ast.CompilerTypeDeclaration)
    assert isinstance(universe.statements[1], ast.TypeDeclaration)
    assert isinstance(universe.statements[2], ast.PropertyDeclaration)
    assert isinstance(universe.statements[3], ast.EntityCreation)


def test_nested_structures():
    source = _strip(
        """
        AbstractUniverse:
            Source creates a String named helloWorld:
                value: "Hello, world!"

        PhysicalUniverse:
            Machine can Output using a String named message:
                Machine makes Machine's terminal Output Machine's message, Machine's message.
            Machine makes Machine's terminal Output Source's helloWorld, Source's helloWorld.
        """
    )
    program = _parse_and_transform(source)
    assert isinstance(program, ast.Program)

    physical = program.get_physical_universe()
    assert len(physical.statements) == 2
    statements = physical.get_statements_by_type(ast.ActionDeclaration)
    assert len(statements) == 1
    action = statements[0]
    assert len(action.body) == 1
    exec_stmt = action.body[0]
    assert isinstance(exec_stmt.arguments[0], ast.PropertyOrEntityReference)
