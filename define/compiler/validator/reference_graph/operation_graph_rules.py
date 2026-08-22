"""Calculate Empty and Move Rule dependencies for Operation Graphs."""

from __future__ import annotations

import typing
from collections.abc import Collection, Iterable, Mapping, Sequence
from dataclasses import dataclass

from define.compiler import ast
from define.compiler.validator.reference_graph import operation_graph_model

# Empty Rule Comparison


def _shares_path_with_any(
    position: tuple[str, ...],
    other_positions: Collection[tuple[str, ...]],
    other_position_prefixes: Collection[tuple[str, ...]],
) -> bool:
    if position in other_positions or position in other_position_prefixes:
        return True
    return any(position[:depth] in other_positions for depth in range(1, len(position)))


def _has_related_position(
    positions: tuple[tuple[str, ...], ...],
    other_positions: Collection[tuple[str, ...]],
    other_position_prefixes: Collection[tuple[str, ...]],
) -> bool:
    """Return whether any position shares a parent-child path with another position."""
    for position in positions:
        if _shares_path_with_any(
            position,
            other_positions,
            other_position_prefixes,
        ):
            return True
    return False


def _apply_empty_rule_comparison_most_recent_first[
    DependencyNodeT: operation_graph_model.LastOperationNode
](
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


def apply_empty_rule_comparison[
    DependencyNodeT: operation_graph_model.LastOperationNode
](
    collected_nodes: set[DependencyNodeT],
    callee_collected_operation_positions: Iterable[tuple[str, ...]] = (),
) -> list[DependencyNodeT]:
    """Apply Comparison and return nodes from least to most recent."""
    return _apply_empty_rule_comparison_most_recent_first(
        sorted(collected_nodes, key=lambda item: item.operation_order, reverse=True),
        callee_collected_operation_positions,
    )


# Move Correction and Fill Dependency removal

type _RemovalCandidatesByCanonicalNode = dict[
    operation_graph_model.OperationNode,
    list[operation_graph_model.OperationNode],
]
type _ReplacementDependsOnTargetsByNode = Mapping[
    operation_graph_model.OperationNode,
    Sequence[
        operation_graph_model.ConcreteOperationNode | operation_graph_model.BindingHole
    ],
]


def _canonical_particle_operation_node(
    node: operation_graph_model.OperationNode,
) -> operation_graph_model.OperationNode:
    if isinstance(node, operation_graph_model.GuaranteeNode):
        return node.canonical_node_for_particle_operation
    return node


def _select_removal_candidates[
    DependencyNodeT: operation_graph_model.LastOperationNode
](
    nodes_remaining_after_comparison: Sequence[DependencyNodeT],
    fill_dependency: DependencyNodeT | None,
    *,
    fill_dependency_is_also_empty_dependency: bool,
    has_concrete_caller_nodes: bool,
) -> tuple[
    _RemovalCandidatesByCanonicalNode,
    operation_graph_model.OperationNode | None,
]:
    """Select the nodes that Move Correction or Fill Dependency removal can remove."""
    removal_candidates_by_canonical_node: _RemovalCandidatesByCanonicalNode = {}
    least_recent_removable_node: operation_graph_model.OperationNode | None = None
    nodes_to_consider_for_removal_count = len(nodes_remaining_after_comparison)
    if not has_concrete_caller_nodes:
        # The final list item is the most recent node. Without a callee node, no
        # remaining node can depend on it, so exclude that one item from the prefix
        # scanned for removal. Earlier nodes remain because more recent nodes can
        # depend on them.
        nodes_to_consider_for_removal_count -= 1
    for node_index in range(nodes_to_consider_for_removal_count):
        node = nodes_remaining_after_comparison[node_index]
        is_fill_dependency_removal_target = (
            node is fill_dependency and not fill_dependency_is_also_empty_dependency
        )
        if (
            not isinstance(node, operation_graph_model.MoveNode)
            and not isinstance(node, operation_graph_model.MoveGuaranteeNode)
            and not is_fill_dependency_removal_target
        ):
            continue
        canonical_node = _canonical_particle_operation_node(node)
        removal_candidates_by_canonical_node.setdefault(canonical_node, []).append(node)
        if least_recent_removable_node is None:
            least_recent_removable_node = node
    return removal_candidates_by_canonical_node, least_recent_removable_node


def _dependency_targets_for_removal_traversal(
    node: operation_graph_model.OperationNode,
    replacement_depends_on_targets_by_node: _ReplacementDependsOnTargetsByNode | None,
) -> Iterable[operation_graph_model.OperationNode]:
    replacement_depends_on_targets = None
    if replacement_depends_on_targets_by_node is not None:
        replacement_depends_on_targets = replacement_depends_on_targets_by_node.get(
            node
        )
    if replacement_depends_on_targets is None:
        return node.depends_on
    return (
        dependency
        for dependency in replacement_depends_on_targets
        if isinstance(dependency, operation_graph_model.OperationNode)
    )


def _find_reachable_removal_candidates[
    DependencyNodeT: operation_graph_model.LastOperationNode
](
    nodes_remaining_after_comparison: Sequence[DependencyNodeT],
    concrete_caller_nodes: Collection[operation_graph_model.ConcreteOperationNode],
    removal_candidates_by_canonical_node: _RemovalCandidatesByCanonicalNode,
    least_recent_removable_node: operation_graph_model.OperationNode,
    replacement_depends_on_targets_by_node: _ReplacementDependsOnTargetsByNode | None,
) -> set[operation_graph_model.OperationNode]:
    """Find removal candidates reached by another remaining or caller node."""
    nodes_to_visit: list[operation_graph_model.OperationNode] = list(
        concrete_caller_nodes
    )
    for node in nodes_remaining_after_comparison:
        if node.operation_order <= least_recent_removable_node.operation_order:
            continue
        # A node cannot remove itself, so begin from the nodes it directly depends on.
        nodes_to_visit.extend(
            _dependency_targets_for_removal_traversal(
                node,
                replacement_depends_on_targets_by_node,
            )
        )
    visited: set[operation_graph_model.OperationNode] = set()
    nodes_to_remove: set[operation_graph_model.OperationNode] = set()
    while nodes_to_visit and removal_candidates_by_canonical_node:
        node = nodes_to_visit.pop()
        if node in visited:
            continue
        visited.add(node)
        canonical_node = _canonical_particle_operation_node(node)
        matching_removal_targets = removal_candidates_by_canonical_node.pop(
            canonical_node,
            None,
        )
        if matching_removal_targets is not None:
            nodes_to_remove.update(matching_removal_targets)
        # Every depends_on edge leads to an earlier operation, so continuing past
        # the least recent removable node cannot reach another removable node.
        if node.operation_order <= least_recent_removable_node.operation_order:
            continue
        # A removable node can depend on an earlier removable node, so the nodes it
        # depends on must participate in the same traversal.
        nodes_to_visit.extend(
            _dependency_targets_for_removal_traversal(
                node,
                replacement_depends_on_targets_by_node,
            )
        )
    return nodes_to_remove


def _without_removed_nodes[DependencyNodeT: operation_graph_model.LastOperationNode](
    nodes_remaining_after_comparison: Sequence[DependencyNodeT],
    nodes_to_remove: set[operation_graph_model.OperationNode],
) -> Sequence[DependencyNodeT]:
    if not nodes_to_remove:
        return nodes_remaining_after_comparison
    return [
        node for node in nodes_remaining_after_comparison if node not in nodes_to_remove
    ]


def apply_move_correction_and_fill_dependency_removal[
    DependencyNodeT: operation_graph_model.LastOperationNode
](
    nodes_remaining_after_comparison: Sequence[DependencyNodeT],
    fill_dependency: DependencyNodeT | None,
    concrete_caller_nodes: Collection[operation_graph_model.ConcreteOperationNode] = (),
    *,
    fill_dependency_is_also_empty_dependency: bool = False,
    replacement_depends_on_targets_by_node: _ReplacementDependsOnTargetsByNode
    | None = None,
) -> Sequence[DependencyNodeT]:
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
    (
        removal_candidates_by_canonical_node,
        least_recent_removable_node,
    ) = _select_removal_candidates(
        nodes_remaining_after_comparison,
        fill_dependency,
        fill_dependency_is_also_empty_dependency=(
            fill_dependency_is_also_empty_dependency
        ),
        has_concrete_caller_nodes=bool(concrete_caller_nodes),
    )
    if least_recent_removable_node is None:
        return nodes_remaining_after_comparison
    nodes_to_remove = _find_reachable_removal_candidates(
        nodes_remaining_after_comparison,
        concrete_caller_nodes,
        removal_candidates_by_canonical_node,
        least_recent_removable_node,
        replacement_depends_on_targets_by_node,
    )

    return _without_removed_nodes(nodes_remaining_after_comparison, nodes_to_remove)


# Caller Collection application


def _apply_comparison_to_caller_collection[
    DependencyNodeT: operation_graph_model.LastOperationNode
](
    collected_nodes: set[DependencyNodeT],
    callee_collected_operation_positions: Iterable[tuple[str, ...]],
) -> tuple[list[DependencyNodeT], list[DependencyNodeT]]:
    collected_nodes_most_recent_first = sorted(
        collected_nodes,
        key=lambda item: item.operation_order,
        reverse=True,
    )
    nodes_remaining_after_comparison = _apply_empty_rule_comparison_most_recent_first(
        collected_nodes_most_recent_first,
        callee_collected_operation_positions,
    )
    return nodes_remaining_after_comparison, collected_nodes_most_recent_first


def _apply_empty_rule_to_caller_collection[
    DependencyNodeT: operation_graph_model.LastOperationNode
](
    collected_nodes: set[DependencyNodeT],
    callee_collected_operation_positions: Iterable[tuple[str, ...]],
    concrete_caller_nodes: Collection[operation_graph_model.ConcreteOperationNode],
    *,
    replacement_depends_on_targets_by_node: _ReplacementDependsOnTargetsByNode
    | None = None,
) -> tuple[list[DependencyNodeT], list[DependencyNodeT]]:
    """Apply the Empty Rule using Collection from one direct caller.

    The first list is ordered least to most recent. The second contains every
    collected node from most to least recent.
    """
    (
        nodes_remaining_after_comparison,
        collected_nodes_most_recent_first,
    ) = _apply_comparison_to_caller_collection(
        collected_nodes,
        callee_collected_operation_positions,
    )
    nodes_remaining_after_rule = typing.cast(
        "list[DependencyNodeT]",
        apply_move_correction_and_fill_dependency_removal(
            nodes_remaining_after_comparison,
            None,
            concrete_caller_nodes,
            replacement_depends_on_targets_by_node=(
                replacement_depends_on_targets_by_node
            ),
        ),
    )
    return nodes_remaining_after_rule, collected_nodes_most_recent_first


def _apply_move_rule_to_caller_collection[
    DependencyNodeT: operation_graph_model.LastOperationNode
](
    collected_nodes: set[DependencyNodeT],
    callee_collected_operation_positions: Iterable[tuple[str, ...]],
    concrete_fill_dependency: DependencyNodeT | None,
    concrete_nodes_from_prerequisite_bindings: Collection[
        operation_graph_model.ConcreteOperationNode
    ],
    *,
    fill_dependency_is_also_empty_dependency: bool,
    replacement_depends_on_targets_by_node: _ReplacementDependsOnTargetsByNode,
) -> tuple[list[DependencyNodeT], list[DependencyNodeT]]:
    """Apply the Move Rule using Collection from one direct caller.

    The first list is ordered least to most recent. The second contains every
    collected node from most to least recent.
    """
    fill_dependency_was_collected = concrete_fill_dependency in collected_nodes
    if concrete_fill_dependency is not None:
        collected_nodes.add(concrete_fill_dependency)
    (
        nodes_remaining_after_comparison,
        collected_nodes_most_recent_first,
    ) = _apply_comparison_to_caller_collection(
        collected_nodes,
        callee_collected_operation_positions,
    )
    nodes_remaining_after_rule = typing.cast(
        "list[DependencyNodeT]",
        apply_move_correction_and_fill_dependency_removal(
            nodes_remaining_after_comparison,
            concrete_fill_dependency,
            concrete_nodes_from_prerequisite_bindings,
            fill_dependency_is_also_empty_dependency=(
                fill_dependency_is_also_empty_dependency
                or fill_dependency_was_collected
            ),
            replacement_depends_on_targets_by_node=(
                replacement_depends_on_targets_by_node
            ),
        ),
    )
    return nodes_remaining_after_rule, collected_nodes_most_recent_first


# Child-operation path rules


def _shares_path(one: tuple[str, ...], other: tuple[str, ...]) -> bool:
    """Return whether either child position is a prefix of the other."""
    shared_depth = min(len(one), len(other))
    return one[:shared_depth] == other[:shared_depth]


def operations_not_on_same_paths_as(
    child_operations: operation_graph_model.ParticleChildOperations,
    relative_positions: frozenset[tuple[str, ...]],
) -> list[operation_graph_model.ChildOperation]:
    """Return surviving operations independent of the supplied paths."""
    if not relative_positions:
        return list(child_operations.operations)
    if () in relative_positions:
        return []
    relative_position_prefixes: set[tuple[str, ...]] = set()
    for position in relative_positions:
        relative_position_prefixes.update(
            position[:depth] for depth in range(1, len(position))
        )
    excluded_operations: set[operation_graph_model.ConcreteOperationNode] = set()
    for child_operation in child_operations.operations:
        shares_dependency_path = _shares_path_with_any(
            child_operation.child_position,
            relative_positions,
            relative_position_prefixes,
        )
        if shares_dependency_path:
            excluded_operations.add(child_operation.operation)
    # The Empty Rule compares Particle Operations rather than the individual
    # child positions through which those operations are known.
    return [
        child_operation
        for child_operation in child_operations.operations
        if child_operation.operation not in excluded_operations
    ]


def _apply_empty_rule_comparison_and_move_correction_most_recent_first[
    DependencyNodeT: operation_graph_model.LastOperationNode
](
    collected_nodes: Iterable[DependencyNodeT],
) -> list[DependencyNodeT]:
    """Apply the Empty Rule's Comparison and Move Correction.

    Requires collected nodes to already be sorted most recent to least recent.
    """
    nodes_remaining_after_comparison = _apply_empty_rule_comparison_most_recent_first(
        collected_nodes
    )
    return typing.cast(
        "list[DependencyNodeT]",
        apply_move_correction_and_fill_dependency_removal(
            nodes_remaining_after_comparison,
            None,
        ),
    )


def empty_rule_dependencies_for(
    child_operations: operation_graph_model.ParticleChildOperations,
    relative_position: tuple[str, ...],
) -> tuple[operation_graph_model.ConcreteOperationNode, ...]:
    """Return Empty Rule dependencies on the supplied position's path."""
    matching_operations: list[operation_graph_model.ConcreteOperationNode] = []
    seen_operations: set[operation_graph_model.ConcreteOperationNode] = set()
    for child_operation in child_operations.operations:
        operation = child_operation.operation
        if operation in seen_operations or not _shares_path(
            child_operation.child_position, relative_position
        ):
            continue
        seen_operations.add(operation)
        matching_operations.append(operation)
    return tuple(
        _apply_empty_rule_comparison_and_move_correction_most_recent_first(
            matching_operations,
        )
    )


# Local Empty and Move Rule dependency determination


def _apply_full_move_rule_to_collected_empty_dependencies[
    DependencyNodeT: operation_graph_model.LastOperationNode
](
    empty_dependencies: set[DependencyNodeT],
    fill_dependency: DependencyNodeT | None,
) -> list[DependencyNodeT]:
    """Apply the Move Rule to collected Empty Dependencies."""
    fill_dependency_is_also_empty_dependency = fill_dependency in empty_dependencies
    if fill_dependency is not None:
        empty_dependencies.add(fill_dependency)
    nodes_remaining_after_comparison = apply_empty_rule_comparison(empty_dependencies)
    return typing.cast(
        "list[DependencyNodeT]",
        apply_move_correction_and_fill_dependency_removal(
            nodes_remaining_after_comparison,
            fill_dependency,
            fill_dependency_is_also_empty_dependency=(
                fill_dependency_is_also_empty_dependency
            ),
        ),
    )


def determine_empty_rule_dependencies(
    child_operations: operation_graph_model.ParticleChildOperations,
    empty_position: tuple[str, ...],
    emptied_ancestor: operation_graph_model.LastOperationNode,
) -> operation_graph_model.EmptyOrMoveRuleResult:
    """Return dependencies required by the Empty Rule."""
    return _determine_emptying_dependencies(
        child_operations,
        empty_position,
        None,
        emptied_ancestor,
        is_move_rule=False,
    )


def determine_move_rule_dependencies(
    child_operations: operation_graph_model.ParticleChildOperations,
    empty_position: tuple[str, ...],
    fill_dependency: operation_graph_model.LastOperationNode | None,
    emptied_ancestor: operation_graph_model.LastOperationNode,
) -> operation_graph_model.EmptyOrMoveRuleResult:
    """Return dependencies required by the Move Rule."""
    return _determine_emptying_dependencies(
        child_operations,
        empty_position,
        fill_dependency,
        emptied_ancestor,
        is_move_rule=True,
    )


def _determine_emptying_dependencies(
    child_operations: operation_graph_model.ParticleChildOperations,
    empty_position: tuple[str, ...],
    fill_dependency: operation_graph_model.LastOperationNode | None,
    emptied_ancestor: operation_graph_model.LastOperationNode,
    *,
    is_move_rule: bool,
) -> operation_graph_model.EmptyOrMoveRuleResult:
    collected_nodes: set[operation_graph_model.ConcreteOperationNode] = set()
    caller_requirement_position: tuple[str, ...] | None = None
    # The action received the particle in the state declared by a position
    # requirement rather than putting it in that state itself.
    if isinstance(emptied_ancestor, operation_graph_model.RequirementNode):
        caller_requirement_position = empty_position
    # An earlier Particle Operation in this action supplied the particle
    # being emptied, directly or by operating on one of its parent names.
    else:
        collected_nodes.add(emptied_ancestor)
    collected_nodes.update(
        child_operation.operation for child_operation in child_operations.operations
    )
    fill_dependency_is_also_empty_dependency = fill_dependency in collected_nodes
    # Caller substitution can add collected nodes that affect Move Correction
    # or the Move Rule's Fill Dependency removal, so neither the Empty Rule nor
    # Move Rule can run while a caller-controlled node remains unresolved.
    if caller_requirement_position is None and not isinstance(
        fill_dependency, operation_graph_model.RequirementNode
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
                    ),
                )
            )
    else:
        # A concrete Fill Dependency must participate in the partial Comparison
        # even though caller substitution prevents the remaining phases.
        if is_move_rule and isinstance(
            fill_dependency,
            (
                operation_graph_model.PositionOperationNode,
                operation_graph_model.GuaranteeNode,
            ),
        ):
            collected_nodes.add(fill_dependency)
        local_nodes = apply_empty_rule_comparison(collected_nodes)
    partial_move_rule_comparison_positions = None
    caller_collection = None
    # Caller substitution can add operations to Comparison, while action
    # resolution can change the paths used by Move Correction and Fill
    # Dependency removal. Either case can leave the rule unfinished here.
    unresolved_rule_application_needs_comparison_positions = (
        caller_requirement_position is not None
        or (
            is_move_rule
            and (
                isinstance(fill_dependency, operation_graph_model.RequirementNode)
                or any(
                    node.depends_on_path_contains_guarantee_or_partial_move_rule
                    for node in local_nodes
                )
            )
        )
    )
    # Avoid retaining every operated position when the rule completed locally.
    # An unfinished rule needs them in either the caller Collection or the
    # partial Move Rule result used after action resolution.
    if unresolved_rule_application_needs_comparison_positions:
        collected_operation_positions: list[tuple[str, ...]] = []
        for node in sorted(
            collected_nodes,
            key=lambda item: item.operation_order,
        ):
            collected_operation_positions.extend(node.operated_positions)
        comparison_positions = tuple(collected_operation_positions)
        # The action's caller supplied the particle being emptied, so
        # Collection must continue in the caller before Comparison can finish.
        if caller_requirement_position is not None:
            caller_collection = operation_graph_model.CallerEmptyRuleCollection(
                requirement_position=caller_requirement_position,
                collected_child_operation_positions=(
                    child_operations.child_position_set()
                ),
                fill_dependency_requirement_position=None,
                collected_operation_positions=comparison_positions,
            )
        else:
            partial_move_rule_comparison_positions = comparison_positions
    return operation_graph_model.EmptyOrMoveRuleResult(
        local_nodes,
        caller_collection,
        partial_move_rule_comparison_positions,
        fill_dependency_is_also_empty_dependency,
    )


