"""Action contract types: automatically inferred requirements and guarantees."""

from __future__ import annotations

import enum
import typing
from dataclasses import dataclass, field

from define.compiler.validator.reference_graph import (
    destruction_contract as destruction_contract_types,
)
from define.compiler.validator.reference_graph import (
    operation_graph_model,
    position_occupancy,
)

if typing.TYPE_CHECKING:
    from collections.abc import Iterator

    from define.compiler import ast
    from define.compiler.validator.reference_graph import (
        child_state,
        quality_assignment,
    )


class PropagationKind(enum.Enum):
    """How a requirement reached a given step in its propagation chain."""

    # The deepest step in the chain: the definition's own body inferred the
    # requirement directly.
    DIRECT_INFERENCE = enum.auto()
    # The current definition's body destroyed a caller-passed particle,
    # firing a destructor; the destructor's requirements propagated up.
    DESTRUCTOR_CASCADE = enum.auto()
    # A position constraint directly assigned a quality to a position.
    QUALITY_ASSIGNED = enum.auto()
    # Creating a particle triggered one of its constructor qualities.
    CONSTRUCTOR_TRIGGER = enum.auto()
    # The current definition's body triggered an action; the action's
    # requirements propagated up.
    ACTION_TRIGGER = enum.auto()
    # The particle whose destructor requirement is violated was originally
    # created here.
    PARTICLE_ORIGIN = enum.auto()
    # The particle is automatically destroyed at the end of a body, firing the
    # destructor whose requirement is violated.
    AUTO_DESTRUCTION = enum.auto()
    # The contracted position was filled here, which is what violates an
    # empty-requirement.
    FILL_SITE = enum.auto()


@dataclass(frozen=True, slots=True)
class PropagationStep:
    """One step in a requirement's propagation chain, with its source location."""

    location: ast.SourceLocation
    kind: PropagationKind
    # The definition, quality, or position that performs or receives the event
    # described by this step (where ``location`` points).
    enclosing_quality_name: str
    # The quality triggered or assigned by an event involving two names; None
    # when the event only describes ``enclosing_quality_name``.
    triggered_quality_name: str | None


@dataclass(frozen=True, slots=True, eq=False)
class PropagationHistory:
    """A shared sequence of Destruction Contract propagation steps."""

    step: PropagationStep
    previous: PropagationHistory | None

    def __iter__(self) -> Iterator[PropagationStep]:
        """Iterate from the immediate callee to the destroying action."""
        current: PropagationHistory | None = self
        while current is not None:
            yield current.step
            current = current.previous


@dataclass(frozen=True)
class ActionAssignment:
    """An action's assignment to a particle at a position."""

    quality: ast.GlobalTypedNameReference
    assigned_to_position_name: ast.TypedName

    def propagation_step(self) -> PropagationStep:
        """Return the action's assignment step."""
        return PropagationStep(
            location=self.quality.location,
            kind=PropagationKind.QUALITY_ASSIGNED,
            enclosing_quality_name=self.assigned_to_position_name.full_typed_name,
            triggered_quality_name=self.quality.full_typed_name,
        )


