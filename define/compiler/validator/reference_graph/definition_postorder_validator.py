"""Post-order validation for a single definition during the reference graph DFS walk."""

from __future__ import annotations

import typing
from functools import cached_property

import msgspec

from define.compiler import ast, diagnostics
from define.compiler.validator import codegen_input, scope_tracker
from define.compiler.validator.reference_graph import (
    action_contract,
    chained_name_validator,
    destruction_contract_validator,
    particle_info,
    particle_operation_validator,
    particle_tracker,
    position_occupancy,
    position_quality_resolver,
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


class PostorderValidationResult(msgspec.Struct):
    """Result of validating a single definition during the DFS post-order walk."""

    diagnostics: list[diagnostics.Diagnostic]
    contract: action_contract.ActionContract
    codegen_input: codegen_input.ActionCodegenInput


class _DestructionTarget(msgspec.Struct, frozen=True):
    """A particle whose destruction also destroys its occupied children."""

    position: ast.PositionReference
    destruction: destruction_contract_types.SimultaneousDestruction
    auto_destruction_target: ast.PositionReference | None


class _PendingDestructionContract(msgspec.Struct, frozen=True):
    """A Destruction Contract captured before tracked particle state changes."""

    particle: particle_info.ParticleInfo
    destruction_fact: destruction_contract_types.DestructionFact


class ActionPostorderValidator:
    """Validates an action definition during a DFS post-order walk of the reference graph."""

    _definition: ast.ActionDefinition
    _particle_statement_validity: Sequence[validation_result.ParticleStatementValidity]
    _definition_results: typed_name_dict.TypedNameDict[
        ast.GlobalTypedName[ast.GlobalNameContent[ast.Fqun | None]],
        validation_result.DefinitionValidationResult,
    ]
    _validation_state: reference_graph_validation_state.ReferenceGraphValidationState
    _diagnostics: list[diagnostics.Diagnostic]
    _inferred_requirements: dict[tuple[str, ...], action_contract.PositionRequirement]
    _destruction_contracts: list[action_contract.DestructionContracts]
    _dead_constraint_tracker: dead_constraint_tracker.DeadConstraintTracker

    def __init__(
        self,
        definition: ast.ActionDefinition,
        particle_statement_validity: Sequence[
            validation_result.ParticleStatementValidity
        ],
        definition_results: typed_name_dict.TypedNameDict[
            ast.GlobalTypedName[ast.GlobalNameContent[ast.Fqun | None]],
            validation_result.DefinitionValidationResult,
        ],
        validation_state: reference_graph_validation_state.ReferenceGraphValidationState,
    ):
        """Initialize with the Action Definition, statement validity, and known definitions."""
        self._definition = definition
        self._particle_statement_validity = particle_statement_validity
        self._definition_results = definition_results
        self._validation_state = validation_state
        self._diagnostics = []
        self._inferred_requirements = {}
        self._destruction_contracts = []
        self._steps: list[codegen_input.ActionStep] = []
        self._dead_constraint_tracker = dead_constraint_tracker.DeadConstraintTracker()

    @property
    def _enclosing_fqun(self) -> ast.Fqun:
        return self._definition.typed_name.name_content.fqun

    @cached_property
    def _tracker(self) -> particle_tracker.ParticleTracker:
        return particle_tracker.ParticleTracker()

    @cached_property
    def _operation_validator(
        self,
    ) -> particle_operation_validator.ParticleOperationValidator:
        return particle_operation_validator.ParticleOperationValidator(
            self._tracker, self._enclosing_fqun
        )

    @cached_property
    def _chained_name_validator(self) -> chained_name_validator.ChainedNameValidator:
        return chained_name_validator.ChainedNameValidator(
            self._definition_results, self._tracker
        )

    @cached_property
    def _destruction_contract_validator(
        self,
    ) -> destruction_contract_validator.DestructionContractValidator:
        return destruction_contract_validator.DestructionContractValidator(
            self._definition,
            self._definition_results,
            self._validation_state,
            self._tracker,
        )

    @cached_property
    def _position_quality_resolver(
        self,
    ) -> position_quality_resolver.PositionQualityResolver:
        return position_quality_resolver.PositionQualityResolver(
            self._definition,
            self._definition_results,
            self._validation_state,
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
        # - A September 2026 experiment batched requirement classification before
        #   recording assumptions. On the default action-graph workload, sampled
        #   requirement-processing CPU fell about 32%, and five-run medians
        #   initially suggested a 0.96% compilation improvement. CPU-pinned,
        #   fixed-hash A/B controls instead showed a 0.16% regression, within
        #   timing noise. The local saving did not establish a compilation
        #   speedup sufficient to justify the structural change, so it was rejected.
        # Revisit only if those consumers or the propagation pipeline change
        # substantially.
        requirement_key = contracted_position.canonical_chained_name_tuple
        self._inferred_requirements[requirement_key] = (
            action_contract.PositionRequirement(
                required_state=required_state,
                position=contracted_position,
                inferred_at=inferred_at,
                enclosing_action=self._definition,
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
                qualities = (
                    self._position_quality_resolver.get_transitive_required_qualities(
                        contracted_position, scope
                    )
                )
                self._tracker.assume_occupied(
                    local_position,
                    qualities,
                    position_in_caller=contracted_position,
                )
            case position_occupancy.PositionOccupancyState.EMPTY:
                self._tracker.assume_empty(local_position)

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
            parent_particle = self._tracker.get_occupant(position)
            self._dead_constraint_tracker.mark_action_alive(
                quality, position, parent_particle.origin_position
            )
            contract = self._validation_state.get_contract_or_none(quality)
            # A rejected circular reference can leave this constructor's contract
            # unpublished while the referencing definition is validated.
            if contract is None:
                continue
            # The constructor is a quality of the particle in `position`, so its
            # interface positions hang off position::action</construct> while its
            # implied qualities hang off the position itself.
            action_chain = position.with_action_suffix(quality)
            self._fire_triggered_action(
                contract,
                action_chain,
                position,
                scope,
                parent_particle=parent_particle,
                action_assignment=action_contract.ActionAssignment(
                    quality=quality,
                    assigned_to_position_name=position.typed_names[-1],
                ),
            )

    def _destroy_particles(
        self,
        targets: Sequence[_DestructionTarget],
        scope: scope_tracker.ScopeTracker,
    ):
        """Destroy the target particles and their occupied transitive children."""
        step = codegen_input.Destruction()
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
                step.positions,
            )
            if pending_contracts:
                snapshot_positions.append(target.position)
                pending_contracts_by_target.append(pending_contracts)

        child_states = self._tracker.snapshot_child_states(snapshot_positions)

        for destructor, auto_destruction_target in destructors:
            self._run_destructor(
                destructor,
                scope,
                step.destructors,
                auto_destruction_target=auto_destruction_target,
            )

        self._tracker.destroy_simultaneously(particle_destructions)
        for shared_state, pending_contracts in zip(
            child_states, pending_contracts_by_target, strict=True
        ):
            contracts = action_contract.DestructionContracts(child_state=shared_state)
            for pending_contract in pending_contracts:
                propagated = self._record_destruction_contract(
                    pending_contract.particle,
                    contracts,
                    pending_contract.destruction_fact,
                )
                step.contract_destructions.append(propagated)
            self._destruction_contracts.append(contracts)
        self._steps.append(step)

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
    ) -> destruction_contract_types.PropagatedDestruction:
        """Record the Destruction Contract for one caller-passed particle."""
        propagated = destruction_contract_types.PropagatedDestruction(
            destruction_fact=destruction_fact,
            contracted_position=particle.origin_position,
        )
        contracts.append(
            action_contract.DestructionContract(
                propagated_destruction=propagated,
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
        return propagated

    def _run_destructor(
        self,
        destructor: action_contract.Destructor,
        scope: scope_tracker.ScopeTracker,
        known_destructors: list[ast.ActionReference],
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
        known_destructors.append(action_chain)
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
        execution = codegen_input.ActionExecution(action=action_chain)
        occupied_interface_child_position_violations = self._tracker.trigger_action(
            execution,
            contract,
            parent_particle=parent_particle,
        )
        self._record_occupied_interface_child_position_violations(
            destructor_name,
            occupied_interface_child_position_violations,
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

        self._dead_constraint_tracker.mark_action_alive(
            action,
            parent_position,
            parent_particle.origin_position if parent_particle is not None else None,
        )
        self._mark_contract_position_constraints_alive(position, particle, scope)

        self._fire_triggered_action(
            contract,
            action_chain,
            particle.last_position,
            scope,
            parent_particle=parent_particle,
        )

    def _fire_triggered_action(
        self,
        contract: action_contract.ActionContract,
        action_chain: ast.ActionReference,
        acting_on_position: ast.PositionReference,
        scope: scope_tracker.ScopeTracker,
        *,
        parent_particle: particle_info.ParticleInfo | None,
        action_assignment: action_contract.ActionAssignment | None = None,
    ):
        execution = codegen_input.ActionExecution(action=action_chain)
        self._steps.append(execution)
        action = action_chain.get_last_action()
        # Requirement propagation and requirement checking each need every
        # requirement's position from the caller's perspective
        # (req.position.in_caller(action_chain)). Deriving it is a fresh
        # allocation, so compute it once here and hand the same objects to both
        # rather than rebuilding it twice per requirement per trigger.
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
        destruction_result = self._destruction_contract_validator.validate(
            contract.destruction_contracts,
            action_chain,
        )
        self._diagnostics.extend(destruction_result.diagnostics)
        self._destruction_contracts.extend(destruction_result.propagated_contracts)
        execution.destruction_connections.extend(destruction_result.connections)
        occupied_interface_child_position_violations = self._tracker.trigger_action(
            execution,
            contract,
            parent_particle=parent_particle,
        )
        self._record_occupied_interface_child_position_violations(
            action,
            occupied_interface_child_position_violations,
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

    def _analyze_statements(
        self,
        action_statements: ast.ActionStatementsBlock,
        scope: scope_tracker.ScopeTracker,
    ):
        validity_iter = iter(self._particle_statement_validity)
        for stmt in action_statements.statements:
            match stmt:
                case ast.LocalPositionDefinition():
                    self._steps.append(stmt)
                    scope.add_definition(stmt)
                    self._dead_constraint_tracker.register_position_constraints(
                        stmt, self._definition_results
                    )
                case ast.CreateParticleStatement():
                    self._steps.append(stmt)
                    validity = next(validity_iter)
                    self._analyze_create(stmt, validity, scope)
                case ast.MoveParticleStatement():
                    self._steps.append(stmt)
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
        self._destroy_particles(targets, scope)

    def _analyze_create(
        self,
        stmt: ast.CreateParticleStatement,
        validity: validation_result.ParticleStatementValidity,
        scope: scope_tracker.ScopeTracker,
    ):
        if not validity.target_ok:
            return
        self._mark_referenced_position_constraints_alive(stmt.target_position)
        self._diagnostics.extend(
            self._chained_name_validator.validate(stmt.target_position, scope)
        )
        position = stmt.target_position
        if self._tracker.has_error_state(position):
            return

        self._maybe_infer_requirements_on_chain(
            position_occupancy.PositionOccupancyState.EMPTY, position, scope
        )
        qualities = self._position_quality_resolver.get_transitive_required_qualities(
            position, scope
        )
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
        self._mark_referenced_position_constraints_alive(stmt.target_position)
        self._diagnostics.extend(
            self._chained_name_validator.validate(stmt.target_position, scope)
        )
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
        self._mark_referenced_position_constraints_alive(stmt.source_position)
        self._diagnostics.extend(
            self._chained_name_validator.validate(stmt.source_position, scope)
        )
        self._mark_referenced_position_constraints_alive(stmt.target_position)
        self._diagnostics.extend(
            self._chained_name_validator.validate(stmt.target_position, scope)
        )
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

        target_required_qualities = (
            self._position_quality_resolver.get_direct_required_qualities(to_pos, scope)
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
                and self._dead_constraint_tracker.has_position_constraint_candidate(
                    typed_name
                )
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
        constraints = self._position_quality_resolver.get_direct_required_qualities(
            position, scope
        )
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

    @property
    def _interface_positions(self) -> dict[str, ast.LocalPositionDefinition]:
        return self._definition.interface_positions_by_name

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
            constraints = self._position_quality_resolver.get_direct_required_qualities(
                final_position, scope
            )
            constraints = typing.cast(
                "tuple[ast.GlobalTypedNameReference, ...]", constraints
            )
            self._dead_constraint_tracker.mark_contract_constraints_alive(
                final_position, origin_position, constraints
            )

    @property
    def _trigger_position_name(self) -> str | None:
        if self._definition.trigger_position is not None:
            return self._definition.trigger_position.typed_name.full_typed_name
        return None

    def analyze(self) -> PostorderValidationResult:
        """Run post-order validation and return diagnostics, contract, and codegen input."""
        contract = self._analyze_action_definition()
        propagated_destructions: list[
            destruction_contract_types.PropagatedDestruction
        ] = []
        for contracts in contract.destruction_contracts:
            for destruction_contract in contracts.particles:
                propagated_destructions.append(
                    destruction_contract.propagated_destruction
                )
        return PostorderValidationResult(
            diagnostics=self._diagnostics,
            contract=contract,
            codegen_input=codegen_input.ActionCodegenInput(
                definition=self._definition,
                steps=self._steps,
                propagated_destructions=propagated_destructions,
            ),
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

    def _analyze_action_definition(self) -> action_contract.ActionContract:
        scope = scope_tracker.ScopeTracker()
        for implication in self._definition.quality_implications:
            implied_action = implication.typed_global_name
            if implied_action.name_type != ast.NameType.ACTION:
                continue
            self._dead_constraint_tracker.register_implied_action(implied_action)
        for pos in self._definition.interface_positions:
            # Skip duplicates so the first definition's constraints are preserved,
            # matching file_validator's behavior of not adding conflicting names.
            if not scope.is_defined(pos.typed_name):
                scope.add_definition(pos)
                self._dead_constraint_tracker.register_position_constraints(
                    pos, self._definition_results
                )

        # Set all positions from the Trigger Conditions Block as having
        # the state that the Trigger Conditions Block says they have.
        trigger_ref = self._definition.trigger_position_reference
        if trigger_ref is not None:
            qualities = (
                self._position_quality_resolver.get_transitive_required_qualities(
                    trigger_ref, scope
                )
            )
            # DLP 37: We assume trigger points are occupied upon the start
            # of the action, but we can only assume they have the qualities
            # they are declared with.
            self._tracker.assume_occupied(
                trigger_ref,
                qualities,
                position_in_caller=trigger_ref,
            )

        scope.enter_child_scope()
        self._analyze_statements(self._definition.action_statements, scope)
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
        if self._definition.is_destructor:
            guarantees = self._tracker.generate_destructor_guarantees(
                self._definition.interface_position_names,
                self._implied_quality_list,
                self._inferred_requirements,
            )
            callees: list[action_contract.CalleeContract] = []
        else:
            guarantees = self._tracker.generate_own_guarantees(
                self._definition.interface_position_names,
                self._implied_quality_list,
                self._inferred_requirements,
            )
            callees = self._tracker.nested_guarantees()
        if self._definition.is_destructor:
            self._check_destructor_guarantees(guarantees)
        return action_contract.ActionContract(
            requirements=self._inferred_requirements,
            guarantees=guarantees,
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
