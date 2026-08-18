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
type EmptyOrMoveRuleDependencyNode = (
    EmptyRuleDependencyNode | CallerMoveRuleFillDependencyNode
)
# TODO: Replace the remaining "input" terminology in consumers with names for
# callee nodes, caller nodes, node bindings, Dependency Fanouts, or Dependency
# Joins according to their actual role.
type AbstractOperationNode = (
    ActionParentLastOperationNode
    | RequirementNode
    | EmptyRuleBindingHoleNode
    | CallerMoveRuleFillDependencyNode
)
type BindingHole = (
    AbstractOperationNode | EmptyRuleBindingHole | CallerMoveRuleFillDependency
)
type PrecedingChildOperations = Iterable[tuple[tuple[str, ...], ConcreteOperationNode]]


def _shares_path(one: tuple[str, ...], other: tuple[str, ...]) -> bool:
    """Return whether either child position is a prefix of the other."""
    shared_depth = min(len(one), len(other))
    return one[:shared_depth] == other[:shared_depth]


def _apply_empty_rule_comparison_most_recent_first[DependencyNodeT: LastOperationNode](
    collected_nodes: Iterable[DependencyNodeT],
    callee_collected_operation_positions: Iterable[tuple[str, ...]] = (),
) -> list[DependencyNodeT]:
    """Apply Comparison to collected nodes from most to least recent.

    Nodes are returned from least to most recent.
    """
    nodes_remaining_after_comparison: list[DependencyNodeT] = []
    more_recent_positions: set[tuple[str, ...]] = set()
    more_recent_position_prefixes: set[tuple[str, ...]] = set()
    # Every node collected in the callee represents a more recent Particle
    # Operation than every one collected in the caller, so it must participate in
    # Comparison before any caller node is considered.
    for position in callee_collected_operation_positions:
        more_recent_positions.add(position)
        more_recent_position_prefixes.update(
            position[:depth] for depth in range(1, len(position))
        )
    for node in collected_nodes:
        positions = node.operated_positions
        has_more_recent_collected_operation_on_shared_path = _has_related_position(
            positions,
            more_recent_positions,
            more_recent_position_prefixes,
        )
        if not has_more_recent_collected_operation_on_shared_path:
            nodes_remaining_after_comparison.append(node)
        # A Particle Operation excluded by a more recent Particle Operation can
        # still exclude every less recent Particle Operation that shares one of its
        # other positions. Keeping its positions preserves that ordering through
        # chains of Move Particle Statements.
        for position in positions:
            more_recent_positions.add(position)
            # A valid wall profile of the August 2026 default operation-graph
            # workload made this generator's allocation and yields look costly.
            # Replacing set.update(generator) with an explicit depth loop shifted
            # sampled attribution, but alternating benchmarks showed no measurable
            # full-compiler change.
            more_recent_position_prefixes.update(
                position[:depth] for depth in range(1, len(position))
            )
    nodes_remaining_after_comparison.reverse()
    return nodes_remaining_after_comparison


def apply_empty_rule_comparison[DependencyNodeT: LastOperationNode](
    collected_nodes: set[DependencyNodeT],
) -> list[DependencyNodeT]:
    """Apply Comparison and return nodes from least to most recent."""
    return _apply_empty_rule_comparison_most_recent_first(
        sorted(collected_nodes, key=lambda item: item.operation_order, reverse=True)
    )


