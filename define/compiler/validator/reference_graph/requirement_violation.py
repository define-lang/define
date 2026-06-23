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
from define.compiler.validator.reference_graph import action_contract, particle_tracker


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
) -> diagnostics.InferredRequirementViolationDiagnostic:
    """Build the diagnostic for an unmet requirement of an action or block this body runs."""
    originating = req.enclosing_quality
    runner_name = originating.typed_name.source_typed_name
    definition_name = definition.typed_name.source_typed_name
    position_name = full_caller_chain.source_form_in_universe(
        definition.typed_name.name_content.fqun
    )
    location = acting_on_position.location
    fill = _fill(
        position_name,
        occupant.last_position.location if occupant is not None else None,
    )
    chain = req.propagation_chain()
    if isinstance(originating, ast.ActionDefinition):
        # The fill that violates an empty-requirement happens before the trigger.
        steps = [
            *fill,
            action_contract.PropagationStep(
                location=location,
                kind=action_contract.PropagationKind.ACTION_TRIGGER,
                enclosing_quality_name=definition_name,
                triggered_quality_name=runner_name,
            ),
            *chain,
        ]
        runner_name_type = ast.NameType.ACTION
    else:
        # The block runs first; a destructor it attaches and the fill it performs
        # both happen inside it, the attachment before the fill.
        leading_attachments, rest = _split_leading_attachments(chain)
        steps = [
            action_contract.PropagationStep(
                location=location,
                kind=action_contract.PropagationKind.INIT_BLOCK_TRIGGER,
                enclosing_quality_name=definition_name,
                triggered_quality_name=runner_name,
            ),
            *leading_attachments,
            *fill,
            *rest,
        ]
        runner_name_type = ast.NameType.POSITION
    return _diagnostic(
        location=location,
        position_name=position_name,
        required_empty=req.required_state
        == action_contract.PositionOccupancyState.EMPTY,
        runner_name=runner_name,
        runner_name_type=runner_name_type,
        steps=steps,
    )


def direct_destructor(
    *,
    req: action_contract.PositionRequirement,
    definition: ast.QualityDefinition,
    full_caller_chain: ast.PositionReference,
    acting_on_position: ast.PositionReference,
    occupant: particle_tracker.ParticleInfo | None,
    destroy_target_origin_at: ast.SourceLocation | None,
    auto_destruction_target: ast.PositionReference | None,
    attachment: action_contract.DestructorAttachment | None,
) -> diagnostics.InferredRequirementViolationDiagnostic:
    """Build the diagnostic for an unmet requirement of a destructor this body fires."""
    if destroy_target_origin_at is None:
        raise ValueError("a destructor violation must know its particle's origin")
    enclosing_fqun = definition.typed_name.name_content.fqun
    definition_name = definition.typed_name.source_typed_name
    destructor_name = req.root_cause_quality_name()
    position_name = full_caller_chain.source_form_in_universe(enclosing_fqun)
    if auto_destruction_target is None:
        location = acting_on_position.location
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
    # The destructor is attached when the particle is created, so its attachment
    # and origin lead; auto-destruction (if any) happens at block end, just
    # before the destruction that fires the destructor.
    steps = [
        *_attachment(attachment, destructor_name),
        action_contract.PropagationStep(
            location=destroy_target_origin_at,
            kind=action_contract.PropagationKind.PARTICLE_ORIGIN,
            enclosing_quality_name=acting_on_position.source_form_in_universe(
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
        runner_name=destructor_name,
        runner_name_type=ast.NameType.ACTION,
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
    acting_position: ast.PositionReference,
    attachment: action_contract.DestructorAttachment | None,
) -> diagnostics.InferredRequirementViolationDiagnostic:
    """Build the diagnostic for an unmet requirement of a destructor surfaced via a Destruction Contract."""
    enclosing_fqun = definition.typed_name.name_content.fqun
    cascade_req = action_contract.PositionRequirement(
        required_state=propagated_requirement.required_state,
        inferred_from=destruction_contract.destroyed_position_local,
        enclosing_quality=destroying_definition,
        propagated_from=propagated_requirement,
        destructor_attachment=attachment,
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
    leading_attachments, rest = _split_leading_attachments(
        cascade_req.propagation_chain()
    )
    # The caller attaches the destructor and creates the particle, then triggers
    # the action whose destruction (or auto-destruction) fires the destructor.
    if destruction_contract.is_auto_destruction:
        # The particle is destroyed implicitly at the block's end, so the
        # destructor itself is the runner the requirement gates.
        runner_name = cascade_req.root_cause_quality_name()
        diagnostic_location = particle.last_position.location
        runner_step = _auto(
            _AutoDestruction(
                local_position_name=destruction_contract.destroyed_position_local.source_form_in_universe(
                    enclosing_fqun
                ),
                containing_definition_name=destruction_contract.destroying_action.source_typed_name,
                location=destruction_contract.destroyed_position_local.location,
            )
        )
    else:
        diagnostic_location = acting_position.location
        triggered_action = acting_position.get_last_action()
        if triggered_action is None:
            raise ValueError(
                "an explicit Destruction Contract violation must name the"
                + " triggered action"
            )
        runner_name = triggered_action.full_typed_name
        runner_step = [
            action_contract.PropagationStep(
                location=diagnostic_location,
                kind=action_contract.PropagationKind.ACTION_TRIGGER,
                enclosing_quality_name=definition.typed_name.source_typed_name,
                triggered_quality_name=runner_name,
            )
        ]
    steps = [
        *leading_attachments,
        action_contract.PropagationStep(
            location=particle.origin_position.location,
            kind=action_contract.PropagationKind.PARTICLE_ORIGIN,
            enclosing_quality_name=particle_position.source_form_in_universe(
                enclosing_fqun
            ),
            triggered_quality_name=None,
        ),
        *runner_step,
        *_fill(position_name, fill_at),
        *rest,
    ]
    return _diagnostic(
        location=diagnostic_location,
        position_name=position_name,
        required_empty=required_empty,
        runner_name=runner_name,
        runner_name_type=ast.NameType.ACTION,
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


def _attachment(
    attachment: action_contract.DestructorAttachment | None, destructor_name: str
) -> list[action_contract.PropagationStep]:
    if attachment is None:
        return []
    return [
        action_contract.PropagationStep(
            location=attachment.attached_at,
            kind=action_contract.PropagationKind.DESTRUCTOR_ATTACHED,
            enclosing_quality_name=attachment.position.full_typed_name,
            triggered_quality_name=destructor_name,
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


def _split_leading_attachments(
    chain: list[action_contract.PropagationStep],
) -> tuple[
    list[action_contract.PropagationStep], list[action_contract.PropagationStep]
]:
    """Split off the destructor-attachment steps that lead the chain.

    They are encountered when the particle is created, so they precede the fill
    and destruction events that the caller interleaves ahead of the rest.
    """
    rest = list(chain)
    leading: list[action_contract.PropagationStep] = []
    while rest and rest[0].kind == action_contract.PropagationKind.DESTRUCTOR_ATTACHED:
        leading.append(rest.pop(0))
    return leading, rest


def _diagnostic(
    *,
    location: ast.SourceLocation,
    position_name: str,
    required_empty: bool,
    runner_name: str,
    runner_name_type: ast.NameType,
    steps: list[action_contract.PropagationStep],
) -> diagnostics.InferredRequirementViolationDiagnostic:
    return diagnostics.InferredRequirementViolationDiagnostic(
        location=location,
        position_name=position_name,
        propagation_chain=steps,
        required_empty=required_empty,
        runner_name=runner_name,
        runner_name_type=runner_name_type,
    )
