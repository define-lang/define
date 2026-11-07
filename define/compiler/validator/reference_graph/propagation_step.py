"""The steps by which a requirement reaches the definition that reports it."""

from __future__ import annotations

import enum
import typing

import msgspec

if typing.TYPE_CHECKING:
    from define.compiler import ast


class PropagationKind(enum.Enum):
    """How a requirement reached a given step in its propagation chain."""

    # The deepest step in the chain: the definition's own body inferred the
    # requirement directly.
    DIRECT_INFERENCE = enum.auto()
    # The current definition's body destroyed a caller-passed particle,
    # firing a destructor; the destructor's requirements propagated up.
    DESTRUCTOR_CASCADE = enum.auto()
    # A position quality assignment directly assigned a quality to a position.
    QUALITY_ASSIGNED = enum.auto()
    # Creating a particle triggered one of its constructor qualities.
    CONSTRUCTOR_TRIGGER = enum.auto()
    # The current definition's body triggered an action; the action's
    # requirements propagated up.
    ACTION_TRIGGER = enum.auto()
    # The particle whose destructor requirement is violated was originally
    # created here.
    PARTICLE_ORIGIN = enum.auto()
    # The particle is automatically destroyed at the end of a body, firing the
    # destructor whose requirement is violated.
    AUTO_DESTRUCTION = enum.auto()
    # The contracted position was filled here, which is what violates an
    # empty-requirement.
    FILL_SITE = enum.auto()


class PropagationStep(msgspec.Struct, frozen=True):
    """One step in a requirement's propagation chain, with its source location."""

    location: ast.SourceLocation
    kind: PropagationKind
    # The definition, quality, or position that performs or receives the event
    # described by this step (where ``location`` points).
    enclosing_quality_name: str
    # The quality triggered or assigned by an event involving two names; None
    # when the event only describes ``enclosing_quality_name``.
    triggered_quality_name: str | None
