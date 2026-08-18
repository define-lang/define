"""Resolves symbolic dependencies between per-action operation graphs.

The purpose of this resolver is to take individual actions and resolve
the dependency relationships between them and their direct callees.
When we say "resolve a dependency relationship," we mean determine how
a dependency that crosses an Action Execution boundary is represented
from the caller's perspective. For any dependencies that cannot be resolved,
we fold them into the caller's contract for resolution at runtime or in
later stages of the compiler.

More concretely, we need to provide the dependency resolution information
that action_plan needs in order to do its responsibilities. Each action is
resolved exactly once into a re-usable object representing the dependency
interface of that action.

Note that this module must not choose or construct code-generation Action
Fragments; that is the responsibility of action_plan. This module does not
understand or know about Action Fragments; it knows about the relationships
between a caller action and its direct callees.

This module must not substitute for deficiencies in the operation_graph
itself. The Operation Graph must internally resolve every dependency
relationship that can be determined from its own nodes and dependency edges.

Also note that this module is restricted to resolving the relationships
between a caller and its direct callees. It must not perform general graph
repair or transitive reduction.

The primary "customer" of this module is action_plan in codegen. There is
also the full-graph consumer, operation_graph_resolver. However, anything
that is needed _only_ by operation_graph_resolver should live only in
operation_graph_resolver. This module only needs to provide support for
action_plan, and operation_graph_resolver uses it for the purposes of
modularity.
"""

from __future__ import annotations

import typing
from dataclasses import dataclass, field

from define.compiler.data_structures import typed_name_dict
from define.compiler.validator.reference_graph import (
    operation_graph,
    operation_graph_model,
)

# Resolution must be limited to substitutions that codegen can perform while
# consuming an operation graph. Operation graphs must already contain the
# correct minimal direct dependencies; resolution must never compensate for
# missing graph-construction information by analyzing or repairing the resolved
# graph.

if typing.TYPE_CHECKING:
    from collections.abc import (
        Iterable,
        Mapping,
    )

    from define.compiler import ast


type _RequirementOrActionParentNode = (
    operation_graph_model.ActionParentLastOperationNode
    | operation_graph_model.RequirementNode
)


@dataclass(frozen=True, slots=True)
class ActionDependencies:
    """Dependencies resolved within one reusable action graph."""

    local_operations: list[operation_graph_model.PositionOperationNode]
    guarantee_dependencies: list[operation_graph.GuaranteePath]

    def concrete_nodes(
        self,
    ) -> Iterable[operation_graph_model.ConcreteOperationNode]:
        """Iterate over the operation-graph nodes represented by these relationships."""
        yield from self.local_operations
        for guarantee in self.guarantee_dependencies:
            yield guarantee.guarantee


@dataclass(frozen=True, slots=True, eq=False)
class ResolvedActionOperation:
    """One operation and its relationships within one reusable action."""

    operation: operation_graph_model.PositionOperationNode
    dependencies: ActionDependencies
    binding_holes_depended_on: list[operation_graph_model.BindingHole]
    dependent_callee_bindings: list[CalleeBinding]
    action_executions: list[ResolvedActionExecution]


@dataclass(frozen=True, slots=True, eq=False)
class ResolvedDestructionOperation(ResolvedActionOperation):
    """One Destruction Fact Destroy and its caller-contribution relationships."""

    operation: operation_graph_model.DestructionFactDestroyNode
    destruction_dependencies: list[operation_graph_model.DestructionDependency]


def _append_action_dependency(
    node: operation_graph_model.OperationNode,
    dependencies: ActionDependencies,
    binding_holes: list[operation_graph_model.BindingHole],
    operation_graphs: operation_graph.OperationGraphs,
):
    """Add one ordinary dependency to its resolved action relationship."""
    match node:
        case operation_graph_model.PositionOperationNode():
            dependencies.local_operations.append(node)
        case (
            operation_graph_model.ActionParentLastOperationNode()
            | operation_graph_model.RequirementNode()
            | operation_graph_model.CallerEmptyRuleDependenciesNode()
            | operation_graph_model.CallerMoveRuleFillDependencyNode()
        ):
            binding_holes.append(node)
        case operation_graph_model.GuaranteeNode():
            dependencies.guarantee_dependencies.append(
                operation_graphs.resolve_guarantee(node)
            )
        case _:
            raise TypeError(f"unknown operation node type: {type(node).__name__}")


