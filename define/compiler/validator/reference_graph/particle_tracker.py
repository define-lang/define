"""Tracks particle occupancy for positions within an action block."""

from __future__ import annotations

import dataclasses
import typing
from dataclasses import dataclass

from define.compiler import ast
from define.compiler.data_structures import trie
from define.compiler.validator.reference_graph import action_contract

if typing.TYPE_CHECKING:
    from collections.abc import Iterator


@dataclass(frozen=True, slots=True)
class ParticleInfo:
    """Information about a tracked particle."""

    # The last position reference written in the code for the last
    # statement that relocated or created this particle.
    last_position: ast.PositionReference
    # The qualities we know that this particle has, in
    # assignment order.
    qualities: tuple[ast.GlobalTypedNameReference, ...]
    # The position reference where this particle was first created. The DLP 42
    # liveness check keys a move's satisfied constraints off this: a constraint is
    # only kept alive by a move if the particle was created in the position that
    # wrote it.
    origin_position: ast.PositionReference
    # Whether this particle was passed in by the caller (trigger/inferred) vs created in the body.
    from_caller: bool = False

    def move_to(self, target: ast.PositionReference) -> ParticleInfo:
        """Return a new ParticleInfo reflecting a move to the target position."""
        return dataclasses.replace(self, last_position=target)


@dataclass
class _NodeState:
    """Mutable state for a position in the state trie."""

    particle_info: ParticleInfo | None = None
    emptied_by: ast.PositionReference | None = None


@dataclass
class _ErrorState:
    """Wrapper for error-state trie values.

    LenientReparentingTrie can't use None as a value, so we wrap
    the caused_by reference in a dataclass.
    """

    caused_by: ast.PositionReference | None = None


# Body statements and a directly-applied contract's own guarantees are both at
# call-chain depth 0.
_BODY_DEPTH = 0


@dataclass(frozen=True, slots=True)
class _WriteRecord:
    """A record of a write to a position, containing the information necessary to resolve it when applying guarantees.

    Writes are ordered by execution: a higher ``body_operation_number`` wins, and
    at the same number the shallower ``depth`` wins (a contract's own guarantee
    outranks a nested guarantee that shares the trigger's operation number).
    """

    body_operation_number: int
    depth: int
    # Whether the current occupant came from a nested guarantee (a callee's guarantee),
    # and thus generate_own_guarantees can exclude it from this block's own guarantees.
    is_from_callee: bool
    # Whether a callee's contract ever set this key, even after the body
    # overwrote it. Once set, it never clears. This is necessary because of a
    # situation like this:
    #
    #   action</filler> fills position</marker>
    #   action</middle> calls action</filler> and then empties position</marker>
    #   action</outer> calls action</middle> and then fills position</marker>
    #
    # When we are re-applying guarantees, we have to know that action</middle>
    # overrides the guarantees of action</filler>, even though normally action</middle>
    # would produce no guarantees (because position</marker> started empty and ended empty).
    ever_set_by_callee: bool


