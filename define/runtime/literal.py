"""Runtime library for literal Python transpilation of Define programs."""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from typing import ClassVar, override

_REPORT_OCCUPIED_POSITIONS_ENV_VAR = "DEFINE_REPORT_OCCUPIED_POSITIONS"


class DefineRuntimeError(Exception):
    """Base class for Define runtime errors."""

    message_format: ClassVar[str]

    def __init__(self, position_name: str):
        """Initialize with the position name and format the message."""
        self.position_name: str = position_name
        super().__init__(self.message_format.format(self=self))


class ParticleExistsError(DefineRuntimeError):
    """Raised when creating a particle in a position that already has one."""

    message_format: ClassVar[str] = (
        "Position '{self.position_name}' already contains a particle."
    )


class NoParticleError(DefineRuntimeError):
    """Raised when moving a particle from a position that has none."""

    message_format: ClassVar[str] = (
        "Position '{self.position_name}' does not contain a particle."
    )


class UnsatisfiedConstraintError(DefineRuntimeError):
    """Raised when moving a particle to a position whose constraints are not met."""

    message_format: ClassVar[str] = (
        "Cannot move particle to '{self.position_name}':"
        " unsatisfied constraint '{self.constraint_name}'."
    )

    def __init__(self, position_name: str, constraint_name: str):
        """Initialize with the destination position name and unsatisfied constraint name."""
        self.constraint_name: str = constraint_name
        super().__init__(position_name)


class DuplicateQualityAssignmentError(DefineRuntimeError):
    """Raised when assigning a quality that is already on the particle."""

    message_format: ClassVar[str] = (
        "Quality '{self.position_name}' is already assigned to this particle."
    )


class Quality:
    """A quality identified by a class-level typed name: a global position or an action."""

    typed_name: ClassVar[str]
    implied_qualities: ClassVar[tuple[type[Quality], ...]] = ()

    def __init__(self, on_particle: Particle):
        """Initialize with the particle this quality is assigned to."""
        self._on_particle: Particle = on_particle

    @property
    def name(self) -> str:
        """Return the typed name of this quality."""
        return type(self).typed_name

    @property
    def on_particle(self) -> Particle:
        """Return the particle this quality is assigned to."""
        return self._on_particle

    def before_parent_particle_destroyed(self):
        """Run when the owning particle is being destroyed. Override in subclasses."""


class Particle:
    """A particle in the Define universe."""

    def __init__(self):
        """Initialize with empty positions and actions dictionaries."""
        self._positions: dict[str, GlobalPosition] = {}
        self._actions: dict[str, Action] = {}
        self._assigned_qualities: list[Quality] = []

    def assign_position(self, position_class: type[GlobalPosition]):
        """Assign a position to this particle, triggering after_assigned."""
        if position_class.typed_name in self._positions:
            raise DuplicateQualityAssignmentError(position_class.typed_name)
        self._assign_implied_qualities(position_class)
        position = position_class(self)
        self._assigned_qualities.append(position)
        self._positions[position_class.typed_name] = position
        position.after_assigned()

    def assign_action(self, action_class: type[Action]):
        """Assign an action to this particle."""
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
        """Return the set of constraint types satisfied by this particle."""
        return frozenset(type(q) for q in self._assigned_qualities)

    def destroy(self):
        """Run the Destruction Cascade, unassigning qualities in reverse order."""
        for quality in reversed(self._assigned_qualities):
            quality.before_parent_particle_destroyed()

    def run_constructors(self):
        """Run each constructor quality, in the order it was assigned (DLP 32)."""
        for quality in self._assigned_qualities:
            if isinstance(quality, Action) and quality.is_constructor:
                quality.execute()

    def occupied_position_names(self) -> list[str]:
        """Return chained names of occupied positions reachable from this particle.

        Names are returned depth-first, each parent position before the
        positions nested within its particle, in quality-assignment order.
        """
        return self._occupied_position_names(())

    def _occupied_position_names(self, prefix: tuple[str, ...]) -> list[str]:
        names: list[str] = []
        for quality in self._assigned_qualities:
            if isinstance(quality, GlobalPosition):
                chain = (*prefix, quality.name)
                if quality.has_particle:
                    names.append("::".join(chain))
                    names.extend(quality.particle._occupied_position_names(chain))
            elif isinstance(quality, Action):
                action_chain = (*prefix, quality.name)
                for interface_position in quality.interface_positions:
                    chain = (*action_chain, interface_position.name)
                    if interface_position.has_particle:
                        names.append("::".join(chain))
                        names.extend(
                            interface_position.particle._occupied_position_names(chain)
                        )
        return names


