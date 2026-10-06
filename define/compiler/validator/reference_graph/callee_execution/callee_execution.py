"""One execution of a callee, as the action triggering it sees it."""

from __future__ import annotations

import typing

import msgspec

from define.compiler import chained_name
from define.compiler.validator.reference_graph import (
    action_contract,
    position_occupancy,
)
from define.compiler.validator.reference_graph.callee_execution import (
    requirement_violation,
)

if typing.TYPE_CHECKING:
    from define.compiler import ast
    from define.compiler.errors import diagnostics
    from define.compiler.validator.reference_graph.destruction import (
        destruction_walk,
    )
    from define.compiler.validator.reference_graph.particles import particle_info


class KnownAtDestruction(msgspec.Struct, frozen=True):
    """The state at the moment of destruction of a position a Destructor requirement is on, as the actions up to this one recorded it."""

    # From this action's perspective, below the destroyed particle.
    position: ast.PositionReference
    position_in_child_state: chained_name.ChainedNameTuple
    occupancy: position_occupancy.ChildOccupancy
    value_state: particle_info.ParticleValueState | None


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


class DestructorExecution(CalleeExecution, frozen=True):
    """One execution of a Destructor, at the moment its particle is destroyed."""

    # A Destructor always triggers on the particle being destroyed.
    parent_particle: particle_info.ParticleInfo

    @property
    @typing.override
    def action_assignment(self) -> action_contract.ActionAssignment:
        return action_contract.ActionAssignment(
            quality=self.action_chain.get_last_action(),
            assigned_to_position_name=self.parent_particle.origin_position.typed_names[
                -1
            ],
        )


class DestructorCalleeExecution(DestructorExecution, frozen=True):
    """One execution of a Destructor that this action directly knows."""

    # The local position whose Automatic Destruction destroys the particle,
    # or None for a Destroy.
    auto_destruction_target: ast.PositionReference | None

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
            acting_on_position=self.acting_on_position,
            destroyed_particle=self.parent_particle,
            action_assignment=self.action_assignment,
            auto_destruction_target=self.auto_destruction_target,
        )


