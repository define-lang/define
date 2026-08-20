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


def _record_execution(
    builder: operation_graph.OperationGraphBuilder,
    callee: ast.GlobalTypedNameReference,
    trigger_name: str,
) -> operation_graph_model.ActionExecution:
    trigger_position = _position(trigger_name)
    _ = builder.record_create(trigger_position)
    return builder.record_action_execution(
        _action_reference(callee),
        trigger_position,
        (),
        is_destructor=False,
        acting_on_preceding_child_operations=(),
        required_preceding_child_operations=(),
    )


def test_resolved_actions_retains_resolved_action():
    action = _action("/test")
    graph = operation_graph.OperationGraphBuilder(action).finish()
    graphs = operation_graph.OperationGraphs()
    graphs[action] = graph
    resolved_actions = operation_graph_action_resolver.ResolvedActions(graphs)

    resolved = resolved_actions.resolve(action)

    assert resolved_actions[action] is resolved


def test_resolved_actions_reuses_resolved_action():
    action = _action("/test")
    graph = operation_graph.OperationGraphBuilder(action).finish()
    graphs = operation_graph.OperationGraphs()
    graphs[action] = graph
    resolved_actions = operation_graph_action_resolver.ResolvedActions(graphs)
    resolved = resolved_actions.resolve(action)

    assert resolved_actions.resolve(action) is resolved


def test_resolved_action_keeps_local_operations_and_binding_holes_distinct():
    action = _action("/test")
    builder = operation_graph.OperationGraphBuilder(action)
    work = _position("work")
    create = builder.record_create(work)
    destroy = builder.record_destroy(work, ())
    graph = builder.finish()
    graphs = operation_graph.OperationGraphs()
    graphs[action] = graph
    resolved = operation_graph_action_resolver.ResolvedActions(graphs).resolve(action)

    (binding_hole,) = resolved.binding_holes.in_binding_order
    assert binding_hole is graph.nodes[0]
    assert resolved.binding_holes_depended_on_by(create) == [binding_hole]
    assert tuple(resolved.local_operations_depended_on_by(destroy)) == (create,)
    assert not resolved.guarantee_dependencies_for(destroy)


def test_resolved_action_binds_action_parent_at_one_action_boundary():
    worker_action = _action("/worker")
    caller_action = _action("/caller")
    caller_builder = operation_graph.OperationGraphBuilder(caller_action)
    trigger_position = _position("run")
    trigger_position_create = caller_builder.record_create(trigger_position)
    execution = caller_builder.record_action_execution(
        _action_reference(worker_action),
        trigger_position,
        (),
        is_destructor=False,
        acting_on_preceding_child_operations=(),
        required_preceding_child_operations=(),
    )
    callee_builder = operation_graph.OperationGraphBuilder(worker_action)
    _ = callee_builder.record_create(_position("work"))
    graphs = operation_graph.OperationGraphs()
    graphs[worker_action] = callee_builder.finish()
    graphs[caller_action] = caller_builder.finish()
    resolved_actions = operation_graph_action_resolver.ResolvedActions(graphs)
    resolved_callee = resolved_actions.resolve(worker_action)
    resolved = resolved_actions.resolve(caller_action)
    (resolved_execution,) = resolved.action_executions
    action_parent = execution.action_parent_last_operation
    assert isinstance(
        action_parent, operation_graph_model.ActionParentLastOperationNode
    )

    assert resolved_execution.execution is execution
    assert len(resolved.action_executions) == 1
    assert resolved.action_executions_triggered_by(trigger_position_create) == [
        resolved_execution
    ]
    callee_binding_hole = resolved_callee.binding_holes.in_binding_order[0]
    callee_binding = resolved_execution.callee_bindings[callee_binding_hole]
    assert callee_binding.callee_binding_hole is callee_binding_hole
    assert (
        callee_binding.caller_dependencies
        == operation_graph_action_resolver.ActionDependencies([], [])
    )
    (binding_hole,) = resolved.binding_holes.in_binding_order
    assert binding_hole is action_parent
    assert callee_binding.caller_binding_holes == [binding_hole]
    assert resolved.binding_holes_depended_on_by(trigger_position_create) == [
        binding_hole
    ]
    assert execution.destructor_trigger_requirement is None