@dataclass(frozen=True)
class PositionRequirement:
    """An automatically inferred requirement on a contracted position.

    A contracted position is an interface position, a child of an interface
    position, an implied quality, or a child of an implied quality.
    """

    required_state: position_occupancy.PositionOccupancyState
    # The position this requirement is on. Contains the full chained name
    # that this requirement is on, starting from the contracted position.
    position: ast.PositionReference
    # The statement this action inferred the requirement at: the body statement
    # that imposed it directly, or the trigger statement it propagated through.
    inferred_at: ast.SourceLocation
    enclosing_action: ast.ActionDefinition
    propagated_from: PositionRequirement | None = None
    # The constructor or destructor assignment that caused this requirement to
    # propagate, if relevant. Used to explain that assignment in diagnostics.
    action_assignment: ActionAssignment | None = None

    def root_cause_action(self) -> ast.ActionDefinition:
        """Return the action definition that originally inferred this requirement."""
        current = self
        while current.propagated_from is not None:
            current = current.propagated_from
        return current.enclosing_action

    def root_cause_action_name(self) -> str:
        """Return the canonical name of the action that originally inferred this requirement."""
        return self.root_cause_action().typed_name.source_typed_name

    def propagated_from_locations(self) -> list[ast.SourceLocation]:
        """Locations of intermediate propagation steps, ordered outer to inner."""
        locations: list[ast.SourceLocation] = []
        current = self.propagated_from
        while current is not None:
            locations.append(current.inferred_at)
            current = current.propagated_from
        return locations

    def propagation_chain(self) -> list[PropagationStep]:
        """Return the chain of propagation steps from this requirement down to its root cause."""
        chain: list[PropagationStep] = []
        current: PositionRequirement | None = self
        while current is not None:
            if current.action_assignment is not None:
                chain.append(current.action_assignment.propagation_step())
            chain.append(current.propagation_step())
            current = current.propagated_from
        return chain

    def propagation_step(self) -> PropagationStep:
        """Return the event that propagated this requirement."""
        enclosing_name = self.enclosing_action.typed_name.source_typed_name
        if self.propagated_from is None:
            return PropagationStep(
                location=self.inferred_at,
                kind=PropagationKind.DIRECT_INFERENCE,
                enclosing_quality_name=enclosing_name,
                triggered_quality_name=None,
            )
        other_action = self.propagated_from.enclosing_action
        if other_action.is_destructor:
            kind = PropagationKind.DESTRUCTOR_CASCADE
        else:
            kind = PropagationKind.ACTION_TRIGGER
        return PropagationStep(
            location=self.inferred_at,
            kind=kind,
            enclosing_quality_name=enclosing_name,
            triggered_quality_name=other_action.typed_name.source_typed_name,
        )


@dataclass(frozen=True, slots=True)
class PositionRequirementInCaller:
    """A callee's Position Requirement expressed from its caller's perspective."""

    requirement: PositionRequirement
    caller_position: ast.PositionReference


@dataclass(frozen=True)
class PositionGuarantee:
    """An automatically inferred guarantee about an interface position after action completion."""

    caused_by: ast.PositionReference


@dataclass(frozen=True)
class EmptyGuarantee(PositionGuarantee):
    """The position is guaranteed to be empty after the action completes."""


@dataclass(frozen=True)
class OccupiedByExistingGuarantee(PositionGuarantee):
    """The position contains the same particle that was passed into another interface position."""

    origin_position: ast.PositionReference


@dataclass(frozen=True)
class OccupiedByNewGuarantee(PositionGuarantee):
    """The position contains a new particle created by the action."""

    qualities: quality_assignment.QualityAssignments
    origin_position: ast.PositionReference


@dataclass(frozen=True)
class UnchangedGuarantee(PositionGuarantee):
    """The action operated on the position but left it in the same state it was in at the start of the action."""


@dataclass(frozen=True)
class ErrorGuarantee(PositionGuarantee):
    """The position's state could not be determined due to an error."""


@dataclass(frozen=True, slots=True)
class FinalPositionOperation:
    """The positions operated on by a position's final Particle Operation."""

    position: ast.ChainedNameTuple
    # Operation-graph construction needs every operated position to apply the
    # Empty Rule from the caller's perspective, including both positions of a Move.
    # Canonical chained-name keys are stored instead of PositionReference objects
    # because expressing them from each caller's perspective only requires tuple
    # composition; source locations and written name forms would be unused.
    operation_positions: tuple[ast.ChainedNameTuple, ...]


@dataclass(frozen=True, slots=True)
class CalleeContract:
    """A callee's contract at its current action chain."""

    action_chain: ast.ChainedNameTuple
    execution: operation_graph_model.ActionExecution
    contract: ActionContract


