"""Renders an action's operation graph as a readable map of dependencies, for tests."""

from __future__ import annotations

import typing

from define.compiler import ast
from define.compiler.data_structures import typed_name_dict
from define.compiler.validator.reference_graph import (
    operation_graph,
    operation_graph_resolver,
)

if typing.TYPE_CHECKING:
    from collections.abc import Iterable

# Every operation graph test names the action it validates /test.
_ENTRY_POINT_ACTION_PATH = "/test"

type _ActionOperationLabels = typed_name_dict.TypedNameDict[
    ast.GlobalTypedName, _OperationLabels
]
# One triggering of one action, by the operation that fired it and the action it
# fires. An action names each of its own triggerings, and one operation can fire
# more than one of them.
type _TriggerKey = tuple[operation_graph.LastOperationNode, str]


def _trigger_key(trigger: operation_graph.ActionTrigger) -> _TriggerKey:
    """Return the key that tells one triggering an action performs from the next."""
    return (trigger.trigger_operation, trigger.callee_action_name.full_typed_name)


def _action_name(action: ast.GlobalTypedName) -> str:
    """Return an action's name without its universe or path, such as ``test``."""
    return action.name_content.path.name.removeprefix("/")


def operation_dependencies(
    operation_graphs: operation_graph.OperationGraphs,
) -> dict[str, list[str]]:
    """Return a label for each operation the entry-point action performs or triggers, mapped to the labels it depends on."""
    for typed_name in operation_graphs:
        if typed_name.name_content.path.name == _ENTRY_POINT_ACTION_PATH:
            resolved = operation_graph_resolver.ResolvedOperationGraphBuilder(
                operation_graphs, typed_name
            ).build()
            return _Program(operation_graphs).to_scheduling_table(resolved)
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


class _OperationLabels:
    """The label of every operation of one graph."""

    def __init__(self, graph: operation_graph.OperationGraph):
        """Label every operation in ``graph``."""
        self._labels: dict[operation_graph.PositionOperationNode, str] = {}
        times_seen: dict[str, int] = {}
        for node in graph.nodes:
            if not isinstance(node, operation_graph.PositionOperationNode):
                continue
            label = self._operation_label(node)
            # An action can perform the same operation on the same position more
            # than once, which every operation after the first says in its label.
            count = times_seen.get(label, 0) + 1
            times_seen[label] = count
            self._labels[node] = label if count == 1 else f"{label}#{count}"

    def __getitem__(self, node: operation_graph.PositionOperationNode) -> str:
        """Return the label of ``node``."""
        return self._labels[node]

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
    """The name one action gives each action it triggers, by the triggering."""

    def __init__(self, graph: operation_graph.OperationGraph):
        """Name every action ``graph`` triggers."""
        self._names: dict[_TriggerKey, str] = {}
        self._callees: list[ast.GlobalTypedNameReference] = []
        times_invoked: dict[str, int] = {}
        for trigger in graph.triggers:
            action_name = _action_name(trigger.callee_action_name)
            # An action can trigger the same action more than once, which every
            # triggering after the first says in its name.
            count = times_invoked.get(action_name, 0) + 1
            times_invoked[action_name] = count
            self._names[_trigger_key(trigger)] = (
                action_name if count == 1 else f"{action_name}#{count}"
            )
            self._callees.append(trigger.callee_action_name)

    def __getitem__(self, trigger: operation_graph.ActionTrigger) -> str:
        """Return the name of the action ``trigger`` fires."""
        return self._names[_trigger_key(trigger)]

    def names(self) -> Iterable[str]:
        """Return the name of every action this action triggers."""
        return self._names.values()

    def callees(self) -> Iterable[ast.GlobalTypedNameReference]:
        """Return the action every triggering of this action fires."""
        return self._callees


