"""Action contract types: automatically inferred requirements and guarantees."""

from __future__ import annotations

import enum
from dataclasses import dataclass
from functools import cached_property

from define.compiler import ast


class PositionOccupancyState(enum.Enum):
    """The occupancy state of an interface position."""

    EMPTY = enum.auto()
    OCCUPIED = enum.auto()
    UNKNOWN = enum.auto()


@dataclass(frozen=True, slots=True)
class ChildOccupancy:
    """A child position's occupancy, plus where its particle was filled when occupied."""

    state: PositionOccupancyState
    # Where the occupying particle was last placed, so a caller that resolves an
    # empty-requirement violation from this record (rather than from its own
    # tracker) can still report the fill site. Only set when state is OCCUPIED.
    filled_at: ast.SourceLocation | None = None


# The empty and unknown states carry no fill site, so a single shared instance
# serves every position. OCCUPIED must be constructed with its own filled_at.
EMPTY_OCCUPANCY = ChildOccupancy(PositionOccupancyState.EMPTY)
UNKNOWN_OCCUPANCY = ChildOccupancy(PositionOccupancyState.UNKNOWN)


class PropagationKind(enum.Enum):
    """How a requirement reached a given step in its propagation chain."""

    # The deepest step in the chain: the definition's own body inferred the
    # requirement directly.
    DIRECT_INFERENCE = enum.auto()
    # The current definition's body destroyed a caller-passed particle,
    # firing a destructor; the destructor's requirements propagated up.
    DESTRUCTOR_CASCADE = enum.auto()
    # The current definition attached a destructor to a particle that a callee
    # later destroyed.
    DESTRUCTOR_ATTACHED = enum.auto()
    # The current definition's body triggered an action; the action's
    # requirements propagated up.
    ACTION_TRIGGER = enum.auto()
    # The current definition's body created a particle in a position
    # with an init block; the init block's requirements propagated up.
    INIT_BLOCK_TRIGGER = enum.auto()
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
    # The definition whose body did the thing this step describes (where
    # ``location`` points).
    enclosing_quality_name: str
    # For non-root steps: the quality (destructor / triggered action / position
    # whose init block ran) that the next step downward is inside.
    triggered_quality_name: str | None


@dataclass(frozen=True, slots=True)
class DestructorAttachment:
    """The position constraint that puts a destructor on the particle."""

    # The constraint line that attaches the destructor: the
    # `it has the action</D>.` line, or the directly-declared constraint whose
    # implication adds it.
    # TODO: When the destructor is added through implication, also explain how
    # this constraint line leads to the implied destructor.
    attached_at: ast.SourceLocation
    # The position whose constraints attach the destructor (the position the
    # particle was created in).
    position: ast.TypedName


