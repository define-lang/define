"""DLP 44 lowering for action code generation.

See ``define/compiler/operation_graph_execution_design.md`` for the shared design.

The responsibility of actual codegen renderers should be little more than
translating what's in this plan into names and structures appropriate for
a particular programming language.

The primary purpose of this module is to take in actions where the operation
dependency relationships of the direct callees have been fully resolved and
turn those actions into fragments. A fragment is an independent set of
straight-line operations that have only single, linear dependencies on each
other (basically, one single function that can run synchronously). The
planner then also provides the information needed to render these fragments
into code, such as join requirements and which fragments call each other.

It also provides other data structures that codegen will need in order to
actually render an action, such as information about which guarantees an
action provides, in the exact form that codegen needs in order to render
those guarantees into generated code.

All of these different constructs and their relationships form into
ActionPlan, which is the primary output of this module.

In general, codegen is responsible for language-specific details, and the
action planner (and the code below it) is responsible for language-independent
logical representations of what we intend to render.
"""

from __future__ import annotations

import typing
from dataclasses import dataclass, field

from define.compiler.data_structures import typed_name_dict
from define.compiler.validator.reference_graph import (
    operation_graph,
    operation_graph_action_resolver,
    operation_graph_model,
)

if typing.TYPE_CHECKING:
    from collections.abc import Collection, Iterable, Iterator, Mapping, Sequence

    from define.compiler import ast


# TODO: Trace the complete dataflow from an Operation Graph through every stage
# of codegen—including resolution, action planning, naming, context construction,
# and template rendering—all the way to the final generated source. The purpose
# of the whole pipeline is to perform that transformation, so streamline the
# dataflow across its existing stages to provide the clearest and simplest path
# from the Operation Graph to generated source. Remove intermediate shapes that
# exist only for a later stage to reconstruct the same data or relationships.
type FanoutContinuation = ActionFragment | CalleeBindingPlan | DestructionConnection
type DestructionConnectionContinuation = (
    ActionFragment | CalleeBindingPlan | DestructionContractDestructorExecutionPlan
)


@dataclass(slots=True, eq=False)
class InitPlan:
    """Runtime-state init performed together before runnable work starts."""

    callee_binding_plans: list[CalleeBindingPlan] = field(
        init=False, default_factory=list
    )
    action_executions: list[operation_graph_model.ActionExecution] = field(
        init=False, default_factory=list
    )
    _action_execution_set: set[operation_graph_model.ActionExecution] = field(
        init=False, default_factory=set
    )

    def append_action_execution(
        self,
        execution: operation_graph_model.ActionExecution,
    ):
        """Add an Action Execution to this init point."""
        self.action_executions.append(execution)
        self._action_execution_set.add(execution)

    def contains(
        self,
        execution: operation_graph_model.ActionExecution,
    ) -> bool:
        """Whether this plan directly inits the Action Execution."""
        return execution in self._action_execution_set

    @property
    def has_inits(self) -> bool:
        """Whether this plan performs any init."""
        return bool(self.action_executions or self.callee_binding_plans)


@dataclass(slots=True, eq=False)
class ActionFragment:
    """A maximal direct-call chain of Particle Operations."""

    operations: list[operation_graph_model.PositionOperationNode]
    guarantee_dependencies: Sequence[operation_graph.ResolvedGuarantee] = field(
        init=False, default=()
    )
    guarantees: ActionGuarantees | None = field(init=False, default=None)
    inline_callee_binding_plans: list[CalleeBindingPlan] = field(
        init=False,
        default_factory=list,
    )
    inits: InitPlan = field(
        init=False,
        default_factory=InitPlan,
    )
    fanout_continuations: list[FanoutContinuation] = field(
        init=False,
        default_factory=list,
    )
    dependency_count: int = field(init=False, default=0)
    caller_binding_hole: operation_graph_action_resolver.ResolvedBindingHole | None = (
        field(
            init=False,
            default=None,
        )
    )

    @property
    def join_is_assigned_by_caller(self) -> bool:
        """Whether a caller determines this fragment's realized predecessors."""
        return self.caller_binding_hole is not None

    @property
    def requires_join_check(self) -> bool:
        """Whether runtime invocation must check for the final Join arrival."""
        return self.join_is_assigned_by_caller or self.dependency_count > 1

    @property
    def fixed_dependency_count(self) -> int:
        """Return predecessors known without resolving this action's caller."""
        return self.dependency_count - int(self.caller_binding_hole is not None)

    @property
    def guarantee_dependent_destroy(
        self,
    ) -> operation_graph_model.DestructionFragmentDestroyNode | None:
        """A contributed Destroy with a Guarantee dependency needs its Position at run time."""
        first_operation = self.operations[0]
        if (
            isinstance(
                first_operation,
                operation_graph_model.DestructionFragmentDestroyNode,
            )
            and self.guarantee_dependencies
        ):
            return first_operation
        return None


@dataclass(slots=True, eq=False)
class DestructionActionFragment(ActionFragment):
    """An Action Fragment that requires a destruction continuation.

    The distinct type lets consumers identify these fragments and access their
    propagated Destruction Fact Destroy without giving every ActionFragment an
    optional propagated Destruction Fact Destroy.
    """

    @property
    def destruction_operation(
        self,
    ) -> operation_graph_model.DestructionFactDestroyNode:
        """Return the propagated Destruction Fact Destroy starting this fragment."""
        return typing.cast(
            "operation_graph_model.DestructionFactDestroyNode", self.operations[0]
        )


@dataclass(slots=True, eq=False)
class DestructionConnection:
    """Caller-contributed continuations connected to a direct callee Destroy."""

    callee_destroy: operation_graph_model.DestructionOperation
    continuations: list[DestructionConnectionContinuation]
    predecessor_count: int

    @property
    def destruction_contract_destructors(
        self,
    ) -> Iterator[DestructionContractDestructorExecutionPlan]:
        """Return the contributed Destructor executions in this fanout."""
        return (
            continuation
            for continuation in self.continuations
            if isinstance(continuation, DestructionContractDestructorExecutionPlan)
        )


@dataclass(frozen=True, slots=True, kw_only=True, eq=False)
class ActionExecutionPlan:
    """One direct Action Execution and its destruction-connection behavior."""

    execution: operation_graph_model.ActionExecution
    created_destruction_connections: list[DestructionConnection] = field(
        default_factory=list
    )
    callee_join_assignments: list[CalleeJoinAssignment] = field(default_factory=list)
    guarantee_consumption_plans: list[GuaranteeConsumptionPlan] = field(
        default_factory=list
    )
    deferred_guarantee_registrations: list[DeferredGuaranteeRegistration] = field(
        default_factory=list
    )
    forwards_destruction_connections: bool = False


@dataclass(frozen=True, slots=True, kw_only=True, eq=False)
class ContributedDestructorActionExecutionPlan(ActionExecutionPlan):
    """A contributed Destructor fired by another Action Execution's Destroy."""

    destroying_action_execution: operation_graph_model.ActionExecution


@dataclass(slots=True)
class _DestructionConnectionPlans:
    """The Destruction Connections and contributed Destructors for one action."""

    destruction_connection_by_operation: dict[
        operation_graph_model.DestructionFragmentDestroyNode,
        DestructionConnection,
    ] = field(default_factory=dict)
    destruction_connection_by_callee_destroy: dict[
        operation_graph_model.ResolvedCalleeDestroy,
        DestructionConnection,
    ] = field(default_factory=dict)
    connections_by_guarantee: dict[
        operation_graph.ResolvedGuarantee,
        list[DestructionConnection],
    ] = field(default_factory=dict)
    created_connections_by_execution: dict[
        operation_graph_model.ActionExecution,
        list[DestructionConnection],
    ] = field(default_factory=dict)
    contributed_destructor_destroying_execution_by_execution: dict[
        operation_graph_model.ActionExecution,
        operation_graph_model.ActionExecution,
    ] = field(default_factory=dict)


