"""Resolves the full operation graph reached from one action."""

from __future__ import annotations

import typing
from dataclasses import dataclass

from define.compiler.validator.reference_graph import (
    operation_graph,
    operation_graph_action_resolver,
    operation_graph_model,
)

if typing.TYPE_CHECKING:
    from define.compiler import ast


@dataclass(frozen=True, slots=True, eq=False)
class TriggeredBy:
    """The direct Action Trigger that created an action execution."""

    caller: ActionExecution
    action_trigger: operation_graph_action_resolver.ResolvedActionTrigger


@dataclass(frozen=True, slots=True, eq=False)
class ActionExecution:
    """One execution of a resolved action."""

    action: ast.GlobalTypedName
    triggered_by: TriggeredBy | None


@dataclass(frozen=True, slots=True, eq=False)
class ResolvedOperation:
    """One operation and its concrete dependencies in an action execution."""

    action_execution: ActionExecution
    operation: operation_graph_model.PositionOperationNode
    dependencies: tuple[ResolvedOperation, ...]


type _ResolvedOperationKey = tuple[
    ActionExecution, operation_graph_model.PositionOperationNode
]


@dataclass(frozen=True, slots=True)
class ResolvedOperationGraph:
    """The concrete operations reached from one action."""

    entry_action_execution: ActionExecution
    operations: tuple[ResolvedOperation, ...]


@typing.final
class ResolvedOperationGraphBuilder:
    """Build the full operation graph reached from one action."""

    def __init__(
        self,
        graphs: operation_graph.OperationGraphs,
        entry_action: ast.GlobalTypedName,
    ):
        """Initialize resolution with all graphs and the entry action."""
        self._graphs = graphs
        self._entry_action = entry_action
        self._resolved_actions = operation_graph_action_resolver.ResolvedActions(graphs)
        self._callee_action_executions: dict[
            ActionExecution,
            list[tuple[operation_graph_model.ActionTrigger, ActionExecution]],
        ] = {}
        self._operation_by_key: dict[_ResolvedOperationKey, ResolvedOperation] = {}

    def build(self) -> ResolvedOperationGraph:
        """Build concrete operations and dependencies from the entry action."""
        self._resolve_all_actions()
        entry_action_execution = ActionExecution(self._entry_action, None)
        operation_keys: list[_ResolvedOperationKey] = []
        work = [entry_action_execution]
        while work:
            action_execution = work.pop()
            resolved_action = self._resolved_actions[action_execution.action]
            for node in resolved_action.graph.nodes:
                if isinstance(node, operation_graph_model.PositionOperationNode):
                    operation_keys.append((action_execution, node))

            callees: list[ActionExecution] = []
            for action_trigger in resolved_action.action_triggers:
                callee = ActionExecution(
                    action_trigger.trigger.callee_action_name,
                    TriggeredBy(action_execution, action_trigger),
                )
                self._callee_action_executions.setdefault(action_execution, []).append(
                    (action_trigger.trigger, callee)
                )
                callees.append(callee)
            work.extend(reversed(callees))

        return ResolvedOperationGraph(
            entry_action_execution,
            tuple(self._resolve_operation(key) for key in operation_keys),
        )

    def _resolve_all_actions(self):
        visited_actions: set[str] = set()
        work = [(self._entry_action, False)]
        while work:
            action, callees_resolved = work.pop()
            graph = self._graphs[action]
            if callees_resolved:
                _ = self._resolved_actions.resolve(action)
                continue

            action_name = action.full_typed_name
            if action_name in visited_actions:
                continue
            visited_actions.add(action_name)
            work.append((action, True))
            for trigger in reversed(graph.triggers):
                work.append((trigger.callee_action_name, False))

    def _resolve_operation(
        self, operation_key: _ResolvedOperationKey
    ) -> ResolvedOperation:
        resolved = self._operation_by_key.get(operation_key)
        if resolved is not None:
            return resolved

        action_execution, operation = operation_key
        resolved_action = self._resolved_actions[action_execution.action]
        resolved_action_operation = resolved_action.operations[operation]
        dependency_keys: dict[_ResolvedOperationKey, None] = {}
        self._add_action_dependencies(
            dependency_keys,
            action_execution,
            resolved_action_operation.dependencies,
        )
        for caller_input in resolved_action_operation.caller_inputs:
            self._add_caller_input(
                dependency_keys,
                action_execution,
                caller_input,
            )
        resolved = ResolvedOperation(
            action_execution,
            operation,
            tuple(
                self._resolve_operation(dependency_key)
                for dependency_key in dependency_keys
            ),
        )
        self._operation_by_key[operation_key] = resolved
        return resolved

    def _add_action_dependencies(
        self,
        dependency_keys: dict[_ResolvedOperationKey, None],
        action_execution: ActionExecution,
        dependencies: operation_graph_action_resolver.ActionDependencies,
    ):
        for operation in dependencies.local_operations:
            dependency_keys[action_execution, operation] = None
        for guarantee in dependencies.guarantee_dependencies:
            self._add_guarantee(dependency_keys, action_execution, guarantee)

    def _add_caller_input(
        self,
        dependency_keys: dict[_ResolvedOperationKey, None],
        action_execution: ActionExecution,
        caller_input: operation_graph_action_resolver.CallerInput,
    ):
        triggered_by = action_execution.triggered_by
        if triggered_by is None:
            return
        resolved_input = triggered_by.action_trigger.input_for(caller_input)
        self._add_action_dependencies(
            dependency_keys,
            triggered_by.caller,
            resolved_input.caller_dependencies,
        )
        for caller_input_dependency in resolved_input.caller_input_dependencies:
            self._add_caller_input(
                dependency_keys,
                triggered_by.caller,
                caller_input_dependency,
            )

    def _add_guarantee(
        self,
        dependency_keys: dict[_ResolvedOperationKey, None],
        action_execution: ActionExecution,
        guarantee: operation_graph_model.GuaranteeNode,
    ):
        resolution = self._graphs.resolve_guarantee(guarantee)
        guaranteed_action_execution = action_execution
        for trigger in resolution.triggers:
            guaranteed_action_execution = self._callee_execution(
                guaranteed_action_execution, trigger
            )
        dependency_keys[guaranteed_action_execution, resolution.operation] = None

    def _callee_execution(
        self,
        action_execution: ActionExecution,
        trigger: operation_graph_model.ActionTrigger,
    ) -> ActionExecution:
        return next(
            callee
            for child_trigger, callee in self._callee_action_executions[
                action_execution
            ]
            if child_trigger is trigger
        )
