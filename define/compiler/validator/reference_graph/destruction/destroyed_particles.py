"""What a Simultaneous Transitive Destruction destroys, from an action's particle state."""

from __future__ import annotations

import typing

from define.compiler import ast, chained_name, name_types
from define.compiler.validator.reference_graph import action_contract
from define.compiler.validator.reference_graph.destruction import destruction_contract
from define.compiler.validator.reference_graph.particles import particle_info

if typing.TYPE_CHECKING:
    from define.compiler.data_structures import typed_name_dict
    from define.compiler.validator import validation_result
    from define.compiler.validator.reference_graph.particles import (
        particle_tracker,
    )


# What a callee left at a child position that the action never expanded: the
# call that runs its Destructors, NOTHING, or EXPAND when destroying it has to
# expand it.
type UnexpandedDestruction = (
    destruction_contract.RunGuaranteedParticleDestructors
    | action_contract.OnDestruction
)
# What destroying a particle finds in one of its child positions: the particle
# there, or what a callee left there that the action never expanded.
type FoundInChildPosition = particle_info.ParticleInfo | UnexpandedDestruction


@typing.final
class DestroyedParticles:
    """What a Simultaneous Transitive Destruction destroys, from one action's particle state."""

    def __init__(
        self,
        tracker: particle_tracker.ParticleTracker,
        definition_results: typed_name_dict.TypedNameDict[
            ast.GlobalTypedName[ast.GlobalNameContent[ast.Fqun | None]],
            validation_result.DefinitionValidationResult,
        ],
    ):
        """Read the particle state ``tracker`` holds."""
        self._tracker = tracker
        self._definition_results = definition_results

    def particle_or_unexpanded_destruction_at(
        self,
        position: ast.PositionReference,
        parent_particle: particle_info.ParticleInfo,
    ) -> FoundInChildPosition | None:
        """Return the particle in ``position``, a child position of ``parent_particle``, or what a callee left there that the action never expanded, or None when nothing there is destroyed."""
        # A particle from the caller is never in a map, so nothing below it
        # was left unexpanded.
        if parent_particle.source is not particle_info.ParticleSource.CALLER:
            unexpanded = self._unexpanded_destruction(position)
            if unexpanded is not None:
                return unexpanded
        return self.particle_destroyed_at(position)

    def child_names_and_destructors(
        self, qualities: tuple[ast.GlobalTypedNameReference, ...]
    ) -> tuple[
        list[tuple[ast.TypedNameReference, ...]], list[ast.GlobalTypedNameReference]
    ]:
        """Return the names of the child positions that ``qualities`` give a particle, after the particle's position, and its Destructors, both in quality order."""
        child_names: list[tuple[ast.TypedNameReference, ...]] = []
        destructors: list[ast.GlobalTypedNameReference] = []
        for quality in qualities:
            if quality.name_type == name_types.NameType.POSITION:
                child_names.append((quality,))
            elif quality.name_type == name_types.NameType.ACTION:
                definition_result = self._definition_results.get(quality)
                # Reference validation has already reported unresolved
                # qualities.
                if definition_result is None:
                    continue
                definition = typing.cast(
                    "ast.ActionDefinition", definition_result.definition
                )
                if definition.is_destructor:
                    destructors.append(quality)
                for interface_position in definition.interface_positions:
                    child_names.append((quality, interface_position.typed_name))
        return child_names, destructors

    def particle_destroyed_at(
        self, position: ast.PositionReference
    ) -> particle_info.ParticleInfo | None:
        """Return the particle a destruction destroys in ``position``, expanding what a callee left there, or None."""
        occupancy = self._tracker.get_occupancy_info(position)
        # This action's errors are already reported, and nothing is destroyed
        # where the state is unknown.
        if occupancy.has_error:
            return None
        return occupancy.occupant

    def _unexpanded_destruction(
        self, position: ast.PositionReference
    ) -> UnexpandedDestruction | None:
        """Return what a callee left at ``position``, a child position, that this action never expanded, or None when there is none."""
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
