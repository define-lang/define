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
    dead_constraint_tracker,
    operation_graph_model,
    particle_operation,
    particle_tracker,
    quality_assignment,
    reference_graph_validation_state,
    requirement_violation,
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


@dataclass(frozen=True, slots=True)
class _ResolvedRequirement:
    """A destructor requirement whose required position's destruction-time occupancy is known here."""

    requirement: action_contract.PositionRequirement
    position: ast.PositionReference
    occupancy: action_contract.ChildOccupancy
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
    guarantees: Sequence[action_contract.GuaranteePair],
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
    for guaranteed_position, guarantee in guarantees:
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
                    operation_positions=guarantee.operation_positions,
                ),
                requirement=related_requirement,
            )
        )
    return verified_guarantees


@dataclass(frozen=True, slots=True)
class _PendingDestructionContract:
    """Contract data retained until the explicit Destroy operation is recorded."""

    particle: particle_tracker.ParticleInfo
    child_state: dict[tuple[str, ...], action_contract.ChildOccupancy]


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
    _destruction_contracts: list[action_contract.DestructionContract]
    _dead_tracker: dead_constraint_tracker.DeadConstraintTracker

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
        self._dead_tracker = dead_constraint_tracker.DeadConstraintTracker()

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
    def _executor(self) -> particle_operation.ParticleOperationExecutor:
        return particle_operation.ParticleOperationExecutor(
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
        required_state: action_contract.PositionOccupancyState,
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
            "typing.Literal[action_contract.PositionOccupancyState.OCCUPIED, action_contract.PositionOccupancyState.EMPTY]",
            required_state,
        )
        match requirement_state:
            case action_contract.PositionOccupancyState.OCCUPIED:
                # We can't know exactly what qualities the particle has, but we
                # can know the minimal set that it _must_ have according to the constraints
                # the contracted position has.
                qualities = self._get_transitive_required_qualities(
                    contracted_position, scope
                )
                self._executor.execute_assume_occupied(
                    particle_operation.AssumeOccupied(
                        target=local_position,
                        qualities=qualities,
                        contracted_position_chain=contracted_position,
                    )
                )
            case action_contract.PositionOccupancyState.EMPTY:
                self._executor.execute_assume_empty(
                    particle_operation.AssumeEmpty(target=local_position)
                )

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
        required_state: action_contract.PositionOccupancyState,
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
        position: ast.PositionReference,
        qualities: quality_assignment.QualityAssignments,
        scope: scope_tracker.ScopeTracker,
    ):
        """Trigger every constructor on the particle just created in position (DLP 32)."""
        for quality in qualities.assignments:
            if quality.name_type != ast.NameType.ACTION:
                continue
            definition_result = self._definition_results.get(quality)
            # The constructor's file may have failed to load or parse, which is
            # reported elsewhere; skipping it here keeps the cascade crash-free.
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
                action_assignment=action_contract.ActionAssignment(
                    quality=quality,
                    assigned_to_position_name=position.typed_names[-1],
                ),
            )

    def _execute_destruction_cascade(
        self,
        position: ast.PositionReference,
        particle: particle_tracker.ParticleInfo,
        destruction_fact: operation_graph_model.DestructionFact,
        scope: scope_tracker.ScopeTracker,
        *,
        is_auto_destruction: bool = False,
        auto_destruction_target: ast.PositionReference | None = None,
        destroy_particle: bool = True,
        has_active_destruction_fact: bool = False,
    ) -> _PendingDestructionContract | None:
        """Execute one occupied particle's destruction cascade."""
        child_state = None
        if particle.from_caller:
            child_state = self._tracker.snapshot_child_state(position)
            has_active_destruction_fact = True
        # A particle keeps its own qualities across moves, so it is the source
        # of the qualities to check for destructors (not the position).
        for quality in reversed(particle.qualities.assignments):
            if quality.name_type == ast.NameType.POSITION:
                child = position.with_position_suffix(quality)
                self._execute_cascade_child(
                    child,
                    destruction_fact,
                    scope,
                    is_auto_destruction=is_auto_destruction,
                    auto_destruction_target=auto_destruction_target,
                    has_active_destruction_fact=has_active_destruction_fact,
                )
            else:
                definition_result = self._definition_results.get(quality)
                if definition_result is None:
                    continue
                definition = typing.cast(
                    "ast.ActionDefinition", definition_result.definition
                )
                if definition.is_destructor:
                    self._run_destructor(
                        action_contract.CascadeDestructor(
                            destructor=quality,
                            position=position,
                            origin_position=particle.origin_position,
                        ),
                        scope,
                        auto_destruction_target=auto_destruction_target,
                    )
                for interface_position in reversed(definition.interface_positions):
                    child = position.with_position_suffix(
                        quality, interface_position.typed_name
                    )
                    self._execute_cascade_child(
                        child,
                        destruction_fact,
                        scope,
                        is_auto_destruction=is_auto_destruction,
                        auto_destruction_target=auto_destruction_target,
                        has_active_destruction_fact=has_active_destruction_fact,
                    )
        if destroy_particle:
            if has_active_destruction_fact:
                self._tracker.destroy_for_destruction_fact(
                    position,
                    destruction_fact,
                )
            else:
                self._tracker.destroy(position)
            if child_state is not None:
                self._record_destruction_contract(
                    particle,
                    child_state,
                    destruction_fact,
                    position,
                    is_auto_destruction=is_auto_destruction,
                )
            return None
        if child_state is None:
            return None
        return _PendingDestructionContract(particle, child_state)

    def _execute_cascade_child(
        self,
        position: ast.PositionReference,
        destruction_fact: operation_graph_model.DestructionFact,
        scope: scope_tracker.ScopeTracker,
        *,
        is_auto_destruction: bool,
        auto_destruction_target: ast.PositionReference | None,
        has_active_destruction_fact: bool,
    ):
        """Execute destruction for one position reached during a cascade."""
        occupancy = self._tracker.get_occupancy_info(position)
        if occupancy.has_error:
            return
        if occupancy.occupant is None:
            # The walk already has the nearest particle, so an exact-position
            # check avoids searching the particle trie for an occupied ancestor.
            return
        _ = self._execute_destruction_cascade(
            position,
            occupancy.occupant,
            destruction_fact,
            scope,
            is_auto_destruction=is_auto_destruction,
            auto_destruction_target=auto_destruction_target,
            has_active_destruction_fact=has_active_destruction_fact,
        )

    def _record_destruction_contract(
        self,
        particle: particle_tracker.ParticleInfo,
        child_state: dict[tuple[str, ...], action_contract.ChildOccupancy],
        destruction_fact: operation_graph_model.DestructionFact,
        destroyed_particle_position: ast.PositionReference,
        *,
        is_auto_destruction: bool,
    ):
        """Record the Destruction Contract for one caller-passed particle."""
        self._destruction_contracts.append(
            action_contract.DestructionContract(
                destroyed_position_contracted=particle.origin_position,
                destruction_fact=destruction_fact,
                destroyed_position_in_destroying_action=destroyed_particle_position,
                child_state=child_state,
                # We know these destructors exist at destruction time, so they are
                # handled through the normal requirements mechanism (fired and
                # propagated as this action's own requirements), not through the
                # Destruction Contract's requirement-verification mechanism.
                verified_destructors=self._destructor_quality_assignments(
                    particle.qualities
                ),
                is_auto_destruction=is_auto_destruction,
            )
        )

    def _run_destructor(
        self,
        destructor: action_contract.CascadeDestructor,
        scope: scope_tracker.ScopeTracker,
        auto_destruction_target: ast.PositionReference | None = None,
    ):
        """Trigger one destructor at its point in a destruction cascade."""
        # A destructor's requirements are checked as though it triggered
        # synchronously at the moment of destruction (DLP 41). The destructor is a
        # quality of the particle in `position`, so its interface positions
        # hang off position::action</destructor> while its implied qualities hang off
        # position itself; in_caller maps both correctly from this chain.
        quality = destructor.destructor
        contract = self._validation_state.get_contract_or_none(quality)
        if contract is None:
            return
        action_chain = destructor.position.with_action_suffix(quality)
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
        _ = self._tracker.trigger_action(
            action_chain,
            contract.guarantees,
            destructor.position,
            requirements_in_caller,
            is_destructor=True,
        )
        self._action_edges.append(
            action_call_graph.ActionGraphEdge(
                source=self._definition.typed_name.source_typed_name,
                target=quality.full_typed_name,
            )
        )

    def _check_interface_fill_trigger(
        self,
        position: ast.PositionReference,
        scope: scope_tracker.ScopeTracker,
    ):
        """Check if filling this interface position triggers the named action.

        Only triggers when the chain ends with action<...>::position<trigger>,
        i.e., we're directly filling an action's interface position.
        """
        interface_position = position.get_last_action_children()
        interface_position = typing.cast("ast.PositionReference", interface_position)
        # Only trigger when filling a single interface position directly,
        # not children of interface positions.
        if len(interface_position.typed_names) != 1:
            return
        # Never None, because interface_position is not None.
        action_ref = typing.cast(
            "ast.GlobalTypedNameReference", position.get_last_action()
        )
        # The action's file may have failed to load or parse.
        contract = self._validation_state.get_contract_or_none(action_ref)
        if contract is None:
            return
        trigger_element = typing.cast(
            "ast.LocalTypedNameReference", interface_position.typed_names[0]
        )
        if trigger_element.full_typed_name != contract.trigger_position_name:
            return

        trigger_particle = self._tracker.get_occupant(position)
        self._mark_contract_position_constraints_alive(
            position, trigger_particle, scope
        )

        action_chain = position.get_chain_to_last_action()
        if action_chain is None:
            raise ValueError(f"no action in chain: {position.source_chained_name}")

        self._fire_triggered_action(
            contract,
            action_chain,
            trigger_particle.last_position,
            scope,
        )

    def _fire_triggered_action(
        self,
        contract: action_contract.ActionContract,
        action_chain: ast.ActionReference,
        acting_on_position: ast.PositionReference,
        scope: scope_tracker.ScopeTracker,
        action_assignment: action_contract.ActionAssignment | None = None,
    ):
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
        current_position = action_chain.parent_position()
        origin_position = (
            self._particle_origin_position(current_position)
            if current_position is not None
            else None
        )
        action = action_chain.get_last_action()
        self._dead_tracker.mark_action_alive(action, current_position, origin_position)
        _ = self._tracker.trigger_action(
            action_chain,
            contract.guarantees,
            acting_on_position,
            requirements_in_caller,
            is_destructor=False,
            destruction_contract_contributions=destruction_contract_contributions,
        )
        self._action_edges.append(
            action_call_graph.ActionGraphEdge(
                source=self._definition.typed_name.source_typed_name,
                target=action.full_typed_name,
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
    ) -> tuple[bool, particle_tracker.ParticleInfo | None]:
        occupancy = self._tracker.get_occupancy_info(full_caller_chain)
        if occupancy.has_error:
            return False, None
        occupant = occupancy.occupant
        empty_violation = (
            req.required_state == action_contract.PositionOccupancyState.EMPTY
            and occupant is not None
        )
        occupied_violation = (
            req.required_state == action_contract.PositionOccupancyState.OCCUPIED
            and occupant is None
        )
        return (empty_violation or occupied_violation, occupant)

    def _check_destructor_requirements(
        self,
        destructor: action_contract.CascadeDestructor,
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
        """Return destructor assignments in firing order."""
        # TODO: This feels inefficient to do every time, but let's wait for actual
        # profiling data to tell us if that's important.
        result: list[ast.GlobalTypedNameReference] = []
        for quality in reversed(qualities.assignments):
            if quality.name_type != ast.NameType.ACTION:
                continue
            definition_result = self._definition_results[quality]
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
        """Check the Destruction Contracts surfaced by a triggered action.

        Args:
            contract: The triggered action's contract, whose
                ``destruction_contracts`` are processed.
            action_chain: The names up to and including the triggered action.
                Each contract's contracted positions are remapped into this caller
                via ``in_caller(action_chain)``.
        """
        if not contract.destruction_contracts:
            return ()
        # The hop recording that this definition triggered the action, used
        # if its destruction contract has to be re-recorded and passed on to
        # the caller action. Constructed once here for memory efficiency so it
        # can be shared across multiple destruction contracts as needed.
        trigger_step = action_contract.PropagationStep(
            location=action_chain.location,
            kind=action_contract.PropagationKind.ACTION_TRIGGER,
            enclosing_quality_name=self._definition.typed_name.source_typed_name,
            triggered_quality_name=action_chain.typed_names[-1].full_typed_name,
        )
        positions_by_destruction_fact: dict[
            operation_graph_model.DestructionFact, set[tuple[str, ...]]
        ] = {}
        for destruction_contract in contract.destruction_contracts:
            position = destruction_contract.destroyed_position_contracted.in_caller(
                action_chain
            )
            destruction_fact = destruction_contract.destruction_fact
            contract_positions = positions_by_destruction_fact.get(destruction_fact)
            if contract_positions is None:
                contract_positions = set[tuple[str, ...]]()
                positions_by_destruction_fact[destruction_fact] = contract_positions
            contract_positions.add(position.canonical_chained_name_tuple)
        contributions: list[operation_graph_model.DestructionContractContribution] = []
        for destruction_contract in contract.destruction_contracts:
            contribution = self._check_one_destruction_contract(
                destruction_contract,
                action_chain,
                trigger_step,
                positions_by_destruction_fact[destruction_contract.destruction_fact],
            )
            if contribution is not None:
                contributions.append(contribution)
        return contributions

    def _check_one_destruction_contract(
        self,
        destruction_contract: action_contract.DestructionContract,
        action_chain: ast.ActionReference,
        trigger_step: action_contract.PropagationStep,
        contract_positions: set[tuple[str, ...]],
    ) -> operation_graph_model.DestructionContractContribution | None:
        caller_particle_position = (
            destruction_contract.destroyed_position_contracted.in_caller(action_chain)
        )
        # The action's requirement check already handles missing or
        # error-state particles, so there is nothing more to verify here.
        occupancy = self._tracker.get_occupancy_info(caller_particle_position)
        if occupancy.has_error or occupancy.occupant is None:
            return None
        caller_particle = occupancy.occupant
        destroying_definition_result = self._definition_results[
            destruction_contract.destruction_fact.destroying_action
        ]
        destroying_definition = typing.cast(
            "ast.ActionDefinition", destroying_definition_result.definition
        )
        # Only the action that created the particle may treat an untouched child as
        # empty; otherwise an untouched child's state is error, because a higher caller
        # could have filled it before passing it.
        created_in_this_action = not caller_particle.from_caller
        if created_in_this_action:
            # This action created the particle, so the child_state recorded in the
            # contract contains everything the action itself doesn't already know
            # (this is an optimization so we don't have to snapshot the child state
            # again during the action that created the particle).
            merged_child_state = destruction_contract.child_state
        else:
            # If this action is receiving a contract from an action it called,
            # then the callee's child state overrides the caller's child state.
            merged_child_state = self._tracker.snapshot_child_state(
                caller_particle_position
            )
            merged_child_state.update(destruction_contract.child_state)
        newly_verified: list[ast.GlobalTypedNameReference] = []
        destructor_contributions: list[
            operation_graph_model.VerifiedDestructionContractDestructor
        ] = []
        newly_occupied_children: list[
            operation_graph_model.ContributedDestructionPosition
        ] = []
        final_contributed_positions = self._verify_destruction_cascade(
            caller_particle_position,
            destruction_contract=destruction_contract,
            destroying_definition=destroying_definition,
            caller_prefix_length=len(
                caller_particle_position.canonical_chained_name_tuple
            ),
            trigger_step=trigger_step,
            merged_child_state=merged_child_state,
            created_in_this_action=created_in_this_action,
            newly_verified=newly_verified,
            destructor_contributions=destructor_contributions,
            newly_occupied_children=newly_occupied_children,
            callee_destroy_position=(),
            contract_positions=contract_positions,
            contracted_position=caller_particle_position.canonical_chained_name_tuple,
        )
        if not created_in_this_action:
            self._re_record_destruction_contract(
                destruction_contract,
                caller_particle,
                merged_child_state,
                newly_verified,
                trigger_step,
            )
        # Destruction Contract propagation ends at the action that created the
        # particle. If that action contributes no child Destroys or Destructors,
        # there is no additional work to record in its Operation Graph.
        if (
            created_in_this_action
            and not newly_occupied_children
            and not destructor_contributions
        ):
            return None
        return operation_graph_model.DestructionContractContribution(
            destruction_fact=destruction_contract.destruction_fact,
            destroyed_particle_position=caller_particle_position,
            destroyed_position_in_destroying_action=(
                destruction_contract.destroyed_position_in_destroying_action
            ),
            children=newly_occupied_children,
            final_contributed_positions=final_contributed_positions,
            is_propagated_to_caller=not created_in_this_action,
            destructors=destructor_contributions,
        )

    def _re_record_destruction_contract(
        self,
        destruction_contract: action_contract.DestructionContract,
        caller_particle: particle_tracker.ParticleInfo,
        merged_child_state: dict[tuple[str, ...], action_contract.ChildOccupancy],
        newly_verified: list[ast.GlobalTypedNameReference],
        trigger_step: action_contract.PropagationStep,
    ):
        # Carry the merged destruction-time picture and the destructors checked
        # so far upward; everything else describes the original destroyer and is
        # fixed. This definition's trigger of the callee leads the trigger chain,
        # since it runs before every hop already recorded below it.
        self._destruction_contracts.append(
            action_contract.DestructionContract(
                destroyed_position_contracted=caller_particle.origin_position,
                destruction_fact=destruction_contract.destruction_fact,
                destroyed_position_in_destroying_action=(
                    destruction_contract.destroyed_position_in_destroying_action
                ),
                child_state=merged_child_state,
                verified_destructors=quality_assignment.QualityAssignments(
                    (
                        *destruction_contract.verified_destructors.assignments,
                        *newly_verified,
                    )
                ),
                is_auto_destruction=destruction_contract.is_auto_destruction,
                trigger_chain=(trigger_step, *destruction_contract.trigger_chain),
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
        merged_child_state: dict[tuple[str, ...], action_contract.ChildOccupancy],
        created_in_this_action: bool,
        newly_verified: list[ast.GlobalTypedNameReference],
        destructor_contributions: list[
            operation_graph_model.VerifiedDestructionContractDestructor
        ],
        newly_occupied_children: list[
            operation_graph_model.ContributedDestructionPosition
        ],
        callee_destroy_position: tuple[str, ...],
        contract_positions: set[tuple[str, ...]],
        contracted_position: tuple[str, ...],
    ) -> tuple[operation_graph_model.ContributedDestructionPosition, ...]:
        position_key = position.canonical_chained_name_tuple
        # Another Destruction Contract for this Destruction Fact starts at this
        # position. It validates this position and its child names, so continuing
        # this traversal would record their caller-contributed Destroys twice.
        if position_key != contracted_position and position_key in contract_positions:
            return ()
        occupancy_info = self._tracker.get_occupancy_info(position)
        if occupancy_info.has_error or occupancy_info.occupant is None:
            return ()
        relative_key = position.canonical_chained_name_tuple[caller_prefix_length:]
        occupancy = merged_child_state.get(relative_key)
        # A position the destruction-time picture records as empty was emptied
        # before the destruction, so nothing there was destroyed and thus there
        # is no more work to do.
        if (
            occupancy is not None
            and occupancy.state == action_contract.PositionOccupancyState.EMPTY
        ):
            return ()
        # A child absent from the contract was unknown to the callee but is
        # occupied from this caller's perspective, so this caller contributes
        # its Destroy. The contracted position itself is already destroyed by
        # the callee and therefore is not a contributed child Destroy.
        callee_occupancy = destruction_contract.child_state.get(relative_key)
        is_newly_occupied_child = bool(relative_key and callee_occupancy is None)
        callee_destroy_position_for_children = callee_destroy_position
        # When the callee recorded a Destroy for this position, any children
        # discovered by the caller must be destroyed before the callee-destroyed
        # position.
        if (
            callee_occupancy is not None
            and callee_occupancy.state
            == action_contract.PositionOccupancyState.OCCUPIED
        ):
            callee_destroy_position_for_children = relative_key
        particle = occupancy_info.occupant
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
                        merged_child_state=merged_child_state,
                        created_in_this_action=created_in_this_action,
                        newly_verified=newly_verified,
                        destructor_contributions=destructor_contributions,
                        newly_occupied_children=newly_occupied_children,
                        callee_destroy_position=callee_destroy_position_for_children,
                        contract_positions=contract_positions,
                        contracted_position=contracted_position,
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
                if definition.is_destructor and not (
                    destruction_contract.verified_destructors.has_quality(quality)
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
                        destroying_definition=destroying_definition,
                        caller_prefix_length=caller_prefix_length,
                        trigger_step=trigger_step,
                        merged_child_state=merged_child_state,
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
                            merged_child_state=merged_child_state,
                            created_in_this_action=created_in_this_action,
                            newly_verified=newly_verified,
                            destructor_contributions=destructor_contributions,
                            newly_occupied_children=newly_occupied_children,
                            callee_destroy_position=callee_destroy_position_for_children,
                            contract_positions=contract_positions,
                            contracted_position=contracted_position,
                        )
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
        particle: particle_tracker.ParticleInfo,
        destruction_contract: action_contract.DestructionContract,
        destroying_definition: ast.ActionDefinition,
        caller_prefix_length: int,
        trigger_step: action_contract.PropagationStep,
        merged_child_state: dict[tuple[str, ...], action_contract.ChildOccupancy],
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
                    destruction_contract.destruction_fact.destroying_action.full_typed_name
                ),
                target=destructor_quality.full_typed_name,
            )
        )
        for resolved_requirement in resolved_requirements:
            occupancy = resolved_requirement.occupancy
            required_state = resolved_requirement.requirement.required_state
            empty_violation = (
                required_state == action_contract.PositionOccupancyState.EMPTY
                and occupancy.state == action_contract.PositionOccupancyState.OCCUPIED
            )
            occupied_violation = (
                required_state == action_contract.PositionOccupancyState.OCCUPIED
                and occupancy.state == action_contract.PositionOccupancyState.EMPTY
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
                destructor_contract.guarantees.own,
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
        destruction_contract_position: operation_graph_model.DestructionContractPosition,
        merged_child_state: dict[tuple[str, ...], action_contract.ChildOccupancy],
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
        callee_occupancy = destruction_contract.child_state.get(relative_key)
        occupancy = merged_child_state.get(relative_key)
        if occupancy is None:
            # A passed-in particle's untouched position is decided higher up: this
            # action cannot resolve it, so the destructor travels up unchecked.
            if not created_in_this_action:
                return None
            # The owner created the particle, and we have optimized this case to
            # not copy the whole subtree to update a new child_state and instead
            # to just read the state out of the current tracker.
            if self._tracker.has_error_state(required_position):
                occupancy = action_contract.ERROR_OCCUPANCY
            elif self._tracker.is_occupied(required_position):
                occupancy = action_contract.ChildOccupancy(
                    action_contract.PositionOccupancyState.OCCUPIED,
                    filled_at=self._tracker.get_occupant(
                        required_position
                    ).last_position.location,
                )
            else:
                occupancy = action_contract.EMPTY_OCCUPANCY
        requirement_callee_destroy_position = None
        # A callee-known occupied requirement uses that position's Destroy. An
        # empty requirement has no Destroy, so it uses the nearest callee-known
        # occupied parent position's Destroy. A caller-only occupied position
        # instead has a caller-contributed Destroy.
        if occupancy.state == action_contract.PositionOccupancyState.EMPTY or (
            callee_occupancy is not None
            and callee_occupancy.state != action_contract.PositionOccupancyState.ERROR
        ):
            requirement_callee_destroy_position = destruction_contract_position.callee_destroy_position_relative_to_destroyed_particle
            occupied_position_or_parent = destruction_contract.occupied_child_state_position_or_nearest_occupied_parent(
                relative_key
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
                    self._dead_tracker.register_position_constraints(
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

        Per the spec's "Automatic Destruction" section: at block end, particles
        still occupying positions defined only within this block are destroyed in
        reverse definition order, firing destructors along the way.
        """
        for definition in reversed(scope.current_scope_definitions()):
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
            _ = self._execute_destruction_cascade(
                position,
                occupancy.occupant,
                operation_graph_model.DestructionFact(
                    destroyed_position_in_destroyer=position,
                    destroying_action=self._definition.typed_name,
                ),
                scope,
                is_auto_destruction=True,
                auto_destruction_target=auto_destruction_target,
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
            action_contract.PositionOccupancyState.EMPTY, position, scope
        )
        qualities = self._get_transitive_required_qualities(position, scope)
        diags = self._executor.execute_create(
            particle_operation.Create(target=position, qualities=qualities)
        )
        self._diagnostics.extend(diags)
        if diags:
            return
        self._run_constructors(position, qualities, scope)
        self._check_trigger(position, scope)

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
            action_contract.PositionOccupancyState.OCCUPIED, stmt.target_position, scope
        )
        destruction_fact = operation_graph_model.DestructionFact(
            destroyed_position_in_destroyer=stmt.target_position,
            destroying_action=self._definition.typed_name,
        )

        def before_destroy() -> _PendingDestructionContract | None:
            return self._execute_destruction_cascade(
                stmt.target_position,
                self._tracker.get_occupant(stmt.target_position),
                destruction_fact,
                scope,
                destroy_particle=False,
            )

        diags, pending_contract = self._executor.execute_destroy(
            particle_operation.Destroy(target=stmt.target_position),
            before_destroy=before_destroy,
            destruction_fact=destruction_fact,
        )
        self._diagnostics.extend(diags)
        if pending_contract is None:
            return
        self._record_destruction_contract(
            pending_contract.particle,
            pending_contract.child_state,
            destruction_fact,
            stmt.target_position,
            is_auto_destruction=False,
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
        self._execute_move(stmt.source_position, stmt.target_position, scope)

    def _execute_move(
        self,
        from_pos: ast.PositionReference,
        to_pos: ast.PositionReference,
        scope: scope_tracker.ScopeTracker,
    ):
        """Execute a move and update tracker state."""
        if self._tracker.has_error_state(from_pos) or self._tracker.has_error_state(
            to_pos
        ):
            self._tracker.mark_error(from_pos)
            self._tracker.mark_error(to_pos)
            return

        self._maybe_infer_requirements_on_chain(
            action_contract.PositionOccupancyState.OCCUPIED, from_pos, scope
        )
        self._maybe_infer_requirements_on_chain(
            action_contract.PositionOccupancyState.EMPTY, to_pos, scope
        )

        target_required_qualities, _ = self._get_direct_required_qualities(
            to_pos, scope
        )
        move_diagnostics = self._executor.execute_move(
            particle_operation.Move(
                source=from_pos,
                target=to_pos,
                target_required_qualities=target_required_qualities or (),
            )
        )
        if move_diagnostics:
            self._diagnostics.extend(move_diagnostics)
            return
        self._check_trigger(to_pos, scope)

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
        if not self._dead_tracker.has_position_constraint_candidates():
            return
        parent_position_name_count: int | None = None
        for name_index, typed_name in enumerate(chain.typed_names):
            if (
                parent_position_name_count is not None
                and isinstance(typed_name, ast.GlobalTypedNameReference)
                and typed_name.name_type == ast.NameType.POSITION
            ):
                current_position = chain.position_prefix(parent_position_name_count)
                self._dead_tracker.mark_position_alive(
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
        if not self._dead_tracker.has_constraint_candidates():
            return
        for requirement_in_caller in requirements_in_caller:
            if (
                requirement_in_caller.requirement.required_state
                != action_contract.PositionOccupancyState.OCCUPIED
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
        particle: particle_tracker.ParticleInfo,
        scope: scope_tracker.ScopeTracker,
    ):
        if not self._dead_tracker.has_constraint_candidates():
            return
        constraints, _ = self._get_direct_required_qualities(position, scope)
        if constraints is not None:
            self._dead_tracker.mark_contract_constraints_alive(
                None, particle.origin_position, constraints
            )

    def _check_dead_constraints(self):
        """Emit diagnostics for dead constraints and untriggered actions."""
        for candidate in self._dead_tracker.dead_position_constraints():
            self._diagnostics.append(
                diagnostics.DeadChildPositionDiagnostic(
                    location=candidate.constraint.location,
                    constraint_name=candidate.constraint.source_typed_name,
                    position_name=candidate.position.source_typed_name,
                )
            )
        for candidate in self._dead_tracker.dead_action_constraints():
            self._diagnostics.append(
                diagnostics.UntriggeredActionDiagnostic(
                    location=candidate.constraint.location,
                    constraint_name=candidate.constraint.source_typed_name,
                    position_name=candidate.position.source_typed_name,
                )
            )
        for implied_action in self._dead_tracker.untriggered_implied_actions():
            self._diagnostics.append(
                diagnostics.UntriggeredImpliedActionDiagnostic(
                    location=implied_action.location,
                    implied_action_name=implied_action.source_typed_name,
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
        own_guarantees: list[action_contract.GuaranteePair],
        scope: scope_tracker.ScopeTracker,
    ):
        """Keep origin position constraints alive through this action's final guarantees."""
        if not self._dead_tracker.has_constraint_candidates():
            return
        for _, guarantee in own_guarantees:
            final_position = guarantee.caused_by
            origin_position = self._particle_origin_position(final_position)
            if origin_position is None:
                continue
            constraints, _ = self._get_direct_required_qualities(final_position, scope)
            if constraints is not None:
                self._dead_tracker.mark_contract_constraints_alive(
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
            position for position, _ in contract.guarantees.own
        )
        return PostorderValidationResult(
            diagnostics=self._diagnostics,
            edges=self._action_edges,
            contract=contract,
            operation_graph=operation_graph_builder.finish(),
        )

    def _check_trigger(
        self,
        position: ast.PositionReference,
        scope: scope_tracker.ScopeTracker,
    ):
        """Check trigger, detecting self-triggering as an error."""
        if position.get_last_action_children() is not None:
            self._check_interface_fill_trigger(position, scope)
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
            self._dead_tracker.register_implied_action(implied_action)
        for pos in definition.interface_positions:
            # Skip duplicates so the first definition's constraints are preserved,
            # matching file_validator's behavior of not adding conflicting names.
            if not scope.is_defined(pos.typed_name):
                scope.add_definition(pos)
                self._dead_tracker.register_position_constraints(
                    pos, self._definition_results
                )

        # Set all positions from the Trigger Conditions Block as having
        # the state that the Trigger Conditions Block says they have.
        trigger_ref = self._action_definition.trigger_position_reference
        if trigger_ref is not None:
            qualities = self._get_transitive_required_qualities(trigger_ref, scope)
            self._tracker.operation_graph_builder.record_requirement(
                trigger_ref,
                action_contract.PositionOccupancyState.OCCUPIED,
            )
            # DLP 37: We assume trigger points are occupied upon the start
            # of the action, but we can only assume they have the qualities
            # they are declared with.
            self._executor.execute_assume_occupied(
                particle_operation.AssumeOccupied(
                    target=trigger_ref,
                    qualities=qualities,
                    contracted_position_chain=trigger_ref,
                )
            )

        scope.enter_child_scope()
        self._analyze_statements(definition.action_statements, scope)

        contract = self._generate_contract()
        self._mark_own_contract_guarantees_alive(contract.guarantees.own, scope)
        self._check_dead_constraints()
        return contract

    def _generate_contract(self) -> action_contract.ActionContract:
        """Generate the action contract from inferred requirements and final tracker state."""
        if self._action_definition.is_destructor:
            guarantees = self._check_destructor_guarantees()
        else:
            own_guarantees = self._tracker.generate_own_guarantees(
                self._action_definition.interface_position_names,
                self._implied_quality_list,
                self._inferred_requirements,
            )
            guarantees = action_contract.Guarantees(
                own=own_guarantees,
                nested=self._tracker.nested_guarantees(),
            )
        return action_contract.ActionContract(
            requirements=self._inferred_requirements,
            guarantees=guarantees,
            destruction_contracts=self._destruction_contracts,
            trigger_position_name=self._trigger_position_name or "",
        )

    def _check_destructor_guarantees(self) -> action_contract.Guarantees:
        """Emit a diagnostic for each guarantee a destructor produces and return a contract that masks them.

        A destructor may not change any contracted position's state (DLP 41), so
        each guarantee it produces is a violation. The returned contract may not
        advertise such a guarantee, so each is replaced with an ErrorGuarantee
        that leaves the position's post-destructor state undetermined for any
        consumer of the contract. The destructor's guarantees are fully expanded
        (no nested references), so the returned contract has no nested guarantees.
        """
        produced = self._tracker.generate_flattened_guarantees(
            self._action_definition.interface_position_names,
            self._implied_quality_list,
            self._inferred_requirements,
        )
        rewritten: list[action_contract.GuaranteePair] = []
        for key, guarantee in produced:
            # TODO: caused_by names the position as it was written in the action
            # where the guarantee originated, so a guarantee surfaced from a
            # deeply-nested triggered action gets that callee's short chained name
            # (e.g. "position<out>") instead of its full chained name relative to
            # the destructor (e.g.
            # "action</a>::position<box>::action</b>::position<out>"). ``key`` holds
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
                    rewritten.append((key, guarantee))
                    continue
                case action_contract.UnchangedGuarantee():
                    rewritten.append((key, guarantee))
                    continue
                case _:
                    raise TypeError(
                        f"unexpected guarantee type {type(guarantee).__name__}"
                    )
            rewritten.append(
                (
                    key,
                    action_contract.ErrorGuarantee(
                        caused_by=guarantee.caused_by,
                        operation_positions=guarantee.operation_positions,
                    ),
                )
            )
        return action_contract.Guarantees(own=rewritten, nested=())

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
