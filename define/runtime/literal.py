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


class Quality(ABC):
    """Abstract base class for all qualities (positions and actions)."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the name of this quality."""


class DimensionPoint:
    """A dimension point in the Define universe."""

    def __init__(self):
        """Initialize with empty positions and actions dictionaries."""
        self._positions: dict[str, GlobalPosition] = {}
        self._actions: dict[str, Action] = {}

    def assign_position(self, position: GlobalPosition):
        """Assign a position to this dimension point, triggering after_assigned."""
        self._positions[position.name] = position
        position.after_assigned()

    def assign_action(self, action: Action):
        """Assign an action to this dimension point."""
        self._actions[action.name] = action

    def get_position(self, name: str) -> GlobalPosition:
        """Return the position stored under the given name."""
        return self._positions[name]

    def get_action(self, name: str) -> Action:
        """Return the action stored under the given name."""
        return self._actions[name]


class Position(Quality, ABC):
    """Abstract base class for positions that can contain a dimension point."""

    def __init__(self):
        """Initialize with no dimension point."""
        self._dimension_point: DimensionPoint | None = None

    @abstractmethod
    def _get_constraints(self) -> list[Constraint]:
        """Return the constraint types for this position."""

    @property
    def has_dimension_point(self) -> bool:
        """Return whether this position contains a dimension point."""
        return self._dimension_point is not None

    @property
    def dimension_point(self) -> DimensionPoint:
        """Return the dimension point, raising NoDimensionPointError if none exists."""
        if self._dimension_point is None:
            raise NoDimensionPointError(self.name)
        return self._dimension_point

    def create_dimension_point(self):
        """Create a dimension point in this position. Raises if one exists."""
        if self._dimension_point is not None:
            raise DimensionPointExistsError(self.name)
        self._dimension_point = DimensionPoint()
        for constraint_type in self._get_constraints():
            constraint = constraint_type()
            if isinstance(constraint, Action):
                self._dimension_point.assign_action(constraint)
            else:
                self._dimension_point.assign_position(constraint)

    def after_assigned(self):
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
    constraints: ClassVar[list[Constraint]] = []

    @property
    @override
    def name(self) -> str:
        """Return the typed name of this position."""
        return type(self)._typed_name

    @override
    def _get_constraints(self) -> list[Constraint]:
        """Return the constraint types from the class variable."""
        return type(self).constraints


class LocalPosition(Position):
    """A locally-defined position with a runtime name and optional constraints."""

    def __init__(
        self,
        name: str,
        constraints: list[Constraint] | None = None,
    ):
        """Initialize a local position with the given name and optional constraints."""
        super().__init__()
        self._name: str = name
        self._constraints: list[Constraint] = constraints or []

    @property
    @override
    def name(self) -> str:
        """Return the name of this position."""
        return self._name

    @override
    def _get_constraints(self) -> list[Constraint]:
        """Return the constraint types for this position."""
        return self._constraints


class Action(Quality):
    """A globally-defined action with a class-level typed name."""

    _typed_name: ClassVar[str]

    @property
    @override
    def name(self) -> str:
        """Return the typed name of this action."""
        return type(self)._typed_name


Constraint = type[GlobalPosition] | type[Action]


def start(entry_point: GlobalPosition):
    """Execute the Define program startup sequence.

    Creates a dimension point (the view point) and assigns the entry point
    position as a quality, which triggers entry_point.after_assigned().
    """
    view_point = DimensionPoint()
    view_point.assign_position(entry_point)