@dataclass(frozen=True, slots=True)
class _PendingGuarantee:
    """A callee's guarantees, recorded at an absolute position for lazy application.

    The callee's own guarantees are applied into the base tries when this nested
    guarantee is applied; its own nested guarantees are prefixed one position deeper.
    """

    # The triggered action's chain.
    parent_chain: tuple[str, ...]
    guarantees: action_contract.Guarantees
    # The body operation number of the trigger that produced this nested guarantee.
    # All of a triggered contract's guarantees (own and nested) carry it, so a
    # body statement that executes later supersedes them.
    body_operation_number: int
    # Call-chain depth from the directly-applied contract: its own guarantees
    # are depth 0; each nested guarantee is one deeper. Within a single trigger
    # (same sequence) a shallower guarantee outranks a deeper one it resolved.
    call_chain_depth: int = 0

    @property
    def parent_position(self) -> tuple[str, ...]:
        """The parent of the callee's implied (global) positions.

        This is ``parent_chain`` with its trailing action stripped: an implied
        quality lives on the action's parent particle, one position shallower than
        the action's interface positions. ``parent_chain`` always ends in the
        triggered action, since that is the only thing that produces guarantees.
        """
        return self.parent_chain[:-1]

    def key_for(self, name: tuple[str, ...]) -> tuple[str, ...]:
        """Re-root a guarantee's local name to its absolute key under this guarantee.

        Implied (global) names hang off ``parent_position``; interface (local)
        names hang off ``parent_chain``.
        """
        if ast.chain_starts_with_global(name):
            return self.parent_position + name
        return self.parent_chain + name


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

    Each nested guarantee is stored under a position prefix. ``drain_shortest_first``
    yields the ones whose prefix is an ancestor of a queried position (shortest
    prefix first); ``drain_at_or_below`` yields the ones whose prefix is at or
    below it. Both remove what they yield and re-query as they go: applying a
    yielded nested guarantee can add deeper ones on the same path, which the
    drain then picks up.
    """

    def __init__(self):
        self._by_prefix: dict[tuple[str, ...], list[_PendingGuarantee]] = {}

    def add(self, nested_guarantee: _PendingGuarantee):
        """Record a nested guarantee to apply once a query reaches at or under ``prefix``."""
        # Store the pending nested guarantee under its parent_position, the
        # common ancestor of the callee's interface guarantees (which are
        # prefixed with the trigger position) and its implied guarantees (which
        # are prefixed with the parent_position itself). Using the trigger
        # position instead would leave the implied guarantees outside that
        # subtree, so a query on an implied position would never apply it.
        self._by_prefix.setdefault(nested_guarantee.parent_position, []).append(
            nested_guarantee
        )

    def drain_shortest_first(self, key: tuple[str, ...]) -> Iterator[_PendingGuarantee]:
        """Yield and remove the pending nested guarantees on the path to ``key``, shortest prefix first."""
        # The common case is no pending guarantees; bail before slicing every prefix of key.
        if not self._by_prefix:
            return
        # Walk the prefixes of key from shortest to longest. Length 0 is the empty
        # prefix (the root): a top-level implied action's nested guarantee, whose
        # parent_position is empty, applies to any key.
        for length in range(len(key) + 1):
            prefix = key[:length]
            # Applying a yielded guarantee can re-add one at this same prefix, so
            # drain it fully before moving to a deeper prefix.
            while prefix in self._by_prefix:
                yield from self._by_prefix.pop(prefix)

    def drain_at_or_below(self, key: tuple[str, ...]) -> Iterator[_PendingGuarantee]:
        """Yield and remove any pending nested guarantees at any prefix at or below ``key``."""
        depth = len(key)
        # The reason for this outer while loop is that our caller adds more prefixes
        # as they are running.
        while matching := [
            p for p in self._by_prefix if len(p) >= depth and p[:depth] == key
        ]:
            for prefix in matching:
                yield from self._by_prefix.pop(prefix)


_ACTION_KEY_PREFIX = f"{ast.NameType.ACTION.value}<"


class _ParticleStateStore:
    """The internal position state store, which tracks both the state of a particle and how it's related to our callees' contracts.

    Particle state lives in two tries (``state`` and ``error``). Particles
    in ``error`` are in an error condition---the compiler detected a problem
    but wants to continue compiling to see if it can find more errors. We ignore
    all particles in error states.

    Each position that gets touched during an Action Statements Block also
    carries a _WriteRecord that tells us about the order in which the operation
    was performned and whether this particle came from a guarantee or was performed
    directly. (This is necessary to generate ```action_contract.Guarantees``` for
    the action.)

    Because guarantees are applied lazily (we check if any guarantees were put onto
    a position only if we take an operation on that position) we need some way
    to determine if a guarantee "wins" over a body write. ```is_superseded```
    is the method that does that.
    """

    def __init__(self):
        self._state: trie.StrictReparentingTrie[_NodeState] = (
            trie.StrictReparentingTrie()
        )
        self._error: trie.LenientReparentingTrie[_ErrorState] = (
            trie.LenientReparentingTrie(default_factory=_ErrorState)
        )
        self._write_record: dict[tuple[str, ...], _WriteRecord] = {}

    @property
    def state(self) -> trie.StrictReparentingTrie[_NodeState]:
        """Return the known-occupancy trie (occupied or known-empty positions)."""
        return self._state

    @property
    def error(self) -> trie.LenientReparentingTrie[_ErrorState]:
        """Return the error-occupancy trie."""
        return self._error

    def is_occupied(self, key: tuple[str, ...]) -> bool:
        """Return whether a particle is known to exist at this position."""
        state = self._state.get(key)
        return state is not None and state.particle_info is not None

    def occupant(self, key: tuple[str, ...]) -> ParticleInfo:
        """Return the particle at this position, raising KeyError if it is empty."""
        state = self._state[key]
        if state.particle_info is None:
            raise KeyError(key)
        return state.particle_info

    def emptied_by(self, key: tuple[str, ...]) -> ast.PositionReference | None:
        """Return the position reference that emptied this position, if it is known-empty."""
        state = self._state.get(key)
        return state.emptied_by if state is not None else None

    def has_been_touched(self, key: tuple[str, ...]) -> bool:
        """Return whether a guarantee or particle statement has decided this position's known state."""
        state = self._state.get(key)
        if state is None:
            return False
        return state.particle_info is not None or state.emptied_by is not None

    def has_error_in_chain(self, key: tuple[str, ...]) -> bool:
        """Return whether this position or any ancestor has error occupancy state."""
        return (
            self._error.find_shortest_prefix_where(
                key, lambda state: state.caused_by is not None
            )
            is not None
        )

    def keys_for_guarantees(
        self, *, include_callee_derived: bool
    ) -> set[tuple[str, ...]]:
        """Return every position that we need to provide a guarantee for: occupied, known-empty, or marked error.

        Positions set by our callees are included only when ``include_callee_derived`` is set.
        """
        keys: set[tuple[str, ...]] = set()
        for key, state in self._state.items():
            if (state.particle_info is not None or state.emptied_by is not None) and (
                include_callee_derived or not self._is_from_callee(key)
            ):
                keys.add(key)
        for key, error_state in self._error.items():
            if error_state.caused_by is not None and (
                include_callee_derived or not self._is_from_callee(key)
            ):
                keys.add(key)
        return keys

    def is_superseded(
        self, key: tuple[str, ...], body_operation_number: int, depth: int
    ) -> bool:
        """Return whether a later-ordered write already decided this key.

        "Later" means a higher body operation number, or the same number at a
        shallower call-chain depth (a contract's own guarantee outranks the
        nested guarantee it resolved).
        """
        existing = self._write_record.get(key)
        if existing is None:
            return False
        return existing.body_operation_number > body_operation_number or (
            existing.body_operation_number == body_operation_number
            and existing.depth < depth
        )

    def _is_from_callee(self, key: tuple[str, ...]) -> bool:
        """Return whether this position's current occupant came from a callee's contract."""
        record = self._write_record.get(key)
        return record is not None and record.is_from_callee

    def ever_set_by_callee(self, key: tuple[str, ...]) -> bool:
        """Return whether a callee's contract ever set this position."""
        record = self._write_record.get(key)
        return record is not None and record.ever_set_by_callee

    def record_body_write(self, key: tuple[str, ...], body_operation_number: int):
        """Record that this Action Statement Block's own body made this change to ``key`` at ``body_operation_number``.

        The occupant is no longer callee-derived, but a key a callee previously
        decided keeps ``ever_set_by_callee`` set.
        """
        existing = self._write_record.get(key)
        self._write_record[key] = _WriteRecord(
            body_operation_number,
            _BODY_DEPTH,
            is_from_callee=False,
            ever_set_by_callee=existing is not None and existing.ever_set_by_callee,
        )

    def record_callee_write(
        self,
        key: tuple[str, ...],
        body_operation_number: int,
        depth: int,
        *,
        occupant_is_callee_derived: bool,
    ):
        """Record that a callee's contract authored ``key`` at ``(body_operation_number, depth)``."""
        self._write_record[key] = _WriteRecord(
            body_operation_number,
            depth,
            is_from_callee=occupant_is_callee_derived,
            ever_set_by_callee=True,
        )

    def rekey_records_for_move(
        self, from_key: tuple[str, ...], to_key: tuple[str, ...]
    ):
        """Relocate the moved subtree's write records to follow a state move.

        Must run after the state subtree has moved to ``to_key``: it mirrors that
        move.
        """
        for relative_key, _node in self._state.subtree_items(to_key):
            record = self._write_record.pop(from_key + relative_key, None)
            if record is not None:
                self._write_record[to_key + relative_key] = record


