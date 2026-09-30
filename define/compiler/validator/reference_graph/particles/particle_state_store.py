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
    from define.compiler.validator.reference_graph.particles import (
        particle_info,
        pending_guarantee,
    )

type _PendingGuarantees = dict[
    pending_guarantee.PendingGuaranteeIdentity, pending_guarantee.PendingGuarantee
]


class _NodeState(msgspec.Struct):
    """Mutable state for a position or action name in the state trie."""


class _PositionNodeState(_NodeState):
    """Mutable state for a position in the state trie."""

    particle_info: particle_info.ParticleInfo | None = None
    emptied_by: ast.PositionReference | None = None
    # Callee Guarantees that describe this particle's children and have not
    # been applied yet, in the order they were added. They move and are
    # deleted with this node.
    pending_guarantees: _PendingGuarantees | None = None


class _ActionNodeState(_NodeState):
    """Mutable state for an action name in the state trie."""

    # This action's executions of that action, in triggering order. They move
    # and are deleted with this node.
    triggered_executions: list[codegen_input.ActionExecution] = msgspec.field(
        default_factory=list
    )


def _node_is_occupied(state: _NodeState) -> bool:
    return isinstance(state, _PositionNodeState) and state.particle_info is not None


class _ErrorState(msgspec.Struct):
    """Wrapper for error-state trie values.

    LenientReparentingTrie can't use None as a value, so we wrap
    the caused_by reference in a dataclass.
    """

    caused_by: ast.PositionReference | None = None


def _child_occupancy(node: _NodeState) -> position_occupancy.ChildOccupancy | None:
    if not isinstance(node, _PositionNodeState):
        return None
    if node.particle_info is not None:
        return position_occupancy.ChildOccupancy(
            position_occupancy.PositionOccupancyState.OCCUPIED,
            filled_at=node.particle_info.last_position.location,
        )
    if node.emptied_by is not None:
        return position_occupancy.EMPTY_OCCUPANCY
    return None


def _child_value(node: _NodeState) -> particle_info.ParticleValueState | None:
    if not isinstance(node, _PositionNodeState):
        return None
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


class _WriteRecord(msgspec.Struct, frozen=True):
    """A record of a write to a position."""

    # Results left in a callee's contract need not be published again by this action.
    include_in_own_guarantees: bool


# Every write from the action body has the same record.
_BODY_WRITE = _WriteRecord(include_in_own_guarantees=True)


class _CalleeWriteRecord(_WriteRecord, frozen=True):
    """A write by a callee's guarantee.

    Within one Action Execution, the lower ``depth`` wins: a contract's own
    guarantee outranks a nested guarantee that it already resolved.
    """

    # Action Executions compare by identity.
    execution: codegen_input.ActionExecution
    depth: int


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

    def has_state(self, key: chained_name.ChainedNameTuple) -> bool:
        """Return whether the Position at ``key`` had state when it was detached."""
        return key in self.state

    def occupant_or_none(
        self, key: chained_name.ChainedNameTuple
    ) -> particle_info.ParticleInfo | None:
        """Return the particle detached from ``key``, or None if the Position was empty."""
        state = self.state[key][chained_name.last_name(key)]
        # Only positions are detached.
        return typing.cast("_PositionNodeState", state).particle_info


