"""Apply callee Guarantees to the particle state store, deferring nested Guarantees until they are needed."""

from __future__ import annotations

import typing

import msgspec

from define.compiler import chained_name
from define.compiler.validator.reference_graph import action_contract
from define.compiler.validator.reference_graph.particles import (
    particle_info,
    particle_state_store,
)

if typing.TYPE_CHECKING:
    from collections.abc import Iterable, Iterator, Sequence

    from define.compiler.validator import codegen_input
    from define.compiler.validator.reference_graph.dead_code import (
        dead_interface_tracker,
    )


class _PendingGuarantee(msgspec.Struct, frozen=True):
    """A callee's guarantees and the execution path where they apply."""

    # The triggered action's chain.
    action_chain: chained_name.ActionReferenceTuple
    contract: action_contract.ActionContract
    # The body operation number of the Action Execution that produced this nested
    # guarantee.
    # All of a triggered contract's guarantees (own and nested) carry it, so a
    # body statement that executes later supersedes them.
    body_operation_number: int
    execution: codegen_input.ActionExecution
    # Call-chain depth from the directly-applied contract: its own guarantees
    # are depth 0; each nested guarantee increments the depth. Within a single
    # Action Execution (same sequence), a lower-depth guarantee outranks a higher-depth
    # one it resolved.
    call_chain_depth: int = 0

    @property
    def parent_position(self) -> chained_name.ChainedNameTuple:
        """The parent of the callee's implied (global) positions.

        This is ``action_chain`` with its trailing action stripped: an implied
        quality lives on the action's parent particle, at the parent name of the
        action's interface position names. ``action_chain`` always ends in the
        triggered action, since that is the only thing that produces guarantees.
        """
        return chained_name.parent(self.action_chain)

    def key_for[T: chained_name.ChainedNameTuple](self, name: T) -> T:
        """Return the absolute key for a guarantee this action names ``name``."""
        return chained_name.in_caller(self.action_chain, name)

    @property
    def identity(self) -> _PendingGuaranteeIdentity:
        """Fields that make two pending guarantees apply identical effects."""
        return _PendingGuaranteeIdentity(
            self.action_chain,
            id(self.contract),
            self.body_operation_number,
            self.execution,
            self.call_chain_depth,
        )


class _PendingGuaranteeIdentity(msgspec.Struct, frozen=True):
    """Fields that make two pending guarantees apply identical effects."""

    action_chain: chained_name.ActionReferenceTuple
    # Contracts are compared by identity because comparing their contents
    # would walk every guarantee, and each definition has one contract.
    contract_id: int
    body_operation_number: int
    # Action Executions already compare by identity.
    execution: codegen_input.ActionExecution
    call_chain_depth: int


