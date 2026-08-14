from __future__ import annotations

import typing

from define.compiler import ast, test_helpers
from define.compiler.codegen import action_plan
from define.compiler.codegen.literal.python import (
    action_context,
    action_names,
    template_context,
)
from define.compiler.data_structures import typed_name_dict
from define.compiler.validator import test_helpers as validator_test_helpers
from define.compiler.validator.reference_graph import (
    action_contract,
    operation_graph_action_resolver,
    operation_graph_model,
)

if typing.TYPE_CHECKING:
    import collections.abc

    from define.compiler import conftest


def _position(position_name: str) -> ast.PositionReference:
    program = test_helpers.parse_and_transform(
        f"""\
define the potential action<my.domain.com:my_lib:/test> {{
    it also assigns the position<{position_name}>.
    it happens when {{
        this particle is created.
    }} and it does {{
        create a particle in position<{position_name}>.
    }}
}}
"""
    )
    definition = program.definitions[0]
    assert isinstance(definition, ast.ActionDefinition)
    statement = definition.action_statements.statements[0]
    assert isinstance(statement, ast.CreateParticleStatement)
    return statement.target_position


def _action_definition(
    local_position_names: tuple[str, ...] = (),
) -> ast.ActionDefinition:
    local_position_statements = "\n".join(
        f"        define the position<{name}>." for name in local_position_names
    )
    program = test_helpers.parse_and_transform(
        f"""\
define the potential action<my.domain.com:my_lib:/test> {{
    it happens when {{
        this particle is created.
    }} and it does {{
{local_position_statements}
        create a particle in position</item>.
    }}
}}
"""
    )
    definition = program.definitions[0]
    assert isinstance(definition, ast.ActionDefinition)
    return definition


def _action_triggers(
    validate_project: conftest.ValidateProject,
) -> collections.abc.Sequence[operation_graph_model.ActionTrigger]:
    result = validate_project(
        {
            "test.dfn": """\
define the potential action<my.domain.com:my_lib:/test> {
    define the position<gateway> {
        it may only contain particles where {
            it has the action</worker>.
            it has the action</worker_2>.
        }
    }
    it happens when {
        this particle is created.
    } and it does {
        create a particle in position<gateway>.
        create a particle in position<gateway>::action</worker_2>::position<trigger_pos>.
        create a particle in position<gateway>::action</worker>::position<trigger_pos>.
        destroy the particle in position<gateway>::action</worker>::position<trigger_pos>.
        create a particle in position<gateway>::action</worker>::position<trigger_pos>.
    }
}
""",
            "worker.dfn": """\
define the potential action<my.domain.com:my_lib:/worker> {
    define the position<trigger_pos>.
    it happens when {
        the position<trigger_pos> has a particle.
    } and it does {
        define the position<scratch>.
        create a particle in position<scratch>.
    }
}
""",
            "worker_2.dfn": """\
define the potential action<my.domain.com:my_lib:/worker_2> {
    define the position<trigger_pos>.
    it happens when {
        the position<trigger_pos> has a particle.
    } and it does {
        define the position<scratch>.
        create a particle in position<scratch>.
    }
}
""",
        }
    )
    validator_test_helpers.assert_no_errors(result.program_result)
    test_definition_result = next(
        definition_result
        for definition_result in result.program_result.definition_results.values()
        if definition_result.definition.typed_name.full_typed_name
        == "action<my.domain.com:my_lib:/test>"
    )
    return result.operation_graphs[
        test_definition_result.definition.typed_name
    ].triggers


def _create_fragment(position_name: str) -> action_plan.ActionFragment:
    return action_plan.ActionFragment(
        [
            operation_graph_model.CreateNode(
                node_id=0,
                depends_on=(),
                target=_position(position_name),
            )
        ]
    )


def _requirement_input(
    position_name: str,
    required_state: action_contract.PositionOccupancyState,
) -> operation_graph_model.RequirementNode:
    action_parent_input = operation_graph_model.ActionParentLastOperationNode(
        node_id=0, depends_on=()
    )
    return operation_graph_model.RequirementNode(
        node_id=1,
        depends_on=(action_parent_input,),
        required_state=required_state,
        requirement_position=(f"position<{position_name}>",),
    )


