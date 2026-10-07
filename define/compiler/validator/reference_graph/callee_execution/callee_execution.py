"""One execution of a callee, as the action triggering it sees it."""

from __future__ import annotations

import typing

import msgspec

from define.compiler import chained_name
from define.compiler.errors import diagnostics
from define.compiler.validator.reference_graph import (
    action_contract,
    position_occupancy,
)

if typing.TYPE_CHECKING:
    from define.compiler import ast
    from define.compiler.validator.reference_graph.destruction import (
        destruction_walk,
    )
    from define.compiler.validator.reference_graph.particles import particle_info


class KnownAtDestruction(msgspec.Struct, frozen=True):
    """The state at the moment of destruction of a position a Destructor requirement is on, as the actions up to this one recorded it."""

    # From this action's perspective, below the destroyed particle.
    position: ast.PositionReference
    position_in_child_state: chained_name.ChainedNameTuple
    occupancy: position_occupancy.PositionOccupancyState
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
        position_name = position_in_caller.source_form_in_universe(
            definition.typed_name.name_content.fqun
        )
        fill = _fill_steps(
            position_name,
            occupant.last_position.location if occupant is not None else None,
        )
        chain = requirement.propagation_chain()
        trigger_step = action_contract.PropagationStep(
            location=self.acting_on_position.location,
            kind=(
                action_contract.PropagationKind.CONSTRUCTOR_TRIGGER
                if requirement.enclosing_action.is_constructor
                else action_contract.PropagationKind.ACTION_TRIGGER
            ),
            enclosing_quality_name=definition.typed_name.source_typed_name,
            triggered_quality_name=requirement.enclosing_action.typed_name.source_typed_name,
        )
        action_assignment = self.action_assignment
        if action_assignment is not None:
            steps = [
                action_assignment.propagation_step(),
                trigger_step,
                *fill,
                *chain,
            ]
        else:
            # An ordinary action can only trigger after the state satisfying its
            # Trigger Conditions Block already exists.
            steps = [*fill, trigger_step, *chain]
        return _diagnostic(
            location=self.acting_on_position.location,
            position_name=position_name,
            requirement=requirement,
            action_name=requirement.enclosing_action.typed_name.source_typed_name,
            steps=steps,
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

    def assignment_and_origin_steps(
        self, enclosing_fqun: ast.Fqun
    ) -> list[action_contract.PropagationStep]:
        """Return the steps that lead a chain about this Destructor: its assignment to the particle, then where the particle came from, named in ``enclosing_fqun``."""
        # The destructor is assigned when the particle is created, so its
        # assignment and origin lead.
        return [
            self.action_assignment.propagation_step(),
            action_contract.PropagationStep(
                location=self.parent_particle.origin_position.location,
                kind=action_contract.PropagationKind.PARTICLE_ORIGIN,
                enclosing_quality_name=self.acting_on_position.source_form_in_universe(
                    enclosing_fqun
                ),
                triggered_quality_name=None,
            ),
        ]


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
        enclosing_fqun = definition.typed_name.name_content.fqun
        definition_name = definition.typed_name.source_typed_name
        destructor_name = requirement.enclosing_action.typed_name.source_typed_name
        position_name = position_in_caller.source_form_in_universe(enclosing_fqun)
        if self.auto_destruction_target is None:
            location = self.acting_on_position.location
            auto_destruction_steps: list[action_contract.PropagationStep] = []
        else:
            location = self.auto_destruction_target.location
            auto_destruction_steps = [
                _auto_destruction_step(
                    self.auto_destruction_target.source_form_in_universe(
                        enclosing_fqun
                    ),
                    definition_name,
                    location,
                )
            ]
        steps = [
            *self.assignment_and_origin_steps(enclosing_fqun),
            *_fill_steps(
                position_name,
                occupant.last_position.location if occupant is not None else None,
            ),
            # Automatic Destruction happens at block end, just before the
            # destruction that fires the destructor.
            *auto_destruction_steps,
            action_contract.PropagationStep(
                location=location,
                kind=action_contract.PropagationKind.DESTRUCTOR_CASCADE,
                enclosing_quality_name=definition_name,
                triggered_quality_name=destructor_name,
            ),
            *requirement.propagation_chain(),
        ]
        return _diagnostic(
            location=location,
            position_name=position_name,
            requirement=requirement,
            action_name=destructor_name,
            steps=steps,
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
            occupancy == position_occupancy.PositionOccupancyState.OCCUPIED
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

    def requirement_of_destroyer[Requirement: action_contract.PositionRequirement](
        self, requirement: Requirement
    ) -> Requirement:
        """Return ``requirement``, one of the Destructor's, as a requirement of the destroyer, propagated from the Destructor's own requirement."""
        destruction_fact = self.root.destruction_fact
        return requirement.propagated_to(
            destruction_fact.destroying_definition,
            inferred_at=destruction_fact.directly_destroyed_position.location,
            position=requirement.position.in_caller(
                destruction_fact.destroyed_position_in_destroyer
            ),
            action_assignment=None,
        )

    def requirement_of_callee[Requirement: action_contract.PositionRequirement](
        self, requirement: Requirement
    ) -> Requirement:
        """Return ``requirement``, one of the Destructor's, as a requirement of the callee: the destroyer's requirement, propagated through each action between the callee and the destroyer."""
        return self.state_at_destruction.callee_contracts.destroyer_requirement_as_callee_requirement(
            self.requirement_of_destroyer(requirement)
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
            requirement, position_in_caller, definition
        )

    def destruction_requirement_violation(
        self,
        requirement: action_contract.PositionRequirement,
        position: ast.PositionReference,
        definition: ast.ActionDefinition,
    ) -> diagnostics.InferredRequirementViolationDiagnostic:
        """Return the diagnostic for ``requirement``, one of the Destructor's on ``position``, which the state at the moment of destruction violates."""
        enclosing_fqun = definition.typed_name.name_content.fqun
        destruction_fact = self.root.destruction_fact
        trigger = self.state_at_destruction.trigger
        destroyer_requirement = self.requirement_of_destroyer(requirement)
        position_name = position.source_form_in_universe(enclosing_fqun)
        # If the destroyer auto-destroyed the particle at its block's end, that
        # happens after every trigger hop and just before the destructor fires
        # (the same placement a directly known Destructor uses).
        auto_destruction_steps: list[action_contract.PropagationStep] = []
        if destruction_fact.is_automatic:
            auto_destruction_steps.append(
                _auto_destruction_step(
                    destruction_fact.directly_destroyed_position.source_form_in_universe(
                        enclosing_fqun
                    ),
                    destruction_fact.destroying_definition.typed_name.source_typed_name,
                    destruction_fact.directly_destroyed_position.location,
                )
            )
        steps = [
            *self.assignment_and_origin_steps(enclosing_fqun),
            trigger.step(),
            *self.state_at_destruction.callee_contracts.propagation_steps(),
            *auto_destruction_steps,
            *destroyer_requirement.propagation_chain(),
        ]
        # The validating definition's own trigger of the callee is the runner the
        # requirement gates.
        return _diagnostic(
            location=trigger.callee.location,
            position_name=position_name,
            requirement=requirement,
            action_name=trigger.callee.get_last_action().full_typed_name,
            steps=steps,
        )


# Steps in a requirement violation's propagation chain are listed in the order
# they would run if the program executed step by step, which differs by the
# kind of execution, so each execution builds its own chain from these steps.


def _fill_steps(
    position_name: str, fill_at: ast.SourceLocation | None
) -> list[action_contract.PropagationStep]:
    if fill_at is None:
        return []
    return [
        action_contract.PropagationStep(
            location=fill_at,
            kind=action_contract.PropagationKind.FILL_SITE,
            enclosing_quality_name=position_name,
            triggered_quality_name=None,
        )
    ]


def _auto_destruction_step(
    local_position_name: str,
    containing_definition_name: str,
    location: ast.SourceLocation,
) -> action_contract.PropagationStep:
    return action_contract.PropagationStep(
        location=location,
        kind=action_contract.PropagationKind.AUTO_DESTRUCTION,
        enclosing_quality_name=local_position_name,
        triggered_quality_name=containing_definition_name,
    )


def _requires_empty(requirement: action_contract.PositionRequirement) -> bool:
    return (
        isinstance(requirement, action_contract.PositionOccupancyRequirement)
        and not requirement.requires_occupied
    )


def _diagnostic(
    *,
    location: ast.SourceLocation,
    position_name: str,
    requirement: action_contract.PositionRequirement,
    action_name: str,
    steps: list[action_contract.PropagationStep],
) -> diagnostics.InferredRequirementViolationDiagnostic:
    return diagnostics.InferredRequirementViolationDiagnostic(
        location=location,
        position_name=position_name,
        propagation_chain=steps,
        required_empty=_requires_empty(requirement),
        required_value=isinstance(requirement, action_contract.ValueRequirement),
        action_name=action_name,
    )
