"""Decides, from an action's final state, what destroying each callee's particle does with the callee's Guarantees."""

from __future__ import annotations

import typing
from functools import cached_property

import msgspec

from define.compiler import ast, chained_name, name_types
from define.compiler.validator import codegen_input
from define.compiler.validator.reference_graph import action_contract

if typing.TYPE_CHECKING:
    from define.compiler.data_structures import typed_name_dict
    from define.compiler.validator import validation_result
    from define.compiler.validator.reference_graph import (
        action_requirement_validator,
        position_quality_resolver,
        quality_assignment,
        reference_graph_validation_state,
    )
    from define.compiler.validator.reference_graph.particles import (
        particle_info,
        particle_tracker,
    )


class CalleesWithDestruction(msgspec.Struct, frozen=True):
    """An action's callees, each with what destroying its particle does with its Guarantees."""

    callees: list[action_contract.CalleeContract]
    # One entry for each callee whose Destructors run when its Guarantees are
    # dropped.
    guaranteed_particle_destructors: list[codegen_input.GuaranteedParticleDestructors]


class ChildPositionsAndDestructors(msgspec.Struct, frozen=True):
    """A particle's child positions and its Destructors, as destruction sees them."""

    child_positions: list[ast.PositionReference]
    destructors: list[ast.GlobalTypedNameReference]


class _GuaranteedDestructor(msgspec.Struct, frozen=True):
    """A Destructor on a particle an action created, found by its destruction plan walk."""

    position: ast.PositionReference
    particle: particle_info.ParticleInfo
    destructor: ast.GlobalTypedNameReference
    contract: action_contract.ActionContract


class _CalleeDestructorsFound(msgspec.Struct):
    """What destroying one callee's particle must still run, found by the walk of this action's final state."""

    destructors: list[_GuaranteedDestructor] = msgspec.field(default_factory=list)
    callee_destructors: list[codegen_input.CalleeDestructorsReference] = msgspec.field(
        default_factory=list
    )
    # Set when the Guarantees of one of the callee's own callees must be
    # applied.
    must_apply: bool = False