def _apply_move_correction_and_fill_dependency_removal[
    DependencyNodeT: LastOperationNode
](
    nodes_remaining_after_comparison: list[DependencyNodeT],
    fill_dependency: DependencyNodeT | None,
    concrete_caller_nodes: Collection[ConcreteOperationNode] = (),
) -> list[DependencyNodeT]:
    """Apply the Empty Rule's Move Correction and the Move Rule's optional Fill Dependency removal.

    ``nodes_remaining_after_comparison`` must be ordered from least to most recent.
    """
    # Removal requires both a removable node and another remaining node that
    # depends on it. A concrete caller node can represent that other node across an
    # action boundary; without one, fewer than two remaining nodes cannot qualify.
    if not nodes_remaining_after_comparison or (
        len(nodes_remaining_after_comparison) < 2 and not concrete_caller_nodes
    ):
        return nodes_remaining_after_comparison
    removable_nodes: set[OperationNode] = set()
    least_recent_removable_node: OperationNode | None = None
    nodes_to_consider_for_removal_count = len(nodes_remaining_after_comparison)
    if not concrete_caller_nodes:
        # The final list item is the most recent node. Without a callee node, no
        # remaining node can depend on it, so exclude that one item from the prefix
        # scanned for removal. Earlier nodes remain because more recent nodes can
        # depend on them.
        nodes_to_consider_for_removal_count -= 1
    for node_index in range(nodes_to_consider_for_removal_count):
        node = nodes_remaining_after_comparison[node_index]
        if not isinstance(node, MoveNode) and node is not fill_dependency:
            continue
        removable_nodes.add(node)
        if least_recent_removable_node is None:
            least_recent_removable_node = node
    if least_recent_removable_node is None:
        return nodes_remaining_after_comparison

    nodes_to_visit: list[OperationNode] = list(concrete_caller_nodes)
    for node in nodes_remaining_after_comparison:
        if node.operation_order <= least_recent_removable_node.operation_order:
            continue
        # A node cannot remove itself, so begin from the nodes it directly depends on.
        nodes_to_visit.extend(node.depends_on)
    visited: set[OperationNode] = set()
    nodes_to_remove: set[OperationNode] = set()
    while nodes_to_visit and removable_nodes:
        node = nodes_to_visit.pop()
        if node in visited:
            continue
        visited.add(node)
        if node in removable_nodes:
            removable_nodes.remove(node)
            nodes_to_remove.add(node)
        # Every depends_on edge leads to an earlier operation, so continuing past
        # the least recent removable node cannot reach another removable node.
        if node.operation_order <= least_recent_removable_node.operation_order:
            continue
        # A removable node can depend on an earlier removable node, so the nodes it
        # depends on must participate in the same traversal.
        nodes_to_visit.extend(node.depends_on)

    if not nodes_to_remove:
        return nodes_remaining_after_comparison
    return [
        node for node in nodes_remaining_after_comparison if node not in nodes_to_remove
    ]


def apply_empty_rule_to_caller_collection[DependencyNodeT: LastOperationNode](
    collected_nodes: set[DependencyNodeT],
    callee_collected_operation_positions: Iterable[tuple[str, ...]],
    concrete_caller_nodes: Collection[ConcreteOperationNode],
) -> list[DependencyNodeT]:
    """Compare caller-collected nodes with the callee's Collection, then apply Move Correction."""
    nodes_remaining_after_comparison = _apply_empty_rule_comparison_most_recent_first(
        sorted(
            collected_nodes,
            key=lambda item: item.operation_order,
            reverse=True,
        ),
        callee_collected_operation_positions,
    )
    return _apply_move_correction_and_fill_dependency_removal(
        nodes_remaining_after_comparison,
        None,
        concrete_caller_nodes,
    )


def _apply_empty_rule_comparison_and_move_correction_most_recent_first[
    DependencyNodeT: LastOperationNode
](
    collected_nodes: Iterable[DependencyNodeT],
) -> list[DependencyNodeT]:
    """Apply the Empty Rule's Comparison and Move Correction.

    Requires collected nodes to already be sorted most recent to least recent.
    """
    nodes_remaining_after_comparison = _apply_empty_rule_comparison_most_recent_first(
        collected_nodes
    )
    return _apply_move_correction_and_fill_dependency_removal(
        nodes_remaining_after_comparison,
        None,
    )


