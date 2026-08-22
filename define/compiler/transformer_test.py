"""Tests for the Define AST transformer.

There is at least one test per concrete AST node the transformer can produce.
Each such test asserts the node's stored data fields, its full source location
(line, column, end_line, end_column), and the substring of the original source
that location addresses.
"""

from __future__ import annotations

from define.compiler import ast, test_helpers


def _require_fqun(name: ast.GlobalNameContent) -> ast.Fqun:
    assert name.fqun is not None
    return name.fqun


def _slice(source: str, location: ast.SourceLocation) -> str:
    """Return the exact substring of ``source`` covered by ``location``.

    Locations use 1-based ``line``/``column`` and an exclusive ``end_column``,
    matching what lark's lexer produces.
    """
    lines = source.split("\n")
    if location.line == location.end_line:
        return lines[location.line - 1][location.column - 1 : location.end_column - 1]
    parts = [lines[location.line - 1][location.column - 1 :]]
    for line_idx in range(location.line, location.end_line - 1):
        parts.append(lines[line_idx])
    parts.append(lines[location.end_line - 1][: location.end_column - 1])
    return "\n".join(parts)


_SIMPLE_POSITION = "define the potential position<standard:/path>.\n"

_FULL_FQUN_POSITION = (
    "define the potential position<my_mv:example.com:my_lib:/some/path>.\n"
)

_AUTHORITY_FQUN_POSITION = (
    "define the potential position<example.com:my_lib:/some/path>.\n"
)

_AUTHORITY_PATH_FQUN_POSITION = (
    "define the potential position<example.com/org/repo:my_lib:/some/path>.\n"
)

_FULL_POSITION = (
    "define the potential position<standard:/path> {\n"
    + "    it also assigns the position</a>.\n"
    + "    it may only contain particles where {\n"
    + "        it has the position</child>.\n"
    + "        it has the action</other>.\n"
    + "    }\n"
    + "}\n"
)

_FULL_ACTION = (
    "define the potential action<standard:/path> {\n"
    + "    it also assigns the position</a>.\n"
    + "    define the position<run>.\n"
    + "    define the position<other_pos>.\n"
    + "    it happens when {\n"
    + "        the position<run> has a particle.\n"
    + "    } and it does {\n"
    + "        create a particle in position<run>.\n"
    + "        move the particle in position<src> to position<dest>.\n"
    + "        destroy the particle in position<run>.\n"
    + "    }\n"
    + "}\n"
)

_DESTRUCTOR_ACTION = (
    "define the potential action<standard:/path> {\n"
    + "    it happens when {\n"
    + "        this particle is being destroyed.\n"
    + "    } and it does {\n"
    + "    }\n"
    + "}\n"
)

_CONSTRUCTOR_ACTION = (
    "define the potential action<standard:/path> {\n"
    + "    it happens when {\n"
    + "        this particle is created.\n"
    + "    } and it does {\n"
    + "    }\n"
    + "}\n"
)

_LOCAL_CONSTRAINED_ACTION = (
    "define the potential action<standard:/path> {\n"
    + "    define the position<my_pos> {\n"
    + "        it may only contain particles where {\n"
    + "            it has the action</child>.\n"
    + "        }\n"
    + "    }\n"
    + "    it happens when {\n"
    + "        the position<my_pos> has a particle.\n"
    + "    } and it does {\n"
    + "    }\n"
    + "}\n"
)

_LOCAL_CHAIN_CREATE = (
    "define the potential action<standard:/path> {\n"
    + "    define the position<run>.\n"
    + "    it happens when {\n"
    + "        the position<run> has a particle.\n"
    + "    } and it does {\n"
    + "        create a particle in position<to>::action<deposit>::position<run>.\n"
    + "    }\n"
    + "}\n"
)

_GLOBAL_CHAIN_CREATE = (
    "define the potential action<standard:/path> {\n"
    + "    define the position<run>.\n"
    + "    it happens when {\n"
    + "        the position<run> has a particle.\n"
    + "    } and it does {\n"
    + "        create a particle in position</a>::action</b>::position</c>.\n"
    + "    }\n"
    + "}\n"
)