@dataclass(frozen=True, slots=True, eq=False)
class CallerResolvedJoin:
    """A reusable continuation join whose realized predecessors depend on its caller."""

    execution_path: tuple[operation_graph_model.ActionExecution, ...]
    target: JoinTarget
    fixed_dependency_count: int
    caller_binding_hole: operation_graph_action_resolver.ResolvedBindingHole


@dataclass(frozen=True, slots=True, eq=False)
class CalleeJoinAssignment:
    """One caller-selected Join for a direct Action Execution."""

    execution_path: tuple[operation_graph_model.ActionExecution, ...]
    target: JoinTarget
    dependency_count: int


@dataclass(frozen=True, slots=True)
class ViewPointCreatePlan:
    """The reusable Action Plan arrivals for the view-point Create."""

    binding_holes: Iterable[operation_graph_action_resolver.ResolvedBindingHole]
    join_assignments: list[CalleeJoinAssignment]


@dataclass(frozen=True, slots=True, eq=False)
class DeferredGuaranteeRegistration:
    """A Guarantee registration performed after its execution path exists."""

    prerequisite_guarantee: operation_graph.ResolvedGuarantee
    consumption_plan: GuaranteeConsumptionPlan


@dataclass(slots=True, eq=False)
class DestructionContractDestructorExecutionPlan:
    """A Destructor Contract contribution fired by a destruction connection."""

    execution: operation_graph_model.ActionExecution
    action_parent_binding_hole: operation_graph_model.ActionParentLastOperationNode
    guarantees_preceding_callee_destroy: Sequence[operation_graph.ResolvedGuarantee]


@dataclass(slots=True)
class _DestructionContractDestructorPlans:
    """The Action Executions and destruction-time triggers for contributed Destructors."""

    destroying_execution_by_execution: dict[
        operation_graph_model.ActionExecution,
        operation_graph_model.ActionExecution,
    ]
    destruction_contract_destructors: list[DestructionContractDestructorExecutionPlan]


@dataclass(slots=True, eq=False)
class BindingHoleFanout:
    """Init and runnable fanout for one Binding Hole."""

    binding_hole: operation_graph_action_resolver.ResolvedBindingHole
    inits: InitPlan = field(
        init=False,
        default_factory=InitPlan,
    )
    continuations: list[FanoutContinuation] = field(
        init=False,
        default_factory=list,
    )

    @property
    def join_is_assigned_by_caller(self) -> bool:
        """Whether the caller resolves this operation-specific Binding Hole."""
        return (
            not operation_graph_action_resolver.binding_hole_binds_one_caller_operation(
                self.binding_hole,
            )
        )

    @property
    def requires_join_check(self) -> bool:
        """Whether runtime invocation must check for the final Join arrival."""
        return self.join_is_assigned_by_caller


@dataclass(slots=True, eq=False)
class CalleeBindingPlan:
    """The runtime plan for completing one direct Callee Binding."""

    execution: operation_graph_model.ActionExecution
    _callee_binding: operation_graph_action_resolver.CalleeBinding = field(repr=False)
    callee_fanout: BindingHoleFanout = field(repr=False)
    inline_after_local_operation: bool = False
    post_init_join_assignments: list[CalleeJoinAssignment] = field(default_factory=list)
    post_init_guarantee_consumption_plans: list[GuaranteeConsumptionPlan] = field(
        default_factory=list
    )
    _caller_fanouts_containing_init: list[tuple[InitPlan, list[FanoutContinuation]]] = (
        field(
            default_factory=list,
            repr=False,
        )
    )
    _requires_init_before_caller_fanout: bool = field(
        init=False,
        default=False,
        repr=False,
    )

    @property
    def callee_binding_hole(
        self,
    ) -> operation_graph_action_resolver.ResolvedBindingHole:
        """The callee Binding Hole invoked by this join."""
        return self.callee_fanout.binding_hole

    @property
    def guarantee_dependencies(self) -> list[operation_graph.GuaranteePath]:
        """The Action Guarantees whose publication provides a join arrival."""
        return self._callee_binding.caller_dependencies.guarantee_dependencies

    @property
    def dependency_count(self) -> int:
        """Return the number of resolved and unresolved dependencies."""
        return self._callee_binding.dependency_count

    @property
    def contributed_destruction_operations(
        self,
    ) -> list[operation_graph_model.DestructionFragmentDestroyNode]:
        """The caller-known Destroy operations captured by this join."""
        return self._callee_binding.contributed_destruction_operations

    @property
    def join_is_assigned_by_caller(self) -> bool:
        """Whether a caller determines this binding's realized predecessors."""
        # Action Parent and Requirement bindings receive one caller operation;
        # the caller resolves any multiple Empty Rule dependencies first.
        if self._callee_binding.binds_one_caller_operation:
            return False
        return self.caller_binding_hole is not None

    @property
    def requires_join_check(self) -> bool:
        """Whether runtime invocation must check for the final Join arrival."""
        return self.join_is_assigned_by_caller or self.dependency_count > 1

    @property
    def caller_binding_hole(
        self,
    ) -> operation_graph_action_resolver.ResolvedBindingHole | None:
        """Return the unresolved predecessor passed to a later caller."""
        return self._callee_binding.caller_binding_hole

    @property
    def has_inits(self) -> bool:
        """Whether this invocation synchronously performs init."""
        return self.callee_fanout.inits.has_inits

    @property
    def has_continuations(self) -> bool:
        """Whether this invocation starts runnable continuations after init."""
        return bool(self.callee_fanout.continuations)

    @property
    def configures_action_executions_after_init(self) -> bool:
        """Whether the caller configures Action Executions after their init."""
        return bool(
            self.post_init_join_assignments
            or self.post_init_guarantee_consumption_plans
        )

    @property
    def requires_separate_init(self) -> bool:
        """Whether a caller must invoke init before the callee fanout."""
        return bool(
            self.has_continuations
            and (
                self._requires_init_before_caller_fanout
                or any(
                    len(continuations) != 1
                    for _, continuations in self._caller_fanouts_containing_init
                )
                or self.configures_action_executions_after_init
            )
        )

    @property
    def caller_invokes_init_method(self) -> bool:
        """Whether this Callee Binding makes the caller invoke an init method."""
        return self.requires_separate_init or (
            self.has_inits and not self.has_continuations
        )

    @property
    def fixed_dependency_count(self) -> int:
        """Return predecessors already resolved within this action."""
        return self.dependency_count - int(self.caller_binding_hole is not None)

    @property
    def requires_caller_method(self) -> bool:
        """Whether invoking this Callee Binding requires caller-side work."""
        return not self.inline_after_local_operation and self._has_caller_work

    @property
    def _has_caller_work(self) -> bool:
        """Whether this Callee Binding performs work specific to its caller."""
        return bool(
            self.guarantee_dependencies
            or self.contributed_destruction_operations
            or self._callee_binding.callee_destroy_for_empty_or_fill_dependency
            is not None
            or self.requires_separate_init
            or self.post_init_guarantee_consumption_plans
        )

    @property
    def invokes_callee_binding_hole(self) -> bool:
        """Whether the caller method invokes the callee Binding Hole."""
        return bool(
            self.has_continuations
            and not self.requires_separate_init
            and not self.inline_after_local_operation
        )

    def add_to(
        self,
        inits: InitPlan,
        continuations: list[FanoutContinuation],
    ):
        """Add this Callee Binding to the init and fanout it requires."""
        if self.has_inits:
            inits.callee_binding_plans.append(self)
            self._caller_fanouts_containing_init.append((inits, continuations))
        if self.has_continuations:
            continuations.append(self)

    def place_after_local_operation(self, fragment: ActionFragment):
        """Place caller work immediately after its sole Particle Operation."""
        self.inline_after_local_operation = True
        fragment.inline_callee_binding_plans.append(self)
        if self.has_continuations:
            if self.has_inits:
                self._requires_init_before_caller_fanout = True
            fragment.fanout_continuations.append(self)

    def finalize_init(self):
        """Let a Callee Binding Hole perform init used only by its fanout."""
        self._requires_init_before_caller_fanout = (
            self._requires_init_before_caller_fanout
            or any(
                len(continuations) != 1
                for _, continuations in self._caller_fanouts_containing_init
            )
        )
        if self.has_continuations and not self.configures_action_executions_after_init:
            for inits, continuations in self._caller_fanouts_containing_init:
                if len(continuations) == 1:
                    inits.callee_binding_plans.remove(self)
        self._caller_fanouts_containing_init.clear()