def _empty_rule_input(
    position_name: str,
) -> operation_graph_model.CallerEmptyRuleDependencies:
    return operation_graph_model.CallerEmptyRuleDependencies(
        requirement_position=(f"position<{position_name}>",),
        dependency_child_positions=frozenset(),
        dependency_requirements=(),
    )


def _generated_action(
    guarantee_interface: action_context.GuaranteeInterface | None,
) -> action_context.GeneratedAction:
    execution = template_context.ActionExecutionContext(
        execution_class_name="CalleeExecution",
        local_position_statements=[],
        fragments=[],
        caller_inputs=[],
        action_triggers=[],
        triggers_for_destroyed_callee_guarantee_particles=[],
        triggered_action_inputs=[],
        guarantees=None,
        accepts_destruction_connections=False,
    )
    context = action_context.ActionDefinitionContext(
        "Callee",
        "local.callee",
        execution,
        [],
        action_context.ActionRole.ACTION,
        [],
        [],
    )
    return action_context.GeneratedAction(context, {}, guarantee_interface, {})


def _action_names(
    plan: action_plan.ActionPlan,
    *,
    definition: ast.ActionDefinition | None = None,
) -> action_names.ActionNames:
    generated_actions = typed_name_dict.TypedNameDict[
        ast.GlobalTypedName, action_context.GeneratedAction
    ]()
    for planned_trigger in plan.action_triggers:
        action_trigger = planned_trigger.action_trigger
        generated_actions[action_trigger.callee_action_name] = _generated_action(None)
    return action_names.ActionNameGenerator(
        definition or _action_definition(),
        plan,
        generated_actions,
    ).generate()


def _input_method_names(
    *resolved_inputs: operation_graph_action_resolver.CallerInput,
) -> dict[operation_graph_action_resolver.CallerInput, str]:
    plan = action_plan.ActionPlan(
        fragments=[],
        execute_fragments=[],
        caller_inputs=[
            action_plan.CallerInputPlan(resolved_input)
            for resolved_input in resolved_inputs
        ],
        action_triggers=[],
        triggered_action_inputs=[],
        triggers_for_destroyed_callee_guarantee_particles=[],
        guarantee_publications=[],
        accepts_destruction_connections=False,
        destruction_connection_by_operation={},
    )
    return _action_names(plan).caller_inputs


def test_local_position_names():
    plan = action_plan.ActionPlan(
        fragments=[],
        execute_fragments=[],
        caller_inputs=[],
        action_triggers=[],
        triggered_action_inputs=[],
        triggers_for_destroyed_callee_guarantee_particles=[],
        guarantee_publications=[],
        accepts_destruction_connections=False,
        destruction_connection_by_operation={},
    )
    definition = _action_definition(("first", "second"))

    assert _action_names(plan, definition=definition).local_positions == {
        "first": "local_position_first",
        "second": "local_position_second",
    }


def test_action_parent_input_name():
    action_parent = operation_graph_model.ActionParentLastOperationNode(
        node_id=0, depends_on=()
    )

    assert _input_method_names(action_parent) == {action_parent: "accept_action_parent"}


def test_requirement_input_names_include_required_state():
    empty = _requirement_input("empty", action_contract.PositionOccupancyState.EMPTY)
    occupied = _requirement_input(
        "occupied", action_contract.PositionOccupancyState.OCCUPIED
    )

    assert _input_method_names(empty, occupied) == {
        empty: "accept_when_empty_position_empty",
        occupied: "accept_when_occupied_position_occupied",
    }