def _partition_caller_dependencies(
    nodes: Iterable[operation_graph_model.OperationNode],
    operation_graphs: operation_graph.OperationGraphs,
) -> tuple[ActionDependencies, list[operation_graph_model.BindingHole]]:
    """Separate local Particle Operations and guarantees from Binding Holes."""
    dependencies = ActionDependencies([], [])
    binding_holes: list[operation_graph_model.BindingHole] = []
    for node in nodes:
        _append_action_dependency(node, dependencies, binding_holes, operation_graphs)
    return dependencies, binding_holes


@dataclass(slots=True, eq=False)
class CalleeBinding:
    """One callee-to-caller binding across a direct Action Execution."""

    callee_binding_hole: operation_graph_model.BindingHole
    caller_dependencies: ActionDependencies
    caller_binding_holes: list[operation_graph_model.BindingHole]
    contributed_destruction_operations: list[
        operation_graph_model.DestructionFragmentDestroyNode
    ] = field(default_factory=list)

    @classmethod
    def for_callee_binding_hole(
        cls,
        caller_graph: operation_graph.OperationGraph,
        execution: operation_graph_model.ActionExecution,
        operation_graphs: operation_graph.OperationGraphs,
        callee_binding_hole: operation_graph_model.BindingHole,
        callee_node_bindings_needed_for_empty_rule_completion: list[CalleeBinding],
    ) -> typing.Self:
        """Bind one callee Binding Hole from the direct caller's perspective."""
        match callee_binding_hole:
            case operation_graph_model.CallerMoveRuleFillDependencyNode(
                caller_move_rule_fill_dependency=caller_dependency
            ):
                return cls._resolve_caller_move_rule_fill_dependency(
                    execution,
                    operation_graphs,
                    callee_binding_hole,
                    caller_dependency,
                )
            case (
                operation_graph_model.CallerMoveRuleFillDependency() as caller_dependency
            ):
                return cls._resolve_caller_move_rule_fill_dependency(
                    execution,
                    operation_graphs,
                    callee_binding_hole,
                    caller_dependency,
                )
            case operation_graph_model.CallerEmptyRuleDependenciesNode(
                caller_empty_rule_dependencies=caller_dependencies
            ):
                return cls._resolve_caller_empty_rule_dependencies(
                    execution,
                    caller_graph,
                    operation_graphs,
                    callee_binding_hole,
                    caller_dependencies,
                    callee_node_bindings_needed_for_empty_rule_completion,
                )
            case (
                operation_graph_model.CallerEmptyRuleDependencies() as caller_dependencies
            ):
                return cls._resolve_caller_empty_rule_dependencies(
                    execution,
                    caller_graph,
                    operation_graphs,
                    callee_binding_hole,
                    caller_dependencies,
                    callee_node_bindings_needed_for_empty_rule_completion,
                )
            case (
                operation_graph_model.ActionParentLastOperationNode()
                | operation_graph_model.RequirementNode()
            ):
                return cls._for_requirement_or_action_parent_binding_hole(
                    execution,
                    operation_graphs,
                    callee_binding_hole,
                )
        typing.assert_never(callee_binding_hole)

    @classmethod
    def _resolve_caller_move_rule_fill_dependency(
        cls,
        execution: operation_graph_model.ActionExecution,
        operation_graphs: operation_graph.OperationGraphs,
        callee_binding_hole: (
            operation_graph_model.CallerMoveRuleFillDependencyNode
            | operation_graph_model.CallerMoveRuleFillDependency
        ),
        caller_dependency: operation_graph_model.CallerMoveRuleFillDependency,
    ) -> typing.Self:
        """Resolve one Move Rule Fill dependency from the caller's perspective."""
        substitution = execution.substitute_caller_move_rule_fill_dependency(
            caller_dependency
        )
        dependencies = ActionDependencies([], [])
        caller_binding_holes: list[operation_graph_model.BindingHole] = []
        if isinstance(substitution, operation_graph_model.CallerMoveRuleFillDependency):
            caller_binding_holes.append(substitution)
        elif substitution is not None:
            _append_action_dependency(
                substitution,
                dependencies,
                caller_binding_holes,
                operation_graphs,
            )
        return cls(callee_binding_hole, dependencies, caller_binding_holes)

    @classmethod
    def _resolve_caller_empty_rule_dependencies(
        cls,
        execution: operation_graph_model.ActionExecution,
        caller_graph: operation_graph.OperationGraph,
        operation_graphs: operation_graph.OperationGraphs,
        callee_binding_hole: (
            operation_graph_model.CallerEmptyRuleDependenciesNode
            | operation_graph_model.CallerEmptyRuleDependencies
        ),
        caller_dependencies: operation_graph_model.CallerEmptyRuleDependencies,
        callee_node_bindings_needed_for_empty_rule_completion: list[CalleeBinding],
    ) -> typing.Self:
        """Resolve one set of Empty Rule dependencies from the caller's perspective."""
        direct_caller_state_for_empty_rule = (
            operation_graph_model.DirectCallerStateForEmptyRule()
        )
        for node_binding in callee_node_bindings_needed_for_empty_rule_completion:
            direct_caller_state_for_empty_rule.add_callee_node_resolution(
                node_binding.caller_dependencies.concrete_nodes(),
                node_binding.caller_binding_holes,
            )
        substitution = caller_graph.apply_callee_empty_rule_in_caller(
            execution,
            caller_dependencies,
            direct_caller_state_for_empty_rule,
        )
        dependencies, caller_binding_holes = _partition_caller_dependencies(
            substitution.caller_nodes,
            operation_graphs,
        )
        if substitution.caller_empty_rule_dependencies is not None:
            caller_binding_holes.append(substitution.caller_empty_rule_dependencies)
        return cls(callee_binding_hole, dependencies, caller_binding_holes)

    @classmethod
    def _for_requirement_or_action_parent_binding_hole(
        cls,
        execution: operation_graph_model.ActionExecution,
        operation_graphs: operation_graph.OperationGraphs,
        callee_binding_hole: _RequirementOrActionParentNode,
    ) -> typing.Self:
        """Bind one Action Parent or Requirement hole in the direct caller."""
        dependencies, caller_binding_holes = _partition_caller_dependencies(
            (execution.caller_operation_for_callee_binding_hole(callee_binding_hole),),
            operation_graphs,
        )
        return cls(callee_binding_hole, dependencies, caller_binding_holes)