# Binding Hole dependency traversal


def binding_holes_depended_on_by(
    nodes: Iterable[operation_graph_model.ConcreteOperationNode],
    *,
    caller_binding_holes: Iterable[operation_graph_model.BindingHole] = (),
    replacement_depends_on_targets_by_node: _ReplacementDependsOnTargetsByNode
    | None = None,
) -> tuple[operation_graph_model.BindingHole, ...]:
    """Return Binding Holes the supplied nodes depend on directly or indirectly.

    The result uses deterministic first-encounter order as a stable tie-break;
    the order gives no semantic priority to one Binding Hole over another.
    """
    prerequisite_binding_holes = list(caller_binding_holes)
    # A prerequisite binding can supply the same Binding Hole that a concrete
    # caller node depends on, so mark directly supplied holes visited.
    visited: set[
        operation_graph_model.OperationNode | operation_graph_model.BindingHole
    ] = set(prerequisite_binding_holes)
    nodes_to_visit: list[
        operation_graph_model.OperationNode | operation_graph_model.BindingHole
    ] = []
    # Walk the dependency tree of the passed-in nodes and extract all binding
    # holes.
    for node in nodes:
        nodes_to_visit.append(node)
        while nodes_to_visit:
            current_node = nodes_to_visit.pop()
            if current_node in visited:
                continue
            visited.add(current_node)
            if isinstance(
                current_node,
                (
                    operation_graph_model.ActionParentLastOperationNode,
                    operation_graph_model.RequirementNode,
                    operation_graph_model.EmptyRuleBindingHoleNode,
                    operation_graph_model.EmptyRuleBindingHole,
                    operation_graph_model.MoveRuleBindingHole,
                ),
            ):
                prerequisite_binding_holes.append(current_node)
                continue
            replacement_depends_on_targets = None
            if replacement_depends_on_targets_by_node is not None:
                replacement_depends_on_targets = (
                    replacement_depends_on_targets_by_node.get(current_node)
                )
            if replacement_depends_on_targets is None:
                nodes_to_visit.extend(reversed(current_node.depends_on))
            else:
                nodes_to_visit.extend(reversed(replacement_depends_on_targets))
    return tuple(prerequisite_binding_holes)


