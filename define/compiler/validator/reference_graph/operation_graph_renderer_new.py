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
type _ActionOperationLabels = typed_name_dict.TypedNameDict[
    ast.GlobalTypedName, _OperationLabels
]


def _action_name(action: ast.GlobalTypedName) -> str:
    """Return an action's name without its universe or path, such as ``test``."""
    return action.name_content.path.name.removeprefix("/")


def operation_dependencies_new(
    operation_graphs: _OperationGraphs,
) -> dict[str, list[str]]:
    """Return a label for each operation the entry-point action performs or triggers, mapped to the labels it depends on."""
    for typed_name in operation_graphs:
        if typed_name.name_content.path.name == _ENTRY_POINT_ACTION_PATH:
            return _GraphRenderer(typed_name, operation_graphs).to_scheduling_table()
    raise KeyError(_ENTRY_POINT_ACTION_PATH)


class _OperationLabels:
    """The label of every operation of one graph, by node id."""

    def __init__(self, graph: operation_graph.OperationGraph):
        """Label every operation in ``graph``."""
        self._labels: dict[int, str] = {}
        times_seen: dict[str, int] = {}
        for node in graph.nodes:
            if not isinstance(node, operation_graph.PositionOperationNode):
                continue
            label = self._operation_label(node)
            # An action can perform the same operation on the same position more
            # than once, which every operation after the first says in its label.
            count = times_seen.get(label, 0) + 1
            times_seen[label] = count
            self._labels[node.node_id] = label if count == 1 else f"{label}#{count}"

    def __getitem__(self, node_id: int) -> str:
        """Return the label of the operation at ``node_id``."""
        return self._labels[node_id]

    @classmethod
    def _operation_label(cls, node: operation_graph.PositionOperationNode) -> str:
        """Return the label of one operation, such as ``move(item, dest)``."""
        target = cls._position_name(node.target)
        match node:
            case operation_graph.CreateNode():
                return f"create({target})"
            case operation_graph.MoveNode():
                source = cls._position_name(node.source)
                return f"move({source}, {target})"
            case operation_graph.DestroyNode():
                return f"destroy({target})"
            case _:
                raise TypeError(f"unknown operation node type: {type(node).__name__}")

    @staticmethod
    def _position_name(position: ast.PositionReference) -> str:
        """Return a position's name as the action that operates on it names it."""
        return "::".join(
            typed_name.name_content.source_name for typed_name in position.typed_names
        )


class _InvocationLabels:
    """A map from trigger_node_id to a short name for that callee."""

    def __init__(self, graph: operation_graph.OperationGraph):
        """Name the invocation every trigger operation in ``graph`` fires."""
        self._names: dict[int, str] = {}
        self._callees: dict[int, ast.GlobalTypedNameReference] = {}
        times_invoked: dict[str, int] = {}
        for node in graph.nodes:
            for satisfaction in node.satisfies:
                if satisfaction.trigger_node_id in self._names:
                    continue
                action_name = _action_name(satisfaction.callee)
                count = times_invoked.get(action_name, 0) + 1
                times_invoked[action_name] = count
                self._names[satisfaction.trigger_node_id] = (
                    action_name if count == 1 else f"{action_name}#{count}"
                )
                self._callees[satisfaction.trigger_node_id] = satisfaction.callee

    def __getitem__(self, trigger_node_id: int) -> str:
        """Return the name of the invocation the trigger operation at ``trigger_node_id`` fires."""
        return self._names[trigger_node_id]

    def names(self) -> Iterable[str]:
        """Return the name of every invocation this action triggers."""
        return self._names.values()

    def callees(self) -> Iterable[ast.GlobalTypedNameReference]:
        """Return the action every invocation this action triggers invokes."""
        return self._callees.values()


