"""Tracks dimension point occupancy for local positions within an action block."""

from __future__ import annotations

import typing
from dataclasses import dataclass

from define.compiler import ast

if typing.TYPE_CHECKING:
    from collections.abc import Set

    from define.compiler.validator import scope_tracker


@dataclass(frozen=True)
class DimensionPointInfo:
    """Information about a tracked dimension point."""

    creation_position: ast.LocalTypedNameReference
    qualities: frozenset[str]


class LocalDimensionPointTracker:
    """Tracks which local positions contain dimension points.

    Pure data structure with no diagnostics logic. The caller is responsible
    for emitting diagnostics based on the tracker's query results.
    """

    _fqun: ast.Fqun

    def __init__(self, enclosing_definition: ast.QualityDefinition):
        """Initialize with the enclosing definition's FQUN."""
        self._fqun = enclosing_definition.typed_name.name_content.fqun
        self._dimension_points: dict[str, DimensionPointInfo] = {}
        self._positions_with_unknown_state: set[str] = set()

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

    def mark_unknown_state(self, ref: ast.PositionReference):
        """Mark a position as having unknown occupancy state."""
        key = ref.chain.canonical_chained_name(in_universe=self._fqun)
        self._positions_with_unknown_state.add(key)

    def has_unknown_state(self, ref: ast.PositionReference) -> bool:
        """Return whether a position has unknown occupancy state."""
        key = ref.chain.canonical_chained_name(in_universe=self._fqun)
        return key in self._positions_with_unknown_state

    def is_occupied(self, ref: ast.PositionReference) -> bool:
        """Return whether a dimension point exists at this position."""
        key = ref.chain.canonical_chained_name(in_universe=self._fqun)
        return key in self._dimension_points

    def get_occupant(self, ref: ast.PositionReference) -> DimensionPointInfo:
        """Return the info for the dimension point at this position."""
        key = ref.chain.canonical_chained_name(in_universe=self._fqun)
        return self._dimension_points[key]

    def create(self, ref: ast.PositionReference, qualities: Set[str]):
        """Record a new dimension point at this position.

        Raises ValueError if the position is already occupied.
        """
        key = ref.chain.canonical_chained_name(in_universe=self._fqun)
        if key in self._dimension_points:
            raise ValueError(f"position {key} is already occupied")
        self._dimension_points[key] = DimensionPointInfo(
            creation_position=typing.cast(
                "ast.LocalTypedNameReference", ref.chain.typed_names[0]
            ),
            qualities=frozenset(qualities),
        )

    def destroy(self, ref: ast.PositionReference):
        """Remove a dimension point from this position.

        Raises ValueError if the position is not occupied.
        """
        key = ref.chain.canonical_chained_name(in_universe=self._fqun)
        if key not in self._dimension_points:
            raise ValueError(f"position {key} is not occupied")
        del self._dimension_points[key]

    def move(self, from_ref: ast.PositionReference, to_ref: ast.PositionReference):
        """Move a dimension point from one position to another.

        Raises ValueError if from is not occupied or to is already occupied.
        """
        from_key = from_ref.chain.canonical_chained_name(in_universe=self._fqun)
        to_key = to_ref.chain.canonical_chained_name(in_universe=self._fqun)
        if from_key not in self._dimension_points:
            raise ValueError(f"source position {from_key} is not occupied")
        if to_key in self._dimension_points:
            raise ValueError(f"destination position {to_key} is already occupied")
        occupant = self._dimension_points.pop(from_key)
        self._dimension_points[to_key] = DimensionPointInfo(
            creation_position=typing.cast(
                "ast.LocalTypedNameReference", to_ref.chain.typed_names[0]
            ),
            qualities=occupant.qualities,
        )