_FULL_FQUN_CREATE = (
    "define the potential action<standard:/path> {\n"
    + "    define the position<run>.\n"
    + "    it happens when {\n"
    + "        the position<run> has a particle.\n"
    + "    } and it does {\n"
    + "        create a particle in position<mv:define-lang.org:parser:/run>.\n"
    + "    }\n"
    + "}\n"
)

_TWO_DEFINITIONS = (
    "define the potential position<my_mv:example.com:lib_a:/pos_a> {\n"
    + "    it may only contain particles where {\n"
    + "        it has the position</child>.\n"
    + "    }\n"
    + "}\n"
    + "define the potential position<my_mv:example.com:lib_b:/pos_b> {\n"
    + "    it may only contain particles where {\n"
    + "        it has the position</other>.\n"
    + "    }\n"
    + "}\n"
)


def _only_action(source: str) -> ast.ActionDefinition:
    program = test_helpers.parse_and_transform(source)
    definition = program.definitions[0]
    assert isinstance(definition, ast.ActionDefinition)
    return definition


def _only_position(source: str) -> ast.PositionDefinition:
    program = test_helpers.parse_and_transform(source)
    definition = program.definitions[0]
    assert isinstance(definition, ast.PositionDefinition)
    return definition


# Name leaf nodes


def test_universe_fields():
    fqun = _require_fqun(_only_position(_SIMPLE_POSITION).typed_name.name_content)
    assert fqun.universe.name == "standard"
    assert fqun.universe.location == ast.SourceLocation(
        line=1, column=31, end_line=1, end_column=39
    )
    assert _slice(_SIMPLE_POSITION, fqun.universe.location) == "standard"


def test_multiverse_fields():
    fqun = _require_fqun(_only_position(_FULL_FQUN_POSITION).typed_name.name_content)
    assert fqun.multiverse is not None
    assert fqun.multiverse.name == "my_mv"
    assert fqun.multiverse.location == ast.SourceLocation(
        line=1, column=31, end_line=1, end_column=36
    )
    assert _slice(_FULL_FQUN_POSITION, fqun.multiverse.location) == "my_mv"


def test_authority_fields():
    fqun = _require_fqun(_only_position(_FULL_FQUN_POSITION).typed_name.name_content)
    assert fqun.authority is not None
    assert fqun.authority.name == "example.com"
    assert fqun.authority.location == ast.SourceLocation(
        line=1, column=37, end_line=1, end_column=48
    )
    assert _slice(_FULL_FQUN_POSITION, fqun.authority.location) == "example.com"


def test_authority_with_path_fields():
    fqun = _require_fqun(
        _only_position(_AUTHORITY_PATH_FQUN_POSITION).typed_name.name_content
    )
    assert fqun.authority is not None
    assert fqun.authority.name == "example.com/org/repo"
    assert fqun.authority.location == ast.SourceLocation(
        line=1, column=31, end_line=1, end_column=51
    )
    assert (
        _slice(_AUTHORITY_PATH_FQUN_POSITION, fqun.authority.location)
        == "example.com/org/repo"
    )


def test_global_path_name_fields():
    path = _only_position(_SIMPLE_POSITION).typed_name.name_content.path
    assert path.name == "/path"
    assert path.location == ast.SourceLocation(
        line=1, column=40, end_line=1, end_column=45
    )
    assert _slice(_SIMPLE_POSITION, path.location) == "/path"


def test_local_name_content_fields():
    name_content = (
        _only_action(_FULL_ACTION).interface_positions[0].typed_name.name_content
    )
    assert name_content.name == "run"
    assert name_content.location == ast.SourceLocation(
        line=3, column=25, end_line=3, end_column=28
    )
    assert _slice(_FULL_ACTION, name_content.location) == "run"


# Fully-qualified universe names


