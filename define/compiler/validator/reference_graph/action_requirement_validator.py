"""Infer, propagate, and check Action Requirements."""

from __future__ import annotations

import typing

from define.compiler.validator.reference_graph import (
    action_contract,
    position_occupancy,
    requirement_violation,
)

if typing.TYPE_CHECKING:
    from define.compiler import ast, diagnostics
    from define.compiler.validator import scope_tracker
    from define.compiler.validator.reference_graph import (
        particle_info,
        particle_tracker,
        position_quality_resolver,
    )


class ActionRequirementValidator:
    """Infer an Action's requirements and check requirements of triggered Actions."""

    _definition: ast.ActionDefinition
    _tracker: particle_tracker.ParticleTracker
    _position_quality_resolver: position_quality_resolver.PositionQualityResolver
    _inferred_requirements: dict[tuple[str, ...], action_contract.PositionRequirement]

    def __init__(
        self,
        definition: ast.ActionDefinition,
        tracker: particle_tracker.ParticleTracker,
        quality_resolver: position_quality_resolver.PositionQualityResolver,
    ):
        """Initialize with the Action Definition, particle state, and Quality resolution."""
        self._definition = definition
        self._tracker = tracker
        self._position_quality_resolver = quality_resolver
        self._inferred_requirements = {}

    @property
    def requirements(
        self,
    ) -> dict[tuple[str, ...], action_contract.PositionRequirement]:
        """The requirements inferred for this Action's contract."""
        return self._inferred_requirements

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
    def propagate_action_requirements(
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

    def infer_requirements_on_chain(
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
            self._definition.interface_positions_by_name,
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

    def check_requirements(
        self,
        acting_on_position: ast.PositionReference,
        requirements_in_caller: list[action_contract.PositionRequirementInCaller],
        *,
        action_assignment: action_contract.ActionAssignment | None,
    ) -> list[diagnostics.Diagnostic]:
        """Emit diagnostics for every requirement in contract that doesn't hold at acting_on_position.

        ``requirements_in_caller`` contains the contract's requirements and
        their positions from the caller's perspective.
        """
        validation_diagnostics: list[diagnostics.Diagnostic] = []
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
                validation_diagnostics.append(
                    requirement_violation.trigger_violation(
                        req=req,
                        definition=self._definition,
                        full_caller_chain=full_caller_chain,
                        acting_on_position=acting_on_position,
                        occupant=occupant,
                        action_assignment=action_assignment,
                    )
                )
        return validation_diagnostics

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

    def check_destructor_requirements(
        self,
        destructor: action_contract.Destructor,
        requirements_in_caller: list[action_contract.PositionRequirementInCaller],
        *,
        auto_destruction_target: ast.PositionReference | None,
    ) -> list[diagnostics.Diagnostic]:
        """Check the requirements of a directly known Destructor."""
        validation_diagnostics: list[diagnostics.Diagnostic] = []
        for requirement_in_caller in requirements_in_caller:
            req = requirement_in_caller.requirement
            full_caller_chain = requirement_in_caller.caller_position
            violated, occupant = self._requirement_violation_occupant(
                full_caller_chain, req
            )
            if violated:
                validation_diagnostics.append(
                    requirement_violation.direct_destructor(
                        req=req,
                        definition=self._definition,
                        full_caller_chain=full_caller_chain,
                        occupant=occupant,
                        destructor=destructor,
                        auto_destruction_target=auto_destruction_target,
                    )
                )
        return validation_diagnostics
