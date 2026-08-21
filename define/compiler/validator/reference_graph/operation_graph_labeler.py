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
_CREATE_OPERATION_NAME = "create"
_MOVE_OPERATION_NAME = "move"
_DESTROY_OPERATION_NAME = "destroy"


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
        target_position = (
            node.target_in_destroying_action
            if isinstance(node, operation_graph_model.DestructionFragmentDestroyNode)
            else node.target
        )
        target = cls._position_name(target_position)
        match node:
            case operation_graph_model.CreateNode():
                return _CREATE_OPERATION_NAME, None, target
            case operation_graph_model.MoveNode():
                source = cls._position_name(node.source)
                return _MOVE_OPERATION_NAME, source, target
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


class _ExecutionLabels:
    """The local name one action gives each action it triggers."""

    def __init__(self, graph: operation_graph.OperationGraph):
        """Name every action ``graph`` triggers."""
        self._names: dict[operation_graph_model.ActionExecution, str] = {}
        execution_counts: dict[str, int] = {}
        for execution in graph.executions_including_contributions():
            action_name = _action_name(execution.callee_action_name)
            # An action can trigger the same action more than once, which every
            # Action Execution after the first says in its name.
            count = execution_counts.get(action_name, 0) + 1
            execution_counts[action_name] = count
            self._names[execution] = (
                action_name if count == 1 else f"{action_name}#{count}"
            )

    def __getitem__(self, execution: operation_graph_model.ActionExecution) -> str:
        """Return the local name of ``execution``'s action."""
        return self._names[execution]

    def names(self) -> Iterable[str]:
        """Return the local name of every action this action triggers."""
        return self._names.values()

    def items(
        self,
    ) -> Iterable[tuple[operation_graph_model.ActionExecution, str]]:
        """Return each Action Execution and its local name."""
        return self._names.items()


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


class _ActionExecutionLabels:
    """The name of every Action Execution, by the action that performs it.

    Each action names its own Action Executions, knowing nothing of the rest of the
    program, so a name can fail to stand for one Action Execution in two ways: two
    actions that trigger the same callee both name their first Action Execution of it
    ``worker``, and an action triggered more than once hands out every one of its
    names again in each execution. Either way, the name carries its caller's Action
    Execution name: ``first:worker``, ``first#2:worker``.
    """

    def __init__(self, graphs: operation_graph.OperationGraphs):
        """Name every Action Execution the actions in ``graphs`` perform."""
        self._labels: typed_name_dict.TypedNameDict[
            ast.GlobalTypedName, _ExecutionLabels
        ] = typed_name_dict.TypedNameDict()
        # How many actions give out each name, and how many times each action is
        # triggered. A name stands for one Action Execution only when one action gives it
        # and that action is itself triggered only once.
        callers_naming: dict[str, int] = {}
        execution_counts: typed_name_dict.TypedNameDict[ast.GlobalTypedName, int] = (
            typed_name_dict.TypedNameDict()
        )
        for caller, graph in graphs.items():
            labels = _ExecutionLabels(graph)
            self._labels[caller] = labels
            for execution, name in labels.items():
                callers_naming[name] = callers_naming.get(name, 0) + 1
                callee = execution.callee_action_name
                execution_counts[callee] = execution_counts.get(callee, 0) + 1
        self._ambiguous: typed_name_dict.TypedNameDict[
            ast.GlobalTypedName, set[str]
        ] = typed_name_dict.TypedNameDict()
        for caller, labels in self._labels.items():
            caller_executes_repeatedly = execution_counts.get(caller, 0) > 1
            self._ambiguous[caller] = {
                name
                for name in labels.names()
                if callers_naming[name] > 1 or caller_executes_repeatedly
            }

    def name(
        self,
        action: ast.GlobalTypedName,
        execution: operation_graph_model.ActionExecution,
    ) -> TriggeredActionExecutionName:
        """Return the local name and qualification rule for ``execution``."""
        local_name = self._labels[action][execution]
        return TriggeredActionExecutionName(
            local_name=local_name,
            uses_caller_name=local_name in self._ambiguous[action],
        )


@typing.final
class OperationGraphLabeler:
    """The names every operation and Action Execution in a program go by.

    Both are decided across the whole program at once: an action's operations are
    labeled with its own name for them in every execution, and whether an Action
    Execution's name includes its caller's Action Execution name depends on what
    the other actions call theirs. Construction prepares every label across the
    supplied graphs, so callers should construct a labeler only when they will
    use it.
    """

    def __init__(self, graphs: operation_graph.OperationGraphs):
        """Prepare labels for every action in ``graphs``."""
        self._operation_labels: _ActionOperationLabels = typed_name_dict.TypedNameDict()
        self._fragment_operation_labels: dict[
            operation_graph_model.DestructionFragmentDestroyNode, OperationLabel
        ] = {}
        for action, graph in graphs.items():
            labels = _OperationLabels(graph)
            self._operation_labels[action] = labels
            for node in graph.nodes:
                if isinstance(
                    node, operation_graph_model.DestructionFragmentDestroyNode
                ):
                    self._fragment_operation_labels[node] = labels[node]
        self._action_execution_labels = _ActionExecutionLabels(graphs)

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
        if isinstance(node, operation_graph_model.DestructionFragmentDestroyNode):
            return self._fragment_operation_labels[node]
        return self._operation_labels[action][node]

    def triggered_action_execution_name(
        self,
        action: ast.GlobalTypedName,
        execution: operation_graph_model.ActionExecution,
    ) -> TriggeredActionExecutionName:
        """Return the name rule for ``execution``."""
        return self._action_execution_labels.name(action, execution)

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
        unnamed_executions: list[operation_graph_resolver.TriggeredActionExecution] = []
        current_execution = action_execution
        while current_execution not in execution_names:
            triggered_execution = typing.cast(
                "operation_graph_resolver.TriggeredActionExecution",
                current_execution,
            )
            unnamed_executions.append(triggered_execution)
            current_execution = triggered_execution.caller
        for triggered_execution in reversed(unnamed_executions):
            execution_names[triggered_execution] = self.triggered_action_execution_name(
                triggered_execution.direct_execution_caller.action,
                triggered_execution.direct_execution.execution,
            ).render(execution_names[triggered_execution.caller])
        return execution_names[action_execution]
