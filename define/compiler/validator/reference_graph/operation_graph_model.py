"""Data structures shared by operation-graph construction and action contracts.

There are two general types of nodes in an operation graph:

* Concrete Nodes: these represent actual particle operations executed within
  an action. This is any create, move, destroy, or guarantee.
* Abstract Nodes: These are Binding Holes represented by Operation Nodes. For
  example: RequirementNode or ActionParentLastOperationNode.

There is also a broader type of abstract "node" that includes bundles of resolved
and unresolved dependencies for propagation during action resolution, such as
EmptyRuleBindingHole. Broadly, we call these (including the Abstract Nodes)
"Binding Holes" because they would be "filled in" by concrete nodes in the caller
if we built a whole-program operation graph.
"""

from __future__ import annotations

import abc
import enum
import typing
from dataclasses import dataclass, field

from define.compiler import ast

if typing.TYPE_CHECKING:
    from collections.abc import Collection, Iterable, Sequence


class PositionOccupancyState(enum.Enum):
    """The occupancy state of an interface position."""

    EMPTY = enum.auto()
    OCCUPIED = enum.auto()
    ERROR = enum.auto()


@dataclass(frozen=True, slots=True)
class OperationGraphRequirement:
    """A caller-controlled position and the state an action requires."""

    requirement_position: tuple[str, ...]
    required_state: PositionOccupancyState


@dataclass(frozen=True, slots=True, eq=False)
class DestructionFact:
    """Identifies one destruction initiated by its destroying action and propagated through callers."""

    destroyed_position_in_destroyer: ast.PositionReference
    destroying_action: ast.GlobalTypedName


type ConcreteOperationNode = PositionOperationNode | GuaranteeNode
type LastOperationNode = ConcreteOperationNode | RequirementNode
type ActionParentOperationNode = ActionParentLastOperationNode | LastOperationNode
type EmptyRuleDependencyNode = LastOperationNode | EmptyRuleBindingHoleNode
type AbstractOperationNode = (
    ActionParentLastOperationNode | RequirementNode | EmptyRuleBindingHoleNode
)
type BindingHole = AbstractOperationNode | EmptyRuleBindingHole | MoveRuleBindingHole
type PositionOperationDependsOnNode = (
    ActionParentLastOperationNode
    | PositionOperationNode
    | DestructionContributionNode
    | GuaranteeNode
    | RequirementNode
    | EmptyRuleBindingHoleNode
)
type PrecedingChildOperations = Iterable[tuple[tuple[str, ...], ConcreteOperationNode]]


@dataclass(frozen=True, slots=True)
class ChildOperation:
    """A caller operation on a transitive child position of a required position."""

    # The child position relative to the required position.
    child_position: tuple[str, ...]
    # The operation node in the caller's graph.
    operation: ConcreteOperationNode


