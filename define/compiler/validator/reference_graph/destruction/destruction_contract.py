"""Semantic identities for destruction and Destruction Contracts."""

from __future__ import annotations

from typing import TYPE_CHECKING

import msgspec

if TYPE_CHECKING:
    from define.compiler import ast, chained_name


class DestructionFact(msgspec.Struct, frozen=True, eq=False):
    """That one specific particle was destroyed, and by which destruction."""

    destroying_definition: ast.ActionDefinition
    # The position the Destroy statement or Automatic Destruction named, whose
    # destruction also destroyed every particle in its transitive child
    # positions.
    directly_destroyed_position: ast.PositionReference
    is_automatic: bool
    destroyed_position_in_destroyer: ast.PositionReference


class PropagatedDestruction(msgspec.Struct, eq=False):
    """A destruction expressed through an action's contracted position."""

    destruction_fact: DestructionFact
    # The contracted origin, as a chained name within the action exposing it.
    contracted_position: ast.PositionReference


class RunGuaranteedParticleDestructors(msgspec.Struct):
    """A call to one of an action's methods that run the Destructors for what it left at and below a position."""

    # The particle to run them for, from the perspective of the action whose
    # step or method this is in.
    position: ast.PositionReference
    action: ast.GlobalTypedName[ast.GlobalNameContent[ast.Fqun | None]]
    # The position in that action's contract that the method is for.
    position_in_action: chained_name.PositionReferenceTuple


class DestroyedPosition(msgspec.Struct, frozen=True):
    """A position whose particle a destruction destroys."""

    # From the perspective of the action whose step or method destroys it.
    position: ast.PositionReference
    # From the perspective of the action that destroys it.
    position_in_destroyer: ast.PositionReference


class KnownDestructionWork(msgspec.Struct):
    """The part of one Simultaneous Transitive Destruction that one action knows about: what it runs and what it destroys."""

    destructors: list[ast.ActionReference] = msgspec.field(default_factory=list)
    # What runs for particles that callees left below the destroyed particles
    # and that the action never expanded.
    guaranteed_particle_destructors: list[RunGuaranteedParticleDestructors] = (
        msgspec.field(default_factory=list)
    )
    # Child positions come before their parent positions.
    positions: list[DestroyedPosition] = msgspec.field(default_factory=list)

    def has_work(self) -> bool:
        """Return whether there is anything to run or destroy."""
        return bool(
            self.destructors or self.guaranteed_particle_destructors or self.positions
        )

    def extend(self, other: KnownDestructionWork):
        """Add the work of ``other``, a destruction of other particles at the same moment, after this work."""
        self.destructors.extend(other.destructors)
        self.guaranteed_particle_destructors.extend(
            other.guaranteed_particle_destructors
        )
        self.positions.extend(other.positions)


class DestructionContribution(msgspec.Struct):
    """What one action adds to the generated code of one Simultaneous Transitive Destruction."""

    work: KnownDestructionWork = msgspec.field(default_factory=KnownDestructionWork)
    # The destructions of particles from this action's caller, each in a
    # Destruction Contract through which the callers add what they know.
    caller_particle_destructions: list[PropagatedDestruction] = msgspec.field(
        default_factory=list
    )

    def has_contribution(self) -> bool:
        """Return whether this action adds anything to the destruction."""
        return self.work.has_work() or bool(self.caller_particle_destructions)

    def extend(self, other: DestructionContribution):
        """Add the contribution of ``other``, to a destruction of other particles at the same moment, after this contribution."""
        self.work.extend(other.work)
        self.caller_particle_destructions.extend(other.caller_particle_destructions)


class DestructionConnection(msgspec.Struct):
    """What a caller adds to one callee destruction."""

    callee_destruction: PropagatedDestruction
    # Positions in its work are from the perspective of the particle the
    # callee destroyed. None when the caller adds nothing.
    contribution: DestructionContribution | None = None
