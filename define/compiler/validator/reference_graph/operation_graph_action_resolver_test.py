from define.compiler import ast
from define.compiler.validator.reference_graph import (
    action_contract,
    operation_graph,
    operation_graph_action_resolver,
    operation_graph_model,
)

_LOCATION = ast.start_of_file_location()
_FQUN = ast.Fqun(
    multiverse=None,
    authority=ast.Authority(name="my.domain.com", location=_LOCATION),
    universe=ast.Universe(name="my_lib", location=_LOCATION),
    location=_LOCATION,
)


def _action(path: str) -> ast.GlobalTypedNameReference:
    return ast.GlobalTypedNameReference(
        name_type=ast.NameType.ACTION,
        name_content=ast.ReferenceGlobalNameContent(
            fqun=None,
            path=ast.GlobalPathName(name=path, location=_LOCATION),
            location=_LOCATION,
        ),
        enclosing_fqun=_FQUN,
        location=_LOCATION,
    )


def _action_reference(action: ast.GlobalTypedNameReference) -> ast.ActionReference:
    return ast.ActionReference(typed_names=(action,), location=_LOCATION)


def _position(name: str) -> ast.PositionReference:
    return ast.PositionReference(
        typed_names=(
            ast.LocalTypedNameReference(
                name_type=ast.NameType.POSITION,
                name_content=ast.LocalNameContent(name=name, location=_LOCATION),
                location=_LOCATION,
            ),
        ),
        location=_LOCATION,
    )


def test_resolved_actions_retains_resolved_action():
    action = _action("/test")
    graph = operation_graph.OperationGraph()
    graphs = operation_graph.OperationGraphs()
    graphs[action] = graph
    resolved_actions = operation_graph_action_resolver.ResolvedActions(graphs)

    resolved = resolved_actions.resolve(action)

    assert resolved_actions[action] is resolved


def test_resolved_actions_reuses_resolved_action():
    action = _action("/test")
    graph = operation_graph.OperationGraph()
    graphs = operation_graph.OperationGraphs()
    graphs[action] = graph
    resolved_actions = operation_graph_action_resolver.ResolvedActions(graphs)
    resolved = resolved_actions.resolve(action)

    assert resolved_actions.resolve(action) is resolved


def test_resolved_action_keeps_local_operations_and_caller_inputs_distinct():
    action = _action("/test")
    graph = operation_graph.OperationGraph()
    work = _position("work")
    create = graph.record_create(work)
    destroy = graph.record_destroy(work, ())
    graphs = operation_graph.OperationGraphs()
    graphs[action] = graph
    resolved = operation_graph_action_resolver.ResolvedActions(graphs).resolve(action)

    (caller_input,) = resolved.caller_inputs
    assert isinstance(
        caller_input, operation_graph_action_resolver.ResolvedActionParentInput
    )
    assert caller_input.node is graph.nodes[0]
    assert caller_input.operation_consumers == [create]
    assert caller_input.triggered_input_consumers == []
    assert caller_input.destructor_trigger_consumers == []
    assert resolved.dependencies_by_operation[
        destroy
    ] == operation_graph_action_resolver.ActionDependencies([create], [])


def test_resolved_action_binds_action_parent_at_one_action_boundary():
    worker_action = _action("/worker")
    caller_graph = operation_graph.OperationGraph()
    trigger_position = _position("run")
    trigger_position_create = caller_graph.record_create(trigger_position)
    trigger = caller_graph.record_action_trigger(
        _action_reference(worker_action),
        trigger_position,
        (),
        is_destructor=False,
        acting_on_preceding_child_operations=(),
        required_preceding_child_operations=(),
    )
    callee_graph = operation_graph.OperationGraph()
    _ = callee_graph.record_create(_position("work"))
    caller_action = _action("/caller")
    graphs = operation_graph.OperationGraphs()
    graphs[worker_action] = callee_graph
    graphs[caller_action] = caller_graph
    resolved_actions = operation_graph_action_resolver.ResolvedActions(graphs)
    resolved_callee = resolved_actions.resolve(worker_action)
    resolved = resolved_actions.resolve(caller_action)
    (resolved_trigger,) = resolved.action_triggers
    action_parent = trigger.action_parent_last_operation
    assert isinstance(
        action_parent, operation_graph_model.ActionParentLastOperationNode
    )

    assert resolved_trigger.trigger is trigger
    assert len(resolved.action_triggers) == 1
    assert tuple(resolved.action_triggers.position_operations) == (
        trigger_position_create,
    )
    assert list(resolved.action_triggers.by_position_operation()) == [
        (trigger_position_create, [resolved_trigger])
    ]
    assert list(resolved.action_triggers.destructors_by_guarantee()) == []
    (resolved_input,) = resolved_trigger.inputs
    assert resolved_input.callee_input is resolved_callee.caller_inputs[0]
    assert (
        resolved_input.caller_dependencies
        == operation_graph_action_resolver.ActionDependencies([], [])
    )
    (caller_input,) = resolved.caller_inputs
    assert isinstance(
        caller_input, operation_graph_action_resolver.ResolvedActionParentInput
    )
    assert caller_input.node is action_parent
    assert resolved_input.caller_input_dependencies == (caller_input,)
    assert caller_input.operation_consumers == [trigger_position_create]
    assert caller_input.triggered_input_consumers == [resolved_input]
    assert caller_input.destructor_trigger_consumers == []


def test_requirement_input_fires_destructor():
    destructor_action = _action("/destructor")
    caller_graph = operation_graph.OperationGraph()
    item = _position("item")
    caller_graph.record_requirement(
        item, action_contract.PositionOccupancyState.OCCUPIED
    )
    destructor_trigger = caller_graph.record_action_trigger(
        ast.ActionReference(
            typed_names=(*item.typed_names, destructor_action),
            location=_LOCATION,
        ),
        item,
        (),
        is_destructor=True,
        acting_on_preceding_child_operations=(),
        required_preceding_child_operations=(),
    )
    destructor_graph = operation_graph.OperationGraph()
    _ = destructor_graph.record_create(_position("work"))
    caller_action = _action("/caller")
    graphs = operation_graph.OperationGraphs()
    graphs[destructor_action] = destructor_graph
    graphs[caller_action] = caller_graph
    resolved_actions = operation_graph_action_resolver.ResolvedActions(graphs)
    _ = resolved_actions.resolve(destructor_action)
    resolved = resolved_actions.resolve(caller_action)

    assert isinstance(
        destructor_trigger.trigger_operation, operation_graph_model.RequirementNode
    )
    (resolved_destructor_trigger,) = resolved.action_triggers
    (resolved_destructor_input,) = resolved_destructor_trigger.inputs
    (caller_input,) = resolved.caller_inputs
    assert isinstance(
        caller_input, operation_graph_action_resolver.ResolvedRequirementInput
    )
    assert caller_input.node is destructor_trigger.trigger_operation
    assert resolved_destructor_input.caller_input_dependencies == (caller_input,)
    assert caller_input.triggered_input_consumers == [
        resolved_destructor_input,
        resolved_destructor_input,
    ]
    assert caller_input.destructor_trigger_consumers == [resolved_destructor_trigger]
    assert tuple(resolved.action_triggers.position_operations) == ()
    assert list(resolved.action_triggers.destructors_by_guarantee()) == []
