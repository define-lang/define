"""Tracks dimension point occupancy for positions within an action block."""

from __future__ import annotations

import dataclasses
import typing
from dataclasses import dataclass

from define.compiler.data_structures import trie
from define.compiler.validator.reference_graph import action_contract

if typing.TYPE_CHECKING:
    from define.compiler import ast


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
        # TODO: Switch to StrictReparentingTrie once intermediate position
        # validation is implemented. Currently lenient because action chain
        # elements in keys don't have DPs.
        self._state: trie.LenientReparentingTrie[_NodeState] = (
            trie.LenientReparentingTrie(default_factory=_NodeState)
        )
        self._unknown: trie.LenientReparentingTrie[bool] = trie.LenientReparentingTrie(
            default_factory=bool
        )

    def _key(self, position: ast.PositionReference) -> tuple[str, ...]:
        """Compute the canonical tuple key for a position reference."""
        return position.chain.canonical_chained_name_tuple(in_universe=self._fqun)

    def mark_unknown(self, in_position: ast.PositionReference):
        """Mark a position as having unknown occupancy state."""
        self._unknown[self._key(in_position)] = True

    def has_unknown_state(self, in_position: ast.PositionReference) -> bool:
        """Return whether a position has unknown occupancy state."""
        return self.has_unknown_state_by_key(self._key(in_position))

    def has_unknown_state_by_key(self, key: tuple[str, ...]) -> bool:
        """Return whether a position has unknown occupancy state, by raw key."""
        return bool(self._unknown.get(key))

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
        for key, is_unknown in self._unknown.items():
            if is_unknown:
                all_keys.add(tuple(key))

        guarantees: dict[
            tuple[str, ...], action_contract.InterfacePositionGuarantee
        ] = {}
        for key in all_keys:
            # TODO: This manual name parsing goes away when interface_positions
            # is keyed by full typed name instead of bare local name.
            first_element = key[0]
            local_name = first_element.split("<")[1].rstrip(">")
            if local_name not in interface_names:
                continue
            guarantees[key] = self._guarantee_for_key(key)
        return guarantees

    def _guarantee_for_key(
        self,
        key: tuple[str, ...],
    ) -> action_contract.InterfacePositionGuarantee:
        """Build a guarantee from the current tracker state for a given key."""
        if self.has_unknown_state_by_key(key):
            return action_contract.UnknownGuarantee()
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
        return action_contract.EmptyGuarantee(caused_by=caused_by)

    def apply_guarantees(
        self,
        trigger_position: ast.PositionReference,
        guarantees: dict[tuple[str, ...], action_contract.InterfacePositionGuarantee],
    ):
        """Apply action guarantees after an action completes.

        The trigger_position should be the position reference that triggered the action.
        Snapshots pre-trigger state, then updates each interface position
        according to its guarantee. For OCCUPIED guarantees with an origin
        position, resolves DP identity from the pre-trigger snapshot.

        TODO: OccupiedByExisting guarantees should move the origin's children
        along with the parent DP, not just copy the parent's dp_info. This
        requires reworking the snapshot approach to use subtree operations.
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

        keys_to_snapshot: set[tuple[str, ...]] = set()
        for name in guarantees:
            keys_to_snapshot.add(key_prefix + name)
        # An existing DP might be moved from one interface position to another
        # (e.g., position<a> → position<b>). We need to read position<a>'s
        # state before any guarantees clear it, so snapshot it here. We might
        # not have made a guarantee about position<a> and so this is the only
        # way to capture that we need to snapshot position<a>'s state.
        for guarantee in guarantees.values():
            if isinstance(guarantee, action_contract.OccupiedByExistingGuarantee):
                origin_tuple = (
                    guarantee.origin_position.chain.canonical_chained_name_tuple(
                        in_universe=self._fqun
                    )
                )
                keys_to_snapshot.add(key_prefix + origin_tuple)

        pre_trigger: dict[tuple[str, ...], DimensionPointInfo] = {}
        for key in keys_to_snapshot:
            state = self._state.get(key)
            if state is not None and state.dp_info is not None:
                pre_trigger[key] = state.dp_info

        for name, guarantee in guarantees.items():
            key = key_prefix + name

            # Clear existing state for this position (without cascading to children).
            existing_state = self._state.get(key)
            if existing_state is not None:
                existing_state.dp_info = None
                existing_state.emptied_by = None
            if key in self._unknown:
                self._unknown[key] = False

            match guarantee:
                case action_contract.EmptyGuarantee():
                    if guarantee.caused_by is not None:
                        if existing_state is not None:
                            existing_state.emptied_by = guarantee.caused_by
                        else:
                            self._state[key] = _NodeState(
                                emptied_by=guarantee.caused_by
                            )
                case action_contract.OccupiedByExistingGuarantee():
                    origin_tuple = (
                        guarantee.origin_position.chain.canonical_chained_name_tuple(
                            in_universe=self._fqun
                        )
                    )
                    origin_key = key_prefix + origin_tuple
                    origin_info = pre_trigger.get(origin_key)
                    if origin_info is not None:
                        moved = origin_info.move_to(guarantee.caused_by)
                        if existing_state is not None:
                            existing_state.dp_info = moved
                        else:
                            self._state[key] = _NodeState(dp_info=moved)
                    else:
                        self._unknown[key] = True
                case action_contract.OccupiedByNewGuarantee():
                    new_info = DimensionPointInfo(
                        last_position=guarantee.caused_by,
                        qualities=guarantee.qualities,
                        origin_position=guarantee.caused_by,
                    )
                    if existing_state is not None:
                        existing_state.dp_info = new_info
                    else:
                        self._state[key] = _NodeState(dp_info=new_info)
                case action_contract.UnknownGuarantee():
                    self._unknown[key] = True
                case _:
                    raise TypeError(f"Unexpected guarantee type: {type(guarantee)}")
