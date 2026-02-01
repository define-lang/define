import textwrap

import lark
import pytest
from lark.exceptions import UnexpectedCharacters, UnexpectedToken

from compiler.prototype.parser import Parser

# Shared parser instance to avoid rebuilding the Lark parser for each test
_parser = Parser()


def _strip(text: str) -> str:
    return textwrap.dedent(text).lstrip("\n")


def _get_identifiers_from_tree(tree: lark.Tree) -> list[str]:
    """Extract all IDENTIFIER token values from a tree."""
    identifiers = []
    for child in tree.children:
        if isinstance(child, lark.Tree):
            identifiers.extend(_get_identifiers_from_tree(child))
        elif child.type == "IDENTIFIER":
            identifiers.append(child.value)
    return identifiers


def _get_tokens_by_type_from_tree(tree: lark.Tree, token_type: str) -> list[lark.Token]:
    """Extract all tokens of a specific type from a tree."""
    tokens = []
    for child in tree.children:
        if isinstance(child, lark.Tree):
            tokens.extend(_get_tokens_by_type_from_tree(child, token_type))
        elif child.type == token_type:
            tokens.append(child)
    return tokens


def _get_direct_children_without_spaces(
    tree: lark.Tree,
) -> list[lark.Tree | lark.Token]:
    """Get direct children of a tree, filtering out SPACE tokens."""
    return [
        child
        for child in tree.children
        if not (isinstance(child, lark.Token) and child.type == "SPACE")
    ]


def _get_direct_token_children_by_type(tree: lark.Tree, token_type: str) -> list[str]:
    """Get token values of a specific type from direct children of a tree."""
    return [
        child.value
        for child in tree.children
        if isinstance(child, lark.Token) and child.type == token_type
    ]


def _get_direct_tree_children(tree: lark.Tree, data: str) -> list[lark.Tree]:
    """Get Tree children with a specific data value from direct children of a tree."""
    return [
        child
        for child in tree.children
        if isinstance(child, lark.Tree) and child.data == data
    ]


def _parse(source: str) -> lark.Tree:
    """Parse source and verify root structure."""
    tree = _parser.parse(source)
    assert isinstance(tree, lark.Tree)
    assert tree.data == "start"
    return tree


def _get_first_universe(tree: lark.Tree, expected_name: str) -> lark.Tree:
    """Get the first universe section and verify its name."""
    universe_sections = _get_direct_tree_children(tree, "universe_section")
    assert len(universe_sections) == 1
    universe = universe_sections[0]

    universe_name_tokens = _get_tokens_by_type_from_tree(universe, "UNIVERSE_NAME")
    assert [t.value for t in universe_name_tokens] == [expected_name]

    return universe


def _get_universe_by_name(tree: lark.Tree, expected_name: str) -> lark.Tree:
    """Get a universe section by name."""
    for universe in _get_direct_tree_children(tree, "universe_section"):
        universe_name_tokens = _get_tokens_by_type_from_tree(universe, "UNIVERSE_NAME")
        if universe_name_tokens and universe_name_tokens[0].value == expected_name:
            return universe
    raise AssertionError(f"Universe '{expected_name}' not found in tree")


def _assert_token_has_type_and_value(
    token: lark.Token | lark.Tree,
    expected_type: str,
    expected_value: str,
) -> None:
    """Assert that a token has the expected type and value."""
    assert isinstance(token, lark.Token)
    assert token.type == expected_type
    assert token.value == expected_value


def test_type_declaration_with_parent():
    source = _strip(
        """
        AbstractUniverse:
            Foo is a Bar.
        """
    )
    tree = _parse(source)
    universe = _get_first_universe(tree, "AbstractUniverse")

    # Verify type declaration
    type_decls = _get_direct_tree_children(universe, "type_declaration")
    assert len(type_decls) == 1
    type_decl = type_decls[0]
    identifiers = _get_identifiers_from_tree(type_decl)
    assert identifiers == ["Foo", "Bar"]


def test_type_declaration_compiler_type():
    source = _strip(
        """
        AbstractUniverse:
            Foo is.
        """
    )
    tree = _parse(source)
    universe = _get_first_universe(tree, "AbstractUniverse")

    # Verify compiler type declaration
    compiler_type_decls = _get_direct_tree_children(
        universe, "compiler_type_declaration"
    )
    assert len(compiler_type_decls) == 1
    compiler_type_decl = compiler_type_decls[0]
    identifiers = _get_identifiers_from_tree(compiler_type_decl)
    assert identifiers == ["Foo"]


