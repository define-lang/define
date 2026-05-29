"""Tracks particle occupancy for positions within an action block."""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass

from define.compiler import ast
from define.compiler.data_structures import trie
from define.compiler.validator.reference_graph import action_contract


@dataclass(frozen=True, slots=True)
class ParticleInfo:
    """Information about a tracked particle."""

    # The last position reference written in the code for the last
    # statement that relocated or created this particle.
    last_position: ast.PositionReference
    # The qualities we know that this particle has, in
    # assignment order.
    qualities: tuple[ast.GlobalTypedNameReference, ...]
    # The position reference where this particle was first created.
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
class _UnknownState:
    """Wrapper for unknown-state trie values.

    LenientReparentingTrie can't use None as a value, so we wrap
    the caused_by reference in a dataclass.
    """

    caused_by: ast.PositionReference | None = None


_ACTION_KEY_PREFIX = f"{ast.NameType.ACTION.value}<"


class ParticleTracker:
    """Tracks which positions contain particles and what qualities those particles currently have.

    Pure data structure with no diagnostics logic.
    """

    def __init__(self):
        """Initialize an empty particle tracker."""
        self._state: trie.StrictReparentingTrie[_NodeState] = (
            trie.StrictReparentingTrie()
        )
        self._unknown: trie.LenientReparentingTrie[_UnknownState] = (
            trie.LenientReparentingTrie(default_factory=_UnknownState)
        )

    def _key(self, position: ast.PositionReference) -> tuple[str, ...]:
        """Compute the canonical tuple key for a position reference."""
        return position.canonical_chained_name_tuple

    def _ensure_action_parent(self, key: tuple[str, ...]):
        """Create the action intermediate trie node if needed."""
        if len(key) >= 2 and key[-2].startswith(_ACTION_KEY_PREFIX):
            parent_key = key[:-1]
            if parent_key not in self._state:
                self._state[parent_key] = _NodeState()

    def mark_unknown(self, in_position: ast.PositionReference):
        """Mark a position as having unknown occupancy state."""
        self._unknown[self._key(in_position)] = _UnknownState(caused_by=in_position)

    def mark_empty(self, in_position: ast.PositionReference):
        """Mark a position as known-empty without a prior particle existing."""
        key = self._key(in_position)
        if key in self._state:
            raise ValueError(f"position {key} already has tracker state")
        self._ensure_action_parent(key)
        self._state[key] = _NodeState(emptied_by=in_position)

    def has_unknown_state(self, in_position: ast.PositionReference) -> bool:
        """Return whether a position or any ancestor has unknown occupancy state."""
        return self.has_unknown_state_by_key(self._key(in_position))

    def has_unknown_state_by_key(self, key: tuple[str, ...]) -> bool:
        """Return whether a position or any ancestor has unknown occupancy state."""
        return (
            self._unknown.find_shortest_prefix_where(
                key, lambda state: state.caused_by is not None
            )
            is not None
        )

    def is_occupied(self, in_position: ast.PositionReference) -> bool:
        """Return whether a particle exists at this position."""
        return self.is_occupied_by_key(self._key(in_position))

    def is_occupied_by_key(self, key: tuple[str, ...]) -> bool:
        """Return whether a particle exists at this position, by raw key."""
        state = self._state.get(key)
        return state is not None and state.particle_info is not None

    def has_been_touched(self, key: tuple[str, ...]) -> bool:
        """Return whether a guarantee or particle statement has decided this position's state."""
        state = self._state.get(key)
        if state is None:
            return False
        return state.particle_info is not None or state.emptied_by is not None

    def get_occupant(self, in_position: ast.PositionReference) -> ParticleInfo:
        """Return the info for the particle at this position."""
        return self.get_occupant_by_key(self._key(in_position))

    def get_occupant_by_key(self, key: tuple[str, ...]) -> ParticleInfo:
        """Return the info for the particle at this position, by raw key."""
        state = self._state[key]
        if state.particle_info is None:
            raise KeyError(key)
        return state.particle_info

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
        self.create_by_key(
            self._key(in_position), in_position, qualities, from_caller=from_caller
        )

    # TODO: The docstring here no longer makes sense now that AST nodes
    # resolve their own FQUN.
    def create_by_key(
        self,
        key: tuple[str, ...],
        position: ast.PositionReference,
        qualities: tuple[ast.GlobalTypedNameReference, ...],
        *,
        from_caller: ast.PositionReference | None = None,
    ):
        """Record a new particle using an explicit canonical key.

        Use this instead of create() when the position's typed names contain
        cross-universe relative references that would resolve incorrectly
        against the tracker's own FQUN.
        """
        self._ensure_action_parent(key)
        existing = self._state.get(key)
        if existing is not None and existing.particle_info is not None:
            raise ValueError(f"position {key} is already occupied")
        info = ParticleInfo(
            last_position=position,
            qualities=qualities,
            origin_position=from_caller if from_caller is not None else position,
            from_caller=from_caller is not None,
        )
        if existing is not None:
            existing.particle_info = info
            existing.emptied_by = None
        else:
            self._state[key] = _NodeState(particle_info=info)

    def destroy(self, in_position: ast.PositionReference):
        """Remove a particle from this position.

        Raises ValueError if the position is not occupied.
        """
        self._destroy_by_key(self._key(in_position), in_position)

    def _destroy_by_key(self, key: tuple[str, ...], position: ast.PositionReference):
        existing = self._state.get(key)
        if existing is None or existing.particle_info is None:
            raise ValueError(f"position {key} is not occupied")
        del self._state[key]
        # Destroying puts all children back into a known state (they don't exist).
        if key in self._unknown:
            del self._unknown[key]
        self._state[key] = _NodeState(emptied_by=position)

    def get_emptied_by(
        self, ref: ast.PositionReference
    ) -> ast.PositionReference | None:
        """Return the position reference that emptied this position, if any."""
        return self.get_emptied_by_key(self._key(ref))

    def get_emptied_by_key(self, key: tuple[str, ...]) -> ast.PositionReference | None:
        """Return the position reference that emptied this position, by raw key."""
        state = self._state.get(key)
        if state is None:
            return None
        return state.emptied_by

    def move(self, source: ast.PositionReference, target: ast.PositionReference):
        """Move a particle from one position to another.

        Children of the source position move with it. After the move,
        the source position is marked as emptied.
        """
        from_key = self._key(source)
        to_key = self._key(target)
        if self.has_unknown_state_by_key(from_key) or self.has_unknown_state_by_key(
            to_key
        ):
            raise RuntimeError(
                f"cannot move between positions with unknown state: {from_key} -> {to_key}"
            )
        self._ensure_action_parent(to_key)
        # TODO: Move last_position into _NodeState so that move_subtree
        # doesn't need this post-move fixup.
        moved_info = self._state[from_key].particle_info
        if moved_info is not None:
            moved_info = moved_info.move_to(target)

        to_state = self._state.get(to_key)
        if to_state is not None:
            # This should never happen, it's just a defensive check.
            if to_state.particle_info is not None:
                raise ValueError(f"destination position {to_key} is already occupied")
            # The target may already exist as an empty node (previously
            # destroyed). Delete it before moving so move_subtree succeeds.
            del self._state[to_key]
        self._state.move_subtree(from_key, to_key)
        self._state[to_key].particle_info = moved_info
        self._state[from_key] = _NodeState(emptied_by=source)

    def generate_guarantees(
        self,
        interface_names: tuple[ast.TypedName, ...],
        implied_quality_names: tuple[ast.GlobalTypedNameReference, ...],
        requirements: dict[tuple[str, ...], action_contract.PositionRequirement],
    ) -> list[action_contract.GuaranteePair]:
        """Generate guarantees for keys whose first element matches an interface or implied quality.

        ``requirements`` is the validator's inferred-requirements dict. A
        position whose requirement is EMPTY started empty, so an end-state
        EmptyGuarantee on it would be a no-op and is skipped here.
        """
        include_names = {
            name.full_typed_name for name in (*interface_names, *implied_quality_names)
        }

        # Collect keys that have interesting state from both tries.
        all_keys: set[tuple[str, ...]] = set()
        for key, state in self._state.items():
            if state.particle_info is not None or state.emptied_by is not None:
                all_keys.add(key)
        for key, unknown_state in self._unknown.items():
            if unknown_state.caused_by is not None:
                all_keys.add(key)

        guarantees: list[action_contract.GuaranteePair] = []
        for key in all_keys:
            first_element = key[0]
            if first_element not in include_names:
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
        or an empty position that was already inferred-empty at the start.
        """
        unknown_state = self._unknown.get(key)
        if unknown_state is not None and unknown_state.caused_by is not None:
            return action_contract.UnknownGuarantee(caused_by=unknown_state.caused_by)
        state = self._state.get(key)
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
        ):
            return None
        return action_contract.EmptyGuarantee(caused_by=caused_by)

    def apply_guarantees(
        self,
        for_position: ast.PositionReference,
        guarantees: list[action_contract.GuaranteePair],
    ):
        """Apply guarantees after an action completes or a quality is assigned.

        Interface-position keys (local names) get prefixed with the full
        action chain. Implied-quality keys (global names) get prefixed
        with the name of the action's parent in the caller.
        For position init blocks, both prefixes collapse to ``for_position``.

        ``guarantees`` is expected pre-sorted by ``generate_guarantees`` into
        parent-before-child / execution order.
        """
        action_chain = for_position.get_chain_to_last_action()
        if action_chain is not None:
            interface_prefix = action_chain.canonical_chained_name_tuple
            implied_prefix = interface_prefix[:-1]
        else:
            # Position Init Block
            interface_prefix = for_position.canonical_chained_name_tuple
            implied_prefix = interface_prefix

        # Make a list of only the origin_positions for OccupiedByExistingGuarantee.
        # We need this list later to know what to "save" before we apply guarantees.
        origin_keys: set[tuple[str, ...]] = set()
        for _name, guarantee in guarantees:
            if isinstance(guarantee, action_contract.OccupiedByExistingGuarantee):
                origin_tuple = guarantee.origin_position.canonical_chained_name_tuple
                if ast.chain_starts_with_global(origin_tuple):
                    origin_keys.add(implied_prefix + origin_tuple)
                else:
                    origin_keys.add(interface_prefix + origin_tuple)

        # Saved subtrees for swap safety. Keyed by the origin's full key.
        saved_state: dict[tuple[str, ...], trie.StrictReparentingTrie[_NodeState]] = {}
        saved_unknown: dict[
            tuple[str, ...], trie.StrictReparentingTrie[_UnknownState]
        ] = {}

        for name, guarantee in guarantees:
            key = (
                implied_prefix + name
                if ast.chain_starts_with_global(name)
                else interface_prefix + name
            )

            if not self._check_key_exists_for_guarantee(key, guarantee):
                continue

            self._ensure_action_parent(key)

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
                if key in self._state:
                    saved_state[key] = self._state.pop_subtree(key)
                if key in self._unknown:
                    saved_unknown[key] = self._unknown.pop_subtree(key)
            elif key in self._state:
                # Subtree cleanup: If an action empties position<item> (EmptyGuarantee)
                # or creates in position<item> (OccupiedByNewGuarantee), any children
                # the caller had under position<item> must disappear. We achieve this
                # by deleting each key's entire subtree before applying its guarantee.
                del self._state[key]
                if key in self._unknown:
                    del self._unknown[key]

            match guarantee:
                case action_contract.OccupiedByExistingGuarantee():
                    self._apply_existing_guarantee(
                        key,
                        interface_prefix,
                        implied_prefix,
                        guarantee,
                        saved_state,
                        saved_unknown,
                    )
                case action_contract.EmptyGuarantee():
                    self._state[key] = _NodeState(emptied_by=guarantee.caused_by)
                case action_contract.OccupiedByNewGuarantee():
                    new_info = ParticleInfo(
                        last_position=guarantee.caused_by,
                        qualities=guarantee.qualities,
                        origin_position=guarantee.caused_by,
                    )
                    self._state[key] = _NodeState(particle_info=new_info)
                case action_contract.UnknownGuarantee():
                    self._unknown[key] = _UnknownState(caused_by=guarantee.caused_by)
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
        as unknown and return False to indicate the guarantee should be skipped.

        Returns True when the parent path is fully in the state trie (or
        could be completed by _ensure_action_parent).
        """
        ancestor_key = self._state.existing_prefix(key)
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
        # Mark the first missing node as unknown.
        missing_key = (*ancestor_key, first_missing)
        self._unknown[missing_key] = _UnknownState(caused_by=guarantee.caused_by)
        return False

    def _apply_existing_guarantee(
        self,
        dest_key: tuple[str, ...],
        interface_prefix: tuple[str, ...],
        implied_prefix: tuple[str, ...],
        guarantee: action_contract.OccupiedByExistingGuarantee,
        saved_state: dict[tuple[str, ...], trie.StrictReparentingTrie[_NodeState]],
        saved_unknown: dict[tuple[str, ...], trie.StrictReparentingTrie[_UnknownState]],
    ):
        """Apply an OccupiedByExisting guarantee at dest_key."""
        origin_tuple = guarantee.origin_position.canonical_chained_name_tuple
        if ast.chain_starts_with_global(origin_tuple):
            origin_key = implied_prefix + origin_tuple
        else:
            origin_key = interface_prefix + origin_tuple

        # Get origin's particle_info — from saved copy if already processed,
        # else from the live trie.
        saved_tree = saved_state.pop(origin_key, None)
        if saved_tree is not None:
            origin_state = saved_tree[origin_tuple[-1:]]
        elif origin_key in self._state:
            origin_state = self._state[origin_key]
        else:
            # The caller never filled the position, and we are executing an OccupiedByExisting
            # guarnatee on the same position that a particle was passed in on.
            self._unknown[dest_key] = _UnknownState(caused_by=guarantee.caused_by)
            return

        # The caller never filled the input interface position. The callee moves the particle to
        # another position. Thus, the origin_state _exists_ but the position got EmptyGuarantee
        # instead of being filled by something (and there's nothing in saved_state).
        if origin_state.particle_info is None:
            self._unknown[dest_key] = _UnknownState(caused_by=guarantee.caused_by)
            return

        moved_info = origin_state.particle_info.move_to(guarantee.caused_by)
        if saved_tree is not None:
            # If we have a saved_tree, we have to graft back in the children of
            # the popped subtree (the popped subtree starts with the particle
            # that we are moving, and we need to re-create it with moved_info).
            self._state[dest_key] = _NodeState(particle_info=moved_info)
            self._state.graft_subtree(dest_key, saved_tree.root_children())
        else:
            self._state.move_subtree(origin_key, dest_key)
            self._state[dest_key] = _NodeState(particle_info=moved_info)

        saved_unk = saved_unknown.pop(origin_key, None)
        # Guarantees reset the unknown state of particles they touch directly.
        # If we guarantee a particle in a position, then we know that it has a
        # particle. However, its _children_ might still be in some unknown state.
        # Exception: if the origin had pre-action unknown state (saved before the
        # guarantee loop began), the destination inherits that caused_by — the
        # guarantee fills it with whatever was at origin, including the uncertainty.
        if saved_unk is not None:
            origin_unknown = saved_unk[origin_tuple[-1:]]
            self._unknown[dest_key] = _UnknownState(caused_by=origin_unknown.caused_by)
            self._unknown.graft_subtree(dest_key, saved_unk.root_children())
        elif origin_key in self._unknown:
            self._unknown.move_subtree(origin_key, dest_key)
            self._unknown[dest_key] = _UnknownState()
