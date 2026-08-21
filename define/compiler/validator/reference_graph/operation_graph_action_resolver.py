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

import collections
import itertools
import typing
from dataclasses import dataclass, field

from define.compiler.data_structures import typed_name_dict
from define.compiler.validator.reference_graph import (
    operation_graph,
    operation_graph_model,
    operation_graph_rules,
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
        Sequence,
    )

    from define.compiler import ast


type _RequirementOrActionParentNode = (
    operation_graph_model.ActionParentLastOperationNode
    | operation_graph_model.RequirementNode
)
type _ActionDependsOnTarget = (
    operation_graph_model.ConcreteOperationNode | operation_graph_model.BindingHole
)
type _OperationDependsOnTarget = (
    _ActionDependsOnTarget | operation_graph_model.DestructionContributionNode
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


@dataclass(slots=True, eq=False)
class _ResolvedOperationRelationships:
    """Relationships retained by a Resolved Action for one Particle Operation.

    This record exists only when the Operation Graph node cannot supply every
    relationship needed by consumers, avoiding duplicate storage for ordinary
    Particle Operations. In the most common case, an Operation Graph node knows
    all of its relationships locally, and so this data structure is not needed.
    Having this be separately stored from the nodes should save us significant
    amounts of memory in large compiles.
    """

    local_operations_depended_on: (
        list[operation_graph_model.PositionOperationNode] | None
    ) = None
    guarantee_dependencies: list[operation_graph.GuaranteePath] | None = None
    binding_holes_depended_on: list[operation_graph_model.BindingHole] | None = None
    callee_bindings_depending_on: list[CalleeBinding] | None = None
    action_executions_triggered: list[ResolvedActionExecution] | None = None
    destruction_dependencies: (
        list[operation_graph_model.ResolvedCalleeDestroy] | None
    ) = None

    def add_callee_binding_depending_on(self, callee_binding: CalleeBinding):
        if self.callee_bindings_depending_on is None:
            self.callee_bindings_depending_on = []
        self.callee_bindings_depending_on.append(callee_binding)

    def add_action_execution_triggered(self, action_execution: ResolvedActionExecution):
        if self.action_executions_triggered is None:
            self.action_executions_triggered = []
        self.action_executions_triggered.append(action_execution)


def _append_action_dependency(
    node: _ActionDependsOnTarget,
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
            | operation_graph_model.EmptyRuleBindingHoleNode()
            | operation_graph_model.EmptyRuleBindingHole()
            | operation_graph_model.MoveRuleBindingHole()
        ):
            binding_holes.append(node)
        case operation_graph_model.GuaranteeNode():
            dependencies.guarantee_dependencies.append(
                operation_graphs.resolve_guarantee(node)
            )


def _partition_caller_dependencies(
    nodes: Iterable[_ActionDependsOnTarget],
    operation_graphs: operation_graph.OperationGraphs,
) -> tuple[ActionDependencies, list[operation_graph_model.BindingHole]]:
    """Separate local Particle Operations and guarantees from Binding Holes."""
    dependencies = ActionDependencies([], [])
    binding_holes: list[operation_graph_model.BindingHole] = []
    for node in nodes:
        _append_action_dependency(node, dependencies, binding_holes, operation_graphs)
    return dependencies, binding_holes


def _resolve_empty_rule_binding_hole(
    node: operation_graph_model.EmptyRuleBindingHoleNode,
    replacement_depends_on_targets_by_node: Mapping[
        operation_graph_model.OperationNode,
        Sequence[_ActionDependsOnTarget],
    ],
) -> operation_graph_model.EmptyRuleBindingHole:
    """Resolve an Operation Graph Empty Rule Binding Hole."""
    prerequisite_binding_holes = operation_graph_rules.binding_holes_depended_on_by(
        node.remaining_concrete_nodes,
        replacement_depends_on_targets_by_node=replacement_depends_on_targets_by_node,
    )
    return operation_graph_model.EmptyRuleBindingHole.from_collection(
        node.empty_rule_binding_hole,
        prerequisite_binding_holes,
    )


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
        execution: operation_graph_model.ActionExecution,
        operation_graphs: operation_graph.OperationGraphs,
        callee_binding_hole: operation_graph_model.BindingHole,
        prerequisite_callee_bindings: list[CalleeBinding],
        *,
        replacement_depends_on_targets_by_node: Mapping[
            operation_graph_model.OperationNode,
            Sequence[_ActionDependsOnTarget],
        ],
    ) -> typing.Self:
        """Bind one callee Binding Hole from the direct caller's perspective."""
        match callee_binding_hole:
            case operation_graph_model.MoveRuleBindingHole() as move_rule_binding_hole:
                return cls._for_move_rule_binding_hole(
                    execution,
                    operation_graphs,
                    move_rule_binding_hole,
                    prerequisite_callee_bindings,
                    replacement_depends_on_targets_by_node,
                )
            case operation_graph_model.EmptyRuleBindingHoleNode(
                empty_rule_binding_hole=empty_rule_binding_hole
            ):
                return cls._for_empty_rule_binding_hole(
                    execution,
                    operation_graphs,
                    callee_binding_hole,
                    empty_rule_binding_hole,
                    prerequisite_callee_bindings,
                    replacement_depends_on_targets_by_node,
                )
            case (
                operation_graph_model.EmptyRuleBindingHole() as empty_rule_binding_hole
            ):
                return cls._for_empty_rule_binding_hole(
                    execution,
                    operation_graphs,
                    callee_binding_hole,
                    empty_rule_binding_hole,
                    prerequisite_callee_bindings,
                    replacement_depends_on_targets_by_node,
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
    def _for_move_rule_binding_hole(
        cls,
        execution: operation_graph_model.ActionExecution,
        operation_graphs: operation_graph.OperationGraphs,
        move_rule_binding_hole: operation_graph_model.MoveRuleBindingHole,
        prerequisite_callee_bindings: list[CalleeBinding],
        replacement_depends_on_targets_by_node: Mapping[
            operation_graph_model.OperationNode,
            Sequence[_ActionDependsOnTarget],
        ],
    ) -> typing.Self:
        """Bind one Move Rule Binding Hole from the caller's perspective."""
        empty_rule_binding_inputs = operation_graph_model.EmptyRuleBindingInputs()
        for prerequisite_callee_binding in prerequisite_callee_bindings:
            empty_rule_binding_inputs.add_inputs(
                prerequisite_callee_binding.caller_dependencies.concrete_nodes(),
                prerequisite_callee_binding.caller_binding_holes,
            )
        move_rule_application_result = (
            operation_graph_rules.apply_move_rule_binding_hole_in_caller(
                execution,
                move_rule_binding_hole,
                empty_rule_binding_inputs,
                replacement_depends_on_targets_by_node=(
                    replacement_depends_on_targets_by_node
                ),
            )
        )
        dependencies, caller_binding_holes = _partition_caller_dependencies(
            move_rule_application_result.concrete_caller_nodes,
            operation_graphs,
        )
        if move_rule_application_result.move_rule_binding_hole is not None:
            caller_binding_holes.append(
                move_rule_application_result.move_rule_binding_hole
            )
        return cls(move_rule_binding_hole, dependencies, caller_binding_holes)

    @classmethod
    def _for_empty_rule_binding_hole(
        cls,
        execution: operation_graph_model.ActionExecution,
        operation_graphs: operation_graph.OperationGraphs,
        callee_binding_hole: (
            operation_graph_model.EmptyRuleBindingHoleNode
            | operation_graph_model.EmptyRuleBindingHole
        ),
        empty_rule_binding_hole: operation_graph_model.EmptyRuleBindingHole,
        prerequisite_callee_bindings: list[CalleeBinding],
        replacement_depends_on_targets_by_node: Mapping[
            operation_graph_model.OperationNode,
            Sequence[_ActionDependsOnTarget],
        ],
    ) -> typing.Self:
        """Bind one Empty Rule Binding Hole from the caller's perspective."""
        empty_rule_binding_inputs = operation_graph_model.EmptyRuleBindingInputs()
        for prerequisite_callee_binding in prerequisite_callee_bindings:
            empty_rule_binding_inputs.add_inputs(
                prerequisite_callee_binding.caller_dependencies.concrete_nodes(),
                prerequisite_callee_binding.caller_binding_holes,
            )
        empty_rule_application_result = (
            operation_graph_rules.apply_empty_rule_binding_hole_in_caller(
                execution,
                empty_rule_binding_hole,
                empty_rule_binding_inputs,
                replacement_depends_on_targets_by_node=(
                    replacement_depends_on_targets_by_node
                ),
            )
        )
        dependencies, caller_binding_holes = _partition_caller_dependencies(
            empty_rule_application_result.caller_nodes,
            operation_graphs,
        )
        if empty_rule_application_result.empty_rule_binding_hole is not None:
            caller_binding_holes.append(
                empty_rule_application_result.empty_rule_binding_hole
            )
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


def prerequisite_binding_holes(
    binding_hole: operation_graph_model.BindingHole,
) -> tuple[operation_graph_model.BindingHole, ...]:
    """Return the Binding Holes that must be bound before this one."""
    match binding_hole:
        case operation_graph_model.EmptyRuleBindingHoleNode(
            empty_rule_binding_hole=empty_rule_binding_hole
        ):
            return empty_rule_binding_hole.prerequisite_binding_holes
        case operation_graph_model.EmptyRuleBindingHole() as empty_rule_binding_hole:
            return empty_rule_binding_hole.prerequisite_binding_holes
        case operation_graph_model.MoveRuleBindingHole() as move_rule_binding_hole:
            return move_rule_binding_hole.prerequisite_binding_holes
        case _:
            return ()


# TODO: Consider maintaining prerequisite-first Binding Hole order as holes are
# discovered. This could remove the final ordering pass, but only if simplifying
# this code justifies requiring every discovery path to update shared ordering
# state.
def _callee_binding_holes_in_binding_order(
    callee_binding_holes: Iterable[operation_graph_model.BindingHole],
) -> list[operation_graph_model.BindingHole]:
    """Order callee Binding Holes so Empty Rule prerequisites come first.

    An EmptyRuleBindingHole names the other callee Binding Holes that must be
    bound first. ActionBindingHoles.in_binding_order stores this order so every
    caller uses it when resolving an Action Execution of the action.
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
                prerequisite_binding_holes(binding_hole_to_order)
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
        with_runtime_consumers: list[CalleeBinding],
    ):
        """Initialize with the Action Execution's completed callee bindings."""
        self._bindings_by_callee_binding_hole = bindings_by_callee_binding_hole
        self._with_runtime_consumers = with_runtime_consumers

    @classmethod
    def for_action_execution(
        cls,
        caller_graph: operation_graph.OperationGraph,
        execution: operation_graph_model.ActionExecution,
        operation_graphs: operation_graph.OperationGraphs,
        callee_action_binding_holes: ActionBindingHoles,
        replacement_depends_on_targets_by_node: Mapping[
            operation_graph_model.OperationNode,
            Sequence[_ActionDependsOnTarget],
        ],
    ) -> typing.Self:
        """Create the bindings and associate caller-contributed destruction fragments."""
        bindings_by_callee_binding_hole: dict[
            operation_graph_model.BindingHole, CalleeBinding
        ] = {}
        # TODO: Investigate reusing Binding Hole dependency traversal results while binding
        # one Action Execution. The replacement relationships do not change during
        # this loop, so separate callee Binding Holes can repeat the same traversal.
        for callee_binding_hole in callee_action_binding_holes.in_binding_order:
            prerequisite_callee_bindings: list[CalleeBinding] = []
            for prerequisite_binding_hole in prerequisite_binding_holes(
                callee_binding_hole
            ):
                prerequisite_callee_bindings.append(
                    bindings_by_callee_binding_hole[prerequisite_binding_hole]
                )
            bindings_by_callee_binding_hole[callee_binding_hole] = (
                CalleeBinding.for_callee_binding_hole(
                    execution,
                    operation_graphs,
                    callee_binding_hole,
                    prerequisite_callee_bindings,
                    replacement_depends_on_targets_by_node=(
                        replacement_depends_on_targets_by_node
                    ),
                )
            )
        cls._associate_contributed_destruction_operations(
            bindings_by_callee_binding_hole,
            caller_graph.contributed_destruction_fragments_for(execution),
            operation_graphs,
        )
        return cls(
            bindings_by_callee_binding_hole,
            cls._bindings_with_runtime_consumers(
                bindings_by_callee_binding_hole,
                callee_action_binding_holes,
            ),
        )

    @property
    def with_runtime_consumers(self) -> list[CalleeBinding]:
        """Bindings consumed by the callee or a contributed Destroy, in order."""
        return self._with_runtime_consumers

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

    # A contributed Destroy can consume a binding otherwise used only as a
    # prerequisite, and that association is known only after every binding is
    # built. Select the runtime-consumed bindings after destruction association.
    @staticmethod
    def _bindings_with_runtime_consumers(
        bindings_by_callee_binding_hole: dict[
            operation_graph_model.BindingHole, CalleeBinding
        ],
        callee_action_binding_holes: ActionBindingHoles,
    ) -> list[CalleeBinding]:
        """Return bindings consumed by the callee or a contributed Destroy.

        ``callee_action_binding_holes.with_runtime_consumers`` must contain the
        same Binding Hole objects in the same relative order as
        ``bindings_by_callee_binding_hole``.
        """
        bindings_with_runtime_consumers: list[CalleeBinding] = []
        runtime_consumer_index = 0
        binding_holes_with_runtime_consumers = (
            callee_action_binding_holes.with_runtime_consumers
        )
        for callee_binding in bindings_by_callee_binding_hole.values():
            has_runtime_consumer = (
                runtime_consumer_index < len(binding_holes_with_runtime_consumers)
                and callee_binding.callee_binding_hole
                is binding_holes_with_runtime_consumers[runtime_consumer_index]
            )
            if has_runtime_consumer:
                runtime_consumer_index += 1
            if (
                has_runtime_consumer
                or callee_binding.contributed_destruction_operations
            ):
                bindings_with_runtime_consumers.append(callee_binding)
        return bindings_with_runtime_consumers

    @staticmethod
    def _associate_contributed_destruction_operations(
        bindings_by_callee_binding_hole: dict[
            operation_graph_model.BindingHole, CalleeBinding
        ],
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
            bindings_by_callee_binding_hole.values()
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
            if not fragment.operations:
                continue
            contribution_dependencies = itertools.chain.from_iterable(
                contributed_destruction.contribution_node.depends_on
                for contributed_destruction in fragment.contributed_destructions
            )
            dependencies, caller_binding_holes = _partition_caller_dependencies(
                contribution_dependencies,
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
        replacement_depends_on_targets_by_node: Mapping[
            operation_graph_model.OperationNode,
            Sequence[_ActionDependsOnTarget],
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
            replacement_depends_on_targets_by_node,
        )
        return cls(
            execution,
            guarantee_dependency,
            caller_graph.propagates_destruction_from_execution_to_caller(execution),
            callee_bindings,
        )


@dataclass(frozen=True, slots=True)
class ResolvedDestructionContribution:
    """Caller-contributed work with its resolved Destructor executions."""

    operation_graph_contribution: operation_graph_model.DestructionContribution
    destructors: list[ResolvedActionExecution]


@dataclass(frozen=True, slots=True)
class ActionBindingHoles:
    """One action's Binding Holes in prerequisite-first order.

    ``with_runtime_consumers`` preserves ``in_binding_order`` while excluding
    holes used only during cross-action resolution.
    """

    in_binding_order: list[operation_graph_model.BindingHole]
    with_runtime_consumers: list[operation_graph_model.BindingHole]
    _binding_holes_by_guaranteed_position: dict[
        tuple[str, ...], tuple[operation_graph_model.BindingHole, ...]
    ]

    def binding_holes_depended_on_by_guaranteed_position(
        self, guaranteed_position: tuple[str, ...]
    ) -> tuple[operation_graph_model.BindingHole, ...]:
        """Return the Binding Holes depended on by an Action Guarantee."""
        binding_holes = self._binding_holes_by_guaranteed_position.get(
            guaranteed_position
        )
        if binding_holes is None:
            return ()
        return binding_holes


@dataclass(frozen=True, slots=True)
class ResolvedAction:
    """The dependency interface of one reusable action."""

    graph: operation_graph.OperationGraph
    relationships_by_operation: dict[
        operation_graph_model.PositionOperationNode,
        _ResolvedOperationRelationships,
    ]
    binding_holes: ActionBindingHoles
    action_executions: list[ResolvedActionExecution]
    destruction_contributions: dict[
        operation_graph_model.ResolvedCalleeDestroy,
        ResolvedDestructionContribution,
    ]
    resolved_execution_by_execution: dict[
        operation_graph_model.ActionExecution, ResolvedActionExecution
    ] = field(repr=False)
    replacement_depends_on_targets_by_node: dict[
        operation_graph_model.OperationNode, Sequence[_ActionDependsOnTarget]
    ] = field(repr=False)

    def local_operations_depended_on_by(
        self,
        operation: operation_graph_model.PositionOperationNode,
    ) -> Sequence[operation_graph_model.PositionOperationNode]:
        """Return the local Particle Operations on which an operation depends."""
        relationships = self.relationships_by_operation.get(operation)
        if (
            relationships is not None
            and relationships.local_operations_depended_on is not None
        ):
            return relationships.local_operations_depended_on
        # If local relationships were not stored, every direct dependency is
        # already a local Particle Operation in the Operation Graph.
        return typing.cast(
            "Sequence[operation_graph_model.PositionOperationNode]",
            operation.depends_on,
        )

    def guarantee_dependencies_for(
        self,
        operation: operation_graph_model.PositionOperationNode,
    ) -> Sequence[operation_graph.GuaranteePath]:
        """Return one Particle Operation's Guarantee Dependencies."""
        relationships = self.relationships_by_operation.get(operation)
        if relationships is None or relationships.guarantee_dependencies is None:
            return ()
        return relationships.guarantee_dependencies

    def binding_holes_depended_on_by(
        self,
        operation: operation_graph_model.PositionOperationNode,
    ) -> Sequence[operation_graph_model.BindingHole]:
        """Return the Binding Holes on which one Particle Operation depends."""
        relationships = self.relationships_by_operation.get(operation)
        if relationships is None or relationships.binding_holes_depended_on is None:
            return ()
        return relationships.binding_holes_depended_on

    def callee_bindings_depending_on(
        self,
        operation: operation_graph_model.PositionOperationNode,
    ) -> Sequence[CalleeBinding]:
        """Return the Callee Bindings that depend on one Particle Operation."""
        relationships = self.relationships_by_operation.get(operation)
        if relationships is None or relationships.callee_bindings_depending_on is None:
            return ()
        return relationships.callee_bindings_depending_on

    def action_executions_triggered_by(
        self,
        operation: operation_graph_model.PositionOperationNode,
    ) -> Sequence[ResolvedActionExecution]:
        """Return the Action Executions triggered by one Particle Operation."""
        relationships = self.relationships_by_operation.get(operation)
        if relationships is None or relationships.action_executions_triggered is None:
            return ()
        return relationships.action_executions_triggered

    def destruction_dependencies_for(
        self,
        operation: operation_graph_model.DestructionFactDestroyNode,
    ) -> Sequence[operation_graph_model.ResolvedCalleeDestroy]:
        """Return the Destruction Dependencies of one Destruction Fact Destroy."""
        relationships = self.relationships_by_operation.get(operation)
        if relationships is None or relationships.destruction_dependencies is None:
            return ()
        return relationships.destruction_dependencies


@typing.final
class _ActionBindingHolesBuilder:
    """Build one action's complete Binding Hole interface."""

    def __init__(
        self,
        graph: operation_graph.OperationGraph,
        operation_graphs: operation_graph.OperationGraphs,
        resolved_callees: Mapping[ast.GlobalTypedName, ResolvedAction],
    ):
        self._graph = graph
        self._operation_graphs = operation_graphs
        self._resolved_callees = resolved_callees

    def replacement_depends_on_targets_for_guarantee(
        self,
        guarantee: operation_graph_model.GuaranteeNode,
        resolved_execution: ResolvedActionExecution,
        replacement_depends_on_targets_by_node: Mapping[
            operation_graph_model.OperationNode,
            Sequence[_ActionDependsOnTarget],
        ],
    ) -> Sequence[_ActionDependsOnTarget]:
        """Return the Guarantee Node's relationships from the caller's perspective."""
        guarantee_path = self._operation_graphs.resolve_guarantee(guarantee)
        # Only the action that publishes the Action Guarantee records its Binding
        # Holes. Having every caller also record them would materialize every
        # possible Action Execution chain.
        terminal_action = self._resolved_callees[
            guarantee_path.executions[-1].callee_action_name
        ]
        callee_binding_holes = terminal_action.binding_holes.binding_holes_depended_on_by_guaranteed_position(
            guarantee.guaranteed_position
        )
        if not callee_binding_holes:
            return ()
        # A Binding Hole can be translated only from a direct callee's perspective
        # to its direct caller's perspective, so resolution must proceed backward
        # from the publishing action.
        for execution_index in range(len(guarantee_path.executions) - 1, -1, -1):
            execution = guarantee_path.executions[execution_index]
            if execution_index == 0:
                # This action's replacements are still being built. Every other
                # action on the path completed resolution before its callers.
                caller_resolved_execution = resolved_execution
                caller_replacements = replacement_depends_on_targets_by_node
            else:
                caller_action = self._resolved_callees[
                    guarantee_path.executions[execution_index - 1].callee_action_name
                ]
                caller_resolved_execution = (
                    caller_action.resolved_execution_by_execution[execution]
                )
                caller_replacements = (
                    caller_action.replacement_depends_on_targets_by_node
                )
            replacement_depends_on_targets = (
                self._replacement_depends_on_targets_from_direct_callee(
                    caller_resolved_execution,
                    callee_binding_holes,
                )
            )
            if execution_index == 0:
                # The Guarantee Node needs the concrete relationships and remaining
                # Binding Holes from this action's perspective. Reducing them again
                # would discard relationships its consumers need.
                return replacement_depends_on_targets
            # The next Action Execution can bind only Binding Holes in its direct
            # callee. Reduce intermediate concrete relationships to that interface
            # without retaining the result after this Guarantee Node is resolved.
            concrete_caller_nodes, directly_propagated_binding_holes = (
                self._partition_replacement_depends_on_targets(
                    replacement_depends_on_targets
                )
            )
            callee_binding_holes = operation_graph_rules.binding_holes_depended_on_by(
                concrete_caller_nodes,
                caller_binding_holes=directly_propagated_binding_holes,
                replacement_depends_on_targets_by_node=caller_replacements,
            )
        raise AssertionError("a Guarantee Path must contain an Action Execution")

    def _replacement_depends_on_targets_from_direct_callee(
        self,
        resolved_execution: ResolvedActionExecution,
        callee_binding_holes: tuple[operation_graph_model.BindingHole, ...],
    ) -> list[_ActionDependsOnTarget]:
        """Return selected Binding Holes from the direct caller's perspective."""
        replacement_depends_on_targets: list[_ActionDependsOnTarget] = []
        for callee_binding_hole in callee_binding_holes:
            # A Binding Hole reached from a guaranteed Particle Operation has a
            # runtime consumer. Its binding therefore already exists on every
            # Action Execution in the guarantee path.
            callee_binding = resolved_execution.callee_bindings[callee_binding_hole]
            replacement_depends_on_targets.extend(
                callee_binding.caller_dependencies.concrete_nodes()
            )
            replacement_depends_on_targets.extend(callee_binding.caller_binding_holes)
        return replacement_depends_on_targets

    @staticmethod
    def _partition_replacement_depends_on_targets(
        replacement_depends_on_targets: Iterable[_ActionDependsOnTarget],
    ) -> tuple[
        list[operation_graph_model.ConcreteOperationNode],
        list[operation_graph_model.BindingHole],
    ]:
        concrete_nodes: list[operation_graph_model.ConcreteOperationNode] = []
        binding_holes: list[operation_graph_model.BindingHole] = []
        for target in replacement_depends_on_targets:
            if isinstance(
                target,
                (
                    operation_graph_model.PositionOperationNode,
                    operation_graph_model.GuaranteeNode,
                ),
            ):
                concrete_nodes.append(target)
            else:
                binding_holes.append(target)
        return concrete_nodes, binding_holes

    def build(
        self,
        operation_relationships: Iterable[_ResolvedOperationRelationships],
        action_executions: Iterable[ResolvedActionExecution],
        replacement_depends_on_targets_by_node: Mapping[
            operation_graph_model.OperationNode,
            Sequence[_ActionDependsOnTarget],
        ],
    ) -> ActionBindingHoles:
        """Build the action's ordered Binding Holes and lookup relationships."""
        # TODO: Investigate whether caching the Binding Holes reachable from each
        # node saves enough repeated traversal across guaranteed operations to
        # justify the cache's memory cost. All replacement targets are final here,
        # so such a cache would remain valid throughout this calculation.
        binding_holes_by_guaranteed_position = (
            self._binding_holes_by_guaranteed_position(
                replacement_depends_on_targets_by_node
            )
        )
        binding_holes: list[operation_graph_model.BindingHole] = []
        binding_holes_with_runtime_consumers: set[operation_graph_model.BindingHole] = (
            set()
        )
        for relationships in operation_relationships:
            if relationships.binding_holes_depended_on is None:
                continue
            for binding_hole in relationships.binding_holes_depended_on:
                binding_holes.append(binding_hole)
                binding_holes_with_runtime_consumers.add(binding_hole)
        for (
            guaranteed_operation_binding_holes
        ) in binding_holes_by_guaranteed_position.values():
            binding_holes.extend(guaranteed_operation_binding_holes)
        for resolved_execution in action_executions:
            for (
                callee_binding
            ) in resolved_execution.callee_bindings.with_runtime_consumers:
                for caller_binding_hole in callee_binding.caller_binding_holes:
                    binding_holes.append(caller_binding_hole)
                    binding_holes_with_runtime_consumers.add(caller_binding_hole)
            # The destructor might not act on an implied position, so resolving its
            # callee bindings does not necessarily discover this dependency.
            destructor_trigger_requirement = (
                resolved_execution.execution.destructor_trigger_requirement
            )
            if destructor_trigger_requirement is not None:
                binding_holes.append(destructor_trigger_requirement)
                binding_holes_with_runtime_consumers.add(destructor_trigger_requirement)
        binding_holes_in_binding_order = _callee_binding_holes_in_binding_order(
            binding_holes
        )
        return ActionBindingHoles(
            in_binding_order=binding_holes_in_binding_order,
            with_runtime_consumers=[
                binding_hole
                for binding_hole in binding_holes_in_binding_order
                if binding_hole in binding_holes_with_runtime_consumers
            ],
            _binding_holes_by_guaranteed_position=(
                binding_holes_by_guaranteed_position
            ),
        )

    def _binding_holes_by_guaranteed_position(
        self,
        replacement_depends_on_targets_by_node: Mapping[
            operation_graph_model.OperationNode,
            Sequence[_ActionDependsOnTarget],
        ],
    ) -> dict[tuple[str, ...], tuple[operation_graph_model.BindingHole, ...]]:
        """Return Binding Holes for this action's published guarantees."""
        binding_holes_by_guaranteed_position: dict[
            tuple[str, ...], tuple[operation_graph_model.BindingHole, ...]
        ] = {}
        for (
            operation,
            guaranteed_positions,
        ) in self._graph.guaranteed_positions_by_operation.items():
            binding_holes = operation_graph_rules.binding_holes_depended_on_by(
                (operation,),
                replacement_depends_on_targets_by_node=(
                    replacement_depends_on_targets_by_node
                ),
            )
            if binding_holes:
                for position in guaranteed_positions:
                    binding_holes_by_guaranteed_position[position] = binding_holes
        return binding_holes_by_guaranteed_position


@typing.final
class _ActionResolver:
    """Build the dependency interface of one reusable action."""

    def __init__(
        self,
        graph: operation_graph.OperationGraph,
        operation_graphs: operation_graph.OperationGraphs,
        resolved_callees: Mapping[ast.GlobalTypedName, ResolvedAction],
        resolved_empty_rule_binding_hole_by_operation_node: dict[
            operation_graph_model.EmptyRuleBindingHoleNode,
            operation_graph_model.EmptyRuleBindingHole,
        ]
        | None,
    ):
        """Initialize resolution with one graph and its resolved direct callees."""
        self._graph = graph
        self._operation_graphs = operation_graphs
        self._resolved_callees = resolved_callees
        self._resolved_empty_rule_binding_hole_by_operation_node = (
            resolved_empty_rule_binding_hole_by_operation_node
        )
        self._action_binding_holes_builder = _ActionBindingHolesBuilder(
            graph,
            operation_graphs,
            resolved_callees,
        )

    def resolve(self) -> ResolvedAction:
        """Resolve the action's operations and direct Action Executions."""
        relationships_by_operation: dict[
            operation_graph_model.PositionOperationNode,
            _ResolvedOperationRelationships,
        ] = collections.defaultdict(_ResolvedOperationRelationships)
        action_executions: list[ResolvedActionExecution] = []
        resolved_execution_by_execution: dict[
            operation_graph_model.ActionExecution, ResolvedActionExecution
        ] = {}
        # Binding direct callees can replace a node's graph-local relationships.
        # An absent entry keeps node.depends_on; an empty entry replaces it with no
        # targets.
        # Lazy nested-Guarantee translation needs the exact local replacements at
        # each Action Execution boundary. Keeping only changed relationships makes
        # this state proportional to the action graph.
        replacement_depends_on_targets_by_node: dict[
            operation_graph_model.OperationNode, Sequence[_ActionDependsOnTarget]
        ] = {}
        executions_by_trigger: dict[
            operation_graph_model.LastOperationNode,
            list[operation_graph_model.ActionExecution],
        ] = {}
        for execution in self._graph.executions:
            executions_by_trigger.setdefault(execution.trigger_operation, []).append(
                execution
            )
        for node in self._graph.nodes:
            if isinstance(node, operation_graph_model.EmptyRuleBindingHoleNode):
                binding_hole = _resolve_empty_rule_binding_hole(
                    node,
                    replacement_depends_on_targets_by_node,
                )
                if self._resolved_empty_rule_binding_hole_by_operation_node is not None:
                    self._resolved_empty_rule_binding_hole_by_operation_node[node] = (
                        binding_hole
                    )
                replacement_depends_on_targets_by_node[node] = (binding_hole,)
            elif isinstance(node, operation_graph_model.GuaranteeNode):
                resolved_execution = resolved_execution_by_execution[node.execution]
                replacement_depends_on_targets_by_node[node] = (
                    self._action_binding_holes_builder.replacement_depends_on_targets_for_guarantee(
                        node,
                        resolved_execution,
                        replacement_depends_on_targets_by_node,
                    )
                )
            elif isinstance(node, operation_graph_model.PositionOperationNode):
                relationships, replacement_depends_on_targets = self._resolve_operation(
                    node,
                    replacement_depends_on_targets_by_node,
                )
                if relationships is not None:
                    relationships_by_operation[node] = relationships
                if replacement_depends_on_targets is not None:
                    replacement_depends_on_targets_by_node[node] = (
                        replacement_depends_on_targets
                    )
            if isinstance(
                node,
                (
                    operation_graph_model.PositionOperationNode,
                    operation_graph_model.GuaranteeNode,
                    operation_graph_model.RequirementNode,
                ),
            ):
                for execution in executions_by_trigger.get(node, ()):
                    callee = self._resolved_callees[execution.callee_action_name]
                    resolved_execution = ResolvedActionExecution.resolve(
                        self._graph,
                        self._operation_graphs,
                        execution,
                        callee,
                        replacement_depends_on_targets_by_node,
                    )
                    action_executions.append(resolved_execution)
                    resolved_execution_by_execution[execution] = resolved_execution
                    if isinstance(
                        execution.trigger_operation,
                        operation_graph_model.PositionOperationNode,
                    ):
                        relationships_by_operation[
                            execution.trigger_operation
                        ].add_action_execution_triggered(resolved_execution)
        self._associate_callee_bindings_with_operations(
            relationships_by_operation,
            action_executions,
        )
        destruction_contributions: dict[
            operation_graph_model.ResolvedCalleeDestroy,
            ResolvedDestructionContribution,
        ] = {}
        for (
            resolved_callee_destroy,
            contribution,
        ) in self._operation_graphs.destruction_contributions(self._graph):
            destructors: list[ResolvedActionExecution] = []
            for execution in contribution.destructors:
                callee = self._resolved_callees[execution.callee_action_name]
                destructors.append(
                    ResolvedActionExecution.resolve(
                        self._graph,
                        self._operation_graphs,
                        execution,
                        callee,
                        replacement_depends_on_targets_by_node,
                    )
                )
            destruction_contributions[resolved_callee_destroy] = (
                ResolvedDestructionContribution(contribution, destructors)
            )
        binding_holes = self._action_binding_holes_builder.build(
            relationships_by_operation.values(),
            itertools.chain(
                action_executions,
                itertools.chain.from_iterable(
                    resolved_contribution.destructors
                    for resolved_contribution in destruction_contributions.values()
                ),
            ),
            replacement_depends_on_targets_by_node,
        )
        return ResolvedAction(
            graph=self._graph,
            relationships_by_operation=relationships_by_operation,
            binding_holes=binding_holes,
            action_executions=action_executions,
            destruction_contributions=destruction_contributions,
            resolved_execution_by_execution=resolved_execution_by_execution,
            replacement_depends_on_targets_by_node=(
                replacement_depends_on_targets_by_node
            ),
        )

    def _resolve_operation(
        self,
        operation: operation_graph_model.PositionOperationNode,
        replacement_depends_on_targets_by_node: Mapping[
            operation_graph_model.OperationNode,
            Sequence[_ActionDependsOnTarget],
        ],
    ) -> tuple[
        _ResolvedOperationRelationships | None,
        list[_ActionDependsOnTarget] | None,
    ]:
        depends_on_targets, relationships_changed = (
            self._depends_on_targets_for_operation(
                operation,
                replacement_depends_on_targets_by_node,
            )
        )
        replacement_depends_on_targets = None
        if relationships_changed:
            # A Destruction Contribution Node is the sole target of its contributed
            # Destroy and that relationship is never replaced. Therefore, any
            # changed relationship contains only targets used by the resolved action.
            replacement_depends_on_targets = typing.cast(
                "list[_ActionDependsOnTarget]", depends_on_targets
            )
        if not relationships_changed and all(
            isinstance(target, operation_graph_model.PositionOperationNode)
            for target in depends_on_targets
        ):
            return None, None
        dependencies, binding_holes, destruction_dependencies = (
            self._resolve_dependencies(depends_on_targets)
        )
        return (
            _ResolvedOperationRelationships(
                local_operations_depended_on=dependencies.local_operations,
                guarantee_dependencies=(dependencies.guarantee_dependencies or None),
                binding_holes_depended_on=binding_holes or None,
                destruction_dependencies=destruction_dependencies or None,
            ),
            replacement_depends_on_targets,
        )

    def _depends_on_targets_for_operation(
        self,
        operation: operation_graph_model.PositionOperationNode,
        replacement_depends_on_targets_by_node: Mapping[
            operation_graph_model.OperationNode,
            Sequence[_ActionDependsOnTarget],
        ],
    ) -> tuple[Sequence[_OperationDependsOnTarget], bool]:
        if isinstance(
            operation,
            operation_graph_model.MoveNodeWithPartialMoveRuleResult,
        ):
            move_rule_result, relationships_changed = (
                operation_graph_rules.apply_partial_move_rule_result(
                    operation,
                    replacement_depends_on_targets_by_node,
                )
            )
            partial_move_depends_on_targets: list[_OperationDependsOnTarget] = list(
                move_rule_result.concrete_caller_nodes
            )
            if move_rule_result.move_rule_binding_hole is not None:
                partial_move_depends_on_targets.append(
                    move_rule_result.move_rule_binding_hole
                )
            return partial_move_depends_on_targets, relationships_changed

        # Most operations retain every graph relationship. Allocate a replacement
        # list only after finding the first Binding Hole that action resolution
        # replaces.
        replacement_depends_on_targets: list[_OperationDependsOnTarget] | None = None
        for dependency_index, dependency in enumerate(operation.depends_on):
            match dependency:
                case operation_graph_model.EmptyRuleBindingHoleNode():
                    if replacement_depends_on_targets is None:
                        replacement_depends_on_targets = list(
                            operation.depends_on[:dependency_index]
                        )
                    replacement_depends_on_targets.append(
                        replacement_depends_on_targets_by_node[dependency][0]
                    )
                case (
                    operation_graph_model.ActionParentLastOperationNode()
                    | operation_graph_model.PositionOperationNode()
                    | operation_graph_model.DestructionContributionNode()
                    | operation_graph_model.GuaranteeNode()
                    | operation_graph_model.RequirementNode()
                ):
                    if replacement_depends_on_targets is not None:
                        replacement_depends_on_targets.append(dependency)
        relationships_changed = replacement_depends_on_targets is not None
        depends_on_targets: Sequence[_OperationDependsOnTarget]
        if replacement_depends_on_targets is None:
            depends_on_targets = operation.depends_on
        else:
            depends_on_targets = replacement_depends_on_targets
        if (
            isinstance(operation, operation_graph_model.DestroyNode)
            and operation.depends_on_path_contains_guarantee_or_partial_move_rule
        ):
            corrected_depends_on_targets = (
                self._apply_move_correction_to_resolved_destroy_depends_on_targets(
                    depends_on_targets,
                    replacement_depends_on_targets_by_node,
                )
            )
            if corrected_depends_on_targets is not depends_on_targets:
                relationships_changed = True
                depends_on_targets = corrected_depends_on_targets
        return depends_on_targets, relationships_changed

    def _apply_move_correction_to_resolved_destroy_depends_on_targets(
        self,
        depends_on_targets: Sequence[_OperationDependsOnTarget],
        replacement_depends_on_targets_by_node: Mapping[
            operation_graph_model.OperationNode,
            Sequence[_ActionDependsOnTarget],
        ],
    ) -> Sequence[_OperationDependsOnTarget]:
        """Reapply Move Correction to a Destroy after action resolution."""
        empty_dependencies: list[operation_graph_model.LastOperationNode] = []
        for depends_on_target in depends_on_targets:
            match depends_on_target:
                case (
                    operation_graph_model.PositionOperationNode()
                    | operation_graph_model.GuaranteeNode()
                    | operation_graph_model.RequirementNode()
                ):
                    empty_dependencies.append(depends_on_target)
                case _:
                    pass
        empty_dependencies.sort(key=lambda node: node.operation_order)
        remaining_empty_dependencies = (
            operation_graph_rules.apply_move_correction_and_fill_dependency_removal(
                empty_dependencies,
                None,
                replacement_depends_on_targets_by_node=(
                    replacement_depends_on_targets_by_node
                ),
            )
        )
        # Move Correction considers only Empty Dependencies, while the resolved
        # Destroy can also depend on Binding Holes and Destruction Contributions.
        # Remove exactly the Empty Dependencies it excluded so those other
        # depends_on targets retain their existing order.
        removed_empty_dependencies = set(empty_dependencies)
        removed_empty_dependencies.difference_update(remaining_empty_dependencies)
        if not removed_empty_dependencies:
            return depends_on_targets
        return [
            depends_on_target
            for depends_on_target in depends_on_targets
            if depends_on_target not in removed_empty_dependencies
        ]

    @staticmethod
    def _associate_callee_bindings_with_operations(
        relationships_by_operation: dict[
            operation_graph_model.PositionOperationNode,
            _ResolvedOperationRelationships,
        ],
        action_executions: list[ResolvedActionExecution],
    ):
        """Associate bindings after resolution because they can name later operations."""
        for resolved_execution in action_executions:
            for (
                callee_binding
            ) in resolved_execution.callee_bindings.with_runtime_consumers:
                for operation in callee_binding.caller_dependencies.local_operations:
                    relationships_by_operation[
                        operation
                    ].add_callee_binding_depending_on(callee_binding)

    def _resolve_dependencies(
        self,
        dependency_nodes: Sequence[_OperationDependsOnTarget],
    ) -> tuple[
        ActionDependencies,
        list[operation_graph_model.BindingHole],
        list[operation_graph_model.ResolvedCalleeDestroy],
    ]:
        dependencies = ActionDependencies([], [])
        binding_holes: list[operation_graph_model.BindingHole] = []
        destruction_dependencies: list[operation_graph_model.ResolvedCalleeDestroy] = []
        for dependency in dependency_nodes:
            if isinstance(
                dependency, operation_graph_model.DestructionContributionNode
            ):
                destruction_dependencies.append(
                    self._operation_graphs.resolve_callee_destroy(
                        dependency.callee_destroy
                    )
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
    """Resolve and retain actions in direct-callee-first definition order.

    Each action is resolved once after its direct callees, so parallel planning
    writes distinct cached actions and only reads completed callee entries.
    """

    def __init__(
        self,
        operation_graphs: operation_graph.OperationGraphs,
        *,
        resolved_empty_rule_binding_hole_by_operation_node: dict[
            operation_graph_model.EmptyRuleBindingHoleNode,
            operation_graph_model.EmptyRuleBindingHole,
        ]
        | None = None,
    ):
        """Initialize with the validated operation graphs."""
        self._operation_graphs = operation_graphs
        self._resolved_empty_rule_binding_hole_by_operation_node = (
            resolved_empty_rule_binding_hole_by_operation_node
        )
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
            self._resolved_empty_rule_binding_hole_by_operation_node,
        ).resolve()
        self._resolved[action] = resolved
        return resolved

    def __getitem__(self, action: ast.GlobalTypedName) -> ResolvedAction:
        """Return a resolved action."""
        return self._resolved[action]