def test_property_declaration():
    source = _strip(
        """
        AbstractUniverse:
            Foo has a Bar named baz.
        """
    )
    tree = _parse(source)
    universe = _get_first_universe(tree, "AbstractUniverse")

    # Verify property declaration
    prop_decls = _get_direct_tree_children(universe, "property_declaration")
    assert len(prop_decls) == 1
    prop_decl = prop_decls[0]
    identifiers = _get_identifiers_from_tree(prop_decl)
    assert identifiers == ["Foo", "Bar", "baz"]


def test_entity_creation_with_properties():
    source = _strip(
        """
        AbstractUniverse:
            Creator creates a Thing named instance:
                prop: "value"
                count: 3
        """
    )
    tree = _parse(source)
    universe = _get_first_universe(tree, "AbstractUniverse")

    # Verify entity creation
    entity_creations = _get_direct_tree_children(universe, "entity_creation")
    assert len(entity_creations) == 1
    entity_creation = entity_creations[0]

    # Verify entity creation identifiers: Creator, Thing, instance
    entity_idents = _get_direct_token_children_by_type(entity_creation, "IDENTIFIER")
    assert entity_idents == ["Creator", "Thing", "instance"]

    # Get property assignments in order from direct children
    property_assignments = _get_direct_tree_children(
        entity_creation, "property_assignment"
    )
    assert len(property_assignments) == 2

    # Verify first assignment: prop = "value"
    first_children = _get_direct_children_without_spaces(property_assignments[0])
    assert len(first_children) == 2
    _assert_token_has_type_and_value(first_children[0], "IDENTIFIER", "prop")
    _assert_token_has_type_and_value(first_children[1], "STRING", '"value"')

    # Verify second assignment: count = 3
    second_children = _get_direct_children_without_spaces(property_assignments[1])
    assert len(second_children) == 2
    _assert_token_has_type_and_value(second_children[0], "IDENTIFIER", "count")
    _assert_token_has_type_and_value(second_children[1], "NUMBER", "3")


def test_entity_creation_without_properties():
    source = _strip(
        """
        AbstractUniverse:
            Creator creates a Thing named instance.
        """
    )
    tree = _parse(source)
    universe = _get_first_universe(tree, "AbstractUniverse")

    # Verify entity creation
    entity_creations = _get_direct_tree_children(universe, "entity_creation")
    assert len(entity_creations) == 1
    entity_creation = entity_creations[0]
    identifiers = _get_identifiers_from_tree(entity_creation)
    assert identifiers == ["Creator", "Thing", "instance"]

    # Verify no property assignments
    property_assignments = _get_direct_tree_children(
        entity_creation, "property_assignment"
    )
    assert len(property_assignments) == 0


def test_knowledge_statement():
    source = _strip(
        """
        PhysicalUniverse:
            Foo knows Bar's baz.
        """
    )
    tree = _parse(source)
    universe = _get_first_universe(tree, "PhysicalUniverse")

    # Verify knowledge statement
    knowledge_stmts = _get_direct_tree_children(universe, "knowledge_statement")
    assert len(knowledge_stmts) == 1
    knowledge_stmt = knowledge_stmts[0]
    identifiers = _get_identifiers_from_tree(knowledge_stmt)
    assert identifiers == ["Foo", "Bar", "baz"]

    # Verify property_or_entity_reference exists
    property_refs = _get_direct_tree_children(
        knowledge_stmt, "property_or_entity_reference"
    )
    assert len(property_refs) == 1


