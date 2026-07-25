from define.compiler import ast, test_helpers
from define.compiler.codegen import action_plan
from define.compiler.validator.reference_graph import (
    action_contract,
    operation_graph,
)


def _action_definition(path: str) -> ast.ActionDefinition:
    program = test_helpers.parse_and_transform(
        f"""\
define the potential action<example.com:test:{path}> {{
    it happens when {{
        this particle is created.
    }} and it does {{
        define the position<item>.
        create a particle in position<item>.
    }}
}}
"""
    )
    definition = program.definitions[0]
    assert isinstance(definition, ast.ActionDefinition)
    return definition


def _position_reference(chained_name: str) -> ast.PositionReference:
    program = test_helpers.parse_and_transform(
        f"""\
define the potential action<example.com:test:/references> {{
    it happens when {{
        this particle is created.
    }} and it does {{
        create a particle in {chained_name}.
    }}
}}
"""
    )
    definition = program.definitions[0]
    assert isinstance(definition, ast.ActionDefinition)
    statement = definition.action_statements.statements[0]
    assert isinstance(statement, ast.CreateParticleStatement)
    return statement.target_position


def _position(name: str) -> ast.PositionReference:
    return _position_reference(f"position<{name}>")


def _work_action_name() -> ast.GlobalTypedNameReference:
    position = _position_reference("position<item>::action</work>::position<trigger>")
    action_name = position.get_last_action()
    assert action_name is not None
    return action_name


_DUMMY_ACTION = _action_definition("/dummy")
_ACTION = _work_action_name()


def _entry_plan(graph: operation_graph.OperationGraph) -> action_plan.ActionPlan:
    graphs = operation_graph.OperationGraphs()
    graphs[_DUMMY_ACTION.typed_name] = graph
    return action_plan.ActionPlans(graphs, _DUMMY_ACTION.typed_name).plan_for(
        _DUMMY_ACTION
    )


def _triggered_plan(graph: operation_graph.OperationGraph) -> action_plan.ActionPlan:
    graphs = operation_graph.OperationGraphs()
    graphs[_DUMMY_ACTION.typed_name] = graph
    return action_plan.ActionPlans(graphs, _ACTION).plan_for(_DUMMY_ACTION)


def _fragment_operations(
    fragment: action_plan.ActionFragment,
) -> tuple[operation_graph.PositionOperationNode, ...]:
    return tuple(fragment.operations)


def _empty_requirement(
    position: ast.PositionReference,
) -> dict[tuple[str, ...], action_contract.PositionRequirement]:
    return {
        position.canonical_chained_name_tuple: action_contract.PositionRequirement(
            required_state=action_contract.PositionOccupancyState.EMPTY,
            position=position,
            inferred_at=position.location,
            enclosing_action=_DUMMY_ACTION,
        )
    }


def test_serial_operations_form_one_fragment():
    graph = operation_graph.OperationGraph({})
    item = _position("item")
    create = graph.record_create(item)
    destroy = graph.record_destroy(item, ())

    plan = _entry_plan(graph)

    assert len(plan.fragments) == 1
    assert _fragment_operations(plan.fragments[0]) == (create, destroy)
    assert plan.fragments[0].dependency_count == 0
    assert plan.execute_fragments == [plan.fragments[0]]
    assert plan.triggered_action_inputs == []


def test_triggered_action_has_no_execute_fragments():
    graph = operation_graph.OperationGraph({})
    _ = graph.record_create(_position("item"))

    plan = _triggered_plan(graph)

    assert plan.execute_fragments == []


def test_fan_out_forms_parallel_serial_fragments():
    graph = operation_graph.OperationGraph({})
    first = _position("first")
    second = _position("second")
    first_create = graph.record_create(first)
    first_destroy = graph.record_destroy(first, ())
    second_create = graph.record_create(second)
    second_destroy = graph.record_destroy(second, ())

    plan = _entry_plan(graph)

    assert [_fragment_operations(fragment) for fragment in plan.fragments] == [
        (first_create, first_destroy),
        (second_create, second_destroy),
    ]
    assert plan.caller_inputs == []


def test_join_starts_a_new_fragment():
    graph = operation_graph.OperationGraph({})
    source = _position("source")
    destination = _position("destination")
    source_create = graph.record_create(source)
    destination_create = graph.record_create(destination)
    move = graph.record_move(source, destination, ())

    plan = _entry_plan(graph)

    assert [_fragment_operations(fragment) for fragment in plan.fragments] == [
        (source_create,),
        (destination_create,),
        (move,),
    ]
    assert plan.fragments[2].dependency_count == 2
    assert plan.fragments[0].successor_fragments == [plan.fragments[2]]
    assert plan.fragments[1].successor_fragments == [plan.fragments[2]]


def test_entry_action_resolves_independent_empty_requirement_away():
    item = _position("item")
    destination = _position("destination")
    graph = operation_graph.OperationGraph(_empty_requirement(destination))
    create = graph.record_create(item)
    move = graph.record_move(item, destination, ())

    plan = _entry_plan(graph)

    assert [_fragment_operations(fragment) for fragment in plan.fragments] == [
        (create, move)
    ]


def test_triggered_action_preserves_independent_caller_input():
    item = _position("item")
    destination = _position("destination")
    graph = operation_graph.OperationGraph(_empty_requirement(destination))
    create = graph.record_create(item)
    move = graph.record_move(item, destination, ())

    plan = _triggered_plan(graph)

    assert [_fragment_operations(fragment) for fragment in plan.fragments] == [
        (create,),
        (move,),
    ]
    assert plan.fragments[1].dependency_count == 2
    assert plan.fragments[0].successor_fragments == [plan.fragments[1]]
    assert [caller_input.fragments for caller_input in plan.caller_inputs] == [
        [plan.fragments[0]],
        [plan.fragments[1]],
    ]