type JoinTarget = ActionFragment | BindingHoleFanout | CalleeBindingPlan


type _CalleeBindingPlansByCalleeBinding = dict[
    operation_graph_action_resolver.CalleeBinding,
    CalleeBindingPlan,
]


@dataclass(slots=True)
class _CalleeBindingPlans:
    """Direct Callee Binding plans and the Binding Hole fanouts they invoke."""

    by_callee_binding: _CalleeBindingPlansByCalleeBinding
    binding_hole_fanouts: dict[
        operation_graph_action_resolver.ResolvedBindingHole,
        BindingHoleFanout,
    ]

    @property
    def caller_method_plans(self) -> list[CalleeBindingPlan]:
        """Return Callee Bindings that need work in the direct caller."""
        return [
            callee_binding_plan
            for callee_binding_plan in self.by_callee_binding.values()
            if callee_binding_plan.requires_caller_method
        ]


@dataclass(frozen=True, slots=True, eq=False)
class ActionGuarantees:
    """Source and target Guarantees produced by one local Particle Operation."""

    operation: operation_graph_model.PositionOperationNode
    guaranteed_source: tuple[str, ...] | None
    guaranteed_target: tuple[str, ...] | None


@dataclass(slots=True, eq=False)
class GuaranteeConsumptionPlan:
    """This action's work that consumes one resolved callee Action Guarantee."""

    guarantee: operation_graph.ResolvedGuarantee
    inits: InitPlan = field(
        init=False,
        default_factory=InitPlan,
    )
    continuations: list[FanoutContinuation] = field(
        init=False,
        default_factory=list,
    )


@dataclass(frozen=True, slots=True)
class _ActionExecutionInitPlacements:
    """The plan points that init Action Executions."""

    creation_inits: InitPlan
    binding_hole_by_action_execution: dict[
        operation_graph_model.ActionExecution,
        operation_graph_action_resolver.ResolvedBindingHole,
    ]


@dataclass(frozen=True, slots=True)
class _InitPlans:
    """Init and Guarantee consumption plans."""

    creation_inits: InitPlan
    guarantee_consumption_plans: list[GuaranteeConsumptionPlan]
    init_binding_hole_by_action_execution: dict[
        operation_graph_model.ActionExecution,
        operation_graph_action_resolver.ResolvedBindingHole,
    ]


@dataclass(frozen=True, slots=True)
class ActionPlan:
    """A split representation of an action at one compilation boundary."""

    fragments: list[ActionFragment]
    binding_hole_fanouts: dict[
        operation_graph_action_resolver.ResolvedBindingHole,
        BindingHoleFanout,
    ]
    action_executions: dict[
        operation_graph_model.ActionExecution,
        ActionExecutionPlan,
    ]
    creation_inits: InitPlan
    callee_binding_method_plans: list[CalleeBindingPlan]
    guarantee_consumption_plans: list[GuaranteeConsumptionPlan]
    init_binding_hole_by_action_execution: dict[
        operation_graph_model.ActionExecution,
        operation_graph_action_resolver.ResolvedBindingHole,
    ]
    accepts_destruction_connections: bool
    destruction_connection_by_operation: dict[
        operation_graph_model.DestructionFragmentDestroyNode,
        DestructionConnection,
    ]
    caller_resolved_joins: list[CallerResolvedJoin]

    def view_point_create_plan(self) -> ViewPointCreatePlan:
        """Resolve the view-point Create against this reusable Action Plan."""
        join_assignments: list[CalleeJoinAssignment] = []
        for caller_resolved_join in self.caller_resolved_joins:
            # The view-point Create is the one realized predecessor represented
            # by the unresolved caller Binding Hole.
            dependency_count = caller_resolved_join.fixed_dependency_count + 1
            join_assignments.append(
                CalleeJoinAssignment(
                    caller_resolved_join.execution_path,
                    caller_resolved_join.target,
                    dependency_count,
                )
            )
        return ViewPointCreatePlan(
            self.binding_hole_fanouts.keys(),
            join_assignments,
        )


@dataclass(slots=True)
class _ActionFragmentPlans:
    """The planned fragments of one action before its Action Plan is assembled.

    Each fragment is a maximal serial chain of Particle Operations. The plans
    record each fragment and the fragment containing each Particle Operation.
    """

    fragments: list[ActionFragment]
    fragment_for_operation: dict[
        operation_graph_model.PositionOperationNode, ActionFragment
    ]


