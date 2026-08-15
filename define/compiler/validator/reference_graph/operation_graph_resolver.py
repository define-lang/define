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
    """The direct Action Execution that created an action execution."""

    caller: ActionExecution
    direct_execution: operation_graph_action_resolver.ResolvedActionExecution


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
            list[tuple[operation_graph_model.ActionExecution, ActionExecution]],
        ] = {}
        self._operation_by_key: dict[_ResolvedOperationKey, ResolvedOperation] = {}
        # Only full-operation-graph resolution expands callee inputs that are not
        # direct inputs of the reusable action. Keep their resolutions at this
        # layer so reusable action resolution does not compute or retain
        # relationships that codegen never consumes.
        self._destruction_dependency_inputs: dict[
            tuple[
                operation_graph_action_resolver.ResolvedActionExecution,
                operation_graph_action_resolver.CallerInput,
            ],
            operation_graph_action_resolver.ResolvedActionExecutionInput,
        ] = {}

    def build(self) -> ResolvedOperationGraph:
        """Build concrete operations and dependencies from the entry action."""
        self._resolve_all_actions()
        entry_action_execution = ActionExecution(self._entry_action, None)
        operation_keys: list[_ResolvedOperationKey] = []
        work = [entry_action_execution]
        while work:
            caller_execution = work.pop()
            resolved_action = self._resolved_actions[caller_execution.action]
            for node in resolved_action.graph.nodes:
                if isinstance(node, operation_graph_model.PositionOperationNode):
                    operation_keys.append((caller_execution, node))

            callees: list[ActionExecution] = []
            for resolved_execution in resolved_action.action_executions:
                callee = ActionExecution(
                    resolved_execution.execution.callee_action_name,
                    TriggeredBy(caller_execution, resolved_execution),
                )
                self._callee_action_executions.setdefault(caller_execution, []).append(
                    (resolved_execution.execution, callee)
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
            for execution in reversed(graph.executions):
                work.append((execution.callee_action_name, False))

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
        destruction_operation = None
        if isinstance(
            resolved_action_operation,
            operation_graph_action_resolver.ResolvedDestructionOperation,
        ):
            destruction_operation = resolved_action_operation
        has_contributed_dependency = False
        if destruction_operation is not None:
            destruction = resolved_action.graph.destruction_for_fact(
                destruction_operation.operation.destruction_fact
            )
            if destruction.is_propagated_to_caller:
                has_contributed_dependency = (
                    self._add_contributed_destruction_dependencies(
                        dependency_keys,
                        action_execution,
                        destruction_operation.operation,
                    )
                )
        # The dependencies on either side of a caller contribution matter only
        # when this test helper expands reusable actions into one concrete graph.
        # Codegen uses the Destruction Dependencies and Destruction Contributions
        # directly, so resolving these nodes in the action resolver would add
        # relationships and work that none of its production consumers need.
        if destruction_operation is not None and has_contributed_dependency:
            for (
                dependency
            ) in destruction_operation.operation.dependencies_after_caller_contribution:
                if isinstance(dependency, operation_graph_model.PositionOperationNode):
                    dependency_keys[action_execution, dependency] = None
                else:
                    self._add_guarantee(
                        dependency_keys,
                        action_execution,
                        self._graphs.resolve_guarantee(dependency),
                    )
        else:
            self._add_action_dependencies(
                dependency_keys,
                action_execution,
                resolved_action_operation.dependencies,
            )
            if destruction_operation is not None:
                self._add_destruction_dependencies(
                    dependency_keys,
                    action_execution,
                    destruction_operation,
                )
            for caller_input in resolved_action_operation.caller_inputs:
                self._add_caller_input(
                    dependency_keys,
                    action_execution,
                    caller_input,
                )
        logical_action_execution = action_execution
        if isinstance(
            operation,
            operation_graph_model.DestructionFragmentDestroyNode,
        ):
            logical_action_execution = self._destruction_fact_execution(
                action_execution,
                operation,
            )
        resolved = ResolvedOperation(
            logical_action_execution,
            operation,
            tuple(
                self._resolve_operation(dependency_key)
                for dependency_key in dependency_keys
            ),
        )
        self._operation_by_key[operation_key] = resolved
        return resolved

    def _destruction_fact_execution(
        self,
        caller_execution: ActionExecution,
        operation: operation_graph_model.DestructionFragmentDestroyNode,
    ) -> ActionExecution:
        """Return the destroying Action Execution for a destruction-fragment operation."""
        current_execution = self._callee_execution(
            caller_execution,
            operation.direct_callee_execution,
        )
        destroying_action = operation.destruction_fact.destroying_action
        while (
            current_execution.action.full_typed_name
            != destroying_action.full_typed_name
        ):
            resolved_action = self._resolved_actions[current_execution.action]
            execution = typing.cast(
                "operation_graph_model.ActionExecution",
                resolved_action.graph.destruction_for_fact(
                    operation.destruction_fact
                ).direct_callee_execution,
            )
            current_execution = self._callee_execution(current_execution, execution)
        return current_execution

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

    def _add_dependencies_before_caller_contribution(
        self,
        dependency_keys: dict[_ResolvedOperationKey, None],
        action_execution: ActionExecution,
        dependencies: tuple[operation_graph_model.EmptyRuleDependencyNode, ...],
    ):
        for dependency in dependencies:
            match dependency:
                case operation_graph_model.PositionOperationNode():
                    dependency_keys[action_execution, dependency] = None
                case operation_graph_model.GuaranteeNode():
                    self._add_guarantee(
                        dependency_keys,
                        action_execution,
                        self._graphs.resolve_guarantee(dependency),
                    )
                case (
                    operation_graph_model.RequirementNode()
                    | operation_graph_model.CallerEmptyRuleDependenciesNode()
                ):
                    self._add_destruction_dependency_input(
                        dependency_keys,
                        action_execution,
                        dependency,
                    )

    def _add_destruction_dependencies(
        self,
        dependency_keys: dict[_ResolvedOperationKey, None],
        action_execution: ActionExecution,
        resolved_operation: operation_graph_action_resolver.ResolvedDestructionOperation,
    ):
        for destruction_dependency in resolved_operation.destruction_dependencies:
            callee_destroy = destruction_dependency.callee_destroy
            direct_callee_execution = self._callee_execution(
                action_execution,
                destruction_dependency.execution,
            )
            callee_destroy_owner_execution = self._execution_for_destruction_action(
                direct_callee_execution,
                callee_destroy.action,
                callee_destroy.operation.destruction_fact,
            )
            callee_start_dependencies: dict[_ResolvedOperationKey, None] = {}
            has_callee_start_dependency = self._add_destruction_start_before_caller(
                callee_start_dependencies,
                callee_destroy_owner_execution,
                callee_destroy.operation,
                action_execution,
            )
            if has_callee_start_dependency:
                dependency_keys.update(callee_start_dependencies)
                continue
            self._add_caller_destruction_start(
                dependency_keys,
                action_execution,
                resolved_operation,
            )

    def _add_caller_destruction_start(
        self,
        dependency_keys: dict[_ResolvedOperationKey, None],
        action_execution: ActionExecution,
        resolved_operation: operation_graph_action_resolver.ResolvedDestructionOperation,
    ):
        self._add_dependencies_before_caller_contribution(
            dependency_keys,
            action_execution,
            resolved_operation.operation.dependencies_before_caller_contribution,
        )

    def _add_destruction_start_before_caller(
        self,
        dependency_keys: dict[_ResolvedOperationKey, None],
        action_execution: ActionExecution,
        operation: operation_graph_model.DestructionFactDestroyNode,
        caller_execution: ActionExecution,
    ) -> bool:
        """Add a destruction start strictly below the contributing caller."""
        has_dependency = False
        for dependency in operation.dependencies_before_caller_contribution:
            match dependency:
                case operation_graph_model.PositionOperationNode():
                    dependency_keys[action_execution, dependency] = None
                    has_dependency = True
                case operation_graph_model.GuaranteeNode():
                    self._add_guarantee(
                        dependency_keys,
                        action_execution,
                        self._graphs.resolve_guarantee(dependency),
                    )
                    has_dependency = True
                case (
                    operation_graph_model.RequirementNode()
                    | operation_graph_model.CallerEmptyRuleDependenciesNode()
                ):
                    has_dependency |= self._add_caller_input_before_execution(
                        dependency_keys,
                        action_execution,
                        dependency,
                        caller_execution,
                    )
        return has_dependency

    def _add_caller_input_before_execution(
        self,
        dependency_keys: dict[_ResolvedOperationKey, None],
        action_execution: ActionExecution,
        caller_input: operation_graph_action_resolver.CallerInput,
        stop_execution: ActionExecution,
    ) -> bool:
        """Add caller-input dependencies before reaching one caller execution."""
        has_dependency = False
        work = [(action_execution, caller_input)]
        while work:
            current_execution, current_input = work.pop()
            triggered_by = typing.cast("TriggeredBy", current_execution.triggered_by)
            if triggered_by.caller is stop_execution:
                continue
            resolved_input = self._destruction_dependency_input_for(
                triggered_by.direct_execution,
                current_input,
            )
            self._add_action_dependencies(
                dependency_keys,
                triggered_by.caller,
                resolved_input.caller_dependencies,
            )
            if (
                resolved_input.caller_dependencies.local_operations
                or resolved_input.caller_dependencies.guarantee_dependencies
            ):
                has_dependency = True
            for dependency in resolved_input.caller_input_dependencies:
                work.append(
                    (
                        triggered_by.caller,
                        dependency,
                    )
                )
        return has_dependency

    def _destruction_dependency_input_for(
        self,
        resolved_execution: operation_graph_action_resolver.ResolvedActionExecution,
        callee_input: operation_graph_action_resolver.CallerInput,
    ) -> operation_graph_action_resolver.ResolvedActionExecutionInput:
        """Resolve an input used only before caller-contributed destruction."""
        resolved_input = resolved_execution.inputs.get(callee_input)
        if resolved_input is not None:
            return resolved_input
        key = resolved_execution, callee_input
        resolved_input = self._destruction_dependency_inputs.get(key)
        if resolved_input is None:
            resolved_input = (
                operation_graph_action_resolver.ResolvedActionExecutionInput.resolve(
                    resolved_execution.execution,
                    self._graphs,
                    callee_input,
                )
            )
            self._destruction_dependency_inputs[key] = resolved_input
        return resolved_input

    def _add_destruction_dependency_input(
        self,
        dependency_keys: dict[_ResolvedOperationKey, None],
        action_execution: ActionExecution,
        caller_input: operation_graph_action_resolver.CallerInput,
    ):
        triggered_by = action_execution.triggered_by
        if triggered_by is None:
            return
        resolved_input = self._destruction_dependency_input_for(
            triggered_by.direct_execution,
            caller_input,
        )
        self._add_action_dependencies(
            dependency_keys,
            triggered_by.caller,
            resolved_input.caller_dependencies,
        )
        for caller_input_dependency in resolved_input.caller_input_dependencies:
            self._add_destruction_dependency_input(
                dependency_keys,
                triggered_by.caller,
                caller_input_dependency,
            )

    def _add_contributed_destruction_dependencies(
        self,
        dependency_keys: dict[_ResolvedOperationKey, None],
        destruction_execution: ActionExecution,
        destruction_operation: operation_graph_model.DestructionFactDestroyNode,
    ) -> bool:
        """Add direct caller fragment operations preceding one callee Destroy."""
        current_execution = destruction_execution
        resolved_destruction_operation = operation_graph_model.DestructionOperation(
            destruction_execution.action,
            destruction_operation,
        )
        found_contribution = False
        while True:
            triggered_by = current_execution.triggered_by
            if triggered_by is None:
                raise ValueError("destruction interface reached the entry action")
            caller_execution = triggered_by.caller
            caller_action = self._resolved_actions[caller_execution.action]
            destruction_dependency = operation_graph_model.DestructionDependency(
                triggered_by.direct_execution.execution,
                resolved_destruction_operation,
            )
            contribution = caller_action.destruction_contributions.get(
                destruction_dependency
            )
            if contribution is not None:
                for operation in contribution.completion_operations:
                    dependency_keys[caller_execution, operation] = None
                found_contribution = True
            if not triggered_by.direct_execution.forwards_destruction_connections:
                return found_contribution
            current_execution = caller_execution

    def _execution_for_destruction_action(
        self,
        action_execution: ActionExecution,
        action: ast.GlobalTypedName,
        destruction_fact: operation_graph_model.DestructionFact,
    ) -> ActionExecution:
        """Return one action's execution along a destruction propagation path."""
        current_execution = action_execution
        while current_execution.action.full_typed_name != action.full_typed_name:
            resolved_action = self._resolved_actions[current_execution.action]
            execution = typing.cast(
                "operation_graph_model.ActionExecution",
                resolved_action.graph.destruction_for_fact(
                    destruction_fact
                ).direct_callee_execution,
            )
            current_execution = self._callee_execution(current_execution, execution)
        return current_execution

    def _callee_execution(
        self,
        caller_execution: ActionExecution,
        execution: operation_graph_model.ActionExecution,
    ) -> ActionExecution:
        """Return the execution created by one direct Action Execution."""
        return next(
            callee_execution
            for candidate_execution, callee_execution in self._callee_action_executions[
                caller_execution
            ]
            if candidate_execution is execution
        )

    def _add_caller_input(
        self,
        dependency_keys: dict[_ResolvedOperationKey, None],
        action_execution: ActionExecution,
        caller_input: operation_graph_action_resolver.CallerInput,
    ):
        triggered_by = action_execution.triggered_by
        if triggered_by is None:
            return
        resolved_input = triggered_by.direct_execution.inputs[caller_input]
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
        resolution: operation_graph.GuaranteePath,
    ):
        guaranteed_action_execution = action_execution
        for execution in resolution.executions:
            guaranteed_action_execution = self._callee_execution(
                guaranteed_action_execution,
                execution,
            )
        dependency_keys[guaranteed_action_execution, resolution.operation] = None
