"""Information retained for a particle during reference-graph validation."""

from __future__ import annotations

import typing
from dataclasses import dataclass

if typing.TYPE_CHECKING:
    from define.compiler import ast
    from define.compiler.validator.reference_graph import quality_assignment


@dataclass(slots=True, eq=False)
class ParticleInfo:
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