# Completing rules after action resolution


def apply_partial_move_rule_result(
    move: operation_graph_model.MoveNodeWithPartialMoveRuleResult,
    replacement_depends_on_targets_by_node: _ReplacementDependsOnTargetsByNode,
) -> tuple[operation_graph_model.MoveRuleApplicationResult, bool]:
    """Finish a partial Move Rule and report whether its depends_on relationships changed."""
    partial_result = move.partial_move_rule_result
    caller_fill_dependency = None
    concrete_fill_dependency = None
    if isinstance(
        partial_result.fill_dependency, operation_graph_model.RequirementNode
    ):
        caller_fill_dependency = operation_graph_model.CallerFillDependency(
            callee_binding_hole=partial_result.fill_dependency,
            requirement=partial_result.fill_dependency.requirement,
        )
    else:
        concrete_fill_dependency = partial_result.fill_dependency

    nodes_remaining_after_comparison = move.depends_on
    nodes_remaining_after_correction = (
        apply_move_correction_and_fill_dependency_removal(
            nodes_remaining_after_comparison,
            concrete_fill_dependency,
            fill_dependency_is_also_empty_dependency=(
                partial_result.fill_dependency_is_also_empty_dependency
            ),
            replacement_depends_on_targets_by_node=(
                replacement_depends_on_targets_by_node
            ),
        )
    )
    application_result = _complete_or_propagate_move_rule(
        nodes_remaining_after_correction,
        caller_empty_rule_collection=partial_result.caller_empty_rule_collection,
        caller_fill_dependency=caller_fill_dependency,
        comparison_positions=partial_result.comparison_positions,
        fill_dependency_is_also_empty_dependency=(
            partial_result.fill_dependency_is_also_empty_dependency
        ),
        caller_binding_holes=(),
        callee_destroy=None,
        replacement_depends_on_targets_by_node=(replacement_depends_on_targets_by_node),
    )
    # A remaining Binding Hole changes the Move's relationships. Otherwise,
    # Move Correction preserves the input sequence when it removes nothing,
    # avoiding a second traversal merely to compare the relationships.
    relationships_changed = (
        application_result.move_rule_binding_hole is not None
        or nodes_remaining_after_correction is not nodes_remaining_after_comparison
    )
    return application_result, relationships_changed


