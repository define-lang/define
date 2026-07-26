"""Render operation graphs as readable maps for tests."""

from define.compiler.validator.reference_graph import (
    operation_graph,
    operation_graph_labeler,
    operation_graph_resolver,
)

# Every operation graph test names the action it validates /test.
_ENTRY_POINT_ACTION_PATH = "/test"


def operation_dependencies(
    operation_graphs: operation_graph.OperationGraphs,
) -> dict[str, list[str]]:
    """Return a label for each operation the entry-point action performs or triggers, mapped to the labels it depends on."""
    for typed_name in operation_graphs:
        if typed_name.name_content.path.name == _ENTRY_POINT_ACTION_PATH:
            resolved = operation_graph_resolver.ResolvedOperationGraphBuilder(
                operation_graphs, typed_name
            ).build()
            labels = operation_graph_labeler.OperationGraphLabeler(
                operation_graphs
            ).resolved_operation_labels(resolved)
            return {
                label: [labels[dependency] for dependency in operation.dependencies]
                for operation, label in labels.items()
            }
    raise KeyError(_ENTRY_POINT_ACTION_PATH)


def action_graph(
    operation_graphs: operation_graph.OperationGraphs,
) -> list[tuple[str, str]]:
    """Return each action's directly-triggered actions as (source, target) name pairs.

    An action that triggers the same action twice yields two edges. Actions appear
    in reference-graph post-order and their triggerings in the order they perform
    them, so the result is deterministic. A reference-graph diamond can still make
    two sibling actions' relative order nondeterministic; assertions spanning such
    actions should compare ``action_graph_set``.
    """
    edges: list[tuple[str, str]] = []
    for action, graph in operation_graphs.items():
        for trigger in graph.triggers:
            edges.append(
                (action.source_typed_name, trigger.callee_action_name.full_typed_name)
            )
    return edges


def action_graph_set(
    operation_graphs: operation_graph.OperationGraphs,
) -> set[tuple[str, str]]:
    """Return ``action_graph`` as a set, for assertions whose edge order is nondeterministic."""
    return set(action_graph(operation_graphs))