def test_fqun_universe_only_fields():
    fqun = _require_fqun(_only_position(_SIMPLE_POSITION).typed_name.name_content)
    assert fqun.multiverse is None
    assert fqun.authority is None
    assert fqun.universe.name == "standard"
    assert fqun.location == ast.SourceLocation(
        line=1, column=31, end_line=1, end_column=39
    )
    assert _slice(_SIMPLE_POSITION, fqun.location) == "standard"


def test_fqun_authority_universe_fields():
    fqun = _require_fqun(
        _only_position(_AUTHORITY_FQUN_POSITION).typed_name.name_content
    )
    assert fqun.multiverse is None
    assert fqun.authority is not None
    assert fqun.authority.name == "example.com"
    assert fqun.universe.name == "my_lib"
    assert fqun.location == ast.SourceLocation(
        line=1, column=31, end_line=1, end_column=49
    )
    assert _slice(_AUTHORITY_FQUN_POSITION, fqun.location) == "example.com:my_lib"


def test_fqun_full_fields():
    fqun = _require_fqun(_only_position(_FULL_FQUN_POSITION).typed_name.name_content)
    assert fqun.multiverse is not None
    assert fqun.multiverse.name == "my_mv"
    assert fqun.authority is not None
    assert fqun.authority.name == "example.com"
    assert fqun.universe.name == "my_lib"
    assert fqun.location == ast.SourceLocation(
        line=1, column=31, end_line=1, end_column=55
    )
    assert _slice(_FULL_FQUN_POSITION, fqun.location) == "my_mv:example.com:my_lib"


# Typed names


def test_global_typed_name_in_definition_fields():
    typed_name = _only_position(_SIMPLE_POSITION).typed_name
    assert typed_name.name_type == ast.NameType.POSITION
    assert isinstance(typed_name.name_content, ast.DefinitionGlobalNameContent)
    assert typed_name.location == ast.SourceLocation(
        line=1, column=22, end_line=1, end_column=46
    )
    assert _slice(_SIMPLE_POSITION, typed_name.location) == "position<standard:/path>"


def test_definition_global_name_content_fields():
    name_content = _only_position(_SIMPLE_POSITION).typed_name.name_content
    assert isinstance(name_content.fqun, ast.Fqun)
    assert isinstance(name_content.path, ast.GlobalPathName)
    assert name_content.location == ast.SourceLocation(
        line=1, column=31, end_line=1, end_column=45
    )
    assert _slice(_SIMPLE_POSITION, name_content.location) == "standard:/path"


def test_reference_global_name_content_without_fqun_fields():
    definition = _only_position(_FULL_POSITION)
    assert definition.constraints is not None
    name_content = definition.constraints.requirements[0].typed_global_name.name_content
    assert name_content.fqun is None
    assert name_content.path.name == "/child"
    assert name_content.location == ast.SourceLocation(
        line=4, column=29, end_line=4, end_column=35
    )
    assert _slice(_FULL_POSITION, name_content.location) == "/child"


def test_reference_global_name_content_with_fqun_fields():
    stmt = _only_action(_FULL_FQUN_CREATE).action_statements.statements[0]
    assert isinstance(stmt, ast.CreateParticleStatement)
    typed_name = stmt.target_position.typed_names[0]
    assert isinstance(typed_name, ast.GlobalTypedNameReference)
    name_content = typed_name.name_content
    assert _require_fqun(name_content).universe.name == "parser"
    assert name_content.path.name == "/run"
    assert name_content.location == ast.SourceLocation(
        line=6, column=39, end_line=6, end_column=69
    )
    assert (
        _slice(_FULL_FQUN_CREATE, name_content.location)
        == "mv:define-lang.org:parser:/run"
    )


def test_global_typed_name_reference_fields():
    definition = _only_position(_FULL_POSITION)
    assert definition.constraints is not None
    typed_name = definition.constraints.requirements[0].typed_global_name
    assert typed_name.name_type == ast.NameType.POSITION
    assert isinstance(typed_name.name_content, ast.ReferenceGlobalNameContent)
    assert typed_name.enclosing_fqun.canonical == "standard"
    assert typed_name.location == ast.SourceLocation(
        line=4, column=20, end_line=4, end_column=36
    )
    assert _slice(_FULL_POSITION, typed_name.location) == "position</child>"


