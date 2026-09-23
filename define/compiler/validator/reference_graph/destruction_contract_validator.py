"""Validate Destruction Contracts from the caller's perspective."""

from __future__ import annotations

import typing

import msgspec

from define.compiler import ast, diagnostics
from define.compiler.validator.reference_graph import (
    action_contract,
    child_state,
    particle_info,
    particle_tracker,
    position_occupancy,
    quality_assignment,
    reference_graph_validation_state,
    requirement_violation,
)
from define.compiler.validator.reference_graph import (
    destruction_contract as destruction_contract_types,
)

if typing.TYPE_CHECKING:
    from collections.abc import Sequence

    from define.compiler.data_structures import typed_name_dict
    from define.compiler.validator import validation_result


class DestructionContractValidationResult(msgspec.Struct):
    """Diagnostics, propagated contracts, and connections for one Action Execution."""

    diagnostics: list[diagnostics.Diagnostic] = msgspec.field(default_factory=list)
    propagated_contracts: list[action_contract.DestructionContracts] = msgspec.field(
        default_factory=list
    )
    connections: list[destruction_contract_types.DestructionConnection] = msgspec.field(
        default_factory=list
    )


class _ResolvedRequirement(msgspec.Struct, frozen=True):
    """A destructor requirement whose required position's destruction-time occupancy is known here."""

    requirement: action_contract.PositionRequirement
    position: ast.PositionReference
    occupancy: position_occupancy.ChildOccupancy


class _DestructionContractInCaller(msgspec.Struct, frozen=True):
    """A callee's Destruction Contract and its particle from the caller's perspective."""

    contract: action_contract.DestructionContract
    position: ast.PositionReference
    connection: destruction_contract_types.DestructionConnection
    particles: dict[ast.ChainedNameTuple, particle_info.ParticleInfo]