def _complete_or_propagate_move_rule(
    concrete_caller_nodes: Sequence[operation_graph_model.ConcreteOperationNode],
    *,
    caller_empty_rule_collection: (
        operation_graph_model.CallerEmptyRuleCollection | None
    ),
    caller_fill_dependency: operation_graph_model.CallerFillDependency | None,
    comparison_positions: Sequence[tuple[str, ...]],
    fill_dependency_is_also_empty_dependency: bool,
    caller_binding_holes: Iterable[operation_graph_model.BindingHole],
    callee_destroy: operation_graph_model.CalleeDestroy | None,
    replacement_depends_on_targets_by_node: _ReplacementDependsOnTargetsByNode,
) -> operation_graph_model.MoveRuleApplicationResult:
    """Return a complete Move Rule result or its Binding Hole for the next caller."""
    if caller_empty_rule_collection is None and caller_fill_dependency is None:
        return operation_graph_model.MoveRuleApplicationResult(
            concrete_caller_nodes,
            None,
            callee_destroy,
        )
    prerequisite_binding_holes = binding_holes_depended_on_by(
        concrete_caller_nodes,
        caller_binding_holes=caller_binding_holes,
        replacement_depends_on_targets_by_node=(replacement_depends_on_targets_by_node),
    )
    if caller_empty_rule_collection is None:
        move_rule_binding_hole = (
            operation_graph_model.MoveRuleBindingHoleWithCompleteEmptyRuleCollection(
                caller_fill_dependency=caller_fill_dependency,
                fill_dependency_is_also_empty_dependency=(
                    fill_dependency_is_also_empty_dependency
                ),
                prerequisite_binding_holes=prerequisite_binding_holes,
                collected_operation_positions=tuple(comparison_positions),
            )
        )
    else:
        move_rule_binding_hole = (
            operation_graph_model.MoveRuleBindingHoleWithCallerEmptyRuleCollection(
                caller_fill_dependency=caller_fill_dependency,
                fill_dependency_is_also_empty_dependency=(
                    fill_dependency_is_also_empty_dependency
                ),
                prerequisite_binding_holes=prerequisite_binding_holes,
                empty_rule_collection=caller_empty_rule_collection,
            )
        )
    return operation_graph_model.MoveRuleApplicationResult(
        concrete_caller_nodes,
        move_rule_binding_hole,
        callee_destroy,
    )