# Nested guarantees are deferred here instead of being flattened into every
# caller's state, and this laziness is a critical performance optimization.
# Eagerly flattening the whole guarantee list re-copies a callee's entire
# guarantee subtree at each level of a deep call chain, so an action graph with
# fan-out F and call depth D produces O(F^D) guarantees: an exponential blowup
# that eventually makes compilation impossible.
#
# Deferring the resolution of guarantees keeps each contract at a size of
# O(own guarantees + F references) and only materializes the guarantees a
# specific caller actually depends on directly in their code.
class _PendingNestedGuarantees:
    """A prefix multimap of nested guarantees, keyed by a position prefix.

    Each nested guarantee is stored by a position prefix.
    ``drain_shortest_first`` yields the ones whose prefix is a parent name of a
    queried position (shortest prefix first); ``drain_at_or_below_for`` yields the
    ones for which a queried position is a parent name. Both remove what they
    yield and re-query as they go: applying a yielded nested guarantee can add
    ones with additional child names, which the drain then picks up.
    """

    # The two drain directions need different lookups. Shortest-first queries
    # can probe successive prefixes directly in _by_prefix. Queries for child
    # names would otherwise have to scan every stored prefix, so we also index
    # each stored prefix under all of its nonempty prefixes.
    #
    # For example, _by_prefix[("a", "b")] holds the guarantees stored at that
    # name. Both _by_requested_prefix[("a",)] and
    # _by_requested_prefix[("a", "b")] contain the key ("a", "b"). A query
    # for ("a",) can therefore find those guarantees without examining unrelated
    # names. The index holds keys rather than guarantees, so adding another
    # guarantee at an existing name needs only an insertion into its ordered set.

    def __init__(self):
        # Each inner dictionary is an ordered set of the guarantees stored at
        # that name.
        self._by_prefix: dict[
            chained_name.ChainedNameTuple,
            dict[_PendingGuaranteeIdentity, _PendingGuarantee],
        ] = {}
        # Queries must skip unrelated guarantees even when many share a parent name.
        self._by_requested_prefix: dict[
            chained_name.ChainedNameTuple, set[chained_name.ChainedNameTuple]
        ] = {}
        # Draining several indexed names must preserve their original insertion order.
        # The sets in _by_requested_prefix do not preserve insertion order, so these
        # numbers recover the order of keys in _by_prefix. Removing and re-adding a
        # key gives it a new place in that order.
        self._prefix_order: dict[chained_name.ChainedNameTuple, int] = {}
        self._next_prefix_order: int = 0
        self._longest_pending_guarantee_key: int = 0

    def add(self, nested_guarantee: _PendingGuarantee):
        """Record a nested guarantee to apply once a query reaches ``prefix`` or one of its child names."""
        # Interface guarantees use action_chain as their prefix; implied-position
        # guarantees use parent_position. Store both under parent_position so that
        # queries on implied positions can find the pending guarantee too.
        prefix = nested_guarantee.parent_position
        guarantees = self._by_prefix.get(prefix)
        if guarantees is None:
            for requested_prefix in chained_name.prefixes(prefix):
                matching = self._by_requested_prefix.get(requested_prefix)
                if matching is None:
                    self._by_requested_prefix[requested_prefix] = {prefix}
                else:
                    matching.add(prefix)
            self._prefix_order[prefix] = self._next_prefix_order
            self._next_prefix_order += 1
            self._by_prefix[prefix] = {nested_guarantee.identity: nested_guarantee}
        else:
            # When several implying qualities imply the same quality, each of
            # them adds that quality's action as a nested guarantee. From the
            # caller's perspective, an implied action's chain drops the action
            # that implied it, so all of those copies have the same chain. Over
            # layers of shared implied qualities, the copies multiply with every
            # layer. Applying each copy would take exponential time. Keeping
            # only the latest copy preserves which guarantee writes each
            # position last.
            identity = nested_guarantee.identity
            _ = guarantees.pop(identity, None)
            guarantees[identity] = nested_guarantee
        self._longest_pending_guarantee_key = max(
            self._longest_pending_guarantee_key, len(prefix)
        )

    def _pop_prefix(
        self, prefix: chained_name.ChainedNameTuple
    ) -> Iterable[_PendingGuarantee]:
        # Every drain must remove the index entries before yielding the guarantees:
        # applying one can query the index again or add new guarantees at this same name.
        guarantees = self._by_prefix.pop(prefix)
        for requested_prefix in chained_name.prefixes(prefix):
            matching = self._by_requested_prefix[requested_prefix]
            matching.remove(prefix)
            if not matching:
                del self._by_requested_prefix[requested_prefix]
        del self._prefix_order[prefix]
        return guarantees.values()

    def stored_at(
        self, prefix: chained_name.ChainedNameTuple
    ) -> Iterable[_PendingGuarantee]:
        """Return the pending nested guarantees stored at exactly ``prefix``."""
        guarantees = self._by_prefix.get(prefix)
        return () if guarantees is None else guarantees.values()

    def discard(self, prefix: chained_name.ChainedNameTuple):
        """Remove the pending nested guarantees stored at exactly ``prefix`` without applying them."""
        _ = self._pop_prefix(prefix)

    def drain_shortest_first(
        self, key: chained_name.ChainedNameTuple
    ) -> Iterator[_PendingGuarantee]:
        """Yield and remove the pending nested guarantees on the path to ``key``, shortest prefix first."""
        # The common case is no pending guarantees; bail before doing any work,
        # as a performance optimization.
        if not self._by_prefix:
            self._longest_pending_guarantee_key = 0
            return
        # Walk the prefixes of key from shortest to longest, but no longer than
        # the longest pending guarantee key.
        key_len = len(key)
        length = 0
        while length < key_len and length <= self._longest_pending_guarantee_key:
            prefix = chained_name.ChainedNameTuple(key[:length])
            # Applying a yielded guarantee can re-add one at this same prefix, so
            # drain it fully before moving to a prefix with another child name.
            while prefix in self._by_prefix:
                yield from self._pop_prefix(prefix)
            length += 1

    def drain_shortest_first_for(
        self, keys: Iterable[chained_name.ChainedNameTuple]
    ) -> Iterator[_PendingGuarantee]:
        """Yield and remove pending guarantees on the paths to ``keys``.

        Keys may be in any order and are processed in the order supplied. Keys
        with common prefixes are faster when adjacent because their already
        drained prefixes are reused, but adjacency is not required for
        correctness. Guarantees on each individual path are yielded from the
        shortest prefix to the longest.
        """
        # Requirement propagation usually has no pending guarantees, so avoid
        # consuming its keys or performing any chained-name comparisons then.
        if not self._by_prefix:
            self._longest_pending_guarantee_key = 0
            return
        previous_key: chained_name.ChainedNameTuple | None = None
        previous_drained_prefix_count = 0
        for key in keys:
            if previous_key is None:
                # A pending implied-action guarantee can use the empty tuple as
                # its prefix, so the first path must begin there.
                length = 0
            else:
                # Reuse only prefixes actually drained for the preceding path.
                common_depth = 0
                common_depth_limit = min(
                    len(previous_key),
                    len(key),
                    previous_drained_prefix_count,
                )
                while (
                    common_depth < common_depth_limit
                    and previous_key[common_depth] == key[common_depth]
                ):
                    common_depth += 1
                length = min(common_depth + 1, previous_drained_prefix_count)
            key_len = len(key)
            # A guarantee can affect the queried position only when its prefix
            # is one of the queried position's parent names.
            while length < key_len and length <= self._longest_pending_guarantee_key:
                prefix = chained_name.ChainedNameTuple(key[:length])
                # Applying a guarantee can add another pending guarantee at this
                # same prefix, so do not advance until the prefix stays empty.
                while prefix in self._by_prefix:
                    yield from self._pop_prefix(prefix)
                # Once no pending guarantees remain, no later path can yield
                # anything.
                if not self._by_prefix:
                    self._longest_pending_guarantee_key = 0
                    return
                length += 1
            previous_key = key
            previous_drained_prefix_count = length

    def drain_at_or_below_for(
        self, keys: Sequence[chained_name.ChainedNameTuple]
    ) -> Iterator[_PendingGuarantee]:
        """Yield guarantees at or below any of the equally long keys."""
        if not self._by_prefix or not keys:
            return
        # Automatic Destruction can request thousands of locally defined
        # Positions. They all have one name; other callers request just one key.
        # Combining their indexed matches avoids scanning unrelated pending prefixes.
        length = len(keys[0])
        requested = set(keys)
        # Applying a guarantee can add more pending guarantees, even at
        # a name just drained. Finish each batch in stored-prefix insertion order,
        # then query again until none of the requested names have matches.
        while self._by_prefix:
            if length == 0:
                # An empty prefix matches every name, so indexing it would only
                # duplicate the complete set of stored keys.
                matching = list(self._by_prefix)
            else:
                matching: list[chained_name.ChainedNameTuple] = []
                # Distinct requested names of equal length have disjoint matches.
                for key in requested:
                    matching.extend(self._by_requested_prefix.get(key, ()))
                matching.sort(key=self._prefix_order.__getitem__)
            if not matching:
                return
            for prefix in matching:
                yield from self._pop_prefix(prefix)


