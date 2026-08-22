"""Render operation graphs as readable maps for tests."""

from __future__ import annotations

import pprint

from define.compiler.validator.reference_graph import (
    operation_graph,
    operation_graph_labeler,
    operation_graph_resolver,
)

# Every operation graph test names the action it validates /test.
_ENTRY_POINT_ACTION_PATH = "/test"


def _operation_dependencies(
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


def assert_operation_dependencies(
    operation_graphs: operation_graph.OperationGraphs,
    expected: dict[str, list[str]],
):
    """Assert the complete, transitively minimal dependencies of the test action."""
    actual = _operation_dependencies(operation_graphs)
    assert_transitively_minimal_dependencies(actual)
    if actual != expected:
        message = "operation dependency mismatch:\n"
        message += f"actual:\n{pprint.pformat(actual)}\n"
        message += f"expected:\n{pprint.pformat(expected)}"
        raise AssertionError(message)


def assert_transitively_minimal_dependencies(
    dependencies: dict[str, list[str]],
):
    """Assert that no direct dependency is reachable through another path."""
    if dependencies != _transitively_minimal_dependencies(dependencies):
        raise AssertionError


def _transitively_minimal_dependencies(
    dependencies: dict[str, list[str]],
) -> dict[str, list[str]]:
    # An Operation Graph is a DAG. For every direct edge from an operation to a
    # dependency, remove the edge and search the entire remaining graph from the
    # operation. Keep the edge removed exactly when the dependency is still
    # reachable, so each removal preserves the graph's transitive closure. An edge
    # that was necessary when examined cannot become redundant after later removals,
    # because removing edges cannot create a new path. After every edge has been
    # examined, no remaining edge can be removed without changing reachability: the
    # result is therefore the DAG's unique transitive reduction. This costs
    # O(E * (V + E)), which is suitable for these small test graphs but not for
    # production Operation Graphs at compiler scale.
    minimal_dependencies = {
        operation: list(direct_dependencies)
        for operation, direct_dependencies in dependencies.items()
    }
    for operation, direct_dependencies in minimal_dependencies.items():
        dependency_index = 0
        while dependency_index < len(direct_dependencies):
            dependency = direct_dependencies.pop(dependency_index)
            if _has_dependency_path(operation, dependency, minimal_dependencies):
                continue
            direct_dependencies.insert(dependency_index, dependency)
            dependency_index += 1
    return minimal_dependencies


def _has_dependency_path(
    operation: str,
    dependency: str,
    dependencies: dict[str, list[str]],
) -> bool:
    visited = {operation}
    work = [operation]
    while work:
        current = work.pop()
        for direct_dependency in dependencies[current]:
            if direct_dependency == dependency:
                return True
            if direct_dependency not in visited:
                visited.add(direct_dependency)
                work.append(direct_dependency)
    return False


def action_graph(
    operation_graphs: operation_graph.OperationGraphs,
) -> list[tuple[str, str]]:
    """Return each action's directly-triggered actions as (source, target) name pairs.

    An action that triggers the same action twice yields two edges. Actions appear
    in reference-graph post-order and their Action Executions in the order they perform
    them, so the result is deterministic. A reference-graph diamond can still make
    two sibling actions' relative order nondeterministic; assertions spanning such
    actions should compare ``action_graph_set``.
    """
    edges: list[tuple[str, str]] = []
    for action, graph in operation_graphs.items():
        for execution in graph.executions:
            edges.append(
                (action.source_typed_name, execution.callee_action_name.full_typed_name)
            )
    return edges


def action_graph_set(
    operation_graphs: operation_graph.OperationGraphs,
) -> set[tuple[str, str]]:
    """Return ``action_graph`` as a set, for assertions whose edge order is nondeterministic."""
    return set(action_graph(operation_graphs))