# Binding rules through direct callers


def _occupied_requirement_position(
    requirement_satisfaction: operation_graph_model.RequirementSatisfaction,
) -> tuple[str, ...] | None:
    if not isinstance(
        requirement_satisfaction.operation,
        operation_graph_model.RequirementNode,
    ):
        return None
    return requirement_satisfaction.operation.requirement.requirement_position


def _add_positions_relative_to_particle(
    relative_positions: set[tuple[str, ...]],
    node: operation_graph_model.ConcreteOperationNode,
    particle_position: tuple[str, ...],
):
    for position in node.operated_positions:
        if not ast.is_prefix(particle_position, position):
            continue
        relative_positions.add(position[len(particle_position) :])


@dataclass(slots=True)
class _CallerEmptyDependencies:
    """Remaining Empty Dependencies collected from one direct caller."""

    collected_nodes: set[operation_graph_model.LastOperationNode]
    requirement_position_in_caller: tuple[str, ...] | None
    collected_child_operation_positions: set[tuple[str, ...]]
    callee_destroy: operation_graph_model.CalleeDestroy | None


def _collect_empty_dependencies_from_caller(
    execution: operation_graph_model.ActionExecution,
    caller_empty_rule_collection: operation_graph_model.CallerEmptyRuleCollection,
) -> _CallerEmptyDependencies:
    """Collect the remaining Empty Dependencies from one direct caller."""
    particle_requirement_satisfaction = execution.requirement_satisfactions[
        caller_empty_rule_collection.requirement_position
    ]
    child_operations = operations_not_on_same_paths_as(
        particle_requirement_satisfaction.child_operations,
        caller_empty_rule_collection.collected_child_operation_positions,
    )
    collected_nodes: set[operation_graph_model.LastOperationNode] = {
        child_operation.operation for child_operation in child_operations
    }
    fill_dependency_requirement_position = (
        caller_empty_rule_collection.fill_dependency_requirement_position
    )
    if fill_dependency_requirement_position is not None:
        # The Fill Rule allows an EMPTY requirement to depend on an
        # operation on any parent position. Search the required position
        # and its parent-position prefixes for that operation.
        for depth in range(len(fill_dependency_requirement_position), 0, -1):
            callee_requirement_position = fill_dependency_requirement_position[:depth]
            requirement_satisfaction = execution.requirement_satisfactions.get(
                callee_requirement_position
            )
            if requirement_satisfaction is None:
                continue
            # The Move Rule combines the Empty Dependencies for the source
            # position with the Fill Dependency for the target position, then
            # applies Comparison. When the Fill Dependency operates on a
            # transitive parent position of the source, a more recent Particle
            # Operation on the source or one of its transitive child positions
            # remains after Comparison.
            if not ast.is_prefix(
                callee_requirement_position,
                caller_empty_rule_collection.requirement_position,
            ):
                # Destruction Contract contributions do not yet propagate a
                # callee Destroy through an intermediate caller's Fill Dependency.
                collected_nodes.add(
                    typing.cast(
                        "operation_graph_model.LastOperationNode",
                        requirement_satisfaction.operation,
                    )
                )
            break

    requirement_position_in_caller = _occupied_requirement_position(
        particle_requirement_satisfaction
    )
    callee_destroy = None
    # When the requirement is satisfied in this caller and no child Particle
    # Operation supplies an Empty Dependency, its satisfying operation is the
    # remaining Empty Dependency. A callee Destroy is returned separately.
    if (
        requirement_position_in_caller is None
        and not child_operations
        and not caller_empty_rule_collection.collected_child_operation_positions
    ):
        if isinstance(
            particle_requirement_satisfaction.operation,
            operation_graph_model.CalleeDestroy,
        ):
            callee_destroy = particle_requirement_satisfaction.operation
        else:
            collected_nodes.add(particle_requirement_satisfaction.operation)

    collected_child_operation_positions: set[tuple[str, ...]] = set()
    if requirement_position_in_caller is not None:
        collected_child_operation_positions.update(
            child_operation.child_position
            for child_operation in particle_requirement_satisfaction.child_operations.operations
        )
        collected_child_operation_positions.update(
            caller_empty_rule_collection.collected_child_operation_positions
        )
    return _CallerEmptyDependencies(
        collected_nodes,
        requirement_position_in_caller,
        collected_child_operation_positions,
        callee_destroy,
    )