class _GuaranteeApplicationState(msgspec.Struct, frozen=True):
    """Shared particle state for applying one callee's guarantees."""

    origin_keys: set[chained_name.PositionReferenceTuple]
    # Detached for swap safety.
    detached: particle_state_store.DetachedSubtrees = msgspec.field(
        default_factory=particle_state_store.DetachedSubtrees
    )

    @classmethod
    def for_callee(cls, pending_guarantee: _PendingGuarantee) -> typing.Self:
        """Prepare shared state for applying the callee's guarantees."""
        # Existing particles must survive earlier Guarantees that overwrite
        # their origin Positions before the particles reach their destinations.
        origin_keys: set[chained_name.PositionReferenceTuple] = set()
        for guarantee in pending_guarantee.contract.guarantees.values():
            if isinstance(guarantee, action_contract.OccupiedByExistingGuarantee):
                origin_tuple = guarantee.origin_position.canonical_chained_name_tuple
                origin_keys.add(pending_guarantee.key_for(origin_tuple))

        return cls(origin_keys=origin_keys)

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
        self._pending = _PendingNestedGuarantees()

    def apply_triggered_action(
        self,
        execution: codegen_input.ActionExecution,
        contract: action_contract.ActionContract,
        body_operation_number: int,
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
        callee_guarantees = _PendingGuarantee(
            action_chain_key,
            contract,
            body_operation_number,
            execution,
        )
        self._store.record_triggered_action(action_chain_key, execution, contract)
        self._apply_pending_guarantee(callee_guarantees)

    def _apply_pending_guarantee(self, pending_guarantee: _PendingGuarantee):
        """Apply a callee's guarantees and add one child name to nested guarantee prefixes."""
        application = _GuaranteeApplicationState.for_callee(pending_guarantee)

        # A preceding Guarantee may create or move a later Guarantee's parent,
        # so acceptance checks must alternate with occupancy updates.
        for position, guarantee in pending_guarantee.contract.guarantees.items():
            key = pending_guarantee.key_for(position)

            # A later-running statement already finalized this key, so this
            # guarantee must not override it.
            if self._store.is_superseded(
                key,
                pending_guarantee.body_operation_number,
                pending_guarantee.call_chain_depth,
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
                pending_guarantee, key, guarantee, application
            )

        for child in pending_guarantee.contract.callees:
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
            # child.action_chain with pending_guarantee.action_chain places those
            # deeper guarantees at the moved particle's current chain when we
            # apply them in the current action.
            #
            # Thus, pending_guarantee.action_chain is the callee's current chained
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
            # pending_guarantee.action_chain =
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
            # pending_guarantee.action_chain =
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
            # pending_guarantee.action_chain =
            #     position<gateway>::action</relocate_particle>::position<destination>::action</process_particle>
            # child.action_chain =
            #     position<marker_parent>::action</fill_marker>
            # Original triggering chain (for comparison):
            #     position<marker_parent>::action</fill_marker>
            # child_action_chain_in_caller =
            #     position<gateway>::action</relocate_particle>::position<destination>::action</process_particle>::position<marker_parent>::action</fill_marker>
            child_action_chain_in_caller = pending_guarantee.key_for(child.action_chain)
            child_nested_guarantee = _PendingGuarantee(
                child_action_chain_in_caller,
                child.contract,
                pending_guarantee.body_operation_number,
                pending_guarantee.execution,
                call_chain_depth=pending_guarantee.call_chain_depth + 1,
            )
            self._pending.add(child_nested_guarantee)

    def apply_pending_guarantees_up_to(self, key: chained_name.PositionReferenceTuple):
        """Apply any nested guarantee on the path from root to ``key``."""
        self._apply_drained(self._pending.drain_shortest_first(key))

    def apply_pending_guarantees_up_to_all(
        self, keys: Iterable[chained_name.PositionReferenceTuple]
    ):
        """Apply nested guarantees on the paths to any of ``keys``."""
        self._apply_drained(self._pending.drain_shortest_first_for(keys))

    def fully_resolve_pending_guarantees(
        self, *keys: chained_name.PositionReferenceTuple
    ):
        """Apply guarantees affecting any of the equally long keys or their children."""
        self.apply_pending_guarantees_up_to_all(keys)
        self._apply_drained(self._pending.drain_at_or_below_for(keys))

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
        #   position, or an error) at or below the positions it writes.
        # - No particle that came from the calling action is at or above
        #   ``key``.
        #
        # Every pending Guarantee stored for this particle has to qualify, or
        # we apply them all as usual. They can overwrite each other, so
        # applying only some of them could change what the others would do.
        pending_guarantees = self._pending.stored_at(key)
        if not pending_guarantees:
            return
        for pending_guarantee in pending_guarantees:
            if not pending_guarantee.contract.guarantees_discardable_on_destruction:
                return
            for position in pending_guarantee.contract.guarantees:
                if self._store.tracks_at_or_below(pending_guarantee.key_for(position)):
                    return
        self._pending.discard(key)

    def fully_resolve_all_pending_guarantees(self):
        """Apply every pending guarantee."""
        # Every stored prefix is at or below the empty chain.
        self._apply_drained(
            self._pending.drain_at_or_below_for([chained_name.ChainedNameTuple(())])
        )

    def _apply_drained(self, pending_guarantees: Iterator[_PendingGuarantee]):
        # The drains re-query as they go, so each guarantee must be applied
        # before the next one is drawn.
        for pending_guarantee in pending_guarantees:
            self._apply_pending_guarantee(pending_guarantee)

    def _update_store_from_callee_direct_guarantee(
        self,
        pending_guarantee: _PendingGuarantee,
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
            pending_guarantee.body_operation_number,
            pending_guarantee.call_chain_depth,
            include_in_own_guarantees=isinstance(
                guarantee, action_contract.OccupiedByExistingGuarantee
            ),
        )

        # The same particle remains at this position. Apply its value effect
        # without the replacement logic below deleting its child positions.
        if isinstance(
            guarantee, action_contract.OccupiedByExistingGuarantee
        ) and key == pending_guarantee.key_for(
            guarantee.origin_position.canonical_chained_name_tuple
        ):
            occupant = self._store.occupant_or_none(key)
            if occupant is not None:
                occupant.set_value_state(
                    guarantee.value_effect,
                    pending_guarantee.execution.action.get_last_action().location,
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
                    pending_guarantee,
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
                    pending_guarantee.execution.action.get_last_action().location,
                )
                self._store.mark_occupied(key, new_info)
                self._dead_interfaces.register_occupied_interface_child_position(
                    key,
                    new_info,
                    pending_guarantee.execution.action.get_last_action().location,
                )
            case action_contract.ErrorGuarantee():
                self._store.mark_error(key, guarantee.caused_by)
            case action_contract.UnchangedGuarantee():
                # The position is unchanged from before the callee triggered,
                # which the caller's store already reflects (the cleanup above
                # kept any occupant). A later Move of its parent must still
                # collect the callee's operations on an otherwise-untracked
                # empty child position. The write record above still supersedes
                # a conflicting nested guarantee.
                self._store.mark_unchanged(key)
            case _:
                raise TypeError(f"Unexpected guarantee type: {type(guarantee)}")

    def _apply_existing_guarantee(
        self,
        dest_key: chained_name.PositionReferenceTuple,
        pending_guarantee: _PendingGuarantee,
        guarantee: action_contract.OccupiedByExistingGuarantee,
        application: _GuaranteeApplicationState,
    ):
        """Apply an OccupiedByExisting guarantee at dest_key."""
        origin_tuple = guarantee.origin_position.canonical_chained_name_tuple
        origin_key = pending_guarantee.key_for(origin_tuple)

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

        source_location = pending_guarantee.execution.action.get_last_action().location
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