def test_action_declaration_with_parameters_and_body():
    source = _strip(
        """
        PhysicalUniverse:
            T can Act using a Arg named first, a Arg named second:
                T makes Owner's target Do Owner's arg1, Owner's arg2.
        """
    )
    tree = _parse(source)
    universe = _get_first_universe(tree, "PhysicalUniverse")

    # Verify action declaration
    action_decls = _get_direct_tree_children(universe, "action_declaration")
    assert len(action_decls) == 1
    action_decl = action_decls[0]

    # Verify action declaration identifiers: T, Act
    action_idents = _get_direct_token_children_by_type(action_decl, "IDENTIFIER")
    assert action_idents[:2] == ["T", "Act"]

    # Get parameters in order from action_parameters
    action_params_trees = _get_direct_tree_children(action_decl, "action_parameters")
    assert len(action_params_trees) == 1
    action_params_tree = action_params_trees[0]
    param_nodes = _get_direct_tree_children(action_params_tree, "action_param")
    assert len(param_nodes) == 2

    # Verify first parameter: Arg named first
    first_param_children = _get_direct_children_without_spaces(param_nodes[0])
    assert len(first_param_children) == 2
    _assert_token_has_type_and_value(first_param_children[0], "IDENTIFIER", "Arg")
    _assert_token_has_type_and_value(first_param_children[1], "IDENTIFIER", "first")

    # Verify second parameter: Arg named second
    second_param_children = _get_direct_children_without_spaces(param_nodes[1])
    assert len(second_param_children) == 2
    _assert_token_has_type_and_value(second_param_children[0], "IDENTIFIER", "Arg")
    _assert_token_has_type_and_value(second_param_children[1], "IDENTIFIER", "second")

    # Get action executions in order from action_body
    action_bodies = _get_direct_tree_children(action_decl, "action_body")
    assert len(action_bodies) == 1
    action_body = action_bodies[0]
    action_executions = _get_direct_tree_children(action_body, "action_execution")
    assert len(action_executions) == 1

    # Verify action execution: T makes Owner's target Do Owner's arg1, Owner's arg2
    action_exec = action_executions[0]
    exec_children = _get_direct_children_without_spaces(action_exec)
    _assert_token_has_type_and_value(exec_children[0], "IDENTIFIER", "T")
    assert isinstance(exec_children[1], lark.Tree)
    assert exec_children[1].data == "property_or_entity_reference"
    target_idents = _get_identifiers_from_tree(exec_children[1])
    assert target_idents == ["Owner", "target"]
    _assert_token_has_type_and_value(exec_children[2], "IDENTIFIER", "Do")
    assert isinstance(exec_children[3], lark.Tree)
    assert exec_children[3].data == "argument_list"

    # Verify arguments
    argument_list = exec_children[3]
    arguments = _get_direct_children_without_spaces(argument_list)
    assert len(arguments) == 2
    assert isinstance(arguments[0], lark.Tree)
    assert arguments[0].data == "property_or_entity_reference"
    arg1_idents = _get_identifiers_from_tree(arguments[0])
    assert arg1_idents == ["Owner", "arg1"]
    assert isinstance(arguments[1], lark.Tree)
    assert arguments[1].data == "property_or_entity_reference"
    arg2_idents = _get_identifiers_from_tree(arguments[1])
    assert arg2_idents == ["Owner", "arg2"]


def test_action_execution_with_mixed_arguments():
    source = _strip(
        """
        PhysicalUniverse:
            Actor makes Owner's target Do Owner's prop, 42, "hello".
        """
    )
    tree = _parse(source)
    universe = _get_first_universe(tree, "PhysicalUniverse")

    # Verify action execution
    action_execs = _get_direct_tree_children(universe, "action_execution")
    assert len(action_execs) == 1
    action_exec = action_execs[0]
    identifiers = _get_identifiers_from_tree(action_exec)
    assert identifiers == [
        "Actor",
        "Owner",
        "target",
        "Do",
        "Owner",
        "prop",
    ]

    # Verify argument_list exists
    argument_lists = _get_direct_tree_children(action_exec, "argument_list")
    assert len(argument_lists) == 1
    argument_list = argument_lists[0]

    value_refs = _get_direct_children_without_spaces(argument_list)
    assert len(value_refs) == 3

    assert isinstance(value_refs[0], lark.Tree)
    assert value_refs[0].data == "property_or_entity_reference"
    prop_ref_idents = _get_identifiers_from_tree(value_refs[0])
    assert prop_ref_idents == ["Owner", "prop"]

    _assert_token_has_type_and_value(value_refs[1], "NUMBER", "42")
    _assert_token_has_type_and_value(value_refs[2], "STRING", '"hello"')