@typing.final
class _ActionFragmentPlanner:
    """Plan one action's Particle Operations as code-generation fragments.

    A fragment ends where a direct method call would not preserve fan-out, a
    join, an Action Execution, guarantee publication, or a Binding Hole resolved
    by the caller.
    """

    def __init__(
        self,
        resolved_action: operation_graph_action_resolver.ResolvedAction,
    ):
        self._resolved_action = resolved_action

    def plan(self) -> _ActionFragmentPlans:
        direct_dependents_by_operation = (
            self._resolved_action.direct_dependents_by_operation()
        )
        fragments = self._build_fragments(direct_dependents_by_operation)
        fragment_for_operation: dict[
            operation_graph_model.PositionOperationNode, ActionFragment
        ] = {}
        for fragment in fragments:
            for operation in fragment.operations:
                fragment_for_operation[operation] = fragment
        for fragment in fragments:
            for direct_dependent in direct_dependents_by_operation[
                fragment.operations[-1]
            ]:
                fragment.fanout_continuations.append(
                    fragment_for_operation[direct_dependent]
                )
        return _ActionFragmentPlans(
            fragments,
            fragment_for_operation,
        )

    def _build_fragment(
        self, operations: list[operation_graph_model.PositionOperationNode]
    ) -> ActionFragment:
        if self._resolved_action.graph.is_propagated_destruction_operation(
            operations[0]
        ):
            fragment = DestructionActionFragment(operations)
        else:
            fragment = ActionFragment(operations)

        first_operation = operations[0]
        fragment.guarantee_dependencies = (
            self._resolved_action.guarantee_dependencies_for(first_operation)
        )
        fragment.dependency_count = self._fragment_dependency_count(
            first_operation,
            fragment.guarantee_dependencies,
        )
        fragment.guarantees = self._action_guarantees_for(operations[-1])
        return fragment

    def _action_guarantees_for(
        self,
        operation: operation_graph_model.PositionOperationNode,
    ) -> ActionGuarantees | None:
        guaranteed_positions = (
            self._resolved_action.graph.direct_guarantees_by_operation.get(operation)
        )
        if guaranteed_positions is None:
            return None
        guaranteed_source = None
        if isinstance(operation, operation_graph_model.MoveNode):
            source = operation.source.canonical_chained_name_tuple
            if source in guaranteed_positions:
                guaranteed_source = source
        target = operation.target.canonical_chained_name_tuple
        return ActionGuarantees(
            operation=operation,
            guaranteed_source=guaranteed_source,
            guaranteed_target=(target if target in guaranteed_positions else None),
        )

    def _fragment_dependency_count(
        self,
        first_operation: operation_graph_model.PositionOperationNode,
        guarantee_dependencies: Sequence[operation_graph.ResolvedGuarantee],
    ) -> int:
        destruction_dependency_count = 0
        if isinstance(
            first_operation,
            operation_graph_model.DestructionFactDestroyNode,
        ):
            destruction_dependency_count = len(
                self._resolved_action.destruction_dependencies_for(first_operation)
            )
        return (
            len(self._resolved_action.local_operations_depended_on_by(first_operation))
            + len(guarantee_dependencies)
            + destruction_dependency_count
        )

    def _build_fragments(
        self,
        direct_dependents_by_operation: dict[
            operation_graph_model.PositionOperationNode,
            list[operation_graph_model.PositionOperationNode],
        ],
    ) -> list[ActionFragment]:
        callee_action_parent_fill_operations = (
            self._resolved_action.callee_action_parent_fill_operations()
        )
        fragments: list[ActionFragment] = []
        for head in self._resolved_action.graph.particle_operations:
            if self._can_follow_predecessor(
                head,
                direct_dependents_by_operation,
                callee_action_parent_fill_operations,
            ):
                continue
            chain = [head]
            while True:
                direct_dependents = direct_dependents_by_operation[chain[-1]]
                if len(direct_dependents) != 1:
                    break
                direct_dependent = direct_dependents[0]
                if not self._can_follow_predecessor(
                    direct_dependent,
                    direct_dependents_by_operation,
                    callee_action_parent_fill_operations,
                ):
                    break
                chain.append(direct_dependent)
            fragments.append(self._build_fragment(chain))
        return fragments

    def _can_follow_predecessor(
        self,
        operation: operation_graph_model.PositionOperationNode,
        direct_dependents_by_operation: dict[
            operation_graph_model.PositionOperationNode,
            list[operation_graph_model.PositionOperationNode],
        ],
        callee_action_parent_fill_operations: set[
            operation_graph_model.PositionOperationNode
        ],
    ) -> bool:
        predecessors = self._resolved_action.local_operations_depended_on_by(operation)
        if len(predecessors) != 1:
            return False
        if (
            self._resolved_action.graph.is_propagated_destruction_operation(operation)
            or not self._resolved_action.depends_only_on_particle_operations_in_this_action(
                operation
            )
        ):
            return False
        predecessor = predecessors[0]
        return len(direct_dependents_by_operation[predecessor]) == 1 and not (
            self._must_end_fragment(
                predecessor,
                callee_action_parent_fill_operations,
            )
        )

    def _must_end_fragment(
        self,
        operation: operation_graph_model.PositionOperationNode,
        callee_action_parent_fill_operations: set[
            operation_graph_model.PositionOperationNode
        ],
    ) -> bool:
        return bool(
            operation in self._resolved_action.graph.direct_guarantees_by_operation
            or self._resolved_action.callee_bindings_depending_on(operation)
            or operation in callee_action_parent_fill_operations
        )


@typing.final
class _DestructionConnectionPlanner:
    """Plan one action's Destruction Connections and contributed Destructors."""

    def __init__(
        self,
        resolved_action: operation_graph_action_resolver.ResolvedAction,
        fragment_for_operation: Mapping[
            operation_graph_model.PositionOperationNode,
            ActionFragment,
        ],
    ):
        self._resolved_action = resolved_action
        self._fragment_for_operation = fragment_for_operation

    def plan(self) -> _DestructionConnectionPlans:
        """Plan Destruction Connections and contributed Destructors."""
        plans = _DestructionConnectionPlans()
        for (
            resolved_callee_destroy,
            resolved_contribution,
        ) in self._resolved_action.destruction_contributions.items():
            self._plan_connection_for_callee_destroy(
                resolved_callee_destroy,
                resolved_contribution,
                plans,
            )
        return plans

    def _plan_connection_for_callee_destroy(
        self,
        resolved_callee_destroy: operation_graph_model.ResolvedCalleeDestroy,
        resolved_contribution: operation_graph_action_resolver.ResolvedDestructionContribution,
        plans: _DestructionConnectionPlans,
    ):
        contribution = resolved_contribution.operation_graph_contribution
        destructor_guarantees_by_execution = resolved_contribution.destructor_guarantees_preceding_callee_destroy_by_execution
        destruction_connection_continuations: list[
            DestructionConnectionContinuation
        ] = []
        for operation in contribution.first_operations:
            destruction_connection_continuations.append(
                self._fragment_for_operation[operation]
            )
        completion_fragments: list[ActionFragment] = []
        for operation in contribution.completion_operations:
            completion_fragments.append(self._fragment_for_operation[operation])
        destruction_contract_destructor_plans = (
            self._plan_destruction_contract_destructors_for_one_callee_destroy(
                resolved_callee_destroy,
                resolved_contribution,
            )
        )
        plans.contributed_destructor_destroying_execution_by_execution.update(
            destruction_contract_destructor_plans.destroying_execution_by_execution
        )
        destruction_connection_continuations.extend(
            destruction_contract_destructor_plans.destruction_contract_destructors
        )
        if not (
            destruction_connection_continuations
            or completion_fragments
            or destructor_guarantees_by_execution
            or resolved_contribution.destructor_binding_depends_on_callee_destroy(
                resolved_callee_destroy
            )
        ):
            # No caller-contributed Destroy or Destructor receives an Empty or
            # Fill Dependency, or a dependency from the Action Parent Rule,
            # from this callee Destroy. The callee Destroy also depends on no
            # caller-contributed Particle Operation, so it needs no Destruction
            # Connection.
            return
        predecessor_count = len(completion_fragments)
        for guarantees in destructor_guarantees_by_execution.values():
            predecessor_count += len(guarantees)
        connection = DestructionConnection(
            resolved_callee_destroy.callee_destroy,
            destruction_connection_continuations,
            predecessor_count,
        )
        plans.destruction_connection_by_callee_destroy[resolved_callee_destroy] = (
            connection
        )
        for (
            destructor_execution,
            guarantees,
        ) in destructor_guarantees_by_execution.items():
            if (
                destructor_execution
                not in plans.contributed_destructor_destroying_execution_by_execution
            ):
                continue
            for guarantee in guarantees:
                connections = plans.connections_by_guarantee.get(guarantee)
                if connections is None:
                    connections = []
                    plans.connections_by_guarantee[guarantee] = connections
                connections.append(connection)
        created_connections = plans.created_connections_by_execution.get(
            resolved_callee_destroy.direct_callee_execution
        )
        if created_connections is None:
            created_connections = []
            plans.created_connections_by_execution[
                resolved_callee_destroy.direct_callee_execution
            ] = created_connections
        created_connections.append(connection)
        for fragment in completion_fragments:
            fragment.fanout_continuations.append(connection)
        for operation in contribution.operations:
            plans.destruction_connection_by_operation[operation] = connection

    def _plan_destruction_contract_destructors_for_one_callee_destroy(
        self,
        resolved_callee_destroy: operation_graph_model.ResolvedCalleeDestroy,
        resolved_contribution: operation_graph_action_resolver.ResolvedDestructionContribution,
    ) -> _DestructionContractDestructorPlans:
        """Plan Destructors contributed at one callee Destroy."""
        destroying_execution_by_execution: dict[
            operation_graph_model.ActionExecution,
            operation_graph_model.ActionExecution,
        ] = {}
        destruction_contract_destructors: list[
            DestructionContractDestructorExecutionPlan
        ] = []
        for resolved_destructor in resolved_contribution.destructors:
            action_parent_binding_hole = (
                resolved_destructor.sole_action_parent_runtime_binding_hole
            )
            if action_parent_binding_hole is None:
                execution = resolved_destructor.execution
                destroying_execution_by_execution[execution] = (
                    resolved_callee_destroy.direct_callee_execution
                )
                continue
            guarantees_preceding_callee_destroy = resolved_contribution.destructor_guarantees_preceding_callee_destroy_by_execution.get(
                resolved_destructor.execution,
                (),
            )
            destruction_contract_destructors.append(
                DestructionContractDestructorExecutionPlan(
                    execution=resolved_destructor.execution,
                    action_parent_binding_hole=action_parent_binding_hole,
                    guarantees_preceding_callee_destroy=(
                        guarantees_preceding_callee_destroy
                    ),
                )
            )
        return _DestructionContractDestructorPlans(
            destroying_execution_by_execution,
            destruction_contract_destructors,
        )


