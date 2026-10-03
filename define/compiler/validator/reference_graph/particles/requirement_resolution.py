"""Resolve Position Requirements against the particle state an action has built so far."""

from __future__ import annotations

import typing

import msgspec

from define.compiler import ast, chained_name
from define.compiler.validator.reference_graph import (
    action_contract,
    position_occupancy,
)

if typing.TYPE_CHECKING:
    from collections.abc import Collection, Iterator, Sequence

    from define.compiler.validator.reference_graph.particles import (
        particle_info,
        particle_state_store,
    )


class ResolvedRequirementPosition(msgspec.Struct, frozen=True):
    """A local requirement position and the contracted position it resolves to."""

    local_position: ast.PositionReference
    contracted_position: ast.PositionReference
    required_state: position_occupancy.PositionOccupancyState


class PropagatedRequirement(msgspec.Struct, frozen=True):
    """A callee requirement that must be propagated into the current contract."""

    requirement_in_caller: action_contract.PositionRequirementInCaller[
        action_contract.PositionOccupancyRequirement
    ]
    contracted_position: ast.PositionReference


@typing.final
class RequirementResolver:
    """Resolves Position Requirements against the particle state an action has built so far."""

    def __init__(self, store: particle_state_store.ParticleStateStore):
        """Resolve requirements against ``store``."""
        self._store = store

    def infer_direct_requirements(
        self,
        position: ast.PositionReference,
        required_state: position_occupancy.PositionOccupancyState,
        interface_position_names: Collection[str],
    ) -> list[ResolvedRequirementPosition]:
        """Infer direct requirements needed by this action."""
        position_is_contracted = (
            position.starts_with_global
            or position.typed_names[0].full_typed_name in interface_position_names
        )
        canonical_position_prefixes = (
            chained_name.position_prefixes_before_first_action(
                position.canonical_chained_name_tuple
            )
        )
        resolved_positions: list[ResolvedRequirementPosition] = []
        for requirement_index, nearest_particle in self._requirement_indices_for_caller(
            canonical_position_prefixes
        ):
            # A non-contracted position contributes an Action Requirement only
            # when a parent position has a particle passed in by the caller.
            # We do this check early before constructing PositionReference objects
            # or doing any other work. This is an important performance improvement.
            if nearest_particle is None and not position_is_contracted:
                continue
            requirement_position = position.position_prefix(
                len(canonical_position_prefixes[requirement_index])
            )
            contracted_position = _contracted_position_for_requirement(
                requirement_position, nearest_particle
            )
            requirement_state = (
                required_state
                if requirement_position is position
                else position_occupancy.PositionOccupancyState.OCCUPIED
            )
            resolved_positions.append(
                ResolvedRequirementPosition(
                    local_position=requirement_position,
                    contracted_position=contracted_position,
                    required_state=requirement_state,
                )
            )
        return resolved_positions

    # Requirement propagation can query dozens or hundreds of positions for each
    # triggered action and millions over a large action call graph. Keeping this
    # operation batched lets trie lookup reuse common position prefixes instead
    # of repeating the ancestor search for every requirement. This is an important
    # performance optimization in the design of the compiler.
    def propagate_requirements(
        self,
        requirements_in_caller: Sequence[
            action_contract.PositionRequirementInCaller[
                action_contract.PositionOccupancyRequirement
            ]
        ],
    ) -> list[PropagatedRequirement]:
        """Propagate requirements that the current action does not satisfy.

        There are two different propagation situations:
        1. The callee's parent position was created by our caller, in which case
           we propagate all requirements that the current action did not satisfy.
        2. The callee's parent position was created by us (the current action) in
           which case we only propagate requirements when one of the particles
           in the callee's contracted positions came from our caller.

        To understand Case 2: it happens when the _parent_ particle of one of our
        contracted positions was moved by us (the current action) from one of our
        _own_ contracted positions. For example, let's say the requirement is on
        interface::b::c. We had our_interface with ::b::c as child positions, but
        all we did in this action is "move our_interface to interface." We don't
        actually _know_ the state of "b" and its child "c". Only our caller knows.
        """
        canonical_positions = [
            requirement.caller_position.canonical_chained_name_tuple
            for requirement in requirements_in_caller
        ]
        propagated_requirements: list[PropagatedRequirement] = []
        for requirement_index, nearest_particle in self._requirement_indices_for_caller(
            canonical_positions
        ):
            requirement_in_caller = requirements_in_caller[requirement_index]
            position = requirement_in_caller.caller_position
            contracted_position = _contracted_position_for_requirement(
                position, nearest_particle
            )
            # Interfaces stop inference: no caller may occupy an action
            # interface position before triggering this action, so this action
            # must satisfy the requirement itself.
            if contracted_position.get_last_action() is not None:
                continue
            propagated_requirements.append(
                PropagatedRequirement(
                    requirement_in_caller=requirement_in_caller,
                    contracted_position=contracted_position,
                )
            )
        return propagated_requirements

    def _requirement_indices_for_caller(
        self,
        canonical_positions: Sequence[chained_name.PositionReferenceTuple],
    ) -> Iterator[
        tuple[
            int,
            tuple[chained_name.PositionReferenceTuple, particle_info.ParticleInfo]
            | None,
        ]
    ]:
        """Yield indices of requirements that the caller must fulfill.

        Each requirement index is paired with the nearest particle passed in by
        the caller, or ``None`` when no parent position is occupied.
        """
        parent_positions: list[chained_name.PositionReferenceTuple] = []
        unresolved_requirements: list[
            tuple[int, chained_name.PositionReferenceTuple | None]
        ] = []
        for requirement_index, canonical_position in enumerate(canonical_positions):
            # If we have touched a position, then the current action overrides any
            # requirements from its callees.
            if self._store.has_known_occupancy_or_error(canonical_position):
                continue
            parent_position = chained_name.parent_position(canonical_position)
            unresolved_requirements.append((requirement_index, parent_position))
            if parent_position is not None:
                parent_positions.append(parent_position)
        nearest_ancestors = self._store.nearest_occupied_ancestors(parent_positions)
        for requirement_index, parent_position in unresolved_requirements:
            nearest_particle = (
                nearest_ancestors[parent_position]
                if parent_position is not None
                else None
            )
            if nearest_particle is None or nearest_particle[1].from_caller:
                yield requirement_index, nearest_particle


def _contracted_position_for_requirement(
    position: ast.PositionReference,
    nearest_particle: tuple[
        chained_name.PositionReferenceTuple, particle_info.ParticleInfo
    ]
    | None,
) -> ast.PositionReference:
    if nearest_particle is None:
        return position
    owner_key, owner = nearest_particle
    if owner_key == owner.origin_position.canonical_chained_name_tuple:
        return position
    return ast.PositionReference(
        location=position.location,
        typed_names=(
            *owner.origin_position.typed_names,
            *position.typed_names[len(owner_key) :],
        ),
    )
