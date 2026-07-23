from define.compiler import ast
from define.compiler.validator.reference_graph import (
    operation_graph,
    operation_graph_action_resolver,
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


def test_resolved_action_keeps_local_operations_and_caller_inputs_distinct():
    graph = operation_graph.OperationGraph({})
    work = _position("work")
    create_id = graph.record_create(work)
    destroy_id = graph.record_destroy(work, ())
    resolved = operation_graph_action_resolver.ActionResolver(graph, {}).resolve()

    create_dependencies = resolved.dependencies_by_operation_node_id[create_id]
    assert create_dependencies.action_inputs == (graph.nodes[0],)
    assert resolved.dependencies_by_operation_node_id[
        destroy_id
    ] == operation_graph_action_resolver.ActionDependencies(
        local_operation_node_ids=(create_id,)
    )


def test_resolved_action_binds_action_parent_at_one_action_boundary():
    worker_action = _action("/worker")
    caller_graph = operation_graph.OperationGraph({})
    trigger_position = _position("run")
    _ = caller_graph.record_create(trigger_position)
    trigger = caller_graph.record_action_trigger(
        _action_reference(worker_action),
        trigger_position,
        (),
        (),
        acting_on_preceding_child_operations=(),
        required_preceding_child_operations=(),
    )
    callee_graph = operation_graph.OperationGraph({})
    _ = callee_graph.record_create(_position("work"))
    resolved_callee = operation_graph_action_resolver.ActionResolver(
        callee_graph, {}
    ).resolve()
    resolved = operation_graph_action_resolver.ActionResolver(
        caller_graph, {worker_action: resolved_callee}
    ).resolve()
    (resolved_trigger,) = resolved.action_triggers
    action_parent = caller_graph.nodes[trigger.action_parent_last_operation_node_id]
    assert isinstance(action_parent, operation_graph.ActionParentLastOperationNode)

    assert resolved_trigger == operation_graph_action_resolver.ResolvedActionTrigger(
        trigger,
        (
            operation_graph_action_resolver.ResolvedActionTriggerInput(
                callee_input=resolved_callee.inputs[0],
                caller_dependencies=operation_graph_action_resolver.ActionDependencies(
                    action_inputs=(action_parent,)
                ),
                callee_dependency_node_ids=(),
            ),
        ),
    )
    (caller_input,) = resolved.inputs
    assert isinstance(caller_input, operation_graph.OperationNode)
    assert caller_input.node_id == trigger.action_parent_last_operation_node_id