def test_callee_continuation_ends_a_direct_call_chain():
    caller_definition = _DUMMY_ACTION
    callee_definition = _action_definition("/work")
    caller_graph = operation_graph.OperationGraph({})
    item = _position("item")
    create = caller_graph.record_create(item)
    callee_position = _position_reference(
        "position<item>::action</work>::position<trigger>"
    )
    callee_reference = callee_position.get_chain_to_last_action()
    assert callee_reference is not None
    trigger = caller_graph.record_action_trigger(
        callee_reference,
        item,
        (),
        (),
        acting_on_preceding_child_operations=(),
        required_preceding_child_operations=(),
    )
    destroy = caller_graph.record_destroy(item, ())
    callee_graph = operation_graph.OperationGraph({})
    _ = callee_graph.record_create(_position("work"))
    graphs = operation_graph.OperationGraphs()
    graphs[callee_definition.typed_name] = callee_graph
    graphs[caller_definition.typed_name] = caller_graph

    plans = action_plan.ActionPlans(graphs, caller_definition.typed_name)
    _ = plans.plan_for(callee_definition)
    plan = plans.plan_for(caller_definition)

    assert [_fragment_operations(fragment) for fragment in plan.fragments] == [
        (create,),
        (destroy,),
    ]
    assert plan.execute_fragments == [plan.fragments[0]]
    (action_trigger,) = plan.action_triggers
    assert action_trigger is trigger
    (triggered_input,) = plan.triggered_action_inputs
    assert plan.fragments[0].triggered_action_successors == [action_trigger]
    assert plan.fragments[0].triggered_input_successors == [triggered_input]
    assert plan.fragments[0].execution_input_successors == [triggered_input]
    assert triggered_input.dependency_count == 2


def test_triggered_action_input_uses_its_resolved_caller_dependency():
    caller_definition = _DUMMY_ACTION
    callee_definition = _action_definition("/work")
    caller_graph = operation_graph.OperationGraph({})
    gateway = _position("gateway")
    gateway_create = caller_graph.record_create(gateway)
    trigger_position = _position_reference(
        "position<gateway>::action</work>::position<trigger>"
    )
    callee = trigger_position.get_chain_to_last_action()
    assert callee is not None
    trigger_create = caller_graph.record_create(trigger_position)
    _ = caller_graph.record_action_trigger(
        callee,
        trigger_position,
        (),
        (),
        acting_on_preceding_child_operations=(),
        required_preceding_child_operations=(),
    )
    output = _position("output")
    callee_graph = operation_graph.OperationGraph(_empty_requirement(output))
    _ = callee_graph.record_create(output)
    graphs = operation_graph.OperationGraphs()
    graphs[callee_definition.typed_name] = callee_graph
    graphs[caller_definition.typed_name] = caller_graph

    plans = action_plan.ActionPlans(graphs, caller_definition.typed_name)
    _ = plans.plan_for(callee_definition)
    caller_plan = plans.plan_for(caller_definition)

    assert [_fragment_operations(fragment) for fragment in caller_plan.fragments] == [
        (gateway_create,),
        (trigger_create,),
    ]
    (action_trigger,) = caller_plan.action_triggers
    (triggered_input,) = caller_plan.triggered_action_inputs
    assert caller_plan.fragments[0].triggered_input_successors == [triggered_input]
    assert caller_plan.fragments[1].triggered_action_successors == [action_trigger]
    assert caller_plan.fragments[1].execution_input_successors == [triggered_input]


def test_guarantee_publication_ends_a_triggered_action_direct_call_chain():
    graph = operation_graph.OperationGraph({})
    first = _position("first")
    second = _position("second")
    first_create = graph.record_create(first)
    move = graph.record_move(first, second, ())
    refill_first = graph.record_create(first)
    graph.record_guaranteed_positions((second.canonical_chained_name_tuple,))

    entry_plan = _entry_plan(graph)
    triggered_plan = _triggered_plan(graph)

    assert [_fragment_operations(fragment) for fragment in entry_plan.fragments] == [
        (first_create, move, refill_first)
    ]
    assert [
        _fragment_operations(fragment) for fragment in triggered_plan.fragments
    ] == [
        (first_create, move),
        (refill_first,),
    ]
    assert len(triggered_plan.guarantee_publications) == 1
    publication = triggered_plan.guarantee_publications[0]
    assert publication.operation is move
    assert publication.guaranteed_source is None
    assert publication.guaranteed_target == second.canonical_chained_name_tuple
    assert triggered_plan.fragments[0].guarantee_publications == [publication]


def test_move_guarantee_publication_separates_source_and_target():
    graph = operation_graph.OperationGraph({})
    source = _position("source")
    target = _position("target")
    _ = graph.record_create(source)
    move = graph.record_move(source, target, ())
    graph.record_guaranteed_positions(
        (
            source.canonical_chained_name_tuple,
            target.canonical_chained_name_tuple,
        )
    )

    plan = _triggered_plan(graph)

    assert len(plan.guarantee_publications) == 1
    publication = plan.guarantee_publications[0]
    assert publication.operation is move
    assert publication.guaranteed_source == source.canonical_chained_name_tuple
    assert publication.guaranteed_target == target.canonical_chained_name_tuple