@dataclass(frozen=True, slots=True)
class ParticleChildOperations:
    """Operations on the child positions of one particle.

    Persistent values are construction-time snapshots of operations that may
    become predecessors of a later operation that empties the particle.
    Operations are ordered from most recent to least recent.
    """

    operations: Sequence[ChildOperation] = ()

    @classmethod
    def from_preceding_operations(
        cls, preceding_operations: PrecedingChildOperations
    ) -> ParticleChildOperations:
        """Create a snapshot from preceding operations on child positions."""
        operations: list[ChildOperation] = []
        operation_positions: set[tuple[str, ...]] = set()
        operation_position_prefixes: set[tuple[str, ...]] = set()
        for child_position, operation in sorted(
            preceding_operations,
            key=lambda item: item[1].operation_order,
            reverse=True,
        ):
            if (
                child_position in operation_positions
                or child_position in operation_position_prefixes
            ):
                continue
            has_operation_on_parent_position = any(
                child_position[:depth] in operation_positions
                for depth in range(1, len(child_position))
            )
            if has_operation_on_parent_position:
                continue
            operations.append(ChildOperation(child_position, operation))
            operation_positions.add(child_position)
            operation_position_prefixes.update(
                child_position[:depth] for depth in range(1, len(child_position))
            )
        return cls(tuple(operations))

    def partition_for_child_positions_without_parent_child_relationships(
        self, child_positions: Collection[tuple[str, ...]]
    ) -> dict[tuple[str, ...], ParticleChildOperations]:
        """Partition matching operations among positions where none is a parent of another."""
        operations_by_position: dict[tuple[str, ...], list[ChildOperation]] = {}
        for position in child_positions:
            operations_by_position[position] = []
        for child_operation in self.operations:
            operation_position = child_operation.child_position
            for depth in range(1, len(operation_position) + 1):
                position = operation_position[:depth]
                operations = operations_by_position.get(position)
                if operations is None:
                    continue
                relative_position = operation_position[depth:]
                if relative_position:
                    operations.append(
                        ChildOperation(relative_position, child_operation.operation)
                    )
                break
        snapshots: dict[tuple[str, ...], ParticleChildOperations] = {}
        for position, operations in operations_by_position.items():
            snapshots[position] = ParticleChildOperations(operations)
        return snapshots

    def all_precede(self, operation: MoveNode) -> bool:
        """Return whether every child operation precedes ``operation``."""
        return not self.operations or (
            self.operations[0].operation.operation_order < operation.operation_order
        )

    def child_position_set(self) -> frozenset[tuple[str, ...]]:
        """Return the relative child positions with preceding operations."""
        return frozenset(operation.child_position for operation in self.operations)


# Separate propagation paths can require distinct Binding Holes with identical
# Empty Rule Collection data, so these values use identity when codegen keys
# Binding Hole methods.
@dataclass(frozen=True, slots=True, eq=False)
class CallerEmptyRuleCollection:
    """The Empty Rule's Collection awaiting an earlier caller.

    ``collected_child_operation_positions`` are relative to the required particle.
    ``fill_dependency_requirement_position`` identifies a Fill Dependency that
    still awaits caller substitution.
    """

    requirement_position: tuple[str, ...]
    collected_child_operation_positions: frozenset[tuple[str, ...]]
    fill_dependency_requirement_position: tuple[str, ...] | None
    collected_operation_positions: tuple[tuple[str, ...], ...]


@dataclass(frozen=True, slots=True, eq=False)
class EmptyRuleBindingHole(CallerEmptyRuleCollection):
    """An unfinished Empty Rule application awaiting an earlier caller.

    ``prerequisite_binding_holes`` identifies the callee Binding Holes that must
    be bound before this Binding Hole.
    """

    prerequisite_binding_holes: tuple[BindingHole, ...]

    @classmethod
    def from_collection(
        cls,
        collection: CallerEmptyRuleCollection,
        prerequisite_binding_holes: tuple[BindingHole, ...],
    ) -> typing.Self:
        """Create a Binding Hole with its prerequisite Binding Holes."""
        return cls(
            requirement_position=collection.requirement_position,
            collected_child_operation_positions=(
                collection.collected_child_operation_positions
            ),
            fill_dependency_requirement_position=(
                collection.fill_dependency_requirement_position
            ),
            collected_operation_positions=collection.collected_operation_positions,
            prerequisite_binding_holes=prerequisite_binding_holes,
        )


@dataclass(slots=True)
class EmptyRuleBindingInputs:
    """Caller-side values needed to bind one Empty Rule Binding Hole."""

    concrete_caller_nodes: list[ConcreteOperationNode] = field(default_factory=list)
    caller_binding_holes: list[BindingHole] = field(default_factory=list)

    def add_inputs(
        self,
        concrete_caller_nodes: Iterable[ConcreteOperationNode],
        caller_binding_holes: Iterable[BindingHole],
    ):
        """Add caller-side values from one prerequisite binding."""
        self.concrete_caller_nodes.extend(concrete_caller_nodes)
        self.caller_binding_holes.extend(caller_binding_holes)


