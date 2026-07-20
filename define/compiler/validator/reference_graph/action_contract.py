"""Action contract types: automatically inferred requirements and guarantees."""

from __future__ import annotations

import enum
import typing
from dataclasses import dataclass, field

if typing.TYPE_CHECKING:
    from define.compiler import ast
    from define.compiler.validator.reference_graph import quality_assignment


class PositionOccupancyState(enum.Enum):
    """The occupancy state of an interface position."""

    EMPTY = enum.auto()
    OCCUPIED = enum.auto()
    ERROR = enum.auto()


@dataclass(frozen=True, slots=True)
class ChildOccupancy:
    """A child position's occupancy, plus where its particle was filled when occupied."""

    state: PositionOccupancyState
    # Where the occupying particle was last placed, so a caller that resolves an
    # empty-requirement violation from this record (rather than from its own
    # tracker) can still report the fill site. Only set when state is OCCUPIED.
    filled_at: ast.SourceLocation | None = None


# The empty and error states carry no fill site, so a single shared instance
# serves every position. OCCUPIED must be constructed with its own filled_at.
EMPTY_OCCUPANCY = ChildOccupancy(PositionOccupancyState.EMPTY)
ERROR_OCCUPANCY = ChildOccupancy(PositionOccupancyState.ERROR)


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
    # One assigned quality implied another quality.
    QUALITY_IMPLIED = enum.auto()
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


@dataclass(frozen=True)
class ActionAssignment:
    """An action's assignment to a particle at a position."""

    quality_assignment: quality_assignment.QualityAssignment
    assigned_to_position_name: ast.TypedName

    def propagation_chain(self) -> list[PropagationStep]:
        """Return the assignment and implication steps in source order."""
        assignment_path = self.quality_assignment.assignment_path()
        direct_assignment = assignment_path[0]
        steps = [
            PropagationStep(
                location=direct_assignment.quality.location,
                kind=PropagationKind.QUALITY_ASSIGNED,
                enclosing_quality_name=self.assigned_to_position_name.full_typed_name,
                triggered_quality_name=direct_assignment.quality.full_typed_name,
            )
        ]
        previous_assignment = direct_assignment
        for implied_assignment in assignment_path[1:]:
            steps.append(
                PropagationStep(
                    location=implied_assignment.quality.location,
                    kind=PropagationKind.QUALITY_IMPLIED,
                    enclosing_quality_name=previous_assignment.quality.full_typed_name,
                    triggered_quality_name=implied_assignment.quality.full_typed_name,
                )
            )
            previous_assignment = implied_assignment
        return steps


@dataclass(frozen=True)
class PositionRequirement:
    """An automatically inferred requirement on a contracted position.

    A contracted position is an interface position, a child of an interface
    position, an implied quality, or a child of an implied quality.
    """

    required_state: PositionOccupancyState
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
                chain.extend(current.action_assignment.propagation_chain())
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
        elif other_action.is_constructor:
            kind = PropagationKind.CONSTRUCTOR_TRIGGER
        else:
            kind = PropagationKind.ACTION_TRIGGER
        return PropagationStep(
            location=self.inferred_at,
            kind=kind,
            enclosing_quality_name=enclosing_name,
            triggered_quality_name=other_action.typed_name.source_typed_name,
        )


@dataclass(frozen=True)
class PositionGuarantee:
    """An automatically inferred guarantee about an interface position after action completion."""

    caused_by: ast.PositionReference
    # Every position operated on by the Particle Operation that produced this
    # guarantee. Operation-graph construction needs the full set to apply the
    # Empty Rule after the guarantee is expressed from a caller's perspective.
    # Canonical chained-name keys are stored instead of PositionReference objects
    # because expressing them from each caller's perspective only requires tuple
    # composition; source locations and written name forms would be unused.
    # TODO: Consider a more holistic combination of ParticleTracker and
    # OperationGraph responsibilities so operation-graph information does not
    # have to travel through validator guarantees. Moving this field alone would
    # require duplicating the lazy nested-guarantee propagation and its
    # caller-perspective conversions for parallel operation-graph metadata.
    operation_positions: tuple[tuple[str, ...], ...] = field(
        compare=False, kw_only=True
    )


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


GuaranteePair = tuple[tuple[str, ...], PositionGuarantee]


@dataclass(frozen=True, slots=True)
class Guarantees:
    """An action block's own guarantees plus references to its callees' guarantees."""

    own: list[GuaranteePair]
    # Nested guarantees are referenced rather than folded in so that we don't
    # get unbounded memory growth from re-copying guarantees as we walk up a
    # call stack (and unbounded compute growth from having to iterate through
    # them and copy them).
    nested: tuple[NestedGuarantees, ...]


@dataclass(frozen=True, slots=True)
class NestedGuarantees:
    """A callee's guarantees, referenced at the position that triggers it.

    ```triggered_action``` is the chained name path at the actual trigger
    site, for the triggered action.
    """

    triggered_action: tuple[str, ...]
    guarantees: Guarantees


@dataclass(frozen=True)
class DestructionContract:
    """Records that an action destroyed a caller-passed particle in a contracted position (DLP 41).

    Callers higher in the stack use this to verify destructors they attach
    that the destroying action could not see.
    """

    # The contracted position whose particle was destroyed (its contracted
    # origin), as a chained name within the action providing this DestructionContract.
    destroyed_position_contracted: ast.PositionReference
    # The position the destroying action actually destroyed, as a chained name
    # within that action: the Destruction Statement target (or the local position
    # that was auto-destroyed at the end of a block). Carries the DESTRUCTOR_CASCADE
    # step location and, for auto-destruction, the local position name.
    destroyed_position_local: ast.PositionReference
    # The occupancy of every transitive child position immediately before
    # destruction, keyed by canonical chained-name tuple relative to the
    # destroyed particle (the suffix that you would put after the particle's
    # position).
    child_state: dict[tuple[str, ...], ChildOccupancy]
    # The action that physically performed the destruction.
    destroying_action: ast.GlobalTypedName
    # Destructors we have already verified, so consumers do not re-verify.
    verified_destructors: quality_assignment.QualityAssignments
    # True when destroyed_position_local was auto-destroyed at block end rather
    # than by an explicit destroy statement.
    is_auto_destruction: bool
    # The trigger hops, in execution order, from the verifying definition's
    # immediate callee down to the destroying action. One step is prepended each
    # time the contract is re-recorded through a pass-through action that did not
    # itself verify the destructor, so a destructor verified many hops above its
    # destruction can render every hop in between.
    trigger_chain: tuple[PropagationStep, ...] = ()


@dataclass(frozen=True, slots=True)
class CascadeDestructor:
    """One destructor in a destruction cascade, paired with the position it fires on."""

    # Used only to explain the destructor assignment in diagnostics. This is the
    # preferred assignment, so a direct constraint replaces an earlier implied
    # assignment here.
    assignment: quality_assignment.QualityAssignment
    position: ast.PositionReference
    origin_position: ast.PositionReference

    def action_assignment(self) -> ActionAssignment:
        """Return the destructor assignment used in diagnostics."""
        return ActionAssignment(
            quality_assignment=self.assignment,
            assigned_to_position_name=self.origin_position.typed_names[-1],
        )


@dataclass(frozen=True)
class ActionContract:
    """The automatically inferred requirements and guarantees for an action."""

    requirements: dict[tuple[str, ...], PositionRequirement]
    guarantees: Guarantees
    destruction_contracts: list[DestructionContract]
    # TODO: Support triggering on chained names?
    trigger_position_name: str
