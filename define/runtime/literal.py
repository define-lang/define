"""Runtime library for literal Python transpilation of Define programs."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import ClassVar, override


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


class Position(ABC):
    """Abstract base class for positions that can contain a dimension point."""

    def __init__(self):
        """Initialize with no dimension point."""
        self._dimension_point: DimensionPoint | None = None

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the name of this position."""

    @abstractmethod
    def _get_constraints(self) -> list[type[GlobalPosition]]:
        """Return the constraint types for this position."""

    @property
    def has_dimension_point(self) -> bool:
        """Return whether this position contains a dimension point."""
        return self._dimension_point is not None

    def create_dimension_point(self):
        """Create a dimension point in this position. Raises if one exists."""
        if self._dimension_point is not None:
            raise DimensionPointExistsError(self.name)
        self._dimension_point = DimensionPoint()
        for constraint_type in self._get_constraints():
            self._dimension_point.assign_quality(constraint_type())

    def after_assigned(self):  # noqa: B027
        """Run when this position is assigned as a quality. Override in subclasses."""

    def move_dimension_point_to(self, destination: Position):
        """Move the dimension point from this position to destination."""
        if self._dimension_point is None:
            raise NoDimensionPointError(self.name)
        if destination._dimension_point is not None:
            raise DimensionPointExistsError(destination.name)
        destination._dimension_point = self._dimension_point
        self._dimension_point = None


class GlobalPosition(Position):
    """A globally-defined position with a class-level typed name and constraints."""

    _typed_name: ClassVar[str]
    constraints: ClassVar[list[type[GlobalPosition]]] = []

    @property
    @override
    def name(self) -> str:
        """Return the typed name of this position."""
        return type(self)._typed_name

    @override
    def _get_constraints(self) -> list[type[GlobalPosition]]:
        """Return the constraint types from the class variable."""
        return type(self).constraints


class LocalPosition(Position):
    """A locally-defined position with a runtime name and optional constraints."""

    def __init__(
        self,
        name: str,
        constraints: list[type[GlobalPosition]] | None = None,
    ):
        """Initialize a local position with the given name and optional constraints."""
        super().__init__()
        self._name: str = name
        self._constraints: list[type[GlobalPosition]] = constraints or []

    @property
    @override
    def name(self) -> str:
        """Return the name of this position."""
        return self._name

    @override
    def _get_constraints(self) -> list[type[GlobalPosition]]:
        """Return the constraint types for this position."""
        return self._constraints


def start(entry_point: Position):
    """Execute the Define program startup sequence.

    Creates a dimension point (the view point) and assigns the entry point
    position as a quality, which triggers entry_point.after_assigned().
    """
    dp = DimensionPoint()
    dp.assign_quality(entry_point)
