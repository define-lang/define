"""Tracks particle occupancy for positions within an action block."""

from __future__ import annotations

import typing
from dataclasses import dataclass

from define.compiler import ast
from define.compiler.data_structures import trie
from define.compiler.validator.reference_graph import (
    action_contract,
    operation_graph,
    operation_graph_model,
    quality_assignment,
)

if typing.TYPE_CHECKING:
    from collections.abc import (
        Collection,
        Iterable,
        Iterator,
        Sequence,
    )


@dataclass(slots=True)
class ParticleInfo:
    """Information about a tracked particle."""

    # The last position reference written in the code for the last
    # statement that relocated or created this particle.
    last_position: ast.PositionReference
    # The qualities we know that this particle has, in
    # assignment order.
    qualities: quality_assignment.QualityAssignments
    # The position reference where this particle was first created. The DLP 42
    # liveness check keys a move's satisfied constraints off this: a constraint is
    # only kept alive by a move if the particle was created in the position that
    # wrote it.
    origin_position: ast.PositionReference
    # Whether this particle was passed in by the caller (trigger/inferred) vs created in the body.
    from_caller: bool = False


@dataclass(frozen=True, slots=True)
class OccupancyInfo:
    """A position's error state and occupant, resolved together in one lookup."""

    # When an ancestor is in an error condition we ignore the position entirely,
    # so the occupant is meaningless and left None.
    has_error: bool
    occupant: ParticleInfo | None


@dataclass(frozen=True, slots=True)
class ResolvedRequirementPosition:
    """A local requirement position and the contracted position it resolves to."""

    local_position: ast.PositionReference
    contracted_position: ast.PositionReference
    required_state: action_contract.PositionOccupancyState


@dataclass(frozen=True, slots=True)
class PropagatedRequirement:
    """A callee requirement that must be propagated into the current contract."""

    requirement_in_caller: action_contract.PositionRequirementInCaller
    contracted_position: ast.PositionReference


