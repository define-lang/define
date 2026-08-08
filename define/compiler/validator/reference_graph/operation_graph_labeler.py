"""Readable labels for resolved operations and Action Executions."""

from __future__ import annotations

import typing
from dataclasses import dataclass

from define.compiler import ast
from define.compiler.data_structures import typed_name_dict
from define.compiler.validator.reference_graph import (
    operation_graph,
    operation_graph_model,
    operation_graph_resolver,
)

if typing.TYPE_CHECKING:
    from collections.abc import Iterable

type _ActionOperationLabels = typed_name_dict.TypedNameDict[
    ast.GlobalTypedName, _OperationLabels
]
# One Action Trigger, by the operation that fired it and the action it fires. An
# action names each of its own Action Triggers, and one operation can fire
# more than one of them.
type _TriggerKey = tuple[operation_graph_model.LastOperationNode, str]

_CREATE_OPERATION_NAME = "create"
_MOVE_OPERATION_NAME = "move"
_DESTROY_OPERATION_NAME = "destroy"
_DESTROY_IF_OCCUPIED_OPERATION_NAME = "destroy_if_occupied"


def _trigger_key(trigger: operation_graph_model.ActionTrigger) -> _TriggerKey:
    """Return the identity of one Action Trigger performed by an action."""
    return (trigger.trigger_operation, trigger.callee_action_name.full_typed_name)


def _action_name(action: ast.GlobalTypedName) -> str:
    """Return an action's name without its universe or path, such as ``test``."""
    return action.name_content.path.name.removeprefix("/")


@dataclass(frozen=True, slots=True)
class OperationLabel:
    """An action's local structured name for one Position Operation."""

    operation_name: str
    source: str | None
    target: str
    occurrence: int

    @typing.override
    def __str__(self) -> str:
        """Render this local operation name."""
        positions = (
            self.target if self.source is None else f"{self.source}, {self.target}"
        )
        label = f"{self.operation_name}({positions})"
        if self.occurrence == 1:
            return label
        return f"{label}#{self.occurrence}"


class _OperationLabels:
    """The label of every operation of one graph."""

    def __init__(self, graph: operation_graph.OperationGraph):
        """Label every operation in ``graph``."""
        self._labels: dict[
            operation_graph_model.PositionOperationNode, OperationLabel
        ] = {}
        times_seen: dict[tuple[str, str | None, str], int] = {}
        for node in graph.nodes:
            if not isinstance(node, operation_graph_model.PositionOperationNode):
                continue
            operation_name, source, target = self._operation_parts(node)
            key = (operation_name, source, target)
            # An action can perform the same operation on the same position more
            # than once, which every operation after the first says in its label.
            occurrence = times_seen.get(key, 0) + 1
            times_seen[key] = occurrence
            self._labels[node] = OperationLabel(
                operation_name,
                source,
                target,
                occurrence,
            )

    def __getitem__(
        self, node: operation_graph_model.PositionOperationNode
    ) -> OperationLabel:
        """Return the label of ``node``."""
        return self._labels[node]

    @classmethod
    def _operation_parts(
        cls, node: operation_graph_model.PositionOperationNode
    ) -> tuple[str, str | None, str]:
        """Return the operation name and positions of one operation."""
        target = cls._position_name(node.target)
        match node:
            case operation_graph_model.CreateNode():
                return _CREATE_OPERATION_NAME, None, target
            case operation_graph_model.MoveNode():
                source = cls._position_name(node.source)
                return _MOVE_OPERATION_NAME, source, target
            case operation_graph_model.DestroyIfOccupiedNode():
                return _DESTROY_IF_OCCUPIED_OPERATION_NAME, None, target
            case operation_graph_model.DestroyNode():
                return _DESTROY_OPERATION_NAME, None, target
            case _:
                raise TypeError(f"unknown operation node type: {type(node).__name__}")

    @staticmethod
    def _position_name(position: ast.PositionReference) -> str:
        """Return a position's name as the action that operates on it names it."""
        return "::".join(
            typed_name.name_content.source_name for typed_name in position.typed_names
        )


class _InvocationLabels:
    """The local name one action gives each action it triggers."""

    def __init__(self, graph: operation_graph.OperationGraph):
        """Name every action ``graph`` triggers."""
        self._names: dict[_TriggerKey, str] = {}
        self._callees: list[ast.GlobalTypedNameReference] = []
        times_invoked: dict[str, int] = {}
        for trigger in graph.triggers:
            action_name = _action_name(trigger.callee_action_name)
            # An action can trigger the same action more than once, which every
            # Action Trigger after the first says in its name.
            count = times_invoked.get(action_name, 0) + 1
            times_invoked[action_name] = count
            self._names[_trigger_key(trigger)] = (
                action_name if count == 1 else f"{action_name}#{count}"
            )
            self._callees.append(trigger.callee_action_name)

    def __getitem__(self, trigger: operation_graph_model.ActionTrigger) -> str:
        """Return the local name of the action ``trigger`` fires."""
        return self._names[_trigger_key(trigger)]

    def names(self) -> Iterable[str]:
        """Return the local name of every action this action triggers."""
        return self._names.values()

    def callees(self) -> Iterable[ast.GlobalTypedNameReference]:
        """Return the action every Action Trigger of this action fires."""
        return self._callees


