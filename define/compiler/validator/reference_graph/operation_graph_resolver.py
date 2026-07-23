"""Resolves the full operation graph reached from one action."""

from __future__ import annotations

import typing
from dataclasses import dataclass

from define.compiler import ast
from define.compiler.data_structures import typed_name_dict
from define.compiler.validator.reference_graph import (
    operation_graph,
    operation_graph_action_resolver,
)


@dataclass(frozen=True, slots=True, eq=False)
class TriggeredBy:
    """The direct Action Triggering that created an action execution."""

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
    operation: operation_graph.PositionOperationNode
    dependencies: tuple[ResolvedOperation, ...]


type _ResolvedOperationKey = tuple[ActionExecution, int]


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
        self._resolved_actions = typed_name_dict.TypedNameDict[
            ast.GlobalTypedName, operation_graph_action_resolver.ResolvedAction
        ]()
        self._callee_action_executions: dict[
            tuple[ActionExecution, int],
            ActionExecution,
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
                if isinstance(node, operation_graph.PositionOperationNode):
                    operation_keys.append((action_execution, node.node_id))

            callees: list[ActionExecution] = []
            for action_trigger in resolved_action.action_triggers:
                callee = ActionExecution(
                    action_trigger.trigger.callee_action_name,
                    TriggeredBy(action_execution, action_trigger),
                )
                self._callee_action_executions[
                    (action_execution, id(action_trigger.trigger))
                ] = callee
                callees.append(callee)
            work.extend(reversed(callees))

        return ResolvedOperationGraph(
            entry_action_execution,
            tuple(self._resolve_operation(key) for key in operation_keys),
        )

    def _resolve_all_actions(self):
        visited_actions: set[str] = set()
        # Walk down the callee tree and resolve them from leaf
        # to root.
        work = [(self._entry_action, False)]
        while work:
            action, callees_resolved = work.pop()
            graph = self._graphs[action]
            if callees_resolved:
                self._resolved_actions[action] = (
                    operation_graph_action_resolver.ActionResolver(
                        graph, self._resolved_actions
                    ).resolve()
                )
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

        action_execution, node_id = operation_key
        resolved_action = self._resolved_actions[action_execution.action]
        operation = typing.cast(
            "operation_graph.PositionOperationNode",
            resolved_action.graph.nodes[node_id],
        )
        dependency_keys: dict[_ResolvedOperationKey, None] = {}
        self._add_action_dependencies(
            dependency_keys,
            action_execution,
            resolved_action.dependencies_by_operation_node_id[node_id],
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
        for node_id in dependencies.local_operation_node_ids:
            dependency_keys[action_execution, node_id] = None
        for action_input in dependencies.action_inputs:
            self._add_caller_input(dependency_keys, action_execution, action_input)
        for guarantee in dependencies.guarantee_dependencies:
            self._add_guarantee(dependency_keys, action_execution, guarantee)

    def _add_caller_input(
        self,
        dependency_keys: dict[_ResolvedOperationKey, None],
        action_execution: ActionExecution,
        action_input: operation_graph_action_resolver.ActionInput,
    ):
        triggered_by = action_execution.triggered_by
        if triggered_by is None:
            return
        resolved_input = triggered_by.action_trigger.input_for(action_input)
        for node_id in resolved_input.callee_dependency_node_ids:
            dependency_keys[action_execution, node_id] = None
        self._add_action_dependencies(
            dependency_keys,
            triggered_by.caller,
            resolved_input.caller_dependencies,
        )

    def _add_guarantee(
        self,
        dependency_keys: dict[_ResolvedOperationKey, None],
        action_execution: ActionExecution,
        guarantee: operation_graph.GuaranteeNode,
    ):
        triggers, operation_node_id = self._graphs.resolve_guarantee(guarantee)
        guaranteed_action_execution = action_execution
        for trigger in triggers:
            guaranteed_action_execution = self._callee_execution(
                guaranteed_action_execution, trigger
            )
        dependency_keys[guaranteed_action_execution, operation_node_id] = None

    def _callee_execution(
        self,
        action_execution: ActionExecution,
        trigger: operation_graph.ActionTrigger,
    ) -> ActionExecution:
        return self._callee_action_executions[action_execution, id(trigger)]
