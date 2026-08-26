"""Builds inferred-requirement violation diagnostics with execution-ordered chains.

Each function takes the raw context of a violation the validator has already
detected and constructs the whole diagnostic: it renders names, derives the
fill site and required state, assembles the causal stack, and produces the
``InferredRequirementViolationDiagnostic``.

Steps in any propagation chain are listed in the order they would run if the program
executed step by step, which differs depending on the context, so each error type is
its own small recipe.
"""

from __future__ import annotations

from dataclasses import dataclass

from define.compiler import ast, diagnostics
from define.compiler.validator.reference_graph import (
    action_contract,
    particle_tracker,
)


@dataclass(frozen=True, slots=True)
class _AutoDestruction:
    """A particle auto-destroyed at the end of a body, firing the gated destructor."""

    local_position_name: str
    containing_definition_name: str
    location: ast.SourceLocation


def trigger_violation(
    *,
    req: action_contract.PositionRequirement,
    definition: ast.QualityDefinition,
    full_caller_chain: ast.PositionReference,
    acting_on_position: ast.PositionReference,
    occupant: particle_tracker.ParticleInfo | None,
    action_assignment: action_contract.ActionAssignment | None,
) -> diagnostics.InferredRequirementViolationDiagnostic:
    """Build the diagnostic for an unmet requirement of an action this body runs."""
    position_name = full_caller_chain.source_form_in_universe(
        definition.typed_name.name_content.fqun
    )
    fill = _fill(
        position_name,
        occupant.last_position.location if occupant is not None else None,
    )
    chain = req.propagation_chain()
    trigger_step = action_contract.PropagationStep(
        location=acting_on_position.location,
        kind=(
            action_contract.PropagationKind.CONSTRUCTOR_TRIGGER
            if req.enclosing_action.is_constructor
            else action_contract.PropagationKind.ACTION_TRIGGER
        ),
        enclosing_quality_name=definition.typed_name.source_typed_name,
        triggered_quality_name=req.enclosing_action.typed_name.source_typed_name,
    )
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
        location=acting_on_position.location,
        position_name=position_name,
        required_empty=req.required_state
        == action_contract.PositionOccupancyState.EMPTY,
        action_name=req.enclosing_action.typed_name.source_typed_name,
        steps=steps,
    )


def direct_destructor(
    *,
    req: action_contract.PositionRequirement,
    definition: ast.QualityDefinition,
    full_caller_chain: ast.PositionReference,
    occupant: particle_tracker.ParticleInfo | None,
    destructor: action_contract.CascadeDestructor,
    auto_destruction_target: ast.PositionReference | None,
) -> diagnostics.InferredRequirementViolationDiagnostic:
    """Build the diagnostic for an unmet requirement of a destructor this body fires."""
    enclosing_fqun = definition.typed_name.name_content.fqun
    definition_name = definition.typed_name.source_typed_name
    destructor_name = req.root_cause_action_name()
    position_name = full_caller_chain.source_form_in_universe(enclosing_fqun)
    if auto_destruction_target is None:
        location = destructor.position.location
        auto_destruction = None
    else:
        location = auto_destruction_target.location
        auto_destruction = _AutoDestruction(
            local_position_name=auto_destruction_target.source_form_in_universe(
                enclosing_fqun
            ),
            containing_definition_name=definition_name,
            location=location,
        )
    steps = [
        # The destructor is assigned when the particle is created, so its assignment
        # and origin lead; auto-destruction (if any) happens at block end, just before
        # the destruction that fires the destructor.
        destructor.action_assignment().propagation_step(),
        action_contract.PropagationStep(
            location=destructor.origin_position.location,
            kind=action_contract.PropagationKind.PARTICLE_ORIGIN,
            enclosing_quality_name=destructor.position.source_form_in_universe(
                enclosing_fqun
            ),
            triggered_quality_name=None,
        ),
        *_fill(
            position_name,
            occupant.last_position.location if occupant is not None else None,
        ),
        *_auto(auto_destruction),
        action_contract.PropagationStep(
            location=location,
            kind=action_contract.PropagationKind.DESTRUCTOR_CASCADE,
            enclosing_quality_name=definition_name,
            triggered_quality_name=destructor_name,
        ),
        *req.propagation_chain(),
    ]
    return _diagnostic(
        location=location,
        position_name=position_name,
        required_empty=req.required_state
        == action_contract.PositionOccupancyState.EMPTY,
        action_name=destructor_name,
        steps=steps,
    )