def callee_nodes_needed_for_empty_rule_completion(
    callee_node: operation_graph_model.BindingHole,
) -> tuple[operation_graph_model.BindingHole, ...]:
    """Identify callee nodes whose bindings are needed to complete the Empty Rule."""
    match callee_node:
        case operation_graph_model.CallerEmptyRuleDependenciesNode(
            caller_empty_rule_dependencies=dependencies
        ):
            return dependencies.callee_nodes_to_bind_for_empty_rule_completion
        case operation_graph_model.CallerEmptyRuleDependencies() as dependencies:
            return dependencies.callee_nodes_to_bind_for_empty_rule_completion
        case _:
            return ()


def _callee_binding_holes_in_binding_order(
    callee_binding_holes: Iterable[operation_graph_model.BindingHole],
) -> list[operation_graph_model.BindingHole]:
    """Order callee Binding Holes so Empty Rule prerequisites come first.

    CallerEmptyRuleDependencies names the other callee nodes whose bindings must
    be substituted into its Empty Rule. Those nodes must therefore be resolved
    first. ResolvedAction.binding_holes stores this order so every caller uses
    it when resolving an Action Execution of the action.
    """
    ordered_binding_holes: list[operation_graph_model.BindingHole] = []
    ordered_binding_hole_set: set[operation_graph_model.BindingHole] = set()
    for callee_binding_hole in callee_binding_holes:
        nodes_to_order = [(callee_binding_hole, False)]
        while nodes_to_order:
            binding_hole_to_order, required_nodes_are_ordered = nodes_to_order.pop()
            if binding_hole_to_order in ordered_binding_hole_set:
                continue
            if required_nodes_are_ordered:
                ordered_binding_holes.append(binding_hole_to_order)
                ordered_binding_hole_set.add(binding_hole_to_order)
                continue
            nodes_to_order.append((binding_hole_to_order, True))
            for prerequisite_binding_hole in reversed(
                callee_nodes_needed_for_empty_rule_completion(binding_hole_to_order)
            ):
                nodes_to_order.append((prerequisite_binding_hole, False))
    return ordered_binding_holes


