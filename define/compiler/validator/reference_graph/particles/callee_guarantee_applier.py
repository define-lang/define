"""Apply callee Guarantees to the particle state store, deferring nested Guarantees until they are needed."""

from __future__ import annotations

import typing

import msgspec

from define.compiler import chained_name
from define.compiler.validator.reference_graph import action_contract
from define.compiler.validator.reference_graph.particles import (
    particle_info,
    particle_state_store,
    pending_guarantee,
)

if typing.TYPE_CHECKING:
    from collections.abc import Iterable

    from define.compiler.validator import codegen_input
    from define.compiler.validator.reference_graph.dead_code import (
        dead_interface_tracker,
    )


class _GuaranteeApplicationState(msgspec.Struct, frozen=True):
    """Shared particle state for applying one callee's guarantees."""

    # The triggered action's chain in the caller.
    action_chain: chained_name.ActionReferenceTuple
    origin_keys: set[chained_name.PositionReferenceTuple]
    # Detached for swap safety.
    detached: particle_state_store.DetachedSubtrees = msgspec.field(
        default_factory=particle_state_store.DetachedSubtrees
    )

    @classmethod
    def for_callee(
        cls,
        pending: pending_guarantee.PendingGuarantee,
        action_chain: chained_name.ActionReferenceTuple,
    ) -> typing.Self:
        """Prepare shared state for applying the callee's guarantees."""
        # Existing particles must survive earlier Guarantees that overwrite
        # their origin Positions before the particles reach their destinations.
        origin_keys: set[chained_name.PositionReferenceTuple] = set()
        for guarantee in pending.contract.guarantees.values():
            if isinstance(guarantee, action_contract.OccupiedByExistingGuarantee):
                origin_tuple = guarantee.origin_position.canonical_chained_name_tuple
                origin_keys.add(chained_name.in_caller(action_chain, origin_tuple))

        return cls(action_chain=action_chain, origin_keys=origin_keys)

    def key_for[T: chained_name.ChainedNameTuple](self, name: T) -> T:
        """Return the absolute key for a guarantee the callee names ``name``."""
        return chained_name.in_caller(self.action_chain, name)

    def save_origins_at_or_below(
        self,
        key: chained_name.PositionReferenceTuple,
        store: particle_state_store.ParticleStateStore,
    ):
        """Detach every origin position at or below ``key`` before ``key``'s subtree is overwritten."""
        key_len = len(key)
        at_or_below: list[chained_name.PositionReferenceTuple] = []
        for origin_key in self.origin_keys:
            if len(origin_key) >= key_len and origin_key[:key_len] == key:
                at_or_below.append(origin_key)
        store.detach_subtrees(at_or_below, self.detached)


