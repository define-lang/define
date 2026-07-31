from define.compiler import ast
from define.compiler.validator.reference_graph import (
    operation_graph,
    operation_graph_resolver,
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


def test_repeated_action_triggers_create_distinct_executions():
    entry_action = _action("/test")
    worker_action = _action("/worker")
    entry_graph = operation_graph.OperationGraph({})
    first_trigger_position = _position("first")
    second_trigger_position = _position("second")
    _ = entry_graph.record_create(first_trigger_position)
    first_trigger = entry_graph.record_action_trigger(
        _action_reference(worker_action),
        first_trigger_position,
        (),
        acting_on_preceding_child_operations=(),
        required_preceding_child_operations=(),
    )
    _ = entry_graph.record_create(second_trigger_position)
    second_trigger = entry_graph.record_action_trigger(
        _action_reference(worker_action),
        second_trigger_position,
        (),
        acting_on_preceding_child_operations=(),
        required_preceding_child_operations=(),
    )
    worker_graph = operation_graph.OperationGraph({})
    worker_operation = _position("work")
    _ = worker_graph.record_create(worker_operation)
    graphs = operation_graph.OperationGraphs()
    graphs[entry_action] = entry_graph
    graphs[worker_action] = worker_graph

    resolved = operation_graph_resolver.ResolvedOperationGraphBuilder(
        graphs, entry_action
    ).build()

    (
        first_entry_node,
        second_entry_node,
        first_worker_node,
        second_worker_node,
    ) = resolved.operations
    assert first_entry_node.action_execution is resolved.entry_action_execution
    assert second_entry_node.action_execution is resolved.entry_action_execution
    assert resolved.entry_action_execution.triggered_by is None
    assert first_worker_node.action_execution is not second_worker_node.action_execution
    assert first_worker_node.action_execution.action == worker_action
    assert second_worker_node.action_execution.action == worker_action
    first_triggered_by = first_worker_node.action_execution.triggered_by
    second_triggered_by = second_worker_node.action_execution.triggered_by
    assert first_triggered_by is not None
    assert second_triggered_by is not None
    assert first_triggered_by.caller is resolved.entry_action_execution
    assert second_triggered_by.caller is resolved.entry_action_execution
    assert first_triggered_by.action_trigger.trigger is first_trigger
    assert second_triggered_by.action_trigger.trigger is second_trigger
    assert first_worker_node.operation.target == worker_operation
