"""Resolves the full operation graph reached from one action."""

from __future__ import annotations

import abc
import typing
from dataclasses import dataclass

from define.compiler.validator.reference_graph import (
    operation_graph,
    operation_graph_action_resolver,
    operation_graph_model,
)

if typing.TYPE_CHECKING:
    from collections.abc import Sequence

    from define.compiler import ast


class ActionExecution(abc.ABC):
    """One execution of a resolved action."""

    __slots__: typing.ClassVar[tuple[str, ...]] = ()

    @property
    @abc.abstractmethod
    def action(self) -> ast.GlobalTypedName:
        """Return the action being executed."""


class EntryActionExecution(ActionExecution):
    """The entry Action Execution of a resolved Operation Graph."""

    __slots__: typing.ClassVar[tuple[str, ...]] = ("_action",)
    _action: ast.GlobalTypedName

    def __init__(self, action: ast.GlobalTypedName):
        """Create the entry Action Execution."""
        self._action = action

    @property
    @typing.override
    def action(self) -> ast.GlobalTypedName:
        """Return the entry action."""
        return self._action


@dataclass(frozen=True, slots=True, eq=False)
class TriggeredActionExecution(ActionExecution):
    """An Action Execution created by a direct Action Execution."""

    caller: ActionExecution
    direct_execution: operation_graph_action_resolver.ResolvedActionExecution

    @property
    @typing.override
    def action(self) -> ast.GlobalTypedName:
        """Return the action named by the direct Action Execution."""
        return self.direct_execution.execution.callee_action_name

    @property
    def direct_execution_caller(self) -> ActionExecution:
        """Return the caller whose graph records this direct Action Execution."""
        return self.caller


@dataclass(frozen=True, slots=True, eq=False)
class ContributedDestructorActionExecution(TriggeredActionExecution):
    """A Destructor execution fired by a destroyer with bindings from a caller."""

    contributing_execution: ActionExecution

    @property
    @typing.override
    def direct_execution_caller(self) -> ActionExecution:
        """Return the caller that contributed this Destructor Action Execution."""
        return self.contributing_execution


@dataclass(frozen=True, slots=True, eq=False)
class ResolvedOperation:
    """One operation and its concrete dependencies in an action execution."""

    action_execution: ActionExecution
    operation: operation_graph_model.PositionOperationNode
    dependencies: tuple[ResolvedOperation, ...]


type _ResolvedOperationKey = tuple[
    ActionExecution, operation_graph_model.PositionOperationNode
]
type _CalleeExecutionKey = tuple[ActionExecution, operation_graph_model.ActionExecution]


