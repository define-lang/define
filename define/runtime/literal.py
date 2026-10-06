"""Runtime library for serial literal Python programs."""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar, Never, cast, overload, override

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

# TODO: Make operation tracing thread-safe somehow. Not a high priority.
_operation_trace: list[str] | None = None


class DefineRuntimeError(Exception):
    """Base class for Define runtime errors."""

    message_format: ClassVar[str]

    def __init__(self):
        """Format the message."""
        super().__init__(self.message_format.format(self=self))


class PositionError(DefineRuntimeError):
    """Base class for Define runtime errors about a position."""

    def __init__(self, position_name: str):
        """Initialize with the position name and format the message."""
        self.position_name: str = position_name
        super().__init__()


class ParticleExistsError(PositionError):
    """Raised when creating a particle in a position that already has one."""

    message_format: ClassVar[str] = (
        "Position '{self.position_name}' already contains a particle."
    )


class NoParticleError(PositionError):
    """Raised when moving a particle from a position that has none."""

    message_format: ClassVar[str] = (
        "Position '{self.position_name}' does not contain a particle."
    )


class UnsetValueError(DefineRuntimeError):
    """Raised when reading the value of a particle whose value is not set."""

    message_format: ClassVar[str] = "The particle does not have a set value."


class UnsatisfiedConstraintError(PositionError):
    """Raised when moving a particle to a position whose constraints are not met."""

    message_format: ClassVar[str] = (
        "Cannot move particle to '{self.position_name}':"
        " unsatisfied constraint '{self.constraint_name}'."
    )

    def __init__(self, position_name: str, constraint_name: str):
        """Initialize with the destination position name and unsatisfied constraint name."""
        self.constraint_name: str = constraint_name
        super().__init__(position_name)


class DuplicateConstraintError(PositionError):
    """Raised when a position declares the same quality as a constraint twice."""

    message_format: ClassVar[str] = (
        "Quality '{self.position_name}' is declared as a constraint more than once."
    )


class Quality:
    """A position or action assigned to a particle."""

    TYPE_NAME: ClassVar[str]
    implied_qualities: ClassVar[tuple[type[Quality], ...]] = ()

    def __init__(self, on_particle: Particle):
        """Initialize with the particle this quality is assigned to."""
        self._on_particle: Particle = on_particle

    @classmethod
    def full_name(cls) -> str:
        """Return the runtime name derived from the full Python class path."""
        return f"{cls.TYPE_NAME}<{cls.__module__}.{cls.__name__}>"

    @property
    def name(self) -> str:
        """The Define name derived from this quality's Python class."""
        return type(self).full_name()

    @property
    def on_particle(self) -> Particle:
        """The particle this quality is assigned to."""
        return self._on_particle


class Particle:
    """A particle in the Define universe."""

    def __init__(self):
        """Initialize with no assigned qualities."""
        self._qualities: dict[type[Quality], Quality] = {}

    def assign_quality(self, quality_class: type[Quality]):
        """Assign a quality to this particle, or do nothing if already present."""
        # A quality is set at most once; a repeat assignment (e.g. a constraint
        # also reached through another constraint's implication) is a no-op.
        # Genuinely duplicate constraints are rejected when a position is built.
        if quality_class in self._qualities:
            return
        for implied_class in quality_class.implied_qualities:
            self.assign_quality(implied_class)
        self._qualities[quality_class] = quality_class(self)

    def get_position[PositionType: Quality](
        self, position_class: type[PositionType]
    ) -> PositionType:
        """Return the assigned position of the given type."""
        return cast("PositionType", self._qualities[position_class])

    def get_action[ActionType: Action](
        self, action_class: type[ActionType]
    ) -> ActionType:
        """Return the assigned action of the given type."""
        return cast("ActionType", self._qualities[action_class])

    def has_quality_type(self, quality_type: type[Quality]) -> bool:
        """Return whether this particle satisfies a constraint of the given type."""
        return quality_type in self._qualities


class ValueParticle[ValueType](Particle):
    """A particle whose value has the Python type of its value type's encoding.

    Every particle is a ValueParticle. Code that does not know a particle's
    value type sees it as a Particle, which has no value.
    """

    def __init__(self):
        """Initialize with an unset value."""
        super().__init__()
        self._value: ValueType | None = None

    @property
    def value(self) -> ValueType:
        """The particle's value; access raises UnsetValueError if unset."""
        if self._value is None:
            raise UnsetValueError
        return self._value

    @value.setter
    def value(self, value: ValueType):
        self._value = value