@typing.final
class _CalleeBindingPlanner:
    """Plan direct Callee Bindings and this action's Binding Hole fanouts."""

    def __init__(
        self,
        resolved_action: operation_graph_action_resolver.ResolvedAction,
        planned_actions: Mapping[ast.GlobalTypedName, ActionPlan],
        action_fragment_plans: _ActionFragmentPlans,
        action_executions: Iterable[operation_graph_model.ActionExecution],
        destruction_connections: Mapping[
            operation_graph_model.ResolvedCalleeDestroy,
            DestructionConnection,
        ],
    ):
        self._resolved_action = resolved_action
        self._planned_actions = planned_actions
        self._action_fragment_plans = action_fragment_plans
        self._action_executions = action_executions
        self._destruction_connections = destruction_connections

    def plan(self) -> _CalleeBindingPlans:
        """Plan direct Callee Bindings and Binding Hole fanouts."""
        by_callee_binding = self._plan_callee_bindings()
        binding_hole_fanouts = self._plan_binding_hole_fanouts(by_callee_binding)
        return _CalleeBindingPlans(
            by_callee_binding,
            binding_hole_fanouts,
        )

    def _plan_callee_bindings(self) -> _CalleeBindingPlansByCalleeBinding:
        callee_binding_plan_by_callee_binding: _CalleeBindingPlansByCalleeBinding = {}
        for execution in self._action_executions:
            resolved_action_execution = (
                self._resolved_action.resolved_execution_by_execution[execution]
            )
            for (
                callee_binding
            ) in resolved_action_execution.callee_bindings.with_runtime_consumers:
                callee_plan = self._planned_actions[
                    resolved_action_execution.execution.callee_action_name
                ]
                callee_fanout = callee_plan.binding_hole_fanouts[
                    callee_binding.callee_binding_hole
                ]
                callee_binding_plan = CalleeBindingPlan(
                    execution=resolved_action_execution.execution,
                    _callee_binding=callee_binding,
                    callee_fanout=callee_fanout,
                )
                callee_binding_plan_by_callee_binding[callee_binding] = (
                    callee_binding_plan
                )
                callee_destroy = (
                    callee_binding.callee_destroy_for_empty_or_fill_dependency
                )
                if callee_destroy is not None:
                    self._destruction_connections[callee_destroy].continuations.append(
                        callee_binding_plan
                    )
        for (
            callee_binding,
            callee_binding_plan,
        ) in callee_binding_plan_by_callee_binding.items():
            sole_caller_particle_operation = (
                callee_binding.sole_caller_particle_operation
            )
            for operation in callee_binding.caller_dependencies.local_operations:
                fragment = self._action_fragment_plans.fragment_for_operation[operation]
                if (
                    callee_binding_plan.requires_caller_method
                    or callee_binding_plan.has_inits
                ) and operation is sole_caller_particle_operation:
                    callee_binding_plan.place_after_local_operation(fragment)
                    continue
                callee_binding_plan.add_to(
                    fragment.inits,
                    fragment.fanout_continuations,
                )
        return callee_binding_plan_by_callee_binding

    def _plan_binding_hole_fanouts(
        self,
        callee_binding_plan_by_callee_binding: _CalleeBindingPlansByCalleeBinding,
    ) -> dict[
        operation_graph_action_resolver.ResolvedBindingHole,
        BindingHoleFanout,
    ]:
        binding_hole_fanout_by_binding_hole: dict[
            operation_graph_action_resolver.ResolvedBindingHole,
            BindingHoleFanout,
        ] = {}
        for binding_hole in self._resolved_action.binding_holes.with_runtime_consumers:
            binding_hole_fanout_by_binding_hole[binding_hole] = BindingHoleFanout(
                binding_hole
            )
        for operation in self._resolved_action.graph.particle_operations:
            fragment = self._action_fragment_plans.fragment_for_operation[operation]
            for binding_hole in self._resolved_action.binding_holes_depended_on_by(
                operation
            ):
                binding_hole_fanout = binding_hole_fanout_by_binding_hole[binding_hole]
                binding_hole_fanout.continuations.append(fragment)
                fragment.dependency_count += 1
                if binding_hole_fanout.join_is_assigned_by_caller:
                    fragment.caller_binding_hole = binding_hole
        for resolved_action_execution in self._resolved_action.action_executions:
            for (
                callee_binding
            ) in resolved_action_execution.callee_bindings.with_runtime_consumers:
                caller_binding_hole = callee_binding.caller_binding_hole
                if caller_binding_hole is None:
                    continue
                binding_hole_fanout = binding_hole_fanout_by_binding_hole[
                    caller_binding_hole
                ]
                callee_binding_plan_by_callee_binding[callee_binding].add_to(
                    binding_hole_fanout.inits,
                    binding_hole_fanout.continuations,
                )
        return binding_hole_fanout_by_binding_hole


@typing.final
class _ActionExecutionInitLocator:
    """Locate the init point for a transitive Action Execution."""

    def __init__(
        self,
        resolved_action: operation_graph_action_resolver.ResolvedAction,
        planned_actions: Mapping[ast.GlobalTypedName, ActionPlan],
        callee_binding_plan_by_callee_binding: _CalleeBindingPlansByCalleeBinding,
    ):
        self._resolved_action = resolved_action
        self._planned_actions = planned_actions
        self._callee_binding_plan_by_callee_binding = (
            callee_binding_plan_by_callee_binding
        )

    def callee_binding_plan(
        self,
        resolved_execution: operation_graph_action_resolver.ResolvedActionExecution,
        execution_path: tuple[operation_graph_model.ActionExecution, ...],
    ) -> CalleeBindingPlan | None:
        """Find the Callee Binding that inits an Action Execution path."""
        callee_plan = self._planned_actions[
            resolved_execution.execution.callee_action_name
        ]
        execution = execution_path[0]
        binding_hole = callee_plan.init_binding_hole_by_action_execution.get(execution)
        if binding_hole is None:
            return None
        fanout = callee_plan.binding_hole_fanouts[binding_hole]
        if not self.inits_include_execution_path(
            fanout.inits,
            execution_path,
        ):
            return None
        callee_binding = resolved_execution.callee_bindings[binding_hole]
        return self._callee_binding_plan_by_callee_binding[callee_binding]

    def inits_include_execution_path(
        self,
        inits: InitPlan,
        execution_path: tuple[operation_graph_model.ActionExecution, ...],
    ) -> bool:
        """Whether the inits construct every execution along one path."""
        execution = execution_path[0]
        inits_path = inits.contains(execution)
        if inits_path and len(execution_path) != 1:
            callee_plan = self._planned_actions[execution.callee_action_name]
            inits_path = self.inits_include_execution_path(
                callee_plan.creation_inits,
                execution_path[1:],
            )
        return inits_path