def _apply_full_move_rule_to_collected_empty_dependencies[
    DependencyNodeT: LastOperationNode
](
    empty_dependencies: set[DependencyNodeT],
    fill_dependency: DependencyNodeT | None,
) -> list[DependencyNodeT]:
    """Apply the Move Rule to collected Empty Dependencies."""
    if fill_dependency is not None:
        empty_dependencies.add(fill_dependency)
    nodes_remaining_after_comparison = apply_empty_rule_comparison(empty_dependencies)
    return _apply_move_correction_and_fill_dependency_removal(
        nodes_remaining_after_comparison,
        fill_dependency,
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

    def operations_not_on_same_paths_as(
        self, relative_positions: frozenset[tuple[str, ...]]
    ) -> list[ChildOperation]:
        """Return surviving operations independent of the supplied paths."""
        if not relative_positions:
            return list(self.operations)
        excluded_operations: set[ConcreteOperationNode] = set()
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
    ) -> tuple[ConcreteOperationNode, ...]:
        """Return Empty Rule dependencies on the supplied position's path."""
        matching_operations: list[ConcreteOperationNode] = []
        seen_operations: set[ConcreteOperationNode] = set()
        for child_operation in self.operations:
            operation = child_operation.operation
            if operation in seen_operations or not _shares_path(
                child_operation.child_position, relative_position
            ):
                continue
            seen_operations.add(operation)
            matching_operations.append(operation)
        return tuple(
            _apply_empty_rule_comparison_and_move_correction_most_recent_first(
                matching_operations
            )
        )

    def determine_empty_rule_dependencies(
        self,
        empty_position: tuple[str, ...],
        emptied_ancestor: LastOperationNode,
    ) -> _EmptyOrMoveRuleResult:
        """Return dependencies required by the Empty Rule."""
        return self._determine_emptying_dependencies(
            empty_position,
            None,
            emptied_ancestor,
            is_move_rule=False,
        )

    def determine_move_rule_dependencies(
        self,
        empty_position: tuple[str, ...],
        fill_dependency: LastOperationNode | None,
        emptied_ancestor: LastOperationNode,
    ) -> _EmptyOrMoveRuleResult:
        """Return dependencies required by the Move Rule."""
        return self._determine_emptying_dependencies(
            empty_position,
            fill_dependency,
            emptied_ancestor,
            is_move_rule=True,
        )

    def _determine_emptying_dependencies(
        self,
        empty_position: tuple[str, ...],
        fill_dependency: LastOperationNode | None,
        emptied_ancestor: LastOperationNode,
        *,
        is_move_rule: bool,
    ) -> _EmptyOrMoveRuleResult:
        collected_nodes: set[LastOperationNode] = set()
        caller_requirement_position: tuple[str, ...] | None = None
        fill_dependency_requirement_position: tuple[str, ...] | None = None
        # The action received the particle in the state declared by a position
        # requirement rather than putting it in that state itself.
        if isinstance(emptied_ancestor, RequirementNode):
            caller_requirement_position = empty_position
            # A move empties this position and fills a position whose required
            # empty state was also supplied by the caller.
            if isinstance(fill_dependency, RequirementNode):
                fill_dependency_requirement_position = (
                    fill_dependency.requirement.requirement_position
                )
        # An earlier Particle Operation in this action supplied the particle
        # being emptied, directly or by operating on one of its parent names.
        else:
            collected_nodes.add(emptied_ancestor)
        collected_nodes.update(
            child_operation.operation for child_operation in self.operations
        )
        # Caller substitution can add collected nodes that affect Move Correction
        # or the Move Rule's Fill Dependency removal, so neither the Empty Rule nor
        # Move Rule can run while a caller-controlled node remains unresolved.
        if caller_requirement_position is None and not isinstance(
            fill_dependency, RequirementNode
        ):
            if is_move_rule:
                local_nodes = _apply_full_move_rule_to_collected_empty_dependencies(
                    collected_nodes,
                    fill_dependency,
                )
            else:
                local_nodes = (
                    _apply_empty_rule_comparison_and_move_correction_most_recent_first(
                        sorted(
                            collected_nodes,
                            key=lambda item: item.operation_order,
                            reverse=True,
                        )
                    )
                )
        else:
            # A concrete Fill Dependency must participate in the partial Comparison
            # even though caller substitution prevents the remaining phases.
            if is_move_rule and isinstance(
                fill_dependency,
                (PositionOperationNode, GuaranteeNode),
            ):
                collected_nodes.add(fill_dependency)
            local_nodes = apply_empty_rule_comparison(collected_nodes)
        caller_collection = None
        if caller_requirement_position is not None:
            collected_operation_positions: list[tuple[str, ...]] = []
            for node in sorted(
                collected_nodes,
                key=lambda item: item.operation_order,
            ):
                collected_operation_positions.extend(node.operated_positions)
            caller_collection = CallerEmptyRuleCollection(
                requirement_position=caller_requirement_position,
                collected_child_operation_positions=self.child_position_set(),
                fill_dependency_requirement_position=(
                    fill_dependency_requirement_position
                ),
                collected_operation_positions=tuple(collected_operation_positions),
            )
        return _EmptyOrMoveRuleResult(
            local_nodes,
            caller_collection,
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
class _EmptyOrMoveRuleResult:
    """Locally selected nodes and a Collection awaiting a caller."""

    local_nodes: list[LastOperationNode]
    caller_collection: CallerEmptyRuleCollection | None


@dataclass(frozen=True, slots=True)
class EmptyRuleApplicationResult:
    """The result of binding an Empty Rule Binding Hole in one caller."""

    # TODO: Move empty_rule_binding_hole to a subclass where it is non-optional.
    # The base class should retain caller_nodes because every application produces
    # them; a base instance means binding is complete, while the subclass means one
    # caller supplied concrete nodes and binding must continue through an earlier
    # caller.
    caller_nodes: list[LastOperationNode]
    empty_rule_binding_hole: EmptyRuleBindingHole | None


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
        # exactly one direct input: the nearest parent-name requirement, or the
        # action parent's last operation when there is no parent-name requirement.
        (parent_binding_hole,) = callee_binding_hole.depends_on
        if isinstance(parent_binding_hole, ActionParentLastOperationNode):
            return self.action_parent_last_operation
        return self.requirement_satisfactions[
            parent_binding_hole.requirement.requirement_position
        ].operation

    def substitute_caller_move_rule_fill_dependency(
        self,
        caller_dependency: CallerMoveRuleFillDependency,
    ) -> ConcreteOperationNode | CallerMoveRuleFillDependency | None:
        """Substitute the Fill dependency and apply the Move Rule comparison."""
        fill_dependency = self.caller_operation_for_callee_binding_hole(
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
class DestructionContractNewlyOccupiedChildren:
    """Children newly known as occupied while validating a Destruction Contract."""

    destruction_fact: DestructionFact
    destroyed_particle_position: ast.PositionReference
    destroyed_position_in_destroying_action: ast.PositionReference
    children: Sequence[ContributedDestructionPosition]
    # Retaining the final contributed positions preserves the Destroys that finish
    # their contributions before the callee Destroy without another traversal.
    final_contributed_positions: Sequence[ContributedDestructionPosition]
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
class EmptyRuleBindingHoleNode(OperationNode):
    """An Empty Rule Binding Hole represented in an Operation Graph.

    ``empty_rule_binding_hole`` preserves the unfinished Empty Rule application
    while caller Action Requirement satisfactions are applied.
    """

    depends_on: tuple[()] = ()
    empty_rule_binding_hole: EmptyRuleBindingHole


@dataclass(frozen=True, slots=True, kw_only=True, eq=False)
class CallerMoveRuleFillDependencyNode(OperationNode):
    """A Move Rule Fill dependency that must be compared after caller substitution."""

    depends_on: tuple[()] = ()
    caller_move_rule_fill_dependency: CallerMoveRuleFillDependency
