"""Store particle state, error state, write records, and nested guarantees for each Position."""

from __future__ import annotations

import typing

import msgspec

from define.compiler import ast, chained_name
from define.compiler.data_structures import trie
from define.compiler.validator.reference_graph import (
    action_contract,
    child_state,
    position_occupancy,
)

if typing.TYPE_CHECKING:
    from collections.abc import Iterable, Iterator, Sequence

    from define.compiler.validator import codegen_input
    from define.compiler.validator.reference_graph.particles import particle_info


class _NodeState(msgspec.Struct):
    """Mutable state for a position in the state trie."""

    particle_info: particle_info.ParticleInfo | None = None
    emptied_by: ast.PositionReference | None = None


def _node_is_occupied(state: _NodeState) -> bool:
    return state.particle_info is not None


class _ErrorState(msgspec.Struct):
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


def _child_value(node: _NodeState) -> particle_info.ParticleValueState | None:
    particle = node.particle_info
    if particle is None or particle.qualities.value_type is None:
        return None
    return particle.value_state


def _child_error_occupancy(
    error: _ErrorState,
) -> position_occupancy.ChildOccupancy | None:
    if error.caused_by is not None:
        return position_occupancy.ERROR_OCCUPANCY
    return None


# Body statements and a directly-applied contract's own guarantees are both at
# call-chain depth 0.
_BODY_DEPTH = 0


class _WriteRecord(msgspec.Struct, frozen=True):
    """A record of a write to a position, containing the information necessary to resolve it when applying guarantees.

    Writes are ordered by execution: a higher ``body_operation_number`` wins, and
    at the same number the lower ``depth`` wins (a contract's own guarantee
    outranks a nested guarantee that shares the trigger's operation number).
    """

    body_operation_number: int
    depth: int
    # Results left in a callee's contract need not be published again by this action.
    include_in_own_guarantees: bool


class DetachedSubtrees(msgspec.Struct):
    """Subtrees detached from the store while a callee's Guarantees overwrite their positions.

    Each subtree is keyed by the full key it was detached from.
    """

    state: dict[
        chained_name.ChainedNameTuple, trie.StrictReparentingTrie[_NodeState]
    ] = msgspec.field(default_factory=dict)
    error: dict[
        chained_name.ChainedNameTuple, trie.StrictReparentingTrie[_ErrorState]
    ] = msgspec.field(default_factory=dict)
    nested_guarantees: dict[
        chained_name.ChainedNameTuple,
        trie.StrictReparentingTrie[list[codegen_input.ActionExecution]],
    ] = msgspec.field(default_factory=dict)

    def has_state(self, key: chained_name.ChainedNameTuple) -> bool:
        """Return whether the Position at ``key`` had state when it was detached."""
        return key in self.state

    def occupant_or_none(
        self, key: chained_name.ChainedNameTuple
    ) -> particle_info.ParticleInfo | None:
        """Return the particle detached from ``key``, or None if the Position was empty."""
        return self.state[key][key[-1:]].particle_info


