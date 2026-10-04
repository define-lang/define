"""Validate Destruction Contracts from the caller's perspective."""

from __future__ import annotations

import typing

import msgspec

from define.compiler import ast, chained_name
from define.compiler.validator.reference_graph import (
    action_contract,
    position_occupancy,
    quality_assignment,
    reference_graph_validation_state,
)
from define.compiler.validator.reference_graph.callee_execution import (
    requirement_violation,
)
from define.compiler.validator.reference_graph.destruction import (
    child_state,
    destroyed_particles,
)
from define.compiler.validator.reference_graph.destruction import (
    destruction_contract as destruction_contract_types,
)
from define.compiler.validator.reference_graph.particles import particle_info

if typing.TYPE_CHECKING:
    from collections.abc import Sequence

    from define.compiler.data_structures import typed_name_dict
    from define.compiler.errors import diagnostics
    from define.compiler.validator import scope_tracker, validation_result
    from define.compiler.validator.reference_graph import action_requirement_validator
    from define.compiler.validator.reference_graph.dead_code import (
        dead_value_write_validator,
    )
    from define.compiler.validator.reference_graph.particles import (
        particle_tracker,
    )


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
    # The required position's name in the shared Child State.
    state_key: chained_name.ChainedNameTuple
    occupancy: position_occupancy.ChildOccupancy
    value_state: particle_info.ParticleValueState | None


class _CalleeDestructionContractInCaller(msgspec.Struct):
    """One Destruction Contract of a callee destruction from the caller's perspective, with what the caller contributes to that destruction."""

    contract: action_contract.DestructionContract
    # The contract's particle, and its position from the caller's perspective.
    position: ast.PositionReference
    particle: particle_info.ParticleInfo
    connection: destruction_contract_types.DestructionConnection
    destroying_definition: ast.ActionDefinition
    # What the caller contributes, with positions from the perspective of the
    # contract's particle, as the callee's generated method names them.
    work: destruction_contract_types.KnownDestructionWork = msgspec.field(
        default_factory=destruction_contract_types.KnownDestructionWork
    )

    def names_below_contract_particle(
        self, position: ast.PositionReference
    ) -> chained_name.ChainedNameTuple:
        """Return the names of ``position``, a position from the caller's perspective at or below the contract's particle, after the particle's position."""
        return chained_name.without_prefix(
            position.canonical_chained_name_tuple,
            self.position.canonical_chained_name_tuple,
        )

    def position_in_child_state(
        self, position: ast.PositionReference
    ) -> chained_name.ChainedNameTuple:
        """Return the Child State name of ``position``, a position from the caller's perspective at or below the contract's particle."""
        return chained_name.with_prefix(
            self.names_below_contract_particle(position),
            self.contract.position_in_child_state,
        )

    def from_particle[Reference: ast.ChainedName](
        self, reference: Reference
    ) -> Reference:
        """Return ``reference``, a chained name from the caller's perspective at or below the contract's particle, from the particle's perspective."""
        return type(reference)(
            location=reference.location,
            typed_names=reference.typed_names[len(self.position.typed_names) :],
        )