@dataclass(frozen=True, slots=True)
class EmptyOrMoveRuleResult:
    """Locally selected nodes and a Collection awaiting a caller."""

    local_nodes: list[ConcreteOperationNode]
    caller_collection: CallerEmptyRuleCollection | None
    partial_move_rule_comparison_positions: tuple[tuple[str, ...], ...] | None
    fill_dependency_is_also_empty_dependency: bool


@dataclass(frozen=True, slots=True)
class EmptyRuleApplicationResult:
    """The result of binding an Empty Rule Binding Hole in one caller."""

    caller_nodes: list[LastOperationNode]
    empty_rule_binding_hole: EmptyRuleBindingHole | None


@dataclass(frozen=True, slots=True)
class PartialMoveRuleResult(abc.ABC):
    """Facts retained after applying every locally decidable part of a Move Rule."""

    fill_dependency: LastOperationNode | None
    fill_dependency_is_also_empty_dependency: bool

    @property
    def caller_empty_rule_collection(self) -> CallerEmptyRuleCollection | None:
        """Return the unresolved Empty Rule Collection, when one remains."""
        return None

    @property
    @abc.abstractmethod
    def comparison_positions(self) -> tuple[tuple[str, ...], ...]:
        """Return every position already established for Comparison."""


@dataclass(frozen=True, slots=True)
class PartialMoveRuleResultWithCallerEmptyRuleCollection(PartialMoveRuleResult):
    """A partial Move Rule whose Empty Rule Collection requires a caller."""

    empty_rule_collection: CallerEmptyRuleCollection

    @property
    @typing.override
    def caller_empty_rule_collection(self) -> CallerEmptyRuleCollection:
        """Return the unresolved Empty Rule Collection."""
        return self.empty_rule_collection

    @property
    @typing.override
    def comparison_positions(self) -> tuple[tuple[str, ...], ...]:
        """Return every position already established for Comparison."""
        return self.empty_rule_collection.collected_operation_positions


@dataclass(frozen=True, slots=True)
class PartialMoveRuleResultWithCompleteEmptyRuleCollection(PartialMoveRuleResult):
    """A partial Move Rule whose Empty Rule Collection is complete."""

    collected_operation_positions: tuple[tuple[str, ...], ...]

    @property
    @typing.override
    def comparison_positions(self) -> tuple[tuple[str, ...], ...]:
        """Return every position already established for Comparison."""
        return self.collected_operation_positions


@dataclass(frozen=True, slots=True, eq=False)
class CallerFillDependency:
    """A Fill Dependency whose Particle Operation must be supplied by a caller."""

    callee_binding_hole: ActionParentLastOperationNode | RequirementNode
    requirement: OperationGraphRequirement


@dataclass(frozen=True, slots=True, eq=False)
class MoveRuleBindingHole(abc.ABC):
    """An unfinished Move Rule application awaiting one direct caller."""

    caller_fill_dependency: CallerFillDependency | None
    fill_dependency_is_also_empty_dependency: bool
    prerequisite_binding_holes: tuple[BindingHole, ...]

    @property
    def caller_empty_rule_collection(self) -> CallerEmptyRuleCollection | None:
        """Return the unresolved Empty Rule Collection, when one remains."""
        return None

    @property
    @abc.abstractmethod
    def comparison_positions(self) -> tuple[tuple[str, ...], ...]:
        """Return every position already established for Comparison."""


@dataclass(frozen=True, slots=True, eq=False)
class MoveRuleBindingHoleWithCallerEmptyRuleCollection(MoveRuleBindingHole):
    """A Move Rule Binding Hole whose Empty Rule Collection remains unfinished."""

    empty_rule_collection: CallerEmptyRuleCollection

    @property
    @typing.override
    def caller_empty_rule_collection(self) -> CallerEmptyRuleCollection:
        """Return the unresolved Empty Rule Collection."""
        return self.empty_rule_collection

    @property
    @typing.override
    def comparison_positions(self) -> tuple[tuple[str, ...], ...]:
        """Return every position already established for Comparison."""
        return self.empty_rule_collection.collected_operation_positions