class _CurrentActionNestedGuarantees:
    """Nested guarantees keyed by the action chain where they currently apply.

    Stores the nested guarantees that will directly become part of this action's
    contract.
    """

    def __init__(self):
        self._by_action_chain: trie.LenientReparentingTrie[
            list[codegen_input.ActionExecution]
        ] = trie.LenientReparentingTrie(default_factory=list)
        self._contracts: dict[
            codegen_input.ActionExecution, action_contract.ActionContract
        ] = {}

    def add(
        self,
        action_chain: chained_name.ActionReferenceTuple,
        execution: codegen_input.ActionExecution,
        contract: action_contract.ActionContract,
    ):
        at_action_chain = self._by_action_chain.get(action_chain)
        if at_action_chain is None:
            at_action_chain = []
            self._by_action_chain[action_chain] = at_action_chain
        at_action_chain.append(execution)
        self._contracts[execution] = contract

    def move(
        self,
        source: chained_name.PositionReferenceTuple,
        target: chained_name.PositionReferenceTuple,
    ):
        """Move nested guarantees beneath a moved particle."""
        if source not in self._by_action_chain:
            return
        self._by_action_chain.move_subtree(source, target)

    def discard_for_destroyed_particle(
        self, position: chained_name.PositionReferenceTuple
    ):
        """Discard nested guarantees belonging to a destroyed particle."""
        if position in self._by_action_chain:
            self._by_action_chain.delete_subtree(position)

    def pop_subtrees(
        self, positions: Iterable[chained_name.PositionReferenceTuple]
    ) -> dict[
        chained_name.ChainedNameTuple,
        trie.StrictReparentingTrie[list[codegen_input.ActionExecution]],
    ]:
        """Detach nested guarantees belonging to particles that may move."""
        return self._by_action_chain.pop_subtrees(positions)

    def restore_moved_particle(
        self,
        source: chained_name.PositionReferenceTuple,
        target: chained_name.PositionReferenceTuple,
        saved_subtree: trie.StrictReparentingTrie[list[codegen_input.ActionExecution]],
    ):
        """Restore a saved particle's nested guarantees at its destination."""
        self._by_action_chain.restore_subtree(
            target, saved_subtree, saved_subtree[source[-1:]]
        )

    def items(self) -> list[action_contract.CalleeContract]:
        """Return nested guarantees in triggering order."""
        by_execution: dict[
            codegen_input.ActionExecution,
            action_contract.CalleeContract,
        ] = {}
        # The trie alone tracks current action chains during Moves, so moving
        # one particle does not rewrite every repeated execution of its actions.
        for action_chain, guarantees in self._by_action_chain.items():
            for nested_guarantees in guarantees:
                by_execution[nested_guarantees] = action_contract.CalleeContract(
                    _stored_action_chain(action_chain),
                    self._contracts[nested_guarantees],
                )
        return [
            by_execution[execution]
            for execution in self._contracts
            if execution in by_execution
        ]

    def action_chains_with_most_recent_trigger(
        self,
    ) -> Iterator[
        tuple[chained_name.ActionReferenceTuple, ast.GlobalTypedNameReference]
    ]:
        """Yield each triggered action chain and its most recent direct trigger."""
        for action_chain, nested_guarantees in self._by_action_chain.items():
            if not nested_guarantees:
                continue
            yield (
                _stored_action_chain(action_chain),
                nested_guarantees[-1].action.get_last_action(),
            )


def _stored_action_chain(key: trie.TrieKey) -> chained_name.ActionReferenceTuple:
    # Only action chains are added, and a Move replaces only a key's parent
    # names, so every key in the trie still ends in its action.
    return chained_name.ActionReferenceTuple(key)