def contract_destructor(
    *,
    propagated_requirement: action_contract.PositionRequirement,
    resolved_position: ast.PositionReference,
    occupancy: action_contract.ChildOccupancy,
    definition: ast.QualityDefinition,
    destroying_definition: ast.ActionDefinition,
    destruction_contract: action_contract.DestructionContract,
    particle_position: ast.PositionReference,
    particle: particle_tracker.ParticleInfo,
    trigger_step: action_contract.PropagationStep,
    destructor_quality: ast.GlobalTypedNameReference,
) -> diagnostics.InferredRequirementViolationDiagnostic:
    """Build the diagnostic for an unmet requirement of a destructor surfaced via a Destruction Contract."""
    enclosing_fqun = definition.typed_name.name_content.fqun
    cascade_req = action_contract.PositionRequirement(
        required_state=propagated_requirement.required_state,
        position=propagated_requirement.position.in_caller(
            destruction_contract.destruction_fact.destroyed_position_in_destroyer
        ),
        inferred_at=destruction_contract.destruction_fact.destroyed_position_in_destroyer.location,
        enclosing_action=destroying_definition,
        propagated_from=propagated_requirement,
    )
    position_name = resolved_position.source_form_in_universe(enclosing_fqun)
    required_empty = (
        cascade_req.required_state == action_contract.PositionOccupancyState.EMPTY
    )
    fill_at = occupancy.filled_at if required_empty else None
    if required_empty and fill_at is None:
        raise ValueError(
            "an empty-requirement violation means the position is filled, "
            + "so its fill site must be known"
        )
    action_assignment = action_contract.ActionAssignment(
        quality=destructor_quality,
        assigned_to_position_name=particle.origin_position.typed_names[-1],
    )
    # The verifying definition's own trigger of the callee is the runner the
    # requirement gates; it is the same step that would be prepended if this
    # definition had instead carried the contract higher.
    runner_name = trigger_step.triggered_quality_name
    if runner_name is None:
        raise ValueError(
            "a Destruction Contract violation must name the triggered action"
        )
    # If the destroyer auto-destroyed the particle at its block's end, that
    # happens after every trigger hop and just before the destructor fires (the
    # same placement direct_destructor uses).
    auto_step: list[action_contract.PropagationStep] = []
    if destruction_contract.is_auto_destruction:
        auto_step = _auto(
            _AutoDestruction(
                local_position_name=destruction_contract.destruction_fact.destroyed_position_in_destroyer.source_form_in_universe(
                    enclosing_fqun
                ),
                containing_definition_name=destruction_contract.destruction_fact.destroying_action.source_typed_name,
                location=destruction_contract.destruction_fact.destroyed_position_in_destroyer.location,
            )
        )
    steps = [
        action_assignment.propagation_step(),
        action_contract.PropagationStep(
            location=particle.origin_position.location,
            kind=action_contract.PropagationKind.PARTICLE_ORIGIN,
            enclosing_quality_name=particle_position.source_form_in_universe(
                enclosing_fqun
            ),
            triggered_quality_name=None,
        ),
        trigger_step,
        *_fill(position_name, fill_at),
        *destruction_contract.trigger_chain,
        *auto_step,
        *cascade_req.propagation_chain(),
    ]
    return _diagnostic(
        location=trigger_step.location,
        position_name=position_name,
        required_empty=required_empty,
        action_name=runner_name,
        steps=steps,
    )


def _fill(
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


def _auto(
    auto_destruction: _AutoDestruction | None,
) -> list[action_contract.PropagationStep]:
    if auto_destruction is None:
        return []
    return [
        action_contract.PropagationStep(
            location=auto_destruction.location,
            kind=action_contract.PropagationKind.AUTO_DESTRUCTION,
            enclosing_quality_name=auto_destruction.local_position_name,
            triggered_quality_name=auto_destruction.containing_definition_name,
        )
    ]


def _diagnostic(
    *,
    location: ast.SourceLocation,
    position_name: str,
    required_empty: bool,
    action_name: str,
    steps: list[action_contract.PropagationStep],
) -> diagnostics.InferredRequirementViolationDiagnostic:
    return diagnostics.InferredRequirementViolationDiagnostic(
        location=location,
        position_name=position_name,
        propagation_chain=steps,
        required_empty=required_empty,
        action_name=action_name,
    )
