"""Store the state of each Position an action tracks."""

from __future__ import annotations

import typing

import msgspec

from define.compiler import chained_name
from define.compiler.data_structures import trie
from define.compiler.validator.reference_graph import (
    action_contract,
    position_occupancy,
)
from define.compiler.validator.reference_graph.particles import particle_info

if typing.TYPE_CHECKING:
    from collections.abc import Collection, Iterator, Sequence
    from collections.abc import Set as AbstractSet

    from define.compiler import ast


class OccupancyInfo(msgspec.Struct, frozen=True):
    """A position's error state and occupant, resolved together in one lookup."""

    # When an ancestor is in an error condition we ignore the position entirely,
    # so the occupant is meaningless and left None.
    has_error: bool
    occupant: particle_info.ParticleInfo | None


class PositionState(msgspec.Struct):
    """Everything the store knows about one position.

    A parent name with no state of its own, such as an action name or a
    position the caller never filled, has a state with nothing set. Only the
    store changes it.
    """

    particle: particle_info.ParticleInfo | None = None
    emptied_by: ast.PositionReference | None = None
    # Whether this position's occupancy is unknowable. It wins over a
    # particle or emptied state that is also recorded.
    has_error: bool = False
    # Whether this position or any position above it has error state.
    is_in_error_chain: bool = False
    # The Move or trigger in this action that put the particle here, or put
    # a particle above it in place since. None where the particle's
    # last_position already says so.
    placed_here_by: ast.SourceLocation | None = None
    # What a callee left in the child positions of the new particle here,
    # which this action has not expanded. A node with this has no child
    # nodes.
    unexpanded: action_contract.ChildPositionParticles | None = None

    def child_occupancy(self) -> position_occupancy.ChildOccupancy | None:
        """Return this position's occupancy as Child State records it, or None when nothing about it is known."""
        if self.has_error:
            return position_occupancy.ERROR_OCCUPANCY
        if self.particle is not None:
            return position_occupancy.ChildOccupancy(
                position_occupancy.PositionOccupancyState.OCCUPIED,
                filled_at=self.particle.last_position.location,
            )
        if self.emptied_by is not None:
            return position_occupancy.EMPTY_OCCUPANCY
        return None

    def child_value(self) -> particle_info.ParticleValueState | None:
        """Return the value state of this position's particle as Child State records it, or None when it has none."""
        particle = self.particle
        if particle is None or particle.qualities.value_type is None:
            return None
        return particle.value_state


def _node_is_occupied(state: PositionState) -> bool:
    return state.particle is not None


def _state_in_map(
    particles: action_contract.ChildPositionParticles,
    names: tuple[str, ...],
) -> tuple[
    position_occupancy.PositionOccupancyState, particle_info.ParticleValueState | None
]:
    """Return the occupancy and value state at ``names``, below the particle that ``particles``, what a callee left below it, belongs to."""
    # Interface positions of actions on the particle are never in its map:
    # they are empty when the action that left the particle ends.
    left = particles.particle_left_below(names)
    if left is None:
        return position_occupancy.PositionOccupancyState.EMPTY, None
    guarantee = left.guarantee
    if isinstance(guarantee, action_contract.ErrorGuarantee):
        return position_occupancy.PositionOccupancyState.ERROR, None
    return (
        position_occupancy.PositionOccupancyState.OCCUPIED,
        guarantee.value_effect,
    )


def _action_parent_position_key(
    action: ast.ActionReference,
) -> chained_name.ChainedNameTuple:
    """Return the key of the action parent position of ``action``, or of this action's parent particle when ``action`` has no action parent position."""
    action_parent_position = action.parent_position()
    if action_parent_position is None:
        return chained_name.ACTION_PARENT_PARTICLE
    return action_parent_position.canonical_chained_name_tuple