def test_local_typed_name_reference_fields():
    typed_name = _only_action(_FULL_ACTION).interface_positions[0].typed_name
    assert typed_name.name_type == ast.NameType.POSITION
    assert isinstance(typed_name.name_content, ast.LocalNameContent)
    assert typed_name.location == ast.SourceLocation(
        line=3, column=16, end_line=3, end_column=29
    )
    assert _slice(_FULL_ACTION, typed_name.location) == "position<run>"


# Position references


def test_position_reference_single_fields():
    stmt = _only_action(_FULL_ACTION).action_statements.statements[0]
    assert isinstance(stmt, ast.CreateParticleStatement)
    reference = stmt.target_position
    assert len(reference.typed_names) == 1
    assert isinstance(reference.typed_names[0], ast.LocalTypedNameReference)
    assert reference.location == ast.SourceLocation(
        line=8, column=30, end_line=8, end_column=43
    )
    assert _slice(_FULL_ACTION, reference.location) == "position<run>"


def test_position_reference_chained_local_fields():
    stmt = _only_action(_LOCAL_CHAIN_CREATE).action_statements.statements[0]
    assert isinstance(stmt, ast.CreateParticleStatement)
    reference = stmt.target_position
    assert len(reference.typed_names) == 3
    assert all(
        isinstance(name, ast.LocalTypedNameReference) for name in reference.typed_names
    )
    assert reference.location == ast.SourceLocation(
        line=6, column=30, end_line=6, end_column=74
    )
    assert (
        _slice(_LOCAL_CHAIN_CREATE, reference.location)
        == "position<to>::action<deposit>::position<run>"
    )


def test_position_reference_chained_global_fields():
    stmt = _only_action(_GLOBAL_CHAIN_CREATE).action_statements.statements[0]
    assert isinstance(stmt, ast.CreateParticleStatement)
    reference = stmt.target_position
    assert len(reference.typed_names) == 3
    assert all(
        isinstance(name, ast.GlobalTypedNameReference) for name in reference.typed_names
    )
    assert reference.location == ast.SourceLocation(
        line=6, column=30, end_line=6, end_column=68
    )
    assert (
        _slice(_GLOBAL_CHAIN_CREATE, reference.location)
        == "position</a>::action</b>::position</c>"
    )


# Particle statements


def test_create_particle_statement_fields():
    stmt = _only_action(_FULL_ACTION).action_statements.statements[0]
    assert isinstance(stmt, ast.CreateParticleStatement)
    assert isinstance(stmt.target_position, ast.PositionReference)
    assert stmt.location == ast.SourceLocation(
        line=8, column=9, end_line=8, end_column=44
    )
    assert _slice(_FULL_ACTION, stmt.location) == "create a particle in position<run>."


def test_move_particle_statement_fields():
    stmt = _only_action(_FULL_ACTION).action_statements.statements[1]
    assert isinstance(stmt, ast.MoveParticleStatement)
    assert isinstance(stmt.source_position, ast.PositionReference)
    source_name = stmt.source_position.typed_names[0]
    assert isinstance(source_name, ast.LocalTypedNameReference)
    assert source_name.name_content.name == "src"
    assert isinstance(stmt.target_position, ast.PositionReference)
    target_name = stmt.target_position.typed_names[0]
    assert isinstance(target_name, ast.LocalTypedNameReference)
    assert target_name.name_content.name == "dest"
    assert stmt.location == ast.SourceLocation(
        line=9, column=9, end_line=9, end_column=62
    )
    assert (
        _slice(_FULL_ACTION, stmt.location)
        == "move the particle in position<src> to position<dest>."
    )


def test_destroy_particle_statement_fields():
    stmt = _only_action(_FULL_ACTION).action_statements.statements[2]
    assert isinstance(stmt, ast.DestroyParticleStatement)
    assert isinstance(stmt.target_position, ast.PositionReference)
    assert stmt.location == ast.SourceLocation(
        line=10, column=9, end_line=10, end_column=47
    )
    assert (
        _slice(_FULL_ACTION, stmt.location) == "destroy the particle in position<run>."
    )


