"""Works out what destroying a particle has to do: its child positions and Destructors, and what each particle an action leaves below a particle it created takes."""

from __future__ import annotations

import typing
from functools import cached_property

import msgspec

from define.compiler import ast, chained_name, name_types
from define.compiler.validator import codegen_input
from define.compiler.validator.reference_graph import (
    action_contract,
    destruction_contract,
)
from define.compiler.validator.reference_graph.particles import particle_info

if typing.TYPE_CHECKING:
    from define.compiler.data_structures import typed_name_dict
    from define.compiler.validator import validation_result
    from define.compiler.validator.reference_graph import (
        action_requirement_validator,
        position_quality_resolver,
        quality_assignment,
        reference_graph_validation_state,
    )
    from define.compiler.validator.reference_graph.particles import (
        particle_tracker,
    )


class ChildPositionsAndDestructors(msgspec.Struct, frozen=True):
    """A particle's child positions and its Destructors, as destruction sees them."""

    child_positions: list[ast.PositionReference]
    destructors: list[ast.GlobalTypedNameReference]


class GuaranteedParticleDestruction(msgspec.Struct):
    """What destroying each particle an action leaves below a particle it created takes, by its position named as action_contract.GuaranteedPosition.position names positions."""

    # Positions where nothing runs are left out.
    on_destruction: dict[
        chained_name.PositionReferenceTuple, action_contract.OnDestruction
    ] = msgspec.field(default_factory=dict)
    guaranteed_particle_destructors: list[
        codegen_input.GuaranteedParticleDestructors
    ] = msgspec.field(default_factory=list)


