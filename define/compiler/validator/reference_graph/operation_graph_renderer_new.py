"""Renders an action's operation graph as a readable map of dependencies, for tests."""

from __future__ import annotations

import typing

from define.compiler.validator.reference_graph import operation_graph

if typing.TYPE_CHECKING:
    from collections.abc import Iterable

    from define.compiler import ast
    from define.compiler.data_structures import typed_name_dict

# Every operation graph test names the action it validates /test.
_ENTRY_POINT_ACTION_PATH = "/test"


def operation_dependencies_new(
    operation_graphs: typed_name_dict.TypedNameDict[
        ast.GlobalTypedName, operation_graph.OperationGraph
    ],
) -> dict[str, list[str]]:
    """Return a label for each operation of the entry-point action, mapped to the labels it depends on."""
    for action, graph in operation_graphs.items():
        if action.name_content.path.name == _ENTRY_POINT_ACTION_PATH:
            return _GraphRenderer(action, graph).to_scheduling_table()
    raise KeyError(_ENTRY_POINT_ACTION_PATH)


class _GraphRenderer:
    """Renders one action's operation graph."""

    def __init__(
        self, action: ast.GlobalTypedName, graph: operation_graph.OperationGraph
    ):
        """Prepare to render ``graph``, which is the graph of ``action``."""
        self._action: ast.GlobalTypedName = action
        self._graph: operation_graph.OperationGraph = graph
        self._action_name: str = action.name_content.path.name.removeprefix("/")

    def to_scheduling_table(self) -> dict[str, list[str]]:
        """Return a label for each operation, mapped to the labels it depends on."""
        table: dict[str, list[str]] = {}
        for node in self._graph.nodes:
            if not isinstance(node, operation_graph.PositionOperationNode):
                continue
            table[self._operation_label(node)] = self._dependency_labels(
                node.depends_on
            )
        return table

    def _dependency_labels(self, depends_on: Iterable[int]) -> list[str]:
        """Return the labels of the operations the ids in ``depends_on`` name."""
        labels: list[str] = []
        for depends_on_node_id in depends_on:
            depends_on_node = self._graph.nodes[depends_on_node_id]
            if isinstance(depends_on_node, operation_graph.PositionOperationNode):
                labels.append(self._operation_label(depends_on_node))
        return labels

    def _operation_label(self, node: operation_graph.PositionOperationNode) -> str:
        """Return the label of one operation, such as ``test.move(item, dest)``."""
        target = self._position_name(node.target)
        match node:
            case operation_graph.CreateNode():
                return f"{self._action_name}.create({target})"
            case operation_graph.MoveNode():
                return f"{self._action_name}.move({self._position_name(node.source)}, {target})"
            case operation_graph.DestroyNode():
                return f"{self._action_name}.destroy({target})"
            case _:
                raise TypeError(f"unknown operation node type: {type(node).__name__}")

    def _position_name(self, position: ast.PositionReference) -> str:
        """Return a position's name from the action's perspective, such as ``box::/child``."""
        typed_names = position.typed_names
        if typed_names[0].full_typed_name == self._action.full_typed_name:
            typed_names = typed_names[1:]
        return "::".join(
            typed_name.name_content.source_name for typed_name in typed_names
        )
