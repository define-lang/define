"""Destroy particles as an operation of the action being validated."""

from __future__ import annotations

import typing

import msgspec

from define.compiler import chained_name
from define.compiler.validator.reference_graph import (
    action_contract,
    quality_assignment,
)
from define.compiler.validator.reference_graph.callee_execution import (
    callee_execution,
)
from define.compiler.validator.reference_graph.destruction import (
    destroyed_particles,
    destruction_contract,
)
from define.compiler.validator.reference_graph.particles import particle_info

if typing.TYPE_CHECKING:
    from collections.abc import Sequence

    from define.compiler import ast
    from define.compiler.errors import diagnostics
    from define.compiler.validator import scope_tracker
    from define.compiler.validator.reference_graph import (
        reference_graph_validation_state,
    )
    from define.compiler.validator.reference_graph.callee_execution import (
        callee_execution_validator,
    )
    from define.compiler.validator.reference_graph.particles import (
        particle_tracker,
    )


class DestructionTarget(msgspec.Struct, frozen=True):
    """A particle whose destruction also destroys the particles below it."""

    destruction: destruction_contract.DirectDestruction
    # The local position Automatic Destruction empties, where the particle
    # last arrived, or None for a Destroy statement.
    auto_destruction_target: ast.PositionReference | None


class DestroyResult(msgspec.Struct):
    """What destroying a set of particles produces."""

    work: destruction_contract.KnownDestructionWork
    contract_destructions: list[destruction_contract.PropagatedDestruction]
    destruction_contracts: list[action_contract.DestructionContracts]
    # From the Destructors the destruction triggers.
    diagnostics: list[diagnostics.Diagnostic]


