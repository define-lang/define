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


class UnsatisfiedConstraintError(DefineRuntimeError):
    """Raised when moving a dimension point to a position whose constraints are not met."""

    message_format: ClassVar[str] = (
        "Cannot move dimension point to '{self.position_name}':"
        " unsatisfied constraint '{self.constraint_name}'."
    )

    def __init__(self, position_name: str, constraint_name: str):
        """Initialize with the destination position name and unsatisfied constraint name."""
        self.constraint_name: str = constraint_name
        super().__init__(position_name)


class DuplicateQualityAssignmentError(DefineRuntimeError):
    """Raised when assigning a quality that is already on the dimension point."""

    message_format: ClassVar[str] = (
        "Quality '{self.position_name}' is already assigned to this dimension point."
    )


class Quality:
    """A quality identified by a class-level typed name: a global position or an action."""

    typed_name: ClassVar[str]
    implied_qualities: ClassVar[tuple[type[Quality], ...]] = ()

    def __init__(self, on_dimension_point: DimensionPoint):
        """Initialize with the dimension point this quality is assigned to."""
        self._on_dimension_point: DimensionPoint = on_dimension_point

    @property
    def name(self) -> str:
        """Return the typed name of this quality."""
        return type(self).typed_name

    @property
    def on_dimension_point(self) -> DimensionPoint:
        """Return the dimension point this quality is assigned to."""
        return self._on_dimension_point


class DimensionPoint:
    """A dimension point in the Define universe."""

    def __init__(self):
        """Initialize with empty positions and actions dictionaries."""
        self._positions: dict[str, GlobalPosition] = {}
        self._actions: dict[str, Action] = {}
        self._assigned_qualities: list[Quality] = []

    def assign_position(self, position_class: type[GlobalPosition]):
        """Assign a position to this dimension point, triggering after_assigned."""
        if position_class.typed_name in self._positions:
            raise DuplicateQualityAssignmentError(position_class.typed_name)
        self._assign_implied_qualities(position_class)
        position = position_class(self)
        self._assigned_qualities.append(position)
        self._positions[position_class.typed_name] = position
        position.after_assigned()

    def assign_action(self, action_class: type[Action]):
        """Assign an action to this dimension point."""
        if action_class.typed_name in self._actions:
            raise DuplicateQualityAssignmentError(action_class.typed_name)
        self._assign_implied_qualities(action_class)
        action = action_class(self)
        self._assigned_qualities.append(action)
        self._actions[action_class.typed_name] = action

    def _assign_implied_qualities(self, quality_class: type[Quality]):
        for implied_class in quality_class.implied_qualities:
            if (
                issubclass(implied_class, GlobalPosition)
                and implied_class.typed_name not in self._positions
            ):
                self.assign_position(implied_class)
            elif (
                issubclass(implied_class, Action)
                and implied_class.typed_name not in self._actions
            ):
                self.assign_action(implied_class)

    def get_position(self, name: str) -> GlobalPosition:
        """Return the position stored under the given name."""
        return self._positions[name]

    def get_action(self, name: str) -> Action:
        """Return the action stored under the given name."""
        return self._actions[name]

    @property
    def quality_types(self) -> frozenset[type[Quality]]:
        """Return the set of constraint types satisfied by this dimension point."""
        return frozenset(type(q) for q in self._assigned_qualities)