class _CalleeDestructionInCaller(msgspec.Struct):
    """One callee destruction from the caller's perspective, shared by all of its Destruction Contracts."""

    callee_contracts: action_contract.DestructionContracts
    # The ones whose particle the caller has.
    contracts: list[_CalleeDestructionContractInCaller]
    propagated_contracts: action_contract.DestructionContracts
    # This action's trigger of the callee, the newest entry in the history
    # of ``propagated_contracts``.
    trigger: action_contract.PropagationHistory
    # The caller's particles at the moment of destruction, by Child State
    # position, which can differ from where the caller has them now when the
    # callee moved them. Every Destruction Contract from one destruction
    # shares these, so a destructor can find a particle that another of those
    # contracts collected.
    caller_particles: dict[chained_name.ChainedNameTuple, particle_info.ParticleInfo]
    validation_diagnostics: list[diagnostics.Diagnostic]
    # The Destructor requirements that only this action's caller can validate.
    occupancy_requirements_for_caller: list[
        action_contract.OccupancyRequirementInCaller
    ] = msgspec.field(default_factory=list)
    value_requirements_for_caller: list[action_contract.ValueRequirementInCaller] = (
        msgspec.field(default_factory=list)
    )

    def another_contract_starts_at(
        self, position_in_child_state: chained_name.ChainedNameTuple
    ) -> bool:
        """Return whether another Destruction Contract of this destruction starts at ``position_in_child_state``."""
        # That contract validates this position and its child names, so
        # continuing this traversal would record their caller-contributed
        # Destroys twice.
        return position_in_child_state in self.callee_contracts.positions

    def nearest_caller_particle(
        self, position_in_child_state: chained_name.ChainedNameTuple
    ) -> tuple[chained_name.ChainedNameTuple, particle_info.ParticleInfo]:
        """Return the caller's particle at ``position_in_child_state``, or the nearest one above it, with its position in the Child State."""
        # Every position a destruction reaches is at or below the particle of
        # one of its contracts, which the caller has.
        length = len(position_in_child_state)
        while (
            particle := self.caller_particles.get(
                chained_name.ChainedNameTuple(position_in_child_state[:length])
            )
        ) is None:
            length -= 1
        return chained_name.ChainedNameTuple(position_in_child_state[:length]), particle

    def position_in_caller(
        self,
        position: ast.PositionReference,
        position_in_child_state: chained_name.ChainedNameTuple,
    ) -> ast.PositionReference:
        """Return where ``position``, named from the caller's perspective below the particle it was found under, was when the callee was triggered."""
        # A callee can move a particle from the caller below another one, so
        # the nearest contract above the position decides where it was.
        nearest: _CalleeDestructionContractInCaller | None = None
        for contract in self.contracts:
            start = contract.contract.position_in_child_state
            if position_in_child_state[: len(start)] == start and (
                nearest is None
                or len(start) > len(nearest.contract.position_in_child_state)
            ):
                nearest = contract
        # Every particle a destruction destroys is below one with a contract.
        nearest = typing.cast("_CalleeDestructionContractInCaller", nearest)
        names_below = len(position_in_child_state) - len(
            nearest.contract.position_in_child_state
        )
        if names_below == 0:
            return nearest.position
        return nearest.position.with_position_suffix(
            *position.typed_names[-names_below:]
        )

    def child_state_records_empty(
        self, position_in_child_state: chained_name.ChainedNameTuple
    ) -> bool:
        """Return whether the merged Child State records ``position_in_child_state`` as empty."""
        # A position the destruction-time picture records as empty was emptied
        # before the destruction, so nothing there was destroyed and thus there
        # is no more work to do.
        occupancy = self.propagated_contracts.child_state.occupancy.get(
            position_in_child_state
        )
        return (
            occupancy is not None
            and occupancy.state == position_occupancy.PositionOccupancyState.EMPTY
        )