def test_action_execution_with_single_entity_reference():
    source = _strip(
        """
        PhysicalUniverse:
            Actor makes Owner's target Do Owner's entityName.
        """
    )
    tree = _parse(source)
    universe = _get_first_universe(tree, "PhysicalUniverse")

    # Verify action execution
    action_execs = _get_direct_tree_children(universe, "action_execution")
    assert len(action_execs) == 1
    action_exec = action_execs[0]
    identifiers = _get_identifiers_from_tree(action_exec)
    assert identifiers == [
        "Actor",
        "Owner",
        "target",
        "Do",
        "Owner",
        "entityName",
    ]

    # Verify argument_list exists
    argument_lists = _get_direct_tree_children(action_exec, "argument_list")
    assert len(argument_lists) == 1
    argument_list = argument_lists[0]

    value_refs = _get_direct_children_without_spaces(argument_list)
    assert len(value_refs) == 1

    # Verify the single argument is an entity reference
    assert isinstance(value_refs[0], lark.Tree)
    assert value_refs[0].data == "property_or_entity_reference"
    entity_ref_idents = _get_identifiers_from_tree(value_refs[0])
    assert entity_ref_idents == ["Owner", "entityName"]


def test_action_execution_with_single_string_literal():
    source = _strip(
        """
        PhysicalUniverse:
            Actor makes Owner's target Do "hello".
        """
    )
    tree = _parse(source)
    universe = _get_first_universe(tree, "PhysicalUniverse")

    # Verify action execution
    action_execs = _get_direct_tree_children(universe, "action_execution")
    assert len(action_execs) == 1
    action_exec = action_execs[0]
    identifiers = _get_identifiers_from_tree(action_exec)
    assert identifiers == [
        "Actor",
        "Owner",
        "target",
        "Do",
    ]

    # Verify argument_list exists
    argument_lists = _get_direct_tree_children(action_exec, "argument_list")
    assert len(argument_lists) == 1
    argument_list = argument_lists[0]

    value_refs = _get_direct_children_without_spaces(argument_list)
    assert len(value_refs) == 1

    # Verify the single argument is a string literal
    _assert_token_has_type_and_value(value_refs[0], "STRING", '"hello"')


def test_action_execution_with_single_number_literal():
    source = _strip(
        """
        PhysicalUniverse:
            Actor makes Owner's target Do 42.
        """
    )
    tree = _parse(source)
    universe = _get_first_universe(tree, "PhysicalUniverse")

    # Verify action execution
    action_execs = _get_direct_tree_children(universe, "action_execution")
    assert len(action_execs) == 1
    action_exec = action_execs[0]
    identifiers = _get_identifiers_from_tree(action_exec)
    assert identifiers == [
        "Actor",
        "Owner",
        "target",
        "Do",
    ]

    # Verify argument_list exists
    argument_lists = _get_direct_tree_children(action_exec, "argument_list")
    assert len(argument_lists) == 1
    argument_list = argument_lists[0]

    value_refs = _get_direct_children_without_spaces(argument_list)
    assert len(value_refs) == 1

    # Verify the single argument is a number literal
    _assert_token_has_type_and_value(value_refs[0], "NUMBER", "42")


def test_comment_allowed():
    source = _strip(
        """
        AbstractUniverse:
            # leading-space comment is allowed
            Foo is a Bar.
        """
    )
    tree = _parse(source)
    universe = _get_first_universe(tree, "AbstractUniverse")

    # Verify type declaration still parses correctly (comments are ignored)
    type_decls = _get_direct_tree_children(universe, "type_declaration")
    assert len(type_decls) == 1
    type_decl = type_decls[0]
    identifiers = _get_identifiers_from_tree(type_decl)
    assert identifiers == ["Foo", "Bar"]


def test_comment_before_first_universe():
    source = _strip(
        """
        # This is a comment before the universe block
        AbstractUniverse:
            Foo is a Bar.
        """
    )
    tree = _parse(source)
    universe = _get_first_universe(tree, "AbstractUniverse")

    # Verify type declaration still parses correctly (comments are ignored)
    type_decls = _get_direct_tree_children(universe, "type_declaration")
    assert len(type_decls) == 1
    type_decl = type_decls[0]
    identifiers = _get_identifiers_from_tree(type_decl)
    assert identifiers == ["Foo", "Bar"]


