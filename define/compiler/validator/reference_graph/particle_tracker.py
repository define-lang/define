"""Tracks particle occupancy for positions within an action block."""

from __future__ import annotations

import itertools
import typing
from dataclasses import dataclass

from define.compiler import ast
from define.compiler.data_structures import trie
from define.compiler.validator.reference_graph import (
    action_contract,
    child_state,
    operation_graph,
    operation_graph_model,
    particle_info,
    position_occupancy,
    quality_assignment,
)
from define.compiler.validator.reference_graph.dead_code import dead_interface_tracker

if typing.TYPE_CHECKING:
    from collections.abc import (
        Collection,
        Iterable,
        Iterator,
        Sequence,
    )


@dataclass(frozen=True, slots=True)
class ParticleDestruction:
    """A destruction target and its occupied transitive child Positions."""

    position: ast.PositionReference
    facts: list[operation_graph_model.DestructionFact]

    def positions(self) -> Iterator[ast.PositionReference]:
        """Yield the target Position followed by its transitive child Positions."""
        for fact in self.facts:
            yield fact.destroyed_position_in_destroyer


@dataclass(frozen=True, slots=True)
class OccupancyInfo:
    """A position's error state and occupant, resolved together in one lookup."""

    # When an ancestor is in an error condition we ignore the position entirely,
    # so the occupant is meaningless and left None.
    has_error: bool
    occupant: particle_info.ParticleInfo | None


@dataclass(frozen=True, slots=True)
class ResolvedRequirementPosition:
    """A local requirement position and the contracted position it resolves to."""

    local_position: ast.PositionReference
    contracted_position: ast.PositionReference
    required_state: position_occupancy.PositionOccupancyState


@dataclass(frozen=True, slots=True)
class PropagatedRequirement:
    """A callee requirement that must be propagated into the current contract."""

    requirement_in_caller: action_contract.PositionRequirementInCaller
    contracted_position: ast.PositionReference


@dataclass
class _NodeState:
    """Mutable state for a position in the state trie."""

    particle_info: particle_info.ParticleInfo | None = None
    emptied_by: ast.PositionReference | None = None
    # Keeping the exact-position operation with the state makes it follow moves,
    # so child-operation snapshots only need to be built when an operation uses one.
    # TODO: Should particle tracking and operation-graph construction consume
    # shared positional and execution information, rather than graph construction
    # depending on the occupancy tracker's guarantee-application process?
    operation_node: operation_graph_model.ConcreteOperationNode | None = None


def _node_is_occupied(state: _NodeState) -> bool:
    return state.particle_info is not None


def _operation_node(
    state: _NodeState,
) -> operation_graph_model.ConcreteOperationNode | None:
    return state.operation_node


@dataclass
class _ErrorState:
    """Wrapper for error-state trie values.

    LenientReparentingTrie can't use None as a value, so we wrap
    the caused_by reference in a dataclass.
    """

    caused_by: ast.PositionReference | None = None


def _child_occupancy(node: _NodeState) -> position_occupancy.ChildOccupancy | None:
    if node.particle_info is not None:
        return position_occupancy.ChildOccupancy(
            position_occupancy.PositionOccupancyState.OCCUPIED,
            filled_at=node.particle_info.last_position.location,
        )
    if node.emptied_by is not None:
        return position_occupancy.EMPTY_OCCUPANCY
    return None


def _child_error_occupancy(
    error: _ErrorState,
) -> position_occupancy.ChildOccupancy | None:
    if error.caused_by is not None:
        return position_occupancy.ERROR_OCCUPANCY
    return None


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
    # Results left in a callee's contract need not be published again by this action.
    include_in_own_guarantees: bool
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
    """A callee's guarantees and the execution path where they apply."""

    # The triggered action's chain.
    action_chain: tuple[str, ...]
    contract: action_contract.ActionContract
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
    queried position (shortest prefix first); ``drain_at_or_below_for`` yields the
    ones for which a queried position is a parent name. Both remove what they
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
            previous_drained_prefix_count = length

    def drain_at_or_below_for(
        self, keys: Sequence[tuple[str, ...]]
    ) -> Iterator[_PendingGuarantee]:
        """Yield guarantees at or below any of the equally long keys."""
        if not self._by_prefix or not keys:
            return
        # Automatic Destruction can request thousands of locally defined
        # Positions. They all have one name; other callers request just one key.
        # Matching against a set avoids scanning the pending prefixes separately
        # for every Position being destroyed.
        length = len(keys[0])
        requested = set(keys)
        # The reason for this outer while loop is that our caller adds more prefixes
        # as they are running.
        while self._by_prefix:
            matching = [
                prefix for prefix in self._by_prefix if prefix[:length] in requested
            ]
            if not matching:
                return
            for prefix in matching:
                yield from self._by_prefix.pop(prefix)


@dataclass(frozen=True, slots=True)
class _ExecutedCallee:
    """An Action Execution and its callee's contract."""

    execution: operation_graph_model.ActionExecution
    contract: action_contract.ActionContract