class DestructionContractValidator:
    """Validate a callee's Destruction Contracts using the caller's particle state."""

    _definition: ast.ActionDefinition
    _definition_results: typed_name_dict.TypedNameDict[
        ast.GlobalTypedName[ast.GlobalNameContent[ast.Fqun | None]],
        validation_result.DefinitionValidationResult,
    ]
    _validation_state: reference_graph_validation_state.ReferenceGraphValidationState
    _tracker: particle_tracker.ParticleTracker

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
        """Initialize with the caller's definition, particle state, and known definitions."""
        self._definition = definition
        self._definition_results = definition_results
        self._validation_state = validation_state
        self._tracker = tracker

    def validate(
        self,
        contracts: Sequence[action_contract.DestructionContracts],
        action_chain: ast.ActionReference,
    ) -> DestructionContractValidationResult:
        """Check a callee's Destruction Contracts from the caller's perspective."""
        result = DestructionContractValidationResult()
        if not contracts:
            return result
        # All collections use the same current step, but each extends its own
        # preceding history without copying the earlier steps.
        trigger_step = action_contract.PropagationStep(
            location=action_chain.location,
            kind=action_contract.PropagationKind.ACTION_TRIGGER,
            enclosing_quality_name=self._definition.typed_name.source_typed_name,
            triggered_quality_name=action_chain.typed_names[-1].full_typed_name,
        )
        for callee_contracts in contracts:
            self._check_destruction_contract_group(
                callee_contracts, action_chain, trigger_step, result
            )
        return result

    def _destruction_contracts_in_caller(
        self,
        callee_contracts: action_contract.DestructionContracts,
        action_chain: ast.ActionReference,
        connections: list[destruction_contract_types.DestructionConnection],
    ) -> tuple[
        list[_DestructionContractInCaller],
        position_occupancy.ChildOccupancyMap,
    ]:
        """Resolve contracted positions and collect the caller's Child State."""
        caller_contracts: list[_DestructionContractInCaller] = []
        caller_knowledge: position_occupancy.ChildOccupancyMap = {}
        for destruction_contract in callee_contracts.particles:
            connection = destruction_contract_types.DestructionConnection(
                callee_destruction=destruction_contract.propagated_destruction,
            )
            connections.append(connection)
            position = destruction_contract.propagated_destruction.contracted_position.in_caller(
                action_chain
            )
            # The action's requirement check already handles missing or
            # error-state particles, so there is nothing more to verify here.
            occupancy = self._tracker.get_occupancy_info(position)
            if occupancy.occupant is None:
                continue
            particles = self._tracker.collect_caller_destruction_state(
                caller_knowledge,
                callee_contracts.child_state,
                position,
                destruction_contract.position_in_child_state,
                callee_contracts.positions,
            )
            caller_contracts.append(
                _DestructionContractInCaller(
                    destruction_contract, position, connection, particles
                )
            )
        return caller_contracts, caller_knowledge

    def _check_destruction_contract_group(
        self,
        callee_contracts: action_contract.DestructionContracts,
        action_chain: ast.ActionReference,
        trigger_step: action_contract.PropagationStep,
        result: DestructionContractValidationResult,
    ):
        """Verify particles sharing Child State and record their contributions."""
        caller_contracts, caller_knowledge = self._destruction_contracts_in_caller(
            callee_contracts, action_chain, result.connections
        )
        propagated_contracts = action_contract.DestructionContracts(
            child_state=callee_contracts.child_state.with_caller(caller_knowledge),
            propagation=action_contract.PropagationHistory(
                trigger_step, callee_contracts.propagation
            ),
        )
        for caller_contract in caller_contracts:
            self._check_one_destruction_contract(
                caller_contract,
                trigger_step,
                callee_contracts,
                propagated_contracts,
                result.diagnostics,
            )
        if propagated_contracts.particles:
            result.propagated_contracts.append(propagated_contracts)

    def _check_one_destruction_contract(
        self,
        caller_contract: _DestructionContractInCaller,
        trigger_step: action_contract.PropagationStep,
        callee_contracts: action_contract.DestructionContracts,
        propagated_contracts: action_contract.DestructionContracts,
        validation_diagnostics: list[diagnostics.Diagnostic],
    ):
        destruction_contract = caller_contract.contract
        caller_particle_position = caller_contract.position
        destroying_definition_result = self._definition_results[
            destruction_contract.propagated_destruction.destruction_fact.destruction.destroying_action
        ]
        destroying_definition = typing.cast(
            "ast.ActionDefinition", destroying_definition_result.definition
        )
        destructor_contributions: list[ast.ActionReference] = []
        newly_occupied_children: list[ast.PositionReference] = []
        self._verify_destruction_cascade(
            caller_particle_position,
            (),
            destruction_contract.position_in_child_state,
            caller_particles=caller_contract.particles,
            destruction_contract=destruction_contract,
            destroying_definition=destroying_definition,
            caller_prefix_length=len(caller_particle_position.typed_names),
            trigger_step=trigger_step,
            callee_contracts=callee_contracts,
            propagated_contracts=propagated_contracts,
            connection=caller_contract.connection,
            destructor_contributions=destructor_contributions,
            newly_occupied_children=newly_occupied_children,
            validation_diagnostics=validation_diagnostics,
        )
        if destructor_contributions or newly_occupied_children:
            caller_contract.connection.contribution = destruction_contract_types.DestructionContribution(
                destruction_fact=destruction_contract.propagated_destruction.destruction_fact,
                position_in_caller=caller_particle_position,
                destructors=destructor_contributions,
                positions=newly_occupied_children,
            )

    def _re_record_destruction_contract(
        self,
        destruction_fact: destruction_contract_types.DestructionFact,
        caller_particle: particle_info.ParticleInfo,
        propagated_contracts: action_contract.DestructionContracts,
        connection: destruction_contract_types.DestructionConnection,
        position_in_child_state: tuple[str, ...],
        verified_destructors: quality_assignment.QualityAssignments,
        newly_verified: list[ast.GlobalTypedNameReference],
    ):
        # Each particle retains only its own verified qualities. Shared state
        # and history remain reusable by independent callers.
        if newly_verified:
            verified_destructors = quality_assignment.QualityAssignments(
                (*verified_destructors.assignments, *newly_verified)
            )
        propagated_destruction = destruction_contract_types.PropagatedDestruction(
            destruction_fact=destruction_fact,
            contracted_position=caller_particle.origin_position,
        )
        propagated_contracts.append(
            action_contract.DestructionContract(
                propagated_destruction=propagated_destruction,
                position_in_child_state=position_in_child_state,
                verified_destructors=verified_destructors,
            )
        )
        connection.forwarded_destructions.append(propagated_destruction)

    def _verify_destruction_cascade(
        self,
        position_prefix: ast.PositionReference,
        position_suffix: tuple[ast.TypedNameReference, ...],
        position_in_child_state: ast.ChainedNameTuple,
        *,
        caller_particles: dict[ast.ChainedNameTuple, particle_info.ParticleInfo],
        destruction_contract: action_contract.DestructionContract,
        destroying_definition: ast.ActionDefinition,
        caller_prefix_length: int,
        trigger_step: action_contract.PropagationStep,
        callee_contracts: action_contract.DestructionContracts,
        propagated_contracts: action_contract.DestructionContracts,
        connection: destruction_contract_types.DestructionConnection,
        destructor_contributions: list[ast.ActionReference],
        newly_occupied_children: list[ast.PositionReference],
        validation_diagnostics: list[diagnostics.Diagnostic],
    ):
        # Another Destruction Contract for this simultaneous destruction starts at this
        # position. It validates this position and its child names, so continuing
        # this traversal would record their caller-contributed Destroys twice.
        if position_suffix and position_in_child_state in callee_contracts.positions:
            return
        particle = caller_particles.get(position_in_child_state)
        if particle is None:
            return
        occupancy = propagated_contracts.child_state.get(position_in_child_state)
        # A position the destruction-time picture records as empty was emptied
        # before the destruction, so nothing there was destroyed and thus there
        # is no more work to do.
        if (
            occupancy is not None
            and occupancy.state == position_occupancy.PositionOccupancyState.EMPTY
        ):
            return
        position = (
            position_prefix.with_position_suffix(*position_suffix)
            if position_suffix
            else position_prefix
        )
        relative_key = position_in_child_state[
            len(destruction_contract.position_in_child_state) :
        ]
        # A child absent from the contract was unknown to the callee but is
        # occupied from this caller's perspective, so this caller contributes
        # its Destroy. The contracted position itself is already destroyed by
        # the callee and therefore is not a contributed child Destroy.
        callee_occupancy = callee_contracts.child_occupancy(
            destruction_contract, relative_key
        )
        is_newly_occupied_child = bool(relative_key and callee_occupancy is None)
        created_in_this_action = not particle.from_caller
        newly_verified: list[ast.GlobalTypedNameReference] = []
        if relative_key:
            destruction_fact = destruction_contract_types.DestructionFact(
                destruction=destruction_contract.propagated_destruction.destruction_fact.destruction,
                # The contracted position can have a different name in the caller,
                # but its child-name suffix is unchanged. Append only that suffix
                # to express the child's position in the destroying action.
                # For example, if the caller's position<box> corresponds to the
                # destroyer's position<target>, position<box>::position</child>
                # becomes position<target>::position</child>.
                destroyed_position_in_destroyer=destruction_contract.propagated_destruction.destruction_fact.destroyed_position_in_destroyer.with_position_suffix(
                    *position.typed_names[caller_prefix_length:]
                ),
            )
            verified_destructors = quality_assignment.EMPTY_QUALITY_ASSIGNMENTS
        else:
            destruction_fact = (
                destruction_contract.propagated_destruction.destruction_fact
            )
            verified_destructors = destruction_contract.verified_destructors
        for quality in reversed(particle.qualities.assignments):
            if quality.name_type == ast.NameType.POSITION:
                child_position_suffix = (quality,)
                child_position_in_child_state = (
                    *position_in_child_state,
                    quality.full_typed_name,
                )
                self._verify_destruction_cascade(
                    position,
                    child_position_suffix,
                    child_position_in_child_state,
                    caller_particles=caller_particles,
                    destruction_contract=destruction_contract,
                    destroying_definition=destroying_definition,
                    caller_prefix_length=caller_prefix_length,
                    trigger_step=trigger_step,
                    callee_contracts=callee_contracts,
                    propagated_contracts=propagated_contracts,
                    connection=connection,
                    destructor_contributions=destructor_contributions,
                    newly_occupied_children=newly_occupied_children,
                    validation_diagnostics=validation_diagnostics,
                )
            elif quality.name_type == ast.NameType.ACTION:
                definition_result = self._definition_results.get(quality)
                if definition_result is None:
                    continue
                definition = typing.cast(
                    "ast.ActionDefinition", definition_result.definition
                )
                destructor_contribution = None
                if definition.is_destructor and not verified_destructors.has_quality(
                    quality
                ):
                    destructor_contribution = self._verify_one_cascade_destructor(
                        destructor_quality=quality,
                        particle_position=position,
                        particle=particle,
                        destruction_contract=destruction_contract,
                        callee_contracts=callee_contracts,
                        destroying_definition=destroying_definition,
                        caller_prefix_length=caller_prefix_length,
                        trigger_step=trigger_step,
                        merged_child_state=propagated_contracts.child_state,
                        created_in_this_action=created_in_this_action,
                        newly_verified=newly_verified,
                        validation_diagnostics=validation_diagnostics,
                    )
                if destructor_contribution is not None:
                    destructor_contributions.append(destructor_contribution)
                for interface_position in reversed(definition.interface_positions):
                    interface_position_name = interface_position.typed_name
                    child_position_suffix = (quality, interface_position_name)
                    child_position_in_child_state = (
                        *position_in_child_state,
                        quality.full_typed_name,
                        interface_position_name.full_typed_name,
                    )
                    self._verify_destruction_cascade(
                        position,
                        child_position_suffix,
                        child_position_in_child_state,
                        caller_particles=caller_particles,
                        destruction_contract=destruction_contract,
                        destroying_definition=destroying_definition,
                        caller_prefix_length=caller_prefix_length,
                        trigger_step=trigger_step,
                        callee_contracts=callee_contracts,
                        propagated_contracts=propagated_contracts,
                        connection=connection,
                        destructor_contributions=destructor_contributions,
                        newly_occupied_children=newly_occupied_children,
                        validation_diagnostics=validation_diagnostics,
                    )

        # A caller-passed child particle still needs its own contract even when
        # the particle at its parent position was created locally: higher callers
        # may know additional Destructors assigned to the child particle.
        if particle.from_caller:
            self._re_record_destruction_contract(
                destruction_fact,
                particle,
                propagated_contracts,
                connection,
                position_in_child_state,
                verified_destructors,
                newly_verified,
            )
        # Record only occupied child positions absent from the callee's
        # destruction-time state. Append after visiting their children so the
        # contributed Destroy operations are recorded child before parent; the
        # contracted position itself is destroyed by the callee.
        if is_newly_occupied_child:
            newly_occupied_children.append(position)

    def _verify_one_cascade_destructor(
        self,
        *,
        destructor_quality: ast.GlobalTypedNameReference,
        particle_position: ast.PositionReference,
        particle: particle_info.ParticleInfo,
        destruction_contract: action_contract.DestructionContract,
        callee_contracts: action_contract.DestructionContracts,
        destroying_definition: ast.ActionDefinition,
        caller_prefix_length: int,
        trigger_step: action_contract.PropagationStep,
        merged_child_state: child_state.ChildState,
        created_in_this_action: bool,
        newly_verified: list[ast.GlobalTypedNameReference],
        validation_diagnostics: list[diagnostics.Diagnostic],
    ) -> ast.ActionReference | None:
        """Verify one Destructor discovered through a Destruction Contract."""
        destructor_contract = self._validation_state.get_contract_or_none(
            destructor_quality
        )
        if destructor_contract is None:
            return None
        action_chain = particle_position.with_action_suffix(destructor_quality)
        # A destructor is checked exactly once: only at the action that knows the
        # state of every position it requires. Resolve the state of all required positions
        # first, before we attempt to check its requirements.
        resolved_requirements: list[_ResolvedRequirement] = []
        for inner_req in destructor_contract.requirements:
            resolution = self._resolve_destructor_requirement(
                inner_req=inner_req,
                action_chain=action_chain,
                caller_prefix_length=caller_prefix_length,
                destruction_contract=destruction_contract,
                merged_child_state=merged_child_state,
                created_in_this_action=created_in_this_action,
            )
            # If the state of any required position is not yet known, we
            # defer verification to our caller.
            if resolution is None:
                return None
            resolved_requirements.append(resolution)
        for resolved_requirement in resolved_requirements:
            occupancy = resolved_requirement.occupancy
            required_state = resolved_requirement.requirement.required_state
            empty_violation = (
                required_state == position_occupancy.PositionOccupancyState.EMPTY
                and occupancy.state
                == position_occupancy.PositionOccupancyState.OCCUPIED
            )
            occupied_violation = (
                required_state == position_occupancy.PositionOccupancyState.OCCUPIED
                and occupancy.state == position_occupancy.PositionOccupancyState.EMPTY
            )
            if not (empty_violation or occupied_violation):
                continue
            validation_diagnostics.append(
                requirement_violation.contract_destructor(
                    propagated_requirement=resolved_requirement.requirement,
                    resolved_position=resolved_requirement.position,
                    occupancy=occupancy,
                    definition=self._definition,
                    destroying_definition=destroying_definition,
                    destruction_contract=destruction_contract,
                    propagation_steps=callee_contracts.propagation_steps(),
                    particle_position=particle_position,
                    particle=particle,
                    trigger_step=trigger_step,
                    destructor_quality=destructor_quality,
                )
            )
        newly_verified.append(destructor_quality)
        return action_chain

    def _resolve_destructor_requirement(
        self,
        *,
        inner_req: action_contract.PositionRequirement,
        action_chain: ast.ActionReference,
        caller_prefix_length: int,
        destruction_contract: action_contract.DestructionContract,
        merged_child_state: child_state.ChildState,
        created_in_this_action: bool,
    ) -> _ResolvedRequirement | None:
        """Resolve one requirement's position to its destruction-time state, or None if this action cannot know it."""
        # action_chain:
        #   position<box>::action</close_file>::position<target>::action</delete_file_destructor>
        # required_position:
        #   position<box>::action</close_file>::position<target>::position</file>
        # relative_key:
        #   ("position</file>",)
        required_position = inner_req.position.in_caller(action_chain)
        relative_key = required_position.canonical_chained_name_tuple[
            caller_prefix_length:
        ]
        occupancy = merged_child_state.get(
            (*destruction_contract.position_in_child_state, *relative_key)
        )
        if occupancy is None:
            # A passed-in particle's untouched position is decided higher up: this
            # action cannot resolve it, so the destructor travels up unchecked.
            if not created_in_this_action:
                return None
            # The owner created the particle, and we have optimized this case to
            # not copy the whole subtree to update a new child_state and instead
            # to just read the state out of the current tracker.
            if self._tracker.has_error_state(required_position):
                occupancy = position_occupancy.ERROR_OCCUPANCY
            elif self._tracker.is_occupied(required_position):
                occupancy = position_occupancy.ChildOccupancy(
                    position_occupancy.PositionOccupancyState.OCCUPIED,
                    filled_at=self._tracker.get_occupant(
                        required_position
                    ).last_position.location,
                )
            else:
                occupancy = position_occupancy.EMPTY_OCCUPANCY
        return _ResolvedRequirement(
            requirement=inner_req,
            position=required_position,
            occupancy=occupancy,
        )