@typing.final
class CalleeBindings:
    """The ordered callee-to-caller bindings of one Action Execution."""

    def __init__(
        self,
        bindings_by_callee_binding_hole: dict[
            operation_graph_model.BindingHole, CalleeBinding
        ],
    ):
        """Initialize with the Action Execution's direct callee bindings."""
        self._bindings_by_callee_binding_hole = bindings_by_callee_binding_hole

    @classmethod
    def for_action_execution(
        cls,
        caller_graph: operation_graph.OperationGraph,
        execution: operation_graph_model.ActionExecution,
        operation_graphs: operation_graph.OperationGraphs,
        callee_binding_holes: list[operation_graph_model.BindingHole],
        destruction_fragments: Iterable[
            operation_graph_model.ContributedDestructionFragment
        ],
    ) -> typing.Self:
        """Create the bindings and associate caller-contributed destruction fragments.

        ``callee_binding_holes`` must be ordered such that every callee Binding
        Hole involved in an Empty Rule completion comes after the callee Binding
        Holes needed to complete its Empty Rule.
        """
        bindings_by_callee_binding_hole: dict[
            operation_graph_model.BindingHole, CalleeBinding
        ] = {}
        for callee_binding_hole in callee_binding_holes:
            callee_node_bindings_needed_for_empty_rule_completion: list[
                CalleeBinding
            ] = []
            for callee_node in callee_nodes_needed_for_empty_rule_completion(
                callee_binding_hole
            ):
                callee_node_bindings_needed_for_empty_rule_completion.append(
                    bindings_by_callee_binding_hole[callee_node]
                )
            bindings_by_callee_binding_hole[callee_binding_hole] = (
                CalleeBinding.for_callee_binding_hole(
                    caller_graph,
                    execution,
                    operation_graphs,
                    callee_binding_hole,
                    callee_node_bindings_needed_for_empty_rule_completion,
                )
            )
        callee_bindings = cls(bindings_by_callee_binding_hole)
        callee_bindings._associate_contributed_destruction_operations_with_callee_bindings(
            destruction_fragments,
            operation_graphs,
        )
        return callee_bindings

    def values(self) -> Iterable[CalleeBinding]:
        """Return the direct callee bindings in their established order."""
        return self._bindings_by_callee_binding_hole.values()

    def __getitem__(
        self, callee_binding_hole: operation_graph_model.BindingHole
    ) -> CalleeBinding:
        """Return the binding for one direct callee Binding Hole."""
        return self._bindings_by_callee_binding_hole[callee_binding_hole]

    def get(
        self, callee_binding_hole: operation_graph_model.BindingHole
    ) -> CalleeBinding | None:
        """Return the binding for one direct callee Binding Hole, if present."""
        return self._bindings_by_callee_binding_hole.get(callee_binding_hole)

    def _associate_contributed_destruction_operations_with_callee_bindings(
        self,
        fragments: Iterable[operation_graph_model.ContributedDestructionFragment],
        operation_graphs: operation_graph.OperationGraphs,
    ):
        # Each contributed destruction fragment belongs to one direct callee
        # binding. The fragment and binding depend on the same Particle Operation,
        # Action Guarantee, or Binding Hole. Index the bindings by those caller-side
        # values, then associate each fragment with the earliest matching binding.
        # Choosing the earliest preserves binding order when one caller-side value
        # satisfies more than one callee Binding Hole.
        callee_binding_indexes: dict[CalleeBinding, int] = {}
        callee_binding_by_local_operation: dict[
            operation_graph_model.PositionOperationNode,
            CalleeBinding,
        ] = {}
        callee_binding_by_guarantee: dict[
            tuple[
                tuple[operation_graph_model.ActionExecution, ...],
                operation_graph_model.PositionOperationNode,
            ],
            CalleeBinding,
        ] = {}
        callee_binding_by_caller_binding_hole: dict[
            operation_graph_model.BindingHole,
            CalleeBinding,
        ] = {}
        for callee_binding_index, callee_binding in enumerate(
            self._bindings_by_callee_binding_hole.values()
        ):
            callee_binding_indexes[callee_binding] = callee_binding_index
            # A callee Binding Hole can bind directly to a caller Particle Operation.
            # A contributed Destroy that follows the same Particle Operation belongs
            # with that callee binding.
            for operation in callee_binding.caller_dependencies.local_operations:
                _ = callee_binding_by_local_operation.setdefault(
                    operation,
                    callee_binding,
                )
            # A callee Binding Hole can instead bind through an Action Guarantee. The
            # sequence of Action Executions and the guaranteed Particle Operation
            # identify the Guarantee that supplied the required particle.
            for guarantee in callee_binding.caller_dependencies.guarantee_dependencies:
                _ = callee_binding_by_guarantee.setdefault(
                    (tuple(guarantee.executions), guarantee.operation),
                    callee_binding,
                )
            # A caller Binding Hole that remains unfilled is passed to the next caller.
            for caller_binding_hole in callee_binding.caller_binding_holes:
                _ = callee_binding_by_caller_binding_hole.setdefault(
                    caller_binding_hole,
                    callee_binding,
                )
        for fragment in fragments:
            dependencies, caller_binding_holes = _partition_caller_dependencies(
                fragment.contribution_dependencies,
                operation_graphs,
            )
            matching_callee_bindings: list[CalleeBinding] = []
            # A contributed Destroy that follows a caller Particle Operation
            # belongs with the callee node resolved to that Particle Operation.
            for operation in dependencies.local_operations:
                callee_binding = callee_binding_by_local_operation.get(operation)
                if callee_binding is not None:
                    matching_callee_bindings.append(callee_binding)
            # A contributed Destroy that follows an Action Guarantee belongs with
            # the callee node resolved through the same sequence of Action
            # Executions and the same guaranteed Particle Operation.
            for guarantee in dependencies.guarantee_dependencies:
                callee_binding = callee_binding_by_guarantee.get(
                    (tuple(guarantee.executions), guarantee.operation)
                )
                if callee_binding is not None:
                    matching_callee_bindings.append(callee_binding)
            # A contributed Destroy whose dependency is passed to the next caller
            # belongs with the callee node that passes the same operation-graph
            # node to that caller.
            for caller_binding_hole in caller_binding_holes:
                callee_binding = callee_binding_by_caller_binding_hole.get(
                    caller_binding_hole
                )
                if callee_binding is not None:
                    matching_callee_bindings.append(callee_binding)
            callee_binding = min(
                matching_callee_bindings, key=callee_binding_indexes.__getitem__
            )
            callee_binding.contributed_destruction_operations.extend(
                fragment.operations
            )


