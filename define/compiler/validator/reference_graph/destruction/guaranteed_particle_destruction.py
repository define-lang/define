"""What destroying each particle an action leaves below a particle it created takes, for a destroyer that never expands it."""

from __future__ import annotations

import typing

import msgspec

from define.compiler import ast, chained_name
from define.compiler.validator import codegen_input
from define.compiler.validator.reference_graph import action_contract
from define.compiler.validator.reference_graph.destruction import (
    destroyed_particles,
    destruction_contract,
)
from define.compiler.validator.reference_graph.particles import particle_info

if typing.TYPE_CHECKING:
    from define.compiler.data_structures import typed_name_dict
    from define.compiler.validator import validation_result
    from define.compiler.validator.reference_graph import (
        quality_assignment,
        reference_graph_validation_state,
    )
    from define.compiler.validator.reference_graph.particles import (
        particle_tracker,
    )


class GuaranteedParticleDestruction(msgspec.Struct):
    """What destroying each particle an action leaves below a particle it created takes, by its position named as action_contract.GuaranteedPosition.position names positions."""

    # Positions where nothing runs are left out.
    on_destruction: dict[
        chained_name.PositionReferenceTuple, action_contract.OnDestruction
    ] = msgspec.field(default_factory=dict)
    guaranteed_particle_destructors: list[
        codegen_input.GuaranteedParticleDestructors
    ] = msgspec.field(default_factory=list)


def guaranteed_particle_destruction(
    definition: ast.ActionDefinition,
    transitive_implied_qualities: quality_assignment.QualityAssignments,
    definition_results: typed_name_dict.TypedNameDict[
        ast.GlobalTypedName[ast.GlobalNameContent[ast.Fqun | None]],
        validation_result.DefinitionValidationResult,
    ],
    validation_state: reference_graph_validation_state.ReferenceGraphValidationState,
    tracker: particle_tracker.ParticleTracker,
) -> GuaranteedParticleDestruction:
    """Return, for each particle the action leaves in a child position of a particle it created, what a destroyer that never expands it has to do: nothing, run the action's method for it, or expand it.

    Judged from the action's final state.
    """
    return _GuaranteedParticleDestructionBuilder(
        definition,
        destroyed_particles.DestroyedParticles(tracker, definition_results),
        validation_state,
        tracker,
    ).build(transitive_implied_qualities)