class Position(ABC):
    """Abstract base class for positions that can contain a particle."""

    _particle: Particle | None = None

    @property
    @abstractmethod
    def name(self) -> str:
        """The name of this position."""

    @abstractmethod
    def _get_constraints(self) -> tuple[type[Quality], ...]:
        """Return the constraint types for this position."""

    @property
    def has_particle(self) -> bool:
        """Whether this position contains a particle."""
        return self._particle is not None

    @property
    def particle(self) -> Particle:
        """The particle; access raises NoParticleError if none exists."""
        if self._particle is None:
            raise NoParticleError(self.name)
        return self._particle

    def create_particle(self):
        """Create a particle in this position. Raises if one exists."""
        if self._particle is not None:
            raise ParticleExistsError(self.name)
        # Type arguments do not exist at runtime; subclasses that know the
        # position's value type narrow the particle to it.
        self._particle = ValueParticle[object]()
        for constraint_type in self._get_constraints():
            self._particle.assign_quality(constraint_type)

    def move_particle_to(self, destination: Position):
        """Move the particle from this position to destination."""
        if self._particle is None:
            raise NoParticleError(self.name)
        if destination._particle is not None:
            raise ParticleExistsError(destination.name)
        for constraint_type in destination._get_constraints():
            if not self._particle.has_quality_type(constraint_type):
                raise UnsatisfiedConstraintError(
                    destination.name, constraint_type.full_name()
                )
        destination._particle = self._particle
        self._particle = None

    def destroy_particle(self):
        """Destroy the particle in this position."""
        if self._particle is None:
            raise NoParticleError(self.name)
        self._particle = None


def _reject_duplicate_constraints(constraints: tuple[type[Quality], ...]):
    """Raise if the same quality appears more than once in a constraint list."""
    seen: set[type[Quality]] = set()
    for constraint in constraints:
        if constraint in seen:
            raise DuplicateConstraintError(constraint.full_name())
        seen.add(constraint)


class GlobalPosition[ValueType](Quality, Position):
    """A globally-defined position with constraints.

    ValueType is the Python type of the position's value, or Never when the
    position has no value constraint.
    """

    constraints: ClassVar[tuple[type[Quality], ...]] = ()
    TYPE_NAME: ClassVar[str] = "position"

    def __init_subclass__(cls, **kwargs: object):
        """Reject duplicate constraints when a global position class is defined."""
        super().__init_subclass__(**kwargs)
        _reject_duplicate_constraints(cls.constraints)

    @property
    @override
    def particle(self) -> ValueParticle[ValueType]:
        """The particle; access raises NoParticleError if none exists."""
        # Validation only allows a particle into this position if its value type
        # is this position's value type.
        return cast("ValueParticle[ValueType]", super().particle)

    @override
    def _get_constraints(self) -> tuple[type[Quality], ...]:
        """Return the constraint types from the class variable."""
        return type(self).constraints


class LocalPosition[ValueType](Position):
    """A locally-defined position with a runtime name and optional constraints.

    ValueType is the Python type of the position's value, or Never when the
    position has no value constraint.
    """

    def __init__(
        self,
        name: str,
        constraints: tuple[type[Quality], ...] = (),
    ):
        """Initialize a local position with its constraints."""
        super().__init__()
        _reject_duplicate_constraints(constraints)
        self._name: str = name
        self._constraints: tuple[type[Quality], ...] = constraints

    @property
    @override
    def name(self) -> str:
        """The name of this position."""
        return self._name

    @property
    @override
    def particle(self) -> ValueParticle[ValueType]:
        """The particle; access raises NoParticleError if none exists."""
        # Validation only allows a particle into this position if its value type
        # is this position's value type.
        return cast("ValueParticle[ValueType]", super().particle)

    @override
    def _get_constraints(self) -> tuple[type[Quality], ...]:
        """Return the constraint types for this position."""
        return self._constraints


type DestructionContribution = Callable[[Particle], None]


class Action(Quality):
    """A globally-defined action."""

    TYPE_NAME: ClassVar[str] = "action"

    def __init__(
        self,
        on_particle: Particle,
        interface_positions: Sequence[Position] = (),
    ):
        """Initialize with the assigned particle and its interface positions."""
        super().__init__(on_particle)
        self._interface_positions: dict[str, Position] = {
            position.name: position for position in interface_positions
        }

    @overload
    def get_interface_position(self, name: str, /) -> Position: ...

    @overload
    def get_interface_position[ValueType](
        self, name: str, value_type: type[ValueType], /
    ) -> LocalPosition[ValueType]: ...

    def get_interface_position[ValueType](
        self, name: str, _value_type: type[ValueType] | None = None, /
    ) -> Position:
        """Return the interface position with the given name.

        Given the Python type of the position's value, the position's particle
        has a value of that type.
        """
        return self._interface_positions[name]

    @property
    def interface_positions(self) -> tuple[Position, ...]:
        """The action's interface positions, in declaration order."""
        return tuple(self._interface_positions.values())

    def run(self) -> None:
        """Execute this action's statements."""
        raise NotImplementedError


def record_operation(label: str):
    """Record an operation when this program is being traced."""
    if _operation_trace is not None:
        _operation_trace.append(label)


def start(entry_point: type[Action], *, trace_operations: bool = False):
    """Create the view point particle and execute its entry action."""
    global _operation_trace  # noqa: PLW0603 - A program run has exactly one operation trace.
    _operation_trace = [] if trace_operations else None
    try:
        view_point = LocalPosition[Never](
            "position<view_point>", constraints=(entry_point,)
        )
        view_point.create_particle()
        view_point.particle.get_action(entry_point).run()
        trace_file = os.environ.get("DEFINE_OPERATION_TRACE_FILE")
        if _operation_trace is not None and trace_file is not None:
            _ = Path(trace_file).write_text(
                "".join(f"{operation}\n" for operation in _operation_trace),
                encoding="utf-8",
            )
    finally:
        _operation_trace = None