class Position(ABC):
    """Abstract base class for positions that can contain a dimension point."""

    _dimension_point: DimensionPoint | None = None

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the name of this position."""

    @abstractmethod
    def _get_constraints(self) -> tuple[type[Quality], ...]:
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
            if issubclass(constraint_type, GlobalPosition):
                self._dimension_point.assign_position(constraint_type)
            elif issubclass(constraint_type, Action):
                self._dimension_point.assign_action(constraint_type)
        self._after_dimension_point_arrived()

    def move_dimension_point_to(self, destination: Position):
        """Move the dimension point from this position to destination."""
        if self._dimension_point is None:
            raise NoDimensionPointError(self.name)
        if destination._dimension_point is not None:
            raise DimensionPointExistsError(destination.name)
        quality_types = self._dimension_point.quality_types
        for constraint_type in destination._get_constraints():
            if constraint_type not in quality_types:
                raise UnsatisfiedConstraintError(
                    destination.name, constraint_type.typed_name
                )
        destination._dimension_point = self._dimension_point
        self._dimension_point = None
        destination._after_dimension_point_arrived()

    def destroy_dimension_point(self):
        """Destroy the dimension point in this position."""
        if self._dimension_point is None:
            raise NoDimensionPointError(self.name)
        self._dimension_point = None

    def _after_dimension_point_arrived(self):  # noqa: B027
        """Run after a dimension point arrives. Override in subclasses."""


class GlobalPosition(Quality, Position):
    """A globally-defined position with a class-level typed name and constraints."""

    constraints: ClassVar[tuple[type[Quality], ...]] = ()

    @override
    def _get_constraints(self) -> tuple[type[Quality], ...]:
        """Return the constraint types from the class variable."""
        return type(self).constraints

    def after_assigned(self):
        """Run when this position is assigned as a quality. Override in subclasses."""


class LocalPosition(Position):
    """A locally-defined position with a runtime name and optional constraints."""

    def __init__(
        self,
        name: str,
        constraints: tuple[type[Quality], ...] = (),
    ):
        """Initialize a local position with the given name and optional constraints."""
        super().__init__()
        self._name: str = name
        self._constraints: tuple[type[Quality], ...] = constraints

    @property
    @override
    def name(self) -> str:
        """Return the name of this position."""
        return self._name

    @override
    def _get_constraints(self) -> tuple[type[Quality], ...]:
        """Return the constraint types for this position."""
        return self._constraints


class Action(Quality):
    """A globally-defined action with a class-level typed name."""

    def __init__(
        self,
        on_dimension_point: DimensionPoint,
        interface_positions: list[InterfacePosition] | None = None,
        trigger_position_name: str | None = None,
    ):
        """Initialize with the assigned dimension point and optional interface positions."""
        super().__init__(on_dimension_point)
        self._interface_positions: dict[str, InterfacePosition] = {
            pos.name: pos for pos in (interface_positions or [])
        }
        self._trigger_position_name: str | None = trigger_position_name
        if self._trigger_position_name is not None:
            self._interface_positions[self._trigger_position_name].set_is_trigger_for(
                self
            )

    def get_interface_position(self, name: str) -> InterfacePosition:
        """Return the interface position with the given name."""
        return self._interface_positions[name]

    @property
    def should_execute(self) -> bool:
        """Return whether the trigger position has a dimension point."""
        if self._trigger_position_name is None:
            return False
        return self._interface_positions[
            self._trigger_position_name
        ].has_dimension_point

    def execute(self):
        """Execute the action body. Override in subclasses."""


class InterfacePosition(LocalPosition):
    """A position that serves as an interface for an action's trigger condition."""

    def __init__(
        self,
        name: str,
        constraints: tuple[type[Quality], ...] = (),
    ):
        """Initialize an interface position with the given name and optional constraints."""
        super().__init__(name, constraints)
        self._trigger_action: Action | None = None

    def set_is_trigger_for(self, action: Action):
        """Mark this position as a trigger condition for the given action."""
        self._trigger_action = action

    @override
    def _after_dimension_point_arrived(self):
        if self._trigger_action is not None and self._trigger_action.should_execute:
            self._trigger_action.execute()


def start(entry_point: type[GlobalPosition]):
    """Execute the Define program startup sequence.

    Creates a dimension point (the view point) and assigns the entry point
    position as a quality, which triggers entry_point.after_assigned().
    """
    view_point = DimensionPoint()
    view_point.assign_position(entry_point)