class _ActionInvocationLabels:
    """The name of every triggering in the program, by the action that performs it.

    Each action names its own triggerings, knowing nothing of the rest of the
    program, so a name can fail to stand for one triggering in two ways: two
    actions that trigger the same callee both name their first triggering of it
    ``worker``, and an action triggered more than once hands out every one of its
    names again in each copy of itself. Either way, the name carries the name of
    the triggering it was spliced in by: ``first:worker``, ``first#2:worker``.
    """

    def __init__(self, graphs: operation_graph.OperationGraphs):
        """Name every triggering the actions in ``graphs`` perform."""
        self._labels: typed_name_dict.TypedNameDict[
            ast.GlobalTypedName, _InvocationLabels
        ] = typed_name_dict.TypedNameDict()
        # How many actions give out each name, and how many times each action is
        # triggered. A name stands for one triggering only when one action gives it
        # and that action is itself triggered only once.
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
        self,
        action: ast.GlobalTypedName,
        spliced_name: str,
        trigger: operation_graph.ActionTrigger,
    ) -> str:
        """Return the name of the action ``trigger`` fires, triggered from the copy of ``action`` named ``spliced_name``."""
        name = self._labels[action][trigger]
        if name in self._ambiguous[action]:
            return f"{spliced_name}:{name}"
        return name


class _NameResolver:
    """The name every operation and every triggering in the program goes by.

    Both are decided across the whole program at once: an action's operations are
    labeled with its own name for them wherever it is spliced in, and whether a
    triggering's name says which triggering spliced it in depends on what the
    other actions call theirs.
    """

    def __init__(self, graphs: operation_graph.OperationGraphs):
        """Name the operations and triggerings of every action in ``graphs``."""
        self._operation_labels: _ActionOperationLabels = typed_name_dict.TypedNameDict()
        for action, graph in graphs.items():
            self._operation_labels[action] = _OperationLabels(graph)
        self._invocation_labels: _ActionInvocationLabels = _ActionInvocationLabels(
            graphs
        )

    def operation_name(
        self, action: ast.GlobalTypedName, node: operation_graph.PositionOperationNode
    ) -> str:
        """Return what ``action`` calls the operation at ``node``, such as ``move(item, dest)``."""
        return self._operation_labels[action][node]

    def triggering_name(
        self,
        action: ast.GlobalTypedName,
        spliced_name: str,
        trigger: operation_graph.ActionTrigger,
    ) -> str:
        """Return the name of the action ``trigger`` fires, triggered from the copy of ``action`` named ``spliced_name``."""
        return self._invocation_labels.name(action, spliced_name, trigger)


class _Program:
    """Every action's operation graph, and the names everything in them goes by."""

    def __init__(self, graphs: operation_graph.OperationGraphs):
        """Prepare to render the actions in ``graphs``."""
        self._graphs: operation_graph.OperationGraphs = graphs
        self._names: _NameResolver = _NameResolver(graphs)

    def to_scheduling_table(
        self, resolved: operation_graph_resolver.ResolvedOperationGraph
    ) -> dict[str, list[str]]:
        """Render the operations and dependencies in ``resolved``."""
        action = resolved.entry_action_execution.action
        execution_names: dict[operation_graph_resolver.ActionExecution, str] = {
            resolved.entry_action_execution: _action_name(action)
        }
        labels: dict[operation_graph_resolver.ResolvedOperation, str] = {}
        for resolved_operation in resolved.operations:
            action_execution = resolved_operation.action_execution
            action_execution_name = execution_names.get(action_execution)
            if action_execution_name is None:
                triggered_by = action_execution.triggered_by
                if triggered_by is None:
                    action_execution_name = _action_name(action_execution.action)
                else:
                    action_execution_name = self._names.triggering_name(
                        triggered_by.caller.action,
                        execution_names[triggered_by.caller],
                        triggered_by.action_trigger.trigger,
                    )
                execution_names[action_execution] = action_execution_name
            labels[resolved_operation] = (
                f"{action_execution_name}.{self._names.operation_name(action_execution.action, resolved_operation.operation)}"
            )
        return {
            label: [labels[dependency] for dependency in operation.dependencies]
            for operation, label in labels.items()
        }