@dataclass
class _NodeState:
    """Mutable state for a position in the state trie."""

    particle_info: ParticleInfo | None = None
    emptied_by: ast.PositionReference | None = None
    # Keeping the exact-position operation with the state makes it follow moves,
    # so child-operation snapshots only need to be built when an operation uses one.
    # TODO: Reconsider the boundary between particle tracking and operation-graph
    # construction; this is operation-graph metadata stored here for reparenting.
    operation_node: operation_graph_model.ConcreteOperationNode | None = None


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
    at the same number the lower ``depth`` wins (a contract's own guarantee
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
    guarantee is applied; its own nested guarantees gain one child name in their prefix.
    """

    # The triggered action's chain.
    action_chain: tuple[str, ...]
    guarantees: action_contract.Guarantees
    # The body operation number of the Action Execution that produced this nested
    # guarantee.
    # All of a triggered contract's guarantees (own and nested) carry it, so a
    # body statement that executes later supersedes them.
    body_operation_number: int
    # DLP 44: the Action Execution, in the operation graph, that fired this callee.
    # Each contracted position the guarantee touches has its last operation
    # pointed at the operation that fired it, so the caller's later ops on it
    # depend on it through the Fill, Empty, or Move Rule. Nested children inherit
    # it verbatim (the whole callee subtree happens, from the caller's view, at
    # the one Action Execution).
    execution: operation_graph_model.ActionExecution
    # The full action chain whose graph contains the operation that last
    # affected these guaranteed positions. A Move keeps this chain at the action
    # performing the Move while the guaranteed positions continue beneath the
    # moved particle.
    operation_graph_action_chain: tuple[str, ...]
    # All the callees down to the one that actually first created this guarantee.
    # Direct callee first and original creator last.
    transitive_executions: tuple[operation_graph_model.ActionExecution, ...] = ()
    # Call-chain depth from the directly-applied contract: its own guarantees
    # are depth 0; each nested guarantee increments the depth. Within a single
    # Action Execution (same sequence), a lower-depth guarantee outranks a higher-depth
    # one it resolved.
    call_chain_depth: int = 0

    @property
    def parent_position(self) -> tuple[str, ...]:
        """The parent of the callee's implied (global) positions.

        This is ``action_chain`` with its trailing action stripped: an implied
        quality lives on the action's parent particle, at the parent name of the
        action's interface position names. ``action_chain`` always ends in the
        triggered action, since that is the only thing that produces guarantees.
        """
        return self.action_chain[:-1]

    def key_for(self, name: tuple[str, ...]) -> tuple[str, ...]:
        """Return the absolute key for a guarantee this action names ``name``."""
        return ast.chain_in_caller(self.action_chain, name)


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
    queried position (shortest prefix first); ``drain_at_or_below`` yields the
    ones for which the queried position is a parent name. Both remove what they
    yield and re-query as they go: applying a yielded nested guarantee can add
    ones with additional child names, which the drain then picks up.
    """

    def __init__(self):
        self._by_prefix: dict[tuple[str, ...], list[_PendingGuarantee]] = {}
        self._longest_pending_guarantee_key: int = 0

    def add(self, nested_guarantee: _PendingGuarantee):
        """Record a nested guarantee to apply once a query reaches ``prefix`` or one of its child names."""
        # Store the pending nested guarantee by its parent_position, the
        # common ancestor of the callee's interface guarantees (which are
        # prefixed with the trigger position) and its implied guarantees (which
        # are prefixed with the parent_position itself). Using the trigger
        # position instead would leave the implied guarantees outside that
        # subtree, so a query on an implied position would never apply it.
        prefix = nested_guarantee.parent_position
        self._by_prefix.setdefault(prefix, []).append(nested_guarantee)
        self._longest_pending_guarantee_key = max(
            self._longest_pending_guarantee_key, len(prefix)
        )

    def drain_shortest_first(self, key: tuple[str, ...]) -> Iterator[_PendingGuarantee]:
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
            prefix = key[:length]
            # Applying a yielded guarantee can re-add one at this same prefix, so
            # drain it fully before moving to a prefix with another child name.
            while prefix in self._by_prefix:
                yield from self._by_prefix.pop(prefix)
            length += 1

    def drain_shortest_first_for(
        self, keys: Iterable[tuple[str, ...]]
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
        previous_key: tuple[str, ...] | None = None
        for key in keys:
            if previous_key is None:
                # A pending implied-action guarantee can use the empty tuple as
                # its prefix, so the first path must begin there.
                length = 0
            else:
                # Every prefix shared with the preceding path was already fully
                # drained. Find the first prefix unique to this path instead of
                # repeating those dictionary lookups.
                common_depth = 0
                common_depth_limit = min(
                    len(previous_key),
                    len(key),
                    # No pending prefix can be longer than this cached depth, so
                    # comparing additional names cannot let us skip more lookups.
                    self._longest_pending_guarantee_key,
                )
                while (
                    common_depth < common_depth_limit
                    and previous_key[common_depth] == key[common_depth]
                ):
                    common_depth += 1
                # ``common_depth`` is the length of the last shared prefix; the
                # next length is therefore the first prefix not yet drained.
                length = common_depth + 1
            key_len = len(key)
            # A guarantee can affect the queried position only when its prefix
            # is one of the queried position's parent names.
            while length < key_len and length <= self._longest_pending_guarantee_key:
                prefix = key[:length]
                # Applying a guarantee can add another pending guarantee at this
                # same prefix, so do not advance until the prefix stays empty.
                while prefix in self._by_prefix:
                    yield from self._by_prefix.pop(prefix)
                # Once no pending guarantees remain, no later path can yield
                # anything.
                if not self._by_prefix:
                    self._longest_pending_guarantee_key = 0
                    return
                length += 1
            previous_key = key

    def drain_at_or_below(self, key: tuple[str, ...]) -> Iterator[_PendingGuarantee]:
        """Yield guarantees whose prefixes equal ``key`` or have it as a parent name."""
        depth = len(key)
        # The reason for this outer while loop is that our caller adds more prefixes
        # as they are running.
        while matching := [
            p for p in self._by_prefix if len(p) >= depth and p[:depth] == key
        ]:
            for prefix in matching:
                yield from self._by_prefix.pop(prefix)


class _CurrentActionNestedGuarantees:
    """Nested guarantees keyed by the action chain where they currently apply.

    Stores the nested guarantees that will directly become part of this action's
    contract.
    """

    def __init__(self):
        self._by_action_chain: trie.LenientReparentingTrie[
            list[action_contract.NestedGuarantees]
        ] = trie.LenientReparentingTrie(default_factory=list)

    def add(
        self,
        action_chain: tuple[str, ...],
        nested_guarantees: action_contract.NestedGuarantees,
    ):
        at_action_chain = self._by_action_chain.get(action_chain)
        if at_action_chain is None:
            at_action_chain = []
            self._by_action_chain[action_chain] = at_action_chain
        at_action_chain.append(nested_guarantees)

    def move(self, source: tuple[str, ...], target: tuple[str, ...]):
        """Move nested guarantees beneath a moved particle."""
        if source not in self._by_action_chain:
            return
        self._by_action_chain.move_subtree(source, target)

    def discard_for_destroyed_particle(self, position: tuple[str, ...]):
        """Discard nested guarantees belonging to a destroyed particle."""
        if position in self._by_action_chain:
            del self._by_action_chain[position]

    def pop_subtrees(
        self, positions: Iterable[tuple[str, ...]]
    ) -> dict[
        tuple[str, ...],
        trie.StrictReparentingTrie[list[action_contract.NestedGuarantees]],
    ]:
        """Detach nested guarantees belonging to particles that may move."""
        return self._by_action_chain.pop_subtrees(positions)

    def restore_moved_particle(
        self,
        source: tuple[str, ...],
        target: tuple[str, ...],
        saved_subtree: trie.StrictReparentingTrie[
            list[action_contract.NestedGuarantees]
        ],
    ):
        """Restore a saved particle's nested guarantees at its destination."""
        self._by_action_chain.restore_subtree(
            target, saved_subtree, saved_subtree[source[-1:]]
        )

    def items(self) -> action_contract.NestedGuaranteesByActionChain:
        """Return nested guarantees in triggering order."""
        result = [
            (action_chain, nested_guarantees)
            for action_chain, guarantees in self._by_action_chain.items()
            for nested_guarantees in guarantees
        ]
        result.sort(
            key=lambda item: item[1].execution.trigger_operation.operation_order
        )
        return tuple(result)


_ACTION_KEY_PREFIX = f"{ast.NameType.ACTION.value}<"


class _ParticleStateStore:
    """The internal position state store, which tracks both the state of a particle and how it's related to our callees' contracts.

    Particle state lives in two tries (``state`` and ``error``). Particles
    in ``error`` are in an error condition---the compiler detected a problem
    but wants to continue compiling to see if it can find more errors. We ignore
    all particles in error states.

    Each position that gets touched during an Action Statements Block also
    carries a _WriteRecord that tells us about the order in which the operation
    was performed and whether this particle came from a guarantee or was performed
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

    def occupant_or_none(self, key: tuple[str, ...]) -> ParticleInfo | None:
        """Return the particle at this position, or None if it is empty."""
        state = self._state.get(key)
        return state.particle_info if state is not None else None

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

    def nearest_occupied_ancestors(
        self, keys: Sequence[tuple[str, ...]]
    ) -> dict[tuple[str, ...], tuple[tuple[str, ...], ParticleInfo] | None]:
        """Return the nearest occupied ancestor for each distinct key."""
        ancestor_keys = self._state.find_longest_prefixes_where(
            keys, lambda node_state: node_state.particle_info is not None
        )
        results: dict[tuple[str, ...], tuple[tuple[str, ...], ParticleInfo] | None] = {}
        for key, ancestor_key in ancestor_keys.items():
            if ancestor_key is None:
                results[key] = None
                continue
            particle_info = self._state[ancestor_key].particle_info
            if particle_info is None:
                raise ValueError(f"position {ancestor_key} lost its particle")
            results[key] = ancestor_key, particle_info
        return results

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
        lower call-chain depth (a contract's own guarantee outranks the
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

    def record_callee_write(self, key: tuple[str, ...], record: _WriteRecord):
        """Record that a callee's contract authored ``key``."""
        self._write_record[key] = record

    def try_add_action_parent(self, key: tuple[str, ...]) -> tuple[str, ...] | None:
        """Create ``key``'s action intermediate when that is the only absent parent name.

        Returns the first absent parent name of ``key``, or None when every
        parent name of ``key`` is present.
        """
        # A strict trie holds a parent name for every key it holds, so a single
        # present parent name means the whole chain above it is present too.
        # That is why two probes settle a question about every parent name.
        parent_key = key[:-1]
        if not parent_key or parent_key in self._state:
            return None
        # The parent name is absent, so the invariant above says nothing about
        # the rest of the chain and the grandparent has to be probed too.
        grandparent_key = parent_key[:-1]
        if not grandparent_key or grandparent_key in self._state:
            # The parent name is the only absent one. A strict trie refuses a
            # write whose own parent name is missing, so this is the only case
            # where the compiler may add the action intermediate. A parent name
            # that is anything else is a position the caller never filled.
            if parent_key[-1].startswith(_ACTION_KEY_PREFIX):
                # Repeated _NodeState construction for action-intermediate trie
                # keys looked costly in the default action-graph full-compiler
                # benchmark. An August 2026 experiment replaced every fresh value
                # here and in _ensure_action_parent with one shared _NodeState;
                # unprofiled runs showed no measurable wall-time change.
                self._state[parent_key] = _NodeState()
                return None
            return parent_key
        # Two or more names are absent, so only a walk can say which of them the
        # caller left unfilled first.
        present_prefix = self._state.existing_prefix(key)
        return (*present_prefix, key[len(present_prefix)])

    def rekey_records_for_move(
        self, from_key: tuple[str, ...], to_key: tuple[str, ...]
    ):
        """Relocate the moved subtree's write records to follow a state move.

        Must run after the state subtree has moved to ``to_key``: it mirrors that
        move.
        """
        to_length = len(to_key)
        for new_key in self._state.subtree_keys(to_key):
            record = self._write_record.pop(from_key + new_key[to_length:], None)
            if record is not None:
                self._write_record[new_key] = record


class ParticleTracker:
    """Tracks which positions contain particles and what qualities those particles currently have."""

    def __init__(self, action: ast.GlobalTypedName):
        """Initialize an empty particle tracker."""
        self._store: _ParticleStateStore = _ParticleStateStore()
        self._pending: _PendingNestedGuarantees = _PendingNestedGuarantees()
        self._nested_guarantees: _CurrentActionNestedGuarantees = (
            _CurrentActionNestedGuarantees()
        )
        # Monotonic body-operation counter, advanced once per body mutation and
        # once per trigger.
        self._body_operation_number: int = 0
        self._operation_graph: operation_graph.OperationGraph = (
            operation_graph.OperationGraph(action)
        )

    @property
    def operation_graph(self) -> operation_graph.OperationGraph:
        """The DLP 44 dependency graph of this action's body operations."""
        return self._operation_graph

    def _ensure_action_parent(self, key: tuple[str, ...]):
        """Create the action intermediate trie node if needed."""
        if len(key) >= 2 and key[-2].startswith(_ACTION_KEY_PREFIX):
            parent_key = key[:-1]
            if parent_key not in self._store.state:
                # This is the other repeated allocation from the default
                # action-graph full-compiler experiment documented in
                # try_add_action_parent: replacing both paths' fresh _NodeState
                # values with one shared object showed no measurable wall-time change.
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
        key = in_position.canonical_chained_name_tuple
        self._apply_pending_guarantees_up_to(key)
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
        self._apply_pending_guarantees_up_to(key)
        if self._store.has_error_in_chain(key):
            return OccupancyInfo(has_error=True, occupant=None)
        return OccupancyInfo(
            has_error=False,
            occupant=self._store.occupant_or_none(key),
        )

    def is_occupied(self, in_position: ast.PositionReference) -> bool:
        """Return whether a particle exists at this position."""
        key = in_position.canonical_chained_name_tuple
        self._apply_pending_guarantees_up_to(key)
        return self._store.is_occupied(key)

    def has_been_touched(self, in_position: ast.PositionReference) -> bool:
        """Return whether a guarantee or particle statement has decided this position's state."""
        key = in_position.canonical_chained_name_tuple
        self._apply_pending_guarantees_up_to(key)
        return self._store.has_been_touched(key)

    def infer_direct_requirements(
        self,
        position: ast.PositionReference,
        required_state: action_contract.PositionOccupancyState,
        interface_position_names: Collection[str],
    ) -> list[ResolvedRequirementPosition]:
        """Infer direct requirements and record their RequirementNodes when needed."""
        self._apply_pending_guarantees_up_to(position.canonical_chained_name_tuple)
        position_is_contracted = (
            position.starts_with_global
            or position.typed_names[0].full_typed_name in interface_position_names
        )
        canonical_position_prefixes = position.canonical_position_prefixes()
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
                else action_contract.PositionOccupancyState.OCCUPIED
            )
            self._record_requirement_in_operation_graph(
                contracted_position,
                requirement_state,
                nearest_particle,
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
        requirements_in_caller: Sequence[action_contract.PositionRequirementInCaller],
    ) -> list[PropagatedRequirement]:
        """Propagate requirements and record their RequirementNodes when needed.

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
        self._apply_pending_guarantees_up_to_all(canonical_positions)
        propagated_requirements: list[PropagatedRequirement] = []
        for requirement_index, nearest_particle in self._requirement_indices_for_caller(
            canonical_positions
        ):
            requirement_in_caller = requirements_in_caller[requirement_index]
            position = requirement_in_caller.caller_position
            contracted_position = self._contracted_position_for_requirement(
                position, nearest_particle
            )
            self._record_requirement_in_operation_graph(
                contracted_position,
                requirement_in_caller.requirement.required_state,
                nearest_particle,
            )
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
    ) -> Iterator[tuple[int, tuple[tuple[str, ...], ParticleInfo] | None]]:
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
            ) or self._store.has_been_touched(canonical_position):
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
        nearest_particle: tuple[tuple[str, ...], ParticleInfo] | None,
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

    def _record_requirement_in_operation_graph(
        self,
        contracted_position: ast.PositionReference,
        required_state: action_contract.PositionOccupancyState,
        nearest_particle: tuple[tuple[str, ...], ParticleInfo] | None,
    ):
        if nearest_particle is not None:
            particle = nearest_particle[1]
            # If the parent was moved, then its move operation is the only thing
            # that needs to go into the graph. That move operation already generated
            # a RequirementNode, and _that_ is what will depend on the caller operation.
            # Any later child operation will depend only on that move operation.
            if particle.last_position != particle.origin_position:
                return
        self._operation_graph.record_requirement(contracted_position, required_state)

    def get_occupant(self, in_position: ast.PositionReference) -> ParticleInfo:
        """Return the info for the particle at this position."""
        key = in_position.canonical_chained_name_tuple
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

    def _preceding_child_operations(
        self, key: tuple[str, ...]
    ) -> Iterator[tuple[tuple[str, ...], operation_graph_model.ConcreteOperationNode]]:
        # Valid wall profiles of the August 2026 focused operation-graph
        # full-compiler workload with 10,000 children made allocating this lambda
        # per snapshot and calling it per descendant look costly. Replacing it with
        # one module-level operator.attrgetter("operation_node") produced no
        # measurable full-compiler change across four unprofiled runs.
        return self._store.state.selected_subtree_items(
            key, lambda state: state.operation_node
        )

    def create(
        self,
        in_position: ast.PositionReference,
        qualities: quality_assignment.QualityAssignments,
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
        # Only a body create becomes a node in the operation graph.
        operation_node: operation_graph_model.CreateNode | None = None
        if from_caller is None:
            operation_node = self._operation_graph.record_create(in_position)
        info = ParticleInfo(
            last_position=in_position,
            qualities=qualities,
            origin_position=from_caller if from_caller is not None else in_position,
            from_caller=from_caller is not None,
        )
        if existing is not None:
            existing.particle_info = info
            existing.emptied_by = None
            existing.operation_node = operation_node
        else:
            self._store.state[key] = _NodeState(
                particle_info=info, operation_node=operation_node
            )

    def destroy(self, in_position: ast.PositionReference):
        """Remove a particle from this position.

        Raises ValueError if the position is not occupied.
        """
        key, preceding_child_operations, _ = self._prepare_destroy(in_position)
        operation_node = self._operation_graph.record_destroy(
            in_position,
            preceding_child_operations,
        )
        self._record_destroyed_state(key, in_position, operation_node)

    def destroy_explicit(
        self,
        in_position: ast.PositionReference,
        destruction_fact: operation_graph_model.DestructionFact,
    ):
        """Remove the particle targeted by an explicit Destroy statement."""
        key, preceding_child_operations, particle = self._prepare_destroy(in_position)
        if particle.from_caller:
            operation_node = self._operation_graph.record_destruction_fact_destroy(
                destruction_fact,
                in_position,
                preceding_child_operations,
                propagate_to_caller=True,
            )
        else:
            operation_node = self._operation_graph.record_destroy(
                in_position,
                preceding_child_operations,
            )
        self._record_destroyed_state(key, in_position, operation_node)

    def destroy_for_destruction_fact(
        self,
        in_position: ast.PositionReference,
        destruction_fact: operation_graph_model.DestructionFact,
    ):
        """Remove a particle as part of one Destruction Fact."""
        key, preceding_child_operations, particle = self._prepare_destroy(in_position)
        operation_node = self._operation_graph.record_destruction_fact_destroy(
            destruction_fact,
            in_position,
            preceding_child_operations,
            propagate_to_caller=particle.from_caller,
        )
        self._record_destroyed_state(key, in_position, operation_node)

    def _prepare_destroy(
        self, in_position: ast.PositionReference
    ) -> tuple[
        tuple[str, ...],
        operation_graph_model.PrecedingChildOperations,
        ParticleInfo,
    ]:
        """Validate a destruction and capture its child operations."""
        key = in_position.canonical_chained_name_tuple
        self._apply_pending_guarantees_up_to(key)
        existing = self._store.state.get(key)
        if existing is None or existing.particle_info is None:
            raise ValueError(f"position {key} is not occupied")
        # Capture these before the subtree is deleted so graph dependencies see
        # the child operations.
        return key, self._preceding_child_operations(key), existing.particle_info

    def _record_destroyed_state(
        self,
        key: tuple[str, ...],
        in_position: ast.PositionReference,
        operation_node: operation_graph_model.DestroyNode,
    ):
        """Record the empty state produced by a Destroy operation."""
        # We have to del to remove all the children in the trie.
        del self._store.state[key]
        # Destroying puts all children back into a known state (they don't exist).
        if key in self._store.error:
            del self._store.error[key]
        self._nested_guarantees.discard_for_destroyed_particle(key)
        self._record_body_write(key)
        self._store.state[key] = _NodeState(
            emptied_by=in_position, operation_node=operation_node
        )

    def get_emptied_by(
        self, position: ast.PositionReference
    ) -> ast.PositionReference | None:
        """Return the position reference that emptied this position, if any."""
        key = position.canonical_chained_name_tuple
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
        if self._store.has_error_in_chain(from_key) or self._store.has_error_in_chain(
            to_key
        ):
            raise RuntimeError(
                f"cannot move between positions with error state: {from_key} -> {to_key}"
            )
        self._ensure_action_parent(to_key)
        # Record before move_subtree relocates the children, so graph dependencies see them.
        source_info = self._store.state[from_key].particle_info
        if source_info is None:
            raise ValueError(f"source position {from_key} is empty")
        operation_node = self._operation_graph.record_move(
            source, target, self._preceding_child_operations(from_key)
        )
        # Both positions are touched by this one move statement, so they share a
        # body operation number.
        self._record_body_write(from_key)
        self._record_body_write(to_key, advance_body_operation_number=False)
        source_info.last_position = target

        to_state = self._store.state.get(to_key)
        if to_state is not None:
            if to_state.particle_info is not None:
                raise ValueError(f"destination position {to_key} is already occupied")
            # The target may already exist as an empty node (previously
            # destroyed). Delete it before moving so move_subtree succeeds.
            del self._store.state[to_key]

        # Empty Rule Collection treats this Move as the most recent Particle
        # Operation on every transitive child position of the moved particle.
        def record_move_on_position(moved_state: _NodeState):
            if (
                moved_state.particle_info is not None
                or moved_state.emptied_by is not None
            ):
                moved_state.operation_node = operation_node

        self._store.state.move_subtree(
            from_key,
            to_key,
            moved_value_callback=record_move_on_position,
        )
        self._store.state[from_key] = _NodeState(
            emptied_by=source, operation_node=operation_node
        )
        self._store.rekey_records_for_move(from_key, to_key)
        self._nested_guarantees.move(from_key, to_key)

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
        """Build a guarantee describing the current tracker state, or None for no-ops.

        A position whose state is identical to the action's starting state, but
        that the action operated on, gets an UnchangedGuarantee. A position that
        was left in its starting state without ever being touched produces None (this
        can only happen to the trigger position of an action).
        """
        error_state = self._store.error.get(key)
        if error_state is not None and error_state.caused_by is not None:
            return action_contract.ErrorGuarantee(
                caused_by=error_state.caused_by,
                operation_positions=(),
            )

        state = self._store.state.get(key)
        operation_positions: tuple[tuple[str, ...], ...] = ()
        if state is not None and state.operation_node is not None:
            operation_positions = state.operation_node.operated_positions
        if state is not None and state.particle_info is not None:
            info = state.particle_info
            if not info.from_caller:
                return action_contract.OccupiedByNewGuarantee(
                    qualities=info.qualities,
                    origin_position=info.origin_position,
                    caused_by=info.last_position,
                    operation_positions=operation_positions,
                )
            if key != info.origin_position.canonical_chained_name_tuple:
                return action_contract.OccupiedByExistingGuarantee(
                    origin_position=info.origin_position,
                    caused_by=info.last_position,
                    operation_positions=operation_positions,
                )
            # The caller's particle is right where it started.
            if self._position_was_touched(key):
                return action_contract.UnchangedGuarantee(
                    caused_by=info.last_position,
                    operation_positions=operation_positions,
                )
            # A trigger position was never touched by the action.
            #
            # TODO: Should we simply require people to always touch the trigger
            # position? It eliminates a lot of "more than one way to do it."
            return None

        caused_by = state.emptied_by if state is not None else None
        if caused_by is None:
            raise ValueError(f"no caused_by for empty position {key}")
        requirement = requirements.get(key)
        if (
            requirement is not None
            and requirement.required_state
            == action_contract.PositionOccupancyState.EMPTY
        ):
            # A requirement propagated from a callee doesn't mean the callee
            # operated on that position directly. (It could have been a transitive
            # callee that did it.)
            if self._position_was_touched(key):
                return action_contract.UnchangedGuarantee(
                    caused_by=caused_by,
                    operation_positions=operation_positions,
                )
            return None
        return action_contract.EmptyGuarantee(
            caused_by=caused_by,
            operation_positions=operation_positions,
        )

    def _position_was_touched(self, key: tuple[str, ...]) -> bool:
        """Whether the action ever touched ``key``."""
        return self._operation_graph.body_touched_key(
            key
        ) or self._store.ever_set_by_callee(key)

    def trigger_action(
        self,
        action_chain: ast.ActionReference,
        guarantees: action_contract.Guarantees,
        acting_on_position: ast.PositionReference,
        requirements_in_caller: Sequence[action_contract.PositionRequirementInCaller],
        *,
        is_destructor: bool,
        newly_occupied_children_by_destruction_contract: Sequence[
            operation_graph_model.DestructionContractNewlyOccupiedChildren
        ] = (),
    ) -> operation_graph_model.ActionExecution:
        """Record an Action Execution and apply the triggered action's guarantees.

        The callee's own guarantees are applied immediately. Any nested guarantees
        from the callee will be applied lazily during later operations.

        ``requirements_in_caller`` pairs each callee requirement with its
        position from the caller's perspective so the operation graph can record
        the caller dependencies that satisfy it.

        """
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
        self._body_operation_number += 1
        action_chain_key = action_chain.canonical_chained_name_tuple
        # We have to record the Action Execution when particles are still
        # in their requirements positions, because applying pending guarantees
        # will trigger the guarantees of the callee in the operation graph.
        acting_on_position_key = acting_on_position.canonical_chained_name_tuple
        execution = self._operation_graph.record_action_execution(
            action_chain,
            acting_on_position,
            requirements_in_caller,
            is_destructor=is_destructor,
            acting_on_preceding_child_operations=self._preceding_child_operations(
                acting_on_position_key
            ),
            required_preceding_child_operations=(
                self._preceding_child_operations(
                    requirement.caller_position.canonical_chained_name_tuple
                )
                for requirement in requirements_in_caller
            ),
        )
        for newly_occupied_children in newly_occupied_children_by_destruction_contract:
            self._operation_graph.record_contributed_destruction_fragment(
                execution,
                newly_occupied_children,
            )
        callee_guarantees = _PendingGuarantee(
            action_chain_key,
            guarantees,
            self._body_operation_number,
            execution,
            operation_graph_action_chain=action_chain_key,
        )
        self._nested_guarantees.add(
            action_chain_key,
            action_contract.NestedGuarantees(
                guarantees=guarantees,
                execution=execution,
            ),
        )
        self._apply_pending_guarantee(callee_guarantees)
        return execution

    def nested_guarantees(
        self,
    ) -> action_contract.NestedGuaranteesByActionChain:
        """Return the guarantees of actions this action triggered."""
        return self._nested_guarantees.items()

    def _apply_pending_guarantee(self, pending_guarantee: _PendingGuarantee):
        """Apply a callee's guarantees and add one child name to nested guarantee prefixes."""
        operation_graph_positions = self._update_store_from_callee_direct_guarantees(
            pending_guarantee
        )
        guarantee_nodes = self._operation_graph.record_guarantees(
            pending_guarantee.execution,
            pending_guarantee.transitive_executions,
            operation_graph_positions,
            guarantee_action_chain=pending_guarantee.action_chain,
            operation_graph_action_chain=(
                pending_guarantee.operation_graph_action_chain
            ),
        )
        for key, node in guarantee_nodes.items():
            state = self._store.state.get(key)
            if state is not None:
                state.operation_node = node
        for (
            child_action_chain_in_guarantee,
            child,
        ) in pending_guarantee.guarantees.nested:
            child_action_chain_in_caller = pending_guarantee.key_for(
                child_action_chain_in_guarantee
            )
            # child.execution.action_chain is the full chain the action had from
            # the perspective of its caller, when it was triggered.
            #
            # child_action_chain_in_guarantee is where that action was, from the
            # perspective of its caller, when that caller finally generated its
            # guarantees.
            #
            # However, nested guarantees can _also_ be moved without their
            # more-deeply nested guarantees being applied in the callee. So we
            # need some way to see that this happened so we can correct it when
            # when we want to actually apply those more-deeply-nested guarantees in
            # the current action.
            #
            # Thus, pending_guarantee.action_chain is the callee's current chained
            # name, where its guarantees apply, from this action's perspective.
            #
            # pending_guarantee.operation_graph_action_chain is the chained name of
            # the action whose operation graph contains the last Particle Operation
            # affecting the positions guaranteed by pending_guarantee.
            #
            # When those two differ, we are in the "callee moved the action's parent
            # without applying all the child guarantees of that action" situation.
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
            # pending_guarantee.operation_graph_action_chain =
            #     position<gateway>::action</relocate_particle>
            # pending_guarantee.action_chain =
            #     position<gateway>::action</relocate_particle>
            # child_action_chain_in_guarantee =
            #     position<stationary>::action</inspect_particle>
            # child.execution.action_chain =
            #     position<stationary>::action</inspect_particle>
            # child_action_chain_in_caller =
            #     position<gateway>::action</relocate_particle>::position<stationary>::action</inspect_particle>
            # guarantee_moved = False
            #
            # This action applies the guarantees of:
            # position<gateway>::action</relocate_particle>
            # which adds the pending guarantees of:
            # position<gateway>::action</relocate_particle>::position<destination>::action</process_particle>.
            #
            # pending_guarantee.operation_graph_action_chain =
            #     position<gateway>::action</relocate_particle>
            # pending_guarantee.action_chain =
            #     position<gateway>::action</relocate_particle>
            # child_action_chain_in_guarantee =
            #     position<destination>::action</process_particle>
            # child.execution.action_chain =
            #     position<source>::action</process_particle>
            # child_action_chain_in_caller =
            #     position<gateway>::action</relocate_particle>::position<destination>::action</process_particle>
            # guarantee_moved = True
            #
            # This action applies the pending guarantees of:
            # position<gateway>::action</relocate_particle>::position<destination>::action</process_particle>
            # which adds the pending guarantees of:
            # position<gateway>::action</relocate_particle>::position<destination>::action</process_particle>::position<marker_parent>::action</fill_marker>.
            #
            # pending_guarantee.operation_graph_action_chain =
            #     position<gateway>::action</relocate_particle>
            # pending_guarantee.action_chain =
            #     position<gateway>::action</relocate_particle>::position<destination>::action</process_particle>
            # child_action_chain_in_guarantee =
            #     position<marker_parent>::action</fill_marker>
            # child.execution.action_chain =
            #     position<marker_parent>::action</fill_marker>
            # child_action_chain_in_caller =
            #     position<gateway>::action</relocate_particle>::position<destination>::action</process_particle>::position<marker_parent>::action</fill_marker>
            # guarantee_moved = True
            guarantee_moved = (
                pending_guarantee.operation_graph_action_chain
                != pending_guarantee.action_chain
                or child_action_chain_in_guarantee != child.execution.action_chain
            )
            if guarantee_moved:
                transitive_executions = pending_guarantee.transitive_executions
                operation_graph_action_chain = (
                    pending_guarantee.operation_graph_action_chain
                )
            else:
                transitive_executions = (
                    *pending_guarantee.transitive_executions,
                    child.execution,
                )
                operation_graph_action_chain = child_action_chain_in_caller
            child_nested_guarantee = _PendingGuarantee(
                child_action_chain_in_caller,
                child.guarantees,
                pending_guarantee.body_operation_number,
                pending_guarantee.execution,
                transitive_executions=transitive_executions,
                operation_graph_action_chain=operation_graph_action_chain,
                call_chain_depth=pending_guarantee.call_chain_depth + 1,
            )
            self._pending.add(child_nested_guarantee)

    def _apply_pending_guarantees_up_to(self, key: tuple[str, ...]):
        """Apply any nested guarantee on the path from root to ``key``."""
        for pending_guarantee in self._pending.drain_shortest_first(key):
            self._apply_pending_guarantee(pending_guarantee)

    def _apply_pending_guarantees_up_to_all(self, keys: Iterable[tuple[str, ...]]):
        """Apply nested guarantees on the paths to any of ``keys``."""
        for pending_guarantee in self._pending.drain_shortest_first_for(keys):
            self._apply_pending_guarantee(pending_guarantee)

    def _fully_resolve_pending_guarantees(self, key: tuple[str, ...]):
        """Apply guarantees at ``key`` and prefixes for which it is a parent name."""
        self._apply_pending_guarantees_up_to(key)
        for pending_guarantee in self._pending.drain_at_or_below(key):
            self._apply_pending_guarantee(pending_guarantee)

    def _update_store_from_callee_direct_guarantees(
        self,
        pending_guarantee: _PendingGuarantee,
    ) -> list[tuple[tuple[str, ...], tuple[tuple[str, ...], ...]]]:
        """Apply a callee's own guarantees; return what it wrote, in order."""
        guarantees = pending_guarantee.guarantees.own
        operation_graph_positions: list[
            tuple[tuple[str, ...], tuple[tuple[str, ...], ...]]
        ] = []

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
        saved_nested_guarantees: dict[
            tuple[str, ...],
            trie.StrictReparentingTrie[list[action_contract.NestedGuarantees]],
        ] = {}

        # Every write below shares this callee's operation number and depth, and a
        # _WriteRecord is immutable, so the loop reuses these two instead of
        # building an identical record for every guaranteed position. This loop
        # applies every guarantee of every action triggered anywhere in the
        # program, so those constructions dominated guarantee propagation.
        callee_derived_write = _WriteRecord(
            pending_guarantee.body_operation_number,
            pending_guarantee.call_chain_depth,
            is_from_callee=True,
            ever_set_by_callee=True,
        )
        caller_identity_write = _WriteRecord(
            pending_guarantee.body_operation_number,
            pending_guarantee.call_chain_depth,
            is_from_callee=False,
            ever_set_by_callee=True,
        )

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

            # Almost every guarantee names a child of the callee's own action
            # intermediate, which no earlier operation has created, so creating
            # it is the common path here rather than the exceptional one. A key
            # comes back only when the caller of this action never filled a
            # position that the guaranteed position is a child name of.
            missing_key = self._store.try_add_action_parent(key)
            if missing_key is not None:
                self._store.error[missing_key] = _ErrorState(
                    caused_by=guarantee.caused_by
                )
                continue

            # OccupiedByExisting depends on caller-passed particle identity, so
            # it must be resolved here (a distant caller can't reconstruct it)
            # and emitted as this block's own guarantee. Other guarantee types
            # are re-derivable in any caller, so they stay behind the nested guarantee.
            self._store.record_callee_write(
                key,
                caller_identity_write
                if isinstance(guarantee, action_contract.OccupiedByExistingGuarantee)
                else callee_derived_write,
            )

            operation_graph_positions.append((key, guarantee.operation_positions))

            overwrites_subtree = key in origin_keys or (
                key in self._store.state
                and not isinstance(guarantee, action_contract.UnchangedGuarantee)
            )
            # We are about to overwrite this key's subtree, and a later guarantee still
            # needs to read a particle from an origin position that may have it as
            # a parent name.
            if origin_keys and overwrites_subtree:
                self._save_origins_at_or_below(
                    key,
                    origin_keys,
                    saved_state,
                    saved_error,
                    saved_nested_guarantees,
                )

            # We are overwriting this key's subtree, and this key is not itself an origin
            # position that a later guarantee reads from, so its old contents can just be
            # dropped.
            if key not in origin_keys and overwrites_subtree:
                # Subtree cleanup: If an action empties position<item> (EmptyGuarantee)
                # or creates in position<item> (OccupiedByNewGuarantee), any children
                # the caller had at child names of position<item> must disappear. We
                # achieve this by deleting each key's entire subtree before applying
                # its guarantee.
                # An UnchangedGuarantee leaves the caller's state as it found it, so
                # it keeps whatever subtree is there.
                del self._store.state[key]
                if key in self._store.error:
                    del self._store.error[key]
                self._nested_guarantees.discard_for_destroyed_particle(key)

            match guarantee:
                case action_contract.OccupiedByExistingGuarantee():
                    self._apply_existing_guarantee(
                        key,
                        pending_guarantee,
                        guarantee,
                        saved_state,
                        saved_error,
                        saved_nested_guarantees,
                    )
                case action_contract.EmptyGuarantee():
                    self._store.state[key] = _NodeState(emptied_by=guarantee.caused_by)
                case action_contract.OccupiedByNewGuarantee():
                    new_info = ParticleInfo(
                        last_position=guarantee.caused_by,
                        qualities=guarantee.qualities,
                        origin_position=guarantee.origin_position,
                    )
                    self._store.state[key] = _NodeState(particle_info=new_info)
                case action_contract.ErrorGuarantee():
                    self._store.error[key] = _ErrorState(caused_by=guarantee.caused_by)
                case action_contract.UnchangedGuarantee():
                    # The position is unchanged from its entry state, which the
                    # caller's store already reflects (the cleanup above kept any
                    # occupant). The write record above still supersedes a
                    # conflicting nested guarantee.
                    pass
                case _:
                    raise TypeError(f"Unexpected guarantee type: {type(guarantee)}")

        return operation_graph_positions

    def _save_origins_at_or_below(
        self,
        key: tuple[str, ...],
        origin_keys: set[tuple[str, ...]],
        saved_state: dict[tuple[str, ...], trie.StrictReparentingTrie[_NodeState]],
        saved_error: dict[tuple[str, ...], trie.StrictReparentingTrie[_ErrorState]],
        saved_nested_guarantees: dict[
            tuple[str, ...],
            trie.StrictReparentingTrie[list[action_contract.NestedGuarantees]],
        ],
    ):
        """Detach every origin position at or below ``key`` before ``key``'s subtree is overwritten."""
        key_len = len(key)
        at_or_below: list[tuple[str, ...]] = []
        for origin_key in origin_keys:
            if len(origin_key) >= key_len and origin_key[:key_len] == key:
                at_or_below.append(origin_key)
        saved_state.update(self._store.state.pop_subtrees(at_or_below))
        saved_error.update(self._store.error.pop_subtrees(at_or_below))
        saved_nested_guarantees.update(
            self._nested_guarantees.pop_subtrees(at_or_below)
        )

    def _apply_existing_guarantee(
        self,
        dest_key: tuple[str, ...],
        pending_guarantee: _PendingGuarantee,
        guarantee: action_contract.OccupiedByExistingGuarantee,
        saved_state: dict[tuple[str, ...], trie.StrictReparentingTrie[_NodeState]],
        saved_error: dict[tuple[str, ...], trie.StrictReparentingTrie[_ErrorState]],
        saved_nested_guarantees: dict[
            tuple[str, ...],
            trie.StrictReparentingTrie[list[action_contract.NestedGuarantees]],
        ],
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
            # guarantee on the same position that a particle was passed in on.
            self._store.error[dest_key] = _ErrorState(caused_by=guarantee.caused_by)
            return

        # The caller never filled the input interface position. The callee moves the particle to
        # another position. Thus, the origin_state _exists_ but the position got EmptyGuarantee
        # instead of being filled by something (and there's nothing in saved_state).
        if origin_state.particle_info is None:
            self._store.error[dest_key] = _ErrorState(caused_by=guarantee.caused_by)
            return

        moved_info = origin_state.particle_info
        moved_info.last_position = guarantee.caused_by
        if saved_tree is not None:
            self._store.state.restore_subtree(
                dest_key, saved_tree, _NodeState(particle_info=moved_info)
            )
            saved_nested_subtree = saved_nested_guarantees.pop(origin_key, None)
            if saved_nested_subtree is not None:
                self._nested_guarantees.restore_moved_particle(
                    origin_key, dest_key, saved_nested_subtree
                )
        else:
            self._store.state.move_subtree(origin_key, dest_key)
            self._store.state[dest_key] = _NodeState(particle_info=moved_info)
            self._nested_guarantees.move(origin_key, dest_key)

        saved_unk = saved_error.pop(origin_key, None)
        # Guarantees reset the error state of particles they touch directly.
        # If we guarantee a particle in a position, then we know that it has a
        # particle. However, its _children_ might still be in some error state.
        # Exception: if the origin had pre-action error state (saved before the
        # guarantee loop began), the destination inherits that caused_by — the
        # guarantee fills it with whatever was at origin, including the uncertainty.
        if saved_unk is not None:
            origin_error = saved_unk[origin_tuple[-1:]]
            self._store.error.restore_subtree(
                dest_key, saved_unk, _ErrorState(caused_by=origin_error.caused_by)
            )
        elif origin_key in self._store.error:
            self._store.error.move_subtree(origin_key, dest_key)
            self._store.error[dest_key] = _ErrorState()