# Trigger conditions


def test_position_presence_statement_fields():
    condition = _only_action(_FULL_ACTION).trigger_conditions.conditions[0]
    assert isinstance(condition, ast.PositionPresenceStatement)
    assert isinstance(condition.typed_name, ast.LocalTypedNameReference)
    assert condition.typed_name.name_content.name == "run"
    assert condition.location == ast.SourceLocation(
        line=6, column=9, end_line=6, end_column=42
    )
    assert (
        _slice(_FULL_ACTION, condition.location) == "the position<run> has a particle."
    )


def test_constructor_condition_statement_fields():
    condition = _only_action(_CONSTRUCTOR_ACTION).trigger_conditions.conditions[0]
    assert isinstance(condition, ast.ConstructorConditionStatement)
    assert condition.location == ast.SourceLocation(
        line=3, column=9, end_line=3, end_column=34
    )
    assert (
        _slice(_CONSTRUCTOR_ACTION, condition.location) == "this particle is created."
    )


def test_destructor_condition_statement_fields():
    condition = _only_action(_DESTRUCTOR_ACTION).trigger_conditions.conditions[0]
    assert isinstance(condition, ast.DestructorConditionStatement)
    assert condition.location == ast.SourceLocation(
        line=3, column=9, end_line=3, end_column=42
    )
    assert (
        _slice(_DESTRUCTOR_ACTION, condition.location)
        == "this particle is being destroyed."
    )


def test_trigger_conditions_block_fields():
    block = _only_action(_FULL_ACTION).trigger_conditions
    assert len(block.conditions) == 1
    assert isinstance(block.conditions[0], ast.PositionPresenceStatement)
    assert block.location == ast.SourceLocation(
        line=5, column=5, end_line=7, end_column=6
    )
    # fmt: off
    assert _slice(_FULL_ACTION, block.location) == (
        "it happens when {\n"
        "        the position<run> has a particle.\n"
        "    }"
    )
    # fmt: on


# Blocks


def test_position_constraint_block_fields():
    definition = _only_position(_FULL_POSITION)
    assert definition.constraints is not None
    block = definition.constraints
    assert len(block.requirements) == 2
    assert all(
        isinstance(requirement, ast.PositionRequirementStatement)
        for requirement in block.requirements
    )
    assert block.location == ast.SourceLocation(
        line=3, column=5, end_line=6, end_column=6
    )
    assert _slice(_FULL_POSITION, block.location) == (
        "it may only contain particles where {\n"
        "        it has the position</child>.\n"
        "        it has the action</other>.\n"
        "    }"
    )


def test_position_requirement_statement_fields():
    definition = _only_position(_FULL_POSITION)
    assert definition.constraints is not None
    requirement = definition.constraints.requirements[0]
    assert isinstance(requirement.typed_global_name, ast.GlobalTypedNameReference)
    assert requirement.location == ast.SourceLocation(
        line=4, column=9, end_line=4, end_column=37
    )
    assert (
        _slice(_FULL_POSITION, requirement.location) == "it has the position</child>."
    )


def test_quality_implication_statement_fields():
    implication = _only_position(_FULL_POSITION).quality_implications[0]
    assert isinstance(implication.typed_global_name, ast.GlobalTypedNameReference)
    assert implication.location == ast.SourceLocation(
        line=2, column=5, end_line=2, end_column=38
    )
    assert (
        _slice(_FULL_POSITION, implication.location)
        == "it also assigns the position</a>."
    )


def test_action_statements_block_fields():
    block = _only_action(_FULL_ACTION).action_statements
    assert len(block.statements) == 3
    assert isinstance(block.statements[0], ast.CreateParticleStatement)
    assert isinstance(block.statements[1], ast.MoveParticleStatement)
    assert isinstance(block.statements[2], ast.DestroyParticleStatement)
    assert block.location == ast.SourceLocation(
        line=7, column=6, end_line=11, end_column=6
    )
    assert _slice(_FULL_ACTION, block.location) == (
        " and it does {\n"
        "        create a particle in position<run>.\n"
        "        move the particle in position<src> to position<dest>.\n"
        "        destroy the particle in position<run>.\n"
        "    }"
    )


