"""Data structures shared by operation-graph construction and action contracts."""

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


type PrecedingChildOperationNode = PositionOperationNode | GuaranteeNode
type LastOperationNode = PrecedingChildOperationNode | RequirementNode
type ActionParentOperationNode = ActionParentLastOperationNode | LastOperationNode
type EmptyRuleDependencyNode = LastOperationNode | CallerEmptyRuleDependenciesNode
type EmptyingOperationDependencyNode = (
    EmptyRuleDependencyNode | CallerMoveRuleFillDependencyNode
)
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
            # workload made this generator's allocation and yields look costly.
            # Replacing set.update(generator) with an explicit depth loop shifted
            # sampled attribution, but alternating benchmarks showed no measurable
            # full-compiler change.
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
        if not relative_positions:
            return list(self.operations)
        excluded_operations: set[PrecedingChildOperationNode] = set()
        for child_operation in self.operations:
            shares_dependency_path = any(
                _shares_path(child_operation.child_position, dependency)
                for dependency in relative_positions
            )
            if shares_dependency_path:
                excluded_operations.add(child_operation.operation)
        # The Empty Rule compares Particle Operations rather than the individual
        # child positions through which those operations are known.
        return [
            child_operation
            for child_operation in self.operations
            if child_operation.operation not in excluded_operations
        ]

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
        emptied_ancestor: LastOperationNode,
    ) -> _EmptyRuleDependencies:
        """Return dependencies required by the Empty Rule."""
        return self._determine_emptying_dependencies(
            empty_position,
            None,
            emptied_ancestor,
        )

    def determine_move_rule_dependencies(
        self,
        empty_position: tuple[str, ...],
        fill_dependency: LastOperationNode | None,
        emptied_ancestor: LastOperationNode,
    ) -> _EmptyRuleDependencies:
        """Return dependencies required by the Move Rule."""
        return self._determine_emptying_dependencies(
            empty_position,
            fill_dependency,
            emptied_ancestor,
        )

    def _determine_emptying_dependencies(
        self,
        empty_position: tuple[str, ...],
        fill_dependency: LastOperationNode | None,
        emptied_ancestor: LastOperationNode,
    ) -> _EmptyRuleDependencies:
        candidates: set[LastOperationNode] = set()
        caller_dependencies: CallerEmptyRuleDependencies | None = None
        # The action received the particle in the state declared by a position
        # requirement rather than putting it in that state itself.
        if isinstance(emptied_ancestor, RequirementNode):
            dependency_requirements: tuple[tuple[str, ...], ...] = ()
            # A move empties this position and fills a position whose required
            # empty state was also supplied by the caller.
            if isinstance(fill_dependency, RequirementNode):
                dependency_requirements = (
                    fill_dependency.requirement.requirement_position,
                )
            # A move empties this position and fills a position that an earlier
            # Particle Operation in this action emptied.
            elif fill_dependency is not None:
                candidates.add(fill_dependency)
            caller_dependencies = CallerEmptyRuleDependencies(
                requirement_position=empty_position,
                dependency_child_positions=self.child_position_set(),
                dependency_requirements=dependency_requirements,
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
    """Empty Rule dependencies for a particle supplied through a position requirement.

    ``dependency_child_positions`` are relative to the required particle and
    identify operations that are already dependencies.
    ``dependency_requirements`` identifies requirement positions whose
    caller-supplied operations must also precede the emptying.
    """

    requirement_position: tuple[str, ...]
    dependency_child_positions: frozenset[tuple[str, ...]]
    dependency_requirements: tuple[tuple[str, ...], ...]


@dataclass(frozen=True, slots=True)
class _EmptyRuleDependencies:
    """Local and caller dependencies required by the Empty or Move Rule."""

    local_dependencies: tuple[LastOperationNode, ...]
    caller_dependencies: CallerEmptyRuleDependencies | None


@dataclass(frozen=True, slots=True)
class CallerEmptyRuleSubstitution:
    """The result of substituting caller bindings into CallerEmptyRuleDependencies."""

    # TODO: Move caller_empty_rule_dependencies to a
    # PartialCallerEmptyRuleSubstitution subclass where it is non-optional. The base
    # class should retain dependency_nodes because every substitution produces them;
    # a base instance means resolution is complete, while the subclass means one
    # caller supplied concrete dependencies and resolution must continue through an
    # earlier caller.
    dependency_nodes: tuple[LastOperationNode, ...]
    caller_empty_rule_dependencies: CallerEmptyRuleDependencies | None


@dataclass(frozen=True, slots=True, eq=False)
class CallerMoveRuleFillDependency:
    """A Fill dependency awaiting the Move Rule comparison in a caller."""

    fill_dependency: ActionParentLastOperationNode | RequirementNode
    requirement: OperationGraphRequirement
    # Retained across caller substitutions because the Move Rule cannot apply the
    # Empty Rule comparison until the caller's Fill dependency becomes a Particle
    # Operation with known operated positions.
    move_rule_comparison_positions: tuple[tuple[str, ...], ...]


@dataclass(frozen=True, slots=True)
class RequirementBinding:
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

    @property
    def caller_input_dependency(self) -> RequirementNode | None:
        """Return the caller input that triggers a destructor Action Execution."""
        if isinstance(self.trigger_operation, RequirementNode):
            return self.trigger_operation
        return None

    def caller_dependency_for_input(
        self,
        callee_input: ActionParentLastOperationNode | RequirementNode,
    ) -> ActionParentOperationNode:
        """Return the caller operation satisfying one direct callee input."""
        if isinstance(callee_input, ActionParentLastOperationNode):
            return self.action_parent_last_operation
        binding = self.bindings.get(callee_input.requirement.requirement_position)
        if binding is not None:
            return binding.operation

        # Position Requirements form a chain through parent names, so this node has
        # exactly one direct input: the nearest parent-name requirement, or the
        # action parent's last operation when there is no parent-name requirement.
        (parent_input,) = callee_input.depends_on
        if isinstance(parent_input, ActionParentLastOperationNode):
            return self.action_parent_last_operation
        return self.bindings[parent_input.requirement.requirement_position].operation

    def substitute_caller_empty_rule_dependencies(
        self,
        caller_dependencies: CallerEmptyRuleDependencies,
    ) -> CallerEmptyRuleSubstitution:
        """Substitute this caller's bindings into Empty Rule dependencies."""
        callee_requirement_binding = self.bindings[
            caller_dependencies.requirement_position
        ]
        child_operations = (
            callee_requirement_binding.child_operations.operations_not_on_same_paths_as(
                caller_dependencies.dependency_child_positions
            )
        )
        candidates: set[LastOperationNode] = {
            child_operation.operation for child_operation in child_operations
        }
        for requirement in caller_dependencies.dependency_requirements:
            # The Fill Rule allows an EMPTY requirement to depend on an
            # operation on any parent position. Search the required position
            # and its parent-position prefixes for that operation.
            for depth in range(len(requirement), 0, -1):
                binding_position = requirement[:depth]
                requirement_binding = self.bindings.get(binding_position)
                if requirement_binding is None:
                    continue
                # The Move Rule combines the dependencies for emptying the
                # source position and filling the target position, then applies
                # the Empty Rule comparison. When filling the target depends on
                # a Particle Operation on a transitive parent position of the
                # source, a more recent Particle Operation on the source or one
                # of its transitive child positions remains as the dependency.
                if not ast.is_prefix(
                    binding_position,
                    caller_dependencies.requirement_position,
                ):
                    candidates.add(requirement_binding.operation)
                break

        requirement_position_in_caller = self._occupied_requirement_position(
            callee_requirement_binding
        )
        # The particle is not from our caller, so we don't have to propagate
        # Empty Rule child dependencies on it.
        if requirement_position_in_caller is None:
            if (
                not child_operations
                and not caller_dependencies.dependency_child_positions
            ):
                # The direct caller created or moved the required particle, or triggered
                # an action that guaranteed it.
                # callee_requirement_binding.operation is the operation on the emptied
                # position. When there are no later child-position operations, it
                # remains the required dependency per the Empty Rule.
                candidates.add(callee_requirement_binding.operation)
            return CallerEmptyRuleSubstitution(
                apply_empty_rule_reduction(candidates),
                None,
            )

        # If this action received the particle from its caller, some operations
        # required by the Empty Rule may belong to that caller and must be propagated.
        # Apply what we can of the Empty Rule now to this caller's operations before
        # propagating dependencies from this caller's occupied requirement to its caller.
        dependencies = apply_empty_rule_reduction(candidates)
        dependency_nodes: list[PrecedingChildOperationNode] = []
        dependency_requirements: list[tuple[str, ...]] = []
        dependency_child_positions = set(
            callee_requirement_binding.child_operations.child_position_set()
        )
        dependency_child_positions.update(
            caller_dependencies.dependency_child_positions
        )
        for node in dependencies:
            if isinstance(node, RequirementNode):
                dependency_requirements.append(node.requirement.requirement_position)
                continue
            dependency_nodes.append(node)
            # This remains linear in the positions on the dependencies because
            # each position is examined once, without comparing dependencies.
            self._add_positions_relative_to_particle(
                dependency_child_positions,
                node,
                requirement_position_in_caller,
            )
        return CallerEmptyRuleSubstitution(
            tuple(dependency_nodes),
            CallerEmptyRuleDependencies(
                requirement_position=requirement_position_in_caller,
                dependency_child_positions=frozenset(dependency_child_positions),
                dependency_requirements=tuple(dependency_requirements),
            ),
        )

    def substitute_caller_move_rule_fill_dependency(
        self,
        caller_dependency: CallerMoveRuleFillDependency,
    ) -> PrecedingChildOperationNode | CallerMoveRuleFillDependency | None:
        """Substitute the Fill dependency and apply the Move Rule comparison."""
        fill_dependency = self.caller_dependency_for_input(
            caller_dependency.fill_dependency
        )
        move_rule_comparison_positions = tuple(
            ast.chain_in_caller(self.action_chain, position)
            for position in caller_dependency.move_rule_comparison_positions
        )
        if isinstance(fill_dependency, (PositionOperationNode, GuaranteeNode)):
            for fill_position in fill_dependency.operated_positions:
                if any(
                    _shares_path(fill_position, comparison_position)
                    for comparison_position in move_rule_comparison_positions
                ):
                    # The Fill dependency is concrete and the Empty Rule excludes it
                    # in favor of a more recent related dependency.
                    return None
            # The Fill dependency is concrete and remains a direct dependency because
            # no more recent dependency operates on a related position.
            return fill_dependency
        # The Fill dependency is still caller-controlled, so carry the comparison
        # state to the next caller substitution.
        return CallerMoveRuleFillDependency(
            fill_dependency=fill_dependency,
            requirement=OperationGraphRequirement(
                requirement_position=ast.chain_in_caller(
                    self.action_chain,
                    caller_dependency.requirement.requirement_position,
                ),
                required_state=caller_dependency.requirement.required_state,
            ),
            move_rule_comparison_positions=move_rule_comparison_positions,
        )

    @staticmethod
    def _occupied_requirement_position(
        binding: RequirementBinding,
    ) -> tuple[str, ...] | None:
        if not isinstance(binding.operation, RequirementNode):
            return None
        return binding.operation.requirement.requirement_position

    @staticmethod
    def _add_positions_relative_to_particle(
        relative_positions: set[tuple[str, ...]],
        node: PrecedingChildOperationNode,
        particle_position: tuple[str, ...],
    ):
        for position in node.operated_positions:
            if not ast.is_prefix(particle_position, position):
                continue
            relative_positions.add(position[len(particle_position) :])


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

    depends_on: tuple[()] = ()


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
class DestructionFactDestroyNode(DestroyNode):
    """A Destroy performed as part of one Destruction Fact."""

    destruction_fact: DestructionFact
    destruction_position: tuple[str, ...]
    dependencies_before_caller_contribution: tuple[EmptyRuleDependencyNode, ...]
    dependencies_after_caller_contribution: tuple[PrecedingChildOperationNode, ...]


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
class DestructionDependency:
    """A callee Destroy preceded by caller-contributed Destroys."""

    execution: ActionExecution
    callee_destroy: DestructionOperation


@dataclass(slots=True)
class DestructionContribution:
    """Caller-contributed Destroy operations for one destruction dependency."""

    operations: dict[DestructionFragmentDestroyNode, None] = field(default_factory=dict)
    first_operations: dict[DestructionFragmentDestroyNode, None] = field(
        default_factory=dict
    )
    completion_operations: dict[DestructionFragmentDestroyNode, None] = field(
        default_factory=dict
    )


@dataclass(frozen=True, slots=True, kw_only=True, eq=False)
class DestructionContributionNode(OperationNode):
    """Connects preceding caller operations to the first Destroy in one contribution."""

    depends_on: tuple[EmptyRuleDependencyNode, ...]
    execution: ActionExecution
    destruction_fact: DestructionFact
    callee_destroy_position: tuple[str, ...]


class ContributedDestructionPosition(typing.NamedTuple):
    """One caller-known occupied position contributed to a destruction."""

    position: ast.PositionReference
    position_relative_to_destroyed_particle: tuple[str, ...]
    callee_destroy_position_relative_to_destroyed_particle: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class DestructionContractNewlyOccupiedChildren:
    """Children newly known as occupied while validating a Destruction Contract."""

    destruction_fact: DestructionFact
    destroyed_particle_position: ast.PositionReference
    destroyed_position_in_destroying_action: ast.PositionReference
    children: Sequence[ContributedDestructionPosition]
    is_propagated_to_caller: bool


@dataclass(frozen=True, slots=True)
class ContributedDestruction:
    """Ordinary Destroy operations contributed before one callee Destroy."""

    contribution_node: DestructionContributionNode
    operations: tuple[DestructionFragmentDestroyNode, ...]
    completion_operations: tuple[DestructionFragmentDestroyNode, ...]


@dataclass(frozen=True, slots=True)
class ContributedDestructionFragment:
    """Ordinary Destroy operations contributed around one direct Action Execution."""

    contribution_dependencies: tuple[EmptyRuleDependencyNode, ...]
    operations: tuple[DestructionFragmentDestroyNode, ...]
    contributed_destructions: tuple[ContributedDestruction, ...]


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
    @typing.override
    def operated_positions(self) -> tuple[tuple[str, ...], ...]:
        """Every position operated on by this node."""
        return self.operation_positions


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
class CallerEmptyRuleDependenciesNode(OperationNode):
    """Caller dependencies needed when an action empties a required particle.

    ``caller_empty_rule_dependencies`` preserves the complete Empty Rule dependency set
    while caller requirement bindings are substituted.
    """

    depends_on: tuple[()] = ()
    caller_empty_rule_dependencies: CallerEmptyRuleDependencies


@dataclass(frozen=True, slots=True, kw_only=True, eq=False)
class CallerMoveRuleFillDependencyNode(OperationNode):
    """A Move Rule Fill dependency that must be compared after caller substitution."""

    depends_on: tuple[()] = ()
    caller_move_rule_fill_dependency: CallerMoveRuleFillDependency