@typing.final
class _InitPlanner:
    """Plan runtime-state init and Guarantee consumption."""

    def __init__(
        self,
        resolved_action: operation_graph_action_resolver.ResolvedAction,
        resolved_actions: operation_graph_action_resolver.ResolvedActions,
        planned_actions: Mapping[ast.GlobalTypedName, ActionPlan],
        action_fragment_plans: _ActionFragmentPlans,
        callee_binding_plans: _CalleeBindingPlans,
        action_executions: Mapping[
            operation_graph_model.ActionExecution,
            ActionExecutionPlan,
        ],
        destruction_connections_by_guarantee: Mapping[
            operation_graph.ResolvedGuarantee,
            list[DestructionConnection],
        ],
        init_locator: _ActionExecutionInitLocator,
    ):
        self._resolved_action = resolved_action
        self._resolved_actions = resolved_actions
        self._planned_actions = planned_actions
        self._action_fragment_plans = action_fragment_plans
        self._callee_binding_plans = callee_binding_plans
        self._action_executions = action_executions
        self._destruction_connections_by_guarantee = (
            destruction_connections_by_guarantee
        )
        self._init_locator = init_locator

    def plan(self) -> _InitPlans:
        """Plan init and assign every Guarantee consumption."""
        (
            init_placements,
            guarantee_consumption_plans,
        ) = self._plan_action_execution_inits()
        assigned_consumption_plans = self._assign_guarantee_consumption_plans(
            guarantee_consumption_plans.values(),
        )
        # No empty BindingHoleFanout validation is needed: the resolver includes a
        # Binding Hole in with_runtime_consumers only because a Particle Operation,
        # Callee Binding, or Action Execution consumes it, and planning those
        # consumers populates its init or runnable fanout.
        return _InitPlans(
            init_placements.creation_inits,
            assigned_consumption_plans,
            init_placements.binding_hole_by_action_execution,
        )

    def _assign_guarantee_consumption_plans(
        self,
        guarantee_consumption_plans: Collection[GuaranteeConsumptionPlan],
    ) -> list[GuaranteeConsumptionPlan]:
        (
            guarantee_consumption_plans,
            post_init_consumption_plans,
        ) = self._plan_consumptions_after_guarantee_inits(guarantee_consumption_plans)
        assigned_consumption_plans: list[GuaranteeConsumptionPlan] = []
        for consumption_plan in guarantee_consumption_plans:
            assigned_consumption_plans.append(consumption_plan)
            execution_path = consumption_plan.guarantee.executions
            direct_execution = execution_path[0]
            planned_execution = self._action_executions[direct_execution]
            # A direct Action Execution exists before its own Action Guarantee can
            # publish, so its construction can register this consumption directly.
            if len(execution_path) == 1:
                planned_execution.guarantee_consumption_plans.append(consumption_plan)
                continue
            # A transitive Action Execution may not exist when its direct caller is
            # constructed, so registration must follow the init of its execution path.
            resolved_execution = self._resolved_action.resolved_execution_by_execution[
                direct_execution
            ]
            callee_plan = self._planned_actions[direct_execution.callee_action_name]
            nested_execution_path = execution_path[1:]
            # When the callee constructs the complete transitive path in its own
            # __init__, configuring the direct execution afterward is already safe.
            if self._init_locator.inits_include_execution_path(
                callee_plan.creation_inits,
                nested_execution_path,
            ):
                planned_execution.guarantee_consumption_plans.append(consumption_plan)
                continue
            init_plan = self._init_locator.callee_binding_plan(
                resolved_execution,
                nested_execution_path,
            )
            # Otherwise, a Callee Binding can construct the path later; register
            # immediately after that init, when every execution on the path exists.
            if init_plan is not None:
                init_plan.post_init_guarantee_consumption_plans.append(consumption_plan)
                continue
            # DLP 45 makes a direct caller resolve callee interface-position
            # particles; a deeper non-creation path cannot use this fallback.
            (nested_execution,) = nested_execution_path
            # DLP 45 guarantees that this remaining one-step path has an Action
            # Parent Guarantee, which is the only safe later init point.
            prerequisite_guarantee = typing.cast(
                "operation_graph.ResolvedGuarantee",
                self._resolved_actions.action_parent_guarantee_for_nested_execution(
                    direct_execution,
                    nested_execution,
                ),
            )
            planned_execution.deferred_guarantee_registrations.append(
                DeferredGuaranteeRegistration(
                    prerequisite_guarantee,
                    consumption_plan,
                )
            )
        for (
            execution,
            consumption_plans,
        ) in post_init_consumption_plans.items():
            self._action_executions[execution].guarantee_consumption_plans.extend(
                consumption_plans
            )
            assigned_consumption_plans.extend(consumption_plans)
        return assigned_consumption_plans

    @staticmethod
    def _plan_consumptions_after_guarantee_inits(
        guarantee_consumption_plans: Collection[GuaranteeConsumptionPlan],
    ) -> tuple[
        list[GuaranteeConsumptionPlan],
        dict[
            operation_graph_model.ActionExecution,
            list[GuaranteeConsumptionPlan],
        ],
    ]:
        """Place consumers whose bound methods need a Guarantee-initialized execution."""
        # Registering a bound Callee Binding method evaluates its Action Execution
        # member immediately, which is impossible before a Guarantee inits it.
        executions_with_guarantee_init: set[operation_graph_model.ActionExecution] = (
            set()
        )
        for consumption_plan in guarantee_consumption_plans:
            executions_with_guarantee_init.update(
                consumption_plan.inits.action_executions
            )
        consumption_plans_by_execution: dict[
            operation_graph_model.ActionExecution,
            list[GuaranteeConsumptionPlan],
        ] = {}
        retained_consumption_plans: list[GuaranteeConsumptionPlan] = []
        for consumption_plan in guarantee_consumption_plans:
            remaining_continuations: list[FanoutContinuation] = []
            consumption_plan_by_execution_with_guarantee_init: dict[
                operation_graph_model.ActionExecution,
                GuaranteeConsumptionPlan,
            ] = {}
            for continuation in consumption_plan.continuations:
                # Only a Callee Binding consumer can name a bound method on its
                # Action Execution; the other continuations are already
                # accessible from the current Action Execution.
                if (
                    not isinstance(continuation, CalleeBindingPlan)
                    or continuation.execution not in executions_with_guarantee_init
                ):
                    remaining_continuations.append(continuation)
                    continue
                post_init_consumption = (
                    consumption_plan_by_execution_with_guarantee_init.get(
                        continuation.execution
                    )
                )
                if post_init_consumption is None:
                    # Guarantee.publish completes all inits before reading its
                    # consumers, so the new execution can register its bound methods
                    # in time for that same publication to invoke them.
                    post_init_consumption = GuaranteeConsumptionPlan(
                        consumption_plan.guarantee
                    )
                    consumption_plan_by_execution_with_guarantee_init[
                        continuation.execution
                    ] = post_init_consumption
                    execution_consumption_plans = consumption_plans_by_execution.get(
                        continuation.execution
                    )
                    if execution_consumption_plans is None:
                        execution_consumption_plans = []
                        consumption_plans_by_execution[continuation.execution] = (
                            execution_consumption_plans
                        )
                    execution_consumption_plans.append(post_init_consumption)
                post_init_consumption.continuations.append(continuation)
            # Retaining these Callee Bindings here would evaluate their bound
            # methods before the Action Execution exists.
            consumption_plan.continuations[:] = remaining_continuations
            # Do not register a Guarantee consumption after all of its uses have
            # moved to the newly initialized Action Executions.
            if consumption_plan.inits.has_inits or remaining_continuations:
                retained_consumption_plans.append(consumption_plan)
        return retained_consumption_plans, consumption_plans_by_execution

    def _plan_action_execution_inits(
        self,
    ) -> tuple[
        _ActionExecutionInitPlacements,
        dict[operation_graph.ResolvedGuarantee, GuaranteeConsumptionPlan],
    ]:
        """Plan Action Execution init when its Action Parent becomes occupied."""
        # Every use of one resolved Guarantee must share a plan so its publication
        # performs all required inits before starting its fanout.
        guarantee_consumption_plans_by_guarantee: dict[
            operation_graph.ResolvedGuarantee,
            GuaranteeConsumptionPlan,
        ] = {}

        creation_inits = InitPlan()
        init_binding_hole_by_action_execution: dict[
            operation_graph_model.ActionExecution,
            operation_graph_action_resolver.ResolvedBindingHole,
        ] = {}
        # Construct each Action Execution at the event that makes its Action Parent
        # occupied, before any work that can use the execution begins.
        for action_execution in self._action_executions.values():
            execution = action_execution.execution
            resolved_execution = self._resolved_action.resolved_execution_by_execution[
                execution
            ]
            resolved_action_parent_last_operation = (
                resolved_execution.resolved_action_parent_last_operation
            )
            match resolved_action_parent_last_operation:
                case operation_graph_model.PositionOperationNode():
                    # The fragment performing the caller Particle Operation can init
                    # the execution before it starts the fragment's fanout.
                    inits = self._action_fragment_plans.fragment_for_operation[
                        resolved_action_parent_last_operation
                    ].inits
                case operation_graph.GuaranteePath():
                    # A callee Particle Operation is visible here through its Action
                    # Guarantee, so that publication must perform the init.
                    inits = self._guarantee_consumption_plan(
                        resolved_action_parent_last_operation,
                        guarantee_consumption_plans_by_guarantee,
                    ).inits
                case operation_graph_model.ActionParentLastOperationNode():
                    # The current execution is constructed only after its own Action
                    # Parent is occupied, so executions sharing that Action Parent can
                    # be constructed in the same __init__.
                    inits = creation_inits
                case _:
                    # A later caller determines when this Action Parent is occupied.
                    # Keep the init with that Binding Hole and retain the association
                    # so a transitive caller can configure the execution path.
                    init_binding_hole_by_action_execution[execution] = (
                        resolved_action_parent_last_operation
                    )
                    inits = self._callee_binding_plans.binding_hole_fanouts[
                        resolved_action_parent_last_operation
                    ].inits
            inits.append_action_execution(execution)
        # Guarantee-dependent fragments must start only after the same publication
        # has performed every Action Execution init recorded above.
        for planned_fragment in self._action_fragment_plans.fragments:
            for dependency in planned_fragment.guarantee_dependencies:
                self._guarantee_consumption_plan(
                    dependency,
                    guarantee_consumption_plans_by_guarantee,
                ).continuations.append(planned_fragment)
        # A Guarantee satisfying a Callee Binding may need to init the callee path
        # before invoking the Binding Hole, so both uses share one consumption plan.
        for (
            callee_binding_plan
        ) in self._callee_binding_plans.by_callee_binding.values():
            for dependency in callee_binding_plan.guarantee_dependencies:
                consumption_plan = self._guarantee_consumption_plan(
                    dependency,
                    guarantee_consumption_plans_by_guarantee,
                )
                callee_binding_plan.add_to(
                    consumption_plan.inits,
                    consumption_plan.continuations,
                )
        # A Destruction Connection cannot receive a Destructor Guarantee arrival
        # before the same Guarantee has initialized its Destructor execution.
        for (
            guarantee,
            connections,
        ) in self._destruction_connections_by_guarantee.items():
            self._guarantee_consumption_plan(
                guarantee,
                guarantee_consumption_plans_by_guarantee,
            ).continuations.extend(connections)
        # The other init placements live on their fragments, Guarantee plans, or
        # Binding Hole fanouts; only these standalone results need to be returned.
        return (
            _ActionExecutionInitPlacements(
                creation_inits,
                init_binding_hole_by_action_execution,
            ),
            guarantee_consumption_plans_by_guarantee,
        )

    @staticmethod
    def _guarantee_consumption_plan(
        guarantee: operation_graph.ResolvedGuarantee,
        plans_by_guarantee: dict[
            operation_graph.ResolvedGuarantee,
            GuaranteeConsumptionPlan,
        ],
    ) -> GuaranteeConsumptionPlan:
        consumption_plan = plans_by_guarantee.get(guarantee)
        if consumption_plan is None:
            consumption_plan = GuaranteeConsumptionPlan(guarantee)
            plans_by_guarantee[guarantee] = consumption_plan
        return consumption_plan


