"""Destroy particles as an operation of the action being validated."""

from __future__ import annotations

import typing

import msgspec

from define.compiler import ast, chained_name
from define.compiler.validator.reference_graph import (
    action_contract,
    quality_assignment,
)
from define.compiler.validator.reference_graph.callee_execution import (
    callee_execution,
)
from define.compiler.validator.reference_graph.destruction import (
    destruction_contract,
    destruction_walk,
)

if typing.TYPE_CHECKING:
    from collections.abc import Sequence

    from define.compiler.data_structures import typed_name_dict
    from define.compiler.errors import diagnostics
    from define.compiler.validator import scope_tracker, validation_result
    from define.compiler.validator.reference_graph import (
        reference_graph_validation_state,
    )
    from define.compiler.validator.reference_graph.callee_execution import (
        callee_execution_validator,
    )
    from define.compiler.validator.reference_graph.particles import (
        particle_tracker,
    )


class DestroyResult(msgspec.Struct):
    """What destroying a set of particles produces."""

    contribution: destruction_contract.DestructionContribution
    destruction_contracts: list[action_contract.DestructionContracts]
    # From the Destructors the destruction triggers.
    diagnostics: list[diagnostics.Diagnostic]


@typing.final
class Destroyer:
    """Destroys particles for the action being validated."""

    def __init__(
        self,
        definition: ast.ActionDefinition,
        definition_results: typed_name_dict.TypedNameDict[
            ast.GlobalTypedName[ast.GlobalNameContent[ast.Fqun | None]],
            validation_result.DefinitionValidationResult,
        ],
        tracker: particle_tracker.ParticleTracker,
        callee_execution_validator: callee_execution_validator.CalleeExecutionValidator,
        validation_state: reference_graph_validation_state.ReferenceGraphValidationState,
    ):
        """Destroy particles for ``definition`` in the state ``tracker`` holds."""
        self._definition = definition
        self._walker = destruction_walk.DestructionWalker(
            tracker, definition_results, validation_state
        )
        self._tracker = tracker
        self._callee_execution_validator = callee_execution_validator

    def destroy(
        self, position: ast.PositionReference, scope: scope_tracker.ScopeTracker
    ) -> DestroyResult:
        """Destroy the particle in ``position``, as a Destroy statement does, with every particle below it, and return what the destruction produces."""
        return self._destroy_simultaneously([position], scope, is_automatic=False)

    def destroy_automatically(
        self,
        local_position_names: Sequence[ast.LocalTypedNameReference],
        scope: scope_tracker.ScopeTracker,
    ) -> DestroyResult:
        """Destroy the particles still in the positions ``local_position_names`` name, the positions defined only in a block that is ending, simultaneously, with every particle below them, and return what the destruction produces."""
        occupied_positions: list[ast.PositionReference] = []
        for name in local_position_names:
            # TODO: Give TypedName an as_position_reference() method, located
            # at the typed name, and use it wherever a reference to a single
            # name is built like this.
            position = ast.PositionReference(
                location=name.location, typed_names=(name,)
            )
            # Spec: "If the compiler is uncertain about whether a position
            # still contains a particle, it only destroys the particle if one
            # is present."
            occupancy = self._tracker.get_occupancy_info(position)
            if occupancy.has_error or occupancy.occupant is None:
                continue
            occupied_positions.append(position)
        return self._destroy_simultaneously(
            occupied_positions, scope, is_automatic=True
        )

    def _destroy_simultaneously(
        self,
        positions: list[ast.PositionReference],
        scope: scope_tracker.ScopeTracker,
        *,
        is_automatic: bool,
    ) -> DestroyResult:
        """Destroy the particles in ``positions`` simultaneously, with every particle below them, and return what the destruction produces."""
        contribution = destruction_contract.DestructionContribution()
        destructor_executions: list[callee_execution.DestructorCalleeExecution] = []
        destruction_contracts: list[action_contract.DestructionContracts] = []
        for position in positions:
            root = self._destruction_root(position, is_automatic=is_automatic)
            walked = self._walker.walk(root, None)
            contribution.extend(walked.contribution)
            # The destructors of a particle that Automatic Destruction destroys
            # are reported where the particle last arrived.
            auto_destruction_target = (
                root.particle.last_position if is_automatic else None
            )
            for destructor_on_destroyed_particle in walked.destructors:
                destructor_executions.append(
                    _destructor_execution(
                        destructor_on_destroyed_particle, auto_destruction_target
                    )
                )
            if walked.destruction_contracts:
                # The Child State is the state immediately before destruction
                # begins. Validating the Destructors further down records their
                # requirements, which changes what this action knows about the
                # child positions, so the Child State is captured first.
                destruction_contracts.append(
                    action_contract.DestructionContracts(
                        child_state=self._tracker.snapshot_child_state(position),
                        particles=walked.destruction_contracts,
                    )
                )
        validation_diagnostics: list[diagnostics.Diagnostic] = []
        for execution in destructor_executions:
            # A Destructor publishes no Destruction Contracts, and the known
            # destruction work records only its action chain, so only the
            # diagnostics are needed from the result.
            validation_diagnostics.extend(
                self._callee_execution_validator.validate(execution, scope).diagnostics
            )
        self._tracker.destroy_simultaneously(positions)
        return DestroyResult(
            contribution=contribution,
            destruction_contracts=destruction_contracts,
            diagnostics=validation_diagnostics,
        )

    def _destruction_root(
        self, position: ast.PositionReference, *, is_automatic: bool
    ) -> destruction_walk.DestructionRoot:
        """Return the DestructionRoot of this action directly destroying the particle in ``position``."""
        return destruction_walk.DestructionRoot(
            position=position,
            particle=self._tracker.get_occupant(position),
            destruction_fact=destruction_contract.DestructionFact(
                destroying_definition=self._definition,
                directly_destroyed_position=position,
                is_automatic=is_automatic,
                destroyed_position_in_destroyer=position,
            ),
            # Child State names positions after the directly destroyed position.
            position_in_child_state=chained_name.ChainedNameTuple(()),
            validated_destructors=quality_assignment.EMPTY_QUALITY_ASSIGNMENTS,
        )


def _destructor_execution(
    destructor_on_destroyed_particle: destruction_walk.DestructorOnDestroyedParticle,
    auto_destruction_target: ast.PositionReference | None,
) -> callee_execution.DestructorCalleeExecution:
    """Return the execution of a Destructor that this action directly knows, reported at ``auto_destruction_target`` when Automatic Destruction destroys its particle."""
    # A destructor's requirements are checked as though it triggered
    # synchronously at the moment of destruction (DLP 41). The destructor is a
    # quality of the destroyed particle, so its interface positions hang off
    # its action chain, the particle's position followed by the destructor,
    # while its implied qualities hang off the particle's position itself;
    # in_caller maps both correctly from that chain.
    return callee_execution.DestructorCalleeExecution(
        contract=destructor_on_destroyed_particle.contract,
        action_chain=destructor_on_destroyed_particle.action_chain,
        parent_particle=destructor_on_destroyed_particle.particle,
        acting_on_position=destructor_on_destroyed_particle.position,
        auto_destruction_target=auto_destruction_target,
    )
