"""Track particle occupancy, identity, and values within an action block."""

from __future__ import annotations

import operator
import typing

from define.compiler import chained_name
from define.compiler.validator.reference_graph.particles import (
    guarantee_generation,
    interface_arrival_tracker,
    particle_info,
    particle_state_store,
    requirement_resolution,
)

if typing.TYPE_CHECKING:
    from collections.abc import (
        Collection,
        Iterator,
        Sequence,
    )
    from collections.abc import Set as AbstractSet

    from define.compiler import ast
    from define.compiler.validator.reference_graph import (
        action_contract,
        position_occupancy,
        quality_assignment,
    )


@typing.final
class ParticleTracker:
    """Tracks which positions contain particles and what qualities those particles currently have.

    Methods that read or change particle state see the state that every
    callee's Guarantees leave.
    """

    def __init__(self):
        """Initialize an empty particle tracker."""
        self._store = particle_state_store.ParticleStateStore()
        self._interface_arrivals = interface_arrival_tracker.InterfaceArrivalTracker()
        self._requirement_resolver = requirement_resolution.RequirementResolver(
            self._store
        )
        self._guarantee_generator = guarantee_generation.GuaranteeGenerator(self._store)

    def mark_error(self, in_position: ast.PositionReference):
        """Mark a position as having error occupancy state."""
        self._store.mark_error(in_position.canonical_chained_name_tuple)

    def mark_error_by_key(self, key: chained_name.PositionReferenceTuple):
        """Mark the position ``key`` as having error occupancy state."""
        self._store.mark_error(key)

    def assume_empty(self, in_position: ast.PositionReference):
        """Record that a required position starts empty."""
        self._store.assume_empty(in_position)

    def has_error_state(self, in_position: ast.PositionReference) -> bool:
        """Return whether a position or any ancestor has error occupancy state."""
        key = in_position.canonical_chained_name_tuple
        return self._store.has_error_in_chain(key)

    def get_occupancy_info(
        self, in_position: ast.PositionReference
    ) -> particle_state_store.OccupancyInfo:
        """Return the error state and occupant of ``in_position`` together.

        It returns exactly what ``has_error_state`` and ``get_occupant_or_none``
        would for the same position, except that the occupant is None when
        the position is in error. The result is a snapshot of the current
        state.
        """
        return self._store.occupancy_info(in_position.canonical_chained_name_tuple)

    def state_without_expanding_by_key(
        self, key: chained_name.PositionReferenceTuple
    ) -> tuple[
        position_occupancy.PositionOccupancyState,
        particle_info.ParticleValueState | None,
    ]:
        """Return the occupancy and value state of a Position whose state is known, reading what callees left without expanding it."""
        return self._store.state_without_expanding(key)

    def unexpanded_entry(
        self, position: ast.PositionReference
    ) -> (
        tuple[
            action_contract.ChildPositionParticles,
            action_contract.ParticleLeftBelow | None,
        ]
        | None
    ):
        """Return what a callee left in ``position``, a child position, that this action never expanded: the map it is in, and its entry, which is None when the position is empty.

        None when this action has expanded what is at ``position``.
        """
        return self._store.unexpanded_entry(position.canonical_chained_name_tuple)

    def unconsumed_action_interfaces(
        self,
    ) -> Iterator[tuple[ast.SourceLocation, chained_name.PositionReferenceTuple]]:
        """Yield each occupied interface position of a callee directly triggered by this action, with where the callee was last triggered."""
        return self._store.unconsumed_action_interfaces()

    def dead_interface_arrivals(self) -> Iterator[ast.PositionReference]:
        """Yield explicit interface arrivals not satisfied by a callee trigger."""
        return self._interface_arrivals.dead_interface_arrivals()

    def is_occupied(self, in_position: ast.PositionReference) -> bool:
        """Return whether a particle exists at this position."""
        key = in_position.canonical_chained_name_tuple
        return self._store.is_occupied(key)

    def first_unoccupied_parent(
        self, position: ast.PositionReference
    ) -> ast.PositionReference | None:
        """Return the first unoccupied parent position in chained-name order.

        The caller must pass a validated chained name.
        """
        key = position.canonical_chained_name_tuple
        parent_key = chained_name.parent_position(key)
        if parent_key is None:
            return None
        deepest_occupied_parent = self._store.longest_occupied_prefix(parent_key)
        occupied_name_count = (
            len(deepest_occupied_parent) if deepest_occupied_parent is not None else 0
        )
        unoccupied_name_count = occupied_name_count + 1
        if unoccupied_name_count == len(position.typed_names):
            return None
        if chained_name.is_action_key(key[unoccupied_name_count - 1]):
            unoccupied_name_count += 1
        if unoccupied_name_count == len(position.typed_names):
            return None
        return position.position_prefix(unoccupied_name_count)

    def infer_direct_requirements(
        self,
        position: ast.PositionReference,
        required_state: position_occupancy.PositionOccupancyState,
        interface_position_names: Collection[str],
    ) -> list[requirement_resolution.ResolvedRequirementPosition]:
        """Infer direct requirements needed by this action."""
        return self._requirement_resolver.infer_direct_requirements(
            position, required_state, interface_position_names
        )

    def propagate_requirements(
        self,
        requirements_in_caller: Sequence[action_contract.OccupancyRequirementInCaller],
    ) -> list[requirement_resolution.PropagatedRequirement]:
        """Propagate requirements that the current action does not satisfy."""
        return self._requirement_resolver.propagate_requirements(requirements_in_caller)

    def get_occupant(
        self, in_position: ast.PositionReference
    ) -> particle_info.ParticleInfo:
        """Return the info for the particle at this position."""
        key = in_position.canonical_chained_name_tuple
        return self._store.occupant(key)

    def get_occupant_or_none(
        self, in_position: ast.PositionReference
    ) -> particle_info.ParticleInfo | None:
        """Get the particle at this position, if one exists."""
        key = in_position.canonical_chained_name_tuple
        return self._store.occupant_or_none(key)

    def occupant_or_none_by_key(
        self, key: chained_name.PositionReferenceTuple
    ) -> particle_info.ParticleInfo | None:
        """Get the particle at ``key``, if one exists."""
        return self._store.occupant_or_none(key)

    def was_placed_by_key(self, key: chained_name.PositionReferenceTuple) -> bool:
        """Return whether a Move or trigger in this action put the particle at ``key``, or a particle above it, in place."""
        return self._store.was_placed(key)

    def set_value(
        self,
        position: ast.PositionReference,
        value_state: particle_info.ParticleValueState,
    ):
        """Apply a validated Value Setting Statement."""
        self.get_occupant(position).set_value_state(value_state, position.location)

    def value_written_at(
        self, key: chained_name.PositionReferenceTuple
    ) -> ast.SourceLocation:
        """Return where this action last wrote the value of the particle at this position."""
        written_at = self._store.occupant(key).value_written_at
        if written_at is None:
            raise ValueError(f"the value of the particle at {key} was not written")
        return written_at

    def mark_value_error(self, position: ast.PositionReference):
        """Suppress further value failures without changing occupancy."""
        self.get_occupant(position).set_value_state(
            particle_info.ParticleValueState.ERROR, position.location
        )

    def state_at(
        self, position: ast.PositionReference
    ) -> particle_state_store.PositionState:
        """Return the state of ``position``, which must have state, expanding what callees left above it. The state must not be changed."""
        return self._store.state_at(position.canonical_chained_name_tuple)

    def transitive_child_states(
        self, position: ast.PositionReference
    ) -> Iterator[
        tuple[chained_name.ChainedNameTuple, particle_state_store.PositionState]
    ]:
        """Yield a ``(names after position, state)`` pair for every transitive child position of ``position`` that has state, where ``position`` has state already. The yielded states must not be changed."""
        return self._store.transitive_child_states(
            position.canonical_chained_name_tuple
        )

    def transitive_child_states_except(
        self,
        position: ast.PositionReference,
        *,
        prefix_for_returned_keys: chained_name.ChainedNameTuple,
        excluded_keys: AbstractSet[chained_name.ChainedNameTuple],
    ) -> Iterator[
        tuple[chained_name.ChainedNameTuple, particle_state_store.PositionState]
    ]:
        """Yield a ``(returned key, state)`` pair for every transitive child position of ``position`` that has state, where ``position`` has state already.

        Each returned key is ``prefix_for_returned_keys`` followed by the
        child position's names after ``position``. A child position whose
        returned key is in ``excluded_keys`` is skipped with all of its own
        transitive child positions. The yielded states must not be changed.
        """
        return self._store.transitive_child_states_except(
            position.canonical_chained_name_tuple,
            prefix_for_returned_keys=prefix_for_returned_keys,
            excluded_keys=excluded_keys,
        )

    def create(
        self,
        in_position: ast.PositionReference,
        qualities: quality_assignment.QualityAssignments,
    ):
        """Record a new particle at this position.

        Args:
            in_position: Where the particle is being created.
            qualities: The qualities this particle has, in assignment order.

        Raises ValueError if the position is already occupied.
        """
        key = in_position.canonical_chained_name_tuple
        info = particle_info.ParticleInfo(
            last_position=in_position,
            qualities=qualities,
            origin_position=in_position,
            value_state=particle_info.ParticleValueState.UNSET,
        )
        self._store.put_particle(key, info)
        self._register_explicit_interface_arrival(in_position, info)

    def assume_occupied(
        self,
        in_position: ast.PositionReference,
        qualities: quality_assignment.QualityAssignments,
        *,
        position_in_caller: ast.PositionReference,
    ):
        """Record that a required position starts occupied."""
        key = in_position.canonical_chained_name_tuple
        info = particle_info.ParticleInfo(
            last_position=in_position,
            qualities=qualities,
            origin_position=position_in_caller,
            source=particle_info.ParticleSource.CALLER,
        )
        self._store.put_particle(key, info)

    def destroy_simultaneously(
        self,
        targets: Sequence[ast.PositionReference],
    ):
        """Record and apply a simultaneous set of particle destructions.

        Each target includes all its occupied transitive children; targets must
        have disjoint state subtrees.
        """
        for target in targets:
            self._store.empty(target)

    def get_emptied_by(
        self, position: ast.PositionReference
    ) -> ast.PositionReference | None:
        """Return the position reference that emptied this position, if any."""
        key = position.canonical_chained_name_tuple
        return self._store.emptied_by(key)

    def move(self, source: ast.PositionReference, target: ast.PositionReference):
        """Move a particle from one position to another.

        Children of the source position move with it. After the move,
        the source position is marked as emptied.
        """
        source_info = self._store.occupant(source.canonical_chained_name_tuple)
        self._interface_arrivals.mark_particle_departed(source_info)
        source_info.last_position = target
        self._store.move(source, target)
        self._register_explicit_interface_arrival(target, source_info)

    def _register_explicit_interface_arrival(
        self, position: ast.PositionReference, particle: particle_info.ParticleInfo
    ):
        """Record a body Create or Move whose target names an action interface."""
        action_chain = position.get_chain_to_last_action()
        if action_chain is None:
            return
        parent_position = action_chain.parent_position()
        parent_particle = (
            self.get_occupant(parent_position) if parent_position is not None else None
        )
        self._interface_arrivals.register(position, parent_particle, particle)

    def generate_own_guarantees(
        self,
        interface_names: tuple[ast.TypedName[ast.NameContent], ...],
        implied_quality_names: tuple[ast.GlobalTypedNameReference, ...],
        requirements: dict[
            chained_name.PositionReferenceTuple,
            action_contract.PositionOccupancyRequirement,
        ],
    ) -> dict[chained_name.PositionReferenceTuple, action_contract.PositionGuarantee]:
        """Generate this block's own guarantees, for every contracted position it tracks.

        A position the block wrote but left in the state it found it in maps
        to None. ``requirements`` is the validator's inferred-requirements
        dict.
        """
        return self._guarantee_generator.contracted_position_guarantees(
            interface_names,
            implied_quality_names,
            requirements,
        )

    def published_guarantees(
        self,
        action: ast.GlobalTypedName[ast.GlobalNameContent[ast.Fqun | None]],
        own_guarantees: dict[
            chained_name.PositionReferenceTuple,
            action_contract.PositionGuarantee,
        ],
        on_destruction: dict[
            chained_name.PositionReferenceTuple, action_contract.OnDestruction
        ],
    ) -> list[action_contract.GuaranteedPosition]:
        """Return the Guarantees this block's contract publishes, with what it left below the particles it created in their Guarantees.

        ``on_destruction`` says what destroying each particle the block left
        below a particle it created takes, by its position from the block's
        parent particle; a particle that is not in it takes nothing.
        """
        return self._guarantee_generator.published_guarantees(
            action, own_guarantees, on_destruction
        )

    def trigger_action(
        self,
        action_chain: ast.ActionReference,
        contract: action_contract.ActionContract,
        *,
        parent_particle: particle_info.ParticleInfo | None,
    ) -> list[tuple[chained_name.PositionReferenceTuple, ast.SourceLocation]]:
        """Record that this action triggered ``action_chain``, and apply the triggered action's guarantees."""
        occupied_interface_child_position_violations = (
            self._occupied_interface_child_positions(
                action_chain, contract.implied_quality_names
            )
        )
        self._mark_interface_arrivals_passed_to_callee(action_chain, parent_particle)
        self._store.trigger(action_chain, contract, parent_particle)
        return occupied_interface_child_position_violations

    def _occupied_interface_child_positions(
        self,
        action: ast.ActionReference,
        implied_quality_names: frozenset[str],
    ) -> list[tuple[chained_name.PositionReferenceTuple, ast.SourceLocation]]:
        """Return the occupied positions that may not hold a particle when this callee triggers, with where each particle arrived."""
        occupied_positions = self._store.occupied_positions_past_an_action(
            action, implied_quality_names
        )
        # This sort keeps multiple diagnostics on the same line/column in deterministic
        # order, and only fires in the error path.
        occupied_positions.sort(key=operator.itemgetter(0))
        return occupied_positions

    def _mark_interface_arrivals_passed_to_callee(
        self,
        action: ast.ActionReference,
        parent_particle: particle_info.ParticleInfo | None,
    ):
        """Satisfy each interface arrival awaiting this callee whose particle is still where it arrived."""
        for particle, arrived_at in self._interface_arrivals.pending_interface_arrivals(
            action, parent_particle
        ):
            # Only a position below an action is registered as an interface arrival.
            arrived_action_chain = typing.cast(
                "ast.ActionReference", arrived_at.get_chain_to_last_action()
            )
            # The callee's particle can have moved since the interface arrival, taking
            # the arrived particle with it.
            position = action.with_position_suffix(
                *arrived_at.typed_names[len(arrived_action_chain.typed_names) :]
            )
            if self.get_occupant_or_none(position) is particle:
                self._interface_arrivals.mark_particle_passed_to_callee(particle)
            else:
                self._interface_arrivals.mark_particle_departed(particle)
