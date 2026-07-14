"""Renders an action's operation graph as a readable map of dependencies, for tests."""

from __future__ import annotations

import typing
from dataclasses import dataclass
from functools import cached_property

from define.compiler import ast
from define.compiler.data_structures import typed_name_dict
from define.compiler.validator.reference_graph import action_contract, operation_graph

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
# One triggering of one action, by the operation that fired it and the action it
# fires. An action names each of its own triggerings, and one operation can fire
# more than one of them.
type _TriggerKey = tuple[int, str]


def _trigger_key(trigger: operation_graph.ActionTrigger) -> _TriggerKey:
    """Return the key that tells one triggering an action performs from the next."""
    return (trigger.trigger_node_id, trigger.callee.full_typed_name)


@dataclass(frozen=True, slots=True)
class _SplicedAction:
    """One copy of an action's operations, spliced into the graph by a triggering.

    Triggering an action does not "call" it in the traditional sense. Logically,
    what it actually does is it splices the operations of the callee into the
    caller's graph. (The callee's operations wait on the caller's operations.)

    An action is spliced separately every time it is triggered.
    """

    action: ast.GlobalTypedName
    # What every operation of this copy is labeled with, such as ``middle``.
    name: str
    # The triggering that spliced this copy in, and the copy whose operation fired
    # it. Both are absent for the entry point, which nothing spliced in.
    trigger: operation_graph.ActionTrigger | None
    spliced_by: _SplicedAction | None


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
    """The name one action gives each action it triggers, by the triggering."""

    def __init__(self, graph: operation_graph.OperationGraph):
        """Name every action ``graph`` triggers."""
        self._names: dict[_TriggerKey, str] = {}
        self._callees: list[ast.GlobalTypedNameReference] = []
        times_invoked: dict[str, int] = {}
        for trigger in graph.triggers:
            action_name = _action_name(trigger.callee)
            # An action can trigger the same action more than once, which every
            # triggering after the first says in its name.
            count = times_invoked.get(action_name, 0) + 1
            times_invoked[action_name] = count
            self._names[_trigger_key(trigger)] = (
                action_name if count == 1 else f"{action_name}#{count}"
            )
            self._callees.append(trigger.callee)

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

    def __init__(self, graphs: _OperationGraphs):
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
        self, spliced: _SplicedAction, trigger: operation_graph.ActionTrigger
    ) -> str:
        """Return the name of the action ``trigger`` fires, triggered from the copy ``spliced``."""
        name = self._labels[spliced.action][trigger]
        if name in self._ambiguous[spliced.action]:
            return f"{spliced.name}:{name}"
        return name


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

    def to_scheduling_table(self) -> dict[str, list[str]]:
        """Return a label for each operation, mapped to the labels it depends on."""
        table: dict[str, list[str]] = {}
        # Nothing triggered the entry-point action, so nothing spliced it in.
        self._splice(
            table,
            _SplicedAction(
                self._action, _action_name(self._action), trigger=None, spliced_by=None
            ),
        )
        return table

    def _splice(self, table: dict[str, list[str]], spliced: _SplicedAction):
        """Add every operation of the copy ``spliced``, and of the actions it triggers, to ``table``."""
        graph = self._graphs[spliced.action]
        for node in graph.nodes:
            if not isinstance(node, operation_graph.PositionOperationNode):
                continue
            label = self._label(spliced, node)
            if label in table:
                raise ValueError(f"two operations are labeled {label}")
            table[label] = self._dependency_labels(spliced, node.depends_on)
        # Triggering an action splices the operations of that action in here.
        for trigger in graph.triggers:
            self._splice(table, self._spliced_callee(spliced, trigger))

    def _spliced_callee(
        self, spliced: _SplicedAction, trigger: operation_graph.ActionTrigger
    ) -> _SplicedAction:
        """Return the copy of the action ``trigger`` fires, spliced in by the copy ``spliced``."""
        return _SplicedAction(
            trigger.callee,
            self._invocation_labels.name(spliced, trigger),
            trigger=trigger,
            spliced_by=spliced,
        )

    def _label(
        self, spliced: _SplicedAction, node: operation_graph.PositionOperationNode
    ) -> str:
        """Return the label of ``node``, an operation the copy ``spliced`` performs, such as ``test.move(item, dest)``."""
        return f"{spliced.name}.{self._operation_labels[spliced.action][node.node_id]}"

    def _dependency_labels(
        self, spliced: _SplicedAction, depends_on: Iterable[int]
    ) -> list[str]:
        """Return the labels of the operations the copy ``spliced`` waits on at the ids in ``depends_on``."""
        graph = self._graphs[spliced.action]
        dependency_labels: list[str] = []
        for depends_on_node_id in depends_on:
            dependency_labels.extend(
                self._node_labels(spliced, graph.nodes[depends_on_node_id])
            )
        return dependency_labels

    def _node_labels(
        self, spliced: _SplicedAction, node: operation_graph.OperationNode
    ) -> list[str]:
        """Return the labels of the operations the copy ``spliced`` waits on at ``node``."""
        match node:
            case operation_graph.PositionOperationNode():
                return [self._label(spliced, node)]
            case operation_graph.RequirementNode():
                return self._requirement_labels(spliced, node)
            case operation_graph.GuaranteeNode():
                # TODO: A guarantee waits on the last operation the triggered
                # action performs on the position, which lives in the graph of
                # that action, so this drops the dependency today.
                return []
            case _:
                raise TypeError(f"unknown node type: {type(node).__name__}")

    def _requirement_labels(
        self, spliced: _SplicedAction, requirement: operation_graph.RequirementNode
    ) -> list[str]:
        """Return the labels of the operations that put the position of ``requirement`` in the state the copy ``spliced`` needs it in."""
        if spliced.trigger is None or spliced.spliced_by is None:
            # Nothing spliced the entry-point action in, so nothing in this program
            # satisfies its requirements.
            return []
        satisfier = spliced.trigger.satisfiers.get(requirement.requirement_position)
        if satisfier is not None:
            # The action that triggered this copy says what satisfies the
            # requirement. That is one of its own operations, or a requirement of
            # its own, which whatever spliced it in satisfies in turn.
            caller_graph = self._graphs[spliced.spliced_by.action]
            return self._node_labels(spliced.spliced_by, caller_graph.nodes[satisfier])
        if (
            requirement.required_state
            is action_contract.PositionOccupancyState.OCCUPIED
        ):
            raise ValueError(
                f"nothing fills the position {requirement.requirement_position}"
            )
        # Nothing the caller did made the position empty: it is empty because
        # nothing was ever put in it. What left it that way is the fill of the
        # position above it, which is the requirement this one waits on.
        return self._dependency_labels(spliced, requirement.depends_on)
