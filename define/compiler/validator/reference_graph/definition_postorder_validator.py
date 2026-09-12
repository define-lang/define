"""Post-order validation for a single definition during the reference graph DFS walk."""

from __future__ import annotations

import typing
from dataclasses import dataclass
from functools import cached_property

from define.compiler import ast, diagnostics
from define.compiler.graphs import action_call_graph
from define.compiler.validator import scope_tracker
from define.compiler.validator.reference_graph import (
    action_contract,
    child_state,
    operation_graph_model,
    particle_info,
    particle_operation_validator,
    particle_tracker,
    position_occupancy,
    quality_assignment,
    reference_graph_validation_state,
    requirement_violation,
)
from define.compiler.validator.reference_graph import (
    destruction_contract as destruction_contract_types,
)
from define.compiler.validator.reference_graph.dead_code import (
    dead_constraint_tracker,
)

if typing.TYPE_CHECKING:
    from collections.abc import Sequence

    from define.compiler.data_structures import typed_name_dict
    from define.compiler.validator import validation_result
    from define.compiler.validator.reference_graph import operation_graph


@dataclass
class PostorderValidationResult:
    """Result of validating a single definition during the DFS post-order walk."""

    diagnostics: list[diagnostics.Diagnostic]
    edges: list[action_call_graph.ActionGraphEdge]
    contract: action_contract.ActionContract
    operation_graph: operation_graph.OperationGraph
    destructions: dict[ast.SourceLocation, list[ast.PositionReference]]
    triggered_actions: action_contract.TriggeredActions


@dataclass(frozen=True, slots=True)
class _ResolvedRequirement:
    """A destructor requirement whose required position's destruction-time occupancy is known here."""

    requirement: action_contract.PositionRequirement
    position: ast.PositionReference
    occupancy: position_occupancy.ChildOccupancy
    callee_destroy_position_relative_to_destroyed_particle: tuple[str, ...] | None

    def as_verified_destruction_contract_requirement(
        self,
    ) -> operation_graph_model.VerifiedDestructionContractRequirement:
        return operation_graph_model.VerifiedDestructionContractRequirement(
            requirement_position=self.requirement.position,
            caller_position=self.position,
            callee_destroy_position_relative_to_destroyed_particle=(
                self.callee_destroy_position_relative_to_destroyed_particle
            ),
        )


def _verified_destructor_guarantees(
    action_chain: ast.ActionReference,
    contract: action_contract.ActionContract,
    requirements: Sequence[
        operation_graph_model.VerifiedDestructionContractRequirement
    ],
) -> list[operation_graph_model.VerifiedDestructionContractDestructorGuarantee]:
    requirements_by_caller_position: dict[
        tuple[str, ...],
        operation_graph_model.VerifiedDestructionContractRequirement,
    ] = {}
    for requirement in requirements:
        requirements_by_caller_position[
            requirement.caller_position.canonical_chained_name_tuple
        ] = requirement

    verified_guarantees: list[
        operation_graph_model.VerifiedDestructionContractDestructorGuarantee
    ] = []
    action_chain_key = action_chain.canonical_chained_name_tuple
    for final_operation in contract.final_operations:
        # Operations on a callee's interface positions do not guarantee the
        # state of a position required by this Destructor.
        if final_operation.position not in contract.guarantees:
            continue
        guaranteed_position = final_operation.position
        caller_position = ast.chain_in_caller(action_chain_key, guaranteed_position)
        # A requirement's Destroy precedes the Destroy for a requirement on one
        # of its parent positions. Searching from the guaranteed position toward
        # its parents therefore retains only the direct dependency.
        requirement_positions = (
            caller_position[:depth] for depth in range(len(caller_position), 0, -1)
        )
        related_requirement = next(
            requirements_by_caller_position[position]
            for position in requirement_positions
            if position in requirements_by_caller_position
        )
        verified_guarantees.append(
            operation_graph_model.VerifiedDestructionContractDestructorGuarantee(
                guarantee=operation_graph_model.OperationGraphGuarantee(
                    guaranteed_position=guaranteed_position,
                    operation_positions=final_operation.operation_positions,
                ),
                requirement=related_requirement,
            )
        )
    return verified_guarantees


@dataclass(frozen=True, slots=True)
class _DestructionTarget:
    """A particle whose destruction also destroys its occupied children."""

    position: ast.PositionReference
    destruction: destruction_contract_types.SimultaneousDestruction
    auto_destruction_target: ast.PositionReference | None


@dataclass(frozen=True, slots=True)
class _PendingDestructionContract:
    """A Destruction Contract captured before tracked particle state changes."""

    particle: particle_info.ParticleInfo
    destruction_fact: destruction_contract_types.DestructionFact


@dataclass(frozen=True, slots=True)
class _DestructionContractInCaller:
    """A callee's Destruction Contract and its particle from the caller's perspective."""

    contract: action_contract.DestructionContract
    position: ast.PositionReference


