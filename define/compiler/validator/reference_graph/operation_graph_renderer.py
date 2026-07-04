"""Renders DLP 44 operation graphs as readable adjacency dicts for tests."""

from collections import Counter

from define.compiler import ast
from define.compiler.validator import validation_result
from define.compiler.validator.reference_graph import operation_graph


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
    ):
        graph = self._registry[action]
        action_name = self._action_display_name(action)
        local_labels: dict[int, str] = {}
        for node in graph.nodes:
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
                self._flatten_action(
                    triggered.typed_names[-1].full_typed_name, label, dependencies
                )

    def _operation_label(
        self, action_name: str, node: operation_graph.OperationNode
    ) -> str:
        target = self._short_chained_name(node.target)
        match node.kind:
            case operation_graph.OperationKind.CREATE:
                label = f"{action_name}.create({target})"
            case operation_graph.OperationKind.DESTROY:
                label = f"{action_name}.destroy({target})"
            case operation_graph.OperationKind.MOVE:
                if node.source is None:
                    raise ValueError("a move node must have a source")
                source = self._short_chained_name(node.source)
                label = f"{action_name}.move({source}, {target})"
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


def operation_dependencies(
    program_result: validation_result.ProgramValidationResult,
    root_action: str,
) -> dict[str, list[str]]:
    """Map each operation of ``root_action`` (and the actions it triggers) to what it waits on.

    A triggered action is spliced in at the operation that fires it: its
    operations are rendered under its own action prefix and its roots wait on the
    firing operation. Every operation is keyed once (repeats of a label are
    suffixed ``#2``, ``#3``) and maps to the operations it waits on.
    """
    return _OperationGraphFlattener(program_result).flatten(root_action)