def test_semantic_prefixes_do_not_conflict_with_position_names():
    empty_rule = _empty_rule_input("source")
    empty_requirement = _requirement_input(
        "empty", action_contract.PositionOccupancyState.EMPTY
    )
    occupied_requirement = _requirement_input(
        "source", action_contract.PositionOccupancyState.OCCUPIED
    )
    named_for_empty_rule = _requirement_input(
        "source_for_empty_rule", action_contract.PositionOccupancyState.OCCUPIED
    )
    named_when_empty = _requirement_input(
        "source_when_empty", action_contract.PositionOccupancyState.OCCUPIED
    )
    named_when_occupied = _requirement_input(
        "source_when_occupied", action_contract.PositionOccupancyState.OCCUPIED
    )

    assert _input_method_names(
        empty_rule,
        empty_requirement,
        occupied_requirement,
        named_for_empty_rule,
        named_when_empty,
        named_when_occupied,
    ) == {
        empty_rule: "accept_for_empty_rule_position_source",
        empty_requirement: "accept_when_empty_position_empty",
        occupied_requirement: "accept_when_occupied_position_source",
        named_for_empty_rule: "accept_when_occupied_position_source_for_empty_rule",
        named_when_empty: "accept_when_occupied_position_source_when_empty",
        named_when_occupied: "accept_when_occupied_position_source_when_occupied",
    }


def test_fragments_skip_a_normalized_source_suffix():
    naturally_suffixed = _create_fragment("/item/name_2")
    separated_path = _create_fragment("/item/name")
    underscored = _create_fragment("/item_name")
    fragments = [naturally_suffixed, separated_path, underscored]
    plan = action_plan.ActionPlan(
        fragments=fragments,
        execute_fragments=fragments,
        caller_inputs=[],
        action_triggers=[],
        triggered_action_inputs=[],
        triggers_for_destroyed_callee_guarantee_particles=[],
        guarantee_publications=[],
        accepts_destruction_connections=False,
        destruction_connection_by_operation={},
    )

    names = _action_names(plan)

    assert names.fragments == {
        naturally_suffixed: "create_global_position_item_name_2",
        separated_path: "create_global_position_item_name",
        underscored: "create_global_position_item_name_3",
    }


def test_fragment_names_preserve_external_universes_and_multiverse():
    first_universe = _create_fragment("my.domain.com:first:/item")
    second_universe = _create_fragment("my.domain.com:second:/item")
    external_multiverse = _create_fragment("mv:other.example:other_lib:/run")
    fragments = [first_universe, second_universe, external_multiverse]
    plan = action_plan.ActionPlan(
        fragments=fragments,
        execute_fragments=fragments,
        caller_inputs=[],
        action_triggers=[],
        triggered_action_inputs=[],
        triggers_for_destroyed_callee_guarantee_particles=[],
        guarantee_publications=[],
        accepts_destruction_connections=False,
        destruction_connection_by_operation={},
    )

    names = _action_names(plan)

    assert names.fragments == {
        first_universe: "create_global_position_my_domain_com_first_item",
        second_universe: "create_global_position_my_domain_com_second_item",
        external_multiverse: ("create_global_position_mv_other_example_other_lib_run"),
    }


def test_repeated_action_trigger_skips_a_source_suffix(
    validate_project: conftest.ValidateProject,
):
    naturally_suffixed, first, second = _action_triggers(validate_project)
    action_triggers = [naturally_suffixed, first, second]
    plan = action_plan.ActionPlan(
        fragments=[],
        execute_fragments=[],
        caller_inputs=[],
        action_triggers=[
            action_plan.ActionTriggerPlan(
                action_trigger=action_trigger,
                created_destruction_connections=[],
                forwards_destruction_connections=False,
            )
            for action_trigger in action_triggers
        ],
        triggered_action_inputs=[],
        triggers_for_destroyed_callee_guarantee_particles=[],
        guarantee_publications=[],
        accepts_destruction_connections=False,
        destruction_connection_by_operation={},
    )

    names = _action_names(plan)

    assert names.triggered_actions == {
        naturally_suffixed: action_names.TriggeredActionNames(
            canonical_name="trigger_position_gateway__global_action_worker_2",
            initializer_name=(
                "init_trigger_position_gateway__global_action_worker_2__execution"
            ),
            execution_name=(
                "trigger_position_gateway__global_action_worker_2__execution"
            ),
        ),
        first: action_names.TriggeredActionNames(
            canonical_name="trigger_position_gateway__global_action_worker",
            initializer_name=(
                "init_trigger_position_gateway__global_action_worker__execution"
            ),
            execution_name="trigger_position_gateway__global_action_worker__execution",
        ),
        second: action_names.TriggeredActionNames(
            canonical_name="trigger_position_gateway__global_action_worker_3",
            initializer_name=(
                "init_trigger_position_gateway__global_action_worker_3__execution"
            ),
            execution_name=(
                "trigger_position_gateway__global_action_worker_3__execution"
            ),
        ),
    }