@dataclass(frozen=True, slots=True, eq=False)
class MoveRuleBindingHoleWithCompleteEmptyRuleCollection(MoveRuleBindingHole):
    """A Move Rule Binding Hole whose Empty Rule Collection is complete."""

    collected_operation_positions: tuple[tuple[str, ...], ...]

    @property
    @typing.override
    def comparison_positions(self) -> tuple[tuple[str, ...], ...]:
        """Return every position already established for Comparison."""
        return self.collected_operation_positions


@dataclass(frozen=True, slots=True)
class MoveRuleApplicationResult:
    """The result of binding one Move Rule Binding Hole in a direct caller."""

    concrete_caller_nodes: Sequence[ConcreteOperationNode]
    move_rule_binding_hole: MoveRuleBindingHole | None


@dataclass(frozen=True, slots=True)
class RequirementSatisfaction:
    """The caller dependencies that satisfy one requirement of a triggered callee."""

    # The operation or RequirementNode that put the position in its required
    # state from the caller's perspective.
    operation: LastOperationNode
    child_operations: ParticleChildOperations


@dataclass(frozen=True, slots=True, eq=False)
class ActionExecution:
    """One Action Execution and what satisfies each requirement of the callee.

    Recorded from the caller's side, at the moment it triggers, because only the
    caller knows what it did to the positions the callee names.
    """

    # The action reference run by this Action Execution, from the caller's perspective.
    callee: ast.ActionReference
    # The operation that triggered the callee.
    trigger_operation: LastOperationNode
    # What satisfies each requirement of the callee, by the callee's own key for
    # that requirement.
    requirement_satisfactions: dict[tuple[str, ...], RequirementSatisfaction]
    # The last operation on the callee action's parent position or one of that
    # position's transitive parent positions.
    action_parent_last_operation: ActionParentOperationNode = field(kw_only=True)

    @property
    def callee_action_name(self) -> ast.GlobalTypedNameReference:
        """Return the final action in the reference."""
        return self.callee.get_last_action()

    @property
    def action_chain(self) -> tuple[str, ...]:
        """Return the caller's chained name for the triggered action."""
        return self.callee.canonical_chained_name_tuple

    @property
    def destructor_trigger_requirement(self) -> RequirementNode | None:
        """Return the Requirement that triggers a destructor Action Execution."""
        if isinstance(self.trigger_operation, RequirementNode):
            return self.trigger_operation
        return None

    def caller_operation_for_callee_binding_hole(
        self,
        callee_binding_hole: ActionParentLastOperationNode | RequirementNode,
    ) -> ActionParentOperationNode:
        """Return the caller operation for one direct callee Binding Hole."""
        if isinstance(callee_binding_hole, ActionParentLastOperationNode):
            return self.action_parent_last_operation
        requirement_satisfaction = self.requirement_satisfactions.get(
            callee_binding_hole.requirement.requirement_position
        )
        if requirement_satisfaction is not None:
            return requirement_satisfaction.operation

        # Position Requirements form a chain through parent names, so this node has
        # exactly one direct dependency: the nearest parent-name requirement, or
        # the action parent's last operation when there is no parent-name
        # requirement.
        (parent_binding_hole,) = callee_binding_hole.depends_on
        if isinstance(parent_binding_hole, ActionParentLastOperationNode):
            return self.action_parent_last_operation
        return self.requirement_satisfactions[
            parent_binding_hole.requirement.requirement_position
        ].operation

    def resolve_move_rule_fill_dependency(
        self,
        caller_fill_dependency: CallerFillDependency,
    ) -> ConcreteOperationNode | CallerFillDependency:
        """Resolve a Fill Dependency through one direct Action Execution."""
        fill_dependency = self.caller_operation_for_callee_binding_hole(
            caller_fill_dependency.callee_binding_hole
        )
        if isinstance(fill_dependency, (PositionOperationNode, GuaranteeNode)):
            return fill_dependency
        return CallerFillDependency(
            callee_binding_hole=fill_dependency,
            requirement=OperationGraphRequirement(
                requirement_position=ast.chain_in_caller(
                    self.action_chain,
                    caller_fill_dependency.requirement.requirement_position,
                ),
                required_state=caller_fill_dependency.requirement.required_state,
            ),
        )