@dataclass(slots=True, eq=False)
class ResolvedActionExecution:
    """The dependency interface of one direct Action Execution."""

    execution: operation_graph_model.ActionExecution
    guarantee_dependency: operation_graph.GuaranteePath | None
    forwards_destruction_connections: bool
    callee_bindings: CalleeBindings

    @classmethod
    def resolve(
        cls,
        caller_graph: operation_graph.OperationGraph,
        operation_graphs: operation_graph.OperationGraphs,
        execution: operation_graph_model.ActionExecution,
        callee: ResolvedAction,
        destruction_fragments: Iterable[
            operation_graph_model.ContributedDestructionFragment
        ],
    ) -> typing.Self:
        """Resolve one direct Action Execution from the caller's perspective."""
        trigger_operation = execution.trigger_operation
        guarantee_dependency = None
        if isinstance(trigger_operation, operation_graph_model.GuaranteeNode):
            guarantee_dependency = operation_graphs.resolve_guarantee(trigger_operation)
        callee_bindings = CalleeBindings.for_action_execution(
            caller_graph,
            execution,
            operation_graphs,
            callee.binding_holes,
            destruction_fragments,
        )
        return cls(
            execution,
            guarantee_dependency,
            caller_graph.propagates_destruction_from_execution_to_caller(execution),
            callee_bindings,
        )


