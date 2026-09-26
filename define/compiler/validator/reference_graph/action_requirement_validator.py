"""Infer, propagate, and check Action Requirements."""

from __future__ import annotations

import typing

from define.compiler.validator.reference_graph import (
    action_contract,
    particle_info,
    position_occupancy,
    requirement_violation,
)

if typing.TYPE_CHECKING:
    from define.compiler import ast, diagnostics
    from define.compiler.validator import scope_tracker
    from define.compiler.validator.reference_graph import (
        particle_tracker,
        position_quality_resolver,
    )


class ActionRequirementValidator:
    """Infer an Action's requirements and check requirements of triggered Actions."""

    _definition: ast.ActionDefinition
    _tracker: particle_tracker.ParticleTracker
    _position_quality_resolver: position_quality_resolver.PositionQualityResolver
    _inferred_occupancy_requirements: dict[
        tuple[str, ...], action_contract.PositionOccupancyRequirement
    ]

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
        self._inferred_occupancy_requirements = {}
        self.value_requirements: dict[
            tuple[str, ...], action_contract.ValueRequirement
        ] = {}

    @property
    def occupancy_requirements(
        self,
    ) -> dict[tuple[str, ...], action_contract.PositionOccupancyRequirement]:
        """The requirements inferred for this Action's contract."""
        return self._inferred_occupancy_requirements

    def _record_requirement(
        self,
        *,
        required_state: position_occupancy.PositionOccupancyState,
        contracted_position: ast.PositionReference,
        local_position: ast.PositionReference,
        inferred_at: ast.SourceLocation,
        propagated_from: action_contract.PositionOccupancyRequirement | None,
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
        self._inferred_occupancy_requirements[requirement_key] = (
            action_contract.PositionOccupancyRequirement(
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
        requirements_in_caller: list[
            action_contract.PositionRequirementInCaller[
                action_contract.PositionOccupancyRequirement
            ]
        ],
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
        requirements_in_caller: list[
            action_contract.PositionRequirementInCaller[
                action_contract.PositionOccupancyRequirement
            ]
        ],
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
        req: action_contract.PositionOccupancyRequirement,
    ) -> tuple[bool, particle_info.ParticleInfo | None]:
        occupancy = self._tracker.get_occupancy_info(full_caller_chain)
        if occupancy.has_error:
            return False, None
        occupant = occupancy.occupant
        state = (
            position_occupancy.PositionOccupancyState.OCCUPIED
            if occupant is not None
            else position_occupancy.PositionOccupancyState.EMPTY
        )
        return requirement_violation.is_violated(req, state, None), occupant

    def check_destructor_requirements(
        self,
        destructor: action_contract.Destructor,
        requirements_in_caller: list[
            action_contract.PositionRequirementInCaller[
                action_contract.PositionOccupancyRequirement
            ]
        ],
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

    def infer_value_requirement(
        self,
        position: ast.PositionReference,
        *,
        inferred_at: ast.SourceLocation,
        propagated_from: action_contract.ValueRequirement | None = None,
        action_assignment: action_contract.ActionAssignment | None = None,
    ):
        """Require a caller-provided particle's value when it is still unknown."""
        occupancy = self._tracker.get_occupancy_info(position)
        particle = occupancy.occupant
        if occupancy.has_error or particle is None:
            return
        if particle.qualities.value_type is None:
            return
        if particle.value_state is not None:
            return
        contracted_position = particle.origin_position
        # Interfaces stop direct inference, including reads after a particle moves.
        if contracted_position.get_last_action() is not None:
            return
        self.value_requirements[contracted_position.canonical_chained_name_tuple] = (
            action_contract.ValueRequirement(
                position=contracted_position,
                inferred_at=inferred_at,
                enclosing_action=self._definition,
                propagated_from=propagated_from,
                action_assignment=action_assignment,
            )
        )
        particle.value_state = particle_info.ParticleValueState.SET

    def propagate_value_requirements(
        self,
        action_chain: ast.ActionReference,
        requirements: list[
            action_contract.PositionRequirementInCaller[
                action_contract.ValueRequirement
            ]
        ],
        action_assignment: action_contract.ActionAssignment | None,
    ):
        """Propagate value requirements after occupancy requirements are resolved."""
        for requirement in requirements:
            self.infer_value_requirement(
                requirement.caller_position,
                inferred_at=action_chain.location,
                propagated_from=requirement.requirement,
                action_assignment=action_assignment,
            )

    def check_value_requirements(
        self,
        requirements: list[
            action_contract.PositionRequirementInCaller[
                action_contract.ValueRequirement
            ]
        ],
        *,
        acting_on_position: ast.PositionReference,
        action_assignment: action_contract.ActionAssignment | None,
        destructor: action_contract.Destructor | None = None,
        auto_destruction_target: ast.PositionReference | None = None,
    ) -> list[diagnostics.Diagnostic]:
        """Check value requirements using the state immediately before triggering."""
        validation_diagnostics: list[diagnostics.Diagnostic] = []
        for requirement in requirements:
            occupancy = self._tracker.get_occupancy_info(requirement.caller_position)
            particle = occupancy.occupant
            # Occupancy failures already have their own diagnostic.
            if occupancy.has_error or particle is None:
                continue
            if not requirement_violation.is_violated(
                requirement.requirement,
                position_occupancy.PositionOccupancyState.OCCUPIED,
                particle.value_state,
            ):
                continue
            if destructor is None:
                diagnostic = requirement_violation.trigger_violation(
                    req=requirement.requirement,
                    definition=self._definition,
                    full_caller_chain=requirement.caller_position,
                    acting_on_position=acting_on_position,
                    occupant=particle,
                    action_assignment=action_assignment,
                )
            else:
                diagnostic = requirement_violation.direct_destructor(
                    req=requirement.requirement,
                    definition=self._definition,
                    full_caller_chain=requirement.caller_position,
                    occupant=particle,
                    destructor=destructor,
                    auto_destruction_target=auto_destruction_target,
                )
            validation_diagnostics.append(diagnostic)
            self._tracker.mark_value_error(requirement.caller_position)
        return validation_diagnostics