# TODO: The spec validates Destructors in Destruction Contracts. Rename
# DestructionContract.verified_destructors to match, along with what uses it
# (_destruction_fact_and_verified_destructors, newly_verified, and comments).
class DestructionContractValidator:
    """Validate a callee's Destruction Contracts using the caller's particle state."""

    _definition: ast.ActionDefinition
    _definition_results: typed_name_dict.TypedNameDict[
        ast.GlobalTypedName[ast.GlobalNameContent[ast.Fqun | None]],
        validation_result.DefinitionValidationResult,
    ]
    _validation_state: reference_graph_validation_state.ReferenceGraphValidationState
    _tracker: particle_tracker.ParticleTracker
    _dead_value_write_validator: dead_value_write_validator.DeadValueWriteValidator
    _destroyed_particles: destroyed_particles.DestroyedParticles
    _requirement_validator: action_requirement_validator.ActionRequirementValidator

    def __init__(
        self,
        definition: ast.ActionDefinition,
        definition_results: typed_name_dict.TypedNameDict[
            ast.GlobalTypedName[ast.GlobalNameContent[ast.Fqun | None]],
            validation_result.DefinitionValidationResult,
        ],
        validation_state: reference_graph_validation_state.ReferenceGraphValidationState,
        tracker: particle_tracker.ParticleTracker,
        dead_value_write_validator: dead_value_write_validator.DeadValueWriteValidator,
        destroyed_particles: destroyed_particles.DestroyedParticles,
        requirement_validator: action_requirement_validator.ActionRequirementValidator,
    ):
        """Initialize with the caller's definition, particle state, and known definitions."""
        self._definition = definition
        self._definition_results = definition_results
        self._validation_state = validation_state
        self._tracker = tracker
        self._dead_value_write_validator = dead_value_write_validator
        self._destroyed_particles = destroyed_particles
        self._requirement_validator = requirement_validator

    def validate(
        self,
        contracts: Sequence[action_contract.DestructionContracts],
        action_chain: ast.ActionReference,
        scope: scope_tracker.ScopeTracker,
    ) -> DestructionContractValidationResult:
        """Check a callee's Destruction Contracts from the caller's perspective."""
        result = DestructionContractValidationResult()
        if not contracts:
            return result
        occupancy_requirements_for_caller: list[
            action_contract.OccupancyRequirementInCaller
        ] = []
        value_requirements_for_caller: list[
            action_contract.ValueRequirementInCaller
        ] = []
        for callee_contracts in contracts:
            occupancy_requirements, value_requirements = (
                self._check_destruction_contract_group(
                    callee_contracts, action_chain, result
                )
            )
            occupancy_requirements_for_caller.extend(occupancy_requirements)
            value_requirements_for_caller.extend(value_requirements)
        # Gained only after every Destruction Contract of the callee is
        # validated, so validating never follows a particle that this action
        # only assumes because of a requirement it gained.
        self._requirement_validator.propagate_action_requirements(
            action_chain.location, occupancy_requirements_for_caller, scope
        )
        self._requirement_validator.propagate_value_requirements(
            action_chain.location, value_requirements_for_caller
        )
        self._dead_value_write_validator.mark_required_values_used(
            value_requirements_for_caller
        )
        return result

    def _callee_destruction_in_caller(
        self,
        callee_contracts: action_contract.DestructionContracts,
        action_chain: ast.ActionReference,
        result: DestructionContractValidationResult,
    ) -> _CalleeDestructionInCaller:
        """Resolve a callee destruction's contracted positions in the caller, and collect the caller's Child State and particles for them."""
        contracts: list[_CalleeDestructionContractInCaller] = []
        occupancy: child_state.ChildOccupancyMap = {}
        values: child_state.ChildValueMap = {}
        particles: dict[chained_name.ChainedNameTuple, particle_info.ParticleInfo] = {}
        unexpanded: dict[
            chained_name.ChainedNameTuple, action_contract.ChildPositionParticles
        ] = {}
        for destruction_contract in callee_contracts.particles:
            connection = destruction_contract_types.DestructionConnection(
                callee_destruction=destruction_contract.propagated_destruction,
            )
            result.connections.append(connection)
            position = destruction_contract.propagated_destruction.contracted_position.in_caller(
                action_chain
            )
            # The action's requirement check already handles missing or
            # error-state particles, so there is nothing more to verify here.
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
                destruction_contract.position_in_child_state,
                callee_contracts.positions,
            )
            destroying_definition_result = self._definition_results[
                destruction_contract.propagated_destruction.destruction_fact.destruction.destroying_action
            ]
            contracts.append(
                _CalleeDestructionContractInCaller(
                    contract=destruction_contract,
                    position=position,
                    particle=particle,
                    connection=connection,
                    destroying_definition=typing.cast(
                        "ast.ActionDefinition", destroying_definition_result.definition
                    ),
                )
            )
        # Every group from the callee shares its caller and callee, and each
        # extends its own earlier history without copying it.
        trigger = action_contract.PropagationHistory(
            caller=self._definition,
            callee=action_chain,
            previous=callee_contracts.propagation,
        )
        return _CalleeDestructionInCaller(
            callee_contracts=callee_contracts,
            contracts=contracts,
            propagated_contracts=action_contract.DestructionContracts(
                child_state=callee_contracts.child_state.with_caller(
                    occupancy, values, unexpanded
                ),
                propagation=trigger,
            ),
            trigger=trigger,
            caller_particles=particles,
            validation_diagnostics=result.diagnostics,
        )

    def _check_destruction_contract_group(
        self,
        callee_contracts: action_contract.DestructionContracts,
        action_chain: ast.ActionReference,
        result: DestructionContractValidationResult,
    ) -> tuple[
        list[action_contract.OccupancyRequirementInCaller],
        list[action_contract.ValueRequirementInCaller],
    ]:
        """Validate the Destructors of particles sharing Child State and record their contributions, and return the occupancy and value requirements of their Destructors that only this action's caller can validate."""
        destruction = self._callee_destruction_in_caller(
            callee_contracts, action_chain, result
        )
        for contract in destruction.contracts:
            self._check_one_destruction_contract(contract, destruction)
        if destruction.propagated_contracts.particles:
            result.propagated_contracts.append(destruction.propagated_contracts)
        return (
            destruction.occupancy_requirements_for_caller,
            destruction.value_requirements_for_caller,
        )

    def _check_one_destruction_contract(
        self,
        contract: _CalleeDestructionContractInCaller,
        destruction: _CalleeDestructionInCaller,
    ):
        self._validate_destroyed(
            contract.position, contract.particle, contract, destruction
        )
        if contract.work.has_work():
            contract.connection.contribution = contract.work

    def _re_record_destruction_contract(
        self,
        destruction_fact: destruction_contract_types.DestructionFact,
        caller_particle: particle_info.ParticleInfo,
        propagated_contracts: action_contract.DestructionContracts,
        connection: destruction_contract_types.DestructionConnection,
        position_in_child_state: chained_name.ChainedNameTuple,
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

    def _validate_destroyed(
        self,
        position: ast.PositionReference,
        particle: particle_info.ParticleInfo,
        contract: _CalleeDestructionContractInCaller,
        destruction: _CalleeDestructionInCaller,
    ):
        """Validate the Destructors on ``particle``, in ``position``, and on the particles in its transitive child positions that this action knows and the callee did not, and record what this action contributes to destroying them."""
        destruction_contract = contract.contract
        relative_key = contract.names_below_contract_particle(position)
        # A child absent from the contract was unknown to the callee but is
        # occupied from this caller's perspective, so this caller contributes
        # its Destroy. The contracted position itself is already destroyed by
        # the callee and therefore is not a contributed child Destroy.
        callee_occupancy = destruction.callee_contracts.child_occupancy(
            destruction_contract, relative_key
        )
        is_newly_occupied_child = bool(relative_key and callee_occupancy is None)
        from_caller = particle.source is particle_info.ParticleSource.CALLER
        newly_verified: list[ast.GlobalTypedNameReference] = []
        destruction_fact, verified_destructors = (
            _destruction_fact_and_verified_destructors(position, particle, contract)
        )
        # A particle keeps its own qualities across Moves, so its qualities,
        # not the current position's constraints, decide what is below it.
        child_names, destructors = (
            self._destroyed_particles.child_names_and_destructors(
                particle.qualities.assignments
            )
        )
        for destructor in destructors:
            if verified_destructors.has_quality(destructor):
                continue
            destructor_contribution = self._validate_one_cascade_destructor(
                destructor,
                position,
                particle,
                contract,
                destruction,
                newly_verified=newly_verified,
            )
            if destructor_contribution is not None:
                contract.work.destructors.append(
                    contract.from_particle(destructor_contribution)
                )
        for names in child_names:
            child_position = position.with_position_suffix(*names)
            found = (
                self._destroyed_particles.particle_to_destroy_or_destructors_call_at(
                    child_position, particle
                )
            )
            if isinstance(
                found, destruction_contract_types.RunGuaranteedParticleDestructors
            ):
                contract.work.guaranteed_particle_destructors.append(
                    msgspec.structs.replace(
                        found, position=contract.from_particle(found.position)
                    )
                )
                continue
            if found is None:
                continue
            child_in_child_state = contract.position_in_child_state(child_position)
            if destruction.another_contract_starts_at(
                child_in_child_state
            ) or destruction.child_state_records_empty(child_in_child_state):
                continue
            self._validate_destroyed(child_position, found, contract, destruction)
        # A caller-passed child particle still needs its own contract even when
        # the particle at its parent position was created locally: higher callers
        # may know additional Destructors assigned to the child particle.
        if from_caller:
            self._re_record_destruction_contract(
                destruction_fact,
                particle,
                destruction.propagated_contracts,
                contract.connection,
                contract.position_in_child_state(position),
                verified_destructors,
                newly_verified,
            )
        # Record only occupied child positions absent from the callee's
        # destruction-time state. Append after visiting their children so the
        # contributed Destroy operations are recorded child before parent; the
        # contracted position itself is destroyed by the callee.
        if is_newly_occupied_child:
            contract.work.positions.append(
                destruction_contract_types.DestroyedPosition(
                    contract.from_particle(position),
                    destruction_fact.destroyed_position_in_destroyer,
                )
            )

    def _validate_one_cascade_destructor(
        self,
        destructor_quality: ast.GlobalTypedNameReference,
        position: ast.PositionReference,
        particle: particle_info.ParticleInfo,
        contract: _CalleeDestructionContractInCaller,
        destruction: _CalleeDestructionInCaller,
        *,
        newly_verified: list[ast.GlobalTypedNameReference],
    ) -> ast.ActionReference | None:
        """Validate one Destructor discovered through a Destruction Contract, and record the requirements of it that only this action's caller can validate."""
        destructor_contract = self._validation_state.get_contract_or_none(
            destructor_quality
        )
        if destructor_contract is None:
            return None
        action_chain = position.with_action_suffix(destructor_quality)
        action_assignment = action_contract.ActionAssignment(
            quality=destructor_quality,
            assigned_to_position_name=particle.origin_position.typed_names[-1],
        )
        # This action is the lowest that knows the destructor, so it validates
        # every requirement it can and gains the rest, which its callers then
        # validate as ordinary requirements.
        resolved_requirements: list[_ResolvedRequirement] = []
        for occupancy_requirement in destructor_contract.occupancy_requirements:
            resolution = self._resolve_destructor_requirement(
                inner_req=occupancy_requirement,
                action_chain=action_chain,
                contract=contract,
                destruction=destruction,
                action_assignment=action_assignment,
            )
            if isinstance(resolution, action_contract.PositionRequirementInCaller):
                destruction.occupancy_requirements_for_caller.append(resolution)
            else:
                resolved_requirements.append(resolution)
        for value_requirement in destructor_contract.value_requirements:
            resolution = self._resolve_destructor_requirement(
                inner_req=value_requirement,
                action_chain=action_chain,
                contract=contract,
                destruction=destruction,
                action_assignment=action_assignment,
            )
            if isinstance(resolution, action_contract.PositionRequirementInCaller):
                destruction.value_requirements_for_caller.append(resolution)
            else:
                resolved_requirements.append(resolution)
        for resolved_requirement in resolved_requirements:
            if isinstance(
                resolved_requirement.requirement, action_contract.ValueRequirement
            ):
                required_particle = destruction.caller_particles.get(
                    resolved_requirement.state_key
                )
                if required_particle is not None:
                    self._dead_value_write_validator.mark_particle_used(
                        required_particle
                    )
            occupancy = resolved_requirement.occupancy
            if not requirement_violation.is_violated(
                resolved_requirement.requirement,
                occupancy.state,
                resolved_requirement.value_state,
            ):
                continue
            destruction.validation_diagnostics.append(
                requirement_violation.contract_destructor(
                    propagated_requirement=resolved_requirement.requirement,
                    resolved_position=resolved_requirement.position,
                    occupancy=occupancy,
                    definition=self._definition,
                    destroying_definition=contract.destroying_definition,
                    destruction_contract=contract.contract,
                    propagation_steps=destruction.callee_contracts.propagation_steps(),
                    particle_position=position,
                    particle=particle,
                    trigger=destruction.trigger,
                    destructor_quality=destructor_quality,
                )
            )
        newly_verified.append(destructor_quality)
        return action_chain

    def _requirement_of_callee[Requirement: action_contract.PositionRequirement](
        self,
        destructor_requirement: Requirement,
        contract: _CalleeDestructionContractInCaller,
        destruction: _CalleeDestructionInCaller,
    ) -> Requirement:
        """Return ``destructor_requirement`` as a requirement of the callee: the destroyer's requirement, propagated through each action between the callee and the destroyer."""
        destruction_fact = contract.contract.propagated_destruction.destruction_fact
        requirement = destructor_requirement.propagated_to(
            contract.destroying_definition,
            inferred_at=destruction_fact.destruction.directly_destroyed_position.location,
            position=destructor_requirement.position.in_caller(
                destruction_fact.destroyed_position_in_destroyer
            ),
            action_assignment=None,
        )
        return destruction.callee_contracts.destroyer_requirement_as_callee_requirement(
            requirement
        )

    def _resolve_destructor_requirement[
        Requirement: action_contract.PositionRequirement
    ](
        self,
        *,
        inner_req: Requirement,
        action_chain: ast.ActionReference,
        contract: _CalleeDestructionContractInCaller,
        destruction: _CalleeDestructionInCaller,
        action_assignment: action_contract.ActionAssignment,
    ) -> (
        _ResolvedRequirement | action_contract.PositionRequirementInCaller[Requirement]
    ):
        """Resolve one requirement's position to its destruction-time state, or return the requirement for this action's caller when only the caller can know it."""
        # action_chain:
        #   position<box>::action</close_file>::position<target>::action</delete_file_destructor>
        # required_position:
        #   position<box>::action</close_file>::position<target>::position</file>
        # names below the contract's particle:
        #   ("position</file>",)
        required_position = inner_req.position.in_caller(action_chain)
        state_key = contract.position_in_child_state(required_position)
        merged_child_state = destruction.propagated_contracts.child_state
        occupancy = merged_child_state.occupancy_at(state_key)
        value_state = None
        if isinstance(inner_req, action_contract.ValueRequirement):
            value_state = merged_child_state.value_at(state_key)
        if occupancy is None:
            # Nothing below changed a position below a particle from the
            # caller, so it is as the caller left it.
            owner_position, owner = destruction.nearest_caller_particle(state_key)
            # An action that puts a particle in an interface position of an
            # action on a particle must trigger that action itself (Dead
            # Interface Positions), and a Destructor triggers only when its
            # particle is destroyed. So only the destroyer could have filled
            # one, and one that nothing below recorded is empty.
            # TODO: That makes a Destructor's interface positions useless to
            # every action but the destroyer. Consider a spec change that
            # forbids Destructors from defining interface positions.
            is_interface_position = any(
                chained_name.is_action_key(name)
                for name in state_key[len(owner_position) :]
            )
            if (
                owner.source is particle_info.ParticleSource.CALLER
                and not is_interface_position
            ):
                return action_contract.PositionRequirementInCaller(
                    requirement=self._requirement_of_callee(
                        inner_req, contract, destruction
                    ),
                    caller_position=destruction.position_in_caller(
                        required_position, state_key
                    ),
                    action_assignment=action_assignment,
                )
            # Child State already says what is in every occupied child
            # position. Check the tracker for errors on parent names before
            # treating a position Child State says nothing about as empty.
            if self._tracker.has_error_state(required_position):
                occupancy = position_occupancy.ERROR_OCCUPANCY
            else:
                occupancy = position_occupancy.EMPTY_OCCUPANCY
        if (
            isinstance(inner_req, action_contract.ValueRequirement)
            and occupancy.state == position_occupancy.PositionOccupancyState.OCCUPIED
            and value_state is None
        ):
            # Neither the callee nor this action knows the value, so it is as
            # this action's caller left it.
            return action_contract.PositionRequirementInCaller(
                requirement=self._requirement_of_callee(
                    inner_req, contract, destruction
                ),
                caller_position=destruction.position_in_caller(
                    required_position, state_key
                ),
                action_assignment=action_assignment,
            )
        return _ResolvedRequirement(
            requirement=inner_req,
            position=required_position,
            state_key=state_key,
            occupancy=occupancy,
            value_state=value_state,
        )


def _destruction_fact_and_verified_destructors(
    position: ast.PositionReference,
    particle: particle_info.ParticleInfo,
    contract: _CalleeDestructionContractInCaller,
) -> tuple[
    destruction_contract_types.DestructionFact, quality_assignment.QualityAssignments
]:
    """Return the Destruction Fact of ``particle``, in ``position``, the contract's particle or one below it, and the Destructors on it that the callee already verified."""
    contract_fact = contract.contract.propagated_destruction.destruction_fact
    if particle is contract.particle:
        return contract_fact, contract.contract.verified_destructors
    fact = destruction_contract_types.DestructionFact(
        destruction=contract_fact.destruction,
        # The contracted position can have a different name in the caller,
        # but its child-name suffix is unchanged. Append only that suffix
        # to express the child's position in the destroying action.
        # For example, if the caller's position<box> corresponds to the
        # destroyer's position<target>, position<box>::position</child>
        # becomes position<target>::position</child>.
        destroyed_position_in_destroyer=contract_fact.destroyed_position_in_destroyer.with_position_suffix(
            *contract.from_particle(position).typed_names
        ),
    )
    return fact, quality_assignment.EMPTY_QUALITY_ASSIGNMENTS
