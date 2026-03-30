"""Tracks dimension point occupancy for positions within an action block."""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass

from define.compiler import ast
from define.compiler.data_structures import trie
from define.compiler.validator.reference_graph import action_contract


@dataclass(frozen=True, slots=True)
class DimensionPointInfo:
    """Information about a tracked dimension point."""

    # The last position reference written in the code for the last
    # statement that relocated or created this dimension point.
    last_position: ast.PositionReference
    # The qualities we know that this dimension point has.
    qualities: frozenset[str]
    # The position reference where this dimension point was first created.
    origin_position: ast.PositionReference
    # Whether this DP was passed in by the caller (trigger/inferred) vs created in the body.
    from_caller: bool = False

    def move_to(self, target: ast.PositionReference) -> DimensionPointInfo:
        """Return a new DimensionPointInfo reflecting a move to the target position."""
        return dataclasses.replace(self, last_position=target)


@dataclass
class _NodeState:
    """Mutable state for a position in the state trie."""

    dp_info: DimensionPointInfo | None = None
    emptied_by: ast.PositionReference | None = None


@dataclass
class _UnknownState:
    """Wrapper for unknown-state trie values.

    LenientReparentingTrie can't use None as a value, so we wrap
    the caused_by reference in a dataclass.
    """

    caused_by: ast.PositionReference | None = None


_ACTION_KEY_PREFIX = f"{ast.NameType.ACTION.value}<"