def test_action_statements_block_empty_fields():
    block = _only_action(_DESTRUCTOR_ACTION).action_statements
    assert block.statements == ()
    assert block.location == ast.SourceLocation(
        line=4, column=6, end_line=5, end_column=6
    )
    # fmt: off
    assert _slice(_DESTRUCTOR_ACTION, block.location) == (
        " and it does {\n"
        "    }"
    )
    # fmt: on


# Local position definitions


def test_local_position_definition_without_constraints_fields():
    local_def = _only_action(_FULL_ACTION).interface_positions[0]
    assert isinstance(local_def.typed_name, ast.LocalTypedNameReference)
    assert local_def.typed_name.name_content.name == "run"
    assert local_def.constraints is None
    assert local_def.location == ast.SourceLocation(
        line=3, column=5, end_line=3, end_column=30
    )
    assert _slice(_FULL_ACTION, local_def.location) == "define the position<run>."


def test_local_position_definition_with_constraints_fields():
    local_def = _only_action(_LOCAL_CONSTRAINED_ACTION).interface_positions[0]
    assert isinstance(local_def.typed_name, ast.LocalTypedNameReference)
    assert local_def.typed_name.name_content.name == "my_pos"
    assert isinstance(local_def.constraints, ast.PositionConstraintBlock)
    assert local_def.location == ast.SourceLocation(
        line=2, column=5, end_line=6, end_column=6
    )
    assert _slice(_LOCAL_CONSTRAINED_ACTION, local_def.location) == (
        "define the position<my_pos> {\n"
        "        it may only contain particles where {\n"
        "            it has the action</child>.\n"
        "        }\n"
        "    }"
    )


# Quality definitions


def test_position_definition_bare_fields():
    definition = _only_position(_SIMPLE_POSITION)
    assert isinstance(definition.typed_name, ast.GlobalTypedNameInDefinition)
    assert definition.quality_implications == ()
    assert definition.constraints is None
    assert definition.location == ast.SourceLocation(
        line=1, column=1, end_line=1, end_column=47
    )
    assert (
        _slice(_SIMPLE_POSITION, definition.location)
        == "define the potential position<standard:/path>."
    )


def test_position_definition_full_fields():
    definition = _only_position(_FULL_POSITION)
    assert isinstance(definition.typed_name, ast.GlobalTypedNameInDefinition)
    assert len(definition.quality_implications) == 1
    assert isinstance(
        definition.quality_implications[0], ast.QualityImplicationStatement
    )
    assert isinstance(definition.constraints, ast.PositionConstraintBlock)
    assert definition.location == ast.SourceLocation(
        line=1, column=1, end_line=7, end_column=2
    )
    assert _slice(_FULL_POSITION, definition.location) == (
        "define the potential position<standard:/path> {\n"
        "    it also assigns the position</a>.\n"
        "    it may only contain particles where {\n"
        "        it has the position</child>.\n"
        "        it has the action</other>.\n"
        "    }\n"
        "}"
    )


def test_action_definition_minimal_fields():
    definition = _only_action(_DESTRUCTOR_ACTION)
    assert isinstance(definition.typed_name, ast.GlobalTypedNameInDefinition)
    assert definition.typed_name.name_type == ast.NameType.ACTION
    assert definition.quality_implications == ()
    assert definition.interface_positions == ()
    assert isinstance(definition.trigger_conditions, ast.TriggerConditionsBlock)
    assert isinstance(definition.action_statements, ast.ActionStatementsBlock)
    assert definition.location == ast.SourceLocation(
        line=1, column=1, end_line=6, end_column=2
    )
    assert _slice(_DESTRUCTOR_ACTION, definition.location) == (
        "define the potential action<standard:/path> {\n"
        "    it happens when {\n"
        "        this particle is being destroyed.\n"
        "    } and it does {\n"
        "    }\n"
        "}"
    )


