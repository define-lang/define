"""Runtime library for serial literal Python programs."""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar, cast, override

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

_REPORT_OCCUPIED_POSITIONS_ENV_VAR = "DEFINE_REPORT_OCCUPIED_POSITIONS"
# TODO: Make operation tracing thread-safe somehow. Not a high priority.
_operation_trace: list[str] | None = None


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


class DuplicateConstraintError(DefineRuntimeError):
    """Raised when a position declares the same quality as a constraint twice."""

    message_format: ClassVar[str] = (
        "Quality '{self.position_name}' is declared as a constraint more than once."
    )


class Quality:
    """A global position or action assigned to a particle."""

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
        """Return the Define name derived from this quality's Python class."""
        return type(self).full_name()

    @property
    def on_particle(self) -> Particle:
        """Return the particle this quality is assigned to."""
        return self._on_particle


class Particle:
    """A particle in the Define universe."""

    def __init__(self):
        """Initialize with empty positions and actions dictionaries."""
        self._positions: dict[type[GlobalPosition], GlobalPosition] = {}
        self._actions: dict[type[Action], Action] = {}
        self._assigned_qualities: list[Quality] = []

    def assign_position(self, position_class: type[GlobalPosition]):
        """Assign a position to this particle, or do nothing if already present."""
        # A quality is set at most once; a repeat assignment (e.g. a constraint
        # also reached through another constraint's implication) is a no-op.
        # Genuinely duplicate constraints are rejected when a position is built.
        if position_class in self._positions:
            return
        self._assign_implied_qualities(position_class)
        position = position_class(self)
        self._assigned_qualities.append(position)
        self._positions[position_class] = position

    def assign_action(self, action_class: type[Action]):
        """Assign an action to this particle, or do nothing if already present."""
        if action_class in self._actions:
            return
        self._assign_implied_qualities(action_class)
        action = action_class(self)
        self._assigned_qualities.append(action)
        self._actions[action_class] = action

    def _assign_implied_qualities(self, quality_class: type[Quality]):
        for implied_class in quality_class.implied_qualities:
            if issubclass(implied_class, GlobalPosition):
                self.assign_position(implied_class)
            elif issubclass(implied_class, Action):
                self.assign_action(implied_class)

    def get_position[PositionType: GlobalPosition](
        self, position_class: type[PositionType]
    ) -> PositionType:
        """Return the assigned position of the given type."""
        return cast("PositionType", self._positions[position_class])

    def get_action[ActionType: Action](
        self, action_class: type[ActionType]
    ) -> ActionType:
        """Return the assigned action of the given type."""
        return cast("ActionType", self._actions[action_class])

    # TODO: Cache this?
    @property
    def quality_types(self) -> frozenset[type[Quality]]:
        """Return the set of constraint types satisfied by this particle."""
        return frozenset(type(q) for q in self._assigned_qualities)

    def occupied_position_names(self) -> list[str]:
        """Return chained names of occupied positions reachable from this particle.

        Names are returned depth-first, each parent position before the
        positions nested within its particle, in quality-assignment order.
        """
        # TODO: Render occupied position names with Define syntax instead of
        # Python class paths.
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

    def move_particle_to(self, destination: Position):
        """Move the particle from this position to destination."""
        if self._particle is None:
            raise NoParticleError(self.name)
        if destination._particle is not None:
            raise ParticleExistsError(destination.name)
        for constraint_type in destination._get_constraints():
            if constraint_type not in self._particle.quality_types:
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


class GlobalPosition(Quality, Position):
    """A globally-defined position with constraints."""

    constraints: ClassVar[tuple[type[Quality], ...]] = ()
    TYPE_NAME: ClassVar[str] = "position"

    def __init_subclass__(cls, **kwargs: object):
        """Reject duplicate constraints when a global position class is defined."""
        super().__init_subclass__(**kwargs)
        _reject_duplicate_constraints(cls.constraints)

    @override
    def _get_constraints(self) -> tuple[type[Quality], ...]:
        """Return the constraint types from the class variable."""
        return type(self).constraints


class LocalPosition(Position):
    """A locally-defined position with a runtime name and optional constraints."""

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
        """Return the name of this position."""
        return self._name

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
        interface_positions: Sequence[LocalPosition] = (),
    ):
        """Initialize with the assigned particle and its interface positions."""
        super().__init__(on_particle)
        self._interface_positions: dict[str, LocalPosition] = {
            position.name: position for position in interface_positions
        }

    def get_interface_position(self, name: str) -> LocalPosition:
        """Return the interface position with the given name."""
        return self._interface_positions[name]

    @property
    def interface_positions(self) -> tuple[LocalPosition, ...]:
        """Return this action's interface positions, in declaration order."""
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
    global _operation_trace
    _operation_trace = [] if trace_operations else None
    try:
        view_point = LocalPosition("position<view_point>", constraints=(entry_point,))
        view_point.create_particle()
        view_point.particle.get_action(entry_point).run()
        occupied_positions_file = os.environ.get(_REPORT_OCCUPIED_POSITIONS_ENV_VAR)
        if occupied_positions_file is not None:
            occupied_names = view_point.particle.occupied_position_names()
            _ = Path(occupied_positions_file).write_text(
                "".join(f"{name}\n" for name in occupied_names)
            )
        trace_file = os.environ.get("DEFINE_OPERATION_TRACE_FILE")
        if _operation_trace is not None and trace_file is not None:
            _ = Path(trace_file).write_text(
                "".join(f"{operation}\n" for operation in _operation_trace)
            )
    finally:
        _operation_trace = None
