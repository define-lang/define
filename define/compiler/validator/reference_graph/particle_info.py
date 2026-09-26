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
    # after the particle moves.
    origin_position: ast.PositionReference
    # Whether this particle was passed in by the caller (trigger/inferred) vs created in the body.
    from_caller: bool = False
    value_state: ParticleValueState | None = None
    # Assuming a value requirement does not change the caller's value.
    value_written: bool = False

    def value_effect(self) -> ParticleValueState | None:
        """Value change for a guarantee, or None when the value is unchanged."""
        if (
            self.from_caller
            and not self.value_written
            and self.value_state != ParticleValueState.ERROR
        ):
            return None
        return self.value_state

    def set_value_state(self, state: ParticleValueState | None):
        """Set the particle's value state; None leaves it unchanged."""
        if state is None:
            return
        self.value_state = state
        if state != ParticleValueState.ERROR:
            self.value_written = True