class DestructorInCalleeExecution(DestructorExecution, frozen=True):
    """One execution of a Destructor that ran when a callee destroyed its particle, which the lowest action that knows the Destructor is on the particle validates."""

    # The particle of the callee's Destruction Contract that the destroyed
    # particle is at or below.
    root: destruction_walk.DestructionRoot
    state_at_destruction: destruction_walk.CalleeStateAtDestruction

    @property
    @typing.override
    def diagnostic_location(self) -> ast.SourceLocation:
        return self.state_at_destruction.trigger.callee.location

    def position_in_child_state(
        self, position: ast.PositionReference
    ) -> chained_name.ChainedNameTuple:
        """Return the Child State name of ``position``, a position from this action's perspective at or below the root's particle."""
        return chained_name.with_prefix(
            chained_name.ChainedNameTuple(
                position.canonical_chained_name_tuple[
                    len(self.root.position.typed_names) :
                ]
            ),
            self.root.position_in_child_state,
        )

    def occupancy_at_destruction(
        self,
        requirement: action_contract.PositionOccupancyRequirement,
    ) -> KnownAtDestruction | ast.PositionReference:
        """Return the occupancy that the actions up to this one recorded for the position ``requirement`` is on at the moment of destruction, or, when they recorded none, where that position was when this action triggered the callee."""
        state = self.state_at_destruction
        position = requirement.position.in_caller(self.action_chain)
        position_in_child_state = self.position_in_child_state(position)
        occupancy = state.child_state.occupancy_at(position_in_child_state)
        if occupancy is None:
            return state.position_in_caller(position, position_in_child_state)
        return KnownAtDestruction(
            position=position,
            position_in_child_state=position_in_child_state,
            occupancy=occupancy,
            value_state=None,
        )

    def value_at_destruction(
        self,
        requirement: action_contract.ValueRequirement,
    ) -> KnownAtDestruction | ast.PositionReference:
        """Return the occupancy and value that the actions up to this one recorded for the position ``requirement`` is on at the moment of destruction, or, when they did not record enough to decide it, where that position was when this action triggered the callee."""
        state = self.state_at_destruction
        position = requirement.position.in_caller(self.action_chain)
        position_in_child_state = self.position_in_child_state(position)
        occupancy = state.child_state.occupancy_at(position_in_child_state)
        if occupancy is None:
            return state.position_in_caller(position, position_in_child_state)
        value_state = state.child_state.value_at(position_in_child_state)
        if (
            occupancy.state == position_occupancy.PositionOccupancyState.OCCUPIED
            and value_state is None
        ):
            return state.position_in_caller(position, position_in_child_state)
        return KnownAtDestruction(
            position=position,
            position_in_child_state=position_in_child_state,
            occupancy=occupancy,
            value_state=value_state,
        )

    def requirement_in_caller[Requirement: action_contract.PositionRequirement](
        self, requirement: Requirement, caller_position: ast.PositionReference
    ) -> action_contract.PositionRequirementInCaller[Requirement]:
        """Return ``requirement`` at ``caller_position``, a position from this action's perspective, with this execution's action assignment."""
        return action_contract.PositionRequirementInCaller(
            requirement=requirement,
            caller_position=caller_position,
            action_assignment=self.action_assignment,
        )

    def callee_requirement_in_caller[Requirement: action_contract.PositionRequirement](
        self, requirement: Requirement, caller_position: ast.PositionReference
    ) -> action_contract.PositionRequirementInCaller[Requirement]:
        """Return ``requirement``, one of the Destructor's, as a requirement of the callee at ``caller_position``, a position from this action's perspective."""
        return self.requirement_in_caller(
            self.requirement_of_callee(requirement), caller_position
        )

    def violation_at_destruction(
        self,
        requirement: action_contract.PositionRequirement,
        at_destruction: KnownAtDestruction,
        definition: ast.ActionDefinition,
    ) -> diagnostics.InferredRequirementViolationDiagnostic | None:
        """Return the diagnostic for ``requirement``, one of the Destructor's, if the state ``at_destruction`` recorded at the moment of destruction violates it."""
        if not requirement_violation.is_violated(
            requirement, at_destruction.occupancy.state, at_destruction.value_state
        ):
            return None
        return self.destruction_requirement_violation(
            requirement, at_destruction.position, at_destruction.occupancy, definition
        )

    def requirement_of_callee[Requirement: action_contract.PositionRequirement](
        self, requirement: Requirement
    ) -> Requirement:
        """Return ``requirement``, one of the Destructor's, as a requirement of the callee: the destroyer's requirement, propagated through each action between the callee and the destroyer."""
        destruction_fact = self.root.destruction_fact
        return self.state_at_destruction.callee_contracts.destroyer_requirement_as_callee_requirement(
            requirement.propagated_to(
                destruction_fact.destroying_definition,
                inferred_at=destruction_fact.directly_destroyed_position.location,
                position=requirement.position.in_caller(
                    destruction_fact.destroyed_position_in_destroyer
                ),
                action_assignment=None,
            )
        )

    @typing.override
    def requirement_violation(
        self,
        requirement: action_contract.PositionRequirement,
        position_in_caller: ast.PositionReference,
        occupant: particle_info.ParticleInfo | None,
        definition: ast.ActionDefinition,
    ) -> diagnostics.InferredRequirementViolationDiagnostic:
        return self.destruction_requirement_violation(
            requirement,
            position_in_caller,
            position_occupancy.EMPTY_OCCUPANCY
            if occupant is None
            else position_occupancy.ChildOccupancy(
                position_occupancy.PositionOccupancyState.OCCUPIED,
                filled_at=occupant.last_position.location,
            ),
            definition,
        )

    def destruction_requirement_violation(
        self,
        requirement: action_contract.PositionRequirement,
        position: ast.PositionReference,
        occupancy: position_occupancy.ChildOccupancy,
        definition: ast.ActionDefinition,
    ) -> diagnostics.InferredRequirementViolationDiagnostic:
        """Return the diagnostic for ``requirement``, one of the Destructor's on ``position``, which ``occupancy`` at the moment of destruction violates."""
        return requirement_violation.contract_destructor(
            propagated_requirement=requirement,
            resolved_position=position,
            occupancy=occupancy,
            definition=definition,
            destruction_fact=self.root.destruction_fact,
            propagation_steps=self.state_at_destruction.callee_contracts.propagation_steps(),
            particle_position=self.acting_on_position,
            particle=self.parent_particle,
            trigger=self.state_at_destruction.trigger,
            destructor_quality=self.action_chain.get_last_action(),
        )