class _ActionInvocationLabels:
    """The name of every invocation in the program, by the action that triggers it and the operation that fires it.

    Each action names its own invocations, knowing nothing of the rest of the
    program, so a name can fail to stand for one invocation in two ways: two
    actions that invoke the same callee both name their first invocation of it
    ``worker``, and an action invoked more than once hands out every one of its
    names again in each of its own invocations. Either way, the name carries the
    name of the invocation it was triggered from: ``first:worker``, ``first#2:worker``.
    """

    def __init__(self, graphs: _OperationGraphs):
        """Name every invocation the actions in ``graphs`` trigger."""
        self._labels: typed_name_dict.TypedNameDict[
            ast.GlobalTypedName, _InvocationLabels
        ] = typed_name_dict.TypedNameDict()
        # How many callers give out each name, and how many times each callee is
        # invoked. A name stands for one invocation only when one caller gives it
        # and that caller is itself invoked only once.
        callers_naming: dict[str, int] = {}
        times_invoked: typed_name_dict.TypedNameDict[ast.GlobalTypedName, int] = (
            typed_name_dict.TypedNameDict()
        )
        for caller, graph in graphs.items():
            labels = _InvocationLabels(graph)
            self._labels[caller] = labels
            for name in labels.names():
                callers_naming[name] = callers_naming.get(name, 0) + 1
            for callee in labels.callees():
                times_invoked[callee] = times_invoked.get(callee, 0) + 1
        self._ambiguous: typed_name_dict.TypedNameDict[
            ast.GlobalTypedName, set[str]
        ] = typed_name_dict.TypedNameDict()
        for caller, labels in self._labels.items():
            caller_invoked_repeatedly = times_invoked.get(caller, 0) > 1
            self._ambiguous[caller] = {
                name
                for name in labels.names()
                if callers_naming[name] > 1 or caller_invoked_repeatedly
            }

    def name(
        self, action: ast.GlobalTypedName, invocation: str, trigger_node_id: int
    ) -> str:
        """Return the name of the invocation the operation at ``trigger_node_id`` fires, in ``action``'s invocation named ``invocation``."""
        name = self._labels[action][trigger_node_id]
        if name in self._ambiguous[action]:
            return f"{invocation}:{name}"
        return name


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
    def _operation_labels(self) -> _ActionOperationLabels:
        # A triggered action's operations are labeled with its own name for them,
        # so every graph is labeled, not only the one being rendered.
        labels: _ActionOperationLabels = typed_name_dict.TypedNameDict()
        for action, graph in self._graphs.items():
            labels[action] = _OperationLabels(graph)
        return labels

    @cached_property
    def _invocation_labels(self) -> _ActionInvocationLabels:
        return _ActionInvocationLabels(self._graphs)

    def _label(
        self,
        invocation: str,
        action: ast.GlobalTypedName,
        node: operation_graph.PositionOperationNode,
    ) -> str:
        """Return the label of ``node``, an operation ``action`` performs in ``invocation``, such as ``test.move(item, dest)``."""
        return f"{invocation}.{self._operation_labels[action][node.node_id]}"

    @cached_property
    def _nodes_waiting_on(self) -> _ForwardDependencyGraph:
        return _ForwardDependencyGraph(self._graphs)

    def to_scheduling_table(self) -> dict[str, list[str]]:
        """Return a label for each operation, mapped to the labels it depends on."""
        table: dict[str, list[str]] = {}
        invocation = _action_name(self._action)
        for node in self._graphs[self._action].nodes:
            if not isinstance(node, operation_graph.PositionOperationNode):
                continue
            label = self._label(invocation, self._action, node)
            table[label] = self._dependency_labels(invocation, node.depends_on)
            # This operation satisfies a requirement, so the callee operations that
            # were waiting on that requirement now run.
            for satisfaction in node.satisfies:
                table.update(
                    self._satisfied_operations(
                        self._action, invocation, satisfaction, label
                    )
                )
        return table

    def _dependency_labels(
        self, invocation: str, depends_on: Iterable[int]
    ) -> list[str]:
        """Return the labels of the operations the ids in ``depends_on`` name."""
        graph = self._graphs[self._action]
        dependency_labels: list[str] = []
        for depends_on_node_id in depends_on:
            depends_on_node = graph.nodes[depends_on_node_id]
            if isinstance(depends_on_node, operation_graph.PositionOperationNode):
                dependency_labels.append(
                    self._label(invocation, self._action, depends_on_node)
                )
        return dependency_labels

    def _satisfied_operations(
        self,
        caller: ast.GlobalTypedName,
        caller_invocation: str,
        satisfaction: operation_graph.RequirementSatisfaction,
        satisfier: str,
    ) -> dict[str, list[str]]:
        """Return the callee operations that wait on the requirement the operation labeled ``satisfier`` satisfies."""
        graph = self._graphs[satisfaction.callee]
        requirement = graph.requirement_node(satisfaction.requirement_position)
        invocation = self._invocation_labels.name(
            caller, caller_invocation, satisfaction.trigger_node_id
        )
        table: dict[str, list[str]] = {}
        for node in self._waiting_on(satisfaction.callee, requirement.node_id):
            dependency_labels: list[str] = []
            for depends_on_node_id in node.depends_on:
                depends_on_node = graph.nodes[depends_on_node_id]
                if depends_on_node_id == requirement.node_id:
                    # We replace the requirement node with the label of the operation
                    # that fulfilled it.
                    dependency_labels.append(satisfier)
                elif isinstance(depends_on_node, operation_graph.PositionOperationNode):
                    dependency_labels.append(
                        self._label(invocation, satisfaction.callee, depends_on_node)
                    )
            label = self._label(invocation, satisfaction.callee, node)
            table[label] = dependency_labels
            # The callee triggers actions of its own, whose operations run in this
            # triggering of the callee and in no other triggering of it.
            for callee_satisfaction in node.satisfies:
                table.update(
                    self._satisfied_operations(
                        satisfaction.callee, invocation, callee_satisfaction, label
                    )
                )
        return table

    def _waiting_on(
        self, action: ast.GlobalTypedName, node_id: int
    ) -> list[operation_graph.PositionOperationNode]:
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
        waiting: list[operation_graph.PositionOperationNode] = []
        for reached_node_id in sorted(reached):
            reached_node = graph.nodes[reached_node_id]
            if isinstance(reached_node, operation_graph.PositionOperationNode):
                waiting.append(reached_node)
        return waiting
