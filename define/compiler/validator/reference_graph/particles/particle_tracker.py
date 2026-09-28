"""Track particle occupancy, identity, and values within an action block."""

from __future__ import annotations

import itertools
import typing

import msgspec

from define.compiler import ast
from define.compiler.validator.reference_graph import (
    action_contract,
    child_state,
    position_occupancy,
    quality_assignment,
)
from define.compiler.validator.reference_graph import (
    destruction_contract as destruction_contract_types,
)
from define.compiler.validator.reference_graph.dead_code import dead_interface_tracker
from define.compiler.validator.reference_graph.particles import (
    callee_guarantee_applier,
    particle_info,
    particle_state_store,
)

if typing.TYPE_CHECKING:
    from collections.abc import (
        Collection,
        Iterator,
        Sequence,
    )

    from define.compiler.validator import codegen_input


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
class ParticleTracker:
    """Tracks which positions contain particles and what qualities those particles currently have."""

    def __init__(self):
        """Initialize an empty particle tracker."""
        self._store = particle_state_store.ParticleStateStore()
        self._dead_interfaces = dead_interface_tracker.DeadInterfaceTracker(self._store)
        self._callee_guarantees = callee_guarantee_applier.CalleeGuaranteeApplier(
            self._store, self._dead_interfaces
        )
        self._body_operation_number = 0

    def _delete_subtree(self, key: ast.ChainedNameTuple):
        """Delete everything tracked at or below a Position while preserving interface-rule history."""
        self._store.delete_subtree(key, self._dead_interfaces.mark_particle_destroyed)

    def _record_write(self, *keys: ast.ChainedNameTuple):
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
    ) -> Iterator[tuple[ast.GlobalTypedNameReference, ast.ChainedNameTuple]]:
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
        immediate_parent = position.parent_position()
        if immediate_parent is None:
            return None
        parent_key = immediate_parent.canonical_chained_name_tuple
        self._callee_guarantees.apply_pending_guarantees_up_to(parent_key)
        deepest_occupied_parent = self._store.longest_occupied_prefix(parent_key)
        occupied_name_count = (
            len(deepest_occupied_parent) if deepest_occupied_parent is not None else 0
        )
        unoccupied_name_count = occupied_name_count + 1
        if unoccupied_name_count == len(position.typed_names):
            return None
        if (
            position.typed_names[unoccupied_name_count - 1].name_type
            == ast.NameType.ACTION
        ):
            unoccupied_name_count += 1
        if unoccupied_name_count == len(position.typed_names):
            return None
        return position.position_prefix(unoccupied_name_count)

    def infer_direct_requirements(
        self,
        position: ast.PositionReference,
        required_state: position_occupancy.PositionOccupancyState,
        interface_position_names: Collection[str],
    ) -> list[ResolvedRequirementPosition]:
        """Infer direct requirements needed by this action."""
        self._callee_guarantees.apply_pending_guarantees_up_to(
            position.canonical_chained_name_tuple
        )
        position_is_contracted = (
            position.starts_with_global
            or position.typed_names[0].full_typed_name in interface_position_names
        )
        canonical_position_prefixes: list[ast.ChainedNameTuple] = []
        canonical_position = position.canonical_chained_name_tuple
        for name_index, typed_name in enumerate(position.typed_names):
            if typed_name.name_type == ast.NameType.ACTION:
                break
            canonical_position_prefixes.append(canonical_position[: name_index + 1])
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
            contracted_position = self._contracted_position_for_requirement(
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
        self._callee_guarantees.apply_pending_guarantees_up_to_all(canonical_positions)
        propagated_requirements: list[PropagatedRequirement] = []
        for requirement_index, nearest_particle in self._requirement_indices_for_caller(
            canonical_positions
        ):
            requirement_in_caller = requirements_in_caller[requirement_index]
            position = requirement_in_caller.caller_position
            contracted_position = self._contracted_position_for_requirement(
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
        canonical_positions: Sequence[ast.ChainedNameTuple],
    ) -> Iterator[
        tuple[int, tuple[tuple[str, ...], particle_info.ParticleInfo] | None]
    ]:
        """Yield indices of requirements that the caller must fulfill.

        Each requirement index is paired with the nearest particle passed in by
        the caller, or ``None`` when no parent position is occupied.
        """
        parent_positions: list[ast.ChainedNameTuple] = []
        unresolved_requirements: list[tuple[int, ast.ChainedNameTuple | None]] = []
        for requirement_index, canonical_position in enumerate(canonical_positions):
            # If we have touched a position, then the current action overrides any
            # requirements from its callees.
            if self._store.has_error_in_chain(
                canonical_position
            ) or self._store.has_known_occupancy(canonical_position):
                continue
            parent_position = (
                canonical_position[:-1] if len(canonical_position) > 1 else None
            )
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
        self,
        position: ast.PositionReference,
        nearest_particle: tuple[tuple[str, ...], particle_info.ParticleInfo] | None,
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

    def set_value(
        self,
        position: ast.PositionReference,
        value_state: particle_info.ParticleValueState,
    ):
        """Apply a validated Value Setting Statement."""
        self.get_occupant(position).set_value_state(value_state)
        self._record_write(position.canonical_chained_name_tuple)

    def mark_value_error(self, position: ast.PositionReference):
        """Suppress further value failures without changing occupancy."""
        self.get_occupant(position).set_value_state(
            particle_info.ParticleValueState.ERROR
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

    def collect_caller_destruction_state(
        self,
        occupancies: child_state.ChildOccupancyMap,
        values: child_state.ChildValueMap,
        snapshot: child_state.ChildState,
        for_position: ast.PositionReference,
        position_in_child_state: tuple[str, ...],
        contract_positions: set[tuple[str, ...]],
    ) -> dict[ast.ChainedNameTuple, particle_info.ParticleInfo]:
        """Collect caller particles and additional Child State."""
        key = for_position.canonical_chained_name_tuple
        self._callee_guarantees.fully_resolve_pending_guarantees(key)
        return self._store.collect_caller_destruction_state(
            occupancies,
            values,
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
            moved_position: ast.ChainedNameTuple,
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
            tuple[str, ...], action_contract.PositionOccupancyRequirement
        ],
    ) -> dict[ast.ChainedNameTuple, action_contract.PositionGuarantee]:
        """Generate this block's own guarantees, excluding the callee-derived keys carried via nested guarantees.

        The own guarantees come from keys whose first element matches an
        interface or implied quality. ``requirements`` is the validator's
        inferred-requirements dict.
        """
        return self._collect_contracted_position_guarantees(
            interface_names,
            implied_quality_names,
            requirements,
        )

    def generate_destructor_guarantees(
        self,
        interface_names: tuple[ast.TypedName[ast.NameContent], ...],
        implied_quality_names: tuple[ast.GlobalTypedNameReference, ...],
        requirements: dict[
            tuple[str, ...], action_contract.PositionOccupancyRequirement
        ],
    ) -> dict[ast.ChainedNameTuple, action_contract.PositionGuarantee]:
        """Produce every guarantee a destructor makes on its contracted positions.

        Guarantees about implied positions from triggered actions are expanded
        into the destructor's state rather than deferred.
        """
        self._callee_guarantees.fully_resolve_pending_guarantees(())
        return self._collect_contracted_position_guarantees(
            interface_names,
            implied_quality_names,
            requirements,
            is_destructor=True,
        )

    def _collect_contracted_position_guarantees(
        self,
        interface_names: tuple[ast.TypedName[ast.NameContent], ...],
        implied_quality_names: tuple[ast.GlobalTypedNameReference, ...],
        requirements: dict[
            tuple[str, ...], action_contract.PositionOccupancyRequirement
        ],
        *,
        is_destructor: bool = False,
    ) -> dict[ast.ChainedNameTuple, action_contract.PositionGuarantee]:
        """Collect and sort the guarantees for every contracted key, excluding the ones _guarantee_for_key reports as no-ops."""
        include_names = {
            name.full_typed_name for name in (*interface_names, *implied_quality_names)
        }

        # generate_own_guarantees excludes keys that came only from our caleees.
        # generate_destructor_guarantees includes callee-derived keys.
        all_keys = self._store.keys_for_guarantees(include_callee_derived=is_destructor)

        guarantees: list[
            tuple[ast.ChainedNameTuple, action_contract.PositionGuarantee]
        ] = []
        for key in all_keys:
            # Consuming a callee's Interface Position must also override its
            # nested Guarantee when our caller later applies that Guarantee.
            # Destructors resolve all nested Guarantees here, and their callees'
            # Interface Positions are not Positions they must preserve.
            if is_destructor and any(ast.is_action_key(name) for name in key):
                continue
            first_element = key[0]
            # Any position that starts with a global is contracted, even if it was updated
            # by an implied action and we can't see it directly.
            if first_element not in include_names and not ast.chain_starts_with_global(
                key
            ):
                continue
            guarantee = self._guarantee_for_key(key, requirements)
            if guarantee is None:
                continue
            guarantees.append((key, guarantee))

        # Parent-before-child ordering: Our first sort is by the key length
        # (the number of names in a chain). To understand why this is necessary,
        # imagine we do this:
        #
        #   move position<item> to position<dest>.
        #   create a particle in position<dest>::position</child>.
        #
        # We have to process the move from item to dest first, to understand
        # that what's in dest is the particle that was originally in
        # item. Only _then_ should we process the creation in position</child>,
        # so that we understand that we are creating a particle in a child
        # of what was originally in "item." Sorting by key length guarantees this
        # property.
        #
        # Execution order: Within the same key length, sorting
        # by caused_by (source position) is also required. For example, if
        # an action does:
        #
        #   move position<item>::position</child> to position<dest>.
        #   move position<item> to position<_sink>.
        #
        # Both of these show up as guarantees in the final output about
        # single-item positions: position<dest> has a guarantee that it
        # contains what was originally in position<item>::position</child>,
        # and position<item> has a guarantee that it's empty. (Remember that
        # guarantees show up entirely using the names of the _final destinations_,
        # so there is no guarantee emitted here about position<item>::position</child>---
        # it's automatically emptied by position<item> being emptied.)
        #
        # Thus, we must process position</child> being in position<dest> before
        # we process that position<item> is empty. Otherwise we would delete
        # the particle in position</child> incorrectly.
        guarantees.sort(
            key=lambda item: (
                len(item[0]),
                item[1].caused_by.location.line,
                item[1].caused_by.location.column,
            ),
        )
        return dict(guarantees)

    def _guarantee_for_key(
        self,
        key: tuple[str, ...],
        requirements: dict[
            tuple[str, ...], action_contract.PositionOccupancyRequirement
        ],
    ) -> action_contract.PositionGuarantee | None:
        """Build a guarantee describing the current tracker state, or None for no-ops.

        A position whose state is identical to the action's starting state, but
        that the action operated on, gets an UnchangedGuarantee. A position that
        was left in its assumed starting state without ever being written produces None.
        """
        error_caused_by = self._store.error_caused_by(key)
        if error_caused_by is not None:
            return action_contract.ErrorGuarantee(
                caused_by=error_caused_by,
            )

        info = self._store.occupant_or_none(key)
        if info is not None:
            if not info.from_caller:
                return action_contract.OccupiedByNewGuarantee(
                    qualities=info.qualities,
                    origin_position=info.origin_position,
                    caused_by=info.last_position,
                    value_effect=typing.cast(
                        "particle_info.ParticleValueState", info.value_state
                    ),
                )
            if (
                key != info.origin_position.canonical_chained_name_tuple
                or info.value_written
                or info.value_state == particle_info.ParticleValueState.ERROR
            ):
                return action_contract.OccupiedByExistingGuarantee(
                    origin_position=info.origin_position,
                    caused_by=info.last_position,
                    value_effect=info.value_effect(),
                )
            # The caller's particle is right where it started.
            if self._store.was_written(key):
                return action_contract.UnchangedGuarantee(
                    caused_by=info.last_position,
                )
            # An assumed particle can remain untouched, including the trigger particle.
            #
            # TODO: Should we simply require people to always touch the trigger
            # position? It eliminates a lot of "more than one way to do it."
            return None

        # keys_for_guarantees returns an unoccupied Position without error
        # state only when it is known to be empty.
        caused_by = typing.cast("ast.PositionReference", self._store.emptied_by(key))
        requirement = requirements.get(key)
        if (
            requirement is not None
            and requirement.required_state
            == position_occupancy.PositionOccupancyState.EMPTY
        ):
            # A requirement propagated from a callee doesn't mean the callee
            # operated on that position directly. (It could have been a transitive
            # callee that did it.)
            if self._store.was_written(key):
                return action_contract.UnchangedGuarantee(
                    caused_by=caused_by,
                )
            return None
        return action_contract.EmptyGuarantee(
            caused_by=caused_by,
        )

    def trigger_action(
        self,
        execution: codegen_input.ActionExecution,
        contract: action_contract.ActionContract,
        *,
        parent_particle: particle_info.ParticleInfo | None,
    ) -> list[tuple[ast.ChainedNameTuple, ast.SourceLocation]]:
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