def test_action_definition_full_fields():
    definition = _only_action(_FULL_ACTION)
    assert isinstance(definition.typed_name, ast.GlobalTypedNameInDefinition)
    assert len(definition.quality_implications) == 1
    assert isinstance(
        definition.quality_implications[0], ast.QualityImplicationStatement
    )
    assert len(definition.interface_positions) == 2
    assert all(
        isinstance(position, ast.LocalPositionDefinition)
        for position in definition.interface_positions
    )
    assert isinstance(definition.trigger_conditions, ast.TriggerConditionsBlock)
    assert isinstance(definition.action_statements, ast.ActionStatementsBlock)
    assert definition.location == ast.SourceLocation(
        line=1, column=1, end_line=12, end_column=2
    )
    assert _slice(_FULL_ACTION, definition.location) == (
        "define the potential action<standard:/path> {\n"
        "    it also assigns the position</a>.\n"
        "    define the position<run>.\n"
        "    define the position<other_pos>.\n"
        "    it happens when {\n"
        "        the position<run> has a particle.\n"
        "    } and it does {\n"
        "        create a particle in position<run>.\n"
        "        move the particle in position<src> to position<dest>.\n"
        "        destroy the particle in position<run>.\n"
        "    }\n"
        "}"
    )


# Program


def test_program_fields():
    program = test_helpers.parse_and_transform(_SIMPLE_POSITION)
    assert len(program.definitions) == 1
    assert isinstance(program.definitions[0], ast.PositionDefinition)
    assert program.location == ast.SourceLocation(
        line=1, column=1, end_line=1, end_column=47
    )
    assert (
        _slice(_SIMPLE_POSITION, program.location)
        == "define the potential position<standard:/path>."
    )


def test_program_multiple_definitions_fields():
    program = test_helpers.parse_and_transform(_TWO_DEFINITIONS)
    assert len(program.definitions) == 2
    assert isinstance(program.definitions[0], ast.PositionDefinition)
    assert isinstance(program.definitions[1], ast.PositionDefinition)
    assert program.location == ast.SourceLocation(
        line=1, column=1, end_line=10, end_column=2
    )
    assert _slice(_TWO_DEFINITIONS, program.location) == (
        "define the potential position<my_mv:example.com:lib_a:/pos_a> {\n"
        "    it may only contain particles where {\n"
        "        it has the position</child>.\n"
        "    }\n"
        "}\n"
        "define the potential position<my_mv:example.com:lib_b:/pos_b> {\n"
        "    it may only contain particles where {\n"
        "        it has the position</other>.\n"
        "    }\n"
        "}"
    )


# enclosing_fqun is a stored field on GlobalTypedNameReference, dispatched by the
# enclosing definition rather than the reference's own (often absent) FQUN.


def test_enclosing_fqun_dispatched_per_definition():
    program = test_helpers.parse_and_transform(_TWO_DEFINITIONS)
    first = program.definitions[0]
    second = program.definitions[1]
    assert isinstance(first, ast.PositionDefinition)
    assert isinstance(second, ast.PositionDefinition)
    assert first.constraints is not None
    assert second.constraints is not None
    first_reference = first.constraints.requirements[0].typed_global_name
    second_reference = second.constraints.requirements[0].typed_global_name
    assert first_reference.enclosing_fqun.canonical == "my_mv:example.com:lib_a"
    assert second_reference.enclosing_fqun.canonical == "my_mv:example.com:lib_b"


def test_enclosing_fqun_on_every_chain_segment():
    stmt = _only_action(_GLOBAL_CHAIN_CREATE).action_statements.statements[0]
    assert isinstance(stmt, ast.CreateParticleStatement)
    chain = stmt.target_position.typed_names
    assert len(chain) == 3
    for segment in chain:
        assert isinstance(segment, ast.GlobalTypedNameReference)
        assert segment.enclosing_fqun.canonical == "standard"