@dataclass(frozen=True)
class PositionRequirement:
    """An automatically inferred requirement on a contracted position.

    A contracted position is an interface position, a child of an interface
    position, an implied quality, or a child of an implied quality.
    """

    required_state: PositionOccupancyState
    # The chained name at the line of source where this action inferred the
    # requirement.
    #
    # If this is a requirement imposed directly by this action,
    # this contains the full chained name used in the statement that imposed
    # the requirement (like `position<iface>::position</x>` for
    # `create a particle in position<iface>::position</x>.`)
    #
    # If this is a requirement that has been propagated from a called
    # action, then it contains only the prefix of the chain that is unique
    # within this action. For example, imagine we trigger an action via
    # `position<iface>::action</inner>::position<run>`, and it includes
    # a requirement on action</inner>::position<item>. This will contain
    # just `position<iface>::action</inner>` (which is why it is a ChainedName
    # and not a PositionReference).
    inferred_from: ast.ChainedName
    enclosing_quality: ast.QualityDefinition
    propagated_from: PositionRequirement | None = None
    destructor_attachment: DestructorAttachment | None = None

    def root_cause_quality(self) -> ast.QualityDefinition:
        """Return the quality definition that originally inferred this requirement."""
        current = self
        while current.propagated_from is not None:
            current = current.propagated_from
        return current.enclosing_quality

    def root_cause_quality_name(self) -> str:
        """Return the canonical name of the quality that originally inferred this requirement."""
        return self.root_cause_quality().typed_name.source_typed_name

    def full_propagation_position_chain(self) -> ast.PositionReference:
        """Get the full chained name composed by walking propagated_from."""
        if self.propagated_from is None:
            if not isinstance(self.inferred_from, ast.PositionReference):
                raise TypeError(
                    f"originating requirement's inferred_from must be a PositionReference, got {type(self.inferred_from).__name__}"
                )
            return self.inferred_from
        inner_full = self.propagated_from.full_propagation_position_chain()
        return inner_full.in_caller(self.inferred_from)

    def propagated_from_locations(self) -> list[ast.SourceLocation]:
        """Locations of intermediate propagation steps, ordered outer to inner."""
        locations: list[ast.SourceLocation] = []
        current = self.propagated_from
        while current is not None:
            locations.append(current.inferred_from.location)
            current = current.propagated_from
        return locations

    def propagation_chain(self) -> list[PropagationStep]:
        """Return the chain of propagation steps from this requirement down to its root cause."""
        chain: list[PropagationStep] = []
        current: PositionRequirement | None = self
        while current is not None:
            chain.extend(current._propagation_steps())
            current = current.propagated_from
        return chain

    def _propagation_steps(self) -> list[PropagationStep]:
        # The constraint that attaches the destructor is encountered before the
        # destruction it eventually causes, so it is listed first.
        steps: list[PropagationStep] = []
        if self.destructor_attachment is not None:
            steps.append(self._destructor_attachment_step(self.destructor_attachment))
        steps.append(self._propagation_step())
        return steps

    def _destructor_attachment_step(
        self, attachment: DestructorAttachment
    ) -> PropagationStep:
        if self.propagated_from is None:
            raise ValueError(
                "destructor_attachment requires a propagated_from requirement"
            )
        destructor = self.propagated_from.enclosing_quality
        return PropagationStep(
            location=attachment.attached_at,
            kind=PropagationKind.DESTRUCTOR_ATTACHED,
            enclosing_quality_name=attachment.position.full_typed_name,
            triggered_quality_name=destructor.typed_name.source_typed_name,
        )

    def _propagation_step(self) -> PropagationStep:
        enclosing_name = self.enclosing_quality.typed_name.source_typed_name
        if self.propagated_from is None:
            return PropagationStep(
                location=self.inferred_from.location,
                kind=PropagationKind.DIRECT_INFERENCE,
                enclosing_quality_name=enclosing_name,
                triggered_quality_name=None,
            )
        other_quality = self.propagated_from.enclosing_quality
        if isinstance(other_quality, ast.ActionDefinition):
            if other_quality.is_destructor:
                kind = PropagationKind.DESTRUCTOR_CASCADE
            else:
                kind = PropagationKind.ACTION_TRIGGER
        else:
            kind = PropagationKind.INIT_BLOCK_TRIGGER
        return PropagationStep(
            location=self.inferred_from.location,
            kind=kind,
            enclosing_quality_name=enclosing_name,
            triggered_quality_name=other_quality.typed_name.source_typed_name,
        )


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

    qualities: tuple[ast.GlobalTypedNameReference, ...]


@dataclass(frozen=True)
class UnknownGuarantee(PositionGuarantee):
    """The position's state could not be determined due to an error."""


GuaranteePair = tuple[tuple[str, ...], PositionGuarantee]


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
    verified_destructors: tuple[ast.GlobalTypedNameReference, ...]
    # True when destroyed_position_local was auto-destroyed at block end rather
    # than by an explicit destroy statement.
    is_auto_destruction: bool
    # The trigger hops, in execution order, from the verifying definition's
    # immediate callee down to the destroying action. One step is prepended each
    # time the contract is re-recorded through a pass-through action that did not
    # itself verify the destructor, so a destructor verified many hops above its
    # destruction can render every hop in between.
    trigger_chain: tuple[PropagationStep, ...] = ()

    @cached_property
    def verified_destructor_names(self) -> frozenset[str]:
        """The full typed names of the destructors the recorder already verified."""
        return frozenset(
            quality.full_typed_name for quality in self.verified_destructors
        )


@dataclass(frozen=True)
class ActionStatementsBlockContract:
    """Base contract for any block containing action statements."""

    requirements: dict[tuple[str, ...], PositionRequirement]
    guarantees: list[GuaranteePair]
    destruction_contracts: list[DestructionContract]


@dataclass(frozen=True)
class ActionContract(ActionStatementsBlockContract):
    """The automatically inferred requirements and guarantees for an action."""

    # TODO: Support triggering on chained names?
    trigger_position_name: str


@dataclass(frozen=True)
class PositionInitBlockContract(ActionStatementsBlockContract):
    """Contract for a position initialization block."""