def test_requirement_binding_hole_fires_destructor():
    destructor_action = _action("/destructor")
    caller_action = _action("/caller")
    caller_builder = operation_graph.OperationGraphBuilder(caller_action)
    item = _position("item")
    caller_builder.record_requirement(
        item, action_contract.PositionOccupancyState.OCCUPIED
    )
    destructor_execution = caller_builder.record_action_execution(
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
    destructor_builder = operation_graph.OperationGraphBuilder(destructor_action)
    _ = destructor_builder.record_create(_position("work"))
    graphs = operation_graph.OperationGraphs()
    graphs[destructor_action] = destructor_builder.finish()
    graphs[caller_action] = caller_builder.finish()
    resolved_actions = operation_graph_action_resolver.ResolvedActions(graphs)
    resolved_destructor = resolved_actions.resolve(destructor_action)
    resolved = resolved_actions.resolve(caller_action)

    assert isinstance(
        destructor_execution.trigger_operation,
        operation_graph_model.RequirementNode,
    )
    (resolved_destructor_execution,) = resolved.action_executions
    (destructor_binding_hole,) = resolved_destructor.binding_holes.in_binding_order
    destructor_callee_binding = resolved_destructor_execution.callee_bindings[
        destructor_binding_hole
    ]
    (binding_hole,) = resolved.binding_holes.in_binding_order
    assert binding_hole is destructor_execution.trigger_operation
    assert destructor_callee_binding.caller_binding_holes == [binding_hole]
    assert destructor_execution.destructor_trigger_requirement is binding_hole
    assert all(
        not resolved.action_executions_triggered_by(operation)
        for operation in resolved.graph.particle_operations
    )


def test_nested_guarantee_binding_holes_are_resolved_without_publishing_every_path():
    depth = 12
    actions = [_action(f"/action_{index}") for index in range(depth + 1)]
    builders = [operation_graph.OperationGraphBuilder(action) for action in actions]
    selected_executions: list[operation_graph_model.ActionExecution] = []
    for index in range(depth):
        selected_executions.append(
            _record_execution(builders[index], actions[index + 1], "first")
        )
        _ = _record_execution(builders[index], actions[index + 1], "second")

    work = _position("work")
    _ = builders[-1].record_create(work)
    builders[-1].record_guaranteed_positions((work.canonical_chained_name_tuple,))
    _ = builders[0].record_guarantees(
        selected_executions[0],
        tuple(selected_executions[1:]),
        (
            (
                work.canonical_chained_name_tuple,
                (work.canonical_chained_name_tuple,),
            ),
        ),
        guarantee_action_chain=(),
        operation_graph_action_chain=(),
    )
    builders[0].record_guaranteed_positions((work.canonical_chained_name_tuple,))

    graphs = operation_graph.OperationGraphs()
    for action, builder in zip(actions, builders, strict=True):
        graphs[action] = builder.finish()
    resolved_actions = operation_graph_action_resolver.ResolvedActions(graphs)
    resolved = None
    for action in reversed(actions):
        resolved = resolved_actions.resolve(action)
    assert resolved is not None

    assert len(resolved.binding_holes.in_binding_order) == 1
    assert (
        len(
            resolved.binding_holes.binding_holes_depended_on_by_guaranteed_position(
                work.canonical_chained_name_tuple
            )
        )
        == 1
    )
    for action in actions[1:-1]:
        assert not resolved_actions[
            action
        ].binding_holes.binding_holes_depended_on_by_guaranteed_position(
            work.canonical_chained_name_tuple
        )