# A node_id is unique only within one graph, so nodes use identity equality and
# hashing when they appear in sets and mappings. A node_id is normally also the
# operation's order. Conditional destructions added after validation override
# that through operation_order, so only operation_order should be used to determine
# the order of operations. Every dataclass subclass must repeat eq=False because
# dataclass decorator options are not inherited.
@dataclass(frozen=True, slots=True, kw_only=True, eq=False)
class OperationNode(abc.ABC):
    """One operation in an action's dependency graph."""

    _is_guarantee_or_has_partial_move_rule_result: typing.ClassVar[bool] = False

    node_id: int
    # The operations this node directly depends on (the operations that must
    # complete before it).
    depends_on: tuple[OperationNode, ...]
    operation_order: tuple[int, int, int] = field(init=False, repr=False)
    depends_on_path_contains_guarantee_or_partial_move_rule: bool = field(
        init=False,
        repr=False,
    )

    def __post_init__(self):
        """Set fields derived from the node's identity and ``depends_on`` paths."""
        object.__setattr__(self, "operation_order", (self.node_id, 1, 0))
        object.__setattr__(
            self,
            "depends_on_path_contains_guarantee_or_partial_move_rule",
            self._is_guarantee_or_has_partial_move_rule_result
            or any(
                dependency.depends_on_path_contains_guarantee_or_partial_move_rule
                for dependency in self.depends_on
            ),
        )

    @property
    def operated_positions(self) -> tuple[tuple[str, ...], ...]:
        """Every position operated on by this node."""
        return ()


@dataclass(frozen=True, slots=True, kw_only=True, eq=False)
class ActionParentLastOperationNode(OperationNode):
    """The caller's last operation on this action's parent position or its transitive parents."""

    depends_on: tuple[()] = ()


@dataclass(frozen=True, slots=True, kw_only=True, eq=False)
class PositionOperationNode(OperationNode):
    """An operation the body performs on a written position."""

    depends_on: tuple[PositionOperationDependsOnNode, ...]
    # The position reference as written (the statement target).
    target: ast.PositionReference

    @property
    @typing.override
    def operated_positions(self) -> tuple[tuple[str, ...], ...]:
        """Every position operated on by this node."""
        return (self.target.canonical_chained_name_tuple,)


@dataclass(frozen=True, slots=True, kw_only=True, eq=False)
class CreateNode(PositionOperationNode):
    """A body create in ``target``."""


@dataclass(frozen=True, slots=True, kw_only=True, eq=False)
class MoveNode(PositionOperationNode):
    """A body move of a particle from ``source`` to ``target``."""

    source: ast.PositionReference

    @property
    @typing.override
    def operated_positions(self) -> tuple[tuple[str, ...], ...]:
        """Every position operated on by this node."""
        return (
            self.source.canonical_chained_name_tuple,
            self.target.canonical_chained_name_tuple,
        )


@dataclass(frozen=True, slots=True, kw_only=True, eq=False)
class MoveNodeWithPartialMoveRuleResult(MoveNode):
    """A Move whose rule still requires facts from a direct callee or caller."""

    _is_guarantee_or_has_partial_move_rule_result: typing.ClassVar[bool] = True

    depends_on: tuple[ConcreteOperationNode, ...]
    partial_move_rule_result: PartialMoveRuleResult


@dataclass(frozen=True, slots=True, kw_only=True, eq=False)
class DestroyNode(PositionOperationNode):
    """A destroy of the particle in ``target``."""


@dataclass(frozen=True, slots=True, kw_only=True, eq=False)
class DestructionFactDestroyNode(DestroyNode):
    """A Destroy performed as part of one Destruction Fact."""

    destruction_fact: DestructionFact
    destruction_position: tuple[str, ...]
    dependencies_before_caller_contribution: tuple[EmptyRuleDependencyNode, ...]
    dependencies_after_caller_contribution: tuple[ConcreteOperationNode, ...]


