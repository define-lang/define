"""Position occupancy values shared by validation and code generation."""

from __future__ import annotations

import enum


class PositionOccupancyState(enum.Enum):
    """The occupancy state of a position."""

    EMPTY = enum.auto()
    OCCUPIED = enum.auto()
    ERROR = enum.auto()
