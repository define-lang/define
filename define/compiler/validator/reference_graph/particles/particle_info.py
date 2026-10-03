"""Information retained for a particle during reference-graph validation."""

from __future__ import annotations

import enum
import typing

import msgspec

if typing.TYPE_CHECKING:
    from define.compiler import ast
    from define.compiler.validator.reference_graph import quality_assignment


class ParticleValueState(enum.Enum):
    """Whether a particle is known to have a set value."""

    UNSET = enum.auto()
    SET = enum.auto()
    ERROR = enum.auto()


class ParticleSource(enum.Enum):
    """Where a particle this action tracks came from."""

    # Created by a statement in this action.
    THIS_ACTION = enum.auto()
    # Passed in by this action's caller, through an Action Requirement.
    CALLER = enum.auto()
    # Created by a callee and left in this action's state by its Guarantees.
    CALLEE = enum.auto()


class ParticleInfo(msgspec.Struct, eq=False):
    """Information about a tracked particle."""

    # The last position reference written in the code for the last
    # statement that relocated or created this particle.
    last_position: ast.PositionReference
    # The qualities we know that this particle has, in
    # assignment order.
    qualities: quality_assignment.QualityAssignments
    # The position where this particle was created or first arrived through an
    # occupied Action Requirement. DLP 42 uses it to attribute constraint uses
    # after the particle moves. For a particle a callee created, it is where
    # the callee created it, named the way that callee wrote it, so it is not
    # one of this action's positions.
    origin_position: ast.PositionReference
    source: ParticleSource = ParticleSource.THIS_ACTION
    value_state: ParticleValueState | None = None
    # Where this action last wrote the particle's value, or None when it has
    # not written it. Assuming a value requirement does not write it.
    value_written_at: ast.SourceLocation | None = None

    def value_effect(self) -> ParticleValueState | None:
        """Value change for a guarantee, or None when the value is unchanged."""
        if (
            self.source is ParticleSource.CALLER
            and self.value_written_at is None
            and self.value_state != ParticleValueState.ERROR
        ):
            return None
        return self.value_state

    def set_value_state(
        self, state: ParticleValueState | None, written_at: ast.SourceLocation
    ):
        """Set the particle's value state as written at ``written_at``; None leaves it unchanged."""
        if state is None:
            return
        self.value_state = state
        if state != ParticleValueState.ERROR:
            self.value_written_at = written_at