def apply_empty_rule_binding_hole_in_caller(
    execution: operation_graph_model.ActionExecution,
    empty_rule_binding_hole: operation_graph_model.EmptyRuleBindingHole,
    empty_rule_binding_inputs: operation_graph_model.EmptyRuleBindingInputs,
    *,
    replacement_depends_on_targets_by_node: _ReplacementDependsOnTargetsByNode
    | None = None,
) -> operation_graph_model.EmptyRuleApplicationResult:
    """Bind the callee's Empty Rule Binding Hole in one direct caller."""
    caller_empty_dependencies = _collect_empty_dependencies_from_caller(
        execution,
        empty_rule_binding_hole,
    )

    collected_operation_positions = [
        ast.chain_in_caller(execution.action_chain, position)
        for position in empty_rule_binding_hole.collected_operation_positions
    ]
    (
        caller_nodes,
        collected_nodes_most_recent_first,
    ) = _apply_empty_rule_to_caller_collection(
        caller_empty_dependencies.collected_nodes,
        collected_operation_positions,
        empty_rule_binding_inputs.concrete_caller_nodes,
        replacement_depends_on_targets_by_node=(replacement_depends_on_targets_by_node),
    )
    requirement_position_in_caller = (
        caller_empty_dependencies.requirement_position_in_caller
    )
    if requirement_position_in_caller is None:
        return operation_graph_model.EmptyRuleApplicationResult(
            caller_nodes,
            None,
        )

    caller_nodes_for_next_substitution: list[
        operation_graph_model.ConcreteOperationNode
    ] = []
    fill_dependency_requirement_position: tuple[str, ...] | None = None
    for node in caller_nodes:
        if isinstance(node, operation_graph_model.RequirementNode):
            fill_dependency_requirement_position = node.requirement.requirement_position
            continue
        caller_nodes_for_next_substitution.append(node)
        # This remains linear in the operated positions because each position
        # is examined once, without comparing nodes.
        _add_positions_relative_to_particle(
            caller_empty_dependencies.collected_child_operation_positions,
            node,
            requirement_position_in_caller,
        )

    for node in reversed(collected_nodes_most_recent_first):
        collected_operation_positions.extend(node.operated_positions)
    prerequisite_binding_holes = binding_holes_depended_on_by(
        (
            *empty_rule_binding_inputs.concrete_caller_nodes,
            *caller_nodes_for_next_substitution,
        ),
        caller_binding_holes=empty_rule_binding_inputs.caller_binding_holes,
    )
    return operation_graph_model.EmptyRuleApplicationResult(
        typing.cast(
            "list[operation_graph_model.LastOperationNode]",
            caller_nodes_for_next_substitution,
        ),
        operation_graph_model.EmptyRuleBindingHole(
            requirement_position=requirement_position_in_caller,
            collected_child_operation_positions=frozenset(
                caller_empty_dependencies.collected_child_operation_positions
            ),
            fill_dependency_requirement_position=(fill_dependency_requirement_position),
            collected_operation_positions=tuple(collected_operation_positions),
            prerequisite_binding_holes=prerequisite_binding_holes,
        ),
    )