@typing.final
class _GuaranteedParticleDestructionBuilder:
    def __init__(
        self,
        definition: ast.ActionDefinition,
        destroyed_particles: destroyed_particles.DestroyedParticles,
        validation_state: reference_graph_validation_state.ReferenceGraphValidationState,
        tracker: particle_tracker.ParticleTracker,
    ):
        self._definition = definition
        self._destroyed_particles = destroyed_particles
        self._validation_state = validation_state
        self._tracker = tracker

    def build(
        self, transitive_implied_qualities: quality_assignment.QualityAssignments
    ) -> GuaranteedParticleDestruction:
        positions: list[ast.PositionReference] = []
        for interface_position in self._definition.interface_positions:
            positions.append(
                ast.PositionReference(
                    location=interface_position.location,
                    typed_names=(interface_position.typed_name,),
                )
            )
        implied_child_names, _ = self._destroyed_particles.child_names_and_destructors(
            transitive_implied_qualities.assignments
        )
        for names in implied_child_names:
            positions.append(
                ast.PositionReference(location=names[0].location, typed_names=names)
            )
        action_chain = chained_name.action(
            (self._definition.typed_name.full_typed_name,)
        )
        destruction = GuaranteedParticleDestruction()
        for position in positions:
            # A caller always applies the Guarantee on a contracted position,
            # so nothing there is left unexpanded.
            occupancy = self._tracker.get_occupancy_info(position)
            # This action's errors are already reported, and a destroyer
            # skips the positions they mark.
            if occupancy.has_error or occupancy.occupant is None:
                continue
            self._visit_guaranteed_position(
                position,
                occupancy.occupant,
                chained_name.in_caller(
                    action_chain, position.canonical_chained_name_tuple
                ),
                destruction,
            )
        return destruction

    def _visit_guaranteed_position(
        self,
        position: ast.PositionReference,
        particle: particle_info.ParticleInfo,
        position_in_action: chained_name.PositionReferenceTuple,
        destruction: GuaranteedParticleDestruction,
    ):
        """Decide what destroying each particle below a particle the action created, at or below ``particle`` in ``position``, takes, and record it in ``destruction``.

        No particle the action created is above ``particle``.
        """
        child_names, _ = self._destroyed_particles.child_names_and_destructors(
            particle.qualities.assignments
        )
        for names in child_names:
            child_position = position.with_position_suffix(*names)
            child_in_action = _with_names(position_in_action, names)
            found = self._destroyed_particles.particle_or_unexpanded_destruction_at(
                child_position, particle
            )
            if found is None:
                continue
            if particle.source is particle_info.ParticleSource.CALLER:
                # A particle from the caller never has what a callee left
                # below it unexpanded.
                self._visit_guaranteed_position(
                    child_position,
                    typing.cast("particle_info.ParticleInfo", found),
                    child_in_action,
                    destruction,
                )
            else:
                _ = self._on_destruction(
                    child_position, found, child_in_action, destruction
                )

    def _on_destruction(
        self,
        position: ast.PositionReference,
        found: destroyed_particles.FoundInChildPosition,
        position_in_action: chained_name.PositionReferenceTuple,
        destruction: GuaranteedParticleDestruction,
    ) -> (
        destruction_contract.RunGuaranteedParticleDestructors
        | action_contract.OnDestruction
    ):
        """Return what destroying ``found``, the particle in ``position`` or what a callee left there, and everything below it takes: the call that runs its Destructors, or whether it takes nothing or has to be expanded.

        What it takes is recorded in ``destruction`` for the particle and for
        each particle below it, unless it takes nothing; a method that runs
        Destructors is added only for what takes RUN_DESTRUCTORS.
        """
        if not isinstance(found, particle_info.ParticleInfo):
            # What a callee left that it could not decide stays EXPAND here
            # without being expanded: this action's state below it is the
            # callee's, so deciding again would only repeat the callee's work.
            return found
        if found.source is particle_info.ParticleSource.CALLER:
            # A particle from the caller is never in a map: a caller always
            # applies its Guarantee, so destroying it always takes EXPAND.
            self._visit_guaranteed_position(
                position, found, position_in_action, destruction
            )
            return action_contract.OnDestruction.EXPAND
        child_names, destructors = (
            self._destroyed_particles.child_names_and_destructors(
                found.qualities.assignments
            )
        )
        on_destruction_for_own_destructors, published_destructors = (
            self._on_destruction_for_own_destructors(position, destructors)
        )
        on_destruction_for_particles_below, for_child_positions = (
            self._on_destruction_for_particles_below(
                position, found, child_names, position_in_action, destruction
            )
        )
        on_destruction = _on_destruction_needing_the_most_work(
            on_destruction_for_own_destructors, on_destruction_for_particles_below
        )
        if on_destruction == action_contract.OnDestruction.NOTHING:
            return on_destruction
        destruction.on_destruction[position_in_action] = on_destruction
        if on_destruction != action_contract.OnDestruction.RUN_DESTRUCTORS:
            return on_destruction
        destruction.guaranteed_particle_destructors.append(
            codegen_input.GuaranteedParticleDestructors(
                position_in_action=position_in_action,
                destructors=published_destructors,
                for_child_positions=for_child_positions,
            )
        )
        return destruction_contract.RunGuaranteedParticleDestructors(
            position=position,
            action=self._definition.typed_name,
            position_in_action=position_in_action,
        )

    def _on_destruction_for_own_destructors(
        self,
        position: ast.PositionReference,
        destructors: list[ast.GlobalTypedNameReference],
    ) -> tuple[action_contract.OnDestruction, list[ast.GlobalTypedNameReference]]:
        """Return what running ``destructors``, the Destructors on the particle in ``position``, takes, and those of them that have a contract.

        RUN_DESTRUCTORS when every one of them can run as this action leaves
        the particle, EXPAND when one of them cannot, NOTHING when there are
        none.
        """
        on_destruction = action_contract.OnDestruction.NOTHING
        published_destructors: list[ast.GlobalTypedNameReference] = []
        for destructor in destructors:
            # A circular reference, already reported, leaves a Destructor's
            # contract unpublished, and a destroyer skips such a Destructor
            # too.
            contract = self._validation_state.get_contract_or_none(destructor)
            if contract is None:
                continue
            published_destructors.append(destructor)
            on_destruction = _on_destruction_needing_the_most_work(
                on_destruction,
                action_contract.OnDestruction.RUN_DESTRUCTORS
                if self._destructor_requirements_hold(position, destructor, contract)
                else action_contract.OnDestruction.EXPAND,
            )
        return on_destruction, published_destructors

    def _on_destruction_for_particles_below(
        self,
        position: ast.PositionReference,
        particle: particle_info.ParticleInfo,
        child_names: list[tuple[ast.TypedNameReference, ...]],
        position_in_action: chained_name.PositionReferenceTuple,
        destruction: GuaranteedParticleDestruction,
    ) -> tuple[
        action_contract.OnDestruction,
        list[destruction_contract.RunGuaranteedParticleDestructors],
    ]:
        """Return what destroying the particles in the child positions of ``particle``, in ``position``, takes, and the calls that run the Destructors of those that take RUN_DESTRUCTORS."""
        on_destruction = action_contract.OnDestruction.NOTHING
        for_child_positions: list[
            destruction_contract.RunGuaranteedParticleDestructors
        ] = []
        for names in child_names:
            child_position = position.with_position_suffix(*names)
            found = self._destroyed_particles.particle_or_unexpanded_destruction_at(
                child_position, particle
            )
            if found is None:
                continue
            on_destruction_of_child = self._on_destruction(
                child_position,
                found,
                _with_names(position_in_action, names),
                destruction,
            )
            if isinstance(
                on_destruction_of_child,
                destruction_contract.RunGuaranteedParticleDestructors,
            ):
                # The call is in the method for the particle in ``position``,
                # so it names the child position from that particle.
                for_child_positions.append(
                    msgspec.structs.replace(
                        on_destruction_of_child,
                        position=ast.PositionReference(
                            location=child_position.location, typed_names=names
                        ),
                    )
                )
                on_destruction_of_child = action_contract.OnDestruction.RUN_DESTRUCTORS
            on_destruction = _on_destruction_needing_the_most_work(
                on_destruction, on_destruction_of_child
            )
        return on_destruction, for_child_positions

    def _destructor_requirements_hold(
        self,
        position: ast.PositionReference,
        destructor: ast.GlobalTypedNameReference,
        contract: action_contract.ActionContract,
    ) -> bool:
        """Return whether this action's final state satisfies the requirements of a Destructor on the particle in ``position``."""
        # A caller may still satisfy them before destroying the particle, so
        # only the destroyer can tell whether they fail. It checks them again,
        # and reports any failure, after applying this action's Guarantees.
        action_chain = chained_name.action(
            (*position.canonical_chained_name_tuple, destructor.full_typed_name)
        )
        for occupancy_requirement in contract.occupancy_requirements:
            occupancy, _ = self._tracker.state_without_expanding_by_key(
                chained_name.in_caller(
                    action_chain,
                    occupancy_requirement.position.canonical_chained_name_tuple,
                )
            )
            if occupancy_requirement.is_violated_by(occupancy):
                return False
        for value_requirement in contract.value_requirements:
            occupancy, value_state = self._tracker.state_without_expanding_by_key(
                chained_name.in_caller(
                    action_chain,
                    value_requirement.position.canonical_chained_name_tuple,
                )
            )
            if value_requirement.is_violated_by(occupancy, value_state):
                return False
        return True


# Each is what a destroyer has to do for a particle when the one before it
# would not be enough.
_ON_DESTRUCTION_BY_WORK: typing.Final = (
    action_contract.OnDestruction.NOTHING,
    action_contract.OnDestruction.RUN_DESTRUCTORS,
    action_contract.OnDestruction.EXPAND,
)


def _on_destruction_needing_the_most_work(
    first: action_contract.OnDestruction, second: action_contract.OnDestruction
) -> action_contract.OnDestruction:
    """Return whichever of ``first`` and ``second`` asks more of a destroyer: EXPAND over RUN_DESTRUCTORS over NOTHING."""
    return max(first, second, key=_ON_DESTRUCTION_BY_WORK.index)


def _with_names(
    position_in_action: chained_name.PositionReferenceTuple,
    names: tuple[ast.TypedNameReference, ...],
) -> chained_name.PositionReferenceTuple:
    """Return the child position ``names`` of ``position_in_action``."""
    return chained_name.position(
        (*position_in_action, *(name.full_typed_name for name in names))
    )