@dataclass(frozen=True, slots=True)
class _GuaranteeApplicationState:
    """Shared particle state for applying one callee's guarantees."""

    origin_keys: set[ast.ChainedNameTuple]
    saved_state: dict[ast.ChainedNameTuple, trie.StrictReparentingTrie[_NodeState]]
    saved_error: dict[ast.ChainedNameTuple, trie.StrictReparentingTrie[_ErrorState]]
    saved_nested_guarantees: dict[
        ast.ChainedNameTuple, trie.StrictReparentingTrie[list[_ExecutedCallee]]
    ]

    @classmethod
    def for_callee(cls, pending_guarantee: _PendingGuarantee) -> typing.Self:
        """Prepare shared state for applying the callee's guarantees."""
        # Make a list of only the origin_positions for OccupiedByExistingGuarantee.
        # We need this list later to know what to "save" before we apply guarantees.
        origin_keys: set[tuple[str, ...]] = set()
        for guarantee in pending_guarantee.contract.guarantees.values():
            if isinstance(guarantee, action_contract.OccupiedByExistingGuarantee):
                origin_tuple = guarantee.origin_position.canonical_chained_name_tuple
                origin_keys.add(pending_guarantee.key_for(origin_tuple))

        # Saved subtrees for swap safety. Keyed by the origin's full key.
        saved_state: dict[tuple[str, ...], trie.StrictReparentingTrie[_NodeState]] = {}
        saved_error: dict[tuple[str, ...], trie.StrictReparentingTrie[_ErrorState]] = {}
        saved_nested_guarantees: dict[
            tuple[str, ...],
            trie.StrictReparentingTrie[list[_ExecutedCallee]],
        ] = {}

        return cls(
            origin_keys=origin_keys,
            saved_state=saved_state,
            saved_error=saved_error,
            saved_nested_guarantees=saved_nested_guarantees,
        )

    def save_origins_at_or_below(
        self,
        key: ast.ChainedNameTuple,
        store: _ParticleStateStore,
        nested_guarantees: _CurrentActionNestedGuarantees,
    ):
        """Detach every origin position at or below ``key`` before ``key``'s subtree is overwritten."""
        key_len = len(key)
        at_or_below: list[tuple[str, ...]] = []
        for origin_key in self.origin_keys:
            if len(origin_key) >= key_len and origin_key[:key_len] == key:
                at_or_below.append(origin_key)
        self.saved_state.update(store.state.pop_subtrees(at_or_below))
        self.saved_error.update(store.error.pop_subtrees(at_or_below))
        self.saved_nested_guarantees.update(nested_guarantees.pop_subtrees(at_or_below))