@dataclass(frozen=True, slots=True, kw_only=True, eq=False)
class DestructionFragmentDestroyNode(DestructionFactDestroyNode):
    """An ordinary Destroy contributed by a direct caller."""

    direct_callee_execution: ActionExecution
    target_in_destroying_action: ast.PositionReference


@dataclass(frozen=True, slots=True)
class DestructionOperation:
    """A Destruction Fact Destroy and the action whose graph contains it."""

    action: ast.GlobalTypedName = field(compare=False)
    operation: DestructionFactDestroyNode


@dataclass(frozen=True, slots=True)
class ResolvedCalleeDestroy:
    """A Destroy resolved through one direct callee Action Execution."""

    direct_callee_execution: ActionExecution
    callee_destroy: DestructionOperation


@dataclass(slots=True)
class DestructionContribution:
    """Caller-contributed work for one direct callee Destroy."""

    operations: dict[DestructionFragmentDestroyNode, None] = field(default_factory=dict)
    first_operations: dict[DestructionFragmentDestroyNode, None] = field(
        default_factory=dict
    )
    completion_operations: dict[DestructionFragmentDestroyNode, None] = field(
        default_factory=dict
    )
    destructors: list[ActionExecution] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class CalleeDestroy:
    """A direct callee Destroy identified from its caller's Operation Graph."""

    direct_callee_execution: ActionExecution
    destruction_fact: DestructionFact
    callee_destroy_position: tuple[str, ...]


@dataclass(frozen=True, slots=True, kw_only=True, eq=False)
class DestructionContributionNode(OperationNode):
    """Connects preceding caller operations to the first Destroy in one contribution."""

    depends_on: tuple[EmptyRuleDependencyNode, ...]
    callee_destroy: CalleeDestroy


@dataclass(frozen=True, slots=True, kw_only=True, eq=False)
class DestructionContractDestructorContribution:
    """A caller-verified Destructor contributed to one Destruction Fact."""

    destructor_execution: ActionExecution
    callee_destroy: CalleeDestroy


@dataclass(frozen=True, slots=True, eq=False)
class ContributedDestructionPosition:
    """One caller-known occupied position contributed to a destruction."""

    position: ast.PositionReference
    position_relative_to_destroyed_particle: tuple[str, ...]
    callee_destroy_position_relative_to_destroyed_particle: tuple[str, ...]
    # Retaining the contributed child positions preserves the Destroys that must
    # precede this position's Destroy without reconstructing name relationships.
    preceding_contributed_positions: tuple[ContributedDestructionPosition, ...]


@dataclass(frozen=True, slots=True)
class VerifiedDestructionContractDestructor:
    """A caller-verified Destructor to contribute through a Destruction Contract."""

    action: ast.ActionReference
    position: ast.PositionReference
    position_relative_to_destroyed_particle: tuple[str, ...]
    callee_destroy_position_relative_to_destroyed_particle: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class DestructionContractContribution:
    """Caller-known work for one Destruction Contract."""

    destruction_fact: DestructionFact
    destroyed_particle_position: ast.PositionReference
    destroyed_position_in_destroying_action: ast.PositionReference
    children: Sequence[ContributedDestructionPosition]
    # Retaining the final contributed positions preserves the Destroys that finish
    # their contributions before the callee Destroy without another traversal.
    final_contributed_positions: Sequence[ContributedDestructionPosition]
    is_propagated_to_caller: bool
    destructors: Sequence[VerifiedDestructionContractDestructor]


@dataclass(frozen=True, slots=True)
class ContributedDestruction:
    """Ordinary Destroy operations contributed before one callee Destroy."""

    contribution_node: DestructionContributionNode
    operations: tuple[DestructionFragmentDestroyNode, ...]
    completion_operations: tuple[DestructionFragmentDestroyNode, ...]