class Position(ABC):
    """Abstract base class for positions that can contain a particle."""

    _particle: Particle | None = None

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the name of this position."""

    @abstractmethod
    def _get_constraints(self) -> tuple[type[Quality], ...]:
        """Return the constraint types for this position."""

    @property
    def has_particle(self) -> bool:
        """Return whether this position contains a particle."""
        return self._particle is not None

    @property
    def particle(self) -> Particle:
        """Return the particle, raising NoParticleError if none exists."""
        if self._particle is None:
            raise NoParticleError(self.name)
        return self._particle

    def create_particle(self):
        """Create a particle in this position. Raises if one exists."""
        if self._particle is not None:
            raise ParticleExistsError(self.name)
        self._particle = Particle()
        for constraint_type in self._get_constraints():
            if issubclass(constraint_type, GlobalPosition):
                self._particle.assign_position(constraint_type)
            elif issubclass(constraint_type, Action):
                self._particle.assign_action(constraint_type)
        # Constructors fire on creation only, never on a move into this position
        # (DLP 32), so they run here rather than in _after_particle_arrived.
        self._particle.run_constructors()
        self._after_particle_arrived()

    def move_particle_to(self, destination: Position):
        """Move the particle from this position to destination."""
        if self._particle is None:
            raise NoParticleError(self.name)
        if destination._particle is not None:
            raise ParticleExistsError(destination.name)
        quality_types = self._particle.quality_types
        for constraint_type in destination._get_constraints():
            if constraint_type not in quality_types:
                raise UnsatisfiedConstraintError(
                    destination.name, constraint_type.typed_name
                )
        destination._particle = self._particle
        self._particle = None
        destination._after_particle_arrived()

    def destroy_particle(self):
        """Destroy the particle in this position, running the Destruction Cascade."""
        if self._particle is None:
            raise NoParticleError(self.name)
        self._particle.destroy()
        self._particle = None

    def _after_particle_arrived(self):  # noqa: B027
        """Run after a particle arrives. Override in subclasses."""


class GlobalPosition(Quality, Position):
    """A globally-defined position with a class-level typed name and constraints."""

    constraints: ClassVar[tuple[type[Quality], ...]] = ()

    @override
    def _get_constraints(self) -> tuple[type[Quality], ...]:
        """Return the constraint types from the class variable."""
        return type(self).constraints

    def after_assigned(self):
        """Run when this position is assigned as a quality. Override in subclasses."""

    @override
    def before_parent_particle_destroyed(self):
        if self.has_particle:
            self.destroy_particle()


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

    is_constructor: ClassVar[bool] = False
    is_destructor: ClassVar[bool] = False

    def __init__(
        self,
        on_particle: Particle,
        interface_positions: list[InterfacePosition] | None = None,
        trigger_position_name: str | None = None,
    ):
        """Initialize with the assigned particle and optional interface positions."""
        super().__init__(on_particle)
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
    def interface_positions(self) -> tuple[InterfacePosition, ...]:
        """Return this action's interface positions, in declaration order."""
        return tuple(self._interface_positions.values())

    @property
    def should_execute(self) -> bool:
        """Return whether the trigger position has a particle."""
        if self._trigger_position_name is None:
            return False
        return self._interface_positions[self._trigger_position_name].has_particle

    def execute(self):
        """Execute the action body. Override in subclasses."""

    @override
    def before_parent_particle_destroyed(self):
        if self.is_destructor:
            self.execute()
        for interface_position in reversed(self._interface_positions.values()):
            if interface_position.has_particle:
                interface_position.destroy_particle()


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
    def _after_particle_arrived(self):
        if self._trigger_action is not None and self._trigger_action.should_execute:
            self._trigger_action.execute()


def start(entry_point: type[Action]):
    """Execute the Define program startup sequence (DLP 33).

    Creates the anonymous view point position, whose only constraint is the
    entry-point constructor, then creates the view point particle in it. The
    creation assigns the constructor and fires it, running the program.
    """
    view_point_position = LocalPosition(
        "position<view_point>", constraints=(entry_point,)
    )
    view_point_position.create_particle()
    if os.environ.get(_REPORT_OCCUPIED_POSITIONS_ENV_VAR):
        for chained_name in view_point_position.particle.occupied_position_names():
            print(chained_name)
