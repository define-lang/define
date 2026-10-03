"""Destroy particles as an operation of the action being validated."""

from __future__ import annotations

import typing

import msgspec

from define.compiler import chained_name
from define.compiler.validator import codegen_input
from define.compiler.validator.reference_graph import (
    action_contract,
    quality_assignment,
)
from define.compiler.validator.reference_graph.destruction import (
    destroyed_particles,
    destruction_contract,
)
from define.compiler.validator.reference_graph.particles import particle_info

if typing.TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from define.compiler import ast
    from define.compiler.validator.reference_graph.particles import (
        particle_tracker,
    )


class DestructionTarget(msgspec.Struct, frozen=True):
    """A particle whose destruction also destroys the particles below it."""

    destruction: destruction_contract.DirectDestruction
    # The local position Automatic Destruction empties, where the particle
    # last arrived, or None for a Destroy statement.
    auto_destruction_target: ast.PositionReference | None


@typing.final
class Destroyer:
    """Destroys particles for the action being validated."""

    def __init__(
        self,
        destroyed_particles: destroyed_particles.DestroyedParticles,
        tracker: particle_tracker.ParticleTracker,
    ):
        """Destroy particles in the state ``tracker`` holds."""
        self._destroyed_particles = destroyed_particles
        self._tracker = tracker

    def destroy(
        self,
        targets: Sequence[DestructionTarget],
        trigger_destructor: Callable[
            [action_contract.Destructor, ast.PositionReference | None],
            ast.ActionReference | None,
        ],
    ) -> tuple[codegen_input.Destruction, list[action_contract.DestructionContracts]]:
        """Destroy the particles in ``targets`` simultaneously, with every particle below them, and return the destruction's step and its Destruction Contracts.

        ``trigger_destructor`` triggers one Destructor, given the local position
        Automatic Destruction empties, and returns its action chain, or None
        when it was not triggered.
        """
        step = codegen_input.Destruction()
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
                step.work,
                destructors,
                contracts,
            )
            if contracts:
                snapshot_positions.append(position)
                contracts_by_target.append(contracts)
        child_states = self._tracker.snapshot_child_states(snapshot_positions)
        for destructor, auto_destruction_target in destructors:
            action_chain = trigger_destructor(destructor, auto_destruction_target)
            if action_chain is not None:
                step.work.destructors.append(action_chain)
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
                step.contract_destructions.append(contract.propagated_destruction)
            destruction_contracts.append(contracts_sharing_child_state)
        return step, destruction_contracts

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
