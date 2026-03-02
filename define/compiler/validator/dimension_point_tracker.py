"""Tracks dimension point occupancy for local positions within an action block."""

from __future__ import annotations

import typing

from define.compiler import ast

if typing.TYPE_CHECKING:
    from define.compiler.validator import scope_tracker


class LocalDimensionPointTracker:
    """Tracks which local positions contain dimension points.

    Pure data structure with no diagnostics logic. The caller is responsible
    for emitting diagnostics based on the tracker's query results.
    """

    _fqun: ast.Fqun

    def __init__(self, enclosing_definition: ast.QualityDefinition):
        """Initialize with the enclosing definition's FQUN."""
        self._fqun = enclosing_definition.typed_name.name_content.fqun
        self._dimension_points: dict[str, ast.LocalTypedNameReference] = {}
        self._positions_with_unknown_state: set[str] = set()

    def get_local_position_reference(
        self,
        ref: ast.PositionReference,
        scope: scope_tracker.ScopeTracker,
    ) -> ast.LocalTypedNameReference | None:
        """Return the local typed name reference if trackable, None otherwise.

        A position reference is trackable when it has a single-item chain,
        that item is a LocalTypedNameReference, and it is defined in the
        current (innermost) scope.
        """
        if len(ref.chain) != 1:
            return None
        first = ref.chain[0]
        if not isinstance(first, ast.LocalTypedNameReference):
            return None
        if not scope.is_defined_in_current_scope(first):
            return None
        return first

    def mark_unknown_state(self, ref: ast.PositionReference):
        """Mark a position as having unknown occupancy state."""
        self._positions_with_unknown_state.add(self._key_for(ref))

    def has_unknown_state(self, ref: ast.PositionReference) -> bool:
        """Return whether a position has unknown occupancy state."""
        return self._key_for(ref) in self._positions_with_unknown_state

    def is_occupied(self, ref: ast.PositionReference) -> bool:
        """Return whether a dimension point exists at this position."""
        return self._key_for(ref) in self._dimension_points

    def get_occupant(self, ref: ast.PositionReference) -> ast.LocalTypedNameReference:
        """Return the reference that created the dimension point at this position."""
        return self._dimension_points[self._key_for(ref)]

    def create(self, ref: ast.PositionReference):
        """Record a new dimension point at this position.

        Raises ValueError if the position is already occupied.
        """
        key = self._key_for(ref)
        if key in self._dimension_points:
            raise ValueError(f"position {key} is already occupied")
        self._dimension_points[key] = typing.cast(
            "ast.LocalTypedNameReference", ref.chain[0]
        )

    def move(self, from_ref: ast.PositionReference, to_ref: ast.PositionReference):
        """Move a dimension point from one position to another.

        Raises ValueError if from is not occupied or to is already occupied.
        """
        from_key = self._key_for(from_ref)
        to_key = self._key_for(to_ref)
        if from_key not in self._dimension_points:
            raise ValueError(f"source position {from_key} is not occupied")
        if to_key in self._dimension_points:
            raise ValueError(f"destination position {to_key} is already occupied")
        occupant = self._dimension_points.pop(from_key)
        self._dimension_points[to_key] = occupant

    def _key_for(self, ref: ast.PositionReference) -> str:
        return ref.chain[0].full_typed_name(in_universe=self._fqun)
