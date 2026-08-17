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
    caller_inputs: list[operation_graph_model.AbstractDependencyOrOperationNode]
    triggered_inputs: list[CalleeBinding]
    action_executions: list[ResolvedActionExecution]


@dataclass(frozen=True, slots=True, eq=False)
class ResolvedDestructionOperation(ResolvedActionOperation):
    """One Destruction Fact Destroy and its caller-contribution relationships."""

    operation: operation_graph_model.DestructionFactDestroyNode
    destruction_dependencies: list[operation_graph_model.DestructionDependency]


def _append_action_dependency(
    node: operation_graph_model.OperationNode,
    dependencies: ActionDependencies,
    caller_inputs: list[operation_graph_model.AbstractDependencyOrOperationNode],
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
            caller_inputs.append(node)
        case operation_graph_model.GuaranteeNode():
            dependencies.guarantee_dependencies.append(
                operation_graphs.resolve_guarantee(node)
            )
        case _:
            raise TypeError(f"unknown operation node type: {type(node).__name__}")


def _partition_caller_dependencies(
    nodes: Iterable[operation_graph_model.OperationNode],
    operation_graphs: operation_graph.OperationGraphs,
) -> tuple[
    ActionDependencies, list[operation_graph_model.AbstractDependencyOrOperationNode]
]:
    """Separate local Particle Operations and guarantees from caller inputs."""
    dependencies = ActionDependencies([], [])
    caller_inputs: list[operation_graph_model.AbstractDependencyOrOperationNode] = []
    for node in nodes:
        _append_action_dependency(node, dependencies, caller_inputs, operation_graphs)
    return dependencies, caller_inputs


@dataclass(slots=True, eq=False)
class CalleeBinding:
    """One callee-to-caller binding across a direct Action Execution."""

    callee_input: operation_graph_model.AbstractDependencyOrOperationNode
    caller_dependencies: ActionDependencies
    caller_input_dependencies: list[
        operation_graph_model.AbstractDependencyOrOperationNode
    ]
    contributed_destruction_operations: list[
        operation_graph_model.DestructionFragmentDestroyNode
    ] = field(default_factory=list)

    @classmethod
    def resolve(
        cls,
        caller_graph: operation_graph.OperationGraph,
        execution: operation_graph_model.ActionExecution,
        operation_graphs: operation_graph.OperationGraphs,
        callee_input: operation_graph_model.AbstractDependencyOrOperationNode,
        callee_node_bindings_needed_for_empty_rule_completion: list[CalleeBinding],
    ) -> typing.Self:
        """Resolve one callee input from the direct caller's perspective."""
        match callee_input:
            case operation_graph_model.CallerMoveRuleFillDependencyNode(
                caller_move_rule_fill_dependency=caller_dependency
            ):
                return cls._resolve_caller_move_rule_fill_dependency(
                    execution,
                    operation_graphs,
                    callee_input,
                    caller_dependency,
                )
            case (
                operation_graph_model.CallerMoveRuleFillDependency() as caller_dependency
            ):
                return cls._resolve_caller_move_rule_fill_dependency(
                    execution,
                    operation_graphs,
                    callee_input,
                    caller_dependency,
                )
            case operation_graph_model.CallerEmptyRuleDependenciesNode(
                caller_empty_rule_dependencies=caller_dependencies
            ):
                return cls._resolve_caller_empty_rule_dependencies(
                    execution,
                    caller_graph,
                    operation_graphs,
                    callee_input,
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
                    callee_input,
                    caller_dependencies,
                    callee_node_bindings_needed_for_empty_rule_completion,
                )
            case (
                operation_graph_model.ActionParentLastOperationNode()
                | operation_graph_model.RequirementNode()
            ):
                return cls._resolve_caller_input_node(
                    execution,
                    operation_graphs,
                    callee_input,
                )
        typing.assert_never(callee_input)

    @classmethod
    def _resolve_caller_move_rule_fill_dependency(
        cls,
        execution: operation_graph_model.ActionExecution,
        operation_graphs: operation_graph.OperationGraphs,
        callee_input: (
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
        caller_inputs: list[
            operation_graph_model.AbstractDependencyOrOperationNode
        ] = []
        if isinstance(substitution, operation_graph_model.CallerMoveRuleFillDependency):
            caller_inputs.append(substitution)
        elif substitution is not None:
            _append_action_dependency(
                substitution,
                dependencies,
                caller_inputs,
                operation_graphs,
            )
        return cls(callee_input, dependencies, caller_inputs)

    @classmethod
    def _resolve_caller_empty_rule_dependencies(
        cls,
        execution: operation_graph_model.ActionExecution,
        caller_graph: operation_graph.OperationGraph,
        operation_graphs: operation_graph.OperationGraphs,
        callee_input: (
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
                node_binding.caller_input_dependencies,
            )
        substitution = caller_graph.apply_callee_empty_rule_in_caller(
            execution,
            caller_dependencies,
            direct_caller_state_for_empty_rule,
        )
        dependencies, caller_inputs = _partition_caller_dependencies(
            substitution.caller_nodes,
            operation_graphs,
        )
        if substitution.caller_empty_rule_dependencies is not None:
            caller_inputs.append(substitution.caller_empty_rule_dependencies)
        return cls(callee_input, dependencies, caller_inputs)

    @classmethod
    def _resolve_caller_input_node(
        cls,
        execution: operation_graph_model.ActionExecution,
        operation_graphs: operation_graph.OperationGraphs,
        callee_input: _RequirementOrActionParentNode,
    ) -> typing.Self:
        """Resolve one Action Parent or requirement input from the caller's perspective."""
        dependencies, caller_inputs = _partition_caller_dependencies(
            (execution.caller_dependency_for_input(callee_input),),
            operation_graphs,
        )
        return cls(callee_input, dependencies, caller_inputs)


def callee_nodes_needed_for_empty_rule_completion(
    callee_node: operation_graph_model.AbstractDependencyOrOperationNode,
) -> tuple[operation_graph_model.AbstractDependencyOrOperationNode, ...]:
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


def _callee_nodes_in_binding_order(
    callee_nodes: Iterable[operation_graph_model.AbstractDependencyOrOperationNode],
) -> list[operation_graph_model.AbstractDependencyOrOperationNode]:
    """Order callee nodes so an Empty Rule completion follows its required bindings.

    CallerEmptyRuleDependencies names the other callee nodes whose bindings must
    be substituted into its Empty Rule. Those nodes must therefore be resolved
    first. ResolvedAction.caller_inputs stores this order so every caller uses
    it when resolving an Action Execution of the action.
    """
    ordered_nodes: list[operation_graph_model.AbstractDependencyOrOperationNode] = []
    ordered_node_set: set[operation_graph_model.AbstractDependencyOrOperationNode] = (
        set()
    )
    for callee_node in callee_nodes:
        nodes_to_order = [(callee_node, False)]
        while nodes_to_order:
            node_to_order, required_nodes_are_ordered = nodes_to_order.pop()
            if node_to_order in ordered_node_set:
                continue
            if required_nodes_are_ordered:
                ordered_nodes.append(node_to_order)
                ordered_node_set.add(node_to_order)
                continue
            nodes_to_order.append((node_to_order, True))
            for required_node in reversed(
                callee_nodes_needed_for_empty_rule_completion(node_to_order)
            ):
                nodes_to_order.append((required_node, False))
    return ordered_nodes


@typing.final
class CalleeBindings:
    """The ordered callee-to-caller bindings of one Action Execution."""

    def __init__(
        self,
        direct_inputs: dict[
            operation_graph_model.AbstractDependencyOrOperationNode, CalleeBinding
        ],
    ):
        """Initialize with the Action Execution's direct callee inputs."""
        self._direct_inputs = direct_inputs

    @classmethod
    def resolve(
        cls,
        caller_graph: operation_graph.OperationGraph,
        execution: operation_graph_model.ActionExecution,
        operation_graphs: operation_graph.OperationGraphs,
        callee_inputs: list[operation_graph_model.AbstractDependencyOrOperationNode],
        destruction_fragments: Iterable[
            operation_graph_model.ContributedDestructionFragment
        ],
    ) -> typing.Self:
        """Resolve the inputs and their caller-contributed destruction fragments.

        ``callee_inputs`` must be ordered such that every callee node involved in
        an empty rule completion comes after the callee nodes needed to complete
        its Empty Rule.
        """
        direct_inputs: dict[
            operation_graph_model.AbstractDependencyOrOperationNode, CalleeBinding
        ] = {}
        for callee_input in callee_inputs:
            callee_node_bindings_needed_for_empty_rule_completion: list[
                CalleeBinding
            ] = []
            for callee_node in callee_nodes_needed_for_empty_rule_completion(
                callee_input
            ):
                callee_node_bindings_needed_for_empty_rule_completion.append(
                    direct_inputs[callee_node]
                )
            direct_inputs[callee_input] = CalleeBinding.resolve(
                caller_graph,
                execution,
                operation_graphs,
                callee_input,
                callee_node_bindings_needed_for_empty_rule_completion,
            )
        inputs = cls(direct_inputs)
        inputs._set_contributed_destruction_operations_on_callee_nodes(
            destruction_fragments,
            operation_graphs,
        )
        return inputs

    def values(self) -> Iterable[CalleeBinding]:
        """Return the direct callee inputs in their established order."""
        return self._direct_inputs.values()

    def __getitem__(
        self, callee_input: operation_graph_model.AbstractDependencyOrOperationNode
    ) -> CalleeBinding:
        """Return one direct resolved callee input."""
        return self._direct_inputs[callee_input]

    def get(
        self, callee_input: operation_graph_model.AbstractDependencyOrOperationNode
    ) -> CalleeBinding | None:
        """Return one direct resolved callee input, if present."""
        return self._direct_inputs.get(callee_input)

    def _set_contributed_destruction_operations_on_callee_nodes(
        self,
        fragments: Iterable[operation_graph_model.ContributedDestructionFragment],
        operation_graphs: operation_graph.OperationGraphs,
    ):
        # Each contributed destruction fragment belongs to one direct callee node.
        # The fragment and callee node depend on the same Particle Operation,
        # Action Guarantee, or propagated operation-graph node. Index the direct
        # callee nodes by those resolved dependencies, then associate each fragment
        # with the earliest matching callee node. Choosing the earliest preserves
        # callee-node order when one dependency satisfies more than one callee node.
        input_indexes: dict[CalleeBinding, int] = {}
        inputs_by_local_operation: dict[
            operation_graph_model.PositionOperationNode,
            CalleeBinding,
        ] = {}
        inputs_by_guarantee: dict[
            tuple[
                tuple[operation_graph_model.ActionExecution, ...],
                operation_graph_model.PositionOperationNode,
            ],
            CalleeBinding,
        ] = {}
        inputs_by_caller_input: dict[
            operation_graph_model.AbstractDependencyOrOperationNode,
            CalleeBinding,
        ] = {}
        for input_index, resolved_input in enumerate(self._direct_inputs.values()):
            input_indexes[resolved_input] = input_index
            # A caller input can resolve directly to a caller Particle Operation.
            # A contributed Destroy that follows the same Particle Operation belongs
            # with that callee node.
            for operation in resolved_input.caller_dependencies.local_operations:
                _ = inputs_by_local_operation.setdefault(
                    operation,
                    resolved_input,
                )
            # A callee node can instead resolve through an Action Guarantee. The
            # sequence of Action Executions and the guaranteed Particle Operation
            # identify the Guarantee that supplied the required particle.
            for guarantee in resolved_input.caller_dependencies.guarantee_dependencies:
                _ = inputs_by_guarantee.setdefault(
                    (tuple(guarantee.executions), guarantee.operation),
                    resolved_input,
                )
            # A caller input that the direct caller cannot satisfy is passed to the
            # next caller.
            for caller_input in resolved_input.caller_input_dependencies:
                _ = inputs_by_caller_input.setdefault(
                    caller_input,
                    resolved_input,
                )
        for fragment in fragments:
            dependencies, caller_inputs = _partition_caller_dependencies(
                fragment.contribution_dependencies,
                operation_graphs,
            )
            candidate_inputs: list[CalleeBinding] = []
            # A contributed Destroy that follows a caller Particle Operation
            # belongs with the callee node resolved to that Particle Operation.
            for operation in dependencies.local_operations:
                resolved_input = inputs_by_local_operation.get(operation)
                if resolved_input is not None:
                    candidate_inputs.append(resolved_input)
            # A contributed Destroy that follows an Action Guarantee belongs with
            # the callee node resolved through the same sequence of Action
            # Executions and the same guaranteed Particle Operation.
            for guarantee in dependencies.guarantee_dependencies:
                resolved_input = inputs_by_guarantee.get(
                    (tuple(guarantee.executions), guarantee.operation)
                )
                if resolved_input is not None:
                    candidate_inputs.append(resolved_input)
            # A contributed Destroy whose dependency is passed to the next caller
            # belongs with the callee node that passes the same operation-graph
            # node to that caller.
            for caller_input in caller_inputs:
                resolved_input = inputs_by_caller_input.get(caller_input)
                if resolved_input is not None:
                    candidate_inputs.append(resolved_input)
            callee_node = min(candidate_inputs, key=input_indexes.__getitem__)
            callee_node.contributed_destruction_operations.extend(fragment.operations)


@dataclass(slots=True, eq=False)
class ResolvedActionExecution:
    """The dependency interface of one direct Action Execution."""

    execution: operation_graph_model.ActionExecution
    guarantee_dependency: operation_graph.GuaranteePath | None
    forwards_destruction_connections: bool
    inputs: CalleeBindings

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
        inputs = CalleeBindings.resolve(
            caller_graph,
            execution,
            operation_graphs,
            callee.caller_inputs,
            destruction_fragments,
        )
        return cls(
            execution,
            guarantee_dependency,
            caller_graph.propagates_destruction_from_execution_to_caller(execution),
            inputs,
        )


@dataclass(frozen=True, slots=True)
class _ActionExecutionResolution:
    """Action Executions and their relationships within one reusable action."""

    action_executions: list[ResolvedActionExecution]
    triggered_inputs_by_operation: dict[
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

    ``caller_inputs`` places every callee node after the callee nodes needed to
    complete its Empty Rule. This order is part of the reusable action's
    contract with each caller.
    """

    graph: operation_graph.OperationGraph
    operations: dict[
        operation_graph_model.PositionOperationNode, ResolvedActionOperation
    ]
    caller_inputs: list[operation_graph_model.AbstractDependencyOrOperationNode]
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
            caller_inputs=self._build_caller_inputs(
                operations,
                action_execution_resolution,
            ),
            action_executions=action_execution_resolution.action_executions,
            destruction_contributions=self._operation_graphs.destruction_contributions(
                self._graph
            ),
        )

    @staticmethod
    def _build_caller_inputs(
        operations: dict[
            operation_graph_model.PositionOperationNode, ResolvedActionOperation
        ],
        action_execution_resolution: _ActionExecutionResolution,
    ) -> list[operation_graph_model.AbstractDependencyOrOperationNode]:
        caller_inputs: dict[
            operation_graph_model.AbstractDependencyOrOperationNode, None
        ] = {}
        for resolved_operation in operations.values():
            for caller_input in resolved_operation.caller_inputs:
                caller_inputs[caller_input] = None
        for resolved_execution in action_execution_resolution.action_executions:
            for resolved_input in resolved_execution.inputs.values():
                for caller_input in resolved_input.caller_input_dependencies:
                    caller_inputs[caller_input] = None
            # The destructor might not act on an implied position, so resolving its
            # inputs does not necessarily discover this dependency.
            caller_input_dependency = (
                resolved_execution.execution.caller_input_dependency
            )
            if caller_input_dependency is not None:
                caller_inputs[caller_input_dependency] = None
        return _callee_nodes_in_binding_order(caller_inputs)

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
                caller_inputs,
                destruction_dependencies,
            ) = self._resolve_dependencies(
                operation.depends_on,
            )
            triggered_inputs = (
                action_execution_resolution.triggered_inputs_by_operation.get(operation)
            )
            if triggered_inputs is None:
                triggered_inputs = []
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
                    caller_inputs=caller_inputs,
                    triggered_inputs=triggered_inputs,
                    action_executions=action_executions,
                    destruction_dependencies=destruction_dependencies,
                )
            else:
                operations[operation] = ResolvedActionOperation(
                    operation,
                    dependencies,
                    caller_inputs,
                    triggered_inputs,
                    action_executions,
                )
        return operations

    def _resolve_action_executions(self) -> _ActionExecutionResolution:
        action_executions: list[ResolvedActionExecution] = []
        triggered_inputs_by_operation: dict[
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
            for resolved_input in resolved_execution.inputs.values():
                for operation in resolved_input.caller_dependencies.local_operations:
                    triggered_inputs_by_operation.setdefault(operation, []).append(
                        resolved_input
                    )
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
            triggered_inputs_by_operation,
            action_executions_by_operation,
        )

    def _resolve_dependencies(
        self,
        dependency_nodes: Iterable[operation_graph_model.OperationNode],
    ) -> tuple[
        ActionDependencies,
        list[operation_graph_model.AbstractDependencyOrOperationNode],
        list[operation_graph_model.DestructionDependency],
    ]:
        dependencies = ActionDependencies([], [])
        caller_inputs: list[
            operation_graph_model.AbstractDependencyOrOperationNode
        ] = []
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
                caller_inputs,
                self._operation_graphs,
            )
        return (
            dependencies,
            caller_inputs,
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