class DimensionPointTracker:
    """Tracks which positions contain dimension points.

    Handles both local positions (single-element chains) and external
    action interface positions (multi-element chains through actions).

    Uses two tries internally:
    - A state trie tracking DP occupancy and emptied-by references.
    - An unknown-state trie tracking positions with unknown occupancy.

    Pure data structure with no diagnostics logic. The caller is responsible
    for emitting diagnostics based on the tracker's query results.
    """

    _fqun: ast.Fqun

    def __init__(self, enclosing_definition: ast.QualityDefinition):
        """Initialize with the enclosing definition's FQUN."""
        self._fqun = enclosing_definition.typed_name.name_content.fqun
        self._state: trie.StrictReparentingTrie[_NodeState] = (
            trie.StrictReparentingTrie()
        )
        self._unknown: trie.LenientReparentingTrie[_UnknownState] = (
            trie.LenientReparentingTrie(default_factory=_UnknownState)
        )

    def _key(self, position: ast.PositionReference) -> tuple[str, ...]:
        """Compute the canonical tuple key for a position reference."""
        return position.chain.canonical_chained_name_tuple(in_universe=self._fqun)

    def _ensure_action_parent(self, key: tuple[str, ...]):
        """Create the action intermediate trie node if needed."""
        if len(key) >= 2 and key[-2].startswith(_ACTION_KEY_PREFIX):
            parent_key = key[:-1]
            if parent_key not in self._state:
                self._state[parent_key] = _NodeState()

    # TODO: Unknown state does not propagate to descendants. If a position
    # is unknown, has_unknown_state on its children still returns False,
    # allowing creates and moves on children to proceed as if the parent
    # state were known. We should check ancestors when querying unknown state.
    def mark_unknown(self, in_position: ast.PositionReference):
        """Mark a position as having unknown occupancy state."""
        self._unknown[self._key(in_position)] = _UnknownState(caused_by=in_position)

    def has_unknown_state(self, in_position: ast.PositionReference) -> bool:
        """Return whether a position has unknown occupancy state."""
        return self.has_unknown_state_by_key(self._key(in_position))

    def has_unknown_state_by_key(self, key: tuple[str, ...]) -> bool:
        """Return whether a position has unknown occupancy state, by raw key."""
        state = self._unknown.get(key)
        return state is not None and state.caused_by is not None

    def is_occupied(self, in_position: ast.PositionReference) -> bool:
        """Return whether a dimension point exists at this position."""
        return self.is_occupied_by_key(self._key(in_position))

    def is_occupied_by_key(self, key: tuple[str, ...]) -> bool:
        """Return whether a dimension point exists at this position, by raw key."""
        state = self._state.get(key)
        return state is not None and state.dp_info is not None

    def get_occupant(self, in_position: ast.PositionReference) -> DimensionPointInfo:
        """Return the info for the dimension point at this position."""
        return self.get_occupant_by_key(self._key(in_position))

    def get_occupant_by_key(self, key: tuple[str, ...]) -> DimensionPointInfo:
        """Return the info for the dimension point at this position, by raw key."""
        state = self._state[key]
        if state.dp_info is None:
            raise KeyError(key)
        return state.dp_info

    def create(
        self,
        in_position: ast.PositionReference,
        qualities: frozenset[str],
        *,
        from_caller: bool = False,
    ):
        """Record a new dimension point at this position.

        Args:
            in_position: Where the dimension point is being created.
            qualities: The qualities this dimension point has.
            from_caller: True if this DP represents one passed in by the caller
                of this action (pass into the trigger condition or an interface
                position), False if created within this action body statement.

        Raises ValueError if the position is already occupied.
        """
        self._create_by_key(
            self._key(in_position), in_position, qualities, from_caller=from_caller
        )

    def _create_by_key(
        self,
        key: tuple[str, ...],
        position: ast.PositionReference,
        qualities: frozenset[str],
        *,
        from_caller: bool = False,
    ):
        self._ensure_action_parent(key)
        existing = self._state.get(key)
        if existing is not None and existing.dp_info is not None:
            raise ValueError(f"position {key} is already occupied")
        info = DimensionPointInfo(
            last_position=position,
            qualities=qualities,
            origin_position=position,
            from_caller=from_caller,
        )
        if existing is not None:
            existing.dp_info = info
            existing.emptied_by = None
        else:
            self._state[key] = _NodeState(dp_info=info)

    def destroy(self, in_position: ast.PositionReference):
        """Remove a dimension point from this position.

        Raises ValueError if the position is not occupied.
        """
        self._destroy_by_key(self._key(in_position), in_position)

    def _destroy_by_key(self, key: tuple[str, ...], position: ast.PositionReference):
        existing = self._state.get(key)
        if existing is None or existing.dp_info is None:
            raise ValueError(f"position {key} is not occupied")
        existing.dp_info = None
        existing.emptied_by = position

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
        """Move a dimension point from one position to another.

        Children of the source position move with it. After the move,
        the source position is marked as emptied.
        """
        self._move_by_key(self._key(source), self._key(target), source, target)

    def _move_by_key(
        self,
        from_key: tuple[str, ...],
        to_key: tuple[str, ...],
        source: ast.PositionReference,
        target: ast.PositionReference,
    ):
        self._ensure_action_parent(to_key)
        # TODO: Move last_position into _NodeState so that move_subtree
        # doesn't need this post-move fixup.
        moved_info = self._state[from_key].dp_info
        if moved_info is not None:
            moved_info = moved_info.move_to(target)

        to_state = self._state.get(to_key)
        if to_state is not None:
            # This should never happen, it's just a defensive check.
            if to_state.dp_info is not None:
                raise ValueError(f"destination position {to_key} is already occupied")
            # The target may already exist as an empty node (previously
            # destroyed). Delete it before moving so move_subtree succeeds.
            del self._state[to_key]
        self._state.move_subtree(from_key, to_key)
        self._state[to_key].dp_info = moved_info
        self._state[from_key] = _NodeState(emptied_by=source)

        if from_key in self._unknown:
            if to_key in self._unknown:
                del self._unknown[to_key]
            self._unknown.move_subtree(from_key, to_key)

    def generate_guarantees(
        self,
        action_def: ast.ActionDefinition,
    ) -> dict[tuple[str, ...], action_contract.InterfacePositionGuarantee]:
        """Generate guarantees for all interface positions that have tracker state."""
        interface_names = set(action_def.interface_positions.keys())

        # Collect keys that have interesting state from both tries.
        all_keys: set[tuple[str, ...]] = set()
        for key, state in self._state.items():
            if state.dp_info is not None or state.emptied_by is not None:
                all_keys.add(tuple(key))
        for key, unknown_state in self._unknown.items():
            if unknown_state.caused_by is not None:
                all_keys.add(tuple(key))

        guarantees: dict[
            tuple[str, ...], action_contract.InterfacePositionGuarantee
        ] = {}
        for key in all_keys:
            first_element = key[0]
            if first_element not in interface_names:
                continue
            guarantees[key] = self._guarantee_for_key(key)
        return guarantees

    def _guarantee_for_key(
        self,
        key: tuple[str, ...],
    ) -> action_contract.InterfacePositionGuarantee:
        """Build a guarantee from the current tracker state for a given key."""
        unknown_state = self._unknown.get(key)
        if unknown_state is not None and unknown_state.caused_by is not None:
            return action_contract.UnknownGuarantee(caused_by=unknown_state.caused_by)
        state = self._state.get(key)
        if state is not None and state.dp_info is not None:
            info = state.dp_info
            if info.from_caller:
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
        return action_contract.EmptyGuarantee(caused_by=caused_by)

    def apply_guarantees(
        self,
        trigger_position: ast.PositionReference,
        guarantees: dict[tuple[str, ...], action_contract.InterfacePositionGuarantee],
    ):
        """Apply action guarantees after an action completes.

        The trigger_position should be the position reference that triggered
        the action. Updates each interface position according to its guarantee.

        OccupiedByExisting guarantees move entire subtrees (the origin's
        children follow the parent DP).
        """
        action_chain = trigger_position.chain.get_action_chain()
        if action_chain is None:
            raise ValueError(
                f"no action in chain: {trigger_position.chain.source_chained_name}"
            )
        key_prefix = action_chain.canonical_chained_name_tuple(in_universe=self._fqun)
        # TODO: Nested action chains still do not propagate callee requirements
        # and guarantees through the outer action. For example, if
        # position<iface>::action</other>::position<item> is prefilled and the
        # outer action only creates position<iface>::action</other>::position<trigger>,
        # we currently do not surface /other's empty requirement on position<item>.

        # Parent-before-child ordering: Our first sort is by the key length
        # (the number of names in a chain). To understand why this is necessary,
        # imagine we do this:
        #
        #   move position<item> to position<dest>.
        #   create a dimension point in position<dest>::position</child>.
        #
        # We have to process the move from item to dest first, to understand
        # that what's in dest is the dimension point that was originally in
        # item. Only _then_ should we process the creation in position</child>,
        # so that we understand that we are creating a dimension point in a child
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
        # the dimension point in position</child> incorrectly.
        sorted_items = sorted(
            guarantees.items(),
            key=lambda item: (
                len(item[0]),
                item[1].caused_by.position.line,
                item[1].caused_by.position.column,
            ),
        )

        # Make a list of only the origin_positions for OccupiedByExistingGuarantee.
        # We need this list later to know what to "save" before we apply guarantees.
        origin_keys: set[tuple[str, ...]] = set()
        for _name, guarantee in sorted_items:
            if isinstance(guarantee, action_contract.OccupiedByExistingGuarantee):
                origin_tuple = (
                    guarantee.origin_position.chain.canonical_chained_name_tuple(
                        in_universe=self._fqun
                    )
                )
                origin_keys.add(key_prefix + origin_tuple)

        # Saved subtrees for swap safety. Keyed by the origin's full key.
        saved_state: dict[tuple[str, ...], trie.StrictReparentingTrie[_NodeState]] = {}
        saved_unknown: dict[
            tuple[str, ...], trie.StrictReparentingTrie[_UnknownState]
        ] = {}

        for name, guarantee in sorted_items:
            key = key_prefix + name

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
                origin_keys.discard(key)
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
                        key_prefix,
                        guarantee,
                        saved_state,
                        saved_unknown,
                    )
                case action_contract.EmptyGuarantee():
                    self._state[key] = _NodeState(emptied_by=guarantee.caused_by)
                case action_contract.OccupiedByNewGuarantee():
                    new_info = DimensionPointInfo(
                        last_position=guarantee.caused_by,
                        qualities=guarantee.qualities,
                        origin_position=guarantee.caused_by,
                    )
                    self._state[key] = _NodeState(dp_info=new_info)
                case action_contract.UnknownGuarantee():
                    self._unknown[key] = _UnknownState(caused_by=guarantee.caused_by)
                case _:
                    raise TypeError(f"Unexpected guarantee type: {type(guarantee)}")

    def _check_key_exists_for_guarantee(
        self,
        key: tuple[str, ...],
        guarantee: action_contract.InterfacePositionGuarantee,
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
        key_prefix: tuple[str, ...],
        guarantee: action_contract.OccupiedByExistingGuarantee,
        saved_state: dict[tuple[str, ...], trie.StrictReparentingTrie[_NodeState]],
        saved_unknown: dict[tuple[str, ...], trie.StrictReparentingTrie[_UnknownState]],
    ):
        """Apply an OccupiedByExisting guarantee at dest_key."""
        origin_tuple = guarantee.origin_position.chain.canonical_chained_name_tuple(
            in_universe=self._fqun
        )
        origin_key = key_prefix + origin_tuple

        # Get origin's dp_info — from saved copy if already processed,
        # else from the live trie.
        saved_tree = saved_state.pop(origin_key, None)
        if saved_tree is not None:
            origin_state = saved_tree[origin_tuple[-1:]]
        elif origin_key in self._state:
            origin_state = self._state[origin_key]
        else:
            # The caller never filled this interface position. There is no
            # dimension point to move, so we mark dest as unknown. The caller
            # already got an ActionRequiresOccupiedPositionDiagnostic from
            # _check_requirements.
            self._unknown[dest_key] = _UnknownState(caused_by=guarantee.caused_by)
            return

        # Only possible if the caller created a DP in a child position without
        # creating a DP in the parent position (TODO: can delete this check when we
        # get strict about this in the future).
        if origin_state.dp_info is None:
            self._unknown[dest_key] = _UnknownState(caused_by=guarantee.caused_by)
            return

        moved_info = origin_state.dp_info.move_to(guarantee.caused_by)
        if saved_tree is not None:
            # If we have a saved_tree, we have to graft back in the children of
            # the popped subtree (the popped subtree starts with the dimension
            # point that we are moving, and we need to re-create it with moved_info).
            self._state[dest_key] = _NodeState(dp_info=moved_info)
            self._state.graft_subtree(dest_key, saved_tree.root_children())
        else:
            self._state.move_subtree(origin_key, dest_key)
            self._state[dest_key] = _NodeState(dp_info=moved_info)

        saved_unk = saved_unknown.pop(origin_key, None)
        # Guarantees reset the unknown state of dimension points they touch directly.
        # If we guarantee a dimension point in a position, then we know that it has a
        # dimension point. However, its _children_ might still be in some unknown state.
        if saved_unk is not None:
            self._unknown[dest_key] = _UnknownState()
            self._unknown.graft_subtree(dest_key, saved_unk.root_children())
        elif origin_key in self._unknown:
            self._unknown.move_subtree(origin_key, dest_key)
            self._unknown[dest_key] = _UnknownState()
