"""Tracks dimension point occupancy for positions within an action block."""

from __future__ import annotations

import dataclasses
import typing
from dataclasses import dataclass

from define.compiler.validator.reference_graph import action_contract

if typing.TYPE_CHECKING:
    from define.compiler import ast


# TODO: We need to track the full state of a dimension point's
# children, so they get moved with it. Probably we can just
# do this by making the tracker use a pygtrie and move whole
# subtrees around.
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


class DimensionPointTracker:
    """Tracks which positions contain dimension points.

    Handles both local positions (single-element chains) and external
    action interface positions (multi-element chains through actions).

    Pure data structure with no diagnostics logic. The caller is responsible
    for emitting diagnostics based on the tracker's query results.
    """

    _fqun: ast.Fqun

    def __init__(self, enclosing_definition: ast.QualityDefinition):
        """Initialize with the enclosing definition's FQUN."""
        self._fqun = enclosing_definition.typed_name.name_content.fqun
        self._dimension_points: dict[str, DimensionPointInfo] = {}
        self._positions_with_unknown_state: set[str] = set()
        self._emptied_by: dict[str, ast.PositionReference] = {}

    def _key(self, position: ast.PositionReference) -> str:
        """Compute the canonical string key for a position reference."""
        return position.chain.canonical_chained_name(in_universe=self._fqun)

    def mark_unknown(self, in_position: ast.PositionReference):
        """Mark a position as having unknown occupancy state."""
        self._positions_with_unknown_state.add(self._key(in_position))

    def has_unknown_state(self, in_position: ast.PositionReference) -> bool:
        """Return whether a position has unknown occupancy state."""
        return self._key(in_position) in self._positions_with_unknown_state

    def has_unknown_state_by_key(self, key: str) -> bool:
        """Return whether a position has unknown occupancy state, by raw key."""
        return key in self._positions_with_unknown_state

    def is_occupied(self, in_position: ast.PositionReference) -> bool:
        """Return whether a dimension point exists at this position."""
        return self._key(in_position) in self._dimension_points

    def is_occupied_by_key(self, key: str) -> bool:
        """Return whether a dimension point exists at this position, by raw key."""
        return key in self._dimension_points

    def get_occupant(self, in_position: ast.PositionReference) -> DimensionPointInfo:
        """Return the info for the dimension point at this position."""
        return self._dimension_points[self._key(in_position)]

    def get_occupant_by_key(self, key: str) -> DimensionPointInfo:
        """Return the info for the dimension point at this position, by raw key."""
        return self._dimension_points[key]

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
        key = self._key(in_position)
        if key in self._dimension_points:
            raise ValueError(f"position {key} is already occupied")
        self._dimension_points[key] = DimensionPointInfo(
            last_position=in_position,
            qualities=qualities,
            origin_position=in_position,
            from_caller=from_caller,
        )
        _ = self._emptied_by.pop(key, None)

    def destroy(self, in_position: ast.PositionReference):
        """Remove a dimension point from this position.

        Raises ValueError if the position is not occupied.
        """
        key = self._key(in_position)
        if key not in self._dimension_points:
            raise ValueError(f"position {key} is not occupied")
        del self._dimension_points[key]
        self._emptied_by[key] = in_position

    def get_emptied_by(
        self, ref: ast.PositionReference
    ) -> ast.PositionReference | None:
        """Return the position reference that emptied this position, if any."""
        return self._emptied_by.get(self._key(ref))

    def get_emptied_by_key(self, key: str) -> ast.PositionReference | None:
        """Return the position reference that emptied this position, by raw key."""
        return self._emptied_by.get(key)

    def move(self, source: ast.PositionReference, target: ast.PositionReference):
        """Move a dimension point from one position to another.

        Raises ValueError if from is not occupied or to is already occupied.
        """
        from_key = self._key(source)
        to_key = self._key(target)
        if from_key not in self._dimension_points:
            raise ValueError(f"source position {from_key} is not occupied")
        if to_key in self._dimension_points:
            raise ValueError(f"destination position {to_key} is already occupied")
        occupant = self._dimension_points.pop(from_key)
        self._dimension_points[to_key] = occupant.move_to(target)
        self._emptied_by[from_key] = source
        _ = self._emptied_by.pop(to_key, None)

    def generate_guarantees(
        self,
        action_def: ast.ActionDefinition,
    ) -> dict[str, action_contract.InterfacePositionGuarantee]:
        """Generate guarantees for all interface positions that have tracker state."""
        interface_names = set(action_def.interface_positions.keys())
        all_keys = (
            set(self._dimension_points.keys())
            | self._positions_with_unknown_state
            | set(self._emptied_by.keys())
        )

        guarantees: dict[str, action_contract.InterfacePositionGuarantee] = {}
        for key in all_keys:
            # TODO: This manual name parsing goes away when interface_positions
            # is keyed by full typed name instead of bare local name.
            first_element = key.split("::")[0]
            local_name = first_element.split("<")[1].rstrip(">")
            if local_name not in interface_names:
                continue
            guarantees[key] = self._guarantee_for_key(key)
        return guarantees

    def _guarantee_for_key(
        self,
        key: str,
    ) -> action_contract.InterfacePositionGuarantee:
        """Build a guarantee from the current tracker state for a given key."""
        if key in self._positions_with_unknown_state:
            return action_contract.UnknownGuarantee()
        if key in self._dimension_points:
            info = self._dimension_points[key]
            if info.from_caller:
                return action_contract.OccupiedByExistingGuarantee(
                    origin_position=info.origin_position,
                    caused_by=info.last_position,
                )
            return action_contract.OccupiedByNewGuarantee(
                qualities=info.qualities,
                caused_by=info.last_position,
            )
        return action_contract.EmptyGuarantee(
            caused_by=self._emptied_by.get(key),
        )

    def apply_guarantees(
        self,
        trigger_position: ast.PositionReference,
        guarantees: dict[str, action_contract.InterfacePositionGuarantee],
    ):
        """Apply action guarantees after an action completes.

        The trigger_position should be the position reference that triggered the action.
        Snapshots pre-trigger state, then updates each interface position
        according to its guarantee. For OCCUPIED guarantees with an origin
        position, resolves DP identity from the pre-trigger snapshot.
        """
        action_chain = trigger_position.chain.get_action_chain()
        if action_chain is None:
            raise ValueError(
                f"no action in chain: {trigger_position.chain.source_chained_name}"
            )
        key_prefix = action_chain.canonical_chained_name(in_universe=self._fqun)
        # TODO: Nested action chains still do not propagate callee requirements
        # and guarantees through the outer action. For example, if
        # position<iface>::action</other>::position<item> is prefilled and the
        # outer action only creates position<iface>::action</other>::position<trigger>,
        # we currently do not surface /other's empty requirement on position<item>.

        keys_to_snapshot: set[str] = set()
        for name in guarantees:
            keys_to_snapshot.add(f"{key_prefix}::{name}")
        # An existing DP might be moved from one interface position to another
        # (e.g., position<a> → position<b>). We need to read position<a>'s
        # state before any guarantees clear it, so snapshot it here. We might
        # not have made a guarantee about position<a> and so this is the only
        # way to capture that we need snapshot position<a>'s state.
        for guarantee in guarantees.values():
            if isinstance(guarantee, action_contract.OccupiedByExistingGuarantee):
                origin_canonical = (
                    guarantee.origin_position.chain.canonical_chained_name(
                        in_universe=self._fqun
                    )
                )
                keys_to_snapshot.add(f"{key_prefix}::{origin_canonical}")

        pre_trigger: dict[str, DimensionPointInfo] = {}
        for key in keys_to_snapshot:
            if key in self._dimension_points:
                pre_trigger[key] = self._dimension_points[key]

        for name, guarantee in guarantees.items():
            key = f"{key_prefix}::{name}"
            if key in self._dimension_points:
                del self._dimension_points[key]
            self._positions_with_unknown_state.discard(key)

            match guarantee:
                case action_contract.EmptyGuarantee():
                    if guarantee.caused_by is not None:
                        self._emptied_by[key] = guarantee.caused_by
                case action_contract.OccupiedByExistingGuarantee():
                    origin_canonical = (
                        guarantee.origin_position.chain.canonical_chained_name(
                            in_universe=self._fqun
                        )
                    )
                    origin_key = f"{key_prefix}::{origin_canonical}"
                    origin_info = pre_trigger.get(origin_key)
                    if origin_info is not None:
                        self._dimension_points[key] = origin_info.move_to(
                            guarantee.caused_by
                        )
                    else:
                        self._positions_with_unknown_state.add(key)
                case action_contract.OccupiedByNewGuarantee():
                    self._dimension_points[key] = DimensionPointInfo(
                        last_position=guarantee.caused_by,
                        qualities=guarantee.qualities,
                        origin_position=guarantee.caused_by,
                    )
                case action_contract.UnknownGuarantee():
                    self._positions_with_unknown_state.add(key)
                case _:
                    raise TypeError(f"Unexpected guarantee type: {type(guarantee)}")