def test_universe_in_comment():
    source = _strip(
        """
        AbstractUniverse:
            # This is a comment with AbstractUniverse in it
            Foo is a Bar.
        """
    )
    tree = _parse(source)
    universe = _get_first_universe(tree, "AbstractUniverse")

    # Verify no UNIVERSE_NAME tokens appear from comments (only in the actual universe name)
    # With %ignore COMMENT, comments are filtered out before parsing
    universe_name_tokens = _get_tokens_by_type_from_tree(tree, "UNIVERSE_NAME")
    assert len(universe_name_tokens) == 1
    assert universe_name_tokens[0].value == "AbstractUniverse"

    # Verify type declaration still parses correctly
    type_decls = _get_direct_tree_children(universe, "type_declaration")
    assert len(type_decls) == 1
    type_decl = type_decls[0]
    identifiers = _get_identifiers_from_tree(type_decl)
    assert identifiers == ["Foo", "Bar"]


def test_universe_in_string_literal():
    source = _strip(
        """
        AbstractUniverse:
            Creator creates a Thing named instance:
                description: "This is a string with AbstractUniverse in it"
        """
    )
    tree = _parse(source)
    universe = _get_first_universe(tree, "AbstractUniverse")

    # Verify string is present in tree
    string_tokens = _get_tokens_by_type_from_tree(tree, "STRING")
    assert len(string_tokens) == 1
    # Verify the string contains "AbstractUniverse"
    assert "AbstractUniverse" in string_tokens[0].value

    # Verify no UNIVERSE_NAME tokens appear in strings (only in the actual universe name)
    universe_name_tokens = _get_tokens_by_type_from_tree(tree, "UNIVERSE_NAME")
    assert len(universe_name_tokens) == 1
    assert universe_name_tokens[0].value == "AbstractUniverse"

    # Verify entity creation still parses correctly
    entity_creations = _get_direct_tree_children(universe, "entity_creation")
    assert len(entity_creations) == 1
    entity_creation = entity_creations[0]
    identifiers = _get_identifiers_from_tree(entity_creation)
    assert identifiers == ["Creator", "Thing", "instance", "description"]


def test_string_literal_with_escaped_quote():
    source = _strip(
        """
        AbstractUniverse:
            Creator creates a Thing named instance:
                message: "hello \\"world\\""
        """
    )
    tree = _parse(source)
    universe = _get_first_universe(tree, "AbstractUniverse")

    # Verify string token is present with escaped quotes
    string_tokens = _get_tokens_by_type_from_tree(tree, "STRING")
    assert len(string_tokens) == 1
    assert string_tokens[0].value == '"hello \\"world\\""'

    # Verify entity creation parses correctly
    entity_creations = _get_direct_tree_children(universe, "entity_creation")
    assert len(entity_creations) == 1


def test_string_literal_with_escaped_backslash():
    source = _strip(
        """
        AbstractUniverse:
            Creator creates a Thing named instance:
                path: "hello \\\\ world"
        """
    )
    tree = _parse(source)
    universe = _get_first_universe(tree, "AbstractUniverse")

    # Verify string token is present with escaped backslash
    string_tokens = _get_tokens_by_type_from_tree(tree, "STRING")
    assert len(string_tokens) == 1
    assert string_tokens[0].value == '"hello \\\\ world"'

    # Verify entity creation parses correctly
    entity_creations = _get_direct_tree_children(universe, "entity_creation")
    assert len(entity_creations) == 1


def test_string_literal_empty():
    source = _strip(
        """
        AbstractUniverse:
            Creator creates a Thing named instance:
                text: ""
        """
    )
    tree = _parse(source)
    universe = _get_first_universe(tree, "AbstractUniverse")

    string_tokens = _get_tokens_by_type_from_tree(tree, "STRING")
    assert len(string_tokens) == 1
    assert string_tokens[0].value == '""'

    entity_creations = _get_direct_tree_children(universe, "entity_creation")
    assert len(entity_creations) == 1


def test_string_literal_with_only_escaped_characters():
    source = _strip(
        """
        AbstractUniverse:
            Creator creates a Thing named instance:
                text: "\\\\\\""
        """
    )
    tree = _parse(source)
    universe = _get_first_universe(tree, "AbstractUniverse")

    string_tokens = _get_tokens_by_type_from_tree(tree, "STRING")
    assert len(string_tokens) == 1
    assert string_tokens[0].value == '"\\\\\\""'

    entity_creations = _get_direct_tree_children(universe, "entity_creation")
    assert len(entity_creations) == 1