def apply_move_rule_binding_hole_in_caller(
    execution: operation_graph_model.ActionExecution,
    move_rule_binding_hole: operation_graph_model.MoveRuleBindingHole,
    empty_rule_binding_inputs: operation_graph_model.EmptyRuleBindingInputs,
    *,
    replacement_depends_on_targets_by_node: _ReplacementDependsOnTargetsByNode,
) -> operation_graph_model.MoveRuleApplicationResult:
    """Apply a callee Move Rule Binding Hole using one direct caller."""
    caller_empty_rule_collection = move_rule_binding_hole.caller_empty_rule_collection
    if caller_empty_rule_collection is None:
        collected_nodes: set[operation_graph_model.ConcreteOperationNode] = set()
        requirement_position_in_caller = None
        collected_child_operation_positions: set[tuple[str, ...]] = set()
        callee_destroy = None
    else:
        caller_empty_dependencies = _collect_empty_dependencies_from_caller(
            execution,
            caller_empty_rule_collection,
        )
        requirement_position_in_caller = (
            caller_empty_dependencies.requirement_position_in_caller
        )
        collected_child_operation_positions = (
            caller_empty_dependencies.collected_child_operation_positions
        )
        callee_destroy = caller_empty_dependencies.callee_destroy
        collected_nodes = typing.cast(
            "set[operation_graph_model.ConcreteOperationNode]",
            caller_empty_dependencies.collected_nodes,
        )

    fill_dependency = move_rule_binding_hole.caller_fill_dependency
    if fill_dependency is not None:
        fill_dependency = execution.resolve_move_rule_fill_dependency(fill_dependency)
    match fill_dependency:
        case (
            operation_graph_model.PositionOperationNode()
            | operation_graph_model.GuaranteeNode()
        ):
            concrete_fill_dependency = fill_dependency
            caller_fill_dependency = None
        case operation_graph_model.CallerFillDependency() | None:
            concrete_fill_dependency = None
            caller_fill_dependency = fill_dependency

    comparison_positions = [
        ast.chain_in_caller(execution.action_chain, position)
        for position in move_rule_binding_hole.comparison_positions
    ]
    (
        concrete_caller_nodes,
        collected_nodes_most_recent_first,
    ) = _apply_move_rule_to_caller_collection(
        collected_nodes,
        comparison_positions,
        concrete_fill_dependency,
        empty_rule_binding_inputs.concrete_caller_nodes,
        fill_dependency_is_also_empty_dependency=(
            move_rule_binding_hole.fill_dependency_is_also_empty_dependency
        ),
        replacement_depends_on_targets_by_node=(replacement_depends_on_targets_by_node),
    )
    next_caller_empty_rule_collection = None
    if requirement_position_in_caller is not None or caller_fill_dependency is not None:
        for node in reversed(collected_nodes_most_recent_first):
            comparison_positions.extend(node.operated_positions)
        if requirement_position_in_caller is not None:
            for node in concrete_caller_nodes:
                _add_positions_relative_to_particle(
                    collected_child_operation_positions,
                    node,
                    requirement_position_in_caller,
                )
            next_caller_empty_rule_collection = (
                operation_graph_model.CallerEmptyRuleCollection(
                    requirement_position=requirement_position_in_caller,
                    collected_child_operation_positions=frozenset(
                        collected_child_operation_positions
                    ),
                    fill_dependency_requirement_position=None,
                    collected_operation_positions=tuple(comparison_positions),
                )
            )
    return _complete_or_propagate_move_rule(
        concrete_caller_nodes,
        caller_empty_rule_collection=next_caller_empty_rule_collection,
        caller_fill_dependency=caller_fill_dependency,
        comparison_positions=comparison_positions,
        fill_dependency_is_also_empty_dependency=(
            move_rule_binding_hole.fill_dependency_is_also_empty_dependency
        ),
        caller_binding_holes=empty_rule_binding_inputs.caller_binding_holes,
        callee_destroy=callee_destroy,
        replacement_depends_on_targets_by_node=(replacement_depends_on_targets_by_node),
    )