@typing.final
class Destroyer:
    """Destroys particles for the action being validated."""

    def __init__(
        self,
        destroyed_particles: destroyed_particles.DestroyedParticles,
        tracker: particle_tracker.ParticleTracker,
        callee_execution_validator: callee_execution_validator.CalleeExecutionValidator,
        validation_state: reference_graph_validation_state.ReferenceGraphValidationState,
    ):
        """Destroy particles in the state ``tracker`` holds."""
        self._destroyed_particles = destroyed_particles
        self._tracker = tracker
        self._callee_execution_validator = callee_execution_validator
        self._validation_state = validation_state

    def destroy(
        self,
        targets: Sequence[DestructionTarget],
        scope: scope_tracker.ScopeTracker,
    ) -> DestroyResult:
        """Destroy the particles in ``targets`` simultaneously, with every particle below them, and return what the destruction produces."""
        work = destruction_contract.KnownDestructionWork()
        contract_destructions: list[destruction_contract.PropagatedDestruction] = []
        validation_diagnostics: list[diagnostics.Diagnostic] = []
        destructors: list[
            tuple[action_contract.Destructor, ast.PositionReference | None]
        ] = []
        # Only targets that destroy a particle from the caller, in target order.
        snapshot_positions: list[ast.PositionReference] = []
        contracts_by_target: list[list[action_contract.DestructionContract]] = []
        for target in targets:
            position = target.destruction.directly_destroyed_position
            contracts: list[action_contract.DestructionContract] = []
            self._collect(
                position,
                self._tracker.get_occupant(position),
                target,
                work,
                destructors,
                contracts,
            )
            if contracts:
                snapshot_positions.append(position)
                contracts_by_target.append(contracts)
        child_states = self._tracker.snapshot_child_states(snapshot_positions)
        for destructor, auto_destruction_target in destructors:
            triggered = self._trigger_destructor(
                destructor, auto_destruction_target, scope
            )
            if triggered is not None:
                action_chain, destructor_diagnostics = triggered
                work.destructors.append(action_chain)
                validation_diagnostics.extend(destructor_diagnostics)
        self._tracker.destroy_simultaneously(
            [target.destruction.directly_destroyed_position for target in targets]
        )
        destruction_contracts: list[action_contract.DestructionContracts] = []
        for shared_state, contracts in zip(
            child_states, contracts_by_target, strict=True
        ):
            contracts_sharing_child_state = action_contract.DestructionContracts(
                child_state=shared_state
            )
            for contract in contracts:
                contracts_sharing_child_state.append(contract)
                contract_destructions.append(contract.propagated_destruction)
            destruction_contracts.append(contracts_sharing_child_state)
        return DestroyResult(
            work=work,
            contract_destructions=contract_destructions,
            destruction_contracts=destruction_contracts,
            diagnostics=validation_diagnostics,
        )

    def _trigger_destructor(
        self,
        destructor: action_contract.Destructor,
        auto_destruction_target: ast.PositionReference | None,
        scope: scope_tracker.ScopeTracker,
    ) -> tuple[ast.ActionReference, list[diagnostics.Diagnostic]] | None:
        """Trigger one directly known Destructor before particle destruction, and return its action chain and the diagnostics its execution causes, or None when it has no contract to trigger."""
        # A destructor's requirements are checked as though it triggered
        # synchronously at the moment of destruction (DLP 41). The destructor is a
        # quality of the particle in `position`, so its interface positions
        # hang off position::action</destructor> while its implied qualities hang off
        # position itself; in_caller maps both correctly from this chain.
        contract = self._validation_state.get_contract_or_none(destructor.destructor)
        if contract is None:
            return None
        action_chain = destructor.position.with_action_suffix(destructor.destructor)
        # A Destructor publishes no Destruction Contracts, and the known
        # destruction work records only its action chain, so only the
        # diagnostics are needed from the result.
        result = self._callee_execution_validator.validate(
            callee_execution.DestructorCalleeExecution(
                contract=contract,
                action_chain=action_chain,
                parent_particle=self._tracker.get_occupant(destructor.position),
                acting_on_position=destructor.position,
                destructor=destructor,
                auto_destruction_target=auto_destruction_target,
            ),
            scope,
        )
        return action_chain, result.diagnostics

    def _collect(
        self,
        position: ast.PositionReference,
        particle: particle_info.ParticleInfo,
        target: DestructionTarget,
        work: destruction_contract.KnownDestructionWork,
        destructors: list[
            tuple[action_contract.Destructor, ast.PositionReference | None]
        ],
        contracts: list[action_contract.DestructionContract],
    ):
        """Collect what destroying ``particle``, in ``position``, and every particle in its transitive child positions does: the Destroys and method calls into ``work``, the Destructors to trigger into ``destructors``, and a Destruction Contract for each particle from the caller into ``contracts``."""
        # A particle keeps its own qualities across Moves, so its qualities,
        # not the current position's constraints, decide what is below it.
        child_names, particle_destructors = (
            self._destroyed_particles.child_names_and_destructors(
                particle.qualities.assignments
            )
        )
        for destructor in particle_destructors:
            destructors.append(
                (
                    action_contract.Destructor(
                        destructor=destructor,
                        position=position,
                        origin_position=particle.origin_position,
                    ),
                    target.auto_destruction_target,
                )
            )
        for names in child_names:
            child_position = position.with_position_suffix(*names)
            found = (
                self._destroyed_particles.particle_to_destroy_or_destructors_call_at(
                    child_position, particle
                )
            )
            if isinstance(found, destruction_contract.RunGuaranteedParticleDestructors):
                work.guaranteed_particle_destructors.append(found)
            elif found is not None:
                self._collect(
                    child_position,
                    found,
                    target,
                    work,
                    destructors,
                    contracts,
                )
        if particle.source is particle_info.ParticleSource.CALLER:
            contracts.append(
                action_contract.DestructionContract(
                    propagated_destruction=destruction_contract.PropagatedDestruction(
                        destruction_fact=destruction_contract.DestructionFact(
                            destruction=target.destruction,
                            destroyed_position_in_destroyer=position,
                        ),
                        contracted_position=particle.origin_position,
                    ),
                    # The snapshot's names are relative to the directly destroyed
                    # Position. For a Destroy of position<box>, a particle at
                    # position<box>::position</child> uses just position</child>
                    # to find its child state; the particle at position<box>
                    # uses ().
                    position_in_child_state=chained_name.without_prefix(
                        position.canonical_chained_name_tuple,
                        target.destruction.directly_destroyed_position.canonical_chained_name_tuple,
                    ),
                    # We know these destructors exist at destruction time, so they are
                    # handled through the normal requirements mechanism (fired and
                    # propagated as this action's own requirements), not through the
                    # Destruction Contract's requirement-verification mechanism.
                    verified_destructors=quality_assignment.QualityAssignments(
                        tuple(particle_destructors)
                    ),
                )
            )
        # A particle's children must remain accessible until their own
        # Destroy executes.
        work.positions.append(
            destruction_contract.DestroyedPosition(position, position)
        )