class ParticleStateStore:
    """The internal Position state store, which tracks particle state and its relationship to our callees' contracts.

    Particle state lives in two tries (``state`` and ``error``). Positions
    in ``error`` have an error condition: the compiler detected a problem
    but continues validation to find other errors. We ignore Positions in
    error states to avoid cascading diagnostics.

    Each Position written during an Action Statements Block also has a
    ``_WriteRecord``. This records whether the Position's Guarantee must be
    published directly in this action's contract or can remain in a callee's
    contract, and, for a callee's write, which Action Execution and call-chain
    depth wrote it. Marking a Position erroneous also records a write; assuming
    its starting occupancy does not.

    Within one Action Execution, a contract's own Guarantee takes precedence
    over a deeper callee's Guarantee that it already resolved; ``is_superseded``
    uses the write record to enforce that.
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
        # Every Action Execution this action triggered, in triggering order.
        # Each one also sits on the node of its action name, which tracks where
        # it currently is.
        self._triggered_contracts: dict[
            codegen_input.ActionExecution, action_contract.ActionContract
        ] = {}
        # Pending Guarantees on the action's own parent particle, which is the
        # empty chained name, so the trie cannot hold them.
        self._root_pending_guarantees: _PendingGuarantees = {}
        # Lets expansions skip their walk when nothing is pending, the common
        # case. Guarantees deleted with a subtree, or in a detached subtree that
        # is never restored, stay counted, which only costs that shortcut.
        self._pending_guarantee_count: int = 0

    def has_state(self, key: chained_name.PositionReferenceTuple) -> bool:
        """Return whether the store tracks this Position, whether or not its occupancy is known."""
        return key in self._state

    def tracks_at_or_below(self, key: chained_name.PositionReferenceTuple) -> bool:
        """Return whether the store tracks any state or error at this Position or below it."""
        # Both tries hold every parent name of each key they hold.
        return key in self._state or key in self._error

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
        self._state[key] = _PositionNodeState(
            emptied_by=emptied_by, pending_guarantees=self._node_pending(key)
        )

    def mark_occupied(
        self, key: chained_name.PositionReferenceTuple, info: particle_info.ParticleInfo
    ):
        """Record that a particle occupies a Position, replacing any state it had."""
        self._state[key] = _PositionNodeState(
            particle_info=info, pending_guarantees=self._node_pending(key)
        )

    def _node_pending(
        self, key: chained_name.PositionReferenceTuple
    ) -> _PendingGuarantees | None:
        state = self._position_state(key)
        return None if state is None else state.pending_guarantees

    def _position_state(
        self, key: chained_name.PositionReferenceTuple
    ) -> _PositionNodeState | None:
        # Only action names hold _ActionNodeState.
        return typing.cast("_PositionNodeState | None", self._state.get(key))

    def _action_state(
        self, key: chained_name.ActionReferenceTuple
    ) -> _ActionNodeState | None:
        # Only action names hold _ActionNodeState.
        return typing.cast("_ActionNodeState | None", self._state.get(key))

    def _pending_state(
        self, prefix: chained_name.ChainedNameTuple
    ) -> _PositionNodeState | None:
        """Return the state at ``prefix`` if it is a tracked position, which is where pending Guarantees are stored."""
        state = self._state.get(prefix)
        return state if isinstance(state, _PositionNodeState) else None

    def add_pending_guarantee(
        self,
        prefix: chained_name.ChainedNameTuple,
        pending: pending_guarantee.PendingGuarantee,
    ):
        """Record a callee's Guarantees to apply once something reaches the particle at ``prefix``, whose children they describe."""
        if prefix:
            # An action name always follows its particle's position.
            state = self._position_state(chained_name.position(prefix))
            # The caller never filled the particle's position, which requirement
            # checking already reported, so nothing can reach these Guarantees.
            if state is None:
                return
            if state.pending_guarantees is None:
                state.pending_guarantees = {}
            guarantees = state.pending_guarantees
        else:
            guarantees = self._root_pending_guarantees
        # When several implying qualities imply the same quality, each of
        # them adds that quality's action as a nested guarantee. From the
        # caller's perspective, an implied action's chain drops the action
        # that implied it, so all of those copies have the same chain. Over
        # layers of shared implied qualities, the copies multiply with every
        # layer. Applying each copy would take exponential time. Keeping
        # only the latest copy preserves which guarantee writes each
        # position last.
        identity = pending.identity
        if guarantees.pop(identity, None) is None:
            self._pending_guarantee_count += 1
        guarantees[identity] = pending

    def has_any_pending_guarantees(self) -> bool:
        """Return whether any pending Guarantees might remain."""
        return self._pending_guarantee_count > 0

    def has_pending_guarantees(self, prefix: chained_name.ChainedNameTuple) -> bool:
        """Return whether pending Guarantees describe the children of the particle at ``prefix``."""
        if not prefix:
            return bool(self._root_pending_guarantees)
        state = self._pending_state(prefix)
        return state is not None and bool(state.pending_guarantees)

    def pending_guarantees_at(
        self, key: chained_name.PositionReferenceTuple
    ) -> Iterable[pending_guarantee.PendingGuarantee]:
        """Return the pending Guarantees that describe the children of the particle at ``key``."""
        # Only action names hold _ActionNodeState.
        state = typing.cast("_PositionNodeState", self._state[key])
        pending_guarantees = state.pending_guarantees
        return () if pending_guarantees is None else pending_guarantees.values()

    def pop_pending_guarantees(
        self, prefix: chained_name.ChainedNameTuple
    ) -> Iterable[pending_guarantee.PendingGuarantee]:
        """Remove and return the pending Guarantees that describe the children of the particle at ``prefix``."""
        if not prefix:
            guarantees = self._root_pending_guarantees
            self._root_pending_guarantees = {}
        else:
            state = self._pending_state(prefix)
            if state is None or state.pending_guarantees is None:
                return ()
            guarantees = state.pending_guarantees
            state.pending_guarantees = None
        self._pending_guarantee_count -= len(guarantees)
        return guarantees.values()

    def guarantees_discardable_on_destruction(
        self, has_destructor: typing.Callable[[particle_info.ParticleInfo], bool]
    ) -> bool:
        """Return whether this action's guarantees can be dropped unapplied when their particle is destroyed.

        That holds when no error is recorded, no particle this action created
        has a Destructor, and every pending Guarantee can itself be dropped.
        """
        for error in self._error.values():
            if error.caused_by is not None:
                return False
        for pending in self._root_pending_guarantees.values():
            if not pending.contract.guarantees_discardable_on_destruction:
                return False
        for state in self._state.values():
            if not isinstance(state, _PositionNodeState):
                continue
            particle = state.particle_info
            # A particle from the caller is already known to whoever destroys
            # it, so it adds nothing here.
            if (
                particle is not None
                and not particle.from_caller
                and has_destructor(particle)
            ):
                return False
            if state.pending_guarantees is None:
                continue
            for pending in state.pending_guarantees.values():
                if not pending.contract.guarantees_discardable_on_destruction:
                    return False
        return True

    def pending_prefixes_at_or_below(
        self, key: chained_name.ChainedNameTuple
    ) -> list[chained_name.ChainedNameTuple]:
        """Return each name at or below ``key`` with pending Guarantees, parent names first."""
        prefixes: list[chained_name.ChainedNameTuple] = []
        found: list[chained_name.ChainedNameTuple] = []
        if not key:
            if self._root_pending_guarantees:
                prefixes.append(key)
            for candidate_key, state in self._state.items():
                if isinstance(state, _PositionNodeState) and state.pending_guarantees:
                    found.append(candidate_key)
        else:
            if self._has_stored_pending_guarantees(key):
                found.append(key)
            for child_key in self._state.subtree_keys(key):
                if self._has_stored_pending_guarantees(child_key):
                    found.append(child_key)
        # Results above a particle must be applied before results below it,
        # because applying them can change or replace what is below. The trie
        # does not keep its keys in that order, since moves reinsert them.
        found.sort(key=len)
        prefixes.extend(found)
        return prefixes

    def _has_stored_pending_guarantees(
        self, key: chained_name.ChainedNameTuple
    ) -> bool:
        state = self._state[key]
        return isinstance(state, _PositionNodeState) and bool(state.pending_guarantees)

    def mark_unchanged(self, key: chained_name.PositionReferenceTuple):
        """Record that a callee left a Position unchanged, tracking it with unknown occupancy if it has no state."""
        if key not in self._state:
            self._state[key] = _PositionNodeState()

    def ensure_action_parent(self, key: chained_name.PositionReferenceTuple):
        """Ensure the action name preceding the position has tracker state."""
        if len(key) >= 2 and chained_name.is_action_key(key[-2]):
            parent_key = chained_name.parent(key)
            if parent_key not in self._state:
                # This is the other repeated allocation from the default
                # action-graph full-compiler experiment documented in
                # try_add_action_parent: replacing both paths' fresh
                # _ActionNodeState values with one shared object showed no
                # measurable wall-time change.
                self._state[parent_key] = _ActionNodeState()

    def delete_subtree(
        self,
        key: chained_name.PositionReferenceTuple,
        removed_particle_callback: typing.Callable[[particle_info.ParticleInfo], None],
    ):
        """Delete everything tracked at or below a Position, passing each removed particle to ``removed_particle_callback``."""

        def call_with_removed_particle(state: _NodeState):
            if (
                isinstance(state, _PositionNodeState)
                and state.particle_info is not None
            ):
                removed_particle_callback(state.particle_info)

        if key in self._state:
            self._state.delete_subtree(
                key, removed_value_callback=call_with_removed_particle
            )
        if key in self._error:
            self._error.delete_subtree(key)

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
                detached_state[chained_name.last_name(from_key)],
                restored_value_callback=self._wrap_moved_particle_callback(
                    moved_particle_callback
                ),
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
                to_key, detached_error, detached_error[chained_name.last_name(from_key)]
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
            if (
                isinstance(state, _PositionNodeState)
                and state.particle_info is not None
            ):
                moved_particle_callback(
                    chained_name.position(position), state.particle_info
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

    def record_triggered_action(
        self,
        action_chain: chained_name.ActionReferenceTuple,
        execution: codegen_input.ActionExecution,
        contract: action_contract.ActionContract,
    ):
        """Record an Action Execution whose nested guarantees this action's contract carries."""
        state = self._action_state(action_chain)
        # A constructor or destructor triggers without a trigger position, so
        # nothing may have tracked its action name yet.
        if state is None:
            state = _ActionNodeState()
            self._state[action_chain] = state
        state.triggered_executions.append(execution)
        self._triggered_contracts[execution] = contract

    def nested_guarantees(self) -> list[action_contract.CalleeContract]:
        """Return the guarantees of actions this action triggered, in triggering order."""
        action_chains: dict[
            codegen_input.ActionExecution, chained_name.ActionReferenceTuple
        ] = {}
        for key, state in self._state.items():
            if not isinstance(state, _ActionNodeState):
                continue
            for execution in state.triggered_executions:
                action_chains[execution] = chained_name.action(key)
        callees: list[action_contract.CalleeContract] = []
        # Executions deleted with their particle are no longer in the state.
        for execution, contract in self._triggered_contracts.items():
            action_chain = action_chains.get(execution)
            if action_chain is not None:
                callees.append(action_contract.CalleeContract(action_chain, contract))
        return callees

    def unconsumed_action_interfaces(
        self,
    ) -> Iterator[
        tuple[ast.GlobalTypedNameReference, chained_name.PositionReferenceTuple]
    ]:
        """Yield occupied interfaces of callees directly triggered by this action."""
        for key, action_state in self._state.items():
            if (
                not isinstance(action_state, _ActionNodeState)
                or not action_state.triggered_executions
            ):
                continue
            action_chain = chained_name.action(key)
            action = action_state.triggered_executions[-1].action.get_last_action()
            if self.has_error_in_chain(action_chain):
                continue
            for child_key, state in self._state.direct_child_items(action_chain):
                # An action's child names are its interface positions.
                position = chained_name.position(child_key)
                particle = typing.cast("_PositionNodeState", state).particle_info
                if particle is None or self.has_error_at(position):
                    continue
                yield action, position

    def longest_occupied_prefix(
        self, key: chained_name.PositionReferenceTuple
    ) -> chained_name.PositionReferenceTuple | None:
        """Return the longest prefix of ``key`` that holds a particle, if any."""
        prefix = self._state.find_longest_prefix_where(key, _node_is_occupied)
        # Only positions hold particles.
        return None if prefix is None else chained_name.position(prefix)

    def error_caused_by(
        self, key: chained_name.PositionReferenceTuple
    ) -> ast.PositionReference | None:
        """Return what caused this exact Position's error occupancy state, if it has one."""
        state = self._error.get(key)
        return state.caused_by if state is not None else None

    def is_occupied(self, key: chained_name.PositionReferenceTuple) -> bool:
        """Return whether a particle is known to exist at this position."""
        state = self._position_state(key)
        return state is not None and state.particle_info is not None

    def occupant(
        self, key: chained_name.PositionReferenceTuple
    ) -> particle_info.ParticleInfo:
        """Return the particle at this position, raising KeyError if it is empty."""
        state = self._position_state(key)
        if state is None or state.particle_info is None:
            raise KeyError(key)
        return state.particle_info

    def occupant_or_none(
        self, key: chained_name.PositionReferenceTuple
    ) -> particle_info.ParticleInfo | None:
        """Return the particle at this position, or None if it is empty."""
        state = self._position_state(key)
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
        # Another contract can describe a child particle with an independent
        # origin after a Move. Its own caller knowledge must determine that
        # particle's Child State, not the old contents of this caller position.
        for state_position, node in self._state.pruned_subtree_items(
            key,
            key_prefix=position_in_child_state,
            excluded_keys=contract_positions,
        ):
            if not isinstance(node, _PositionNodeState):
                continue
            particle = node.particle_info
            if particle is not None:
                caller_position_key = chained_name.replace_prefix(
                    state_position, position_in_child_state, key
                )
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
        state = self._position_state(key)
        return state.emptied_by if state is not None else None

    def has_known_occupancy(self, key: chained_name.PositionReferenceTuple) -> bool:
        """Return whether the Position is known to be occupied or empty."""
        state = self._position_state(key)
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
            ancestor_position = chained_name.position(ancestor_key)
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
            if not isinstance(state, _PositionNodeState):
                continue
            position = chained_name.position(key)
            if (state.particle_info is not None or state.emptied_by is not None) and (
                include_callee_derived or self._include_in_own_guarantees(position)
            ):
                keys.add(position)
        for key, error_state in self._error.items():
            position = chained_name.position(key)
            if error_state.caused_by is not None and (
                include_callee_derived or self._include_in_own_guarantees(position)
            ):
                keys.add(position)
        return keys

    def is_superseded(
        self,
        key: chained_name.PositionReferenceTuple,
        execution: codegen_input.ActionExecution,
        depth: int,
    ) -> bool:
        """Return whether a shallower guarantee from the same Action Execution already decided this key."""
        existing = self._write_record.get(key)
        if existing is None:
            return False
        # Guarantees from different Action Executions need no ordering here:
        # before anything writes below an earlier execution's pending
        # Guarantees, a requirement check, a Destruction Contract's resolution,
        # or the destruction walk applies or drops them.
        return (
            isinstance(existing, _CalleeWriteRecord)
            and existing.execution is execution
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

    def record_write(self, key: chained_name.PositionReferenceTuple):
        """Record a state write from the action body, whose Guarantee this action publishes itself."""
        self._write_record[key] = _BODY_WRITE

    def record_callee_write(
        self,
        key: chained_name.PositionReferenceTuple,
        execution: codegen_input.ActionExecution,
        depth: int,
        *,
        include_in_own_guarantees: bool,
    ):
        """Record that a callee's contract authored ``key``."""
        self._write_record[key] = _CalleeWriteRecord(
            include_in_own_guarantees=include_in_own_guarantees,
            execution=execution,
            depth=depth,
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
        parent_key = chained_name.parent(key)
        if not parent_key or parent_key in self._state:
            return None
        # The parent name is absent, so the invariant above says nothing about
        # the rest of the chain and the grandparent has to be probed too.
        grandparent_key = chained_name.parent(parent_key)
        if not grandparent_key or grandparent_key in self._state:
            # The parent name is the only absent one. A strict trie refuses a
            # write whose own parent name is missing, so this is the only case
            # where the compiler may add a tracker entry for an action name. Any
            # other absent parent name is a position the caller never filled.
            if chained_name.is_action_key(parent_key[-1]):
                # Repeated _ActionNodeState construction for action-name trie
                # keys looked costly in the default action-graph full-compiler
                # benchmark. An August 2026 experiment replaced every fresh value
                # here and in ensure_action_parent with one shared value;
                # unprofiled runs showed no measurable wall-time change.
                self._state[parent_key] = _ActionNodeState()
                return None
            return chained_name.position(parent_key)
        # Two or more names are absent, so only a walk can say which of them the
        # caller left unfilled first.
        first_missing_index = len(self._state.existing_prefix(key))
        # An action name never holds a particle, so the position after it is the
        # one the caller left unfilled.
        if chained_name.is_action_key(key[first_missing_index]):
            first_missing_index += 1
        return chained_name.position(key[: first_missing_index + 1])

    def _rekey_records_for_move(
        self,
        from_key: chained_name.PositionReferenceTuple,
        to_key: chained_name.PositionReferenceTuple,
    ):
        """Relocate the moved subtree's write records to follow a state move.

        Must run after the state subtree has moved to ``to_key``: it mirrors that
        move.
        """
        for new_key in self._state.subtree_keys(to_key):
            record = self._write_record.pop(
                chained_name.replace_prefix(new_key, to_key, from_key), None
            )
            if record is not None:
                self._write_record[new_key] = record
