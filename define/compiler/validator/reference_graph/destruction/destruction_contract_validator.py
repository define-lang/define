"""Add what a caller knows to a callee's destructions, from its Destruction Contracts."""

from __future__ import annotations

import typing

import msgspec

from define.compiler.validator.reference_graph import (
    action_contract,
)
from define.compiler.validator.reference_graph.callee_execution import (
    callee_execution,
)
from define.compiler.validator.reference_graph.destruction import (
    destruction_contract,
    destruction_walk,
)

if typing.TYPE_CHECKING:
    from collections.abc import Iterator, Sequence

    from define.compiler import ast, chained_name
    from define.compiler.data_structures import typed_name_dict
    from define.compiler.validator import validation_result
    from define.compiler.validator.reference_graph import (
        reference_graph_validation_state,
    )
    from define.compiler.validator.reference_graph.destruction import (
        child_state,
    )
    from define.compiler.validator.reference_graph.particles import (
        particle_info,
        particle_tracker,
    )


class DestructionContractValidationResult(msgspec.Struct):
    """What a caller adds to a callee's destructions, for one Action Execution."""

    propagated_contracts: list[action_contract.DestructionContracts] = msgspec.field(
        default_factory=list
    )
    connections: list[destruction_contract.DestructionConnection] = msgspec.field(
        default_factory=list
    )
    # The Destructors on destroyed particles that this action is the lowest to
    # know, which still have to be validated.
    destructor_executions: list[callee_execution.DestructorInCalleeExecution] = (
        msgspec.field(default_factory=list)
    )


@typing.final
class DestructionContractValidator:
    """Add what a caller knows to a callee's destructions, from the callee's Destruction Contracts."""

    def __init__(
        self,
        definition: ast.ActionDefinition,
        definition_results: typed_name_dict.TypedNameDict[
            ast.GlobalTypedName[ast.GlobalNameContent[ast.Fqun | None]],
            validation_result.DefinitionValidationResult,
        ],
        validation_state: reference_graph_validation_state.ReferenceGraphValidationState,
        tracker: particle_tracker.ParticleTracker,
    ):
        """Add what ``definition`` knows, from the particle state ``tracker`` holds."""
        self._definition = definition
        self._tracker = tracker
        self._walker = destruction_walk.DestructionWalker(
            tracker, definition_results, validation_state
        )

    def validate(
        self,
        contracts: Sequence[action_contract.DestructionContracts],
        action_chain: ast.ActionReference,
    ) -> DestructionContractValidationResult:
        """Add what this action knows to the destructions of the callee that ``action_chain`` triggers."""
        result = DestructionContractValidationResult()
        for callee_contracts in contracts:
            self._add_to_callee_destruction(callee_contracts, action_chain, result)
        return result

    def _add_to_callee_destruction(
        self,
        callee_contracts: action_contract.DestructionContracts,
        action_chain: ast.ActionReference,
        result: DestructionContractValidationResult,
    ):
        """Add what this action knows to one destruction of the callee, whose Destruction Contracts share a Child State."""
        occupancy: child_state.ChildOccupancyMap = {}
        values: child_state.ChildValueMap = {}
        particles: dict[chained_name.ChainedNameTuple, particle_info.ParticleInfo] = {}
        unexpanded: dict[
            chained_name.ChainedNameTuple, action_contract.ChildPositionParticles
        ] = {}
        contracted_roots: list[destruction_walk.DestructionRoot] = []
        connections: list[destruction_contract.DestructionConnection] = []
        for callee_contract in callee_contracts.particles:
            connection = destruction_contract.DestructionConnection(
                callee_destruction=callee_contract.propagated_destruction,
            )
            result.connections.append(connection)
            position = (
                callee_contract.propagated_destruction.contracted_position.in_caller(
                    action_chain
                )
            )
            # The action's requirement check already handles missing or
            # error-state particles, so there is nothing more to add here.
            particle = self._tracker.get_occupancy_info(position).occupant
            if particle is None:
                continue
            self._tracker.collect_caller_destruction_state(
                occupancy,
                values,
                particles,
                unexpanded,
                callee_contracts.child_state,
                position,
                callee_contract.position_in_child_state,
                callee_contracts.positions,
            )
            contracted_roots.append(
                destruction_walk.DestructionRoot(
                    position=position,
                    particle=particle,
                    destruction_fact=callee_contract.propagated_destruction.destruction_fact,
                    position_in_child_state=callee_contract.position_in_child_state,
                    validated_destructors=callee_contract.validated_destructors,
                )
            )
            connections.append(connection)
        # Every group from the callee shares its caller and callee, and each
        # extends its own earlier history without copying it.
        trigger = action_contract.PropagationHistory(
            caller=self._definition,
            callee=action_chain,
            previous=callee_contracts.propagation,
        )
        state = destruction_walk.CalleeStateAtDestruction(
            callee_contracts,
            callee_contracts.child_state.with_caller(occupancy, values, unexpanded),
            contracted_roots,
            particles,
            trigger,
        )
        destruction_contracts: list[action_contract.DestructionContract] = []
        for root, connection in zip(contracted_roots, connections, strict=True):
            walked = self._walker.walk(root, state)
            result.destructor_executions.extend(
                _destructor_executions(root, walked, state)
            )
            destruction_contracts.extend(walked.destruction_contracts)
            if walked.contribution.has_contribution():
                connection.contribution = walked.contribution
        if destruction_contracts:
            result.propagated_contracts.append(
                action_contract.DestructionContracts(
                    child_state=state.child_state,
                    particles=destruction_contracts,
                    propagation=trigger,
                )
            )


def _destructor_executions(
    root: destruction_walk.DestructionRoot,
    walked: destruction_walk.WalkedDestruction,
    state: destruction_walk.CalleeStateAtDestruction,
) -> Iterator[callee_execution.DestructorInCalleeExecution]:
    """Yield the executions of the Destructors that walking ``root`` found and that this action is the lowest to know."""
    for destructor_on_destroyed_particle in walked.destructors:
        yield callee_execution.DestructorInCalleeExecution(
            contract=destructor_on_destroyed_particle.contract,
            action_chain=destructor_on_destroyed_particle.action_chain,
            parent_particle=destructor_on_destroyed_particle.particle,
            acting_on_position=destructor_on_destroyed_particle.position,
            root=root,
            state_at_destruction=state,
        )
