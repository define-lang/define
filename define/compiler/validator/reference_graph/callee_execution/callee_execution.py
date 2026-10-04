"""One execution of a callee, as the action triggering it sees it."""

from __future__ import annotations

import typing

import msgspec

from define.compiler.validator.reference_graph import action_contract
from define.compiler.validator.reference_graph.callee_execution import (
    requirement_violation,
)

if typing.TYPE_CHECKING:
    from define.compiler import ast
    from define.compiler.errors import diagnostics
    from define.compiler.validator.reference_graph.particles import particle_info


class CalleeExecution(msgspec.Struct, frozen=True):
    """One execution of a callee, triggered by a particle arriving at its trigger position, that the action being validated is about to trigger."""

    contract: action_contract.ActionContract
    action_chain: ast.ActionReference
    # None when the callee is one of this action's implied actions, which
    # triggers on this action's parent particle.
    parent_particle: particle_info.ParticleInfo | None
    acting_on_position: ast.PositionReference

    @property
    def action_assignment(self) -> action_contract.ActionAssignment | None:
        """The assignment of the callee to a particle that caused this execution, or None when no assignment did."""
        return None

    @property
    def diagnostic_location(self) -> ast.SourceLocation:
        """Where diagnostics about this execution point."""
        return self.acting_on_position.location

    def requirement_violation(
        self,
        requirement: action_contract.PositionRequirement,
        position_in_caller: ast.PositionReference,
        occupant: particle_info.ParticleInfo | None,
        definition: ast.ActionDefinition,
    ) -> diagnostics.InferredRequirementViolationDiagnostic:
        """Return the diagnostic for a requirement of the callee, in ``position_in_caller``, that the state of ``definition`` violates."""
        return requirement_violation.trigger_violation(
            req=requirement,
            definition=definition,
            full_caller_chain=position_in_caller,
            acting_on_position=self.acting_on_position,
            occupant=occupant,
            action_assignment=self.action_assignment,
        )


class ConstructorCalleeExecution(CalleeExecution, frozen=True):
    """One execution of a constructor, triggered by the Create of the particle it is a quality of."""

    @property
    @typing.override
    def action_assignment(self) -> action_contract.ActionAssignment:
        return action_contract.ActionAssignment(
            quality=self.action_chain.get_last_action(),
            assigned_to_position_name=self.acting_on_position.typed_names[-1],
        )


class DestructorCalleeExecution(CalleeExecution, frozen=True):
    """One execution of a Destructor, at the moment its particle is destroyed."""

    destructor: action_contract.Destructor
    # The local position whose Automatic Destruction destroys the particle,
    # or None for a Destroy.
    auto_destruction_target: ast.PositionReference | None

    @property
    @typing.override
    def action_assignment(self) -> action_contract.ActionAssignment:
        return self.destructor.action_assignment()

    @property
    @typing.override
    def diagnostic_location(self) -> ast.SourceLocation:
        if self.auto_destruction_target is None:
            return self.acting_on_position.location
        return self.auto_destruction_target.location

    @typing.override
    def requirement_violation(
        self,
        requirement: action_contract.PositionRequirement,
        position_in_caller: ast.PositionReference,
        occupant: particle_info.ParticleInfo | None,
        definition: ast.ActionDefinition,
    ) -> diagnostics.InferredRequirementViolationDiagnostic:
        return requirement_violation.direct_destructor(
            req=requirement,
            definition=definition,
            full_caller_chain=position_in_caller,
            occupant=occupant,
            destructor=self.destructor,
            auto_destruction_target=self.auto_destruction_target,
        )