class DestructionPlanner:
    """Works out what destroying a particle has to do, for the action being validated."""

    _definition: ast.ActionDefinition
    _implied_qualities: tuple[ast.GlobalTypedNameReference, ...]
    _definition_results: typed_name_dict.TypedNameDict[
        ast.GlobalTypedName[ast.GlobalNameContent[ast.Fqun | None]],
        validation_result.DefinitionValidationResult,
    ]
    _validation_state: reference_graph_validation_state.ReferenceGraphValidationState
    _tracker: particle_tracker.ParticleTracker
    _quality_resolver: position_quality_resolver.PositionQualityResolver
    _requirement_validator: action_requirement_validator.ActionRequirementValidator

    def __init__(
        self,
        definition: ast.ActionDefinition,
        implied_qualities: tuple[ast.GlobalTypedNameReference, ...],
        definition_results: typed_name_dict.TypedNameDict[
            ast.GlobalTypedName[ast.GlobalNameContent[ast.Fqun | None]],
            validation_result.DefinitionValidationResult,
        ],
        validation_state: reference_graph_validation_state.ReferenceGraphValidationState,
        tracker: particle_tracker.ParticleTracker,
        quality_resolver: position_quality_resolver.PositionQualityResolver,
        requirement_validator: action_requirement_validator.ActionRequirementValidator,
    ):
        """Initialize with the action being validated and the state its validator tracks."""
        self._definition = definition
        self._implied_qualities = implied_qualities
        self._definition_results = definition_results
        self._validation_state = validation_state
        self._tracker = tracker
        self._quality_resolver = quality_resolver
        self._requirement_validator = requirement_validator

    @cached_property
    def _transitive_implied_qualities(self) -> quality_assignment.QualityAssignments:
        return self._quality_resolver.get_transitive_implied_qualities(
            self._implied_qualities
        )

    def guaranteed_particle_destruction(self) -> GuaranteedParticleDestruction:
        """Return, for each particle this action leaves in a child position of a particle it created, what a destroyer that never expands it has to do: nothing, run this action's method for it, or expand it.

        Judged from the action's final state.
        """
        destruction = GuaranteedParticleDestruction()
        action_chain = chained_name.action(
            (self._definition.typed_name.full_typed_name,)
        )
        for definition in self._definition.interface_positions:
            position = ast.PositionReference(
                location=definition.location, typed_names=(definition.typed_name,)
            )
            self._visit_guaranteed_position(
                position,
                chained_name.in_caller(
                    action_chain, position.canonical_chained_name_tuple
                ),
                destruction,
            )
        for child in self._child_positions(
            None, self._transitive_implied_qualities.assignments
        ):
            self._visit_guaranteed_position(
                child,
                chained_name.in_caller(
                    action_chain, child.canonical_chained_name_tuple
                ),
                destruction,
            )
        return destruction

    def _visit_guaranteed_position(
        self,
        position: ast.PositionReference,
        position_in_action: chained_name.PositionReferenceTuple,
        destruction: GuaranteedParticleDestruction,
    ):
        """Find what destroying each particle below a particle the action created at or below ``position`` takes.

        ``position`` is one whose state a caller always applies: no particle
        the action created is above it.
        """
        occupancy = self._tracker.get_occupancy_info(position)
        # This action's errors are already reported, and a destroyer skips the
        # positions they mark.
        if occupancy.has_error or occupancy.occupant is None:
            return
        particle = occupancy.occupant
        for child in self._child_positions(position, particle.qualities.assignments):
            child_in_action = _with_names_after(position, child, position_in_action)
            if particle.source is particle_info.ParticleSource.CALLER:
                self._visit_guaranteed_position(child, child_in_action, destruction)
            else:
                _ = self._on_destruction_of_child(child, child_in_action, destruction)

    def _on_destruction_of_child(
        self,
        position: ast.PositionReference,
        position_in_action: chained_name.PositionReferenceTuple,
        destruction: GuaranteedParticleDestruction,
    ) -> (
        destruction_contract.RunGuaranteedParticleDestructors
        | action_contract.OnDestruction
    ):
        """Return what destroying what is at and below ``position`` takes: the call that runs its Destructors, or whether it takes nothing or has to be expanded."""
        unexpanded = self.on_unexpanded_destruction(position)
        if unexpanded is not None:
            return unexpanded
        occupancy = self._tracker.get_occupancy_info(position)
        # This action's errors are already reported, and a destroyer skips the
        # positions they mark.
        if occupancy.has_error or occupancy.occupant is None:
            return action_contract.OnDestruction.NOTHING
        on_destruction = self._on_destruction_of_particle(
            position, position_in_action, occupancy.occupant, destruction
        )
        if on_destruction != action_contract.OnDestruction.RUN_DESTRUCTORS:
            return on_destruction
        return destruction_contract.RunGuaranteedParticleDestructors(
            position=position,
            action=self._definition.typed_name,
            position_in_action=position_in_action,
        )

    def on_unexpanded_destruction(
        self, position: ast.PositionReference
    ) -> (
        destruction_contract.RunGuaranteedParticleDestructors
        | action_contract.OnDestruction
        | None
    ):
        """Return what destroying what a callee left at and below ``position`` takes, when this action never expanded it: the call that runs its Destructors, or whether it takes nothing or has to be expanded.

        None when this action has expanded what is at ``position``.
        """
        left = self._tracker.unexpanded_entry(position)
        if left is None:
            return None
        particles, left_here = left
        if left_here is None:
            return action_contract.OnDestruction.NOTHING
        if left_here.on_destruction != action_contract.OnDestruction.RUN_DESTRUCTORS:
            return left_here.on_destruction
        return destruction_contract.RunGuaranteedParticleDestructors(
            position=position,
            action=particles.action,
            position_in_action=typing.cast(
                "chained_name.PositionReferenceTuple",
                left_here.guaranteed_particle_destructors_position,
            ),
        )

    def _on_destruction_of_particle(
        self,
        position: ast.PositionReference,
        position_in_action: chained_name.PositionReferenceTuple,
        particle: particle_info.ParticleInfo,
        destruction: GuaranteedParticleDestruction,
    ) -> action_contract.OnDestruction:
        """Return what destroying ``particle``, in ``position``, and everything below it takes.

        What it takes is recorded in ``destruction`` for the particle, and for
        each particle below it, unless it takes nothing; a method that runs
        Destructors is added only for what takes RUN_DESTRUCTORS. A particle
        from the caller is never in a map, so destroying it always takes
        EXPAND.
        """
        if particle.source is particle_info.ParticleSource.CALLER:
            # A caller always applies the Guarantee on a particle from its
            # own state, so the particle is never left for it unexpanded.
            self._visit_guaranteed_position(position, position_in_action, destruction)
            return action_contract.OnDestruction.EXPAND
        on_destruction = action_contract.OnDestruction.NOTHING
        children_and_destructors = self.child_positions_and_destructors(
            position, particle
        )
        destructors: list[ast.GlobalTypedNameReference] = []
        for destructor in children_and_destructors.destructors:
            # A circular reference, already reported, leaves a Destructor's
            # contract unpublished, and a destroyer skips such a Destructor
            # too.
            contract = self._validation_state.get_contract_or_none(destructor)
            if contract is None:
                continue
            destructors.append(destructor)
            on_destruction = action_contract.OnDestruction.RUN_DESTRUCTORS
        # Checking a Destructor can expand what a callee left below the
        # particle. Doing that before the child positions are visited makes
        # every particle below it one this action publishes itself, with what
        # destroying it takes recorded here. Expanding afterward would publish
        # particles whose entries were never recorded.
        for destructor in destructors:
            if not self._destructor_requirements_satisfied(position, destructor):
                on_destruction = action_contract.OnDestruction.EXPAND
        for_child_positions: list[
            destruction_contract.RunGuaranteedParticleDestructors
        ] = []
        for child in children_and_destructors.child_positions:
            of_child = self._on_destruction_of_child(
                child,
                _with_names_after(position, child, position_in_action),
                destruction,
            )
            if isinstance(
                of_child, destruction_contract.RunGuaranteedParticleDestructors
            ):
                for_child_positions.append(of_child)
                if on_destruction == action_contract.OnDestruction.NOTHING:
                    on_destruction = action_contract.OnDestruction.RUN_DESTRUCTORS
            elif of_child == action_contract.OnDestruction.EXPAND:
                on_destruction = action_contract.OnDestruction.EXPAND
        if on_destruction == action_contract.OnDestruction.NOTHING:
            return on_destruction
        destruction.on_destruction[position_in_action] = on_destruction
        if on_destruction == action_contract.OnDestruction.RUN_DESTRUCTORS:
            destruction.guaranteed_particle_destructors.append(
                codegen_input.GuaranteedParticleDestructors(
                    position=position,
                    position_in_action=position_in_action,
                    destructors=destructors,
                    for_child_positions=for_child_positions,
                )
            )
        return on_destruction

    def _child_positions(
        self,
        position: ast.PositionReference | None,
        qualities: tuple[ast.GlobalTypedNameReference, ...],
    ) -> list[ast.PositionReference]:
        """Return the child positions that ``qualities`` give the particle in ``position``, or the action's parent particle when it is None."""
        child_positions: list[ast.PositionReference] = []
        for quality in qualities:
            if quality.name_type == name_types.NameType.POSITION:
                child_positions.append(_with_suffix(position, quality))
            elif quality.name_type == name_types.NameType.ACTION:
                definition_result = self._definition_results.get(quality)
                # Reference validation has already reported unresolved qualities;
                # their absence must not prevent checking the remaining Destructors.
                if definition_result is None:
                    continue
                definition = typing.cast(
                    "ast.ActionDefinition", definition_result.definition
                )
                for interface_position in definition.interface_positions:
                    child_positions.append(
                        _with_suffix(position, quality, interface_position.typed_name)
                    )
        return child_positions

    def child_positions_and_destructors(
        self, position: ast.PositionReference, particle: particle_info.ParticleInfo
    ) -> ChildPositionsAndDestructors:
        """Return the child positions and Destructors of the particle at ``position``."""
        destructors: list[ast.GlobalTypedNameReference] = []
        # A particle keeps its own qualities across Moves, so its qualities (not
        # the current Position's constraints) determine its child Positions and
        # Destructors.
        for quality in particle.qualities.assignments:
            if quality.name_type != name_types.NameType.ACTION:
                continue
            definition_result = self._definition_results.get(quality)
            if definition_result is None:
                continue
            definition = typing.cast(
                "ast.ActionDefinition", definition_result.definition
            )
            if definition.is_destructor:
                destructors.append(quality)
        return ChildPositionsAndDestructors(
            child_positions=self._child_positions(
                position, particle.qualities.assignments
            ),
            destructors=destructors,
        )

    def _destructor_requirements_satisfied(
        self,
        position: ast.PositionReference,
        destructor: ast.GlobalTypedNameReference,
    ) -> bool:
        """Return whether this action's final state satisfies the requirements of a Destructor on a particle it leaves behind, without reporting anything."""
        # A caller may still satisfy them before destroying the particle, so
        # only the destroyer can tell whether they fail. It checks them again,
        # and reports any failure, after applying this action's Guarantees.
        contract = self._validation_state.get_contract(destructor)
        action_chain = position.with_action_suffix(destructor)
        return self._requirement_validator.requirements_satisfied(
            contract.occupancy_requirements_in_caller(action_chain),
            contract.value_requirements_in_caller(action_chain),
        )


def _with_suffix(
    position: ast.PositionReference | None,
    *typed_names: ast.TypedNameReference,
) -> ast.PositionReference:
    if position is None:
        return ast.PositionReference(
            location=typed_names[0].location, typed_names=typed_names
        )
    return position.with_position_suffix(*typed_names)


def _with_names_after(
    position: ast.PositionReference,
    child: ast.PositionReference,
    position_in_action: chained_name.PositionReferenceTuple,
) -> chained_name.PositionReferenceTuple:
    """Return ``child``, a child position of ``position``, named as ``position_in_action`` names ``position``."""
    child_in_action = [*position_in_action]
    for typed_name in child.typed_names[len(position.typed_names) :]:
        child_in_action.append(typed_name.full_typed_name)
    return chained_name.position(tuple(child_in_action))