class _CurrentActionNestedGuarantees:
    """Nested guarantees keyed by the action chain where they currently apply.

    Stores the nested guarantees that will directly become part of this action's
    contract.
    """

    def __init__(self):
        self._by_action_chain: trie.LenientReparentingTrie[list[_ExecutedCallee]] = (
            trie.LenientReparentingTrie(default_factory=list)
        )

    def add(
        self,
        action_chain: tuple[str, ...],
        execution: operation_graph_model.ActionExecution,
        contract: action_contract.ActionContract,
    ):
        at_action_chain = self._by_action_chain.get(action_chain)
        if at_action_chain is None:
            at_action_chain = []
            self._by_action_chain[action_chain] = at_action_chain
        at_action_chain.append(_ExecutedCallee(execution, contract))

    def move(self, source: tuple[str, ...], target: tuple[str, ...]):
        """Move nested guarantees beneath a moved particle."""
        if source not in self._by_action_chain:
            return
        self._by_action_chain.move_subtree(source, target)

    def discard_for_destroyed_particle(self, position: tuple[str, ...]):
        """Discard nested guarantees belonging to a destroyed particle."""
        if position in self._by_action_chain:
            self._by_action_chain.delete_subtree(position)

    def pop_subtrees(
        self, positions: Iterable[tuple[str, ...]]
    ) -> dict[
        tuple[str, ...],
        trie.StrictReparentingTrie[list[_ExecutedCallee]],
    ]:
        """Detach nested guarantees belonging to particles that may move."""
        return self._by_action_chain.pop_subtrees(positions)

    def restore_moved_particle(
        self,
        source: tuple[str, ...],
        target: tuple[str, ...],
        saved_subtree: trie.StrictReparentingTrie[list[_ExecutedCallee]],
    ):
        """Restore a saved particle's nested guarantees at its destination."""
        self._by_action_chain.restore_subtree(
            target, saved_subtree, saved_subtree[source[-1:]]
        )

    def items(
        self,
        executions: Sequence[operation_graph_model.ActionExecution],
    ) -> list[action_contract.CalleeContract]:
        """Return nested guarantees in triggering order."""
        by_execution: dict[
            operation_graph_model.ActionExecution,
            action_contract.CalleeContract,
        ] = {}
        # The trie alone tracks current action chains during Moves, so moving
        # one particle does not rewrite every repeated execution of its actions.
        for action_chain, guarantees in self._by_action_chain.items():
            for nested_guarantees in guarantees:
                by_execution[nested_guarantees.execution] = (
                    action_contract.CalleeContract(
                        action_chain,
                        nested_guarantees.execution,
                        nested_guarantees.contract,
                    )
                )
        return [
            by_execution[execution]
            for execution in executions
            if execution in by_execution
        ]

    def action_chains_with_most_recent_trigger(
        self,
    ) -> Iterator[tuple[ast.ChainedNameTuple, ast.GlobalTypedNameReference]]:
        """Yield each triggered action chain and its most recent direct trigger."""
        for action_chain, nested_guarantees in self._by_action_chain.items():
            if not nested_guarantees:
                continue
            yield action_chain, nested_guarantees[-1].execution.callee_action_name


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
    directly. (This is necessary to generate ```action_contract.ActionContract``` for
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

    def occupant(self, key: tuple[str, ...]) -> particle_info.ParticleInfo:
        """Return the particle at this position, raising KeyError if it is empty."""
        state = self._state[key]
        if state.particle_info is None:
            raise KeyError(key)
        return state.particle_info

    def occupant_or_none(
        self, key: tuple[str, ...]
    ) -> particle_info.ParticleInfo | None:
        """Return the particle at this position, or None if it is empty."""
        state = self._state.get(key)
        return state.particle_info if state is not None else None

    def snapshot_child_state(self, key: tuple[str, ...]) -> child_state.ChildState:
        """Capture known descendant occupancy, with keys relative to key."""
        result = dict(self._state.selected_subtree_items(key, _child_occupancy))
        # An error entry wins over a stale state entry, so it is applied last.
        result.update(self._error.selected_subtree_items(key, _child_error_occupancy))
        return child_state.FlatChildState(result)

    def add_child_state(
        self,
        values: position_occupancy.ChildOccupancyMap,
        snapshot: child_state.ChildState,
        key: tuple[str, ...],
        position_in_child_state: tuple[str, ...],
        contract_positions: set[tuple[str, ...]],
    ):
        """Collect new caller knowledge up to other contract positions."""
        # Another contract can describe a child particle with an independent
        # origin after a Move. Its own caller knowledge must determine that
        # particle's Child State, not the old contents of this caller position.
        for state_position, node in self._state.pruned_subtree_items(
            key,
            key_prefix=position_in_child_state,
            excluded_keys=contract_positions,
        ):
            if snapshot.get(state_position) is not None:
                continue
            occupancy = _child_occupancy(node)
            if occupancy is not None:
                values[state_position] = occupancy
        # An error entry wins over a stale state entry, so it is applied last.
        for state_position, error in self._error.pruned_subtree_items(
            key,
            key_prefix=position_in_child_state,
            excluded_keys=contract_positions,
        ):
            if snapshot.get(state_position) is not None:
                continue
            if error.caused_by is not None:
                values[state_position] = position_occupancy.ERROR_OCCUPANCY

    def callees_with_occupied_interface_child_position(
        self, position: ast.ChainedNameTuple
    ) -> list[tuple[particle_info.ParticleInfo | None, str]]:
        """Return callees whose interface position has an occupied child position with an action in its chained name."""
        callees: list[tuple[particle_info.ParticleInfo | None, str]] = []
        previous_action_index: int | None = None
        for name_index, name in enumerate(position):
            if not name.startswith(_ACTION_KEY_PREFIX):
                continue
            if previous_action_index is not None:
                parent_particle = (
                    None
                    if previous_action_index == 0
                    else self.occupant(position[:previous_action_index])
                )
                callees.append((parent_particle, position[previous_action_index]))
            previous_action_index = name_index
        return callees

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

    def has_error_at(self, key: tuple[str, ...]) -> bool:
        """Return whether this exact position has error occupancy state."""
        state = self._error.get(key)
        return state is not None and state.caused_by is not None

    def nearest_occupied_ancestors(
        self, keys: Sequence[tuple[str, ...]]
    ) -> dict[
        tuple[str, ...], tuple[tuple[str, ...], particle_info.ParticleInfo] | None
    ]:
        """Return the nearest occupied ancestor for each distinct key."""
        ancestor_keys = self._state.find_longest_prefixes_where(keys, _node_is_occupied)
        results: dict[
            tuple[str, ...],
            tuple[tuple[str, ...], particle_info.ParticleInfo] | None,
        ] = {}
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
                include_callee_derived or self._include_in_own_guarantees(key)
            ):
                keys.add(key)
        for key, error_state in self._error.items():
            if error_state.caused_by is not None and (
                include_callee_derived or self._include_in_own_guarantees(key)
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

    def _include_in_own_guarantees(self, key: tuple[str, ...]) -> bool:
        """Whether to include this position when collecting this action's own Guarantees."""
        record = self._write_record.get(key)
        return record is None or record.include_in_own_guarantees

    def ever_set_by_callee(self, key: tuple[str, ...]) -> bool:
        """Return whether a callee's contract ever set this position."""
        record = self._write_record.get(key)
        return record is not None and record.ever_set_by_callee

    def record_body_write(self, key: tuple[str, ...], body_operation_number: int):
        """Record that this Action Statement Block's own body made this change to ``key`` at ``body_operation_number``.

        A later body operation overrides earlier callee Guarantees, even if it
        leaves the position in its initial state.
        """
        existing = self._write_record.get(key)
        self._write_record[key] = _WriteRecord(
            body_operation_number,
            _BODY_DEPTH,
            include_in_own_guarantees=True,
            ever_set_by_callee=existing is not None and existing.ever_set_by_callee,
        )

    def record_callee_write(self, key: tuple[str, ...], record: _WriteRecord):
        """Record that a callee's contract authored ``key``."""
        self._write_record[key] = record

    def record_operation_write(
        self, key: ast.ChainedNameTuple, pending_guarantee: _PendingGuarantee
    ):
        """Update operation ordering without changing Guarantee publication or callee history."""
        existing = self._write_record.get(key)
        self._write_record[key] = _WriteRecord(
            pending_guarantee.body_operation_number,
            pending_guarantee.call_chain_depth,
            include_in_own_guarantees=(
                existing is None or existing.include_in_own_guarantees
            ),
            ever_set_by_callee=existing is not None and existing.ever_set_by_callee,
        )

    def try_add_action_parent(self, key: tuple[str, ...]) -> tuple[str, ...] | None:
        """Track ``key``'s action name when that is the only absent parent name.

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
            # where the compiler may add a tracker entry for an action name. Any
            # other absent parent name is a position the caller never filled.
            if parent_key[-1].startswith(_ACTION_KEY_PREFIX):
                # Repeated _NodeState construction for action-name trie
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
        self._interface_arrival_tracker: dead_interface_tracker.InterfaceArrivalTracker = dead_interface_tracker.InterfaceArrivalTracker()
        self._interface_child_tracker: dead_interface_tracker.OccupiedInterfaceChildPositionTracker = dead_interface_tracker.OccupiedInterfaceChildPositionTracker()
        self._pending: _PendingNestedGuarantees = _PendingNestedGuarantees()
        self._nested_guarantees: _CurrentActionNestedGuarantees = (
            _CurrentActionNestedGuarantees()
        )
        self._body_operation_number: int = 0
        self._operation_graph_builder: operation_graph.OperationGraphBuilder = (
            operation_graph.OperationGraphBuilder(action)
        )

    def _register_occupied_interface_child_position(
        self,
        position: ast.ChainedNameTuple,
        particle: particle_info.ParticleInfo,
        location: ast.SourceLocation,
    ):
        """Register relevant interface occupancy for a new particle."""
        callees = self._store.callees_with_occupied_interface_child_position(position)
        if not callees:
            return
        self._interface_child_tracker.register(
            particle,
            position,
            location,
            callees,
        )

    def _replace_occupied_interface_child_position(
        self,
        position: ast.ChainedNameTuple,
        particle: particle_info.ParticleInfo,
        location: ast.SourceLocation,
    ):
        """Replace relevant interface occupancy for an existing particle."""
        self._interface_child_tracker.replace(
            particle,
            position,
            location,
            self._store.callees_with_occupied_interface_child_position(position),
        )

    def _register_explicit_action_interface_arrival(
        self,
        position: ast.PositionReference,
        particle: particle_info.ParticleInfo,
    ):
        """Register a body Create or Move whose target names an action interface."""
        action_chain = position.get_chain_to_last_action()
        if action_chain is None:
            return
        parent_position = action_chain.parent_position()
        parent_particle = (
            self.get_occupant(parent_position) if parent_position is not None else None
        )
        self._interface_arrival_tracker.register(
            action_chain.get_last_action().full_typed_name,
            position,
            parent_particle,
            particle,
        )

    def _mark_removed_occupant_destroyed(self, state: _NodeState):
        """Mark the particle at a removed position as destroyed."""
        if state.particle_info is not None:
            self._interface_arrival_tracker.mark_particle_departed(state.particle_info)
            self._interface_child_tracker.mark_particle_destroyed(state.particle_info)

    def _delete_particle_state_subtree(self, key: ast.ChainedNameTuple):
        """Delete particle state while preserving interface-rule history."""
        self._store.state.delete_subtree(
            key,
            removed_value_callback=self._mark_removed_occupant_destroyed,
        )

    @property
    def operation_graph_builder(self) -> operation_graph.OperationGraphBuilder:
        """The builder for this action's DLP 44 dependency graph."""
        return self._operation_graph_builder

    def _ensure_action_parent(self, key: tuple[str, ...]):
        """Ensure the action name preceding the position has tracker state."""
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

    def unconsumed_action_interfaces(
        self,
    ) -> Iterator[tuple[ast.GlobalTypedNameReference, ast.ChainedNameTuple]]:
        """Yield occupied interfaces of callees directly triggered by this action."""
        for (
            action_chain,
            action,
        ) in self._nested_guarantees.action_chains_with_most_recent_trigger():
            if self._store.has_error_in_chain(action_chain):
                continue
            for position, state in self._store.state.direct_child_items(action_chain):
                if state.particle_info is None or self._store.has_error_at(position):
                    continue
                yield action, position

    def dead_action_interface_arrivals(self) -> Iterator[ast.PositionReference]:
        """Yield explicit interface arrivals not satisfied by a callee trigger."""
        return self._interface_arrival_tracker.dead_arrivals()

    def _new_occupied_interface_child_position_violations(
        self,
        action: ast.GlobalTypedNameReference,
        parent_particle: particle_info.ParticleInfo | None,
    ) -> list[tuple[ast.ChainedNameTuple, ast.SourceLocation]]:
        """Return newly reportable occupied interface child positions for one trigger."""
        violations: list[tuple[ast.ChainedNameTuple, ast.SourceLocation]] = []
        occupied_positions = (
            self._interface_child_tracker.pop_occupied_interface_child_positions(
                action.full_typed_name, parent_particle
            )
        )
        for position, location in occupied_positions:
            if self._store.has_error_in_chain(position):
                continue
            violations.append((position, location))
        return violations

    def is_occupied(self, in_position: ast.PositionReference) -> bool:
        """Return whether a particle exists at this position."""
        key = in_position.canonical_chained_name_tuple
        self._apply_pending_guarantees_up_to(key)
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
        self._apply_pending_guarantees_up_to(parent_key)
        deepest_occupied_parent = self._store.state.find_longest_prefix_where(
            parent_key, _node_is_occupied
        )
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

    def has_been_touched(self, in_position: ast.PositionReference) -> bool:
        """Return whether a guarantee or particle statement has decided this position's state."""
        key = in_position.canonical_chained_name_tuple
        self._apply_pending_guarantees_up_to(key)
        return self._store.has_been_touched(key)

    def infer_direct_requirements(
        self,
        position: ast.PositionReference,
        required_state: position_occupancy.PositionOccupancyState,
        interface_position_names: Collection[str],
    ) -> list[ResolvedRequirementPosition]:
        """Infer direct requirements and record their RequirementNodes when needed."""
        self._apply_pending_guarantees_up_to(position.canonical_chained_name_tuple)
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

    def _record_requirement_in_operation_graph(
        self,
        contracted_position: ast.PositionReference,
        required_state: position_occupancy.PositionOccupancyState,
        nearest_particle: tuple[tuple[str, ...], particle_info.ParticleInfo] | None,
    ):
        if nearest_particle is not None:
            particle = nearest_particle[1]
            # If the parent was moved, then its move operation is the only thing
            # that needs to go into the graph. That move operation already generated
            # a RequirementNode, and _that_ is what will depend on the caller operation.
            # Any later child operation will depend only on that move operation.
            if particle.last_position != particle.origin_position:
                return
        self._operation_graph_builder.record_requirement(
            contracted_position, required_state
        )

    def get_occupant(
        self, in_position: ast.PositionReference
    ) -> particle_info.ParticleInfo:
        """Return the info for the particle at this position."""
        key = in_position.canonical_chained_name_tuple
        self._apply_pending_guarantees_up_to(key)
        return self._store.occupant(key)

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
        self._fully_resolve_pending_guarantees(*keys)
        return [self._store.snapshot_child_state(key) for key in keys]

    def add_child_state(
        self,
        values: position_occupancy.ChildOccupancyMap,
        snapshot: child_state.ChildState,
        for_position: ast.PositionReference,
        position_in_child_state: tuple[str, ...],
        contract_positions: set[tuple[str, ...]],
    ):
        """Collect new caller knowledge up to other contract positions."""
        key = for_position.canonical_chained_name_tuple
        self._fully_resolve_pending_guarantees(key)
        self._store.add_child_state(
            values, snapshot, key, position_in_child_state, contract_positions
        )

    def _preceding_child_operations(
        self, key: tuple[str, ...]
    ) -> Iterator[tuple[tuple[str, ...], operation_graph_model.ConcreteOperationNode]]:
        # Empty Rule Collection includes operations on positions that ended empty,
        # even when their Guarantees did not need to change the tracked occupancy.
        return self._store.state.selected_subtree_items(key, _operation_node)

    def _preceding_child_operations_for_contributed_destructor_requirement(
        self,
        requirement: operation_graph_model.VerifiedDestructionContractRequirement,
    ) -> operation_graph_model.PrecedingChildOperations:
        """Return child operations needed by one contributed Destructor requirement."""
        if (
            requirement.callee_destroy_position_relative_to_destroyed_particle
            is not None
        ):
            # The Callee Destroy supplies the dependency directly, so child
            # operations at the destroyed position cannot add a dependency.
            return ()
        return self._preceding_child_operations(
            requirement.caller_position.canonical_chained_name_tuple
        )

    def _preceding_child_operations_for_contributed_destructors(
        self,
        destructors: Sequence[
            operation_graph_model.VerifiedDestructionContractDestructor
        ],
    ) -> Iterator[
        tuple[
            operation_graph_model.PrecedingChildOperations,
            list[operation_graph_model.PrecedingChildOperations],
        ]
    ]:
        for verified_destructor in destructors:
            required_preceding_child_operations: list[
                operation_graph_model.PrecedingChildOperations
            ] = []
            for requirement in verified_destructor.requirements:
                required_preceding_child_operations.append(
                    self._preceding_child_operations_for_contributed_destructor_requirement(
                        requirement
                    )
                )
            acting_on_preceding_child_operations = self._preceding_child_operations(
                verified_destructor.destruction_contract_position.position.canonical_chained_name_tuple
            )
            yield (
                acting_on_preceding_child_operations,
                required_preceding_child_operations,
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
            operation_node = self._operation_graph_builder.record_create(in_position)
        info = particle_info.ParticleInfo(
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
        self._register_occupied_interface_child_position(
            key, info, in_position.location
        )
        if from_caller is None:
            self._register_explicit_action_interface_arrival(in_position, info)

    def destroy_simultaneously(
        self,
        destructions: Sequence[ParticleDestruction],
    ):
        """Record and apply a simultaneous set of particle destructions.

        Each target includes all its occupied transitive children; targets must
        have disjoint state subtrees. Child order imposes no graph dependencies.
        All graph operations are recorded before deleting each target's state.
        """
        positions = (destruction.positions() for destruction in destructions)
        self._apply_pending_guarantees_up_to_all(
            position.canonical_chained_name_tuple
            for position in itertools.chain.from_iterable(positions)
        )
        # Capture these before the subtree is deleted so graph dependencies see
        # the child operations.
        graph_destructions: list[operation_graph.DestructionFactDestroyInput] = []
        target_operation_indices: list[int] = []
        for destruction in destructions:
            target_operation_indices.append(len(graph_destructions))
            for destruction_fact in destruction.facts:
                position = destruction_fact.destroyed_position_in_destroyer
                key = position.canonical_chained_name_tuple
                particle = self._store.occupant_or_none(key)
                # An invalid Destructor's ErrorGuarantee can remove this particle
                # or its parent's state after collection. Valid Destructors
                # preserve these particles; the source error is already reported.
                if particle is None:
                    continue
                graph_destructions.append(
                    operation_graph.DestructionFactDestroyInput(
                        destruction_fact=destruction_fact,
                        target=position,
                        preceding_child_operations=self._preceding_child_operations(
                            key
                        ),
                        propagate_to_caller=particle.from_caller,
                    )
                )
        operation_nodes = (
            self._operation_graph_builder.record_destruction_fact_destroys(
                graph_destructions
            )
        )
        for destruction, target_operation_index in zip(
            destructions, target_operation_indices, strict=True
        ):
            self._record_destroyed_state(
                destruction,
                operation_nodes[target_operation_index],
            )

    def _record_destroyed_state(
        self,
        destruction: ParticleDestruction,
        operation_node: operation_graph_model.DestroyNode,
    ):
        """Record state changes for a target and its transitive children."""
        # Pending Guarantees compare writes by Position, so children still
        # need write records even though their state is deleted with the parent.
        for fact in itertools.islice(destruction.facts, 1, None):
            child = fact.destroyed_position_in_destroyer
            self._record_body_write(child.canonical_chained_name_tuple)
        key = destruction.position.canonical_chained_name_tuple
        # Subtree deletion notifies the interface trackers for every removed
        # particle. Only the target's empty state survives the destruction.
        self._delete_particle_state_subtree(key)
        # Destroying puts all children back into a known state (they don't exist).
        if key in self._store.error:
            self._store.error.delete_subtree(key)
        self._nested_guarantees.discard_for_destroyed_particle(key)
        self._record_body_write(key)
        self._store.state[key] = _NodeState(
            emptied_by=destruction.position, operation_node=operation_node
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
        self._interface_arrival_tracker.mark_particle_departed(source_info)
        operation_node = self._operation_graph_builder.record_move(
            source,
            target,
            self._store.state.selected_subtree_items(from_key, _operation_node),
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
            self._delete_particle_state_subtree(to_key)

        # Empty Rule Collection treats this Move as the most recent Particle
        # Operation on every transitive child position of the moved particle.
        def record_move_on_position(
            moved_position: ast.ChainedNameTuple,
            moved_state: _NodeState,
        ):
            if (
                moved_state.particle_info is not None
                or moved_state.emptied_by is not None
            ):
                moved_state.operation_node = operation_node
            if moved_state.particle_info is not None:
                self._replace_occupied_interface_child_position(
                    moved_position,
                    moved_state.particle_info,
                    target.location,
                )

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
        self._register_explicit_action_interface_arrival(target, source_info)

    def generate_own_guarantees(
        self,
        interface_names: tuple[ast.TypedName, ...],
        implied_quality_names: tuple[ast.GlobalTypedNameReference, ...],
        requirements: dict[tuple[str, ...], action_contract.PositionRequirement],
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
            include_callee_derived=False,
        )

    def generate_destructor_guarantees(
        self,
        interface_names: tuple[ast.TypedName, ...],
        implied_quality_names: tuple[ast.GlobalTypedNameReference, ...],
        requirements: dict[tuple[str, ...], action_contract.PositionRequirement],
    ) -> dict[ast.ChainedNameTuple, action_contract.PositionGuarantee]:
        """Produce every guarantee a destructor makes on its contracted positions.

        Guarantees about implied positions from triggered actions are expanded
        into the destructor's state rather than deferred.
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
    ) -> dict[ast.ChainedNameTuple, action_contract.PositionGuarantee]:
        """Collect and sort the guarantees for every contracted key, excluding the ones _guarantee_for_key reports as no-ops."""
        include_names = {
            name.full_typed_name for name in (*interface_names, *implied_quality_names)
        }

        # generate_own_guarantees excludes keys that came only from our caleees.
        # generate_destructor_guarantees includes callee-derived keys.
        all_keys = self._store.keys_for_guarantees(
            include_callee_derived=include_callee_derived
        )

        guarantees: list[
            tuple[ast.ChainedNameTuple, action_contract.PositionGuarantee]
        ] = []
        for key in all_keys:
            # A callee's interface guarantees must be consumed in this Action
            # Statements Block, so they cannot become guarantees of this action.
            if any(name.startswith(_ACTION_KEY_PREFIX) for name in key):
                continue
            first_element = key[0]
            # Any position that starts with a global is contracted, even if it was updated
            # by an implied action and we can't see it directly.
            if first_element not in include_names and not ast.chain_starts_with_global(
                key
            ):
                continue
            state = self._store.state.get(key)
            guarantee = self._guarantee_for_key(key, state, requirements)
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

    def final_operations(
        self,
        guarantees: dict[ast.ChainedNameTuple, action_contract.PositionGuarantee],
        *,
        include_callee_derived: bool,
    ) -> list[action_contract.FinalPositionOperation]:
        """Collect final Particle Operations for the action contract."""
        final_operations: list[action_contract.FinalPositionOperation] = []
        for key, guarantee in guarantees.items():
            operation_positions: tuple[ast.ChainedNameTuple, ...] = ()
            if not isinstance(guarantee, action_contract.ErrorGuarantee):
                # A non-error guarantee can only be produced from existing state.
                state = self._store.state[key]
                # A callee can move a particle whose known child positions have
                # no operation nodes: applying its guarantee moves their state,
                # but only explicitly guaranteed positions receive nodes.
                if state.operation_node is not None:
                    operation_positions = state.operation_node.operated_positions
            final_operations.append(
                action_contract.FinalPositionOperation(key, operation_positions)
            )
        # Callers need these positions' final Particle Operations when calculating
        # dependencies, even though their occupancy Guarantees do not propagate.
        # Apply them after occupancy Guarantees, which can create or move their
        # parent positions.
        for key, state in self._store.state.items():
            operation = state.operation_node
            if operation is None:
                continue
            if not include_callee_derived and isinstance(
                operation, operation_graph_model.GuaranteeNode
            ):
                continue
            if not any(name.startswith(_ACTION_KEY_PREFIX) for name in key):
                continue
            # Automatic destruction has removed child state for positions
            # defined in the Action Statements Block.
            final_operations.append(
                action_contract.FinalPositionOperation(
                    key, operation.operated_positions
                )
            )
        return final_operations

    def _guarantee_for_key(
        self,
        key: tuple[str, ...],
        state: _NodeState | None,
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
            )

        if state is not None and state.particle_info is not None:
            info = state.particle_info
            if not info.from_caller:
                return action_contract.OccupiedByNewGuarantee(
                    qualities=info.qualities,
                    origin_position=info.origin_position,
                    caused_by=info.last_position,
                )
            if key != info.origin_position.canonical_chained_name_tuple:
                return action_contract.OccupiedByExistingGuarantee(
                    origin_position=info.origin_position,
                    caused_by=info.last_position,
                )
            # The caller's particle is right where it started.
            if self._position_was_touched(key):
                return action_contract.UnchangedGuarantee(
                    caused_by=info.last_position,
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
            == position_occupancy.PositionOccupancyState.EMPTY
        ):
            # A requirement propagated from a callee doesn't mean the callee
            # operated on that position directly. (It could have been a transitive
            # callee that did it.)
            if self._position_was_touched(key):
                return action_contract.UnchangedGuarantee(
                    caused_by=caused_by,
                )
            return None
        return action_contract.EmptyGuarantee(
            caused_by=caused_by,
        )

    def _position_was_touched(self, key: tuple[str, ...]) -> bool:
        """Whether the action ever touched ``key``."""
        return self._operation_graph_builder.body_touched_key(
            key
        ) or self._store.ever_set_by_callee(key)

    def trigger_action(
        self,
        action_chain: ast.ActionReference,
        contract: action_contract.ActionContract,
        acting_on_position: ast.PositionReference,
        requirements_in_caller: Sequence[action_contract.PositionRequirementInCaller],
        *,
        is_destructor: bool,
        parent_particle: particle_info.ParticleInfo | None,
        destruction_contract_contributions: Sequence[
            operation_graph_model.DestructionContractContribution
        ] = (),
    ) -> list[tuple[ast.ChainedNameTuple, ast.SourceLocation]]:
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
        action_chain_key = action_chain.canonical_chained_name_tuple
        action = action_chain.get_last_action()
        occupied_interface_child_position_violations = (
            self._new_occupied_interface_child_position_violations(
                action, parent_particle
            )
        )
        self._interface_arrival_tracker.mark_action_triggered(
            action.full_typed_name, parent_particle
        )
        self._body_operation_number += 1
        # We have to record the Action Execution when particles are still
        # in their requirements positions, because applying pending guarantees
        # will trigger the guarantees of the callee in the operation graph.
        acting_on_position_key = acting_on_position.canonical_chained_name_tuple
        execution = self._operation_graph_builder.record_action_execution(
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
        # TODO: Investigate whether batching or reusing child-operation subtree
        # traversals across all Destruction Contract contributions for one Action
        # Execution improves project-scale performance without excessive memory.
        for contribution in destruction_contract_contributions:
            self._operation_graph_builder.record_contributed_destruction_fragment(
                execution,
                contribution,
                self._preceding_child_operations_for_contributed_destructors(
                    contribution.destructors
                ),
            )
        callee_guarantees = _PendingGuarantee(
            action_chain_key,
            contract,
            self._body_operation_number,
            execution,
            operation_graph_action_chain=action_chain_key,
        )
        self._nested_guarantees.add(action_chain_key, execution, contract)
        self._apply_pending_guarantee(callee_guarantees)
        return occupied_interface_child_position_violations

    def nested_guarantees(
        self,
    ) -> list[action_contract.CalleeContract]:
        """Return the guarantees of actions this action triggered."""
        return self._nested_guarantees.items(self._operation_graph_builder.executions)

    def _apply_pending_guarantee(self, pending_guarantee: _PendingGuarantee):
        """Apply a callee's guarantees and add one child name to nested guarantee prefixes."""
        operation_graph_guarantees: list[
            operation_graph_model.OperationGraphGuarantee
        ] = []

        application = _GuaranteeApplicationState.for_callee(pending_guarantee)
        applied_guarantee_keys: dict[ast.ChainedNameTuple, ast.ChainedNameTuple] = {}

        # A preceding guarantee may create or move a later guarantee's parent,
        # so acceptance checks must alternate with occupancy updates. Graph
        # recording must wait until all swap-safety restoration has completed.
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
                self._store.error[missing_key] = _ErrorState(
                    caused_by=guarantee.caused_by
                )
                continue

            self._update_store_from_callee_direct_guarantee(
                pending_guarantee, key, guarantee, application
            )
            applied_guarantee_keys[position] = key

        for final_operation in pending_guarantee.contract.final_operations:
            key = applied_guarantee_keys.get(final_operation.position)
            if key is None:
                # A rejected occupancy Guarantee must not replace the operation
                # belonging to the newer state either.
                if final_operation.position in pending_guarantee.contract.guarantees:
                    continue
                key = pending_guarantee.key_for(final_operation.position)
                if self._store.is_superseded(
                    key,
                    pending_guarantee.body_operation_number,
                    pending_guarantee.call_chain_depth,
                ):
                    continue
                if self._store.try_add_action_parent(key) is not None:
                    continue
                self._store.record_operation_write(key, pending_guarantee)
                if key not in self._store.state:
                    self._store.state[key] = _NodeState()
            operation_graph_guarantees.append(
                operation_graph_model.OperationGraphGuarantee(
                    guaranteed_position=key,
                    operation_positions=final_operation.operation_positions,
                )
            )

        guarantee_nodes = self._operation_graph_builder.record_guarantees(
            pending_guarantee.execution,
            pending_guarantee.transitive_executions,
            operation_graph_guarantees,
            guarantee_action_chain=pending_guarantee.action_chain,
            operation_graph_action_chain=pending_guarantee.operation_graph_action_chain,
        )
        for key, node in guarantee_nodes.items():
            state = self._store.state.get(key)
            if state is not None:
                state.operation_node = node
        for child in pending_guarantee.contract.callees:
            child_action_chain_in_guarantee = child.action_chain
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
                child.contract,
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

    def _fully_resolve_pending_guarantees(self, *keys: tuple[str, ...]):
        """Apply guarantees affecting any of the equally long keys or their children."""
        self._apply_pending_guarantees_up_to_all(keys)
        for pending_guarantee in self._pending.drain_at_or_below_for(keys):
            self._apply_pending_guarantee(pending_guarantee)

    def _update_store_from_callee_direct_guarantee(
        self,
        pending_guarantee: _PendingGuarantee,
        key: ast.ChainedNameTuple,
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
            _WriteRecord(
                pending_guarantee.body_operation_number,
                pending_guarantee.call_chain_depth,
                include_in_own_guarantees=isinstance(
                    guarantee, action_contract.OccupiedByExistingGuarantee
                ),
                ever_set_by_callee=True,
            ),
        )

        overwrites_subtree = key in application.origin_keys or (
            key in self._store.state
            and not isinstance(guarantee, action_contract.UnchangedGuarantee)
        )
        # We are about to overwrite this key's subtree, and a later guarantee still
        # needs to read a particle from an origin position that may have it as
        # a parent name.
        if application.origin_keys and overwrites_subtree:
            application.save_origins_at_or_below(
                key, self._store, self._nested_guarantees
            )

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
            self._delete_particle_state_subtree(key)
            if key in self._store.error:
                self._store.error.delete_subtree(key)
            self._nested_guarantees.discard_for_destroyed_particle(key)

        match guarantee:
            case action_contract.OccupiedByExistingGuarantee():
                self._apply_existing_guarantee(
                    key,
                    pending_guarantee,
                    guarantee,
                    application,
                )
            case action_contract.EmptyGuarantee():
                self._store.state[key] = _NodeState(emptied_by=guarantee.caused_by)
            case action_contract.OccupiedByNewGuarantee():
                new_info = particle_info.ParticleInfo(
                    last_position=guarantee.caused_by,
                    qualities=guarantee.qualities,
                    origin_position=guarantee.origin_position,
                )
                self._store.state[key] = _NodeState(particle_info=new_info)
                self._register_occupied_interface_child_position(
                    key,
                    new_info,
                    pending_guarantee.execution.callee_action_name.location,
                )
            case action_contract.ErrorGuarantee():
                self._store.error[key] = _ErrorState(caused_by=guarantee.caused_by)
            case action_contract.UnchangedGuarantee():
                # The position is unchanged from before the callee triggered,
                # which the caller's store already reflects (the cleanup above
                # kept any occupant). A later Move of its parent must still
                # collect the callee's operations on an otherwise-untracked
                # empty child position. The write record above still supersedes
                # a conflicting nested guarantee.
                if key not in self._store.state:
                    self._store.state[key] = _NodeState()
            case _:
                raise TypeError(f"Unexpected guarantee type: {type(guarantee)}")

    def _apply_existing_guarantee(
        self,
        dest_key: tuple[str, ...],
        pending_guarantee: _PendingGuarantee,
        guarantee: action_contract.OccupiedByExistingGuarantee,
        application: _GuaranteeApplicationState,
    ):
        """Apply an OccupiedByExisting guarantee at dest_key."""
        origin_tuple = guarantee.origin_position.canonical_chained_name_tuple
        origin_key = pending_guarantee.key_for(origin_tuple)

        # Get origin's particle_info — from saved copy if already processed,
        # else from the live trie.
        saved_tree = application.saved_state.pop(origin_key, None)
        if saved_tree is not None:
            origin_state = saved_tree[origin_tuple[-1:]]
        elif origin_key in self._store.state:
            origin_state = self._store.state[origin_key]
        else:
            # The caller never filled the position, and we are executing an OccupiedByExisting
            # guarantee on the same position that a particle was passed in on.
            self._store.error[dest_key] = _ErrorState(caused_by=guarantee.caused_by)
            return

        # The caller never filled the Interface Position. The callee moves the
        # particle to another position. Thus, the origin_state _exists_ but the
        # position got EmptyGuarantee instead of being filled by something (and
        # there's nothing in application.saved_state).
        if origin_state.particle_info is None:
            self._store.error[dest_key] = _ErrorState(caused_by=guarantee.caused_by)
            return

        moved_info = origin_state.particle_info
        moved_info.last_position = guarantee.caused_by
        self._interface_arrival_tracker.mark_particle_departed(moved_info)
        source_location = pending_guarantee.execution.callee_action_name.location

        def record_guaranteed_position(
            position: ast.ChainedNameTuple,
            state: _NodeState,
        ):
            if state.particle_info is not None:
                self._replace_occupied_interface_child_position(
                    position,
                    state.particle_info,
                    source_location,
                )

        if saved_tree is not None:
            self._store.state.restore_subtree(
                dest_key,
                saved_tree,
                _NodeState(particle_info=moved_info),
                restored_value_callback=record_guaranteed_position,
            )
            saved_nested_subtree = application.saved_nested_guarantees.pop(
                origin_key, None
            )
            if saved_nested_subtree is not None:
                self._nested_guarantees.restore_moved_particle(
                    origin_key, dest_key, saved_nested_subtree
                )
        else:
            self._store.state.move_subtree(
                origin_key,
                dest_key,
                moved_value_callback=record_guaranteed_position,
            )
            self._store.state[dest_key] = _NodeState(particle_info=moved_info)
            self._nested_guarantees.move(origin_key, dest_key)

        saved_unk = application.saved_error.pop(origin_key, None)
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
