"""Data structures shared by operation-graph construction and action contracts."""

from __future__ import annotations

import abc
import enum
import typing
from dataclasses import dataclass, field

if typing.TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

    from define.compiler import ast


class PositionOccupancyState(enum.Enum):
    """The occupancy state of an interface position."""

    EMPTY = enum.auto()
    OCCUPIED = enum.auto()
    ERROR = enum.auto()


type PrecedingChildOperationNode = PositionOperationNode | GuaranteeNode
type LastOperationNode = PrecedingChildOperationNode | RequirementNode
type ActionParentOperationNode = ActionParentLastOperationNode | LastOperationNode
type PrecedingChildOperations = Iterable[
    tuple[tuple[str, ...], PrecedingChildOperationNode]
]


def _shares_path(one: tuple[str, ...], other: tuple[str, ...]) -> bool:
    """Return whether either child position is a prefix of the other."""
    shared_depth = min(len(one), len(other))
    return one[:shared_depth] == other[:shared_depth]


def _apply_empty_rule_reduction_newest_first[DependencyNodeT: LastOperationNode](
    candidates: Iterable[DependencyNodeT],
) -> tuple[DependencyNodeT, ...]:
    """Apply the Empty Rule to dependencies ordered newest to oldest."""
    dependencies: list[DependencyNodeT] = []
    newer_positions: set[tuple[str, ...]] = set()
    newer_position_prefixes: set[tuple[str, ...]] = set()
    for node in candidates:
        positions = node.operated_positions
        has_newer_related_operation = _has_related_position(
            positions, newer_positions, newer_position_prefixes
        )
        if not has_newer_related_operation:
            dependencies.append(node)
        # An operation covered by a newer operation still covers every older
        # operation that shares one of its other positions. Keeping its
        # positions here preserves that ordering through chains of moves.
        for position in positions:
            newer_positions.add(position)
            # A valid wall profile of the August 2026 default operation-graph
            # full-compiler workload made this generator's allocation and yields
            # look costly. Replacing set.update(generator) with an explicit depth
            # loop calling set.add made py-spy attribute 69% less time here, but
            # alternating benchmarks showed no measurable full-compiler change.
            newer_position_prefixes.update(
                position[:depth] for depth in range(1, len(position))
            )
    dependencies.reverse()
    return tuple(dependencies)


def apply_empty_rule_reduction[DependencyNodeT: LastOperationNode](
    candidates: set[DependencyNodeT],
) -> tuple[DependencyNodeT, ...]:
    """Apply the Empty Rule to unordered candidate dependencies."""
    return _apply_empty_rule_reduction_newest_first(
        sorted(candidates, key=lambda item: item.operation_order, reverse=True)
    )


def _has_related_position(
    positions: tuple[tuple[str, ...], ...],
    other_positions: set[tuple[str, ...]],
    other_position_prefixes: set[tuple[str, ...]],
) -> bool:
    """Return whether any position shares a parent-child path with another position."""
    for position in positions:
        if position in other_positions or position in other_position_prefixes:
            return True
        for depth in range(1, len(position)):
            if position[:depth] in other_positions:
                return True
    return False