def test_destruction_connection_names_use_action_trigger(
    validate_project: conftest.ValidateProject,
):
    _, trigger, _ = _action_triggers(validate_project)
    destroyed_position = _position("/destroyed")
    destruction_fact = operation_graph_model.DestructionFact(
        destroyed_position,
        trigger.callee_action_name,
    )
    destruction_start = operation_graph_model.ActionParentLastOperationNode(
        node_id=0,
        depends_on=(),
    )
    first_destroy = operation_graph_model.DestructionFactDestroyNode(
        node_id=1,
        depends_on=(),
        target=destroyed_position,
        destruction_fact=destruction_fact,
        destruction_position=(),
        dependencies_before_caller_contribution=(destruction_start,),
        dependencies_after_caller_contribution=(),
    )
    second_destroy = operation_graph_model.DestructionFactDestroyNode(
        node_id=2,
        depends_on=(),
        target=destroyed_position,
        destruction_fact=destruction_fact,
        destruction_position=(),
        dependencies_before_caller_contribution=(destruction_start,),
        dependencies_after_caller_contribution=(),
    )
    first_connection = action_plan.DestructionConnection(
        operation_graph_model.DestructionOperation(
            trigger.callee_action_name,
            first_destroy,
        ),
        [],
        [],
        [],
    )
    second_connection = action_plan.DestructionConnection(
        operation_graph_model.DestructionOperation(
            trigger.callee_action_name,
            second_destroy,
        ),
        [],
        [],
        [],
    )
    plan = action_plan.ActionPlan(
        fragments=[],
        execute_fragments=[],
        caller_inputs=[],
        action_triggers=[
            action_plan.ActionTriggerPlan(
                action_trigger=trigger,
                created_destruction_connections=[
                    first_connection,
                    second_connection,
                ],
                forwards_destruction_connections=False,
            )
        ],
        triggered_action_inputs=[],
        triggers_for_destroyed_callee_guarantee_particles=[],
        guarantee_publications=[],
        accepts_destruction_connections=False,
        destruction_connection_by_operation={},
    )

    names = _action_names(plan)

    assert names.destruction_connections == {
        first_connection: (
            "destruction_connection_trigger_position_gateway__global_action_worker"
        ),
        second_connection: (
            "destruction_connection_trigger_position_gateway__global_action_worker_2"
        ),
    }


def test_continue_destroy_method_uses_destroy_fragment_name():
    definition = _action_definition()
    destroyed_position = _position("/destroyed")
    destruction_fact = operation_graph_model.DestructionFact(
        destroyed_position,
        definition.typed_name,
    )
    destruction_start = operation_graph_model.ActionParentLastOperationNode(
        node_id=0,
        depends_on=(),
    )
    destroy = operation_graph_model.DestructionFactDestroyNode(
        node_id=1,
        depends_on=(),
        target=destroyed_position,
        destruction_fact=destruction_fact,
        destruction_position=(),
        dependencies_before_caller_contribution=(destruction_start,),
        dependencies_after_caller_contribution=(),
    )
    fragment = action_plan.DestructionActionFragment([destroy])
    plan = action_plan.ActionPlan(
        fragments=[fragment],
        execute_fragments=[],
        caller_inputs=[],
        action_triggers=[],
        triggered_action_inputs=[],
        triggers_for_destroyed_callee_guarantee_particles=[],
        guarantee_publications=[],
        accepts_destruction_connections=False,
        destruction_connection_by_operation={},
    )

    names = _action_names(plan, definition=definition)

    assert names.continue_destroy_methods == {
        fragment: "continue_destroy_global_position_destroyed"
    }