class ParticleTracker:
    """Tracks which positions contain particles and what qualities those particles currently have."""

    def __init__(self):
        """Initialize an empty particle tracker."""
        self._store: _ParticleStateStore = _ParticleStateStore()
        self._pending: _PendingNestedGuarantees = _PendingNestedGuarantees()
        # Monotonic body-operation counter, advanced once per body mutation and
        # once per trigger.
        self._body_operation_number: int = 0

    def _ensure_action_parent(self, key: tuple[str, ...]):
        """Create the action intermediate trie node if needed."""
        if len(key) >= 2 and key[-2].startswith(_ACTION_KEY_PREFIX):
            parent_key = key[:-1]
            if parent_key not in self._store.state:
                self._store.state[parent_key] = _NodeState()

    def _record_body_write(
        self, key: tuple[str, ...], *, advance_body_operation_number: bool = True
    ):
        """Record that this Action Statement Block's own body made a change to ``key`` (as opposed to compiler internals).

        Advances the body operation number first, so each body statement gets a
        later number than the one before it. A move authors two positions in the
        same statement, so it passes ``advance_body_operation_number=False`` for
        the second.
        """
        if advance_body_operation_number:
            self._body_operation_number += 1
        self._store.record_body_write(key, self._body_operation_number)

    def mark_error(self, in_position: ast.PositionReference):
        """Mark a position as having error occupancy state."""
        key = in_position.canonical_chained_name_tuple
        self._apply_pending_guarantees_up_to(key)
        self._record_body_write(key)
        self._store.error[key] = _ErrorState(caused_by=in_position)

    def mark_empty(self, in_position: ast.PositionReference):
        """Mark a position as known-empty without a prior particle existing."""
        key = in_position.canonical_chained_name_tuple
        self._apply_pending_guarantees_up_to(key)
        if key in self._store.state:
            raise ValueError(f"position {key} already has tracker state")
        self._ensure_action_parent(key)
        self._record_body_write(key)
        self._store.state[key] = _NodeState(emptied_by=in_position)

    def has_error_state(self, in_position: ast.PositionReference) -> bool:
        """Return whether a position or any ancestor has error occupancy state."""
        return self.has_error_state_by_key(in_position.canonical_chained_name_tuple)

    def has_error_state_by_key(self, key: tuple[str, ...]) -> bool:
        """Return whether a position or any ancestor has error occupancy state."""
        self._apply_pending_guarantees_up_to(key)
        return self._store.has_error_in_chain(key)

    def is_occupied(self, in_position: ast.PositionReference) -> bool:
        """Return whether a particle exists at this position."""
        return self.is_occupied_by_key(in_position.canonical_chained_name_tuple)

    def is_occupied_by_key(self, key: tuple[str, ...]) -> bool:
        """Return whether a particle exists at this position, by raw key."""
        self._apply_pending_guarantees_up_to(key)
        return self._store.is_occupied(key)

    def has_been_touched(self, key: tuple[str, ...]) -> bool:
        """Return whether a guarantee or particle statement has decided this position's state."""
        self._apply_pending_guarantees_up_to(key)
        return self._store.has_been_touched(key)

    def get_occupant(self, in_position: ast.PositionReference) -> ParticleInfo:
        """Return the info for the particle at this position."""
        return self.get_occupant_by_key(in_position.canonical_chained_name_tuple)

    def get_occupant_by_key(self, key: tuple[str, ...]) -> ParticleInfo:
        """Return the info for the particle at this position, by raw key."""
        self._apply_pending_guarantees_up_to(key)
        return self._store.occupant(key)

    def snapshot_child_state(
        self, for_position: ast.PositionReference
    ) -> dict[tuple[str, ...], action_contract.ChildOccupancy]:
        """Capture the occupancy of every descendant position, keyed relative to for_position.

        The result is plain immutable data, decoupled from later tracker
        mutation. Each key is the chained-name suffix below the snapshotted
        particle, so a caller's snapshot of the same particle shares the key
        space and merges directly.
        """
        key = for_position.canonical_chained_name_tuple
        # TODO: Not sure we actually need to fully resolve this; I think there's a world
        # in which we use references somehow here just like we do with normal guarantees.
        self._fully_resolve_pending_guarantees(key)
        result: dict[tuple[str, ...], action_contract.ChildOccupancy] = {}
        for relative_key, node in self._store.state.subtree_items(key):
            if node.particle_info is not None:
                result[relative_key] = action_contract.ChildOccupancy(
                    action_contract.PositionOccupancyState.OCCUPIED,
                    filled_at=node.particle_info.last_position.location,
                )
            elif node.emptied_by is not None:
                result[relative_key] = action_contract.EMPTY_OCCUPANCY
        # An error entry wins over a stale state entry, so it is applied last.
        for relative_key, error_state in self._store.error.subtree_items(key):
            if error_state.caused_by is not None:
                result[relative_key] = action_contract.ERROR_OCCUPANCY
        return result

    def create(
        self,
        in_position: ast.PositionReference,
        qualities: tuple[ast.GlobalTypedNameReference, ...],
        *,
        from_caller: ast.PositionReference | None = None,
    ):
        """Record a new particle at this position.

        Args:
            in_position: Where the particle is being created.
            qualities: The qualities this particle has, in assignment order.
            from_caller: When provided, the particle represents one passed in by the
                caller, and this is its caller-side chained name.

        Raises ValueError if the position is already occupied.
        """
        key = in_position.canonical_chained_name_tuple
        self._apply_pending_guarantees_up_to(key)
        self._ensure_action_parent(key)
        self._record_body_write(key)
        existing = self._store.state.get(key)
        if existing is not None and existing.particle_info is not None:
            raise ValueError(f"position {key} is already occupied")
        info = ParticleInfo(
            last_position=in_position,
            qualities=qualities,
            origin_position=from_caller if from_caller is not None else in_position,
            from_caller=from_caller is not None,
        )
        if existing is not None:
            existing.particle_info = info
            existing.emptied_by = None
        else:
            self._store.state[key] = _NodeState(particle_info=info)

    def destroy(self, in_position: ast.PositionReference):
        """Remove a particle from this position.

        Raises ValueError if the position is not occupied.
        """
        key = in_position.canonical_chained_name_tuple
        self._apply_pending_guarantees_up_to(key)
        existing = self._store.state.get(key)
        if existing is None or existing.particle_info is None:
            raise ValueError(f"position {key} is not occupied")
        del self._store.state[key]
        # Destroying puts all children back into a known state (they don't exist).
        if key in self._store.error:
            del self._store.error[key]
        self._record_body_write(key)
        self._store.state[key] = _NodeState(emptied_by=in_position)

    def get_emptied_by(
        self, position: ast.PositionReference
    ) -> ast.PositionReference | None:
        """Return the position reference that emptied this position, if any."""
        return self.get_emptied_by_key(position.canonical_chained_name_tuple)

    def get_emptied_by_key(self, key: tuple[str, ...]) -> ast.PositionReference | None:
        """Return the position reference that emptied this position, by raw key."""
        self._apply_pending_guarantees_up_to(key)
        return self._store.emptied_by(key)

    def move(self, source: ast.PositionReference, target: ast.PositionReference):
        """Move a particle from one position to another.

        Children of the source position move with it. After the move,
        the source position is marked as emptied.
        """
        from_key = source.canonical_chained_name_tuple
        to_key = target.canonical_chained_name_tuple
        self._fully_resolve_pending_guarantees(from_key)
        self._apply_pending_guarantees_up_to(to_key)
        if self.has_error_state_by_key(from_key) or self.has_error_state_by_key(to_key):
            raise RuntimeError(
                f"cannot move between positions with error state: {from_key} -> {to_key}"
            )
        self._ensure_action_parent(to_key)
        # Both positions are touched by this one move statement, so they share a
        # body operation number.
        self._record_body_write(from_key)
        self._record_body_write(to_key, advance_body_operation_number=False)
        # TODO: Move last_position into _NodeState so that move_subtree
        # doesn't need this post-move fixup.
        moved_info = self._store.state[from_key].particle_info
        if moved_info is not None:
            moved_info = moved_info.move_to(target)

        to_state = self._store.state.get(to_key)
        if to_state is not None:
            # This should never happen, it's just a defensive check.
            if to_state.particle_info is not None:
                raise ValueError(f"destination position {to_key} is already occupied")
            # The target may already exist as an empty node (previously
            # destroyed). Delete it before moving so move_subtree succeeds.
            del self._store.state[to_key]
        self._store.state.move_subtree(from_key, to_key)
        self._store.state[to_key].particle_info = moved_info
        self._store.state[from_key] = _NodeState(emptied_by=source)
        self._store.rekey_records_for_move(from_key, to_key)

    def generate_own_guarantees(
        self,
        interface_names: tuple[ast.TypedName, ...],
        implied_quality_names: tuple[ast.GlobalTypedNameReference, ...],
        requirements: dict[tuple[str, ...], action_contract.PositionRequirement],
    ) -> list[action_contract.GuaranteePair]:
        """Generate this block's own guarantees, excluding the callee-derived keys carried via nested guarantees.

        The own guarantees come from keys whose first element matches an
        interface or implied quality. ``requirements`` is the validator's
        inferred-requirements dict.
        """
        return self._collect_contracted_position_guarantees(
            interface_names,
            implied_quality_names,
            requirements,
            include_callee_derived=False,
        )

    def generate_flattened_guarantees(
        self,
        interface_names: tuple[ast.TypedName, ...],
        implied_quality_names: tuple[ast.GlobalTypedNameReference, ...],
        requirements: dict[tuple[str, ...], action_contract.PositionRequirement],
    ) -> list[action_contract.GuaranteePair]:
        """Produce every guarantee this block makes, with all triggered guarantees flattened in.

        Unlike generate_own_guarantees, the guarantees of triggered actions are
        expanded into the base state and surfaced (callee-derived keys included)
        rather than deferred behind nested guarantees. A destructor needs this:
        it may not change any contracted position, including via a triggered
        action, so every such guarantee must be visible for checking (DLP 41).
        """
        self._fully_resolve_pending_guarantees(())
        return self._collect_contracted_position_guarantees(
            interface_names,
            implied_quality_names,
            requirements,
            include_callee_derived=True,
        )

    def _collect_contracted_position_guarantees(
        self,
        interface_names: tuple[ast.TypedName, ...],
        implied_quality_names: tuple[ast.GlobalTypedNameReference, ...],
        requirements: dict[tuple[str, ...], action_contract.PositionRequirement],
        *,
        include_callee_derived: bool,
    ) -> list[action_contract.GuaranteePair]:
        """Collect and sort the guarantees for every contracted key, excluding the ones _guarantee_for_key reports as no-ops."""
        include_names = {
            name.full_typed_name for name in (*interface_names, *implied_quality_names)
        }

        # generate_own_guarantees excludes keys that came only from our caleees.
        # generate_flattened_guarantees includes all keys.
        all_keys = self._store.keys_for_guarantees(
            include_callee_derived=include_callee_derived
        )

        guarantees: list[action_contract.GuaranteePair] = []
        for key in all_keys:
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
        return guarantees

    def _guarantee_for_key(
        self,
        key: tuple[str, ...],
        requirements: dict[tuple[str, ...], action_contract.PositionRequirement],
    ) -> action_contract.PositionGuarantee | None:
        """Build a guarantee from the current tracker state, or None for no-ops.

        Returns None when the guarantee would describe state identical to the
        action's starting state: a from-caller particle that never left its origin,
        or an empty position that was inferred-empty at the start and never set by
        a callee (with one exception: see the docstring of _WriteRecord.ever_set_by_callee).
        """
        error_state = self._store.error.get(key)
        if error_state is not None and error_state.caused_by is not None:
            return action_contract.ErrorGuarantee(caused_by=error_state.caused_by)
        state = self._store.state.get(key)
        if state is not None and state.particle_info is not None:
            info = state.particle_info
            if info.from_caller:
                if key == info.origin_position.canonical_chained_name_tuple:
                    return None
                return action_contract.OccupiedByExistingGuarantee(
                    origin_position=info.origin_position,
                    caused_by=info.last_position,
                )
            return action_contract.OccupiedByNewGuarantee(
                qualities=info.qualities,
                caused_by=info.last_position,
            )
        caused_by = state.emptied_by if state is not None else None
        if caused_by is None:
            raise ValueError(f"no caused_by for empty position {key}")
        requirement = requirements.get(key)

        if (
            requirement is not None
            and requirement.required_state
            == action_contract.PositionOccupancyState.EMPTY
            # A callee that filled this key and then had it emptied still needs the
            # EmptyGuarantee emitted, to override the callee's lingering fill
            # guarantee (see _WriteRecord.ever_set_by_callee).
            #
            # TODO: I find this inconsistency frustrating but haven't been able
            # to yet reason through a better solution.
            and not self._store.ever_set_by_callee(key)
        ):
            return None
        return action_contract.EmptyGuarantee(caused_by=caused_by)

    def apply_guarantees(
        self,
        parent_chain: ast.ChainedName,
        guarantees: action_contract.Guarantees,
    ) -> action_contract.NestedGuarantees:
        """Apply the guarantees for a triggered action.

        ``parent_chain`` is a triggered action's chain.

        The callee's own guarantees are applied immediately. Any nested guarantees
        from the callee will be applied lazily during later operations.

        Returns a nested guarantee for this action to record.
        """
        self._body_operation_number += 1
        parent_chain_key = parent_chain.canonical_chained_name_tuple
        callee_guarantees = _PendingGuarantee(
            parent_chain_key, guarantees, self._body_operation_number
        )
        self._apply_pending_guarantee(callee_guarantees)
        return action_contract.NestedGuarantees(
            triggered_action=parent_chain_key, guarantees=guarantees
        )

    def _apply_pending_guarantee(self, pending_guarantee: _PendingGuarantee):
        """Apply a callee's own guarantees; prefix its own nested guarantees one position deeper."""
        self._update_store_from_callee_direct_guarantees(pending_guarantee)
        for child in pending_guarantee.guarantees.nested:
            child_position = pending_guarantee.key_for(child.triggered_action)
            child_nested_guarantee = _PendingGuarantee(
                child_position,
                child.guarantees,
                pending_guarantee.body_operation_number,
                pending_guarantee.call_chain_depth + 1,
            )
            self._pending.add(child_nested_guarantee)

    def _apply_pending_guarantees_up_to(self, key: tuple[str, ...]):
        """Apply any nested guarantee on the path from root to ``key``."""
        for pending_guarantee in self._pending.drain_shortest_first(key):
            self._apply_pending_guarantee(pending_guarantee)

    def _fully_resolve_pending_guarantees(self, key: tuple[str, ...]):
        """Apply the nested guarantee at ``key`` (if any) and every one below it."""
        self._apply_pending_guarantees_up_to(key)
        for pending_guarantee in self._pending.drain_at_or_below(key):
            self._apply_pending_guarantee(pending_guarantee)

    def _update_store_from_callee_direct_guarantees(
        self, pending_guarantee: _PendingGuarantee
    ):
        guarantees = pending_guarantee.guarantees.own

        # Make a list of only the origin_positions for OccupiedByExistingGuarantee.
        # We need this list later to know what to "save" before we apply guarantees.
        origin_keys: set[tuple[str, ...]] = set()
        for _name, guarantee in guarantees:
            if isinstance(guarantee, action_contract.OccupiedByExistingGuarantee):
                origin_tuple = guarantee.origin_position.canonical_chained_name_tuple
                origin_keys.add(pending_guarantee.key_for(origin_tuple))

        # Saved subtrees for swap safety. Keyed by the origin's full key.
        saved_state: dict[tuple[str, ...], trie.StrictReparentingTrie[_NodeState]] = {}
        saved_error: dict[tuple[str, ...], trie.StrictReparentingTrie[_ErrorState]] = {}

        for name, guarantee in guarantees:
            key = pending_guarantee.key_for(name)

            # A later-running statement already finalized this key, so this
            # guarantee must not override it.
            if self._store.is_superseded(
                key,
                pending_guarantee.body_operation_number,
                pending_guarantee.call_chain_depth,
            ):
                continue

            if not self._check_key_exists_for_guarantee(key, guarantee):
                continue

            self._ensure_action_parent(key)
            self._store.record_callee_write(
                key,
                pending_guarantee.body_operation_number,
                pending_guarantee.call_chain_depth,
                # OccupiedByExisting depends on caller-passed particle identity, so
                # it must be resolved here (a distant caller can't reconstruct it)
                # and emitted as this block's own guarantee. Other guarantee types
                # are re-derivable in any caller, so they stay behind the nested guarantee.
                occupant_is_callee_derived=not isinstance(
                    guarantee, action_contract.OccupiedByExistingGuarantee
                ),
            )

            if key in origin_keys:
                # Save-before-overwrite: if this key is an origin for a later
                # OccupiedByExisting, pop it and its children so the later guarantee
                # can read from the saved copy.
                #
                # Two OccupiedByExisting guarantees can reference each other's positions
                # as origins (e.g., the action swaps position<a> and position<b>). So we
                # have to save the state of any position listed as an origin position
                # that we _might_ be about to overwrite with any other guarantee. (Things
                # like running OccupiedByNew accidentally before OccupiedByExisting are
                # already handled by caused_by sorting, above.)
                if key in self._store.state:
                    saved_state[key] = self._store.state.pop_subtree(key)
                if key in self._store.error:
                    saved_error[key] = self._store.error.pop_subtree(key)
            elif key in self._store.state:
                # Subtree cleanup: If an action empties position<item> (EmptyGuarantee)
                # or creates in position<item> (OccupiedByNewGuarantee), any children
                # the caller had under position<item> must disappear. We achieve this
                # by deleting each key's entire subtree before applying its guarantee.
                del self._store.state[key]
                if key in self._store.error:
                    del self._store.error[key]

            match guarantee:
                case action_contract.OccupiedByExistingGuarantee():
                    self._apply_existing_guarantee(
                        key,
                        pending_guarantee,
                        guarantee,
                        saved_state,
                        saved_error,
                    )
                case action_contract.EmptyGuarantee():
                    self._store.state[key] = _NodeState(emptied_by=guarantee.caused_by)
                case action_contract.OccupiedByNewGuarantee():
                    new_info = ParticleInfo(
                        last_position=guarantee.caused_by,
                        qualities=guarantee.qualities,
                        origin_position=guarantee.caused_by,
                    )
                    self._store.state[key] = _NodeState(particle_info=new_info)
                case action_contract.ErrorGuarantee():
                    self._store.error[key] = _ErrorState(caused_by=guarantee.caused_by)
                case _:
                    raise TypeError(f"Unexpected guarantee type: {type(guarantee)}")

    def _check_key_exists_for_guarantee(
        self,
        key: tuple[str, ...],
        guarantee: action_contract.PositionGuarantee,
    ) -> bool:
        """Check whether the parent path for a guarantee key is present.

        This happens only when the caller of an action did not fill a required
        position and now we are trying to apply a guarantee to a child of that
        position. If that happened for this key, we mark the first missing node
        as error and return False to indicate the guarantee should be skipped.

        Returns True when the parent path is fully in the state trie (or
        could be completed by _ensure_action_parent).
        """
        ancestor_key = self._store.state.existing_prefix(key)
        if len(ancestor_key) >= len(key) - 1:
            return True
        # Parent path is incomplete. _ensure_action_parent can fill
        # exactly one gap when the missing node is an action
        # intermediate and its own parent exists.
        first_missing = key[len(ancestor_key)]
        can_bridge = len(ancestor_key) == len(key) - 2 and first_missing.startswith(
            _ACTION_KEY_PREFIX
        )
        if can_bridge:
            return True
        # The caller never filled a required position ancestor.
        # Mark the first missing node as error.
        missing_key = (*ancestor_key, first_missing)
        self._store.error[missing_key] = _ErrorState(caused_by=guarantee.caused_by)
        return False

    def _apply_existing_guarantee(
        self,
        dest_key: tuple[str, ...],
        pending_guarantee: _PendingGuarantee,
        guarantee: action_contract.OccupiedByExistingGuarantee,
        saved_state: dict[tuple[str, ...], trie.StrictReparentingTrie[_NodeState]],
        saved_error: dict[tuple[str, ...], trie.StrictReparentingTrie[_ErrorState]],
    ):
        """Apply an OccupiedByExisting guarantee at dest_key."""
        origin_tuple = guarantee.origin_position.canonical_chained_name_tuple
        origin_key = pending_guarantee.key_for(origin_tuple)

        # Get origin's particle_info — from saved copy if already processed,
        # else from the live trie.
        saved_tree = saved_state.pop(origin_key, None)
        if saved_tree is not None:
            origin_state = saved_tree[origin_tuple[-1:]]
        elif origin_key in self._store.state:
            origin_state = self._store.state[origin_key]
        else:
            # The caller never filled the position, and we are executing an OccupiedByExisting
            # guarnatee on the same position that a particle was passed in on.
            self._store.error[dest_key] = _ErrorState(caused_by=guarantee.caused_by)
            return

        # The caller never filled the input interface position. The callee moves the particle to
        # another position. Thus, the origin_state _exists_ but the position got EmptyGuarantee
        # instead of being filled by something (and there's nothing in saved_state).
        if origin_state.particle_info is None:
            self._store.error[dest_key] = _ErrorState(caused_by=guarantee.caused_by)
            return

        moved_info = origin_state.particle_info.move_to(guarantee.caused_by)
        if saved_tree is not None:
            # If we have a saved_tree, we have to graft back in the children of
            # the popped subtree (the popped subtree starts with the particle
            # that we are moving, and we need to re-create it with moved_info).
            self._store.state[dest_key] = _NodeState(particle_info=moved_info)
            self._store.state.graft_subtree(dest_key, saved_tree.root_children())
        else:
            self._store.state.move_subtree(origin_key, dest_key)
            self._store.state[dest_key] = _NodeState(particle_info=moved_info)

        saved_unk = saved_error.pop(origin_key, None)
        # Guarantees reset the error state of particles they touch directly.
        # If we guarantee a particle in a position, then we know that it has a
        # particle. However, its _children_ might still be in some error state.
        # Exception: if the origin had pre-action error state (saved before the
        # guarantee loop began), the destination inherits that caused_by — the
        # guarantee fills it with whatever was at origin, including the uncertainty.
        if saved_unk is not None:
            origin_error = saved_unk[origin_tuple[-1:]]
            self._store.error[dest_key] = _ErrorState(caused_by=origin_error.caused_by)
            self._store.error.graft_subtree(dest_key, saved_unk.root_children())
        elif origin_key in self._store.error:
            self._store.error.move_subtree(origin_key, dest_key)
            self._store.error[dest_key] = _ErrorState()