@dataclass(frozen=True, slots=True)
class ChildOperation:
    """A caller operation on a transitive child position of a required position."""

    # The child position relative to the required position.
    child_position: tuple[str, ...]
    # The operation node in the caller's graph.
    operation: PrecedingChildOperationNode


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

    def operations_not_on_same_paths_as(
        self, relative_positions: frozenset[tuple[str, ...]]
    ) -> list[ChildOperation]:
        """Return surviving operations independent of the supplied paths."""
        operations: list[ChildOperation] = []
        for operation in self.operations:
            shares_dependency_path = any(
                _shares_path(operation.child_position, dependency)
                for dependency in relative_positions
            )
            if not shares_dependency_path:
                operations.append(operation)
        return operations

    def empty_rule_dependencies_for(
        self, relative_position: tuple[str, ...]
    ) -> tuple[PrecedingChildOperationNode, ...]:
        """Return Empty Rule dependencies on the supplied position's path."""
        matching_operations: list[PrecedingChildOperationNode] = []
        seen_operations: set[PrecedingChildOperationNode] = set()
        for child_operation in self.operations:
            operation = child_operation.operation
            if operation in seen_operations or not _shares_path(
                child_operation.child_position, relative_position
            ):
                continue
            seen_operations.add(operation)
            matching_operations.append(operation)
        return _apply_empty_rule_reduction_newest_first(matching_operations)

    def determine_empty_rule_dependencies(
        self,
        empty_position: tuple[str, ...],
        fill_dependency: LastOperationNode | None,
        emptied_ancestor: LastOperationNode,
    ) -> _EmptyRuleDependencies:
        """Return the local and caller dependencies required by the Empty Rule."""
        candidates: set[LastOperationNode] = set()
        caller_dependencies: CallerEmptyRuleDependencies | None = None
        # The action received the particle in the state declared by a position
        # requirement rather than putting it in that state itself.
        if isinstance(emptied_ancestor, RequirementNode):
            requirement_position = emptied_ancestor.requirement_position
            # The action empties the required position itself rather than one of
            # that particle's child positions.
            if requirement_position == empty_position:
                dependency_requirements: tuple[tuple[str, ...], ...] = ()
                # A move empties this position and fills a position whose
                # required empty state was also supplied by the caller. (We know
                # it is a move because fill_dependency is not None.)
                if isinstance(fill_dependency, RequirementNode):
                    dependency_requirements = (fill_dependency.requirement_position,)
                # A move empties this position and fills a position that an
                # earlier Particle Operation in this action emptied.
                elif fill_dependency is not None:
                    candidates.add(fill_dependency)
                caller_dependencies = CallerParticleEmptyRuleDependencies(
                    requirement_position=empty_position,
                    dependency_child_positions=self.child_position_set(),
                    dependency_requirements=dependency_requirements,
                )
            # The destruction cascade empties a child position of the particle
            # that the action received through a position requirement.
            else:
                caller_dependencies = CallerChildPositionEmptyRuleDependencies(
                    requirement_position=requirement_position,
                    emptied_position=empty_position[len(requirement_position) :],
                )
        # An earlier Particle Operation in this action supplied the particle
        # being emptied, directly or by operating on one of its parent names.
        else:
            candidates.add(emptied_ancestor)
            # This is a move, and its destination was previously operated on.
            if fill_dependency is not None:
                candidates.add(fill_dependency)
        candidates.update(
            child_operation.operation for child_operation in self.operations
        )
        return _EmptyRuleDependencies(
            apply_empty_rule_reduction(candidates),
            caller_dependencies,
        )

    def all_precede(self, operation: MoveNode) -> bool:
        """Return whether every child operation precedes ``operation``."""
        return not self.operations or (
            self.operations[0].operation.operation_order < operation.operation_order
        )

    def child_position_set(self) -> frozenset[tuple[str, ...]]:
        """Return the relative child positions with preceding operations."""
        return frozenset(operation.child_position for operation in self.operations)


# Separate propagation paths can require distinct caller inputs with identical
# dependency data, so these values use identity when codegen keys input methods.
@dataclass(frozen=True, slots=True, eq=False)
class CallerEmptyRuleDependencies:
    """Empty Rule dependencies supplied through a position requirement."""

    requirement_position: tuple[str, ...]

    @property
    def full_emptied_position(self) -> tuple[str, ...]:
        """The emptied position from the caller's perspective."""
        return self.requirement_position


@dataclass(frozen=True, slots=True, eq=False)
class CallerParticleEmptyRuleDependencies(CallerEmptyRuleDependencies):
    """Information needed when the required position itself is emptied.

    ``dependency_child_positions`` are relative to the required particle and
    identify operations that are already dependencies.
    ``dependency_requirements`` identifies requirement positions whose
    caller-supplied operations must also precede the emptying.
    """

    dependency_child_positions: frozenset[tuple[str, ...]]
    dependency_requirements: tuple[tuple[str, ...], ...]


@dataclass(frozen=True, slots=True, eq=False)
class CallerChildPositionEmptyRuleDependencies(CallerEmptyRuleDependencies):
    """Information needed when a child position of the required particle is emptied."""

    emptied_position: tuple[str, ...]

    @property
    @typing.override
    def full_emptied_position(self) -> tuple[str, ...]:
        """The emptied position from the caller's perspective."""
        return (*self.requirement_position, *self.emptied_position)


@dataclass(frozen=True, slots=True)
class _EmptyRuleDependencies:
    """Local and caller dependencies required by the Empty Rule."""

    local_dependencies: tuple[LastOperationNode, ...]
    caller_dependencies: CallerEmptyRuleDependencies | None


@dataclass(frozen=True, slots=True)
class CallerEmptyRuleSubstitution:
    """The result of substituting caller bindings into CallerEmptyRuleDependencies."""

    dependency_nodes: tuple[LastOperationNode, ...]
    caller_empty_rule_dependencies: CallerEmptyRuleDependencies | None


@dataclass(frozen=True, slots=True)
class RequirementBinding:
    """The caller dependencies that satisfy one requirement of a triggered callee."""

    # The operation or RequirementNode that put the position in its required
    # state from the caller's perspective.
    operation: LastOperationNode
    child_operations: ParticleChildOperations


@dataclass(frozen=True, slots=True, eq=False)
class ActionTrigger:
    """One Action Trigger and what satisfies each requirement of the callee.

    Recorded from the caller's side, at the moment it triggers, because only the
    caller knows what it did to the positions the callee names.
    """

    # The action reference this Action Trigger fires, from the caller's perspective.
    callee: ast.ActionReference
    # The operation that triggered the callee.
    trigger_operation: LastOperationNode
    # What satisfies each requirement of the callee, by the callee's own key for
    # that requirement.
    bindings: dict[tuple[str, ...], RequirementBinding]
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


