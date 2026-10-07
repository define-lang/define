"""Infer, propagate, and check Action Requirements."""

from __future__ import annotations

import typing

from define.compiler.validator.reference_graph import (
    action_contract,
    position_occupancy,
)
from define.compiler.validator.reference_graph.particles import particle_info

if typing.TYPE_CHECKING:
    from define.compiler import ast, chained_name
    from define.compiler.errors import diagnostics
    from define.compiler.validator import scope_tracker
    from define.compiler.validator.reference_graph import position_quality_resolver
    from define.compiler.validator.reference_graph.callee_execution import (
        callee_execution,
    )
    from define.compiler.validator.reference_graph.particles import particle_tracker


class ActionRequirementValidator:
    """Infer an Action's requirements and check requirements of triggered Actions."""

    _definition: ast.ActionDefinition
    _tracker: particle_tracker.ParticleTracker
    _position_quality_resolver: position_quality_resolver.PositionQualityResolver
    _inferred_occupancy_requirements: dict[
        chained_name.PositionReferenceTuple,
        action_contract.PositionOccupancyRequirement,
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
            chained_name.PositionReferenceTuple, action_contract.ValueRequirement
        ] = {}

    @property
    def occupancy_requirements(
        self,
    ) -> dict[
        chained_name.PositionReferenceTuple,
        action_contract.PositionOccupancyRequirement,
    ]:
        """The requirements inferred for this Action's contract."""
        return self._inferred_occupancy_requirements

    def _record_requirement(
        self,
        requirement: action_contract.PositionOccupancyRequirement,
        local_position: ast.PositionReference,
        scope: scope_tracker.ScopeTracker,
    ):
        """Record ``requirement`` in this definition's contract and reflect it in the tracker at ``local_position``, the position in this definition's local namespace that the requirement's contracted position names."""
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
        contracted_position = requirement.position
        self._inferred_occupancy_requirements[
            contracted_position.canonical_chained_name_tuple
        ] = requirement
        # ERROR represents a tracker failure and is never a Position Requirement state.
        requirement_state = typing.cast(
            "typing.Literal[position_occupancy.PositionOccupancyState.OCCUPIED, position_occupancy.PositionOccupancyState.EMPTY]",
            requirement.required_state,
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

    def propagate_action_requirements(
        self,
        inferred_at: ast.SourceLocation,
        requirements_in_caller: list[action_contract.OccupancyRequirementInCaller],
        scope: scope_tracker.ScopeTracker,
    ):
        """Propagate the requirements of a callee triggered at ``inferred_at`` into this definition's contract."""
        propagated_requirements = self._tracker.propagate_requirements(
            requirements_in_caller
        )
        for propagated in propagated_requirements:
            requirement_in_caller = propagated.requirement_in_caller
            self._record_requirement(
                requirement_in_caller.requirement.propagated_to(
                    self._definition,
                    inferred_at=inferred_at,
                    position=propagated.contracted_position,
                    action_assignment=requirement_in_caller.action_assignment,
                ),
                requirement_in_caller.caller_position,
                scope,
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
            contracted_position = resolved_requirement.contracted_position
            self._record_requirement(
                action_contract.PositionOccupancyRequirement(
                    required_state=resolved_requirement.required_state,
                    position=contracted_position,
                    inferred_at=contracted_position.location,
                    enclosing_action=self._definition,
                ),
                resolved_requirement.local_position,
                scope,
            )

    def check_occupancy_requirements(
        self,
        execution: callee_execution.CalleeExecution,
        requirements_in_caller: list[action_contract.OccupancyRequirementInCaller],
    ) -> list[diagnostics.Diagnostic]:
        """Emit diagnostics for every occupancy requirement of the callee that doesn't hold before ``execution``.

        ``requirements_in_caller`` contains the callee's requirements and
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
                    execution.requirement_violation(
                        req, full_caller_chain, occupant, self._definition
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
        return req.is_violated_by(state), occupant

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
        inferred_at: ast.SourceLocation,
        requirements: list[action_contract.ValueRequirementInCaller],
    ):
        """Propagate the value requirements of a callee triggered at ``inferred_at``, after occupancy requirements are resolved."""
        for requirement in requirements:
            self.infer_value_requirement(
                requirement.caller_position,
                inferred_at=inferred_at,
                propagated_from=requirement.requirement,
                action_assignment=requirement.action_assignment,
            )

    def check_value_requirements(
        self,
        execution: callee_execution.CalleeExecution,
        requirements: list[action_contract.ValueRequirementInCaller],
    ) -> list[diagnostics.Diagnostic]:
        """Check the callee's value requirements using the state immediately before ``execution``."""
        validation_diagnostics: list[diagnostics.Diagnostic] = []
        for requirement in requirements:
            particle = self._value_requirement_violation(requirement)
            if particle is None:
                continue
            validation_diagnostics.append(
                execution.requirement_violation(
                    requirement.requirement,
                    requirement.caller_position,
                    particle,
                    self._definition,
                )
            )
            self._tracker.mark_value_error(requirement.caller_position)
        return validation_diagnostics

    def _value_requirement_violation(
        self,
        requirement: action_contract.ValueRequirementInCaller,
    ) -> particle_info.ParticleInfo | None:
        """Return the particle whose value violates ``requirement``, if one does."""
        occupancy = self._tracker.get_occupancy_info(requirement.caller_position)
        particle = occupancy.occupant
        # Occupancy failures already have their own diagnostic.
        if occupancy.has_error or particle is None:
            return None
        if not requirement.requirement.is_violated_by(
            position_occupancy.PositionOccupancyState.OCCUPIED,
            particle.value_state,
        ):
            return None
        return particle