class ActionPostorderValidator:
    """Validates an action definition during a DFS post-order walk of the reference graph."""

    _definition_result: validation_result.DefinitionValidationResult
    _definition_results: typed_name_dict.TypedNameDict[
        ast.GlobalTypedName, validation_result.DefinitionValidationResult
    ]
    _validation_state: reference_graph_validation_state.ReferenceGraphValidationState
    _diagnostics: list[diagnostics.Diagnostic]
    _action_edges: list[action_call_graph.ActionGraphEdge]
    _inferred_requirements: dict[tuple[str, ...], action_contract.PositionRequirement]
    _destruction_contracts: list[action_contract.DestructionContracts]
    _dead_constraint_tracker: dead_constraint_tracker.DeadConstraintTracker

    def __init__(
        self,
        definition_result: validation_result.DefinitionValidationResult,
        definition_results: typed_name_dict.TypedNameDict[
            ast.GlobalTypedName, validation_result.DefinitionValidationResult
        ],
        validation_state: reference_graph_validation_state.ReferenceGraphValidationState,
    ):
        """Initialize with the definition to validate and the full results map."""
        self._definition_result = definition_result
        self._definition_results = definition_results
        self._validation_state = validation_state
        self._diagnostics = []
        self._action_edges = []
        self._inferred_requirements = {}
        self._destruction_contracts = []
        self._triggered_actions: action_contract.TriggeredActions = {}
        self._destructions: dict[ast.SourceLocation, list[ast.PositionReference]] = {}
        self._dead_constraint_tracker = dead_constraint_tracker.DeadConstraintTracker()

    @property
    def _definition(self) -> ast.QualityDefinition:
        return self._definition_result.definition

    @property
    def _enclosing_fqun(self) -> ast.Fqun:
        return self._definition.typed_name.name_content.fqun

    @cached_property
    def _tracker(self) -> particle_tracker.ParticleTracker:
        return particle_tracker.ParticleTracker(self._definition.typed_name)

    @cached_property
    def _operation_validator(
        self,
    ) -> particle_operation_validator.ParticleOperationValidator:
        return particle_operation_validator.ParticleOperationValidator(
            self._tracker, self._enclosing_fqun
        )

    @cached_property
    def _implied_quality_list(self) -> tuple[ast.GlobalTypedNameReference, ...]:
        return tuple(
            impl.typed_global_name for impl in self._definition.quality_implications
        )

    def _record_requirement(
        self,
        *,
        required_state: position_occupancy.PositionOccupancyState,
        contracted_position: ast.PositionReference,
        local_position: ast.PositionReference,
        inferred_at: ast.SourceLocation,
        propagated_from: action_contract.PositionRequirement | None,
        scope: scope_tracker.ScopeTracker,
        action_assignment: action_contract.ActionAssignment | None = None,
    ):
        """Record a requirement in this definition's contract and reflect it in the tracker.

        Args:
            required_state: The state that the requirement says the position must be in.
            contracted_position: The requirement's position as we expose it in
                this action's contract.
            local_position: The position in this definition's local namespace
                that we are actually operating on.
            inferred_at: The statement this action inferred the requirement at.
            propagated_from: The inner requirement this was propagated
                from, or None for a directly inferred requirement.
            scope: The scope tracker (for resolving qualities of local positions).
        """
        # Profiles of dense action call graphs make requirement recording and
        # propagation look like avoidable allocation and repeated-pass costs.
        # Experiments in July 2026 showed that those apparent costs are mostly
        # required by later consumers or already shared and batched:
        # - Storing canonical-name tuples as the primary data and creating
        #   PositionReferences only when requested made dense action call graphs
        #   14-16% slower and a deeply chained position-operation workload 20%
        #   slower. Propagation and diagnostics request PositionReferences for
        #   most requirements, so the prototype added conversions without
        #   avoiding the original objects.
        # - Combining requirement propagation stages into one pass changed
        #   runtime by only about 1%. The existing code already shares caller
        #   PositionReferences and batches nearest-particle work.
        # Revisit only if those consumers or the propagation pipeline change
        # substantially.
        requirement_key = contracted_position.canonical_chained_name_tuple
        self._inferred_requirements[requirement_key] = (
            action_contract.PositionRequirement(
                required_state=required_state,
                position=contracted_position,
                inferred_at=inferred_at,
                enclosing_action=self._action_definition,
                propagated_from=propagated_from,
                action_assignment=action_assignment,
            )
        )
        # ERROR represents a tracker failure and is never a Position Requirement state.
        requirement_state = typing.cast(
            "typing.Literal[position_occupancy.PositionOccupancyState.OCCUPIED, position_occupancy.PositionOccupancyState.EMPTY]",
            required_state,
        )
        match requirement_state:
            case position_occupancy.PositionOccupancyState.OCCUPIED:
                # We can't know exactly what qualities the particle has, but we
                # can know the minimal set that it _must_ have according to the constraints
                # the contracted position has.
                qualities = self._get_transitive_required_qualities(
                    contracted_position, scope
                )
                self._tracker.create(
                    local_position,
                    qualities,
                    from_caller=contracted_position,
                )
            case position_occupancy.PositionOccupancyState.EMPTY:
                self._tracker.mark_empty(local_position)

    # TODO: Classify every Position Requirement once, in one batched tracker
    # query, as either needing propagation or local violation checking. The
    # current propagation pass inspects position state and particle provenance,
    # records assumptions for propagated requirements, and then the checking
    # pass queries every position again. A combined result must classify all
    # requirements from the pre-assumption state and retain occupancy information
    # for the requirements that need local violation checking.
    def _propagate_action_requirements(
        self,
        action_chain: ast.ActionReference,
        scope: scope_tracker.ScopeTracker,
        requirements_in_caller: list[action_contract.PositionRequirementInCaller],
        action_assignment: action_contract.ActionAssignment | None,
    ):
        """Propagate the triggered action's requirements into this definition's contract."""
        propagated_requirements = self._tracker.propagate_requirements(
            requirements_in_caller
        )
        for propagated in propagated_requirements:
            self._record_requirement(
                required_state=(
                    propagated.requirement_in_caller.requirement.required_state
                ),
                contracted_position=propagated.contracted_position,
                local_position=propagated.requirement_in_caller.caller_position,
                inferred_at=action_chain.location,
                propagated_from=propagated.requirement_in_caller.requirement,
                scope=scope,
                action_assignment=action_assignment,
            )

    def _maybe_infer_requirements_on_chain(
        self,
        required_state: position_occupancy.PositionOccupancyState,
        position: ast.PositionReference,
        scope: scope_tracker.ScopeTracker,
    ):
        """Infer requirements for a position and all its parent positions.

        The leaf position uses the given required_state; all parent positions
        use OCCUPIED, since a parent must be occupied for its child to be
        accessible.
        """
        inferred_requirements = self._tracker.infer_direct_requirements(
            position,
            required_state,
            self._interface_positions,
        )
        for resolved_requirement in inferred_requirements:
            local_position = resolved_requirement.local_position
            self._record_requirement(
                required_state=resolved_requirement.required_state,
                contracted_position=resolved_requirement.contracted_position,
                local_position=local_position,
                inferred_at=resolved_requirement.contracted_position.location,
                propagated_from=None,
                scope=scope,
            )

    def _run_constructors(
        self,
        statement: ast.CreateParticleStatement,
        qualities: quality_assignment.QualityAssignments,
        scope: scope_tracker.ScopeTracker,
    ):
        """Trigger every constructor on the particle just created in position (DLP 32)."""
        position = statement.target_position
        for quality in qualities.assignments:
            if quality.name_type != ast.NameType.ACTION:
                continue
            definition_result = self._definition_results.get(quality)
            # The constructor's file may have failed to load or parse, which is
            # reported elsewhere; skipping it here keeps destruction analysis
            # from failing on an already-reported error.
            if definition_result is None:
                continue
            definition = typing.cast(
                "ast.ActionDefinition", definition_result.definition
            )
            if not definition.is_constructor:
                continue
            contract = self._validation_state.get_contract(quality)
            # The constructor is a quality of the particle in `position`, so its
            # interface positions hang off position::action</construct> while its
            # implied qualities hang off the position itself.
            action_chain = position.with_action_suffix(quality)
            self._fire_triggered_action(
                contract,
                action_chain,
                position,
                scope,
                triggering_statement=statement,
                current_position=position,
                parent_particle=self._tracker.get_occupant(position),
                action_assignment=action_contract.ActionAssignment(
                    quality=quality,
                    assigned_to_position_name=position.typed_names[-1],
                ),
            )

    def _destroy_particles(
        self,
        targets: Sequence[_DestructionTarget],
        scope: scope_tracker.ScopeTracker,
        location: ast.SourceLocation,
    ):
        """Destroy the target particles and their occupied transitive children."""
        destruction: list[ast.PositionReference] = []
        particle_destructions: list[particle_tracker.ParticleDestruction] = []
        destructors: list[
            tuple[action_contract.Destructor, ast.PositionReference | None]
        ] = []
        snapshot_positions: list[ast.PositionReference] = []
        pending_contracts_by_target: list[list[_PendingDestructionContract]] = []
        for target in targets:
            destruction_facts: list[destruction_contract_types.DestructionFact] = []
            pending_contracts: list[_PendingDestructionContract] = []
            particle_destructions.append(
                particle_tracker.ParticleDestruction(target.position, destruction_facts)
            )
            self._collect_particle_destructions(
                target.position,
                self._tracker.get_occupant(target.position),
                target,
                destruction_facts,
                destructors,
                pending_contracts,
                destruction,
            )
            if pending_contracts:
                snapshot_positions.append(target.position)
                pending_contracts_by_target.append(pending_contracts)

        child_states = self._tracker.snapshot_child_states(snapshot_positions)

        for destructor, auto_destruction_target in destructors:
            self._run_destructor(
                destructor,
                scope,
                location,
                auto_destruction_target=auto_destruction_target,
            )

        self._destructions[location] = destruction
        self._tracker.destroy_simultaneously(particle_destructions)
        for shared_state, pending_contracts in zip(
            child_states, pending_contracts_by_target, strict=True
        ):
            contracts = action_contract.DestructionContracts(child_state=shared_state)
            for pending_contract in pending_contracts:
                self._record_destruction_contract(
                    pending_contract.particle,
                    contracts,
                    pending_contract.destruction_fact,
                )
            self._destruction_contracts.append(contracts)

    def _collect_particle_destructions(
        self,
        position: ast.PositionReference,
        particle: particle_info.ParticleInfo,
        target: _DestructionTarget,
        destruction_facts: list[destruction_contract_types.DestructionFact],
        destructors: list[
            tuple[action_contract.Destructor, ast.PositionReference | None]
        ],
        pending_contracts: list[_PendingDestructionContract],
        destruction: list[ast.PositionReference],
    ):
        """Collect one particle and every occupied transitive child."""
        destruction_fact = destruction_contract_types.DestructionFact(
            destruction=target.destruction,
            destroyed_position_in_destroyer=position,
        )
        destruction_facts.append(destruction_fact)
        if particle.from_caller:
            pending_contracts.append(
                _PendingDestructionContract(
                    particle=particle,
                    destruction_fact=destruction_fact,
                )
            )

        # A particle keeps its own qualities across Moves, so its qualities—not
        # the current Position's constraints—determine its child Positions and
        # Destructors.
        for quality in particle.qualities.assignments:
            if quality.name_type == ast.NameType.POSITION:
                child = position.with_position_suffix(quality)
                self._collect_child_particle_destructions(
                    child,
                    target,
                    destruction_facts,
                    destructors,
                    pending_contracts,
                    destruction,
                )
            else:
                definition_result = self._definition_results.get(quality)
                if definition_result is None:
                    continue
                definition = typing.cast(
                    "ast.ActionDefinition", definition_result.definition
                )
                if definition.is_destructor:
                    destructors.append(
                        (
                            action_contract.Destructor(
                                destructor=quality,
                                position=position,
                                origin_position=particle.origin_position,
                            ),
                            target.auto_destruction_target,
                        )
                    )
                for interface_position in definition.interface_positions:
                    child = position.with_position_suffix(
                        quality, interface_position.typed_name
                    )
                    self._collect_child_particle_destructions(
                        child,
                        target,
                        destruction_facts,
                        destructors,
                        pending_contracts,
                        destruction,
                    )

        # Children must remain accessible until their own Destroy executes.
        destruction.append(position)

    def _collect_child_particle_destructions(
        self,
        position: ast.PositionReference,
        target: _DestructionTarget,
        destruction_facts: list[destruction_contract_types.DestructionFact],
        destructors: list[
            tuple[action_contract.Destructor, ast.PositionReference | None]
        ],
        pending_contracts: list[_PendingDestructionContract],
        destruction: list[ast.PositionReference],
    ):
        """Collect an occupied child Position's transitive destruction."""
        occupancy = self._tracker.get_occupancy_info(position)
        if occupancy.has_error or occupancy.occupant is None:
            return
        self._collect_particle_destructions(
            position,
            occupancy.occupant,
            target,
            destruction_facts,
            destructors,
            pending_contracts,
            destruction,
        )

    def _record_destruction_contract(
        self,
        particle: particle_info.ParticleInfo,
        contracts: action_contract.DestructionContracts,
        destruction_fact: destruction_contract_types.DestructionFact,
    ):
        """Record the Destruction Contract for one caller-passed particle."""
        contracts.append(
            action_contract.DestructionContract(
                destroyed_position_contracted=particle.origin_position,
                destruction_fact=destruction_fact,
                # The snapshot's names are relative to the directly destroyed
                # Position. For a Destroy of position<box>, a particle at
                # position<box>::position</child> uses just position</child>
                # to find its child state; the particle at position<box> uses ().
                position_in_child_state=destruction_fact.destroyed_position_in_destroyer.canonical_chained_name_tuple[
                    len(
                        destruction_fact.destruction.directly_destroyed_position.typed_names
                    ) :
                ],
                # We know these destructors exist at destruction time, so they are
                # handled through the normal requirements mechanism (fired and
                # propagated as this action's own requirements), not through the
                # Destruction Contract's requirement-verification mechanism.
                verified_destructors=self._destructor_quality_assignments(
                    particle.qualities
                ),
            )
        )

    def _run_destructor(
        self,
        destructor: action_contract.Destructor,
        scope: scope_tracker.ScopeTracker,
        location: ast.SourceLocation,
        auto_destruction_target: ast.PositionReference | None = None,
    ):
        """Trigger one directly known destructor before particle destruction."""
        # A destructor's requirements are checked as though it triggered
        # synchronously at the moment of destruction (DLP 41). The destructor is a
        # quality of the particle in `position`, so its interface positions
        # hang off position::action</destructor> while its implied qualities hang off
        # position itself; in_caller maps both correctly from this chain.
        destructor_name = destructor.destructor
        contract = self._validation_state.get_contract_or_none(destructor_name)
        if contract is None:
            return
        action_chain = destructor.position.with_action_suffix(destructor_name)
        self._triggered_actions.setdefault(location, []).append(action_chain)
        parent_particle = self._tracker.get_occupant(destructor.position)
        requirements_in_caller = contract.requirements_in_caller(action_chain)
        self._mark_callee_contract_constraints_alive(requirements_in_caller, scope)
        self._propagate_action_requirements(
            action_chain,
            scope,
            requirements_in_caller,
            destructor.action_assignment(),
        )
        self._check_destructor_requirements(
            destructor,
            requirements_in_caller,
            auto_destruction_target=auto_destruction_target,
        )
        occupied_interface_child_position_violations = self._tracker.trigger_action(
            action_chain,
            contract,
            destructor.position,
            requirements_in_caller,
            is_destructor=True,
            parent_particle=parent_particle,
        )
        self._record_occupied_interface_child_position_violations(
            destructor_name,
            occupied_interface_child_position_violations,
        )
        self._action_edges.append(
            action_call_graph.ActionGraphEdge(
                source=self._definition.typed_name.source_typed_name,
                target=destructor_name.full_typed_name,
            )
        )

    def _process_action_position_arrival(
        self,
        statement: ast.CreateParticleStatement | ast.MoveParticleStatement,
        action_chain: ast.ActionReference,
        scope: scope_tracker.ScopeTracker,
    ):
        """Record an action-position arrival and trigger its final action if appropriate."""
        position = statement.target_position
        particle = self._tracker.get_occupant(position)
        action = action_chain.get_last_action()
        parent_position = action_chain.parent_position()
        parent_particle = (
            self._tracker.get_occupant(parent_position)
            if parent_position is not None
            else None
        )
        contract = self._validation_state.get_contract_or_none(action)
        if contract is None:
            return
        # Only trigger when filling a single interface position directly,
        # not children of interface positions.
        if len(position.typed_names) != len(action_chain.typed_names) + 1:
            return
        trigger_element = typing.cast(
            "ast.LocalTypedNameReference", position.typed_names[-1]
        )
        if trigger_element.full_typed_name != contract.trigger_position_name:
            return

        self._mark_contract_position_constraints_alive(position, particle, scope)

        self._fire_triggered_action(
            contract,
            action_chain,
            particle.last_position,
            scope,
            triggering_statement=statement,
            current_position=parent_position,
            parent_particle=parent_particle,
        )

    def _fire_triggered_action(
        self,
        contract: action_contract.ActionContract,
        action_chain: ast.ActionReference,
        acting_on_position: ast.PositionReference,
        scope: scope_tracker.ScopeTracker,
        *,
        triggering_statement: ast.CreateParticleStatement | ast.MoveParticleStatement,
        current_position: ast.PositionReference | None,
        parent_particle: particle_info.ParticleInfo | None,
        action_assignment: action_contract.ActionAssignment | None = None,
    ):
        self._triggered_actions.setdefault(triggering_statement.location, []).append(
            action_chain
        )
        action = action_chain.get_last_action()
        # Requirement propagation, requirement checking, and the operation graph
        # each need every requirement's position from the caller's perspective
        # (req.position.in_caller(action_chain)). Deriving it is a fresh
        # allocation, so compute it once here and hand the same objects to all
        # three rather than rebuilding it three times per requirement per trigger.
        requirements_in_caller = contract.requirements_in_caller(action_chain)
        self._mark_callee_contract_constraints_alive(requirements_in_caller, scope)
        self._propagate_action_requirements(
            action_chain,
            scope,
            requirements_in_caller,
            action_assignment,
        )
        self._check_requirements(
            acting_on_position,
            requirements_in_caller,
            action_assignment=action_assignment,
        )
        destruction_contract_contributions = self._check_destruction_contracts(
            contract,
            action_chain,
        )
        origin_position = (
            parent_particle.origin_position if parent_particle is not None else None
        )
        self._dead_constraint_tracker.mark_action_alive(
            action, current_position, origin_position
        )
        occupied_interface_child_position_violations = self._tracker.trigger_action(
            action_chain,
            contract,
            acting_on_position,
            requirements_in_caller,
            is_destructor=False,
            parent_particle=parent_particle,
            destruction_contract_contributions=destruction_contract_contributions,
        )
        self._record_occupied_interface_child_position_violations(
            action,
            occupied_interface_child_position_violations,
        )
        self._action_edges.append(
            action_call_graph.ActionGraphEdge(
                source=self._definition.typed_name.source_typed_name,
                target=action.full_typed_name,
            )
        )

    def _record_occupied_interface_child_position_violations(
        self,
        action: ast.GlobalTypedNameReference,
        occupied_interface_child_position_violations: Sequence[
            tuple[ast.ChainedNameTuple, ast.SourceLocation]
        ],
    ):
        """Record occupied interface child positions found when one callee triggers."""
        for position, location in occupied_interface_child_position_violations:
            self._diagnostics.append(
                diagnostics.OccupiedActionInterfaceWhenActionTriggersDiagnostic(
                    location=location,
                    action_name=action.source_typed_name,
                    position_name=ast.source_form_chained_name(
                        position, self._enclosing_fqun.canonical
                    ),
                )
            )

    def _check_requirements(
        self,
        acting_on_position: ast.PositionReference,
        requirements_in_caller: list[action_contract.PositionRequirementInCaller],
        *,
        action_assignment: action_contract.ActionAssignment | None,
    ):
        """Emit diagnostics for every requirement in contract that doesn't hold at acting_on_position.

        ``requirements_in_caller`` contains the contract's requirements and
        their positions from the caller's perspective.
        """
        # Action Execution:
        #   the chain that triggered the execution:
        #     position<box>::action</outer>
        #   acting_on_position:
        #     position<box>::action</outer>::position<trigger>
        #   req.position:
        #     position<iface>::action</inner>::position<item>
        #   requirement_in_caller.caller_position (full_caller_chain):
        #     position<box>::action</outer>::position<iface>::action</inner>::position<item>
        for requirement_in_caller in requirements_in_caller:
            req = requirement_in_caller.requirement
            full_caller_chain = requirement_in_caller.caller_position
            violated, occupant = self._requirement_violation_occupant(
                full_caller_chain, req
            )
            if violated:
                self._diagnostics.append(
                    requirement_violation.trigger_violation(
                        req=req,
                        definition=self._definition,
                        full_caller_chain=full_caller_chain,
                        acting_on_position=acting_on_position,
                        occupant=occupant,
                        action_assignment=action_assignment,
                    )
                )

    def _requirement_violation_occupant(
        self,
        full_caller_chain: ast.PositionReference,
        req: action_contract.PositionRequirement,
    ) -> tuple[bool, particle_info.ParticleInfo | None]:
        occupancy = self._tracker.get_occupancy_info(full_caller_chain)
        if occupancy.has_error:
            return False, None
        occupant = occupancy.occupant
        empty_violation = (
            req.required_state == position_occupancy.PositionOccupancyState.EMPTY
            and occupant is not None
        )
        occupied_violation = (
            req.required_state == position_occupancy.PositionOccupancyState.OCCUPIED
            and occupant is None
        )
        return (empty_violation or occupied_violation, occupant)

    def _check_destructor_requirements(
        self,
        destructor: action_contract.Destructor,
        requirements_in_caller: list[action_contract.PositionRequirementInCaller],
        *,
        auto_destruction_target: ast.PositionReference | None,
    ):
        for requirement_in_caller in requirements_in_caller:
            req = requirement_in_caller.requirement
            full_caller_chain = requirement_in_caller.caller_position
            violated, occupant = self._requirement_violation_occupant(
                full_caller_chain, req
            )
            if violated:
                self._diagnostics.append(
                    requirement_violation.direct_destructor(
                        req=req,
                        definition=self._definition,
                        full_caller_chain=full_caller_chain,
                        occupant=occupant,
                        destructor=destructor,
                        auto_destruction_target=auto_destruction_target,
                    )
                )

    def _destructor_quality_assignments(
        self, qualities: quality_assignment.QualityAssignments
    ) -> quality_assignment.QualityAssignments:
        """Return the destructor assignments among a particle's qualities."""
        # TODO: This feels inefficient to do every time, but let's wait for actual
        # profiling data to tell us if that's important.
        result: list[ast.GlobalTypedNameReference] = []
        for quality in qualities.assignments:
            if quality.name_type != ast.NameType.ACTION:
                continue
            definition_result = self._definition_results.get(quality)
            # Reference validation has already reported unresolved qualities;
            # their absence must not prevent checking the remaining Destructors.
            if definition_result is None:
                continue
            definition = typing.cast(
                "ast.ActionDefinition", definition_result.definition
            )
            if definition.is_destructor:
                result.append(quality)
        return quality_assignment.QualityAssignments(tuple(result))

    def _check_destruction_contracts(
        self,
        contract: action_contract.ActionContract,
        action_chain: ast.ActionReference,
    ) -> Sequence[operation_graph_model.DestructionContractContribution]:
        """Check a callee's Destruction Contracts from the caller's perspective."""
        if not contract.destruction_contracts:
            return ()
        # All collections use the same current step, but each extends its own
        # preceding history without copying the earlier steps.
        trigger_step = action_contract.PropagationStep(
            location=action_chain.location,
            kind=action_contract.PropagationKind.ACTION_TRIGGER,
            enclosing_quality_name=self._definition.typed_name.source_typed_name,
            triggered_quality_name=action_chain.typed_names[-1].full_typed_name,
        )
        contributions: list[operation_graph_model.DestructionContractContribution] = []
        for callee_contracts in contract.destruction_contracts:
            caller_contracts: list[_DestructionContractInCaller] = []
            caller_knowledge: position_occupancy.ChildOccupancyMap = {}
            for destruction_contract in callee_contracts.particles:
                position = destruction_contract.destroyed_position_contracted.in_caller(
                    action_chain
                )
                # The action's requirement check already handles missing or
                # error-state particles, so there is nothing more to verify here.
                occupancy = self._tracker.get_occupancy_info(position)
                if occupancy.occupant is None:
                    continue
                caller_contracts.append(
                    _DestructionContractInCaller(destruction_contract, position)
                )
                self._tracker.add_child_state(
                    caller_knowledge,
                    callee_contracts.child_state,
                    position,
                    destruction_contract.position_in_child_state,
                    callee_contracts.positions,
                )
            propagated_contracts = action_contract.DestructionContracts(
                child_state=callee_contracts.child_state.with_caller(caller_knowledge),
                propagation=action_contract.PropagationHistory(
                    trigger_step, callee_contracts.propagation
                ),
            )
            for caller_contract in caller_contracts:
                contribution = self._check_one_destruction_contract(
                    caller_contract,
                    trigger_step,
                    callee_contracts,
                    propagated_contracts,
                )
                if contribution is not None:
                    contributions.append(contribution)
            if propagated_contracts.particles:
                self._destruction_contracts.append(propagated_contracts)
        return contributions

    def _check_one_destruction_contract(
        self,
        caller_contract: _DestructionContractInCaller,
        trigger_step: action_contract.PropagationStep,
        callee_contracts: action_contract.DestructionContracts,
        propagated_contracts: action_contract.DestructionContracts,
    ) -> operation_graph_model.DestructionContractContribution | None:
        destruction_contract = caller_contract.contract
        caller_particle_position = caller_contract.position
        destroying_definition_result = self._definition_results[
            destruction_contract.destruction_fact.destruction.destroying_action
        ]
        destroying_definition = typing.cast(
            "ast.ActionDefinition", destroying_definition_result.definition
        )
        destructor_contributions: list[
            operation_graph_model.VerifiedDestructionContractDestructor
        ] = []
        newly_occupied_children: list[
            operation_graph_model.ContributedDestructionPosition
        ] = []
        previous_contract_count = len(propagated_contracts.particles)
        final_contributed_positions = self._verify_destruction_cascade(
            caller_particle_position,
            destruction_contract=destruction_contract,
            destroying_definition=destroying_definition,
            caller_prefix_length=len(caller_particle_position.typed_names),
            trigger_step=trigger_step,
            callee_contracts=callee_contracts,
            propagated_contracts=propagated_contracts,
            destructor_contributions=destructor_contributions,
            newly_occupied_children=newly_occupied_children,
            callee_destroy_position=(),
        )
        # Verification only appends contracts, and a child particle can propagate
        # even when this particle does not, so any added contract counts here.
        is_propagated = len(propagated_contracts.particles) != previous_contract_count
        # A locally created parent can have a caller-passed child. Propagation
        # ends independently for each particle, not for the whole destruction.
        if (
            not is_propagated
            and not newly_occupied_children
            and not destructor_contributions
        ):
            return None
        return operation_graph_model.DestructionContractContribution(
            destruction_fact=destruction_contract.destruction_fact,
            destroyed_particle_position=caller_particle_position,
            children=newly_occupied_children,
            final_contributed_positions=final_contributed_positions,
            is_propagated_to_caller=is_propagated,
            destructors=destructor_contributions,
        )

    def _re_record_destruction_contract(
        self,
        destruction_fact: destruction_contract_types.DestructionFact,
        caller_particle: particle_info.ParticleInfo,
        propagated_contracts: action_contract.DestructionContracts,
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
        propagated_contracts.append(
            action_contract.DestructionContract(
                destroyed_position_contracted=caller_particle.origin_position,
                destruction_fact=destruction_fact,
                position_in_child_state=position_in_child_state,
                verified_destructors=verified_destructors,
            )
        )

    def _verify_destruction_cascade(
        self,
        position: ast.PositionReference,
        *,
        destruction_contract: action_contract.DestructionContract,
        destroying_definition: ast.ActionDefinition,
        caller_prefix_length: int,
        trigger_step: action_contract.PropagationStep,
        callee_contracts: action_contract.DestructionContracts,
        propagated_contracts: action_contract.DestructionContracts,
        destructor_contributions: list[
            operation_graph_model.VerifiedDestructionContractDestructor
        ],
        newly_occupied_children: list[
            operation_graph_model.ContributedDestructionPosition
        ],
        callee_destroy_position: tuple[str, ...],
    ) -> tuple[operation_graph_model.ContributedDestructionPosition, ...]:
        position_key = position.canonical_chained_name_tuple
        relative_key = position_key[caller_prefix_length:]
        position_in_child_state = (
            *destruction_contract.position_in_child_state,
            *relative_key,
        )
        # Another Destruction Contract for this simultaneous destruction starts at this
        # position. It validates this position and its child names, so continuing
        # this traversal would record their caller-contributed Destroys twice.
        if relative_key and position_in_child_state in callee_contracts.positions:
            return ()
        occupancy_info = self._tracker.get_occupancy_info(position)
        if occupancy_info.has_error or occupancy_info.occupant is None:
            return ()
        occupancy = propagated_contracts.child_state.get(position_in_child_state)
        # A position the destruction-time picture records as empty was emptied
        # before the destruction, so nothing there was destroyed and thus there
        # is no more work to do.
        if (
            occupancy is not None
            and occupancy.state == position_occupancy.PositionOccupancyState.EMPTY
        ):
            return ()
        # A child absent from the contract was unknown to the callee but is
        # occupied from this caller's perspective, so this caller contributes
        # its Destroy. The contracted position itself is already destroyed by
        # the callee and therefore is not a contributed child Destroy.
        callee_occupancy = callee_contracts.child_occupancy(
            destruction_contract, relative_key
        )
        is_newly_occupied_child = bool(relative_key and callee_occupancy is None)
        callee_destroy_position_for_children = callee_destroy_position
        # When the callee recorded a Destroy for this position, any children
        # discovered by the caller must be destroyed before the callee-destroyed
        # position.
        if (
            callee_occupancy is not None
            and callee_occupancy.state
            == position_occupancy.PositionOccupancyState.OCCUPIED
        ):
            callee_destroy_position_for_children = relative_key
        particle = occupancy_info.occupant
        created_in_this_action = not particle.from_caller
        newly_verified: list[ast.GlobalTypedNameReference] = []
        if relative_key:
            destruction_fact = destruction_contract_types.DestructionFact(
                destruction=destruction_contract.destruction_fact.destruction,
                # The contracted position can have a different name in the caller,
                # but its child-name suffix is unchanged. Append only that suffix
                # to express the child's position in the destroying action.
                # For example, if the caller's position<box> corresponds to the
                # destroyer's position<target>, position<box>::position</child>
                # becomes position<target>::position</child>.
                destroyed_position_in_destroyer=destruction_contract.destruction_fact.destroyed_position_in_destroyer.with_position_suffix(
                    *position.typed_names[caller_prefix_length:]
                ),
            )
            verified_destructors = quality_assignment.EMPTY_QUALITY_ASSIGNMENTS
        else:
            destruction_fact = destruction_contract.destruction_fact
            verified_destructors = destruction_contract.verified_destructors
        destruction_contract_position = None
        final_contributed_positions: list[
            operation_graph_model.ContributedDestructionPosition
        ] = []
        for quality in reversed(particle.qualities.assignments):
            if quality.name_type == ast.NameType.POSITION:
                child = position.with_position_suffix(quality)
                final_contributed_positions.extend(
                    self._verify_destruction_cascade(
                        child,
                        destruction_contract=destruction_contract,
                        destroying_definition=destroying_definition,
                        caller_prefix_length=caller_prefix_length,
                        trigger_step=trigger_step,
                        callee_contracts=callee_contracts,
                        propagated_contracts=propagated_contracts,
                        destructor_contributions=destructor_contributions,
                        newly_occupied_children=newly_occupied_children,
                        callee_destroy_position=callee_destroy_position_for_children,
                    )
                )
            else:
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
                    if destruction_contract_position is None:
                        destruction_contract_position = (
                            operation_graph_model.DestructionContractPosition(
                                position,
                                relative_key,
                                callee_destroy_position_for_children,
                            )
                        )
                    destructor_contribution = self._verify_one_cascade_destructor(
                        destructor_quality=quality,
                        destruction_contract_position=destruction_contract_position,
                        particle=particle,
                        destruction_contract=destruction_contract,
                        callee_contracts=callee_contracts,
                        destroying_definition=destroying_definition,
                        caller_prefix_length=caller_prefix_length,
                        trigger_step=trigger_step,
                        merged_child_state=propagated_contracts.child_state,
                        created_in_this_action=created_in_this_action,
                        newly_verified=newly_verified,
                    )
                if destructor_contribution is not None:
                    destructor_contributions.append(destructor_contribution)
                for interface_position in reversed(definition.interface_positions):
                    child = position.with_position_suffix(
                        quality, interface_position.typed_name
                    )
                    final_contributed_positions.extend(
                        self._verify_destruction_cascade(
                            child,
                            destruction_contract=destruction_contract,
                            destroying_definition=destroying_definition,
                            caller_prefix_length=caller_prefix_length,
                            trigger_step=trigger_step,
                            callee_contracts=callee_contracts,
                            propagated_contracts=propagated_contracts,
                            destructor_contributions=destructor_contributions,
                            newly_occupied_children=newly_occupied_children,
                            callee_destroy_position=callee_destroy_position_for_children,
                        )
                    )

        # A caller-passed child particle still needs its own contract even when
        # the particle at its parent position was created locally: higher callers
        # may know additional Destructors assigned to the child particle.
        if particle.from_caller:
            self._re_record_destruction_contract(
                destruction_fact,
                particle,
                propagated_contracts,
                position_in_child_state,
                verified_destructors,
                newly_verified,
            )
        # Record only occupied child positions absent from the callee's
        # destruction-time state. Append after visiting their children so the
        # contributed Destroy operations are recorded child before parent; the
        # contracted position itself is destroyed by the callee.
        if is_newly_occupied_child:
            if destruction_contract_position is None:
                destruction_contract_position = (
                    operation_graph_model.DestructionContractPosition(
                        position,
                        relative_key,
                        callee_destroy_position,
                    )
                )
            contributed_position = operation_graph_model.ContributedDestructionPosition(
                destruction_contract_position,
                destruction_fact,
                tuple(reversed(final_contributed_positions)),
            )
            newly_occupied_children.append(contributed_position)
            return (contributed_position,)
        return tuple(final_contributed_positions)

    def _verify_one_cascade_destructor(
        self,
        *,
        destructor_quality: ast.GlobalTypedNameReference,
        destruction_contract_position: operation_graph_model.DestructionContractPosition,
        particle: particle_info.ParticleInfo,
        destruction_contract: action_contract.DestructionContract,
        callee_contracts: action_contract.DestructionContracts,
        destroying_definition: ast.ActionDefinition,
        caller_prefix_length: int,
        trigger_step: action_contract.PropagationStep,
        merged_child_state: child_state.ChildState,
        created_in_this_action: bool,
        newly_verified: list[ast.GlobalTypedNameReference],
    ) -> operation_graph_model.VerifiedDestructionContractDestructor | None:
        """Verify one Destructor discovered through a Destruction Contract."""
        destructor_contract = self._validation_state.get_contract_or_none(
            destructor_quality
        )
        if destructor_contract is None:
            return None
        particle_position = destruction_contract_position.position
        action_chain = particle_position.with_action_suffix(destructor_quality)
        # A destructor is checked exactly once: only at the action that knows the
        # state of every position it requires. Resolve the state of all required positions
        # first, before we attempt to check its requirements.
        resolved_requirements: list[_ResolvedRequirement] = []
        for inner_req in destructor_contract.requirements.values():
            resolution = self._resolve_destructor_requirement(
                inner_req=inner_req,
                action_chain=action_chain,
                caller_prefix_length=caller_prefix_length,
                destruction_contract=destruction_contract,
                callee_contracts=callee_contracts,
                destruction_contract_position=destruction_contract_position,
                merged_child_state=merged_child_state,
                created_in_this_action=created_in_this_action,
            )
            # If the state of any required position is not yet known, we
            # defer verification to our caller.
            if resolution is None:
                return None
            resolved_requirements.append(resolution)
        # Every required state is known here, so this is where the destructor is
        # actually verified; record the firing edge once, from the true destroyer.
        self._action_edges.append(
            action_call_graph.ActionGraphEdge(
                source=(
                    destruction_contract.destruction_fact.destruction.destroying_action.full_typed_name
                ),
                target=destructor_quality.full_typed_name,
            )
        )
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
            self._diagnostics.append(
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
        verified_requirements = [
            resolved_requirement.as_verified_destruction_contract_requirement()
            for resolved_requirement in resolved_requirements
        ]
        return operation_graph_model.VerifiedDestructionContractDestructor(
            action=action_chain,
            destruction_contract_position=destruction_contract_position,
            requirements=verified_requirements,
            guarantees=_verified_destructor_guarantees(
                action_chain,
                destructor_contract,
                verified_requirements,
            ),
        )

    def _resolve_destructor_requirement(
        self,
        *,
        inner_req: action_contract.PositionRequirement,
        action_chain: ast.ActionReference,
        caller_prefix_length: int,
        destruction_contract: action_contract.DestructionContract,
        callee_contracts: action_contract.DestructionContracts,
        destruction_contract_position: operation_graph_model.DestructionContractPosition,
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
        callee_occupancy = callee_contracts.child_occupancy(
            destruction_contract, relative_key
        )
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
        requirement_callee_destroy_position = None
        # A callee-known occupied requirement uses that position's Destroy. An
        # empty requirement has no Destroy, so it uses the nearest callee-known
        # occupied parent position's Destroy. A caller-only occupied position
        # instead has a caller-contributed Destroy.
        if occupancy.state == position_occupancy.PositionOccupancyState.EMPTY or (
            callee_occupancy is not None
            and callee_occupancy.state
            != position_occupancy.PositionOccupancyState.ERROR
        ):
            requirement_callee_destroy_position = destruction_contract_position.callee_destroy_position_relative_to_destroyed_particle
            occupied_position_or_parent = callee_contracts.occupied_child_state_position_or_nearest_occupied_parent(
                destruction_contract, relative_key
            )
            if occupied_position_or_parent is not None:
                requirement_callee_destroy_position = occupied_position_or_parent
        return _ResolvedRequirement(
            requirement=inner_req,
            position=required_position,
            occupancy=occupancy,
            callee_destroy_position_relative_to_destroyed_particle=(
                requirement_callee_destroy_position
            ),
        )

    def _analyze_statements(
        self,
        action_statements: ast.ActionStatementsBlock,
        scope: scope_tracker.ScopeTracker,
    ):
        validity_iter = iter(self._definition_result.particle_statement_validity)
        for stmt in action_statements.statements:
            match stmt:
                case ast.LocalPositionDefinition():
                    scope.add_definition(stmt)
                    self._dead_constraint_tracker.register_position_constraints(
                        stmt, self._definition_results
                    )
                case ast.CreateParticleStatement():
                    validity = next(validity_iter)
                    self._analyze_create(stmt, validity, scope)
                case ast.MoveParticleStatement():
                    validity = next(validity_iter)
                    self._analyze_move(stmt, validity, scope)
                case ast.DestroyParticleStatement():
                    validity = next(validity_iter)
                    self._analyze_destroy(stmt, validity, scope)
        self._auto_destruct_locals(scope)

    def _auto_destruct_locals(self, scope: scope_tracker.ScopeTracker):
        """Destroy any particles still in positions defined locally in this block.

        Per the spec's "Automatic Destruction" section, all particles still
        occupying Positions defined only within this block are simultaneously
        automatically destroyed.
        """
        targets: list[_DestructionTarget] = []
        for definition in scope.current_scope_definitions():
            position = ast.PositionReference(
                typed_names=(definition.typed_name,),
                location=definition.location,
            )
            # Spec: "If the compiler is uncertain about whether a position still
            # contains a particle, it only destroys the particle if
            # one is present."
            occupancy = self._tracker.get_occupancy_info(position)
            if occupancy.has_error or occupancy.occupant is None:
                continue
            auto_destruction_target = occupancy.occupant.last_position
            targets.append(
                _DestructionTarget(
                    position=position,
                    destruction=destruction_contract_types.SimultaneousDestruction(
                        directly_destroyed_position=position,
                        destroying_action=self._definition.typed_name,
                        is_automatic=True,
                    ),
                    auto_destruction_target=auto_destruction_target,
                )
            )
        self._destroy_particles(
            targets, scope, self._action_definition.action_statements.location
        )

    def _analyze_create(
        self,
        stmt: ast.CreateParticleStatement,
        validity: validation_result.ParticleStatementValidity,
        scope: scope_tracker.ScopeTracker,
    ):
        if not validity.target_ok:
            return
        self._validate_chained_name(stmt.target_position, scope)
        position = stmt.target_position
        if self._tracker.has_error_state(position):
            return

        self._maybe_infer_requirements_on_chain(
            position_occupancy.PositionOccupancyState.EMPTY, position, scope
        )
        qualities = self._get_transitive_required_qualities(position, scope)
        diagnostic = self._operation_validator.validate_create(position)
        if diagnostic is not None:
            self._diagnostics.append(diagnostic)
            return
        self._tracker.create(position, qualities)
        self._run_constructors(stmt, qualities, scope)
        self._check_trigger(stmt, scope)

    def _analyze_destroy(
        self,
        stmt: ast.DestroyParticleStatement,
        validity: validation_result.ParticleStatementValidity,
        scope: scope_tracker.ScopeTracker,
    ):
        if not validity.target_ok:
            return
        self._validate_chained_name(stmt.target_position, scope)
        if self._tracker.has_error_state(stmt.target_position):
            return

        self._maybe_infer_requirements_on_chain(
            position_occupancy.PositionOccupancyState.OCCUPIED,
            stmt.target_position,
            scope,
        )
        diagnostic = self._operation_validator.validate_destroy(stmt.target_position)
        if diagnostic is not None:
            self._diagnostics.append(diagnostic)
            return
        destruction = destruction_contract_types.SimultaneousDestruction(
            directly_destroyed_position=stmt.target_position,
            destroying_action=self._definition.typed_name,
            is_automatic=False,
        )

        self._destroy_particles(
            (
                _DestructionTarget(
                    position=stmt.target_position,
                    destruction=destruction,
                    auto_destruction_target=None,
                ),
            ),
            scope,
            stmt.location,
        )

    def _analyze_move(
        self,
        stmt: ast.MoveParticleStatement,
        validity: validation_result.ParticleStatementValidity,
        scope: scope_tracker.ScopeTracker,
    ):
        if not (validity.source_ok and validity.target_ok):
            return
        if validity.from_is_prefix_of_to:
            self._tracker.mark_error(stmt.source_position)
            self._tracker.mark_error(stmt.target_position)
            return
        self._validate_chained_name(stmt.source_position, scope)
        self._validate_chained_name(stmt.target_position, scope)
        if (
            stmt.source_position.canonical_chained_name_tuple
            == stmt.target_position.canonical_chained_name_tuple
        ):
            # We can't execute self-to-self moves because it would re-trigger
            # actions if the move is for a trigger position.
            return
        self._execute_move(stmt, scope)

    def _execute_move(
        self,
        stmt: ast.MoveParticleStatement,
        scope: scope_tracker.ScopeTracker,
    ):
        """Execute a move and update tracker state."""
        from_pos = stmt.source_position
        to_pos = stmt.target_position
        if self._tracker.has_error_state(from_pos) or self._tracker.has_error_state(
            to_pos
        ):
            self._tracker.mark_error(from_pos)
            self._tracker.mark_error(to_pos)
            return

        self._maybe_infer_requirements_on_chain(
            position_occupancy.PositionOccupancyState.OCCUPIED, from_pos, scope
        )
        self._maybe_infer_requirements_on_chain(
            position_occupancy.PositionOccupancyState.EMPTY, to_pos, scope
        )

        target_required_qualities, _ = self._get_direct_required_qualities(
            to_pos, scope
        )
        move_diagnostics = self._operation_validator.validate_move(
            source=from_pos,
            target=to_pos,
            target_required_qualities=target_required_qualities or (),
        )
        if move_diagnostics:
            self._diagnostics.extend(move_diagnostics)
            return
        self._tracker.move(from_pos, to_pos)
        self._check_trigger(stmt, scope)

    def _validate_chained_name(
        self,
        chain: ast.PositionReference,
        scope: scope_tracker.ScopeTracker,
    ):
        """Validate chained name elements against their parent name's constraints.

        Marks the chain's occupancy state as ERROR in the tracker if validation fails.
        """
        self._mark_referenced_position_constraints_alive(chain)
        if len(chain.typed_names) < 2:
            return
        elements = chain.typed_names
        first = elements[0]
        # An interface position at index 0 is in scope and provides its own
        # constraints; every other parent name in the chain must be a global
        # definition that we have to look up.
        index = 0
        if scope.is_defined(first):
            self._check_chain_element_in_constraints(
                chain,
                elements[1],
                scope.get_definition(first).constraints,
                first.full_typed_name,
            )
            index = 1

        while index < len(elements) - 1:
            # The file_validator rejects any non-first local in a chain unless
            # it follows a global action, and _validate_action_chain_step
            # consumes that local along with the global, so parent is always
            # global here.
            parent = elements[index]
            if not isinstance(parent, ast.GlobalTypedNameReference):
                raise TypeError(
                    f"chain parent at index {index} is not global: {parent}"
                )
            child = elements[index + 1]
            parent_def = self._get_chain_element_definition(parent, chain)
            if parent_def is None:
                return
            match parent_def:
                case ast.PositionDefinition() as position_def:
                    self._check_chain_element_in_constraints(
                        chain,
                        child,
                        position_def.constraints,
                        parent.full_typed_name,
                    )
                    index += 1
                case ast.ActionDefinition() as action_def:
                    consumed = self._validate_action_chain_step(
                        chain,
                        child,
                        elements,
                        index + 1,
                        action_def,
                        parent.full_typed_name,
                    )
                    if consumed == 0:
                        return
                    index += consumed
                case _:
                    raise TypeError(f"Unexpected definition type: {type(parent_def)}")

    def _get_chain_element_definition(
        self,
        parent: ast.GlobalTypedNameReference,
        chain: ast.PositionReference,
    ) -> ast.QualityDefinition | None:
        """Get the QualityDefinition for a chain element, or None on failure (and mark chain error)."""
        parent_result = self._definition_results.get(parent)
        # This means the definition's file did not load or did not parse.
        if parent_result is None:
            self._tracker.mark_error(chain)
            return None
        return parent_result.definition

    def _validate_action_chain_step(
        self,
        chain: ast.PositionReference,
        child: ast.TypedNameReference,
        elements: tuple[ast.TypedNameReference, ...],
        child_index: int,
        action_def: ast.ActionDefinition,
        parent_name: str,
    ) -> int:
        """Validate chain elements against an action definition's local positions.

        Returns the number of elements consumed (0 means stop walking).
        """
        if not isinstance(child, ast.LocalTypedNameReference):
            self._emit_chain_after_action_diagnostic(
                chain,
                child,
                parent_name,
                diagnostics.ChainGlobalNameAfterActionDiagnostic,
            )
            return 0
        if child.full_typed_name not in action_def.interface_positions_by_name:
            self._emit_chain_after_action_diagnostic(
                chain,
                child,
                parent_name,
                diagnostics.ChainElementNotInterfacePositionDiagnostic,
            )
            return 0
        # The caller guarantees child exists, but not that the child's child exists.
        if child_index + 1 >= len(elements):
            return 1
        next_child = elements[child_index + 1]
        self._check_chain_element_in_constraints(
            chain,
            next_child,
            action_def.interface_positions_by_name[child.full_typed_name].constraints,
            child.source_typed_name,
        )
        return 2

    def _check_chain_element_in_constraints(
        self,
        chain: ast.PositionReference,
        element: ast.TypedNameReference,
        constraints: ast.PositionConstraintBlock | None,
        parent_name: str,
    ):
        """Check that a chain element is an explicit constraint of its parent name."""
        element_name = element.full_typed_name
        declared = constraints.as_set if constraints is not None else frozenset[str]()
        if element_name not in declared:
            self._diagnostics.append(
                diagnostics.ChainElementNotInConstraintsDiagnostic(
                    location=element.location,
                    element_name=element_name,
                    parent_name=parent_name,
                )
            )
            self._tracker.mark_error(chain)

    def _emit_chain_after_action_diagnostic(
        self,
        chain: ast.PositionReference,
        element: ast.TypedNameReference,
        parent_name: str,
        diagnostic_class: type[
            diagnostics.ChainGlobalNameAfterActionDiagnostic
            | diagnostics.ChainElementNotInterfacePositionDiagnostic
        ],
    ):
        """Emit a diagnostic for a chain element that cannot follow an action."""
        self._diagnostics.append(
            diagnostic_class(
                location=element.location,
                element_name=element.full_typed_name,
                parent_name=parent_name,
            )
        )
        self._tracker.mark_error(chain)

    def _particle_origin_position(
        self, position: ast.PositionReference
    ) -> ast.PositionReference | None:
        occupancy = self._tracker.get_occupancy_info(position)
        if occupancy.occupant is None:
            return None
        return occupancy.occupant.origin_position

    def _mark_referenced_position_constraints_alive(self, chain: ast.PositionReference):
        if not self._dead_constraint_tracker.has_position_constraint_candidates():
            return
        parent_position_name_count: int | None = None
        for name_index, typed_name in enumerate(chain.typed_names):
            if (
                parent_position_name_count is not None
                and isinstance(typed_name, ast.GlobalTypedNameReference)
                and typed_name.name_type == ast.NameType.POSITION
            ):
                current_position = chain.position_prefix(parent_position_name_count)
                self._dead_constraint_tracker.mark_position_alive(
                    current_position,
                    self._particle_origin_position(current_position),
                    typed_name,
                )
            if typed_name.name_type == ast.NameType.POSITION:
                parent_position_name_count = name_index + 1

    def _mark_callee_contract_constraints_alive(
        self,
        requirements_in_caller: list[action_contract.PositionRequirementInCaller],
        scope: scope_tracker.ScopeTracker,
    ):
        if not self._dead_constraint_tracker.has_constraint_candidates():
            return
        for requirement_in_caller in requirements_in_caller:
            if (
                requirement_in_caller.requirement.required_state
                != position_occupancy.PositionOccupancyState.OCCUPIED
            ):
                continue
            occupancy = self._tracker.get_occupancy_info(
                requirement_in_caller.caller_position
            )
            if occupancy.occupant is None:
                continue
            self._mark_contract_position_constraints_alive(
                requirement_in_caller.caller_position, occupancy.occupant, scope
            )

    def _mark_contract_position_constraints_alive(
        self,
        position: ast.PositionReference,
        particle: particle_info.ParticleInfo,
        scope: scope_tracker.ScopeTracker,
    ):
        if not self._dead_constraint_tracker.has_constraint_candidates():
            return
        constraints, _ = self._get_direct_required_qualities(position, scope)
        if constraints is None:
            return
        self._dead_constraint_tracker.mark_contract_constraints_alive(
            None, particle.origin_position, constraints
        )

    def _check_dead_constraints(self):
        """Emit diagnostics for dead constraints and untriggered actions."""
        for candidate in self._dead_constraint_tracker.dead_position_constraints():
            self._diagnostics.append(
                diagnostics.DeadChildPositionDiagnostic(
                    location=candidate.constraint.location,
                    constraint_name=candidate.constraint.source_typed_name,
                    position_name=candidate.position.source_typed_name,
                )
            )
        for candidate in self._dead_constraint_tracker.dead_action_constraints():
            self._diagnostics.append(
                diagnostics.UntriggeredActionDiagnostic(
                    location=candidate.constraint.location,
                    constraint_name=candidate.constraint.source_typed_name,
                    position_name=candidate.position.source_typed_name,
                )
            )
        for (
            implied_action
        ) in self._dead_constraint_tracker.untriggered_implied_actions():
            self._diagnostics.append(
                diagnostics.UntriggeredImpliedActionDiagnostic(
                    location=implied_action.location,
                    implied_action_name=implied_action.source_typed_name,
                )
            )
        for position in self._tracker.dead_action_interface_arrivals():
            action = typing.cast(
                "ast.GlobalTypedNameReference", position.get_last_action()
            )
            self._diagnostics.append(
                diagnostics.UntriggeredActionInterfaceDiagnostic(
                    location=action.location,
                    action_name=action.source_typed_name,
                    position_name=position.source_chained_name,
                )
            )

    def _get_direct_required_qualities(
        self,
        position: ast.PositionReference,
        scope: scope_tracker.ScopeTracker,
    ) -> tuple[
        tuple[ast.GlobalTypedNameReference, ...] | None,
        tuple[str, ...] | None,
    ]:
        """Resolve the constraint qualities required at a position, in source order.

        Also returns the cache key identifying the cacheable entity (a
        global position or an action interface position), or ``None``
        for local positions defined inside of an Action Statements Block.
        """
        if scope.is_defined_local(position):
            # is_defined_local already verified the chain is a single LocalTypedNameReference.
            local_name = typing.cast(
                "ast.LocalTypedNameReference", position.typed_names[0]
            )
            definition = scope.get_definition(local_name)
            return (
                definition.constraint_typed_names,
                self._local_definition_cache_key(local_name),
            )

        last_element = position.typed_names[-1]

        if isinstance(last_element, ast.LocalTypedNameReference):
            # Local position inside an action — look up the parent action's
            # interface position definition. Chain validation guarantees the
            # parent is a global action reference whose definition exists and
            # contains this interface position.
            parent = typing.cast(
                "ast.GlobalTypedNameReference", position.typed_names[-2]
            )
            action_def = self._definition_results[parent].definition
            action_def = typing.cast("ast.ActionDefinition", action_def)
            return (
                action_def.interface_positions_by_name[
                    last_element.full_typed_name
                ].constraint_typed_names,
                (parent.full_typed_name, last_element.full_typed_name),
            )

        # This can be None if the last element in the chain is a definition we never loaded
        # (file not found or failed to parse).
        definition_result = self._definition_results.get(last_element)
        if definition_result is None:
            return (None, None)
        position_def = typing.cast(
            "ast.PositionDefinition", definition_result.definition
        )
        return (position_def.constraint_typed_names, (last_element.full_typed_name,))

    def _get_transitive_required_qualities(
        self,
        position: ast.PositionReference,
        scope: scope_tracker.ScopeTracker,
    ) -> quality_assignment.QualityAssignments:
        direct, cache_key = self._get_direct_required_qualities(position, scope)
        if direct is None:
            return quality_assignment.EMPTY_QUALITY_ASSIGNMENTS
        if cache_key is None:
            return self._build_quality_assignments(direct)
        return self._validation_state.get_or_build_quality_assignments(
            cache_key, lambda: self._build_quality_assignments(direct)
        )

    def _build_quality_assignments(
        self, direct: tuple[ast.GlobalTypedNameReference, ...]
    ) -> quality_assignment.QualityAssignments:
        """Build assigned qualities in source-order depth-first assignment order."""

        def implications_for(
            typed_name: ast.GlobalTypedNameReference,
        ) -> tuple[ast.GlobalTypedNameReference, ...]:
            defn_result = self._definition_results.get(typed_name)
            if defn_result is None:
                return ()
            return tuple(
                implication.typed_global_name
                for implication in defn_result.definition.quality_implications
            )

        return quality_assignment.QualityAssignments.expand_implications(
            direct, implications_for
        )

    @property
    def _action_definition(self) -> ast.ActionDefinition:
        return typing.cast("ast.ActionDefinition", self._definition)

    @property
    def _interface_positions(self) -> dict[str, ast.LocalPositionDefinition]:
        return self._action_definition.interface_positions_by_name

    def _mark_own_contract_guarantees_alive(
        self,
        own_guarantees: dict[ast.ChainedNameTuple, action_contract.PositionGuarantee],
        scope: scope_tracker.ScopeTracker,
    ):
        """Keep origin position constraints alive through this action's final guarantees."""
        if not self._dead_constraint_tracker.has_constraint_candidates():
            return
        for guarantee in own_guarantees.values():
            final_position = guarantee.caused_by
            origin_position = self._particle_origin_position(final_position)
            if origin_position is None:
                continue
            constraints, _ = self._get_direct_required_qualities(final_position, scope)
            constraints = typing.cast(
                "tuple[ast.GlobalTypedNameReference, ...]", constraints
            )
            self._dead_constraint_tracker.mark_contract_constraints_alive(
                final_position, origin_position, constraints
            )

    @property
    def _trigger_position_name(self) -> str | None:
        if self._action_definition.trigger_position is not None:
            return self._action_definition.trigger_position.typed_name.full_typed_name
        return None

    def analyze(self) -> PostorderValidationResult:
        """Run post-order validation and return diagnostics, edges, and contract."""
        action_def = self._action_definition
        contract = self._analyze_action_definition(action_def)
        operation_graph_builder = self._tracker.operation_graph_builder
        operation_graph_builder.record_guaranteed_positions(
            final_operation.position for final_operation in contract.final_operations
        )
        return PostorderValidationResult(
            diagnostics=self._diagnostics,
            edges=self._action_edges,
            contract=contract,
            operation_graph=operation_graph_builder.finish(),
            destructions=self._destructions,
            triggered_actions=self._triggered_actions,
        )

    def _check_trigger(
        self,
        statement: ast.CreateParticleStatement | ast.MoveParticleStatement,
        scope: scope_tracker.ScopeTracker,
    ):
        """Check trigger, detecting self-triggering as an error."""
        position = statement.target_position
        action_chain = position.get_chain_to_last_action()
        if action_chain is not None:
            self._process_action_position_arrival(statement, action_chain, scope)
            return
        if self._trigger_position_name is None:
            return
        if len(position.typed_names) != 1:
            return
        if position.typed_names[0].full_typed_name != self._trigger_position_name:
            return
        self._diagnostics.append(
            diagnostics.ActionSelfTriggerDiagnostic(
                location=position.location,
                action_name=self._definition.typed_name.source_typed_name,
                position_name=position.source_chained_name,
            )
        )

    def _analyze_action_definition(
        self,
        definition: ast.ActionDefinition,
    ) -> action_contract.ActionContract:
        scope = scope_tracker.ScopeTracker()
        for implication in definition.quality_implications:
            implied_action = implication.typed_global_name
            if implied_action.name_type != ast.NameType.ACTION:
                continue
            self._dead_constraint_tracker.register_implied_action(implied_action)
        for pos in definition.interface_positions:
            # Skip duplicates so the first definition's constraints are preserved,
            # matching file_validator's behavior of not adding conflicting names.
            if not scope.is_defined(pos.typed_name):
                scope.add_definition(pos)
                self._dead_constraint_tracker.register_position_constraints(
                    pos, self._definition_results
                )

        # Set all positions from the Trigger Conditions Block as having
        # the state that the Trigger Conditions Block says they have.
        trigger_ref = self._action_definition.trigger_position_reference
        if trigger_ref is not None:
            qualities = self._get_transitive_required_qualities(trigger_ref, scope)
            self._tracker.operation_graph_builder.record_requirement(
                trigger_ref,
                position_occupancy.PositionOccupancyState.OCCUPIED,
            )
            # DLP 37: We assume trigger points are occupied upon the start
            # of the action, but we can only assume they have the qualities
            # they are declared with.
            self._tracker.create(
                trigger_ref,
                qualities,
                from_caller=trigger_ref,
            )

        scope.enter_child_scope()
        self._analyze_statements(definition.action_statements, scope)
        self._check_unconsumed_action_interfaces()

        contract = self._generate_contract()
        self._mark_own_contract_guarantees_alive(contract.guarantees, scope)
        self._check_dead_constraints()
        return contract

    def _check_unconsumed_action_interfaces(self):
        """Diagnose occupied interface positions of actions triggered by this action."""
        for action, position in self._tracker.unconsumed_action_interfaces():
            self._diagnostics.append(
                diagnostics.UnconsumedActionInterfaceDiagnostic(
                    location=action.location,
                    action_name=action.source_typed_name,
                    position_name=ast.source_form_chained_name(
                        position, self._enclosing_fqun.canonical
                    ),
                )
            )

    def _generate_contract(self) -> action_contract.ActionContract:
        """Generate the action contract from inferred requirements and final tracker state."""
        if self._action_definition.is_destructor:
            guarantees = self._tracker.generate_destructor_guarantees(
                self._action_definition.interface_position_names,
                self._implied_quality_list,
                self._inferred_requirements,
            )
            callees: list[action_contract.CalleeContract] = []
        else:
            guarantees = self._tracker.generate_own_guarantees(
                self._action_definition.interface_position_names,
                self._implied_quality_list,
                self._inferred_requirements,
            )
            callees = self._tracker.nested_guarantees()
        final_operations = self._tracker.final_operations(
            guarantees,
            include_callee_derived=self._action_definition.is_destructor,
        )
        if self._action_definition.is_destructor:
            self._check_destructor_guarantees(guarantees)
        return action_contract.ActionContract(
            requirements=self._inferred_requirements,
            guarantees=guarantees,
            final_operations=final_operations,
            callees=callees,
            destruction_contracts=self._destruction_contracts,
            trigger_position_name=self._trigger_position_name or "",
        )

    def _check_destructor_guarantees(
        self,
        guarantees: dict[ast.ChainedNameTuple, action_contract.PositionGuarantee],
    ):
        """Report forbidden Destructor Guarantees and replace them with Error Guarantees.

        A destructor may not change any contracted position's state (DLP 41), so
        each guarantee it produces is a violation. The contract may not
        advertise such a guarantee, so each is replaced with an ErrorGuarantee
        that leaves the position's post-destructor state undetermined for any
        consumer of the contract. Guarantees from actions triggered by the
        Destructor must also be checked, even when they are applied lazily.
        """
        for position, guarantee in guarantees.items():
            # TODO: caused_by names the position as it was written in the action
            # where the guarantee originated, so a guarantee surfaced from a
            # deeply-nested triggered action gets that callee's short chained name
            # (e.g. "position<out>") instead of its full chained name relative to
            # the destructor (e.g.
            # "action</a>::position<box>::action</b>::position<out>"). The contract holds
            # that full chained name, but only as canonical names, not a source form.
            position_name = guarantee.caused_by.source_form_in_universe(
                self._enclosing_fqun
            )
            match guarantee:
                case action_contract.EmptyGuarantee():
                    self._diagnostics.append(
                        diagnostics.DestructorProducesEmptyGuaranteeDiagnostic(
                            location=guarantee.caused_by.location,
                            position_name=position_name,
                        )
                    )
                case action_contract.OccupiedByNewGuarantee():
                    self._diagnostics.append(
                        diagnostics.DestructorProducesOccupiedGuaranteeDiagnostic(
                            location=guarantee.caused_by.location,
                            position_name=position_name,
                        )
                    )
                case action_contract.OccupiedByExistingGuarantee():
                    self._diagnostics.append(
                        diagnostics.DestructorProducesOccupiedByExistingGuaranteeDiagnostic(
                            location=guarantee.caused_by.location,
                            position_name=position_name,
                            origin_name=guarantee.origin_position.source_form_in_universe(
                                self._enclosing_fqun
                            ),
                        )
                    )
                case action_contract.ErrorGuarantee():
                    continue
                case action_contract.UnchangedGuarantee():
                    continue
                case _:
                    raise TypeError(
                        f"unexpected guarantee type {type(guarantee).__name__}"
                    )
            guarantees[position] = action_contract.ErrorGuarantee(
                caused_by=guarantee.caused_by,
            )

    def _local_definition_cache_key(
        self,
        local_name: ast.LocalTypedNameReference,
    ) -> tuple[str, ...] | None:
        """Cache interface positions so the action's own processing fills the same key external references use."""
        if local_name.full_typed_name in self._interface_positions:
            return (
                self._action_definition.typed_name.full_typed_name,
                local_name.full_typed_name,
            )
        return None