class ParticleStateStore:
    """The internal Position state store, which tracks particle state and its relationship to our callees' contracts.

    Particle state lives in two tries (``state`` and ``error``). Positions
    in ``error`` have an error condition: the compiler detected a problem
    but continues validation to find other errors. We ignore Positions in
    error states to avoid cascading diagnostics.

    Each Position written during an Action Statements Block also has a
    ``_WriteRecord``. This records execution order and whether the Position's
    Guarantee must be published directly in this action's contract or can remain
    in a callee's contract. Marking a Position erroneous also records a write;
    assuming its starting occupancy does not.

    Because Guarantees are applied lazily, a Guarantee from an earlier Action
    Execution can be processed after a later statement has changed the Position.
    ``is_superseded`` uses the write record to prevent that earlier Guarantee
    from overwriting the later state, including error state. Within one Action
    Execution, a contract's own Guarantee takes precedence over a deeper callee's
    Guarantee that it already resolved.
    """

    def __init__(self):
        """Initialize a store that tracks no Positions."""
        self._state: trie.StrictReparentingTrie[_NodeState] = (
            trie.StrictReparentingTrie()
        )
        self._error: trie.LenientReparentingTrie[_ErrorState] = (
            trie.LenientReparentingTrie(default_factory=_ErrorState)
        )
        # Keyed generically because a Move re-keys records by subtree keys, which
        # include action names; only positions ever have a record.
        self._write_record: dict[chained_name.ChainedNameTuple, _WriteRecord] = {}
        self._nested_guarantees: _CurrentActionNestedGuarantees = (
            _CurrentActionNestedGuarantees()
        )

    def has_state(self, key: chained_name.PositionReferenceTuple) -> bool:
        """Return whether the store tracks this Position, whether or not its occupancy is known."""
        return key in self._state

    def mark_error(
        self, key: chained_name.PositionReferenceTuple, caused_by: ast.PositionReference
    ):
        """Mark a Position as having error occupancy state."""
        self._error[key] = _ErrorState(caused_by=caused_by)

    def mark_emptied(
        self,
        key: chained_name.PositionReferenceTuple,
        emptied_by: ast.PositionReference,
    ):
        """Record that a Position is known to be empty, replacing any state it had."""
        self._state[key] = _NodeState(emptied_by=emptied_by)

    def mark_occupied(
        self, key: chained_name.PositionReferenceTuple, info: particle_info.ParticleInfo
    ):
        """Record that a particle occupies a Position, replacing any state it had."""
        self._state[key] = _NodeState(particle_info=info)

    def mark_unchanged(self, key: chained_name.PositionReferenceTuple):
        """Record that a callee left a Position unchanged, tracking it with unknown occupancy if it has no state."""
        if key not in self._state:
            self._state[key] = _NodeState()

    def ensure_action_parent(self, key: chained_name.PositionReferenceTuple):
        """Ensure the action name preceding the position has tracker state."""
        if len(key) >= 2 and chained_name.is_action_key(key[-2]):
            parent_key = key[:-1]
            if parent_key not in self._state:
                # This is the other repeated allocation from the default
                # action-graph full-compiler experiment documented in
                # try_add_action_parent: replacing both paths' fresh _NodeState
                # values with one shared object showed no measurable wall-time change.
                self._state[parent_key] = _NodeState()

    def delete_subtree(
        self,
        key: chained_name.PositionReferenceTuple,
        removed_particle_callback: typing.Callable[[particle_info.ParticleInfo], None],
    ):
        """Delete everything tracked at or below a Position, passing each removed particle to ``removed_particle_callback``."""

        def call_with_removed_particle(state: _NodeState):
            if state.particle_info is not None:
                removed_particle_callback(state.particle_info)

        if key in self._state:
            self._state.delete_subtree(
                key, removed_value_callback=call_with_removed_particle
            )
        if key in self._error:
            self._error.delete_subtree(key)
        self._nested_guarantees.discard_for_destroyed_particle(key)

    def move_subtree(
        self,
        from_key: chained_name.PositionReferenceTuple,
        to_key: chained_name.PositionReferenceTuple,
        moved_particle_callback: typing.Callable[
            [chained_name.PositionReferenceTuple, particle_info.ParticleInfo], None
        ],
    ):
        """Move a particle and everything tracked below it to an untracked Position."""
        self._move_live_subtree(from_key, to_key, moved_particle_callback)
        if from_key in self._error:
            self._move_error_subtree(from_key, to_key)
        self._rekey_records_for_move(from_key, to_key)

    def move_guaranteed_particle(
        self,
        from_key: chained_name.PositionReferenceTuple,
        to_key: chained_name.PositionReferenceTuple,
        detached: DetachedSubtrees,
        moved_particle_callback: typing.Callable[
            [chained_name.PositionReferenceTuple, particle_info.ParticleInfo], None
        ],
    ):
        """Move the particle that a callee's Guarantee says occupies ``to_key``.

        The particle comes from ``detached`` if an earlier Guarantee of the same
        callee overwrote its origin position, and from the live state otherwise.
        """
        detached_state = detached.state.pop(from_key, None)
        if detached_state is None:
            self._move_live_subtree(from_key, to_key, moved_particle_callback)
        else:
            self._state.restore_subtree(
                to_key,
                detached_state,
                detached_state[from_key[-1:]],
                restored_value_callback=self._wrap_moved_particle_callback(
                    moved_particle_callback
                ),
            )
            detached_nested_guarantees = detached.nested_guarantees.pop(from_key, None)
            if detached_nested_guarantees is not None:
                self._nested_guarantees.restore_moved_particle(
                    from_key, to_key, detached_nested_guarantees
                )

        detached_error = detached.error.pop(from_key, None)
        # Guarantees reset the error state of particles they touch directly.
        # If we guarantee a particle in a position, then we know that it has a
        # particle. However, its _children_ might still be in some error state.
        # Exception: if the origin had pre-action error state (saved before the
        # guarantee loop began), the destination inherits that caused_by — the
        # guarantee fills it with whatever was at origin, including the uncertainty.
        if detached_error is not None:
            self._error.restore_subtree(
                to_key, detached_error, detached_error[from_key[-1:]]
            )
        elif from_key in self._error:
            self._move_error_subtree(from_key, to_key)

    def _move_live_subtree(
        self,
        from_key: chained_name.PositionReferenceTuple,
        to_key: chained_name.PositionReferenceTuple,
        moved_particle_callback: typing.Callable[
            [chained_name.PositionReferenceTuple, particle_info.ParticleInfo], None
        ],
    ):
        self._state.move_subtree(
            from_key,
            to_key,
            moved_value_callback=self._wrap_moved_particle_callback(
                moved_particle_callback
            ),
        )
        self._nested_guarantees.move(from_key, to_key)

    def _move_error_subtree(
        self,
        from_key: chained_name.PositionReferenceTuple,
        to_key: chained_name.PositionReferenceTuple,
    ):
        self._error.move_subtree(from_key, to_key)
        # A moved particle's own Position is known once it arrives; only its
        # child positions keep their error state.
        self._error[to_key] = _ErrorState()

    @staticmethod
    def _wrap_moved_particle_callback(
        moved_particle_callback: typing.Callable[
            [chained_name.PositionReferenceTuple, particle_info.ParticleInfo], None
        ],
    ) -> typing.Callable[[chained_name.ChainedNameTuple, _NodeState], None]:
        def call_with_moved_particle(
            position: chained_name.ChainedNameTuple, state: _NodeState
        ):
            if state.particle_info is not None:
                # Only positions hold particles.
                moved_particle_callback(
                    chained_name.PositionReferenceTuple(position), state.particle_info
                )

        return call_with_moved_particle

    def detach_subtrees(
        self,
        keys: Sequence[chained_name.PositionReferenceTuple],
        detached: DetachedSubtrees,
    ):
        """Detach everything tracked at or below each of ``keys`` into ``detached``."""
        detached.state.update(self._state.pop_subtrees(keys))
        detached.error.update(self._error.pop_subtrees(keys))
        detached.nested_guarantees.update(self._nested_guarantees.pop_subtrees(keys))

    def record_triggered_action(
        self,
        action_chain: chained_name.ActionReferenceTuple,
        execution: codegen_input.ActionExecution,
        contract: action_contract.ActionContract,
    ):
        """Record an Action Execution whose nested guarantees this action's contract carries."""
        self._nested_guarantees.add(action_chain, execution, contract)

    def nested_guarantees(self) -> list[action_contract.CalleeContract]:
        """Return the guarantees of actions this action triggered, in triggering order."""
        return self._nested_guarantees.items()

    def unconsumed_action_interfaces(
        self,
    ) -> Iterator[
        tuple[ast.GlobalTypedNameReference, chained_name.PositionReferenceTuple]
    ]:
        """Yield occupied interfaces of callees directly triggered by this action."""
        for (
            action_chain,
            action,
        ) in self._nested_guarantees.action_chains_with_most_recent_trigger():
            if self.has_error_in_chain(action_chain):
                continue
            for child_key, state in self._state.direct_child_items(action_chain):
                # An action's child names are its interface positions.
                position = chained_name.PositionReferenceTuple(child_key)
                if state.particle_info is None or self.has_error_at(position):
                    continue
                yield action, position

    def longest_occupied_prefix(
        self, key: chained_name.PositionReferenceTuple
    ) -> chained_name.PositionReferenceTuple | None:
        """Return the longest prefix of ``key`` that holds a particle, if any."""
        prefix = self._state.find_longest_prefix_where(key, _node_is_occupied)
        # Only positions hold particles.
        return None if prefix is None else chained_name.PositionReferenceTuple(prefix)

    def error_caused_by(
        self, key: chained_name.PositionReferenceTuple
    ) -> ast.PositionReference | None:
        """Return what caused this exact Position's error occupancy state, if it has one."""
        state = self._error.get(key)
        return state.caused_by if state is not None else None

    def is_occupied(self, key: chained_name.PositionReferenceTuple) -> bool:
        """Return whether a particle is known to exist at this position."""
        state = self._state.get(key)
        return state is not None and state.particle_info is not None

    def occupant(
        self, key: chained_name.PositionReferenceTuple
    ) -> particle_info.ParticleInfo:
        """Return the particle at this position, raising KeyError if it is empty."""
        state = self._state[key]
        if state.particle_info is None:
            raise KeyError(key)
        return state.particle_info

    def occupant_or_none(
        self, key: chained_name.PositionReferenceTuple
    ) -> particle_info.ParticleInfo | None:
        """Return the particle at this position, or None if it is empty."""
        state = self._state.get(key)
        return state.particle_info if state is not None else None

    def snapshot_child_state(
        self, key: chained_name.PositionReferenceTuple
    ) -> child_state.ChildState:
        """Capture known descendant occupancy and values, with keys relative to key."""
        result = dict(self._state.selected_subtree_items(key, _child_occupancy))
        # An error entry wins over a stale state entry, so it is applied last.
        result.update(self._error.selected_subtree_items(key, _child_error_occupancy))
        values = dict(self._state.selected_subtree_items(key, _child_value))
        return child_state.ChildState(
            child_state.FlatChildStateStore(result),
            child_state.FlatChildStateStore(values),
        )

    def collect_caller_destruction_state(
        self,
        occupancies: child_state.ChildOccupancyMap,
        values: child_state.ChildValueMap,
        particles: dict[chained_name.ChainedNameTuple, particle_info.ParticleInfo],
        snapshot: child_state.ChildState,
        key: chained_name.PositionReferenceTuple,
        position_in_child_state: chained_name.ChainedNameTuple,
        contract_positions: set[chained_name.ChainedNameTuple],
    ):
        """Collect caller particles and additional Child State, keyed by Child State position."""
        particle = self.occupant(key)
        particles[position_in_child_state] = particle
        known_occupancy = snapshot.occupancy.get(position_in_child_state)
        # The walk below visits only child positions. For the particle itself,
        # use its original position in the caller, even if the callee moved it.
        if (
            known_occupancy is not None
            and known_occupancy.state
            == position_occupancy.PositionOccupancyState.OCCUPIED
        ):
            self._collect_caller_value(
                position_in_child_state, particle, snapshot.values, values
            )
        prefix_length = len(position_in_child_state)
        # Another contract can describe a child particle with an independent
        # origin after a Move. Its own caller knowledge must determine that
        # particle's Child State, not the old contents of this caller position.
        for state_position, node in self._state.pruned_subtree_items(
            key,
            key_prefix=position_in_child_state,
            excluded_keys=contract_positions,
        ):
            particle = node.particle_info
            if particle is not None:
                caller_position_key = key + state_position[prefix_length:]
                if not self.has_error_in_chain(caller_position_key):
                    particles[state_position] = particle
            known_occupancy = snapshot.occupancy.get(state_position)
            if known_occupancy is None:
                # The callee left occupancy unknown, so the caller can supply it.
                occupancy = _child_occupancy(node)
                if occupancy is not None:
                    occupancies[state_position] = occupancy
            elif (
                known_occupancy.state
                != position_occupancy.PositionOccupancyState.OCCUPIED
            ):
                # The callee knows this position is empty or has an error, so
                # the caller's particle cannot supply a value here.
                continue
            # Even when occupancy was already known, the value may be unknown.
            self._collect_caller_value(
                state_position, particle, snapshot.values, values
            )
        # An error entry wins over a stale state entry, so it is applied last.
        for state_position, error in self._error.pruned_subtree_items(
            key,
            key_prefix=position_in_child_state,
            excluded_keys=contract_positions,
        ):
            if snapshot.occupancy.get(state_position) is not None:
                continue
            if error.caused_by is not None:
                occupancies[state_position] = position_occupancy.ERROR_OCCUPANCY

    @staticmethod
    def _collect_caller_value(
        position: chained_name.ChainedNameTuple,
        particle: particle_info.ParticleInfo | None,
        known_values: child_state.ChildStateStore[particle_info.ParticleValueState],
        values: child_state.ChildValueMap,
    ):
        """Fill missing destruction-time value state from the caller."""
        if (
            particle is not None
            and particle.qualities.value_type is not None
            and particle.value_state is not None
            and known_values.get(position) is None
        ):
            values[position] = particle.value_state

    def emptied_by(
        self, key: chained_name.PositionReferenceTuple
    ) -> ast.PositionReference | None:
        """Return the position reference that emptied this position, if it is known-empty."""
        state = self._state.get(key)
        return state.emptied_by if state is not None else None

    def has_known_occupancy(self, key: chained_name.PositionReferenceTuple) -> bool:
        """Return whether the Position is known to be occupied or empty."""
        state = self._state.get(key)
        if state is None:
            return False
        return state.particle_info is not None or state.emptied_by is not None

    def has_error_in_chain(self, key: chained_name.ChainedNameTuple) -> bool:
        """Return whether this position or any ancestor has error occupancy state."""
        return (
            self._error.find_shortest_prefix_where(
                key, lambda state: state.caused_by is not None
            )
            is not None
        )

    def has_error_at(self, key: chained_name.PositionReferenceTuple) -> bool:
        """Return whether this exact position has error occupancy state."""
        state = self._error.get(key)
        return state is not None and state.caused_by is not None

    def nearest_occupied_ancestors(
        self, keys: Sequence[chained_name.PositionReferenceTuple]
    ) -> dict[
        chained_name.PositionReferenceTuple,
        tuple[chained_name.PositionReferenceTuple, particle_info.ParticleInfo] | None,
    ]:
        """Return the nearest occupied ancestor for each distinct key."""
        ancestor_keys = self._state.find_longest_prefixes_where(keys, _node_is_occupied)
        results: dict[
            chained_name.PositionReferenceTuple,
            tuple[chained_name.PositionReferenceTuple, particle_info.ParticleInfo]
            | None,
        ] = {}
        for key in keys:
            ancestor_key = ancestor_keys[key]
            if ancestor_key is None:
                results[key] = None
                continue
            # Only positions hold particles.
            ancestor_position = chained_name.PositionReferenceTuple(ancestor_key)
            results[key] = ancestor_position, self.occupant(ancestor_position)
        return results

    def keys_for_guarantees(
        self, *, include_callee_derived: bool
    ) -> set[chained_name.PositionReferenceTuple]:
        """Return every position that we need to provide a guarantee for: occupied, known-empty, or marked error.

        Positions set by our callees are included only when ``include_callee_derived`` is set.
        """
        # Only positions hold a particle, emptied state, or error state.
        keys: set[chained_name.PositionReferenceTuple] = set()
        for key, state in self._state.items():
            position = chained_name.PositionReferenceTuple(key)
            if (state.particle_info is not None or state.emptied_by is not None) and (
                include_callee_derived or self._include_in_own_guarantees(position)
            ):
                keys.add(position)
        for key, error_state in self._error.items():
            position = chained_name.PositionReferenceTuple(key)
            if error_state.caused_by is not None and (
                include_callee_derived or self._include_in_own_guarantees(position)
            ):
                keys.add(position)
        return keys

    def is_superseded(
        self,
        key: chained_name.PositionReferenceTuple,
        body_operation_number: int,
        depth: int,
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

    def _include_in_own_guarantees(
        self, key: chained_name.PositionReferenceTuple
    ) -> bool:
        """Whether to include this position when collecting this action's own Guarantees."""
        record = self._write_record.get(key)
        return record is None or record.include_in_own_guarantees

    def was_written(self, key: chained_name.PositionReferenceTuple) -> bool:
        """Return whether the action body or a callee wrote this position."""
        return key in self._write_record

    def record_write(
        self,
        key: chained_name.PositionReferenceTuple,
        body_operation_number: int,
    ):
        """Record an ordered state write from the action body.

        A later body operation overrides earlier callee Guarantees, even if it
        leaves the position in its initial state.
        """
        self._write_record[key] = _WriteRecord(
            body_operation_number,
            _BODY_DEPTH,
            include_in_own_guarantees=True,
        )

    def record_callee_write(
        self,
        key: chained_name.PositionReferenceTuple,
        body_operation_number: int,
        depth: int,
        *,
        include_in_own_guarantees: bool,
    ):
        """Record that a callee's contract authored ``key``."""
        self._write_record[key] = _WriteRecord(
            body_operation_number, depth, include_in_own_guarantees
        )

    def try_add_action_parent(
        self, key: chained_name.PositionReferenceTuple
    ) -> chained_name.PositionReferenceTuple | None:
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
            if chained_name.is_action_key(parent_key[-1]):
                # Repeated _NodeState construction for action-name trie
                # keys looked costly in the default action-graph full-compiler
                # benchmark. An August 2026 experiment replaced every fresh value
                # here and in ensure_action_parent with one shared _NodeState;
                # unprofiled runs showed no measurable wall-time change.
                self._state[parent_key] = _NodeState()
                return None
            return chained_name.PositionReferenceTuple(parent_key)
        # Two or more names are absent, so only a walk can say which of them the
        # caller left unfilled first.
        first_missing_index = len(self._state.existing_prefix(key))
        # An action name never holds a particle, so the position after it is the
        # one the caller left unfilled.
        if chained_name.is_action_key(key[first_missing_index]):
            first_missing_index += 1
        return chained_name.PositionReferenceTuple(key[: first_missing_index + 1])

    def _rekey_records_for_move(
        self,
        from_key: chained_name.PositionReferenceTuple,
        to_key: chained_name.PositionReferenceTuple,
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