# A node_id is unique only within one graph, so nodes use identity equality and
# hashing when they appear in sets and mappings. A node_id is normally also the
# operation's order. Conditional destructions added after validation override
# that through operation_order, so only operation_order should be used to determine
# the order of operations. Every dataclass subclass must repeat eq=False because
# dataclass decorator options are not inherited.
@dataclass(frozen=True, slots=True, kw_only=True, eq=False)
class OperationNode(abc.ABC):
    """One operation in an action's dependency graph."""

    node_id: int
    # The operations this node directly depends on (the operations that must
    # complete before it).
    depends_on: tuple[OperationNode, ...]
    operation_order: tuple[int, int, int] = field(init=False, repr=False)

    def __post_init__(self):
        """Set the operation's order within its action."""
        object.__setattr__(self, "operation_order", (self.node_id, 1, 0))

    @property
    def operated_positions(self) -> tuple[tuple[str, ...], ...]:
        """Every position operated on by this node."""
        return ()


@dataclass(frozen=True, slots=True, kw_only=True, eq=False)
class ActionParentLastOperationNode(OperationNode):
    """The caller's last operation on this action's parent position or its transitive parents."""

    depends_on: tuple[()]


@dataclass(frozen=True, slots=True, kw_only=True, eq=False)
class PositionOperationNode(OperationNode):
    """An operation the body performs on a written position."""

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
class DestroyNode(PositionOperationNode):
    """A destroy of the particle in ``target``."""


@dataclass(frozen=True, slots=True, kw_only=True, eq=False)
class DestroyIfOccupiedNode(DestroyNode):
    """A destroy of the particle in ``target`` only if the position is occupied."""

    inserted_before: DestroyNode | None = None

    def __post_init__(self):
        """Set the conditional destruction's order within its action."""
        OperationNode.__post_init__(self)
        if self.inserted_before is not None:
            object.__setattr__(
                self,
                "operation_order",
                (self.inserted_before.node_id, 0, self.node_id),
            )


@dataclass(frozen=True, slots=True, kw_only=True, eq=False)
class GuaranteeNode(OperationNode):
    """A position a triggered action guarantees, which the callee itself operates on.

    This stands in for an operation whose details live in the callee's own graph.
    ``depends_on`` holds the operation that fired the trigger; codegen resolves
    this node to the callee's last operation on ``guaranteed_position`` when it
    splices ``action`` in at that trigger. Caller operations that read the
    position depend on this node with ordinary edges.
    """

    depends_on: tuple[LastOperationNode, ...]
    # The Action Trigger of the action that guarantees the position.
    trigger: ActionTrigger
    # Action Triggers to follow after ``trigger`` before resolving
    # ``guaranteed_position`` in the final callee's operation graph.
    nested_triggers: tuple[ActionTrigger, ...]
    # The guaranteed position, by the callee's own key for it.
    guaranteed_position: tuple[str, ...]
    # Every caller position operated on by the guaranteed Particle Operation.
    operation_positions: tuple[tuple[str, ...], ...]

    @property
    @typing.override
    def operated_positions(self) -> tuple[tuple[str, ...], ...]:
        """Every position operated on by this node."""
        return self.operation_positions


@dataclass(frozen=True, slots=True, kw_only=True, eq=False)
class RequirementNode(OperationNode):
    """A caller-controlled contracted position an operation needs in a given state.

    This stands in for the caller operation that satisfies an inferred requirement.
    The renderer/codegen resolves it to the caller op that most recently operated
    on ``requirement_position`` before the trigger. A position can be empty
    without any operation emptying it, so an empty requirement can have no such
    caller op at all, which is why the required state is recorded here.

    ``depends_on`` contains exactly one node. It is the RequirementNode for the
    nearest parent name with a Position Requirement, or the action parent's last
    operation when there is no such parent requirement. This represents the rule
    that every position in a chained name except the last must contain a particle.
    """

    depends_on: tuple[ActionParentLastOperationNode | RequirementNode]
    # The state this action needs the position to be in.
    required_state: PositionOccupancyState
    # This action's own key for the caller-controlled contracted position.
    requirement_position: tuple[str, ...] = field(default=(), compare=False)


@dataclass(frozen=True, slots=True, kw_only=True, eq=False)
class CallerEmptyRuleDependenciesNode(OperationNode):
    """Caller dependencies needed when an action empties a required particle.

    ``caller_empty_rule_dependencies`` preserves the complete Empty Rule dependency set
    while caller requirement bindings are substituted.
    """

    depends_on: tuple[()]
    caller_empty_rule_dependencies: CallerEmptyRuleDependencies
