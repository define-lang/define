"""Runtime library for literal Python transpilation of Define programs."""

from __future__ import annotations

from typing import ClassVar


class DefineRuntimeError(Exception):
    """Base class for Define runtime errors."""

    message_format: ClassVar[str]

    def __init__(self, position_name: str):
        """Initialize with the position name and format the message."""
        self.position_name: str = position_name
        super().__init__(self.message_format.format(self=self))


class DimensionPointExistsError(DefineRuntimeError):
    """Raised when creating a dimension point in a position that already has one."""

    message_format: ClassVar[str] = (
        "Position '{self.position_name}' already contains a dimension point."
    )


class NoDimensionPointError(DefineRuntimeError):
    """Raised when moving a dimension point from a position that has none."""

    message_format: ClassVar[str] = (
        "Position '{self.position_name}' does not contain a dimension point."
    )


class DimensionPoint:
    """A dimension point in the Define universe."""

    def __init__(self):
        """Initialize with an empty qualities dictionary."""
        self._qualities: dict[str, Position] = {}

    def assign_quality(self, quality_position: Position):
        """Assign a quality to this dimension point, triggering after_assigned."""
        self._qualities[quality_position.name] = quality_position
        quality_position.after_assigned()


class Position:
    """A position that can contain a dimension point."""

    def __init__(self, name: str, constraints: list[str] | None = None):
        """Initialize a position with the given name and optional constraints."""
        self._name: str = name
        self._constraints: list[str] = constraints or []
        self._dimension_point: DimensionPoint | None = None

    @property
    def name(self) -> str:
        """Return the name of this position."""
        return self._name

    @property
    def has_dimension_point(self) -> bool:
        """Return whether this position contains a dimension point."""
        return self._dimension_point is not None

    def create_dimension_point(self) -> DimensionPoint:
        """Create a dimension point in this position. Raises if one exists."""
        if self._dimension_point is not None:
            raise DimensionPointExistsError(self._name)
        self._dimension_point = DimensionPoint()
        return self._dimension_point

    def after_assigned(self):
        """Run when this position is assigned as a quality. Override in subclasses."""

    def move_dimension_point_to(self, destination: Position):
        """Move the dimension point from this position to destination."""
        if self._dimension_point is None:
            raise NoDimensionPointError(self._name)
        if destination._dimension_point is not None:
            raise DimensionPointExistsError(destination._name)
        destination._dimension_point = self._dimension_point
        self._dimension_point = None


def start(entry_point: Position):
    """Execute the Define program startup sequence.

    Creates a dimension point (the view point) and assigns the entry point
    position as a quality, which triggers entry_point.after_assigned().
    """
    dp = DimensionPoint()
    dp.assign_quality(entry_point)