def _new_particle(
    guarantee: action_contract.OccupiedByNewGuarantee, written_at: ast.SourceLocation
) -> particle_info.ParticleInfo:
    particle = particle_info.ParticleInfo(
        last_position=guarantee.caused_by,
        qualities=guarantee.qualities,
        origin_position=guarantee.origin_position,
        source=particle_info.ParticleSource.CALLEE,
    )
    particle.set_value_state(guarantee.value_effect, written_at)
    return particle


class ParticleStateStore:
    """Tracks the state of every Position an action has touched.

    A Position can have an error condition: the compiler detected a problem
    but continues validation to find other errors. We ignore Positions in
    error states to avoid cascading diagnostics.

    A callee's Guarantees are applied when it is triggered. What a callee left
    below a new particle stays on the particle's node, unexpanded, until
    something reads or writes below the particle.
    """

    def __init__(self):
        """Initialize a store that tracks no Positions."""
        self._state: trie.ReparentingTrie[PositionState] = trie.ReparentingTrie(
            default_factory=PositionState
        )
        # Set the first time any position gets error state, and never
        # cleared, so that programs without errors skip every error check.
        self._has_any_error: bool = False
        # Set the first time any node gets something unexpanded, and never
        # cleared, so that a position without a node needs no search for a
        # map above it until then.
        self._has_unexpanded: bool = False
        # Where this action last triggered each callee it triggered directly,
        # by the callee's parent particle (None for this action's parent
        # particle) and its name. A Move of the parent particle needs no
        # renaming here.
        self._triggered: dict[
            tuple[particle_info.ParticleInfo | None, str], ast.SourceLocation
        ] = {}

    def _node(self, key: chained_name.ChainedNameTuple) -> PositionState | None:
        """Return the node of ``key``, if it has one, after expanding what callees left above it."""
        node = self._state.get(key)
        if node is not None or not self._has_unexpanded:
            return node
        prefix = self._state.existing_prefix(key)
        node = self._state[prefix]
        length = len(prefix)
        while node.unexpanded is not None:
            self._expand(prefix, node)
            length += 1
            prefix = chained_name.ChainedNameTuple(key[:length])
            child = self._state.get(prefix)
            if child is None or length == len(key):
                return child
            node = child
        return None

    def _expand(self, key: chained_name.ChainedNameTuple, node: PositionState):
        """Give each particle a callee left in the child positions of ``key`` its own node."""
        particles = typing.cast(
            "action_contract.ChildPositionParticles", node.unexpanded
        )
        node.unexpanded = None
        # A node gets something unexpanded only from a Move or trigger, which
        # also sets where it was placed.
        placed_here_by = typing.cast("ast.SourceLocation", node.placed_here_by)
        for name, left in particles.particles.items():
            guarantee = left.guarantee
            child = PositionState(
                placed_here_by=placed_here_by,
                is_in_error_chain=node.is_in_error_chain,
            )
            if isinstance(guarantee, action_contract.ErrorGuarantee):
                child.has_error = True
                child.is_in_error_chain = True
                self._has_any_error = True
            else:
                child.particle = _new_particle(guarantee, placed_here_by)
                child.unexpanded = guarantee.left_in_child_positions
            self._state[chained_name.ChainedNameTuple((*key, name))] = child

    def _has_error_above(self, key: chained_name.ChainedNameTuple) -> bool:
        """Return whether a position above ``key`` has error state, from the recorded state."""
        if not self._has_any_error:
            return False
        # Every position above a node has a node, and each node knows whether
        # a position at or above it has error state.
        parent = self._state.existing_prefix(chained_name.ChainedNameTuple(key[:-1]))
        return self._state[parent].is_in_error_chain

    def _put(
        self, key: chained_name.PositionReferenceTuple, node: PositionState
    ) -> PositionState:
        """Give a Position a new node, keeping only the error state it had, and return the node."""
        replaced = self._state.get(key)
        if replaced is not None:
            # Only deleting what is in the position clears its error state.
            node.has_error = replaced.has_error
        is_below_error = self._has_error_above(key)
        node.is_in_error_chain = node.has_error or is_below_error
        self._state[key] = node
        if is_below_error:
            # Setting the node can have created the positions above it, up to
            # the one with error state.
            length = len(key) - 1
            above = self._state[chained_name.ChainedNameTuple(key[:length])]
            while not above.is_in_error_chain:
                above.is_in_error_chain = True
                length -= 1
                above = self._state[chained_name.ChainedNameTuple(key[:length])]
        return node

    def _mark_error(self, key: chained_name.PositionReferenceTuple) -> PositionState:
        """Give a Position error occupancy state, and return its node."""
        self._has_any_error = True
        node = self._state.get(key)
        if node is None:
            node = self._put(key, PositionState(has_error=True))
        else:
            node.has_error = True
        node.is_in_error_chain = True
        for _, below in self._state.subtree_values_with_parents(key):
            below.is_in_error_chain = True
        return node

    def _clear(self, key: chained_name.PositionReferenceTuple):
        """Remove whatever is recorded at or below a Position that is about to get a new state, if anything is."""
        if key in self._state:
            self._state.delete_subtree(key)

    def _placed(self, key: chained_name.PositionReferenceTuple, by: ast.SourceLocation):
        """Record that a Move or trigger put the particle in ``key`` and what is below it in place."""
        node = self._state[key]
        node.placed_here_by = by
        if self._has_any_error:
            node.is_in_error_chain = node.has_error or self._has_error_above(key)
        # Each parent position comes before its child positions.
        for parent, child in self._state.subtree_values_with_parents(key):
            child.placed_here_by = by
            if self._has_any_error:
                child.is_in_error_chain = child.has_error or parent.is_in_error_chain

    def occupied_positions_past_an_action(
        self,
        action: ast.ActionReference,
        implied_quality_names: Collection[str],
    ) -> list[tuple[chained_name.PositionReferenceTuple, ast.SourceLocation]]:
        """Return each occupied position that has an action in its chained name below a callee's interface positions or below what the callee implies, with where in this action its particle got there.

        ``action`` is the callee's reference and ``implied_quality_names`` are
        the qualities it transitively implies. An implied action's own name
        counts as the action. Positions with error occupancy state are left
        out, and so is every position below one that is returned.
        """
        action_chain = action.canonical_chained_name_tuple
        action_parent_position = _action_parent_position_key(action)
        # Each chained name still to visit, and whether it has an action in it
        # that counts. A callee never leaves a particle past an action below a
        # new particle, so what is unexpanded is not visited.
        pending: list[tuple[chained_name.ChainedNameTuple, bool]] = []
        # The callee's own interface positions are what the caller passes it.
        # Only another action's interface positions below them may not hold a
        # particle.
        for interface_position in self._state.child_keys(action_chain):
            pending.append((interface_position, False))
        for quality_name in implied_quality_names:
            implied_chained_name = chained_name.ChainedNameTuple(
                (*action_parent_position, quality_name)
            )
            pending.append((implied_chained_name, False))
        occupied: list[
            tuple[chained_name.PositionReferenceTuple, ast.SourceLocation]
        ] = []
        while pending:
            key, is_past_action = pending.pop()
            if chained_name.is_action_key(key[-1]):
                for interface_position in self._state.child_keys(key):
                    pending.append((interface_position, True))
                continue
            node = self._state.get(key)
            if node is None:
                continue
            if is_past_action:
                # Removing this particle removes everything below it, so
                # nothing below it is visited.
                particle = node.particle
                if particle is not None and not node.is_in_error_chain:
                    occupied.append(
                        (
                            chained_name.position(key),
                            node.placed_here_by or particle.last_position.location,
                        )
                    )
                continue
            for child_key in self._state.child_keys(key):
                pending.append((child_key, False))
        return occupied

    def unconsumed_action_interfaces(
        self,
    ) -> Iterator[tuple[ast.SourceLocation, chained_name.PositionReferenceTuple]]:
        """Yield each occupied interface position of a callee directly triggered by this action, with where the callee was last triggered."""
        for key, node in self._state.items():
            if not key or not chained_name.is_action_key(key[-1]):
                continue
            parent_particle = (
                self._state[chained_name.ChainedNameTuple(key[:-1])].particle
                if len(key) > 1
                else None
            )
            triggered_at = self._triggered.get((parent_particle, key[-1]))
            if triggered_at is None or node.is_in_error_chain:
                continue
            for child_key, state in self._state.direct_child_items(key):
                # An action's child names are its interface positions.
                if state.particle is None or state.has_error:
                    continue
                yield triggered_at, chained_name.position(child_key)

    def longest_occupied_prefix(
        self, key: chained_name.PositionReferenceTuple
    ) -> chained_name.PositionReferenceTuple | None:
        """Return the longest prefix of ``key`` that holds a particle, if any."""
        _ = self._node(key)
        prefix = self._state.find_longest_prefix_where(key, _node_is_occupied)
        # Only positions hold particles.
        return None if prefix is None else chained_name.position(prefix)

    def state_at(self, key: chained_name.PositionReferenceTuple) -> PositionState:
        """Return the state of ``key``, which must have state, expanding what callees left above it. Only the store may change it."""
        return typing.cast("PositionState", self._node(key))

    def transitive_child_states(
        self, key: chained_name.PositionReferenceTuple
    ) -> Iterator[tuple[chained_name.ChainedNameTuple, PositionState]]:
        """Yield a ``(names after key, state)`` pair for every transitive child position of ``key`` that has state, where ``key`` has state already. Only the store may change the yielded states."""
        return self._state.descendant_items(key)

    def transitive_child_states_except(
        self,
        key: chained_name.PositionReferenceTuple,
        *,
        prefix_for_returned_keys: chained_name.ChainedNameTuple,
        excluded_keys: AbstractSet[chained_name.ChainedNameTuple],
    ) -> Iterator[tuple[chained_name.ChainedNameTuple, PositionState]]:
        """Yield a ``(returned key, state)`` pair for every transitive child position of ``key`` that has state, where ``key`` has state already.

        Each returned key is ``prefix_for_returned_keys`` followed by the
        child position's names after ``key``. A child position whose returned
        key is in ``excluded_keys`` is skipped with all of its own transitive
        child positions. Only the store may change the yielded states.
        """
        return self._state.descendant_items_except(
            key,
            prefix_for_returned_keys=prefix_for_returned_keys,
            excluded_keys=excluded_keys,
        )

    def state_without_expanding(
        self, key: chained_name.PositionReferenceTuple
    ) -> tuple[
        position_occupancy.PositionOccupancyState,
        particle_info.ParticleValueState | None,
    ]:
        """Return the occupancy and value state of a Position whose state is known, reading what callees left without expanding it."""
        node = self._state.get(key)
        if node is None:
            prefix = self._state.existing_prefix(key)
            above = self._state[prefix]
            if above.is_in_error_chain:
                return position_occupancy.PositionOccupancyState.ERROR, None
            if above.unexpanded is not None:
                return _state_in_map(above.unexpanded, key[len(prefix) :])
            return position_occupancy.PositionOccupancyState.EMPTY, None
        if node.is_in_error_chain:
            return position_occupancy.PositionOccupancyState.ERROR, None
        particle = node.particle
        if particle is None:
            return position_occupancy.PositionOccupancyState.EMPTY, None
        return position_occupancy.PositionOccupancyState.OCCUPIED, particle.value_state

    def has_known_occupancy_or_error(
        self, key: chained_name.PositionReferenceTuple
    ) -> bool:
        """Return whether the Position is known to be occupied or empty, or it or a position above it has error occupancy state."""
        node = self._node(key)
        if node is None:
            return self._has_error_above(key)
        return (
            node.particle is not None
            or node.emptied_by is not None
            or node.is_in_error_chain
        )

    def nearest_occupied_ancestors(
        self, keys: Sequence[chained_name.PositionReferenceTuple]
    ) -> dict[
        chained_name.PositionReferenceTuple,
        tuple[chained_name.PositionReferenceTuple, particle_info.ParticleInfo] | None,
    ]:
        """Return the nearest occupied ancestor for each distinct key."""
        if self._has_unexpanded:
            for key in keys:
                _ = self._node(key)
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
            results[key] = (
                ancestor_position,
                typing.cast(
                    "particle_info.ParticleInfo", self._state[ancestor_key].particle
                ),
            )
        return results

    def positions_with_state(
        self,
    ) -> list[tuple[chained_name.PositionReferenceTuple, PositionState]]:
        """Return every position that is occupied, known-empty, or marked error, with its state."""
        # Only positions hold a particle, emptied state, or error state.
        positions: list[tuple[chained_name.PositionReferenceTuple, PositionState]] = []
        for key, state in self._state.items():
            if (
                state.particle is not None
                or state.emptied_by is not None
                or state.has_error
            ):
                positions.append((chained_name.position(key), state))
        return positions

    def unexpanded_child_positions(
        self, key: chained_name.PositionReferenceTuple
    ) -> action_contract.ChildPositionParticles | None:
        """Return what a callee left in the child positions of the particle in ``key`` that this action never expanded."""
        return self._state[key].unexpanded

    def unexpanded_entry(
        self, key: chained_name.PositionReferenceTuple
    ) -> (
        tuple[
            action_contract.ChildPositionParticles,
            action_contract.ParticleLeftBelow | None,
        ]
        | None
    ):
        """Return what a callee left in ``key``, a child position, that this action never expanded: the map it is in, and its entry, which is None when the position is empty.

        None when this action has expanded what is at ``key``.
        """
        parent_position = typing.cast(
            "chained_name.PositionReferenceTuple", chained_name.parent_position(key)
        )
        parent = self._node(parent_position)
        if parent is None or parent.unexpanded is None:
            return None
        # Interface positions of actions on the particle are never in its map.
        if chained_name.is_action_key(key[-2]):
            return parent.unexpanded, None
        return parent.unexpanded, parent.unexpanded.particles.get(key[-1])

    def occupant(
        self, key: chained_name.PositionReferenceTuple
    ) -> particle_info.ParticleInfo:
        """Return the particle at this position, raising KeyError if it is empty."""
        node = self._node(key)
        if node is None or node.particle is None:
            raise KeyError(key)
        return node.particle

    def occupant_or_none(
        self, key: chained_name.PositionReferenceTuple
    ) -> particle_info.ParticleInfo | None:
        """Return the particle at this position, or None if it is empty."""
        node = self._node(key)
        return node.particle if node is not None else None

    def is_occupied(self, key: chained_name.PositionReferenceTuple) -> bool:
        """Return whether a particle is known to exist at this position."""
        node = self._node(key)
        return node is not None and node.particle is not None

    def occupancy_info(self, key: chained_name.PositionReferenceTuple) -> OccupancyInfo:
        """Return the error state and occupant of this position, from one lookup of its node."""
        node = self._node(key)
        if node is None:
            return OccupancyInfo(has_error=self._has_error_above(key), occupant=None)
        if node.is_in_error_chain:
            return OccupancyInfo(has_error=True, occupant=None)
        return OccupancyInfo(has_error=False, occupant=node.particle)

    def has_error_in_chain(self, key: chained_name.PositionReferenceTuple) -> bool:
        """Return whether this position or any ancestor has error occupancy state."""
        node = self._node(key)
        if node is None:
            return self._has_error_above(key)
        return node.is_in_error_chain

    def was_placed(self, key: chained_name.PositionReferenceTuple) -> bool:
        """Return whether a Move or trigger in this action put the particle in ``key``, or a particle above it, in place."""
        node = self._node(key)
        return node is not None and node.placed_here_by is not None

    def emptied_by(
        self, key: chained_name.PositionReferenceTuple
    ) -> ast.PositionReference | None:
        """Return the position reference that emptied this position, if it is known-empty."""
        node = self._node(key)
        return node.emptied_by if node is not None else None

    def mark_error(self, key: chained_name.PositionReferenceTuple):
        """Mark a Position as having error occupancy state, as an operation of the action body."""
        _ = self._node(key)
        _ = self._mark_error(key)

    def assume_empty(self, position: ast.PositionReference):
        """Record that a Position starts empty."""
        key = position.canonical_chained_name_tuple
        _ = self._node(key)
        _ = self._put(key, PositionState(emptied_by=position))

    def put_particle(
        self, key: chained_name.PositionReferenceTuple, info: particle_info.ParticleInfo
    ):
        """Record that a particle is in a Position, either when the action starts or because the action body created it."""
        _ = self._node(key)
        _ = self._put(key, PositionState(particle=info))

    def empty(self, position: ast.PositionReference):
        """Destroy the particle in a Position and everything below it, as an operation of the action body."""
        key = position.canonical_chained_name_tuple
        _ = self._node(key)
        # Destroying puts all children back into a known state (they don't
        # exist), and clears the target's error state.
        self._clear(key)
        _ = self._put(key, PositionState(emptied_by=position))

    def move(self, source: ast.PositionReference, target: ast.PositionReference):
        """Move a particle and everything below it to another Position, as an operation of the action body."""
        from_key = source.canonical_chained_name_tuple
        to_key = target.canonical_chained_name_tuple
        _ = self._node(from_key)
        _ = self._node(to_key)
        # The target may already exist as an empty node (previously
        # destroyed), and its child positions may have error state. Whatever
        # was below the target no longer exists, so delete it before moving.
        self._clear(to_key)
        # Neither position has error state itself, but their child positions
        # can. The particle's children keep their unknown state as they move,
        # and what is unexpanded below it moves with it.
        self._state.move_subtree(from_key, to_key)
        self._placed(to_key, target.location)
        _ = self._put(from_key, PositionState(emptied_by=source))

    def trigger(
        self,
        action: ast.ActionReference,
        contract: action_contract.ActionContract,
        parent_particle: particle_info.ParticleInfo | None,
    ):
        """Record that this action triggered an action on a particle, and apply the action's Guarantees."""
        last_action = action.get_last_action()
        triggered_at = last_action.location
        self._triggered[(parent_particle, last_action.full_typed_name)] = triggered_at
        action_parent_position = _action_parent_position_key(action)
        guaranteed_keys: list[chained_name.PositionReferenceTuple] = []
        # Each particle from the caller that the callee moved leaves its
        # position before anything is put anywhere: the Guarantees name it by
        # where it was before the callee ran, and its destination can be
        # where another moved particle was.
        moved_to: list[
            tuple[
                chained_name.PositionReferenceTuple, chained_name.PositionReferenceTuple
            ]
        ] = []
        # Each position whose Guarantee replaces or moves what is below it.
        # A particle from the caller that stays where it is below one of
        # these leaves too, or it would go along with what is above it.
        replaced: set[chained_name.PositionReferenceTuple] = set()
        for guaranteed in contract.guarantees:
            destination = chained_name.position(
                (*action_parent_position, *guaranteed.position)
            )
            guaranteed_keys.append(destination)
            guarantee = guaranteed.guarantee
            if not isinstance(guarantee, action_contract.OccupiedByExistingGuarantee):
                replaced.add(destination)
                continue
            origin = guarantee.origin_position.in_caller(
                action
            ).canonical_chained_name_tuple
            if origin != destination:
                replaced.add(destination)
                moved_to.append((origin, destination))
            elif chained_name.parent_position(destination) in replaced:
                moved_to.append((origin, destination))
        # A particle moved out from below another moved particle leaves first,
        # so that it does not go along with the other one.
        moved_to.sort(key=lambda move: len(move[0]), reverse=True)
        moving: dict[
            chained_name.PositionReferenceTuple,
            tuple[PositionState, trie.DetachedSubtree[PositionState]] | None,
        ] = {}
        for origin, destination in moved_to:
            origin_node = self._node(origin)
            if origin_node is None or origin_node.particle is None:
                moving[destination] = None
            else:
                moving[destination] = (origin_node, self._state.pop_subtree(origin))
        for key, guaranteed in zip(guaranteed_keys, contract.guarantees, strict=True):
            self._apply_guarantee(key, guaranteed.guarantee, triggered_at, moving)

    def _apply_guarantee(
        self,
        key: chained_name.PositionReferenceTuple,
        guarantee: action_contract.PositionGuarantee,
        triggered_at: ast.SourceLocation,
        moving: dict[
            chained_name.PositionReferenceTuple,
            tuple[PositionState, trie.DetachedSubtree[PositionState]] | None,
        ],
    ):
        """Put ``key`` in the state a callee's Guarantee says it has.

        ``moving`` has the node and subtree of each particle from the caller
        taken out of the caller's state, by its destination, or None when the
        caller had no particle at its origin.
        """
        parent_position = chained_name.parent_position(key)
        if parent_position is not None:
            parent = self._node(parent_position)
            if parent is None or parent.particle is None:
                # For example, the caller triggers without filling
                # position<a>, but the callee moves from
                # position<a>::position</c1>. Requirement checking already
                # reported the missing particle; mark the parent as error so
                # later operations on it or its child positions do not
                # produce cascading diagnostics. A parent known to be empty
                # has nothing below it to change.
                if parent is None or (
                    parent.emptied_by is None and not parent.is_in_error_chain
                ):
                    _ = self._mark_error(parent_position)
                return
        node = self._node(key)
        if isinstance(guarantee, action_contract.OccupiedByExistingGuarantee):
            if key not in moving:
                if node is not None and node.particle is not None:
                    node.particle.set_value_state(guarantee.value_effect, triggered_at)
                return
            moved_entry = moving.pop(key)
            self._clear(key)
            if moved_entry is None:
                # The caller never filled the origin position, so the callee's
                # Move cannot supply a particle here.
                _ = self._mark_error(key)
                return
            moved_node, moved = moved_entry
            moved_particle = typing.cast(
                "particle_info.ParticleInfo", moved_node.particle
            )
            moved_particle.set_value_state(guarantee.value_effect, triggered_at)
            moved_particle.last_position = guarantee.caused_by
            # The destination keeps the particle's error state: the Guarantee
            # fills it with whatever was at the origin, including the
            # uncertainty.
            self._state.restore_subtree(key, moved)
            self._placed(key, triggered_at)
            return
        # Whatever the caller had at or below the position no longer exists.
        self._clear(key)
        match guarantee:
            case action_contract.EmptyGuarantee():
                _ = self._put(key, PositionState(emptied_by=guarantee.caused_by))
            case action_contract.OccupiedByNewGuarantee():
                unexpanded = guarantee.left_in_child_positions
                if unexpanded is not None:
                    self._has_unexpanded = True
                _ = self._put(
                    key,
                    PositionState(
                        particle=_new_particle(guarantee, triggered_at),
                        placed_here_by=triggered_at,
                        unexpanded=unexpanded,
                    ),
                )
            case action_contract.ErrorGuarantee():
                _ = self._mark_error(key)
            case _:
                raise TypeError(f"Unexpected guarantee type: {type(guarantee)}")
