"""Position occupancy values shared by validation and code generation."""

from __future__ import annotations

import enum
import typing
from dataclasses import dataclass

if typing.TYPE_CHECKING:
    from define.compiler import ast


class PositionOccupancyState(enum.Enum):
    """The occupancy state of a position."""

    EMPTY = enum.auto()
    OCCUPIED = enum.auto()
    ERROR = enum.auto()


@dataclass(frozen=True, slots=True)
class ChildOccupancy:
    """A child position's occupancy and the Source location of the statement that filled it."""

    state: PositionOccupancyState
    # Where the occupying particle was last placed, so a caller that resolves an
    # empty-requirement violation from this record (rather than from its own
    # tracker) can still report the fill site. Only set when state is OCCUPIED.
    filled_at: ast.SourceLocation | None = None


type ChildOccupancyMap = dict[tuple[str, ...], ChildOccupancy]


# The empty and error states carry no fill site, so a single shared instance
# serves every position. OCCUPIED must be constructed with its own filled_at.
EMPTY_OCCUPANCY = ChildOccupancy(PositionOccupancyState.EMPTY)
ERROR_OCCUPANCY = ChildOccupancy(PositionOccupancyState.ERROR)