@dataclass(frozen=True, slots=True)
class ContributedDestructionFragment:
    """Work from one Destruction Contract contributed around an Action Execution."""

    operations: tuple[DestructionFragmentDestroyNode, ...]
    contributed_destructions: tuple[ContributedDestruction, ...]
    destructors: tuple[DestructionContractDestructorContribution, ...]


@dataclass(slots=True, eq=False)
class OperationGraphDestruction:
    """One Destruction Fact and its relationships in an Operation Graph."""

    operations_by_position: dict[tuple[str, ...], DestructionFactDestroyNode] = field(
        init=False, default_factory=dict
    )
    direct_callee_execution: ActionExecution | None = field(init=False, default=None)
    is_propagated_to_caller: bool = field(init=False, default=False)


@dataclass(frozen=True, slots=True, kw_only=True, eq=False)
class GuaranteeNode(OperationNode):
    """A position a triggered action guarantees, which the callee itself operates on.

    This stands in for an operation whose details live in the callee's own graph.
    ``depends_on`` holds the operation that triggered the Action Execution; codegen resolves
    this node to the callee's last operation on ``guaranteed_position`` when it
    includes ``action`` for that execution. Caller operations that read the
    position depend on this node with ordinary edges.
    """

    _is_guarantee_or_has_partial_move_rule_result: typing.ClassVar[bool] = True

    depends_on: tuple[LastOperationNode, ...]
    # The Action Execution of the action that guarantees the position.
    execution: ActionExecution
    # Action Executions to follow after ``execution`` before resolving
    # ``guaranteed_position`` in the final callee's operation graph.
    nested_executions: tuple[ActionExecution, ...]
    # The guaranteed position, by the callee's own key for it.
    guaranteed_position: tuple[str, ...]
    # Every caller position operated on by the guaranteed Particle Operation.
    operation_positions: tuple[tuple[str, ...], ...]

    @property
    def canonical_node_for_particle_operation(self) -> GuaranteeNode:
        """Return this node as the guaranteed Particle Operation's representative."""
        return self

    @property
    @typing.override
    def operated_positions(self) -> tuple[tuple[str, ...], ...]:
        """Every position operated on by this node."""
        return self.operation_positions


@dataclass(frozen=True, slots=True, kw_only=True, eq=False)
class MoveGuaranteeNode(GuaranteeNode):
    """One position operated on by a guaranteed Move Particle Statement."""

    canonical_move_guarantee: MoveGuaranteeNode | None = field(repr=False)

    @property
    @typing.override
    def canonical_node_for_particle_operation(self) -> MoveGuaranteeNode:
        """Return the shared representative for the guaranteed Move."""
        return self.canonical_move_guarantee or self


@dataclass(frozen=True, slots=True, kw_only=True, eq=False)
class RequirementNode(OperationNode):
    """A caller-controlled contracted position an operation needs in a given state.

    This stands in for the caller operation that satisfies an inferred requirement.
    The renderer/codegen resolves it to the caller op that most recently operated
    on the position identified by ``requirement`` before the Action Execution. A
    position can be empty without any operation emptying it, so an empty requirement
    can have no such caller op at all, which is why the required state is recorded
    here.

    ``depends_on`` contains exactly one node. It is the RequirementNode for the
    nearest parent name with a Position Requirement, or the action parent's last
    operation when there is no such parent requirement. This represents the rule
    that every position in a chained name except the last must contain a particle.
    """

    depends_on: tuple[ActionParentLastOperationNode | RequirementNode]
    requirement: OperationGraphRequirement


@dataclass(frozen=True, slots=True, kw_only=True, eq=False)
class EmptyRuleBindingHoleNode(OperationNode):
    """An Empty Rule Binding Hole represented in an Operation Graph.

    ``empty_rule_binding_hole`` preserves the unfinished Empty Rule application
    while caller Action Requirement satisfactions are applied.
    """

    depends_on: tuple[()] = ()
    empty_rule_binding_hole: EmptyRuleBindingHole
    remaining_concrete_nodes: tuple[ConcreteOperationNode, ...]