@dataclass(frozen=True, slots=True)
class TriggeredActionExecutionName:
    """A triggered Action Execution's local name and qualification rule."""

    local_name: str
    uses_caller_name: bool

    def render(self, caller_execution_name: str) -> str:
        """Render the complete name from the caller's Action Execution name."""
        if self.uses_caller_name:
            return f"{caller_execution_name}:{self.local_name}"
        return self.local_name


class _ActionInvocationLabels:
    """The name of every Action Trigger, by the action that performs it.

    Each action names its own Action Triggers, knowing nothing of the rest of the
    program, so a name can fail to stand for one Action Trigger in two ways: two
    actions that trigger the same callee both name their first Action Trigger of it
    ``worker``, and an action triggered more than once hands out every one of its
    names again in each copy of itself. Either way, the name carries the name of
    the Action Trigger it was spliced in by: ``first:worker``, ``first#2:worker``.
    """

    def __init__(self, graphs: operation_graph.OperationGraphs):
        """Name every Action Trigger the actions in ``graphs`` perform."""
        self._labels: typed_name_dict.TypedNameDict[
            ast.GlobalTypedName, _InvocationLabels
        ] = typed_name_dict.TypedNameDict()
        # How many actions give out each name, and how many times each action is
        # triggered. A name stands for one Action Trigger only when one action gives it
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
        trigger: operation_graph_model.ActionTrigger,
    ) -> TriggeredActionExecutionName:
        """Return the local name and qualification rule for ``trigger``."""
        local_name = self._labels[action][trigger]
        return TriggeredActionExecutionName(
            local_name=local_name,
            uses_caller_name=local_name in self._ambiguous[action],
        )


@typing.final
class OperationGraphLabeler:
    """The names every operation and Action Execution in a program go by.

    Both are decided across the whole program at once: an action's operations are
    labeled with its own name for them wherever it is spliced in, and whether a
    Action Trigger's name says which Action Trigger spliced it in depends on what the
    other actions call theirs. Construction prepares every label across the
    supplied graphs, so callers should construct a labeler only when they will
    use it.
    """

    def __init__(self, graphs: operation_graph.OperationGraphs):
        """Prepare labels for every action in ``graphs``."""
        self._operation_labels: _ActionOperationLabels = typed_name_dict.TypedNameDict()
        for action, graph in graphs.items():
            self._operation_labels[action] = _OperationLabels(graph)
        self._invocation_labels = _ActionInvocationLabels(graphs)

    @staticmethod
    def entry_action_execution_name(action: ast.GlobalTypedName) -> str:
        """Return the name of an entry Action Execution."""
        return _action_name(action)

    def operation_label(
        self,
        action: ast.GlobalTypedName,
        node: operation_graph_model.PositionOperationNode,
    ) -> OperationLabel:
        """Return ``action``'s local label for ``node``."""
        return self._operation_labels[action][node]

    def triggered_action_execution_name(
        self,
        action: ast.GlobalTypedName,
        trigger: operation_graph_model.ActionTrigger,
    ) -> TriggeredActionExecutionName:
        """Return the name rule for the Action Execution fired by ``trigger``."""
        return self._invocation_labels.name(action, trigger)

    def resolved_operation_labels(
        self,
        resolved: operation_graph_resolver.ResolvedOperationGraph,
    ) -> dict[operation_graph_resolver.ResolvedOperation, str]:
        """Return the complete label of every operation in ``resolved``."""
        execution_names: dict[operation_graph_resolver.ActionExecution, str] = {
            resolved.entry_action_execution: self.entry_action_execution_name(
                resolved.entry_action_execution.action
            )
        }
        labels: dict[operation_graph_resolver.ResolvedOperation, str] = {}
        for resolved_operation in resolved.operations:
            labels[resolved_operation] = ".".join(
                (
                    self._action_execution_name(
                        resolved_operation.action_execution, execution_names
                    ),
                    str(
                        self.operation_label(
                            resolved_operation.action_execution.action,
                            resolved_operation.operation,
                        )
                    ),
                )
            )
        return labels

    def _action_execution_name(
        self,
        action_execution: operation_graph_resolver.ActionExecution,
        execution_names: dict[operation_graph_resolver.ActionExecution, str],
    ) -> str:
        unnamed_executions: list[operation_graph_resolver.ActionExecution] = []
        current_execution = action_execution
        while current_execution not in execution_names:
            triggered_by = typing.cast(
                "operation_graph_resolver.TriggeredBy",
                current_execution.triggered_by,
            )
            unnamed_executions.append(current_execution)
            current_execution = triggered_by.caller
        for unnamed_execution in reversed(unnamed_executions):
            triggered_by = typing.cast(
                "operation_graph_resolver.TriggeredBy",
                unnamed_execution.triggered_by,
            )
            execution_names[unnamed_execution] = self.triggered_action_execution_name(
                triggered_by.caller.action,
                triggered_by.action_trigger.trigger,
            ).render(execution_names[triggered_by.caller])
        return execution_names[action_execution]