@dataclass(frozen=True, slots=True)
class DestructionContract:
    """Records that an action destroyed a caller-passed particle in a contracted position (DLP 41).

    Callers higher in the stack use this to verify destructors they attach
    that the destroying action could not see.
    """

    propagated_destruction: destruction_contract_types.PropagatedDestruction
    # The position in the shared snapshot stays fixed when a caller expresses
    # the particle's contracted origin from its own perspective.
    position_in_child_state: tuple[str, ...]
    # Verification belongs to a particle, not just a quality: different child
    # particles can have the same Destructor assigned to them.
    verified_destructors: quality_assignment.QualityAssignments


@dataclass(frozen=True, slots=True)
class DestructionContracts:
    """Contracts for particles sharing destruction-time state and propagation history."""

    particles: list[DestructionContract] = field(default_factory=list, init=False)
    # Callers repeatedly need membership checks while verifying child positions.
    positions: set[tuple[str, ...]] = field(default_factory=set, init=False)
    # Particles destroyed together share their destruction-time occupancy.
    child_state: child_state.ChildState
    # The trigger hops, in execution order, from the verifying definition's
    # immediate callee down to the destroying action must remain available for
    # diagnostics without copying every earlier hop during propagation.
    propagation: PropagationHistory | None = None

    def append(self, contract: DestructionContract):
        """Add a particle's Destruction Contract to this collection."""
        self.particles.append(contract)
        self.positions.add(contract.position_in_child_state)

    def child_occupancy(
        self, contract: DestructionContract, position: tuple[str, ...]
    ) -> position_occupancy.ChildOccupancy | None:
        """Look up occupancy relative to this contract's destroyed particle."""
        return self.child_state.get((*contract.position_in_child_state, *position))

    def occupied_child_state_position_or_nearest_occupied_parent(
        self,
        contract: DestructionContract,
        position: tuple[str, ...],
    ) -> tuple[str, ...] | None:
        """Return the position or its nearest occupied parent in the Child State."""
        # TODO: Investigate whether projects with many contributed Destructor
        # requirements repeat enough Child State parent-position lookups to justify
        # caching or indexing them without an excessive memory cost.
        for depth in range(len(position), 0, -1):
            candidate_position = position[:depth]
            occupancy = self.child_occupancy(contract, candidate_position)
            if (
                occupancy is not None
                and occupancy.state
                == position_occupancy.PositionOccupancyState.OCCUPIED
            ):
                return candidate_position
        return None

    def propagation_steps(self) -> Iterator[PropagationStep]:
        """Iterate from the immediate callee to the destroying action."""
        if self.propagation is not None:
            yield from self.propagation


@dataclass(frozen=True, slots=True)
class Destructor:
    """One destructor paired with the position on which it triggers."""

    destructor: ast.GlobalTypedNameReference
    position: ast.PositionReference
    origin_position: ast.PositionReference

    def action_assignment(self) -> ActionAssignment:
        """Return the destructor assignment used in diagnostics."""
        return ActionAssignment(
            quality=self.destructor,
            assigned_to_position_name=self.origin_position.typed_names[-1],
        )


@dataclass(frozen=True)
class ActionContract:
    """The automatically inferred requirements and guarantees for an action."""

    # TODO: Consider publishing requirements as a sequence. Callers only iterate
    # them; keyed lookup is needed during analysis, not after publication.
    requirements: dict[tuple[str, ...], PositionRequirement]
    guarantees: dict[ast.ChainedNameTuple, PositionGuarantee]
    final_operations: list[FinalPositionOperation]
    # Callee contracts are referenced rather than folded in so that we don't
    # get unbounded memory growth from re-copying guarantees as we walk up a
    # call stack (and unbounded compute growth from having to iterate through
    # them and copy them).
    callees: list[CalleeContract]
    destruction_contracts: list[DestructionContracts]
    # TODO: Support triggering on chained names?
    trigger_position_name: str

    def requirements_in_caller(
        self, action_chain: ast.ActionReference
    ) -> list[PositionRequirementInCaller]:
        """Express every Position Requirement from the caller's perspective."""
        return [
            PositionRequirementInCaller(
                requirement=requirement,
                caller_position=requirement.position.in_caller(action_chain),
            )
            for requirement in self.requirements.values()
        ]
