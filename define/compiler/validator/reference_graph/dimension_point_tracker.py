"""Tracks dimension point occupancy for positions within an action block."""

from __future__ import annotations

import typing
from dataclasses import dataclass

from define.compiler import ast
from define.compiler.validator.reference_graph import action_contract

if typing.TYPE_CHECKING:
    from define.compiler.validator import scope_tracker

PositionRef = ast.LocalTypedNameReference | ast.PositionReference


@dataclass(frozen=True)
class DimensionPointInfo:
    """Information about a tracked dimension point."""

    # The source line that caused this to be where it is.
    code_position: ast.SourcePosition
    # The qualities we know that this dimension point has.
    qualities: frozenset[str]
    # The interface position that this originally came from, if any.
    origin_position: ast.LocalPositionDefinition | None = None


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
        self._emptied_by: dict[str, ast.SourcePosition] = {}

    def _key(self, ref: PositionRef) -> str:
        """Compute the canonical string key for a position reference."""
        if isinstance(ref, ast.PositionReference):
            return ref.chain.canonical_chained_name(in_universe=self._fqun)
        return ref.source_typed_name

    # TODO: This is a pure function; it should probably be a helper
    # where it's used rather than here. It's also misnamed.
    def get_local_position(
        self,
        ref: ast.PositionReference,
        scope: scope_tracker.ScopeTracker,
    ) -> ast.LocalTypedNameReference | None:
        """Return the local typed name reference if trackable, None otherwise.

        A position reference is trackable when it has a single-item chain,
        that item is a LocalTypedNameReference, and it is defined in any
        enclosing scope.
        """
        if len(ref.chain.typed_names) != 1:
            return None
        first = ref.chain.typed_names[0]
        if not isinstance(first, ast.LocalTypedNameReference):
            return None
        if not scope.is_defined(first):
            return None
        return first

    def mark_unknown(self, ref: PositionRef):
        """Mark a position as having unknown occupancy state."""
        self._positions_with_unknown_state.add(self._key(ref))

    def has_unknown_state(self, ref: PositionRef) -> bool:
        """Return whether a position has unknown occupancy state."""
        return self._key(ref) in self._positions_with_unknown_state

    def has_unknown_state_by_key(self, key: str) -> bool:
        """Return whether a position has unknown occupancy state, by raw key."""
        return key in self._positions_with_unknown_state

    def is_occupied(self, ref: PositionRef) -> bool:
        """Return whether a dimension point exists at this position."""
        return self._key(ref) in self._dimension_points

    def is_occupied_by_key(self, key: str) -> bool:
        """Return whether a dimension point exists at this position, by raw key."""
        return key in self._dimension_points

    def get_occupant(self, ref: PositionRef) -> DimensionPointInfo:
        """Return the info for the dimension point at this position."""
        return self._dimension_points[self._key(ref)]

    def get_occupant_by_key(self, key: str) -> DimensionPointInfo:
        """Return the info for the dimension point at this position, by raw key."""
        return self._dimension_points[key]

    def create(
        self,
        ref: PositionRef,
        qualities: frozenset[str],
        *,
        origin_position: ast.LocalPositionDefinition | None = None,
    ):
        """Record a new dimension point at this position.

        Raises ValueError if the position is already occupied.
        """
        key = self._key(ref)
        if key in self._dimension_points:
            raise ValueError(f"position {key} is already occupied")
        self._dimension_points[key] = DimensionPointInfo(
            code_position=ref.position,
            qualities=qualities,
            origin_position=origin_position,
        )
        _ = self._emptied_by.pop(key, None)

    def destroy(self, ref: PositionRef):
        """Remove a dimension point from this position.

        Raises ValueError if the position is not occupied.
        """
        key = self._key(ref)
        if key not in self._dimension_points:
            raise ValueError(f"position {key} is not occupied")
        del self._dimension_points[key]
        self._emptied_by[key] = ref.position

    def get_emptied_by(self, ref: PositionRef) -> ast.SourcePosition | None:
        """Return the source position that emptied this position, if any."""
        return self._emptied_by.get(self._key(ref))

    def get_emptied_by_key(self, key: str) -> ast.SourcePosition | None:
        """Return the source position that emptied this position, by raw key."""
        return self._emptied_by.get(key)

    def move(self, from_ref: PositionRef, to_ref: PositionRef):
        """Move a dimension point from one position to another.

        Raises ValueError if from is not occupied or to is already occupied.
        """
        from_key = self._key(from_ref)
        to_key = self._key(to_ref)
        if from_key not in self._dimension_points:
            raise ValueError(f"source position {from_key} is not occupied")
        if to_key in self._dimension_points:
            raise ValueError(f"destination position {to_key} is already occupied")
        occupant = self._dimension_points.pop(from_key)
        self._dimension_points[to_key] = DimensionPointInfo(
            code_position=to_ref.position,
            qualities=occupant.qualities,
            origin_position=occupant.origin_position,
        )
        self._emptied_by[from_key] = from_ref.position
        _ = self._emptied_by.pop(to_key, None)

    def interface_position_key(
        self, ref: ast.PositionReference, local_name: str
    ) -> str:
        """Compute the key for a sibling interface position of the same action.

        Given a ref like position<box>::action</other>::position<trigger_pos>
        and local_name "item", returns the key for
        position<box>::action</other>::position<item>.
        """
        elements = ref.chain.typed_names
        prefix = "::".join(
            e.full_typed_name(in_universe=self._fqun) for e in elements[:-1]
        )
        return f"{prefix}::position<{local_name}>"

    def apply_guarantees(
        self,
        ref: ast.PositionReference,
        guarantees: dict[str, action_contract.InterfacePositionGuarantee],
    ):
        """Apply action guarantees after an action completes.

        The ref should be the position reference that triggered the action.
        Snapshots pre-trigger state, then updates each interface position
        according to its guarantee. For OCCUPIED guarantees with an origin
        position, resolves DP identity from the pre-trigger snapshot.
        """
        names_to_snapshot: set[str] = set(guarantees.keys())
        for guarantee in guarantees.values():
            if isinstance(guarantee, action_contract.OccupiedByExistingGuarantee):
                names_to_snapshot.add(
                    guarantee.origin_position.typed_name.name_content.name
                )

        pre_trigger: dict[str, DimensionPointInfo] = {}
        for name in names_to_snapshot:
            key = self.interface_position_key(ref, name)
            if key in self._dimension_points:
                pre_trigger[name] = self._dimension_points[key]

        for name, guarantee in guarantees.items():
            key = self.interface_position_key(ref, name)
            if key in self._dimension_points:
                del self._dimension_points[key]
            self._positions_with_unknown_state.discard(key)

            match guarantee:
                case action_contract.EmptyGuarantee():
                    if guarantee.caused_by is not None:
                        self._emptied_by[key] = guarantee.caused_by
                case action_contract.OccupiedByExistingGuarantee():
                    origin_name = guarantee.origin_position.typed_name.name_content.name
                    origin_info = pre_trigger.get(origin_name)
                    if origin_info is not None:
                        self._dimension_points[key] = DimensionPointInfo(
                            code_position=guarantee.caused_by,
                            qualities=origin_info.qualities,
                            origin_position=origin_info.origin_position,
                        )
                    else:
                        self._positions_with_unknown_state.add(key)
                case action_contract.OccupiedByNewGuarantee():
                    self._dimension_points[key] = DimensionPointInfo(
                        code_position=guarantee.caused_by,
                        qualities=guarantee.qualities,
                    )
                case action_contract.UnknownGuarantee():
                    self._positions_with_unknown_state.add(key)
                case _:
                    raise TypeError(f"Unexpected guarantee type: {type(guarantee)}")
