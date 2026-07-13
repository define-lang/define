"""Renders an action's operation graph as a readable map of dependencies, for tests."""

from __future__ import annotations

import typing
from functools import cached_property

from define.compiler import ast
from define.compiler.data_structures import typed_name_dict
from define.compiler.validator.reference_graph import operation_graph

if typing.TYPE_CHECKING:
    from collections.abc import Iterable

# Every operation graph test names the action it validates /test.
_ENTRY_POINT_ACTION_PATH = "/test"

type _OperationGraphs = typed_name_dict.TypedNameDict[
    ast.GlobalTypedName, operation_graph.OperationGraph
]


def operation_dependencies_new(
    operation_graphs: _OperationGraphs,
) -> dict[str, list[str]]:
    """Return a label for each operation the entry-point action performs or triggers, mapped to the labels it depends on."""
    for typed_name in operation_graphs:
        if typed_name.name_content.path.name == _ENTRY_POINT_ACTION_PATH:
            return _GraphRenderer(typed_name, operation_graphs).to_scheduling_table()
    raise KeyError(_ENTRY_POINT_ACTION_PATH)


class _GraphLabelDict:
    """The label of every operation of every action, by action and then by node id.

    A triggered action's operations are labeled with its own name for them, so
    every graph is labeled, not only the one being rendered.
    """

    def __init__(self, graphs: _OperationGraphs):
        """Label every operation in ``graphs``."""
        self._labels: typed_name_dict.TypedNameDict[
            ast.GlobalTypedName, dict[int, str]
        ] = typed_name_dict.TypedNameDict()
        for action, graph in graphs.items():
            self._labels[action] = self._graph_labels(graph, self._action_name(action))

    def __getitem__(self, action: ast.GlobalTypedName) -> dict[int, str]:
        """Return ``action``'s label for each of its operations, by node id."""
        return self._labels[action]

    @classmethod
    def _graph_labels(
        cls, graph: operation_graph.OperationGraph, action_name: str
    ) -> dict[int, str]:
        """Return the label of every operation in ``graph``, numbered so that no two share one."""
        labels: dict[int, str] = {}
        times_seen: dict[str, int] = {}
        for node in graph.nodes:
            if not isinstance(node, operation_graph.PositionOperationNode):
                continue
            label = cls._operation_label(node, action_name)
            # An action can perform the same operation on the same position more
            # than once, which every operation after the first says in its label.
            count = times_seen.get(label, 0) + 1
            times_seen[label] = count
            labels[node.node_id] = label if count == 1 else f"{label}#{count}"
        return labels

    @classmethod
    def _operation_label(
        cls, node: operation_graph.PositionOperationNode, action_name: str
    ) -> str:
        """Return the label of one operation, such as ``test.move(item, dest)``."""
        target = cls._position_name(node.target)
        match node:
            case operation_graph.CreateNode():
                return f"{action_name}.create({target})"
            case operation_graph.MoveNode():
                source = cls._position_name(node.source)
                return f"{action_name}.move({source}, {target})"
            case operation_graph.DestroyNode():
                return f"{action_name}.destroy({target})"
            case _:
                raise TypeError(f"unknown operation node type: {type(node).__name__}")

    @staticmethod
    def _action_name(action: ast.GlobalTypedName) -> str:
        """Return an action's name without its universe or path, such as ``test``."""
        return action.name_content.path.name.removeprefix("/")

    @staticmethod
    def _position_name(position: ast.PositionReference) -> str:
        """Return a position's name as the action that operates on it names it."""
        return "::".join(
            typed_name.name_content.source_name for typed_name in position.typed_names
        )


class _ForwardDependencyGraph:
    """A forward dependency graph for each action, starting at the root nodes and going downward.

    Querying this dictionary with a node_id gives you all the nodes that
    are waiting on this node. This is here, currently, instead of in the
    operation_graph, because right now I believe only the renderer needs this.
    """

    def __init__(self, graphs: _OperationGraphs):
        """Map the dependents of every node in ``graphs``."""
        self._dependents: typed_name_dict.TypedNameDict[
            ast.GlobalTypedName, dict[int, list[int]]
        ] = typed_name_dict.TypedNameDict()
        for action, graph in graphs.items():
            self._dependents[action] = self._graph_dependents(graph)

    def __getitem__(self, action: ast.GlobalTypedName) -> dict[int, list[int]]:
        """Return the ids of the operations waiting on each node of ``action``, by node id."""
        return self._dependents[action]

    @staticmethod
    def _graph_dependents(
        graph: operation_graph.OperationGraph,
    ) -> dict[int, list[int]]:
        """Return the ids of the nodes of ``graph`` that wait directly on each node, by node id."""
        dependents: dict[int, list[int]] = {}
        for node in graph.nodes:
            for depends_on_node_id in node.depends_on:
                dependents.setdefault(depends_on_node_id, []).append(node.node_id)
        return dependents


