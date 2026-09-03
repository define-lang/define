from __future__ import annotations

import typing

from define.compiler import ast, test_helpers
from define.compiler.codegen import action_plan
from define.compiler.codegen.literal.python import (
    action_context,
    action_names,
)
from define.compiler.data_structures import typed_name_dict
from define.compiler.validator import test_helpers as validator_test_helpers
from define.compiler.validator.reference_graph import (
    action_contract,
    operation_graph_model,
)

if typing.TYPE_CHECKING:
    import collections.abc

    from define.compiler import conftest
    from define.compiler.validator.reference_graph import (
        operation_graph_action_resolver,
    )


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


def _action_executions(
    validate_project: conftest.ValidateProject,
) -> collections.abc.Sequence[operation_graph_model.ActionExecution]:
    result = validate_project(
        {
            "test.dfn": """\
define the potential action<my.domain.com:my_lib:/test> {
    it happens when {
        this particle is created.
    } and it does {
        define the position<gateway> {
            it may only contain particles where {
                it has the action</worker>.
                it has the action</worker_2>.
            }
        }
        create a particle in position<gateway>.
        create a particle in position<gateway>::action</worker_2>::position<trigger_pos>.
        create a particle in position<gateway>::action</worker>::position<trigger_pos>.
        destroy the particle in position<gateway>::action</worker>::position<trigger_pos>.
        create a particle in position<gateway>::action</worker>::position<trigger_pos>.
        destroy the particle in position<gateway>::action</worker>::position<trigger_pos>.
        destroy the particle in position<gateway>::action</worker_2>::position<trigger_pos>.
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
    ].executions


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


def _requirement_binding_hole(
    position_name: str,
    required_state: action_contract.PositionOccupancyState,
) -> operation_graph_model.RequirementNode:
    action_parent_binding_hole = operation_graph_model.ActionParentLastOperationNode(
        node_id=0
    )
    return operation_graph_model.RequirementNode(
        node_id=1,
        depends_on=(action_parent_binding_hole,),
        requirement=operation_graph_model.OperationGraphRequirement(
            requirement_position=(f"position<{position_name}>",),
            required_state=required_state,
        ),
    )


def _empty_rule_binding_hole(
    position_name: str,
) -> operation_graph_model.EmptyRuleBindingHole:
    return operation_graph_model.EmptyRuleBindingHole(
        requirement_position=(f"position<{position_name}>",),
        collected_child_operation_positions=frozenset(),
        collected_operation_positions=(),
        prerequisite_binding_holes=(),
    )


def _generated_action_interface() -> action_context.GeneratedActionInterface:
    return action_context.GeneratedActionInterface(
        needs_action=False,
        binding_holes={},
        guarantee_names_by_operation={},
        execution_member_names={},
        join_member_names={},
        fragment_method_names={},
        destruction_continuations={},
    )


def _action_names(
    plan: action_plan.ActionPlan,
    *,
    definition: ast.ActionDefinition | None = None,
) -> action_names.ActionNames:
    generated_actions = typed_name_dict.TypedNameDict[
        ast.GlobalTypedName, action_context.GeneratedActionInterface
    ]()
    for planned_execution in plan.action_executions.values():
        action_execution = planned_execution.execution
        generated_actions[action_execution.callee_action_name] = (
            _generated_action_interface()
        )
    return action_names.ActionNameGenerator(
        definition or _action_definition(),
        plan,
        generated_actions,
    ).generate()


def _binding_hole_method_names(
    *binding_holes: operation_graph_action_resolver.ResolvedBindingHole,
) -> dict[operation_graph_model.BindingHole, str]:
    fragment = _create_fragment("/consumer")
    binding_hole_fanouts: dict[
        operation_graph_action_resolver.ResolvedBindingHole,
        action_plan.BindingHoleFanout,
    ] = {}
    for binding_hole in binding_holes:
        fanout = action_plan.BindingHoleFanout(binding_hole)
        fanout.continuations.append(fragment)
        binding_hole_fanouts[binding_hole] = fanout
    plan = action_plan.ActionPlan(
        fragments=[fragment],
        binding_hole_fanouts=binding_hole_fanouts,
        action_executions={},
        creation_inits=action_plan.ActionExecutionInits(),
        callee_binding_method_plans=[],
        guarantee_consumption_plans=[],
        init_binding_hole_by_action_execution={},
        accepts_destruction_connections=False,
        destruction_connection_by_operation={},
        caller_resolved_joins=[],
    )
    names = _action_names(plan)
    return {
        binding_hole: binding_hole_names.method_name
        for binding_hole, binding_hole_names in names.binding_holes.items()
    }


def test_local_position_names():
    plan = action_plan.ActionPlan(
        fragments=[],
        binding_hole_fanouts={},
        action_executions={},
        creation_inits=action_plan.ActionExecutionInits(),
        callee_binding_method_plans=[],
        guarantee_consumption_plans=[],
        init_binding_hole_by_action_execution={},
        accepts_destruction_connections=False,
        destruction_connection_by_operation={},
        caller_resolved_joins=[],
    )
    definition = _action_definition(("first", "second"))

    assert _action_names(plan, definition=definition).local_positions == {
        "first": "local_position_first",
        "second": "local_position_second",
    }


def test_action_parent_binding_hole_method_name():
    action_parent = operation_graph_model.ActionParentLastOperationNode(node_id=0)

    assert _binding_hole_method_names(action_parent) == {
        action_parent: "on_action_parent_occupied"
    }


def test_requirement_binding_hole_method_names_include_required_state():
    empty = _requirement_binding_hole(
        "empty", action_contract.PositionOccupancyState.EMPTY
    )
    occupied = _requirement_binding_hole(
        "occupied", action_contract.PositionOccupancyState.OCCUPIED
    )

    assert _binding_hole_method_names(empty, occupied) == {
        empty: "accept_when_empty_position_empty",
        occupied: "accept_when_occupied_position_occupied",
    }


def test_semantic_prefixes_do_not_conflict_with_position_names():
    empty_rule = _empty_rule_binding_hole("source")
    empty_requirement = _requirement_binding_hole(
        "empty", action_contract.PositionOccupancyState.EMPTY
    )
    occupied_requirement = _requirement_binding_hole(
        "source", action_contract.PositionOccupancyState.OCCUPIED
    )
    named_for_empty_rule = _requirement_binding_hole(
        "source_for_empty_rule", action_contract.PositionOccupancyState.OCCUPIED
    )
    named_when_empty = _requirement_binding_hole(
        "source_when_empty", action_contract.PositionOccupancyState.OCCUPIED
    )
    named_when_occupied = _requirement_binding_hole(
        "source_when_occupied", action_contract.PositionOccupancyState.OCCUPIED
    )

    assert _binding_hole_method_names(
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
        binding_hole_fanouts={},
        action_executions={},
        creation_inits=action_plan.ActionExecutionInits(),
        callee_binding_method_plans=[],
        guarantee_consumption_plans=[],
        init_binding_hole_by_action_execution={},
        accepts_destruction_connections=False,
        destruction_connection_by_operation={},
        caller_resolved_joins=[],
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
        binding_hole_fanouts={},
        action_executions={},
        creation_inits=action_plan.ActionExecutionInits(),
        callee_binding_method_plans=[],
        guarantee_consumption_plans=[],
        init_binding_hole_by_action_execution={},
        accepts_destruction_connections=False,
        destruction_connection_by_operation={},
        caller_resolved_joins=[],
    )

    names = _action_names(plan)

    assert names.fragments == {
        first_universe: "create_global_position_my_domain_com_first_item",
        second_universe: "create_global_position_my_domain_com_second_item",
        external_multiverse: ("create_global_position_mv_other_example_other_lib_run"),
    }


def test_repeated_action_execution_skips_a_source_suffix(
    validate_project: conftest.ValidateProject,
):
    naturally_suffixed, first, second = _action_executions(validate_project)
    action_executions = [naturally_suffixed, first, second]
    planned_action_executions: dict[
        operation_graph_model.ActionExecution,
        action_plan.ActionExecutionPlan,
    ] = {}
    for action_execution in action_executions:
        planned_action_executions[action_execution] = action_plan.ActionExecutionPlan(
            execution=action_execution,
        )
    plan = action_plan.ActionPlan(
        fragments=[],
        binding_hole_fanouts={},
        action_executions=planned_action_executions,
        creation_inits=action_plan.ActionExecutionInits(),
        callee_binding_method_plans=[],
        guarantee_consumption_plans=[],
        init_binding_hole_by_action_execution={},
        accepts_destruction_connections=False,
        destruction_connection_by_operation={},
        caller_resolved_joins=[],
    )

    names = _action_names(plan)

    assert names.action_executions == {
        naturally_suffixed: action_names.ActionExecutionNames(
            canonical_name="position_gateway__action_worker_2",
            execution_name="execution_position_gateway__action_worker_2",
        ),
        first: action_names.ActionExecutionNames(
            canonical_name="position_gateway__action_worker",
            execution_name="execution_position_gateway__action_worker",
        ),
        second: action_names.ActionExecutionNames(
            canonical_name="position_gateway__action_worker_3",
            execution_name="execution_position_gateway__action_worker_3",
        ),
    }


def test_destruction_connection_names_use_action_execution(
    validate_project: conftest.ValidateProject,
):
    _, execution, _ = _action_executions(validate_project)
    destroyed_position = _position("/destroyed")
    destruction_fact = operation_graph_model.DestructionFact(
        destroyed_position,
        execution.callee_action_name,
    )
    first_destroy = operation_graph_model.DestructionFactDestroyNode(
        node_id=1,
        depends_on=(),
        target=destroyed_position,
        destruction_fact=destruction_fact,
        destruction_position=(),
        dependencies_before_caller_contribution=(),
        dependencies_after_caller_contribution=(),
    )
    second_destroy = operation_graph_model.DestructionFactDestroyNode(
        node_id=2,
        depends_on=(),
        target=destroyed_position,
        destruction_fact=destruction_fact,
        destruction_position=(),
        dependencies_before_caller_contribution=(),
        dependencies_after_caller_contribution=(),
    )
    first_connection = action_plan.DestructionConnection(
        operation_graph_model.DestructionOperation(
            execution.callee_action_name,
            first_destroy,
        ),
        [],
        0,
    )
    second_connection = action_plan.DestructionConnection(
        operation_graph_model.DestructionOperation(
            execution.callee_action_name,
            second_destroy,
        ),
        [],
        0,
    )
    plan = action_plan.ActionPlan(
        fragments=[],
        binding_hole_fanouts={},
        action_executions={
            execution: action_plan.ActionExecutionPlan(
                execution=execution,
                created_destruction_connections=[
                    first_connection,
                    second_connection,
                ],
            )
        },
        creation_inits=action_plan.ActionExecutionInits(),
        callee_binding_method_plans=[],
        guarantee_consumption_plans=[],
        init_binding_hole_by_action_execution={},
        accepts_destruction_connections=False,
        destruction_connection_by_operation={},
        caller_resolved_joins=[],
    )

    names = _action_names(plan)

    assert names.destruction_connections == {
        first_connection: "destruction_connection_position_gateway__action_worker",
        second_connection: "destruction_connection_position_gateway__action_worker_2",
    }


def test_continue_destroy_method_uses_destroy_fragment_name():
    definition = _action_definition()
    destroyed_position = _position("/destroyed")
    destruction_fact = operation_graph_model.DestructionFact(
        destroyed_position,
        definition.typed_name,
    )
    destroy = operation_graph_model.DestructionFactDestroyNode(
        node_id=1,
        depends_on=(),
        target=destroyed_position,
        destruction_fact=destruction_fact,
        destruction_position=(),
        dependencies_before_caller_contribution=(),
        dependencies_after_caller_contribution=(),
    )
    fragment = action_plan.DestructionActionFragment([destroy])
    plan = action_plan.ActionPlan(
        fragments=[fragment],
        binding_hole_fanouts={},
        action_executions={},
        creation_inits=action_plan.ActionExecutionInits(),
        callee_binding_method_plans=[],
        guarantee_consumption_plans=[],
        init_binding_hole_by_action_execution={},
        accepts_destruction_connections=False,
        destruction_connection_by_operation={},
        caller_resolved_joins=[],
    )

    names = _action_names(plan, definition=definition)

    assert names.continue_destroy_methods == {
        fragment: "continue_destroy_global_position_destroyed"
    }
