# pyright: reportUnusedCallResult=false
"""Renders DLP 44 operation graphs as readable adjacency dicts for tests."""

from collections import Counter

from define.compiler import ast
from define.compiler.validator import validation_result
from define.compiler.validator.reference_graph import operation_graph

# For a spliced-in triggered action: its graph, and its node-id -> rendered label.
_CalleeSplice = tuple[operation_graph.OperationGraph, dict[int, str]]


class _OperationGraphFlattener:
    """Flattens an operation graph and any actions it triggers."""

    def __init__(self, program_result: validation_result.ProgramValidationResult):
        self._registry: dict[str, operation_graph.OperationGraph] = {
            typed_name.full_typed_name: definition_result.operation_graph
            for typed_name, definition_result in program_result.definition_results.items()
            if definition_result.operation_graph is not None
        }
        self._label_counts: Counter[str] = Counter()

    def flatten(self, root_action: str) -> dict[str, list[str]]:
        """Map each operation to the operations it waits on."""
        dependencies: dict[str, list[str]] = {}
        self._flatten_action(root_action, None, dependencies)
        return dependencies

    def _flatten_action(
        self,
        action: str,
        trigger_label: str | None,
        dependencies: dict[str, list[str]],
    ) -> dict[int, str]:
        graph = self._registry[action]
        action_name = self._action_display_name(action)
        local_labels: dict[int, str] = {}
        # Keyed by (trigger operation id, callee action), for resolving the
        # guarantee nodes that stand in for those callees' outputs.
        callee_splices: dict[tuple[int, str], _CalleeSplice] = {}
        for node in graph.nodes:
            if isinstance(node, operation_graph.GuaranteeNode):
                # A callee output: it renders as the callee's own split point.
                local_labels[node.node_id] = self._split_point_label(
                    node, callee_splices
                )
                continue
            label = self._operation_label(action_name, node)
            if node.depends_on:
                predecessors = [local_labels[dep] for dep in node.depends_on]
            elif trigger_label is not None:
                predecessors = [trigger_label]
            else:
                predecessors = []
            dependencies[label] = predecessors
            local_labels[node.node_id] = label
            for triggered in graph.triggered_actions(node.node_id):
                callee_action = triggered.typed_names[-1].full_typed_name
                callee_labels = self._flatten_action(callee_action, label, dependencies)
                callee_splices[(node.node_id, callee_action)] = (
                    self._registry[callee_action],
                    callee_labels,
                )
        return local_labels

    def _split_point_label(
        self,
        node: operation_graph.GuaranteeNode,
        callee_splices: dict[tuple[int, str], _CalleeSplice],
    ) -> str:
        trigger_node_id = node.depends_on[0]
        callee_graph, callee_labels = callee_splices[(trigger_node_id, node.action)]
        split_point = callee_graph.last_operation_node_id_for_key(node.output_position)
        if split_point is None:
            raise ValueError(
                f"no split point for {node.output_position} in {node.action}"
            )
        return callee_labels[split_point]

    def _operation_label(
        self, action_name: str, node: operation_graph.OperationNode
    ) -> str:
        match node:
            case operation_graph.CreateNode():
                label = f"{action_name}.create({self._short_chained_name(node.target)})"
            case operation_graph.DestroyNode():
                label = (
                    f"{action_name}.destroy({self._short_chained_name(node.target)})"
                )
            case operation_graph.MoveNode():
                source = self._short_chained_name(node.source)
                label = f"{action_name}.move({source}, {self._short_chained_name(node.target)})"
            case _:
                raise TypeError(f"unexpected operation node {type(node).__name__}")
        return self._disambiguated(label)

    def _short_chained_name(self, reference: ast.PositionReference) -> str:
        return "::".join(
            element.name_content.source_name for element in reference.typed_names
        )

    def _action_display_name(self, action_full_typed_name: str) -> str:
        inner = action_full_typed_name[
            action_full_typed_name.index("<") + 1 : action_full_typed_name.rindex(">")
        ]
        return inner.rsplit(":", 1)[-1].lstrip("/")

    def _disambiguated(self, label: str) -> str:
        self._label_counts[label] += 1
        count = self._label_counts[label]
        return label if count == 1 else f"{label}#{count}"


def action_graph(
    program_result: validation_result.ProgramValidationResult,
) -> list[tuple[str, str]]:
    """Return each action's directly-triggered actions as (source, target) name pairs."""
    edges: list[tuple[str, str]] = []
    for typed_name, definition_result in program_result.definition_results.items():
        graph = definition_result.operation_graph
        if graph is None:
            continue
        source = typed_name.source_typed_name
        for node in graph.nodes:
            for action_ref in graph.triggered_actions(node.node_id):
                edges.append((source, action_ref.typed_names[-1].full_typed_name))
    return edges


def operation_dependencies(
    program_result: validation_result.ProgramValidationResult,
    root_action: str,
) -> dict[str, list[str]]:
    """Map each operation of ``root_action`` (and the actions it triggers) to what it waits on.

    A triggered action is spliced in at the operation that fires it: its
    operations are rendered under its own action prefix and its roots wait on the
    firing operation. A caller operation that reads a triggered action's output
    waits on that callee's own split point. Every operation is keyed once
    (repeats of a label are suffixed ``#2``, ``#3``) and maps to what it waits on.
    """
    return _OperationGraphFlattener(program_result).flatten(root_action)