class _GraphRenderer:
    """Renders one action's operation graph, and the operations of the actions it triggers."""

    def __init__(self, action: ast.GlobalTypedName, graphs: _OperationGraphs):
        """Prepare to render the graph of ``action``, one of the graphs in ``graphs``."""
        self._action: ast.GlobalTypedName = action
        self._graphs: _OperationGraphs = graphs

    @cached_property
    def _labels(self) -> _GraphLabelDict:
        return _GraphLabelDict(self._graphs)

    @cached_property
    def _nodes_waiting_on(self) -> _ForwardDependencyGraph:
        return _ForwardDependencyGraph(self._graphs)

    def to_scheduling_table(self) -> dict[str, list[str]]:
        """Return a label for each operation, mapped to the labels it depends on."""
        table: dict[str, list[str]] = {}
        labels = self._labels[self._action]
        for node in self._graphs[self._action].nodes:
            if not isinstance(node, operation_graph.PositionOperationNode):
                continue
            table[labels[node.node_id]] = self._dependency_labels(node.depends_on)
            # This operation satisfies a requirement, so the callee operations that
            # were waiting on that requirement now run.
            for satisfaction in node.satisfies:
                table.update(
                    self._satisfied_operations(satisfaction, labels[node.node_id])
                )
        return table

    def _dependency_labels(self, depends_on: Iterable[int]) -> list[str]:
        """Return the labels of the operations the ids in ``depends_on`` name."""
        graph = self._graphs[self._action]
        labels = self._labels[self._action]
        dependency_labels: list[str] = []
        for depends_on_node_id in depends_on:
            depends_on_node = graph.nodes[depends_on_node_id]
            if isinstance(depends_on_node, operation_graph.PositionOperationNode):
                dependency_labels.append(labels[depends_on_node_id])
        return dependency_labels

    def _satisfied_operations(
        self,
        satisfaction: operation_graph.RequirementSatisfaction,
        satisfier: str,
    ) -> dict[str, list[str]]:
        """Return the callee operations that wait on the requirement the operation labeled ``satisfier`` satisfies."""
        graph = self._graphs[satisfaction.callee]
        labels = self._labels[satisfaction.callee]
        requirement = graph.requirement_node(satisfaction.requirement_position)
        table: dict[str, list[str]] = {}
        for node_id in self._waiting_on(satisfaction.callee, requirement.node_id):
            node = graph.nodes[node_id]
            dependency_labels: list[str] = []
            for depends_on_node_id in node.depends_on:
                if depends_on_node_id == requirement.node_id:
                    # We replace the requirement node with the label of the operation
                    # that fulfilled it.
                    dependency_labels.append(satisfier)
                else:
                    dependency_labels.append(labels[depends_on_node_id])
            table[labels[node_id]] = dependency_labels
        return table

    def _waiting_on(self, action: ast.GlobalTypedName, node_id: int) -> list[int]:
        """Return the operations of ``action`` that wait on the node at ``node_id``, directly or through another."""
        graph = self._graphs[action]
        dependents = self._nodes_waiting_on[action]
        reached: set[int] = set()
        to_visit = [node_id]
        while to_visit:
            for dependent in dependents.get(to_visit.pop(), ()):
                if dependent not in reached:
                    reached.add(dependent)
                    to_visit.append(dependent)
        # An operation only ever depends on an earlier one, so id order is an
        # order the operations can run in.
        waiting: list[int] = []
        for reached_node_id in sorted(reached):
            reached_node = graph.nodes[reached_node_id]
            if isinstance(reached_node, operation_graph.PositionOperationNode):
                waiting.append(reached_node_id)
        return waiting