@dataclass(frozen=True, slots=True)
class ResolvedOperationGraph:
    """The concrete operations reached from one action."""

    entry_action_execution: EntryActionExecution
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
        self._resolved_empty_rule_binding_hole_by_operation_node: dict[
            operation_graph_model.EmptyRuleBindingHoleNode,
            operation_graph_model.EmptyRuleBindingHole,
        ] = {}
        self._resolved_actions = operation_graph_action_resolver.ResolvedActions(
            graphs,
            resolved_empty_rule_binding_hole_by_operation_node=(
                self._resolved_empty_rule_binding_hole_by_operation_node
            ),
        )
        self._callee_execution_by_key: dict[
            _CalleeExecutionKey, TriggeredActionExecution
        ] = {}
        self._operation_by_key: dict[_ResolvedOperationKey, ResolvedOperation] = {}
        # Only full-operation-graph resolution binds callee nodes used exclusively
        # before caller destruction contributions. Keep those bindings at this
        # layer because codegen never consumes them.
        self._callee_bindings_for_destruction_before_caller_contribution: dict[
            tuple[
                operation_graph_action_resolver.ResolvedActionExecution,
                operation_graph_model.BindingHole,
            ],
            operation_graph_action_resolver.CalleeBinding,
        ] = {}

    def build(self) -> ResolvedOperationGraph:
        """Build concrete operations and dependencies from the entry action."""
        self._resolve_all_actions()
        entry_action_execution = EntryActionExecution(self._entry_action)
        operation_keys: list[_ResolvedOperationKey] = []
        pending_destructors: list[
            tuple[
                ActionExecution,
                operation_graph_model.ResolvedCalleeDestroy,
                operation_graph_action_resolver.ResolvedActionExecution,
            ]
        ] = []
        work: list[ActionExecution] = [entry_action_execution]
        while work:
            caller_execution = work.pop()
            resolved_action = self._resolved_actions[caller_execution.action]
            for operation in resolved_action.graph.particle_operations:
                operation_keys.append((caller_execution, operation))

            callees: list[TriggeredActionExecution] = []
            for resolved_execution in resolved_action.action_executions:
                callee = TriggeredActionExecution(
                    caller_execution,
                    resolved_execution,
                )
                self._index_callee_execution(callee)
                callees.append(callee)
            for (
                resolved_callee_destroy,
                resolved_contribution,
            ) in resolved_action.destruction_contributions.items():
                for destructor in resolved_contribution.destructors:
                    pending_destructors.append(
                        (caller_execution, resolved_callee_destroy, destructor)
                    )
            work.extend(reversed(callees))

        for (
            contributing_execution,
            resolved_callee_destroy,
            destructor,
        ) in pending_destructors:
            direct_callee_execution = self._callee_execution(
                contributing_execution,
                resolved_callee_destroy.direct_callee_execution,
            )
            callee_destroy = resolved_callee_destroy.callee_destroy
            destroying_execution = self._execution_for_destruction_action(
                direct_callee_execution,
                callee_destroy.action,
                callee_destroy.operation.destruction_fact,
            )
            destructor_execution = ContributedDestructorActionExecution(
                caller=destroying_execution,
                direct_execution=destructor,
                contributing_execution=contributing_execution,
            )
            self._index_callee_execution(destructor_execution)
            resolved_destructor_action = self._resolved_actions[
                destructor_execution.action
            ]
            for operation in resolved_destructor_action.graph.particle_operations:
                operation_keys.append((destructor_execution, operation))

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
            for execution in graph.executions_including_contributions():
                work.append((execution.callee_action_name, False))

    def _resolve_operation(
        self, operation_key: _ResolvedOperationKey
    ) -> ResolvedOperation:
        resolved = self._operation_by_key.get(operation_key)
        if resolved is not None:
            return resolved

        action_execution, operation = operation_key
        resolved_action = self._resolved_actions[action_execution.action]
        dependency_keys: dict[_ResolvedOperationKey, None] = {}
        is_destruction_operation = isinstance(
            operation,
            operation_graph_model.DestructionFactDestroyNode,
        )
        has_contributed_dependency = False
        if is_destruction_operation:
            destruction = resolved_action.graph.destruction_for_fact(
                operation.destruction_fact
            )
            if destruction.is_propagated_to_caller:
                has_contributed_dependency = (
                    self._add_contributed_destruction_dependencies(
                        dependency_keys,
                        action_execution,
                        operation,
                    )
                )
        # The dependencies on either side of a caller contribution matter only
        # when this test helper expands reusable actions into one concrete graph.
        # Codegen uses the Destruction Dependencies and Destruction Contributions
        # directly, so resolving these nodes in the action resolver would add
        # relationships and work that none of its production consumers need.
        if is_destruction_operation and has_contributed_dependency:
            for dependency in operation.dependencies_after_caller_contribution:
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
                resolved_action.local_operations_depended_on_by(operation),
                resolved_action.guarantee_dependencies_for(operation),
            )
            if is_destruction_operation:
                self._add_destruction_dependencies(
                    dependency_keys,
                    action_execution,
                    operation,
                    resolved_action.destruction_dependencies_for(operation),
                )
            for binding_hole in resolved_action.binding_holes_depended_on_by(operation):
                self._add_dependencies_for_binding_hole(
                    dependency_keys,
                    action_execution,
                    binding_hole,
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
        local_operations: Sequence[operation_graph_model.PositionOperationNode],
        guarantee_dependencies: Sequence[operation_graph.GuaranteePath],
    ):
        for operation in local_operations:
            dependency_keys[action_execution, operation] = None
        for guarantee in guarantee_dependencies:
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
                    | operation_graph_model.EmptyRuleBindingHoleNode()
                ):
                    self._add_destruction_dependencies_for_binding_hole(
                        dependency_keys,
                        action_execution,
                        dependency,
                    )

    def _add_destruction_dependencies(
        self,
        dependency_keys: dict[_ResolvedOperationKey, None],
        action_execution: ActionExecution,
        operation: operation_graph_model.DestructionFactDestroyNode,
        destruction_dependencies: Sequence[operation_graph_model.ResolvedCalleeDestroy],
    ):
        for resolved_callee_destroy in destruction_dependencies:
            callee_destroy = resolved_callee_destroy.callee_destroy
            direct_callee_execution = self._callee_execution(
                action_execution,
                resolved_callee_destroy.direct_callee_execution,
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
                operation,
            )

    def _add_caller_destruction_start(
        self,
        dependency_keys: dict[_ResolvedOperationKey, None],
        action_execution: ActionExecution,
        operation: operation_graph_model.DestructionFactDestroyNode,
    ):
        self._add_dependencies_before_caller_contribution(
            dependency_keys,
            action_execution,
            operation.dependencies_before_caller_contribution,
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
                    | operation_graph_model.EmptyRuleBindingHoleNode()
                ):
                    has_dependency |= (
                        self._add_dependencies_for_binding_hole_before_execution(
                            dependency_keys,
                            action_execution,
                            dependency,
                            caller_execution,
                        )
                    )
        return has_dependency

    def _add_dependencies_for_binding_hole_before_execution(
        self,
        dependency_keys: dict[_ResolvedOperationKey, None],
        action_execution: ActionExecution,
        binding_hole: operation_graph_model.BindingHole,
        stop_execution: ActionExecution,
    ) -> bool:
        """Add a Binding Hole's dependencies before reaching one caller execution."""
        has_dependency = False
        work = [(action_execution, binding_hole)]
        while work:
            current_execution, current_binding_hole = work.pop()
            triggered_execution = typing.cast(
                "TriggeredActionExecution", current_execution
            )
            if triggered_execution.caller is stop_execution:
                continue
            callee_binding = (
                self._callee_binding_for_destruction_before_caller_contribution(
                    triggered_execution,
                    current_binding_hole,
                )
            )
            self._add_action_dependencies(
                dependency_keys,
                triggered_execution.caller,
                callee_binding.caller_dependencies.local_operations,
                callee_binding.caller_dependencies.guarantee_dependencies,
            )
            if (
                callee_binding.caller_dependencies.local_operations
                or callee_binding.caller_dependencies.guarantee_dependencies
            ):
                has_dependency = True
            for caller_binding_hole in callee_binding.caller_binding_holes:
                work.append(
                    (
                        triggered_execution.caller,
                        caller_binding_hole,
                    )
                )
        return has_dependency

    def _callee_binding_for_destruction_before_caller_contribution(
        self,
        triggered_execution: TriggeredActionExecution,
        callee_binding_hole: operation_graph_model.BindingHole,
    ) -> operation_graph_action_resolver.CalleeBinding:
        """Return one binding used before a caller's destruction contribution."""
        resolved_execution = triggered_execution.direct_execution
        callee_binding_hole = self._binding_hole_for_destruction(callee_binding_hole)
        callee_binding = self._existing_callee_binding_for_destruction(
            resolved_execution,
            callee_binding_hole,
        )
        if callee_binding is not None:
            return callee_binding

        callee_binding_holes_to_bind = [(callee_binding_hole, False)]
        while callee_binding_holes_to_bind:
            callee_binding_hole_to_bind, prerequisite_holes_are_bound = (
                callee_binding_holes_to_bind.pop()
            )
            execution_and_binding_hole = (
                resolved_execution,
                callee_binding_hole_to_bind,
            )
            callee_binding = self._existing_callee_binding_for_destruction(
                resolved_execution,
                callee_binding_hole_to_bind,
            )
            if callee_binding is not None:
                continue
            prerequisite_callee_binding_holes = (
                operation_graph_action_resolver.prerequisite_binding_holes(
                    callee_binding_hole_to_bind
                )
            )
            if not prerequisite_holes_are_bound:
                callee_binding_holes_to_bind.append((callee_binding_hole_to_bind, True))
                for prerequisite_callee_binding_hole in reversed(
                    prerequisite_callee_binding_holes
                ):
                    callee_binding_holes_to_bind.append(
                        (prerequisite_callee_binding_hole, False)
                    )
                continue
            prerequisite_callee_bindings: list[
                operation_graph_action_resolver.CalleeBinding
            ] = []
            for prerequisite_callee_binding_hole in prerequisite_callee_binding_holes:
                prerequisite_callee_binding = resolved_execution.callee_bindings.get(
                    prerequisite_callee_binding_hole
                )
                if prerequisite_callee_binding is None:
                    prerequisite_callee_binding = self._callee_bindings_for_destruction_before_caller_contribution[
                        resolved_execution, prerequisite_callee_binding_hole
                    ]
                prerequisite_callee_bindings.append(prerequisite_callee_binding)
            self._callee_bindings_for_destruction_before_caller_contribution[
                execution_and_binding_hole
            ] = operation_graph_action_resolver.CalleeBinding.for_callee_binding_hole(
                resolved_execution.execution,
                self._graphs,
                callee_binding_hole_to_bind,
                prerequisite_callee_bindings,
                replacement_depends_on_targets_by_node={},
            )
        return self._callee_bindings_for_destruction_before_caller_contribution[
            resolved_execution, callee_binding_hole
        ]

    def _binding_hole_for_destruction(
        self,
        binding_hole: operation_graph_model.BindingHole,
    ) -> operation_graph_model.BindingHole:
        """Translate an Operation Graph node to its resolved Binding Hole."""
        if isinstance(
            binding_hole,
            operation_graph_model.EmptyRuleBindingHoleNode,
        ):
            return self._resolved_empty_rule_binding_hole_by_operation_node[
                binding_hole
            ]
        return binding_hole

    def _existing_callee_binding_for_destruction(
        self,
        resolved_execution: operation_graph_action_resolver.ResolvedActionExecution,
        binding_hole: operation_graph_model.BindingHole,
    ) -> operation_graph_action_resolver.CalleeBinding | None:
        """Return an ordinary or already-created destruction binding."""
        callee_binding = resolved_execution.callee_bindings.get(binding_hole)
        if callee_binding is not None:
            return callee_binding
        return self._callee_bindings_for_destruction_before_caller_contribution.get(
            (resolved_execution, binding_hole)
        )

    def _add_destruction_dependencies_for_binding_hole(
        self,
        dependency_keys: dict[_ResolvedOperationKey, None],
        action_execution: ActionExecution,
        binding_hole: operation_graph_model.BindingHole,
    ):
        if not isinstance(action_execution, TriggeredActionExecution):
            return
        callee_binding = (
            self._callee_binding_for_destruction_before_caller_contribution(
                action_execution,
                binding_hole,
            )
        )
        self._add_action_dependencies(
            dependency_keys,
            action_execution.caller,
            callee_binding.caller_dependencies.local_operations,
            callee_binding.caller_dependencies.guarantee_dependencies,
        )
        for caller_binding_hole in callee_binding.caller_binding_holes:
            self._add_destruction_dependencies_for_binding_hole(
                dependency_keys,
                action_execution.caller,
                caller_binding_hole,
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
            if not isinstance(current_execution, TriggeredActionExecution):
                raise TypeError("destruction interface reached the entry action")
            caller_execution = current_execution.caller
            caller_action = self._resolved_actions[caller_execution.action]
            resolved_callee_destroy = operation_graph_model.ResolvedCalleeDestroy(
                current_execution.direct_execution.execution,
                resolved_destruction_operation,
            )
            resolved_contribution = caller_action.destruction_contributions.get(
                resolved_callee_destroy
            )
            if resolved_contribution is not None:
                completion_operations = resolved_contribution.operation_graph_contribution.completion_operations
                for operation in completion_operations:
                    dependency_keys[caller_execution, operation] = None
                if completion_operations:
                    found_contribution = True
            if not current_execution.direct_execution.forwards_destruction_connections:
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
    ) -> TriggeredActionExecution:
        """Return the execution created by one direct Action Execution."""
        return self._callee_execution_by_key[caller_execution, execution]

    def _index_callee_execution(self, callee_execution: TriggeredActionExecution):
        """Make repeated callee resolution independent of caller fan-out."""
        self._callee_execution_by_key[
            callee_execution.direct_execution_caller,
            callee_execution.direct_execution.execution,
        ] = callee_execution

    def _add_dependencies_for_binding_hole(
        self,
        dependency_keys: dict[_ResolvedOperationKey, None],
        action_execution: ActionExecution,
        binding_hole: operation_graph_model.BindingHole,
    ):
        if not isinstance(action_execution, TriggeredActionExecution):
            return
        callee_binding = action_execution.direct_execution.callee_bindings[binding_hole]
        direct_execution_caller = action_execution.direct_execution_caller
        self._add_action_dependencies(
            dependency_keys,
            direct_execution_caller,
            callee_binding.caller_dependencies.local_operations,
            callee_binding.caller_dependencies.guarantee_dependencies,
        )
        for caller_binding_hole in callee_binding.caller_binding_holes:
            self._add_dependencies_for_binding_hole(
                dependency_keys,
                direct_execution_caller,
                caller_binding_hole,
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