class CalleeDestructionValidator:
    """Decides what destroying each of an action's callees' particles does with the callee's Guarantees."""

    _definition: ast.ActionDefinition
    _implied_qualities: tuple[ast.GlobalTypedNameReference, ...]
    _definition_results: typed_name_dict.TypedNameDict[
        ast.GlobalTypedName[ast.GlobalNameContent[ast.Fqun | None]],
        validation_result.DefinitionValidationResult,
    ]
    _validation_state: reference_graph_validation_state.ReferenceGraphValidationState
    _tracker: particle_tracker.ParticleTracker
    _quality_resolver: position_quality_resolver.PositionQualityResolver
    _requirement_validator: action_requirement_validator.ActionRequirementValidator

    def __init__(
        self,
        definition: ast.ActionDefinition,
        implied_qualities: tuple[ast.GlobalTypedNameReference, ...],
        definition_results: typed_name_dict.TypedNameDict[
            ast.GlobalTypedName[ast.GlobalNameContent[ast.Fqun | None]],
            validation_result.DefinitionValidationResult,
        ],
        validation_state: reference_graph_validation_state.ReferenceGraphValidationState,
        tracker: particle_tracker.ParticleTracker,
        quality_resolver: position_quality_resolver.PositionQualityResolver,
        requirement_validator: action_requirement_validator.ActionRequirementValidator,
    ):
        """Initialize with the action being validated and the state its validator tracks."""
        self._definition = definition
        self._implied_qualities = implied_qualities
        self._definition_results = definition_results
        self._validation_state = validation_state
        self._tracker = tracker
        self._quality_resolver = quality_resolver
        self._requirement_validator = requirement_validator

    @cached_property
    def _transitive_implied_qualities(self) -> quality_assignment.QualityAssignments:
        return self._quality_resolver.get_transitive_implied_qualities(
            self._implied_qualities
        )

    def callees_with_destruction(
        self,
        guarantees: dict[
            chained_name.PositionReferenceTuple, action_contract.PositionGuarantee
        ],
    ) -> CalleesWithDestruction:
        """Return this action's callees, each with what destroying its particle does with its Guarantees, decided from this action's final state."""
        # Every callee whose Destructors could run gets them, because this
        # action's generated code must not depend on its callers.
        # TODO: Add an optimization mode that uses the whole program to leave
        # them out for callees whose Guarantees no destruction drops.
        tracked_executions = self._tracker.tracked_action_executions()
        # This action's errors are already reported, and a destroyer skips the
        # positions they mark, so applying its callees' Guarantees would find
        # nothing more to report.
        found = (
            {}
            if self._tracker.has_any_recorded_error()
            else self._find_callee_destructors(guarantees)
        )
        result = CalleesWithDestruction(callees=[], guaranteed_particle_destructors=[])
        occurrences: dict[chained_name.ActionReferenceTuple, int] = {}
        for execution, action_chain in tracked_executions.items():
            occurrence = occurrences.get(action_chain, 0) + 1
            occurrences[action_chain] = occurrence
            callee_found = found.get(execution)
            on_destruction = self._callee_on_destruction(callee_found)
            result.callees.append(
                action_contract.CalleeContract(
                    action_chain,
                    self._validation_state.get_contract(
                        execution.action.get_last_action()
                    ),
                    on_destruction,
                    occurrence,
                )
            )
            if (
                on_destruction
                == action_contract.GuaranteesOnDestruction.DISCARD_AFTER_DESTRUCTORS
            ):
                result.guaranteed_particle_destructors.append(
                    self._guaranteed_particle_destructors_of(
                        action_chain,
                        occurrence,
                        typing.cast("_CalleeDestructorsFound", callee_found),
                    )
                )
        return result

    def _callee_on_destruction(
        self, found: _CalleeDestructorsFound | None
    ) -> action_contract.GuaranteesOnDestruction:
        if found is None:
            return action_contract.GuaranteesOnDestruction.DISCARD
        # Checking a Destructor reads the state below its particle, which can
        # change what the walk would see there, so every Destructor is checked
        # only after the walk that collected them.
        if found.must_apply or not all(
            self._destructor_requirements_satisfied(destructor)
            for destructor in found.destructors
        ):
            return action_contract.GuaranteesOnDestruction.APPLY
        return action_contract.GuaranteesOnDestruction.DISCARD_AFTER_DESTRUCTORS

    @staticmethod
    def _guaranteed_particle_destructors_of(
        callee: chained_name.ActionReferenceTuple,
        occurrence: int,
        found: _CalleeDestructorsFound,
    ) -> codegen_input.GuaranteedParticleDestructors:
        destructors: list[ast.ActionReference] = []
        for destructor in found.destructors:
            destructors.append(
                destructor.position.with_action_suffix(destructor.destructor)
            )
        return codegen_input.GuaranteedParticleDestructors(
            callee=callee,
            occurrence=occurrence,
            destructors=destructors,
            callee_destructors=found.callee_destructors,
        )

    def _find_callee_destructors(
        self,
        published: dict[
            chained_name.PositionReferenceTuple, action_contract.PositionGuarantee
        ],
    ) -> dict[codegen_input.ActionExecution, _CalleeDestructorsFound]:
        """Walk this action's final state, finding what destroying each callee's particle must still run, keyed by the callee's Action Execution."""
        found: dict[codegen_input.ActionExecution, _CalleeDestructorsFound] = {}
        self._find_unapplied_callee_destructors(None, found)
        # Its implied positions hold what its callees created on its own
        # particle, and its interface positions what they created below the
        # particles its caller gave it.
        roots: list[ast.PositionReference] = []
        for definition in self._definition.interface_positions:
            roots.append(
                ast.PositionReference(
                    location=definition.location, typed_names=(definition.typed_name,)
                )
            )
        for quality in self._transitive_implied_qualities.assignments:
            if quality.name_type == name_types.NameType.POSITION:
                roots.append(
                    ast.PositionReference(
                        location=quality.location, typed_names=(quality,)
                    )
                )
        for position in roots:
            self._find_particle_callee_destructors(position, published, found)
        return found

    def _find_particle_callee_destructors(
        self,
        position: ast.PositionReference,
        published: dict[
            chained_name.PositionReferenceTuple, action_contract.PositionGuarantee
        ],
        found: dict[codegen_input.ActionExecution, _CalleeDestructorsFound],
    ):
        key = position.canonical_chained_name_tuple
        # This reads only what this action recorded. Callees' Guarantees that
        # are still pending are covered by their own callers' entries instead.
        particle = self._tracker.recorded_occupant_or_none_by_key(key)
        if particle is None:
            return
        self._find_unapplied_callee_destructors(position, found)
        children_and_destructors = self.child_positions_and_destructors(
            position, particle
        )
        # A particle this action publishes is seen by whoever destroys it, and
        # a particle from this action's caller is already known to them. This
        # action publishes everything its own statements wrote, so any other
        # particle was last written by a callee.
        if key not in published and not particle.from_caller:
            execution = self._tracker.callee_execution_that_wrote(key)
            for destructor in children_and_destructors.destructors:
                # A circular reference, already reported, leaves a Destructor's
                # contract unpublished, and a destroyer skips such a Destructor
                # too.
                contract = self._validation_state.get_contract_or_none(destructor)
                if contract is None:
                    continue
                found.setdefault(
                    execution, _CalleeDestructorsFound()
                ).destructors.append(
                    _GuaranteedDestructor(position, particle, destructor, contract)
                )
        for child in children_and_destructors.child_positions:
            self._find_particle_callee_destructors(child, published, found)

    def _find_unapplied_callee_destructors(
        self,
        position: ast.PositionReference | None,
        found: dict[codegen_input.ActionExecution, _CalleeDestructorsFound],
    ):
        """Record, for the callees of this action whose Guarantees about the particle in ``position`` are still pending, what destroying it runs.

        A ``position`` of None means this action's parent particle.
        """
        for callee_destructors in self._tracker.unapplied_callee_destructors(
            chained_name.ACTION_PARENT_PARTICLE
            if position is None
            else position.canonical_chained_name_tuple
        ):
            match callee_destructors.callee.on_destruction:
                case action_contract.GuaranteesOnDestruction.APPLY:
                    found.setdefault(
                        callee_destructors.execution, _CalleeDestructorsFound()
                    ).must_apply = True
                case action_contract.GuaranteesOnDestruction.DISCARD:
                    pass
                case action_contract.GuaranteesOnDestruction.DISCARD_AFTER_DESTRUCTORS:
                    found.setdefault(
                        callee_destructors.execution, _CalleeDestructorsFound()
                    ).callee_destructors.append(
                        self.callee_destructors_reference(callee_destructors, position)
                    )

    def callee_destructors_reference(
        self,
        callee_destructors: particle_tracker.CalleeDestructors,
        position: ast.PositionReference | None,
    ) -> codegen_input.CalleeDestructorsReference:
        """Return the reference to ``callee_destructors``, whose callee's particle is at or above ``position``."""
        return codegen_input.CalleeDestructorsReference(
            caller=self._triggering_action_chain(callee_destructors, position),
            callee=callee_destructors.callee.action_chain,
            occurrence=callee_destructors.callee.occurrence,
        )

    def _triggering_action_chain(
        self,
        callee_destructors: particle_tracker.CalleeDestructors,
        position: ast.PositionReference | None,
    ) -> ast.ActionReference:
        """Return the chain of the action that triggered the callee of ``callee_destructors``, whose particle is at or above ``position``."""
        chain = callee_destructors.triggering_action_chain
        if callee_destructors.triggering_action_is_implied:
            # The caller is assigned to this action's parent particle, so it is
            # one of this action's implied qualities.
            quality = self._transitive_implied_qualities.quality_named(chain[-1])
            return ast.ActionReference(
                location=quality.location, typed_names=(quality,)
            )
        # A caller's callees are assigned to particles at or below its own, so
        # the caller of a callee on this action's parent particle, where
        # ``position`` is None, is always implied. ``position`` is set here.
        caller_position = typing.cast(
            "ast.PositionReference", position
        ).position_prefix(len(chain) - 1)
        caller_particle = self._tracker.recorded_occupant(caller_position)
        return caller_position.with_action_suffix(
            caller_particle.qualities.quality_named(chain[-1])
        )

    def child_positions_and_destructors(
        self, position: ast.PositionReference, particle: particle_info.ParticleInfo
    ) -> ChildPositionsAndDestructors:
        """Return the child positions and Destructors of the particle at ``position``."""
        children_and_destructors = ChildPositionsAndDestructors(
            child_positions=[], destructors=[]
        )
        # A particle keeps its own qualities across Moves, so its qualities (not
        # the current Position's constraints) determine its child Positions and
        # Destructors.
        for quality in particle.qualities.assignments:
            if quality.name_type == name_types.NameType.POSITION:
                children_and_destructors.child_positions.append(
                    position.with_position_suffix(quality)
                )
            elif quality.name_type == name_types.NameType.ACTION:
                definition_result = self._definition_results.get(quality)
                # Reference validation has already reported unresolved qualities;
                # their absence must not prevent checking the remaining Destructors.
                if definition_result is None:
                    continue
                definition = typing.cast(
                    "ast.ActionDefinition", definition_result.definition
                )
                if definition.is_destructor:
                    children_and_destructors.destructors.append(quality)
                for interface_position in definition.interface_positions:
                    children_and_destructors.child_positions.append(
                        position.with_position_suffix(
                            quality, interface_position.typed_name
                        )
                    )
        return children_and_destructors

    def _destructor_requirements_satisfied(self, found: _GuaranteedDestructor) -> bool:
        """Return whether this action's final state satisfies the requirements of a Destructor on a particle it created, without reporting anything."""
        # A caller may still satisfy them before destroying the particle, so
        # only the destroyer can tell whether they fail. It checks them again,
        # and reports any failure, after applying this action's Guarantees.
        contract = found.contract
        action_chain = found.position.with_action_suffix(found.destructor)
        destructor_record = action_contract.Destructor(
            destructor=found.destructor,
            position=found.position,
            origin_position=found.particle.origin_position,
        )
        if self._requirement_validator.check_destructor_requirements(
            destructor_record,
            contract.occupancy_requirements_in_caller(action_chain),
            auto_destruction_target=None,
        ):
            return False
        return not self._requirement_validator.check_value_requirements(
            contract.value_requirements_in_caller(action_chain),
            acting_on_position=found.position,
            action_assignment=destructor_record.action_assignment(),
            destructor=destructor_record,
        )