@typing.final
class _CallerResolvedJoinPlanner:
    """Plan Joins whose realized predecessors depend on an action's caller."""

    def __init__(
        self,
        resolved_action: operation_graph_action_resolver.ResolvedAction,
        planned_actions: Mapping[ast.GlobalTypedName, ActionPlan],
        action_fragment_plans: _ActionFragmentPlans,
        callee_binding_plans: _CalleeBindingPlans,
        action_executions: Mapping[
            operation_graph_model.ActionExecution,
            ActionExecutionPlan,
        ],
        init_locator: _ActionExecutionInitLocator,
    ):
        self._resolved_action = resolved_action
        self._planned_actions = planned_actions
        self._action_fragment_plans = action_fragment_plans
        self._callee_binding_plans = callee_binding_plans
        self._action_executions = action_executions
        self._init_locator = init_locator

    def plan(self) -> list[CallerResolvedJoin]:
        """Plan this action's caller-resolved Joins and callee assignments."""
        caller_resolved_joins = self._plan_callee_caller_resolved_joins()
        caller_resolved_joins.extend(self._binding_hole_caller_resolved_joins())
        caller_resolved_joins.extend(self._fragment_caller_resolved_joins())
        caller_resolved_joins.extend(self._callee_binding_caller_resolved_joins())
        return caller_resolved_joins

    def _plan_callee_caller_resolved_joins(self) -> list[CallerResolvedJoin]:
        caller_resolved_joins: list[CallerResolvedJoin] = []
        for action_execution in self._action_executions.values():
            execution = action_execution.execution
            callee_plan = self._planned_actions[execution.callee_action_name]
            resolved_execution = self._resolved_action.resolved_execution_by_execution[
                execution
            ]
            for caller_resolved_join in callee_plan.caller_resolved_joins:
                propagated_join = self._plan_callee_caller_resolved_join(
                    action_execution,
                    resolved_execution,
                    caller_resolved_join,
                )
                if propagated_join is not None:
                    caller_resolved_joins.append(propagated_join)
        return caller_resolved_joins

    def _plan_callee_caller_resolved_join(
        self,
        action_execution: ActionExecutionPlan,
        resolved_execution: operation_graph_action_resolver.ResolvedActionExecution,
        caller_resolved_join: CallerResolvedJoin,
    ) -> CallerResolvedJoin | None:
        fixed_dependency_count = caller_resolved_join.fixed_dependency_count
        resolves_direct_binding_hole = bool(
            isinstance(caller_resolved_join.target, BindingHoleFanout)
            and not caller_resolved_join.execution_path
        )
        binding_hole = caller_resolved_join.caller_binding_hole
        callee_binding = resolved_execution.callee_bindings[binding_hole]
        propagated_binding_hole = None
        if resolves_direct_binding_hole:
            callee_binding_plan = self._callee_binding_plans.by_callee_binding[
                callee_binding
            ]
            if callee_binding_plan.requires_caller_method:
                fixed_dependency_count += 1
            else:
                fixed_dependency_count += callee_binding.concrete_dependency_count
                propagated_binding_hole = callee_binding.caller_binding_hole
        elif callee_binding.concrete_dependency_count:
            fixed_dependency_count += 1
        else:
            propagated_binding_hole = callee_binding.caller_binding_hole
        execution_path = (
            action_execution.execution,
            *caller_resolved_join.execution_path,
        )
        if propagated_binding_hole is not None:
            return CallerResolvedJoin(
                execution_path,
                caller_resolved_join.target,
                fixed_dependency_count,
                propagated_binding_hole,
            )
        self._assign_callee_join(
            action_execution,
            resolved_execution,
            CalleeJoinAssignment(
                execution_path,
                caller_resolved_join.target,
                fixed_dependency_count,
            ),
        )
        return None

    def _assign_callee_join(
        self,
        action_execution: ActionExecutionPlan,
        resolved_execution: operation_graph_action_resolver.ResolvedActionExecution,
        assignment: CalleeJoinAssignment,
    ):
        if len(assignment.execution_path) == 1:
            action_execution.callee_join_assignments.append(assignment)
            return
        init_plan = self._init_locator.callee_binding_plan(
            resolved_execution,
            assignment.execution_path[1:],
        )
        if init_plan is None:
            action_execution.callee_join_assignments.append(assignment)
            return
        init_plan.post_init_join_assignments.append(assignment)

    def _binding_hole_caller_resolved_joins(self) -> list[CallerResolvedJoin]:
        caller_resolved_joins: list[CallerResolvedJoin] = []
        for fanout in self._callee_binding_plans.binding_hole_fanouts.values():
            if not fanout.join_is_assigned_by_caller:
                continue
            caller_resolved_joins.append(
                CallerResolvedJoin(
                    (),
                    fanout,
                    0,
                    fanout.binding_hole,
                )
            )
        return caller_resolved_joins

    def _fragment_caller_resolved_joins(self) -> list[CallerResolvedJoin]:
        caller_resolved_joins: list[CallerResolvedJoin] = []
        for fragment in self._action_fragment_plans.fragments:
            caller_binding_hole = fragment.caller_binding_hole
            if caller_binding_hole is None:
                continue
            caller_resolved_joins.append(
                CallerResolvedJoin(
                    (),
                    fragment,
                    fragment.fixed_dependency_count,
                    caller_binding_hole,
                )
            )
        return caller_resolved_joins

    def _callee_binding_caller_resolved_joins(self) -> list[CallerResolvedJoin]:
        caller_resolved_joins: list[CallerResolvedJoin] = []
        for (
            callee_binding_plan
        ) in self._callee_binding_plans.by_callee_binding.values():
            caller_binding_hole = callee_binding_plan.caller_binding_hole
            if not (
                callee_binding_plan.requires_caller_method
                and callee_binding_plan.join_is_assigned_by_caller
                and caller_binding_hole is not None
            ):
                continue
            caller_resolved_joins.append(
                CallerResolvedJoin(
                    (),
                    callee_binding_plan,
                    callee_binding_plan.fixed_dependency_count,
                    caller_binding_hole,
                )
            )
        return caller_resolved_joins