def test_blank_line_between_statements():
    # This test verifies that statements can be separated by blank lines
    # Blank lines should be filtered out by the lexer, so this should work
    source = _strip(
        """
        AbstractUniverse:
            Foo is a Bar.

            Baz is a Qux.
        """
    )
    tree = _parse(source)
    universe = _get_first_universe(tree, "AbstractUniverse")

    # Verify both type declarations are present
    type_decls = _get_direct_tree_children(universe, "type_declaration")
    assert len(type_decls) == 2
    first_decl = type_decls[0]
    second_decl = type_decls[1]
    assert _get_identifiers_from_tree(first_decl) == ["Foo", "Bar"]
    assert _get_identifiers_from_tree(second_decl) == ["Baz", "Qux"]


def test_multiple_blank_lines():
    # Multiple blank lines should all be filtered out
    source = _strip(
        """
        AbstractUniverse:
            Foo is a Bar.

            Baz is a Qux.
        """
    )
    tree = _parse(source)
    universe = _get_first_universe(tree, "AbstractUniverse")

    # Verify both type declarations are present (blank lines are ignored)
    type_decls = _get_direct_tree_children(universe, "type_declaration")
    assert len(type_decls) == 2
    first_decl = type_decls[0]
    second_decl = type_decls[1]
    assert _get_identifiers_from_tree(first_decl) == ["Foo", "Bar"]
    assert _get_identifiers_from_tree(second_decl) == ["Baz", "Qux"]


def test_blank_line_before_first_universe():
    source = _strip(
        """

        AbstractUniverse:
            Foo is a Bar.
        """
    )
    tree = _parse(source)
    universe = _get_first_universe(tree, "AbstractUniverse")

    # Verify type declaration still parses correctly
    type_decls = _get_direct_tree_children(universe, "type_declaration")
    assert len(type_decls) == 1
    type_decl = type_decls[0]
    identifiers = _get_identifiers_from_tree(type_decl)
    assert identifiers == ["Foo", "Bar"]


def test_blank_line_between_universes():
    source = _strip(
        """
        AbstractUniverse:
            Foo is a Bar.

        PhysicalUniverse:
            Baz is a Qux.
        """
    )
    tree = _parse(source)
    abstract_universe = _get_universe_by_name(tree, "AbstractUniverse")
    physical_universe = _get_universe_by_name(tree, "PhysicalUniverse")

    # Verify both universes parse correctly
    abstract_decls = _get_direct_tree_children(abstract_universe, "type_declaration")
    physical_decls = _get_direct_tree_children(physical_universe, "type_declaration")
    assert len(abstract_decls) == 1
    assert len(physical_decls) == 1
    assert _get_identifiers_from_tree(abstract_decls[0]) == ["Foo", "Bar"]
    assert _get_identifiers_from_tree(physical_decls[0]) == ["Baz", "Qux"]


def test_blank_lines_in_action_body():
    source = _strip(
        """
        PhysicalUniverse:
            Actor can Act:
                Actor makes Owner's target Do Owner's arg1.

                Actor makes Owner's target Do Owner's arg2.
        """
    )
    tree = _parse(source)
    universe = _get_first_universe(tree, "PhysicalUniverse")

    # Verify action declaration is present
    action_decls = _get_direct_tree_children(universe, "action_declaration")
    assert len(action_decls) == 1

    # Verify both action executions are present and in correct order
    action_bodies = _get_direct_tree_children(action_decls[0], "action_body")
    assert len(action_bodies) == 1
    action_body = action_bodies[0]

    # Get action executions from body, filtering out blank_line trees
    action_executions = _get_direct_tree_children(action_body, "action_execution")
    assert len(action_executions) == 2

    # Verify they match the found executions
    found_executions = list(action_decls[0].find_data("action_execution"))
    assert action_executions[0] == found_executions[0]
    assert action_executions[1] == found_executions[1]