@typing.final
class CalleeGuaranteeApplier:
    """Applies callee Guarantees to the particle state store.

    A triggered action's own Guarantees are applied as soon as it triggers. Its
    nested Guarantees wait until an operation needs a Position they describe.
    """

    def __init__(
        self,
        store: particle_state_store.ParticleStateStore,
        dead_interfaces: dead_interface_tracker.DeadInterfaceTracker,
    ):
        """Apply Guarantees to ``store``, recording particle changes in ``dead_interfaces``."""
        self._store = store
        self._dead_interfaces = dead_interfaces

    def apply_triggered_action(
        self,
        execution: codegen_input.ActionExecution,
        contract: action_contract.ActionContract,
    ):
        """Apply a triggered action's own Guarantees and defer its nested Guarantees."""
        # Profiles make eager guarantee application look like duplicated work
        # that can simply be deferred. Experiments in July 2026 showed that much
        # of this work represents ordering that the particle state and operation
        # graph must both observe, rather than redundant computation:
        # - Deferring callee guarantees in a lazy overlay improved dense action
        #   call graphs by 7-12%, but produced incorrect operation graphs.
        #   Superseded GuaranteeNodes, parent dependencies,
        #   OccupiedByExisting swaps, and nested or implied guarantees depend on
        #   guarantees becoming visible in their precise application order.
        # - Expanding every nested guarantee prefix before applying it preserved
        #   more ordering, but exhausted memory on the largest dense action call
        #   graph.
        # - Passing each accepted guarantee directly to the operation graph
        #   looked like it would remove duplicated work: it eliminated the
        #   temporary accepted-guarantee list, the second recording pass, and the
        #   operation-node association pass. Creating a shared-effect object for
        #   each guarantee instead made validation 3.1% slower, so the prototype
        #   was rejected.
        # Do not repeat these deferral experiments unless the prototype preserves
        # the ordering behavior above and remains memory-efficient on the largest
        # dense action call graph.
        # These measurements predate operation-graph removal; graph-specific
        # failures describe the former implementation, not current requirements.
        action_chain_key = execution.action.canonical_chained_name_tuple
        callee_guarantees = pending_guarantee.PendingGuarantee(
            action_chain_key[-1],
            contract,
            execution,
        )
        self._store.record_triggered_action(action_chain_key, execution, contract)
        self._apply_pending_guarantee(callee_guarantees, action_chain_key)

    def _apply_pending_guarantee(
        self,
        pending: pending_guarantee.PendingGuarantee,
        action_chain: chained_name.ActionReferenceTuple,
    ):
        """Apply a callee's guarantees and add one child name to nested guarantee prefixes."""
        application = _GuaranteeApplicationState.for_callee(pending, action_chain)

        # A preceding Guarantee may create or move a later Guarantee's parent,
        # so acceptance checks must alternate with occupancy updates.
        for position, guarantee in pending.contract.guarantees.items():
            key = application.key_for(position)

            # A shallower guarantee from the same Action Execution already
            # decided this key, so this one must not override it.
            if self._store.is_superseded(
                key,
                pending.execution,
                pending.call_chain_depth,
            ):
                continue

            # An interface-position guarantee needs a tracker entry for the
            # callee's action name as its immediate parent name. That entry
            # usually does not exist yet, so creating it here is the common path.
            # Implied-position guarantees omit that action name.
            missing_key = self._store.try_add_action_parent(key)
            if missing_key is not None:
                # For example, the caller triggers without filling position<a>,
                # but the callee moves from position<a>::position</c1>. Applying
                # that child's EmptyGuarantee finds no entry for position<a>.
                # Requirement checking already reported the missing particle;
                # mark the parent as error so later operations on it or its
                # child positions do not produce cascading diagnostics.
                self._store.mark_error(missing_key, guarantee.caused_by)
                continue

            self._update_store_from_callee_direct_guarantee(
                pending, key, guarantee, application
            )

        for child in pending.contract.callees:
            # The original triggering chain is the full chain the action had from
            # the perspective of its caller, when it was triggered. CalleeContract
            # does not retain that chain; the examples below show it for comparison.
            #
            # child.action_chain is where that action was, from the
            # perspective of its caller, when that caller finally generated its
            # guarantees.
            #
            # However, nested guarantees can _also_ be moved without their
            # more-deeply nested guarantees being applied in the callee. Composing
            # child.action_chain with pending.action_chain places those
            # deeper guarantees at the moved particle's current chain when we
            # apply them in the current action.
            #
            # Thus, pending.action_chain is the callee's current chained
            # name, where its guarantees apply, from this action's perspective.
            #
            # We have this system to avoid the same potentially exponential work that
            # pending guarantees exist to avoid.
            #
            # -------
            # Example
            # -------
            #
            # Consider these operations, with each chained name written from the
            # perspective of the action performing that operation:
            #
            # 1. This action creates a particle in local position<gateway>.
            #
            # 2. This action creates a particle in:
            #    position<gateway>::action</relocate_particle>::position<source>.
            #
            # 3. This action creates a particle in:
            #    position<gateway>::action</relocate_particle>::position<source>::action</process_particle>::position<marker_parent>.
            #
            # 4. This action creates a particle in:
            #    position<gateway>::action</relocate_particle>::position<trigger_pos>.
            #    This triggers:
            #    position<gateway>::action</relocate_particle>.
            #
            # 5. action</relocate_particle>
            #    creates a particle in its interface:
            #    position<stationary>.
            #
            # 6. action</relocate_particle>
            #    creates a particle in its interface:
            #    position<source>::action</process_particle>::position<trigger_pos>.
            #    This triggers:
            #    position<source>::action</process_particle>.
            #
            # 7. action</process_particle>
            #    creates a particle in its interface:
            #    position<marker_parent>::action</fill_marker>::position<trigger_pos>.
            #    This triggers:
            #    position<marker_parent>::action</fill_marker>.
            #
            # 8. action</fill_marker>
            #    creates a particle in:
            #    position<result>.
            #
            # 9. action</relocate_particle>
            #    creates a particle in its interface:
            #    position<stationary>::action</inspect_particle>::position<trigger_pos>.
            #    This triggers:
            #    position<stationary>::action</inspect_particle>.
            #
            # 10. action</inspect_particle>
            #     creates a particle in its interface:
            #     position<result>.
            #
            # 11. action</relocate_particle>
            #     moves the particle in its interface:
            #     position<source>
            #     to:
            #     position<destination>.
            #
            # This action applies the guarantees of:
            # position<gateway>::action</relocate_particle>
            # which adds the pending guarantees of:
            # position<gateway>::action</relocate_particle>::position<stationary>::action</inspect_particle>.
            #
            # pending.action_chain =
            #     position<gateway>::action</relocate_particle>
            # child.action_chain =
            #     position<stationary>::action</inspect_particle>
            # Original triggering chain (for comparison):
            #     position<stationary>::action</inspect_particle>
            # child_action_chain_in_caller =
            #     position<gateway>::action</relocate_particle>::position<stationary>::action</inspect_particle>
            #
            # This action applies the guarantees of:
            # position<gateway>::action</relocate_particle>
            # which adds the pending guarantees of:
            # position<gateway>::action</relocate_particle>::position<destination>::action</process_particle>.
            #
            # pending.action_chain =
            #     position<gateway>::action</relocate_particle>
            # child.action_chain =
            #     position<destination>::action</process_particle>
            # Original triggering chain (for comparison):
            #     position<source>::action</process_particle>
            # child_action_chain_in_caller =
            #     position<gateway>::action</relocate_particle>::position<destination>::action</process_particle>
            #
            # This action applies the pending guarantees of:
            # position<gateway>::action</relocate_particle>::position<destination>::action</process_particle>
            # which adds the pending guarantees of:
            # position<gateway>::action</relocate_particle>::position<destination>::action</process_particle>::position<marker_parent>::action</fill_marker>.
            #
            # pending.action_chain =
            #     position<gateway>::action</relocate_particle>::position<destination>::action</process_particle>
            # child.action_chain =
            #     position<marker_parent>::action</fill_marker>
            # Original triggering chain (for comparison):
            #     position<marker_parent>::action</fill_marker>
            # child_action_chain_in_caller =
            #     position<gateway>::action</relocate_particle>::position<destination>::action</process_particle>::position<marker_parent>::action</fill_marker>
            child_action_chain_in_caller = application.key_for(child.action_chain)
            child_nested_guarantee = pending_guarantee.PendingGuarantee(
                child_action_chain_in_caller[-1],
                child.contract,
                pending.execution,
                call_chain_depth=pending.call_chain_depth + 1,
            )
            self._store.add_pending_guarantee(
                chained_name.parent(child_action_chain_in_caller),
                child_nested_guarantee,
            )

    def apply_pending_guarantees_up_to(self, key: chained_name.PositionReferenceTuple):
        """Apply any nested guarantee on the path from root to ``key``."""
        if not self._store.has_any_pending_guarantees():
            return
        for prefix in chained_name.proper_prefixes(key):
            # Applying a guarantee can add another pending guarantee at this
            # same prefix, so do not advance until the prefix stays empty.
            while self._store.has_pending_guarantees(prefix):
                self._apply_all(prefix, self._store.pop_pending_guarantees(prefix))

    def apply_pending_guarantees_up_to_all(
        self, keys: Iterable[chained_name.PositionReferenceTuple]
    ):
        """Apply nested guarantees on the paths to any of ``keys``."""
        if not self._store.has_any_pending_guarantees():
            return
        for key in keys:
            for prefix in chained_name.proper_prefixes(key):
                # Applying a guarantee can add another pending guarantee at
                # this same prefix. Callers never read positions below it
                # before a later expansion applies that one, so it can wait.
                self._apply_all(prefix, self._store.pop_pending_guarantees(prefix))

    def fully_resolve_pending_guarantees(
        self, *keys: chained_name.PositionReferenceTuple
    ):
        """Apply guarantees affecting any of the keys or their children."""
        self.apply_pending_guarantees_up_to_all(keys)
        self._apply_at_or_below(keys)

    def discard_discardable_pending_guarantees(
        self, key: chained_name.PositionReferenceTuple
    ):
        """Discard the nested guarantees for ``key``'s children if each is discardable on destruction and nothing is tracked where it applies."""
        # When we destroy a particle, we walk all of its children to find their
        # Destructors, and that walk applies every pending Guarantee below the
        # particle. If a tree of triggered actions built those children, that's
        # exponentially many Guarantees for a linear amount of source code.
        #
        # Often, though, applying a pending Guarantee makes no difference. If
        # all it would do is create children that have no Destructors, those
        # children just vanish along with the particle we're destroying, so we
        # can throw the Guarantee away instead. That's only safe when all of
        # these are true:
        # - Its contract says so (ActionContract.guarantees_discardable_on_destruction).
        #   That covers what the action creates and what every action it
        #   triggered creates, too.
        # - We don't already have any state recorded (a particle, a known-empty
        #   position, or an error) at or below the positions it writes, or
        #   that the actions it triggered write.
        # - No particle that came from the calling action is at or above
        #   ``key``.
        #
        # Every pending Guarantee stored for this particle has to qualify, or
        # we apply them all as usual. They can overwrite each other, so
        # applying only some of them could change what the others would do.
        pending_guarantees = self._store.pending_guarantees_at(key)
        if not pending_guarantees:
            return
        for pending in pending_guarantees:
            if not pending.contract.guarantees_discardable_on_destruction:
                return
            if self._result_overwrites_recorded_state(
                pending, pending.action_chain(key)
            ):
                return
        _ = self._store.pop_pending_guarantees(key)

    def apply_overwriting_pending_guarantees(
        self, key: chained_name.PositionReferenceTuple
    ):
        """Apply the pending guarantees at or below ``key`` that would overwrite state already recorded there."""
        # State recorded below a pending guarantee is older than it, and only
        # queries that walk into the guarantee's particle know to apply it
        # first. Code that reads whole subtrees would read that older state.
        # Other pending guarantees write only where nothing is recorded, so
        # they can wait.
        applied = True
        while applied:
            applied = False
            for prefix in self._store.pending_prefixes_at_or_below(key):
                if self._overwrites_recorded_state(prefix):
                    self._apply_all(prefix, self._store.pop_pending_guarantees(prefix))
                    applied = True

    def _overwrites_recorded_state(
        self, particle: chained_name.ChainedNameTuple
    ) -> bool:
        # Pending guarantees below a position always sit on particle positions.
        for pending in self._store.pending_guarantees_at(
            chained_name.position(particle)
        ):
            if self._result_overwrites_recorded_state(
                pending, pending.action_chain(particle)
            ):
                return True
        return False

    def _result_overwrites_recorded_state(
        self,
        pending: pending_guarantee.PendingGuarantee,
        action_chain: chained_name.ActionReferenceTuple,
    ) -> bool:
        for position in pending.contract.guarantees:
            key = chained_name.in_caller(action_chain, position)
            # A shallower guarantee from the same Action Execution recorded
            # its final state here after this one, so this one would not
            # apply.
            if not self._store.is_superseded(
                key, pending.execution, pending.call_chain_depth
            ) and self._store.tracks_at_or_below(key):
                return True
        for callee in pending.contract.callees:
            callee_chain = chained_name.in_caller(action_chain, callee.action_chain)
            # A callee writes only below the particle it acts on, so if
            # nothing is recorded there, its guarantees and those of the
            # actions it triggered cannot overwrite anything.
            if self._store.tracks_at_or_below(
                chained_name.position(chained_name.parent(callee_chain))
            ) and self._result_overwrites_recorded_state(
                pending_guarantee.PendingGuarantee(
                    callee_chain[-1],
                    callee.contract,
                    pending.execution,
                    call_chain_depth=pending.call_chain_depth + 1,
                ),
                callee_chain,
            ):
                return True
        return False

    def fully_resolve_all_pending_guarantees(self):
        """Apply every pending guarantee."""
        # Every stored prefix is at or below the empty chain.
        self._apply_at_or_below([chained_name.ChainedNameTuple(())])

    def _apply_at_or_below(self, keys: Iterable[chained_name.ChainedNameTuple]):
        # Applying a guarantee can add pending guarantees below it, so look
        # again until none remain.
        while True:
            prefixes: list[chained_name.ChainedNameTuple] = []
            for key in keys:
                prefixes.extend(self._store.pending_prefixes_at_or_below(key))
            if not prefixes:
                return
            for prefix in prefixes:
                self._apply_all(prefix, self._store.pop_pending_guarantees(prefix))

    def _apply_all(
        self,
        particle: chained_name.ChainedNameTuple,
        pending_guarantees: Iterable[pending_guarantee.PendingGuarantee],
    ):
        for pending in pending_guarantees:
            self._apply_pending_guarantee(pending, pending.action_chain(particle))

    def _update_store_from_callee_direct_guarantee(
        self,
        pending: pending_guarantee.PendingGuarantee,
        key: chained_name.PositionReferenceTuple,
        guarantee: action_contract.PositionGuarantee,
        application: _GuaranteeApplicationState,
    ):
        """Update particle state from one applicable callee guarantee."""
        # OccupiedByExisting depends on caller-passed particle identity, so
        # it must be resolved here (a distant caller can't reconstruct it)
        # and emitted as this block's own guarantee. Other guarantee types
        # are re-derivable in any caller, so they stay behind the nested guarantee.
        self._store.record_callee_write(
            key,
            pending.execution,
            pending.call_chain_depth,
            include_in_own_guarantees=isinstance(
                guarantee, action_contract.OccupiedByExistingGuarantee
            ),
        )

        # The same particle remains at this position. Apply its value effect
        # without the replacement logic below deleting its child positions.
        if isinstance(
            guarantee, action_contract.OccupiedByExistingGuarantee
        ) and key == application.key_for(
            guarantee.origin_position.canonical_chained_name_tuple
        ):
            occupant = self._store.occupant_or_none(key)
            if occupant is not None:
                occupant.set_value_state(
                    guarantee.value_effect,
                    pending.execution.action.get_last_action().location,
                )
            return

        overwrites_subtree = key in application.origin_keys or (
            self._store.has_state(key)
            and not isinstance(guarantee, action_contract.UnchangedGuarantee)
        )
        # We are about to overwrite this key's subtree, and a later guarantee still
        # needs to read a particle from an origin position that may have it as
        # a parent name.
        if application.origin_keys and overwrites_subtree:
            application.save_origins_at_or_below(key, self._store)

        # We are overwriting this key's subtree, and this key is not itself an origin
        # position that a later guarantee reads from, so its old contents can just be
        # dropped.
        if key not in application.origin_keys and overwrites_subtree:
            # Subtree cleanup: If an action empties position<item> (EmptyGuarantee)
            # or creates in position<item> (OccupiedByNewGuarantee), any children
            # the caller had at child names of position<item> must disappear. We
            # achieve this by deleting each key's entire subtree before applying
            # its guarantee.
            # An UnchangedGuarantee leaves the caller's state as it found it, so
            # it keeps whatever subtree is there.
            self._store.delete_subtree(
                key, self._dead_interfaces.mark_particle_destroyed
            )

        match guarantee:
            case action_contract.OccupiedByExistingGuarantee():
                self._apply_existing_guarantee(
                    key,
                    pending,
                    guarantee,
                    application,
                )
            case action_contract.EmptyGuarantee():
                self._store.mark_emptied(key, guarantee.caused_by)
            case action_contract.OccupiedByNewGuarantee():
                new_info = particle_info.ParticleInfo(
                    last_position=guarantee.caused_by,
                    qualities=guarantee.qualities,
                    origin_position=guarantee.origin_position,
                )
                new_info.set_value_state(
                    guarantee.value_effect,
                    pending.execution.action.get_last_action().location,
                )
                self._store.mark_occupied(key, new_info)
                self._dead_interfaces.register_occupied_interface_child_position(
                    key,
                    new_info,
                    pending.execution.action.get_last_action().location,
                )
            case action_contract.ErrorGuarantee():
                self._store.mark_error(key, guarantee.caused_by)
            case action_contract.UnchangedGuarantee():
                # The position is unchanged from before the callee triggered,
                # which the caller's store already reflects (the cleanup above
                # kept any occupant). A later Move of its parent must still
                # collect the callee's operations on an otherwise-untracked
                # empty child position. The write record above still outranks a
                # deeper guarantee from the same Action Execution.
                self._store.mark_unchanged(key)
            case _:
                raise TypeError(f"Unexpected guarantee type: {type(guarantee)}")

    def _apply_existing_guarantee(
        self,
        dest_key: chained_name.PositionReferenceTuple,
        pending: pending_guarantee.PendingGuarantee,
        guarantee: action_contract.OccupiedByExistingGuarantee,
        application: _GuaranteeApplicationState,
    ):
        """Apply an OccupiedByExisting guarantee at dest_key."""
        origin_tuple = guarantee.origin_position.canonical_chained_name_tuple
        origin_key = application.key_for(origin_tuple)

        # Get origin's particle_info — from saved copy if already processed,
        # else from the live trie.
        if application.detached.has_state(origin_key):
            moved_info = application.detached.occupant_or_none(origin_key)
        elif self._store.has_state(origin_key):
            moved_info = self._store.occupant_or_none(origin_key)
        else:
            # The caller never filled the origin position, so the callee's Move
            # cannot supply a particle at the destination.
            self._store.mark_error(dest_key, guarantee.caused_by)
            return

        # The caller never filled the Interface Position. The callee moves the
        # particle to another position. Thus, the origin_state _exists_ but the
        # position got EmptyGuarantee instead of being filled by something (and
        # there's nothing in application.detached).
        if moved_info is None:
            self._store.mark_error(dest_key, guarantee.caused_by)
            return

        source_location = pending.execution.action.get_last_action().location
        moved_info.set_value_state(guarantee.value_effect, source_location)
        moved_info.last_position = guarantee.caused_by
        self._dead_interfaces.mark_particle_departed(moved_info)

        def record_guaranteed_position(
            position: chained_name.PositionReferenceTuple,
            particle: particle_info.ParticleInfo,
        ):
            self._dead_interfaces.replace_occupied_interface_child_position(
                position, particle, source_location
            )

        self._store.move_guaranteed_particle(
            origin_key, dest_key, application.detached, record_guaranteed_position
        )