@typing.final
class _ActionPlanBuilder:
    """Coordinate construction of one reusable Action Plan."""

    def __init__(
        self,
        resolved_action: operation_graph_action_resolver.ResolvedAction,
        planned_actions: Mapping[ast.GlobalTypedName, ActionPlan],
        resolved_actions: operation_graph_action_resolver.ResolvedActions,
    ):
        self._resolved_action = resolved_action
        self._planned_actions = planned_actions
        self._resolved_actions = resolved_actions

    def build(self) -> ActionPlan:
        """Build the action's reusable execution plan."""
        action_fragment_plans = _ActionFragmentPlanner(self._resolved_action).plan()
        destruction_connection_plans = _DestructionConnectionPlanner(
            self._resolved_action,
            action_fragment_plans.fragment_for_operation,
        ).plan()
        action_executions = self._plan_action_executions(
            destruction_connection_plans,
        )
        callee_binding_plans = _CalleeBindingPlanner(
            self._resolved_action,
            self._planned_actions,
            action_fragment_plans,
            action_executions,
            destruction_connection_plans.destruction_connection_by_callee_destroy,
        ).plan()
        init_locator = _ActionExecutionInitLocator(
            self._resolved_action,
            self._planned_actions,
            callee_binding_plans.by_callee_binding,
        )
        init_plans = _InitPlanner(
            self._resolved_action,
            self._resolved_actions,
            self._planned_actions,
            action_fragment_plans,
            callee_binding_plans,
            action_executions,
            destruction_connection_plans.connections_by_guarantee,
            init_locator,
        ).plan()
        caller_resolved_joins = _CallerResolvedJoinPlanner(
            self._resolved_action,
            self._planned_actions,
            action_fragment_plans,
            callee_binding_plans,
            action_executions,
            init_locator,
        ).plan()
        for callee_binding_plan in callee_binding_plans.by_callee_binding.values():
            callee_binding_plan.finalize_init()
        return ActionPlan(
            fragments=action_fragment_plans.fragments,
            binding_hole_fanouts=callee_binding_plans.binding_hole_fanouts,
            action_executions=action_executions,
            creation_inits=init_plans.creation_inits,
            callee_binding_method_plans=callee_binding_plans.caller_method_plans,
            guarantee_consumption_plans=init_plans.guarantee_consumption_plans,
            init_binding_hole_by_action_execution=(
                init_plans.init_binding_hole_by_action_execution
            ),
            caller_resolved_joins=caller_resolved_joins,
            accepts_destruction_connections=(
                self._resolved_action.graph.propagates_destruction_facts
            ),
            destruction_connection_by_operation=(
                destruction_connection_plans.destruction_connection_by_operation
            ),
        )

    def _plan_action_executions(
        self,
        destruction_connection_plans: _DestructionConnectionPlans,
    ) -> dict[operation_graph_model.ActionExecution, ActionExecutionPlan]:
        action_execution_by_execution: dict[
            operation_graph_model.ActionExecution,
            ActionExecutionPlan,
        ] = {}
        for resolved_execution in self._resolved_action.action_executions:
            execution = resolved_execution.execution
            action_execution_by_execution[execution] = ActionExecutionPlan(
                execution=execution,
                created_destruction_connections=(
                    destruction_connection_plans.created_connections_by_execution.get(
                        execution,
                        [],
                    )
                ),
                forwards_destruction_connections=(
                    resolved_execution.forwards_destruction_connections
                ),
            )
        for (
            execution,
            destroying_execution,
        ) in destruction_connection_plans.contributed_destructor_destroying_execution_by_execution.items():
            action_execution_by_execution[execution] = (
                ContributedDestructorActionExecutionPlan(
                    execution=execution,
                    destroying_action_execution=destroying_execution,
                )
            )
        return action_execution_by_execution


@typing.final
class ActionPlans:
    """Build action plans in direct-callee-first definition order."""

    def __init__(
        self,
        operation_graphs: operation_graph.OperationGraphs,
    ):
        """Init with the validated operation graphs."""
        self._resolved_actions = operation_graph_action_resolver.ResolvedActions(
            operation_graphs
        )
        self._plans: typed_name_dict.TypedNameDict[ast.GlobalTypedName, ActionPlan] = (
            typed_name_dict.TypedNameDict()
        )

    def plan_for(self, definition: ast.ActionDefinition) -> ActionPlan:
        """Build the plan for an action.

        Yuu must have already requested the plan of all callees beforehand.

        Args:
            definition: The validated action definition to plan. Every direct
                callee must already have been planned.
        """
        resolved_action = self._resolved_actions.resolve(definition.typed_name)
        builder = _ActionPlanBuilder(
            resolved_action,
            self._plans,
            self._resolved_actions,
        )
        plan = builder.build()
        self._plans[definition.typed_name] = plan
        return plan
