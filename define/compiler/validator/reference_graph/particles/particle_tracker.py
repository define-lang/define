"""Track particle occupancy, identity, and values within an action block."""

from __future__ import annotations

import itertools
import typing

import msgspec

from define.compiler import ast, chained_name
from define.compiler.validator.reference_graph.dead_code import dead_interface_tracker
from define.compiler.validator.reference_graph.particles import (
    callee_guarantee_applier,
    guarantee_generation,
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

    from define.compiler.validator import codegen_input
    from define.compiler.validator.reference_graph import (
        action_contract,
        child_state,
        position_occupancy,
        quality_assignment,
    )
    from define.compiler.validator.reference_graph import (
        destruction_contract as destruction_contract_types,
    )


class ParticleDestruction(msgspec.Struct, frozen=True):
    """A destruction target and its occupied transitive child Positions."""

    position: ast.PositionReference
    facts: list[destruction_contract_types.DestructionFact]

    def positions(self) -> Iterator[ast.PositionReference]:
        """Yield the target Position followed by its transitive child Positions."""
        for fact in self.facts:
            yield fact.destroyed_position_in_destroyer


class OccupancyInfo(msgspec.Struct, frozen=True):
    """A position's error state and occupant, resolved together in one lookup."""

    # When an ancestor is in an error condition we ignore the position entirely,
    # so the occupant is meaningless and left None.
    has_error: bool
    occupant: particle_info.ParticleInfo | None


@typing.final
class ParticleTracker:
    """Tracks which positions contain particles and what qualities those particles currently have."""

    def __init__(self):
        """Initialize an empty particle tracker."""
        self._store = particle_state_store.ParticleStateStore()
        self._dead_interfaces = dead_interface_tracker.DeadInterfaceTracker(self._store)
        self._callee_guarantees = callee_guarantee_applier.CalleeGuaranteeApplier(
            self._store, self._dead_interfaces
        )
        self._requirement_resolver = requirement_resolution.RequirementResolver(
            self._store
        )
        self._guarantee_generator = guarantee_generation.GuaranteeGenerator(self._store)
        self._body_operation_number = 0

    def _delete_subtree(self, key: chained_name.PositionReferenceTuple):
        """Delete everything tracked at or below a Position while preserving interface-rule history."""
        self._store.delete_subtree(key, self._dead_interfaces.mark_particle_destroyed)

    def _record_write(self, *keys: chained_name.PositionReferenceTuple):
        """Record Position state changes at one point in execution order."""
        self._body_operation_number += 1
        for key in keys:
            self._store.record_write(key, self._body_operation_number)

    def mark_error(self, in_position: ast.PositionReference):
        """Mark a position as having error occupancy state."""
        key = in_position.canonical_chained_name_tuple
        self._callee_guarantees.apply_pending_guarantees_up_to(key)
        self._record_write(key)
        self._store.mark_error(key, in_position)

    def assume_empty(self, in_position: ast.PositionReference):
        """Record that a required position starts empty."""
        key = in_position.canonical_chained_name_tuple
        self._callee_guarantees.apply_pending_guarantees_up_to(key)
        self._store.ensure_action_parent(key)
        self._store.mark_emptied(key, in_position)

    def has_error_state(self, in_position: ast.PositionReference) -> bool:
        """Return whether a position or any ancestor has error occupancy state."""
        key = in_position.canonical_chained_name_tuple
        self._callee_guarantees.apply_pending_guarantees_up_to(key)
        return self._store.has_error_in_chain(key)

    def get_occupancy_info(self, in_position: ast.PositionReference) -> OccupancyInfo:
        """Return the error state and occupant of ``in_position`` together.

        This is a performance optimization for the common case of needing both
        whether a position is in an error condition and what particle occupies
        it. It returns exactly what ``has_error_state`` and ``get_occupant``
        would for the same position, so it is only correct to use when both
        answers are about the same position at the same moment; for two different
        positions, ask about each separately. The result is a snapshot of the
        current state, so re-query after any operation that could change the
        position rather than reusing an earlier result.
        """
        key = in_position.canonical_chained_name_tuple
        self._callee_guarantees.apply_pending_guarantees_up_to(key)
        if self._store.has_error_in_chain(key):
            return OccupancyInfo(has_error=True, occupant=None)
        return OccupancyInfo(
            has_error=False,
            occupant=self._store.occupant_or_none(key),
        )

    def unconsumed_action_interfaces(
        self,
    ) -> Iterator[
        tuple[ast.GlobalTypedNameReference, chained_name.PositionReferenceTuple]
    ]:
        """Yield occupied interfaces of callees directly triggered by this action."""
        return self._store.unconsumed_action_interfaces()

    def dead_action_interface_arrivals(self) -> Iterator[ast.PositionReference]:
        """Yield explicit interface arrivals not satisfied by a callee trigger."""
        return self._dead_interfaces.dead_arrivals()

    def is_occupied(self, in_position: ast.PositionReference) -> bool:
        """Return whether a particle exists at this position."""
        key = in_position.canonical_chained_name_tuple
        self._callee_guarantees.apply_pending_guarantees_up_to(key)
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
        self._callee_guarantees.apply_pending_guarantees_up_to(parent_key)
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
        self._callee_guarantees.apply_pending_guarantees_up_to(
            position.canonical_chained_name_tuple
        )
        return self._requirement_resolver.infer_direct_requirements(
            position, required_state, interface_position_names
        )

    def propagate_requirements(
        self,
        requirements_in_caller: Sequence[
            action_contract.PositionRequirementInCaller[
                action_contract.PositionOccupancyRequirement
            ]
        ],
    ) -> list[requirement_resolution.PropagatedRequirement]:
        """Propagate requirements that the current action does not satisfy."""
        self._callee_guarantees.apply_pending_guarantees_up_to_all(
            requirement.caller_position.canonical_chained_name_tuple
            for requirement in requirements_in_caller
        )
        return self._requirement_resolver.propagate_requirements(requirements_in_caller)

    def get_occupant(
        self, in_position: ast.PositionReference
    ) -> particle_info.ParticleInfo:
        """Return the info for the particle at this position."""
        key = in_position.canonical_chained_name_tuple
        self._callee_guarantees.apply_pending_guarantees_up_to(key)
        return self._store.occupant(key)

    def get_occupant_or_none(
        self, in_position: ast.PositionReference
    ) -> particle_info.ParticleInfo | None:
        """Get the particle at this position, if one exists."""
        key = in_position.canonical_chained_name_tuple
        self._callee_guarantees.apply_pending_guarantees_up_to(key)
        return self._store.occupant_or_none(key)

    def get_occupant_or_none_by_key(
        self, key: chained_name.PositionReferenceTuple
    ) -> particle_info.ParticleInfo | None:
        """Get the particle at this position, if one exists."""
        return self._store.occupant_or_none(key)

    def set_value(
        self,
        position: ast.PositionReference,
        value_state: particle_info.ParticleValueState,
    ):
        """Apply a validated Value Setting Statement."""
        self.get_occupant(position).set_value_state(value_state, position.location)
        self._record_write(position.canonical_chained_name_tuple)

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
        self._record_write(position.canonical_chained_name_tuple)

    def snapshot_child_states(
        self, for_positions: Sequence[ast.PositionReference]
    ) -> list[child_state.ChildState]:
        """Capture child occupancy for Positions destroyed together, in order.

        An explicit Destroy has one target; Automatic Destruction targets
        locally defined Positions, each with a single name.

        Each snapshot is decoupled from later tracker mutation. Its keys are
        chained-name suffixes below the snapshotted
        particle, so a caller's snapshot of the same particle shares the key
        space and merges directly.
        """
        keys = [position.canonical_chained_name_tuple for position in for_positions]
        # TODO: Not sure we actually need to fully resolve this; I think there's a world
        # in which we use references somehow here just like we do with normal guarantees.
        self._callee_guarantees.fully_resolve_pending_guarantees(*keys)
        return [self._store.snapshot_child_state(key) for key in keys]

    def discard_discardable_pending_guarantees(self, position: ast.PositionReference):
        """Discard the pending callee Guarantees for this particle's children if each is discardable on destruction and nothing is tracked where it applies."""
        self._callee_guarantees.discard_discardable_pending_guarantees(
            position.canonical_chained_name_tuple
        )

    def collect_caller_destruction_state(
        self,
        occupancies: child_state.ChildOccupancyMap,
        values: child_state.ChildValueMap,
        particles: dict[chained_name.ChainedNameTuple, particle_info.ParticleInfo],
        snapshot: child_state.ChildState,
        for_position: ast.PositionReference,
        position_in_child_state: chained_name.ChainedNameTuple,
        contract_positions: set[chained_name.ChainedNameTuple],
    ):
        """Collect caller particles and additional Child State, keyed by Child State position."""
        key = for_position.canonical_chained_name_tuple
        self._callee_guarantees.fully_resolve_pending_guarantees(key)
        self._store.collect_caller_destruction_state(
            occupancies,
            values,
            particles,
            snapshot,
            key,
            position_in_child_state,
            contract_positions,
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
        self._callee_guarantees.apply_pending_guarantees_up_to(key)
        self._store.ensure_action_parent(key)
        self._record_write(key)
        info = particle_info.ParticleInfo(
            last_position=in_position,
            qualities=qualities,
            origin_position=in_position,
            value_state=particle_info.ParticleValueState.UNSET,
        )
        self._set_occupied(in_position, info)
        self._dead_interfaces.register_explicit_action_interface_arrival(
            in_position, info
        )

    def assume_occupied(
        self,
        in_position: ast.PositionReference,
        qualities: quality_assignment.QualityAssignments,
        *,
        position_in_caller: ast.PositionReference,
    ):
        """Record that a required position starts occupied."""
        key = in_position.canonical_chained_name_tuple
        self._callee_guarantees.apply_pending_guarantees_up_to(key)
        self._store.ensure_action_parent(key)
        self._set_occupied(
            in_position,
            particle_info.ParticleInfo(
                last_position=in_position,
                qualities=qualities,
                origin_position=position_in_caller,
                from_caller=True,
            ),
        )

    def _set_occupied(
        self,
        in_position: ast.PositionReference,
        info: particle_info.ParticleInfo,
    ):
        key = in_position.canonical_chained_name_tuple
        self._store.mark_occupied(key, info)
        self._dead_interfaces.register_occupied_interface_child_position(
            key, info, in_position.location
        )

    def destroy_simultaneously(
        self,
        destructions: Sequence[ParticleDestruction],
    ):
        """Record and apply a simultaneous set of particle destructions.

        Each target includes all its occupied transitive children; targets must
        have disjoint state subtrees.
        """
        positions = (destruction.positions() for destruction in destructions)
        self._callee_guarantees.apply_pending_guarantees_up_to_all(
            position.canonical_chained_name_tuple
            for position in itertools.chain.from_iterable(positions)
        )
        for destruction in destructions:
            self._record_destroyed_state(destruction)

    def _record_destroyed_state(
        self,
        destruction: ParticleDestruction,
    ):
        """Record state changes for a target and its transitive children."""
        # Pending Guarantees compare writes by Position, so children still
        # need write records even though their state is deleted with the parent.
        for fact in itertools.islice(destruction.facts, 1, None):
            child = fact.destroyed_position_in_destroyer
            self._record_write(child.canonical_chained_name_tuple)
        key = destruction.position.canonical_chained_name_tuple
        # Subtree deletion notifies the interface trackers for every removed
        # particle. Only the target's empty state survives the destruction.
        # Destroying puts all children back into a known state (they don't exist).
        self._delete_subtree(key)
        self._record_write(key)
        self._store.mark_emptied(key, destruction.position)

    def get_emptied_by(
        self, position: ast.PositionReference
    ) -> ast.PositionReference | None:
        """Return the position reference that emptied this position, if any."""
        key = position.canonical_chained_name_tuple
        self._callee_guarantees.apply_pending_guarantees_up_to(key)
        return self._store.emptied_by(key)

    def move(self, source: ast.PositionReference, target: ast.PositionReference):
        """Move a particle from one position to another.

        Children of the source position move with it. After the move,
        the source position is marked as emptied.
        """
        from_key = source.canonical_chained_name_tuple
        to_key = target.canonical_chained_name_tuple
        self._callee_guarantees.fully_resolve_pending_guarantees(from_key)
        self._callee_guarantees.apply_pending_guarantees_up_to(to_key)
        self._store.ensure_action_parent(to_key)
        source_info = self._store.occupant(from_key)
        self._dead_interfaces.mark_particle_departed(source_info)
        # Both positions are touched by this one move statement, so they share a
        # body operation number.
        self._record_write(from_key, to_key)
        source_info.last_position = target

        # The target may already exist as an empty node (previously
        # destroyed), and its child positions may have error state. Whatever
        # was below the target no longer exists, so delete it before moving.
        self._delete_subtree(to_key)

        def update_interface_occupancy(
            moved_position: chained_name.PositionReferenceTuple,
            moved_particle: particle_info.ParticleInfo,
        ):
            self._dead_interfaces.replace_occupied_interface_child_position(
                moved_position, moved_particle, target.location
            )

        # Neither position has error state itself, but their child positions
        # can. The particle's children keep their unknown state as they move.
        self._store.move_subtree(from_key, to_key, update_interface_occupancy)
        self._store.mark_emptied(from_key, source)
        self._dead_interfaces.register_explicit_action_interface_arrival(
            target, source_info
        )

    def generate_own_guarantees(
        self,
        interface_names: tuple[ast.TypedName[ast.NameContent], ...],
        implied_quality_names: tuple[ast.GlobalTypedNameReference, ...],
        requirements: dict[
            chained_name.PositionReferenceTuple,
            action_contract.PositionOccupancyRequirement,
        ],
    ) -> dict[chained_name.PositionReferenceTuple, action_contract.PositionGuarantee]:
        """Generate this block's own guarantees, excluding the callee-derived keys carried via nested guarantees.

        The own guarantees come from keys whose first element matches an
        interface or implied quality. ``requirements`` is the validator's
        inferred-requirements dict.
        """
        return self._guarantee_generator.contracted_position_guarantees(
            interface_names,
            implied_quality_names,
            requirements,
        )

    def generate_destructor_guarantees(
        self,
        interface_names: tuple[ast.TypedName[ast.NameContent], ...],
        implied_quality_names: tuple[ast.GlobalTypedNameReference, ...],
        requirements: dict[
            chained_name.PositionReferenceTuple,
            action_contract.PositionOccupancyRequirement,
        ],
    ) -> dict[chained_name.PositionReferenceTuple, action_contract.PositionGuarantee]:
        """Produce every guarantee a destructor makes on its contracted positions.

        Guarantees about implied positions from triggered actions are expanded
        into the destructor's state rather than deferred.
        """
        self._callee_guarantees.fully_resolve_all_pending_guarantees()
        return self._guarantee_generator.contracted_position_guarantees(
            interface_names,
            implied_quality_names,
            requirements,
            is_destructor=True,
        )

    def trigger_action(
        self,
        execution: codegen_input.ActionExecution,
        contract: action_contract.ActionContract,
        *,
        parent_particle: particle_info.ParticleInfo | None,
    ) -> list[tuple[chained_name.PositionReferenceTuple, ast.SourceLocation]]:
        """Record an Action Execution and apply the triggered action's guarantees.

        The callee's own guarantees are applied immediately. Any nested guarantees
        from the callee will be applied lazily during later operations.
        """
        action = execution.action.get_last_action()
        occupied_interface_child_position_violations = (
            self._dead_interfaces.mark_action_triggered(
                action, contract.implied_quality_names, parent_particle
            )
        )
        self._body_operation_number += 1
        self._callee_guarantees.apply_triggered_action(
            execution, contract, self._body_operation_number
        )
        return occupied_interface_child_position_violations

    def nested_guarantees(
        self,
    ) -> list[action_contract.CalleeContract]:
        """Return the guarantees of actions this action triggered."""
        return self._store.nested_guarantees()