@pytest.mark.parametrize(
    ("source", "token_type", "token_value"),
    [
        pytest.param(
            _strip(
                """
                AbstractUniverse:
                    Foo  is a Bar.
                """
            ),
            "SPACE",
            " ",
            id="double_space_between_tokens",
        ),
        pytest.param(
            _strip(
                """
                AbstractUniverse:
                    Foo is .
                """
            ),
            "IDENTIFIER",
            "is",
            id="space_before_period_in_is_form",
        ),
        pytest.param(
            _strip(
                """
                AbstractUniverse:
                    Creator creates a Thing named instance:
                        prop:"value"
                """
            ),
            "STRING",
            '"value"',
            id="missing_space_after_colon_in_property_assignment",
        ),
        pytest.param(
            _strip(
                """
                AbstractUniverse:
                    Foo is a Bar .
                """
            ),
            "SPACE",
            " ",
            id="space_before_period",
        ),
        pytest.param(
            _strip(
                """
                AbstractUniverse:
                    Foo has an Bar named baz.
                """
            ),
            "IDENTIFIER",
            "n",
            id="invalid_keyword_has_an",
        ),
        pytest.param(
            _strip(
                """
                AbstractUniverse:
                    Foo creates the Bar named baz:
                        prop: "value"
                """
            ),
            "IDENTIFIER",
            "creates",
            id="invalid_keyword_creates_the",
        ),
        pytest.param(
            _strip(
                """
                AbstractUniverse:
                    Foo creates a Bar baz:
                        prop: "value"
                """
            ),
            "IDENTIFIER",
            "baz",
            id="missing_required_keyword_named",
        ),
        pytest.param(
            _strip(
                """
                AbstractUniverse :
                    Foo is a Bar.
                """
            ),
            "SPACE",
            " ",
            id="bad_universe_header_spacing",
        ),
        pytest.param(
            "AbstractUniverse:\n    Foo is a Bar.",
            "DEDENT",
            "",
            id="missing_final_newline",
        ),
        pytest.param(
            _strip(
                """
                PhysicalUniverse:
                    T  can act.
                """
            ),
            "SPACE",
            " ",
            id="action_declaration_with_extra_spaces",
        ),
        pytest.param(
            _strip(
                """
                PhysicalUniverse:
                    actor makes target'saction arg1.
                """
            ),
            "IDENTIFIER",
            "action",
            id="action_execution_missing_space_between_target_and_action",
        ),
        pytest.param(
            _strip(
                """
                PhysicalUniverse:
                    T can Act.
                """
            ),
            "DOT",
            ".",
            id="action_declaration_without_body",
        ),
        pytest.param(
            _strip(
                """
                PhysicalUniverse:
                    TypeName can ActionName:
                """
            ),
            "DEDENT",
            "",
            id="action_declaration_with_colon_but_no_body",
        ),
        pytest.param(
            _strip(
                """
                AbstractUniverse:
                    PhysicalUniverse:
                        Foo is a Bar.
                """
            ),
            "COLON",
            ":",
            id="nested_universe_block_forbidden",
        ),
        pytest.param(
            "AbstractUniverse:\n",
            "$END",
            "",
            id="empty_universe_block",
        ),
        pytest.param(
            "AbstractUniverse:\n     \n\n",
            "$END",
            "",
            id="empty_universe_block_with_indent_and_dedent",
        ),
        pytest.param(
            _strip(
                """
                AbstractUniverse:
                PhysicalUniverse:
                    Foo is a Bar.
                """
            ),
            "UNIVERSE_NAME",
            "PhysicalUniverse",
            id="empty_universe_followed_by_another_universe",
        ),
    ],
)
def test_unexpected_token(source: str, token_type: str, token_value: str):
    with pytest.raises(UnexpectedToken) as exc_info:
        _parser.parse(source)

    exception = exc_info.value
    assert exception.token.type == token_type, str(exception)
    assert exception.token.value == token_value, str(exception)


@pytest.mark.parametrize(
    ("source", "char"),
    [
        pytest.param(
            "AbstractUniverse:\n\tFoo is a Bar.\n",
            "\t",
            id="tab_indentation",
        ),
        pytest.param(
            "AbstractUniverse:\r\n    Foo is a Bar.\r\n",
            "\r",
            id="carriage_return_usage",
        ),
    ],
)
def test_unexpected_characters(source: str, char: str):
    with pytest.raises(UnexpectedCharacters) as exc_info:
        _parser.parse(source)

    exception = exc_info.value
    assert exception.char == char, str(exception)