@dataclass(frozen=True, slots=True)
class _ActionExecutionResolution:
    """Action Executions and their relationships within one reusable action."""

    action_executions: list[ResolvedActionExecution]
    dependent_callee_bindings_by_operation: dict[
        operation_graph_model.PositionOperationNode,
        list[CalleeBinding],
    ]
    action_executions_by_operation: dict[
        operation_graph_model.PositionOperationNode,
        list[ResolvedActionExecution],
    ]


@dataclass(frozen=True, slots=True)
class ResolvedAction:
    """The dependency interface of one reusable action.

    ``binding_holes`` places every callee Binding Hole after the holes needed to
    complete its Empty Rule. This order is part of the reusable action's contract
    with each caller.
    """

    graph: operation_graph.OperationGraph
    operations: dict[
        operation_graph_model.PositionOperationNode, ResolvedActionOperation
    ]
    binding_holes: list[operation_graph_model.BindingHole]
    action_executions: list[ResolvedActionExecution]
    destruction_contributions: dict[
        operation_graph_model.DestructionDependency,
        operation_graph_model.DestructionContribution,
    ]


@typing.final
class _ActionResolver:
    """Build the dependency interface of one reusable action."""

    def __init__(
        self,
        graph: operation_graph.OperationGraph,
        operation_graphs: operation_graph.OperationGraphs,
        resolved_callees: Mapping[ast.GlobalTypedName, ResolvedAction],
    ):
        """Initialize resolution with one graph and its resolved direct callees."""
        self._graph = graph
        self._operation_graphs = operation_graphs
        self._resolved_callees = resolved_callees

    def resolve(self) -> ResolvedAction:
        """Resolve the action's operations and direct Action Executions."""
        action_execution_resolution = self._resolve_action_executions()
        operations = self._resolve_operations(action_execution_resolution)
        return ResolvedAction(
            graph=self._graph,
            operations=operations,
            binding_holes=self._collect_binding_holes(
                operations,
                action_execution_resolution,
            ),
            action_executions=action_execution_resolution.action_executions,
            destruction_contributions=self._operation_graphs.destruction_contributions(
                self._graph
            ),
        )

    @staticmethod
    def _collect_binding_holes(
        operations: dict[
            operation_graph_model.PositionOperationNode, ResolvedActionOperation
        ],
        action_execution_resolution: _ActionExecutionResolution,
    ) -> list[operation_graph_model.BindingHole]:
        binding_holes: dict[operation_graph_model.BindingHole, None] = {}
        for resolved_operation in operations.values():
            for binding_hole in resolved_operation.binding_holes_depended_on:
                binding_holes[binding_hole] = None
        for resolved_execution in action_execution_resolution.action_executions:
            for callee_binding in resolved_execution.callee_bindings.values():
                for caller_binding_hole in callee_binding.caller_binding_holes:
                    binding_holes[caller_binding_hole] = None
            # The destructor might not act on an implied position, so resolving its
            # callee bindings does not necessarily discover this dependency.
            destructor_trigger_requirement = (
                resolved_execution.execution.destructor_trigger_requirement
            )
            if destructor_trigger_requirement is not None:
                binding_holes[destructor_trigger_requirement] = None
        return _callee_binding_holes_in_binding_order(binding_holes)

    def _resolve_operations(
        self,
        action_execution_resolution: _ActionExecutionResolution,
    ) -> dict[operation_graph_model.PositionOperationNode, ResolvedActionOperation]:
        operations: dict[
            operation_graph_model.PositionOperationNode, ResolvedActionOperation
        ] = {}
        for operation in self._graph.nodes:
            if not isinstance(operation, operation_graph_model.PositionOperationNode):
                continue
            (
                dependencies,
                binding_holes,
                destruction_dependencies,
            ) = self._resolve_dependencies(
                operation.depends_on,
            )
            dependent_callee_bindings = (
                action_execution_resolution.dependent_callee_bindings_by_operation.get(
                    operation
                )
            )
            if dependent_callee_bindings is None:
                dependent_callee_bindings = []
            action_executions = (
                action_execution_resolution.action_executions_by_operation.get(
                    operation
                )
            )
            if action_executions is None:
                action_executions = []
            if isinstance(operation, operation_graph_model.DestructionFactDestroyNode):
                operations[operation] = ResolvedDestructionOperation(
                    operation=operation,
                    dependencies=dependencies,
                    binding_holes_depended_on=binding_holes,
                    dependent_callee_bindings=dependent_callee_bindings,
                    action_executions=action_executions,
                    destruction_dependencies=destruction_dependencies,
                )
            else:
                operations[operation] = ResolvedActionOperation(
                    operation,
                    dependencies,
                    binding_holes,
                    dependent_callee_bindings,
                    action_executions,
                )
        return operations

    def _resolve_action_executions(self) -> _ActionExecutionResolution:
        action_executions: list[ResolvedActionExecution] = []
        dependent_callee_bindings_by_operation: dict[
            operation_graph_model.PositionOperationNode,
            list[CalleeBinding],
        ] = {}
        action_executions_by_operation: dict[
            operation_graph_model.PositionOperationNode,
            list[ResolvedActionExecution],
        ] = {}
        for execution in self._graph.executions:
            callee = self._resolved_callees[execution.callee_action_name]
            destruction_fragments = self._graph.contributed_destruction_fragments_for(
                execution
            )
            resolved_execution = ResolvedActionExecution.resolve(
                self._graph,
                self._operation_graphs,
                execution,
                callee,
                destruction_fragments,
            )
            action_executions.append(resolved_execution)
            for callee_binding in resolved_execution.callee_bindings.values():
                for operation in callee_binding.caller_dependencies.local_operations:
                    dependent_callee_bindings_by_operation.setdefault(
                        operation, []
                    ).append(callee_binding)
            trigger_operation = execution.trigger_operation
            if isinstance(
                trigger_operation,
                operation_graph_model.PositionOperationNode,
            ):
                action_executions_by_operation.setdefault(trigger_operation, []).append(
                    resolved_execution
                )
        return _ActionExecutionResolution(
            action_executions,
            dependent_callee_bindings_by_operation,
            action_executions_by_operation,
        )

    def _resolve_dependencies(
        self,
        dependency_nodes: Iterable[operation_graph_model.OperationNode],
    ) -> tuple[
        ActionDependencies,
        list[operation_graph_model.BindingHole],
        list[operation_graph_model.DestructionDependency],
    ]:
        dependencies = ActionDependencies([], [])
        binding_holes: list[operation_graph_model.BindingHole] = []
        destruction_dependencies: list[operation_graph_model.DestructionDependency] = []
        for dependency in dependency_nodes:
            if isinstance(
                dependency, operation_graph_model.DestructionContributionNode
            ):
                destruction_dependencies.append(
                    self._operation_graphs.resolve_destruction_dependency(dependency)
                )
                continue
            _append_action_dependency(
                dependency,
                dependencies,
                binding_holes,
                self._operation_graphs,
            )
        return (
            dependencies,
            binding_holes,
            destruction_dependencies,
        )


@typing.final
class ResolvedActions:
    """Resolve and retain reusable action dependency interfaces."""

    # TODO: For parallel codegen, coordinate each action with a single-assignment
    # future. The first thread to claim an action resolves it; other threads wait
    # for the same result or exception.

    def __init__(self, operation_graphs: operation_graph.OperationGraphs):
        """Initialize with the validated operation graphs."""
        self._operation_graphs = operation_graphs
        self._resolved: typed_name_dict.TypedNameDict[
            ast.GlobalTypedName, ResolvedAction
        ] = typed_name_dict.TypedNameDict()

    def resolve(self, action: ast.GlobalTypedName) -> ResolvedAction:
        """Resolve an action whose direct callees have already been resolved."""
        resolved = self._resolved.get(action)
        if resolved is not None:
            return resolved
        resolved = _ActionResolver(
            self._operation_graphs[action],
            self._operation_graphs,
            self._resolved,
        ).resolve()
        self._resolved[action] = resolved
        return resolved

    def __getitem__(self, action: ast.GlobalTypedName) -> ResolvedAction:
        """Return a resolved action."""
        return self._resolved[action]
