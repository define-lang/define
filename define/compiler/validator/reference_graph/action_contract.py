"""Action contract types: automatically inferred requirements and guarantees."""

from __future__ import annotations

import enum
import typing
from dataclasses import dataclass, field

import msgspec

from define.compiler import chained_name
from define.compiler.validator.reference_graph import position_occupancy
from define.compiler.validator.reference_graph.particles import particle_info

if typing.TYPE_CHECKING:
    from collections.abc import Iterator

    from define.compiler import ast
    from define.compiler.validator.reference_graph import quality_assignment
    from define.compiler.validator.reference_graph.destruction import child_state
    from define.compiler.validator.reference_graph.destruction import (
        destruction_contract as destruction_contract_types,
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


class PropagationStep(msgspec.Struct, frozen=True):
    """One step in a requirement's propagation chain, with its source location."""

    location: ast.SourceLocation
    kind: PropagationKind
    # The definition, quality, or position that performs or receives the event
    # described by this step (where ``location`` points).
    enclosing_quality_name: str
    # The quality triggered or assigned by an event involving two names; None
    # when the event only describes ``enclosing_quality_name``.
    triggered_quality_name: str | None


class PropagationHistory(msgspec.Struct, frozen=True, eq=False):
    """A shared sequence of Destruction Contract propagation steps."""

    step: PropagationStep
    previous: PropagationHistory | None

    def __iter__(self) -> Iterator[PropagationStep]:
        """Iterate from the immediate callee to the destroying action."""
        current: PropagationHistory | None = self
        while current is not None:
            yield current.step
            current = current.previous


class ActionAssignment(msgspec.Struct, frozen=True):
    """An action's assignment to a particle at a position."""

    quality: ast.GlobalTypedNameReference
    assigned_to_position_name: ast.TypedName[ast.NameContent]

    def propagation_step(self) -> PropagationStep:
        """Return the action's assignment step."""
        return PropagationStep(
            location=self.quality.location,
            kind=PropagationKind.QUALITY_ASSIGNED,
            enclosing_quality_name=self.assigned_to_position_name.full_typed_name,
            triggered_quality_name=self.quality.full_typed_name,
        )


class PositionRequirement(msgspec.Struct, frozen=True, kw_only=True):
    """An automatically inferred requirement on a contracted position.

    A contracted position is an interface position, a child of an interface
    position, an implied quality, or a child of an implied quality.
    """

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


class PositionOccupancyRequirement(PositionRequirement, frozen=True):
    """An automatically inferred occupancy requirement."""

    required_state: position_occupancy.PositionOccupancyState

    @property
    def requires_occupied(self) -> bool:
        """Whether this requirement requires an occupied position."""
        return self.required_state == position_occupancy.PositionOccupancyState.OCCUPIED


class ValueRequirement(PositionRequirement, frozen=True):
    """A contracted position must have a particle with a set value."""


class PositionRequirementInCaller[Requirement: PositionRequirement](
    msgspec.Struct, frozen=True
):
    """A callee's Position Requirement expressed from its caller's perspective."""

    requirement: Requirement
    caller_position: ast.PositionReference


class PositionGuarantee(msgspec.Struct, frozen=True):
    """An automatically inferred guarantee about an interface position after action completion."""


class EmptyGuarantee(PositionGuarantee, frozen=True):
    """The position is guaranteed to be empty after the action completes."""

    caused_by: ast.PositionReference


class OccupiedByExistingGuarantee(PositionGuarantee, frozen=True):
    """The position contains a particle passed into a contracted position.

    A None value_effect leaves the caller's value unchanged.
    """

    caused_by: ast.PositionReference
    origin_position: ast.PositionReference
    value_effect: particle_info.ParticleValueState | None = None


class OccupiedByNewGuarantee(PositionGuarantee, frozen=True):
    """The position contains a new particle created by the action."""

    caused_by: ast.PositionReference
    qualities: quality_assignment.QualityAssignments
    origin_position: ast.PositionReference
    value_effect: particle_info.ParticleValueState = (
        particle_info.ParticleValueState.UNSET
    )
    # What the action left in the particle's child positions, or None when
    # it left them all empty.
    left_in_child_positions: ChildPositionParticles | None = None


class ErrorGuarantee(PositionGuarantee, frozen=True):
    """The position's state could not be determined due to an error."""


class GuaranteedPosition(msgspec.Struct, frozen=True):
    """What an action leaves in one position that its caller always applies."""

    # From the perspective of a caller that triggers the action as one of its
    # implied actions. A caller that triggers the action through another
    # action reference puts that reference's parent positions in front.
    position: chained_name.PositionReferenceTuple
    guarantee: PositionGuarantee


class OnDestruction(enum.Enum):
    """What destroying a particle an action left below a particle it created takes, when the destroyer has not expanded it."""

    # Nothing runs. The destroyer forgets the particle.
    #
    # TODO: A compiled target with explicit memory management has to free a
    # forgotten particle. Give each action a generated method that destroys
    # what it left at a position, running any Destructors first and calling
    # the owning action's method for each particle below, so that a destroyer
    # frees what it never expanded without enumerating it.
    NOTHING = enum.auto()
    # Destructors run, and what the action left meets their requirements. The
    # destroyer runs them through the action's method for the position.
    RUN_DESTRUCTORS = enum.auto()
    # The destroyer has to expand the particle's entry and destroy the
    # particle and what is below it as it destroys its own particles.
    EXPAND = enum.auto()


class ParticleLeftBelow(msgspec.Struct, frozen=True):
    """What an action left in one child position of a particle it created, and what destroying it takes."""

    # ErrorGuarantee for a position whose state an error made unknown, so a
    # caller does not report cascading diagnostics below it.
    guarantee: OccupiedByNewGuarantee | ErrorGuarantee
    on_destruction: OnDestruction
    # The position whose method in the action that owns the map runs the
    # Destructors, named as GuaranteedPosition.position names positions for
    # that action. Set exactly when on_destruction is RUN_DESTRUCTORS.
    guaranteed_particle_destructors_position: (
        chained_name.PositionReferenceTuple | None
    ) = None


class ChildPositionParticles(msgspec.Struct, frozen=True):
    """What an action left in the child positions of one particle it created."""

    # Whose methods run the Destructors of these particles. A map an action
    # passes on from a callee without expanding it keeps the callee's.
    action: ast.GlobalTypedName[ast.GlobalNameContent[ast.Fqun | None]]
    # By child position name. Interface positions of actions on the particle
    # are never here: they are empty when the action ends.
    particles: dict[str, ParticleLeftBelow]

    def particle_left_below(self, names: tuple[str, ...]) -> ParticleLeftBelow | None:
        """Return what was left at the position ``names`` below the particle, or None when it is empty."""
        left: ParticleLeftBelow | None = None
        current: ChildPositionParticles | None = self
        for name in names:
            if current is None:
                return None
            left = current.particles.get(name)
            if left is None:
                return None
            # What is below a position with error state is unknown too.
            if isinstance(left.guarantee, ErrorGuarantee):
                return left
            current = left.guarantee.left_in_child_positions
        return left


class ChildState(msgspec.Struct, frozen=True):
    """Independent occupancy and value knowledge at destruction time."""

    occupancy: child_state.ChildStateStore[position_occupancy.ChildOccupancy]
    # Unknown values have no entry, so resolving a value only adds knowledge.
    values: child_state.ChildStateStore[particle_info.ParticleValueState]
    # For each position at or below the destroyed position that the
    # destroyer or one of its callers tracked, what callees left in its child
    # positions that was never expanded.
    unexpanded: dict[chained_name.ChainedNameTuple, ChildPositionParticles]

    def with_caller(
        self,
        occupancy: child_state.ChildOccupancyMap,
        values: child_state.ChildValueMap,
        unexpanded: dict[chained_name.ChainedNameTuple, ChildPositionParticles],
    ) -> ChildState:
        """Take ownership of additional caller knowledge without changing earlier facts."""
        if not occupancy and not values and not unexpanded:
            return self
        if unexpanded:
            unexpanded.update(self.unexpanded)
        else:
            unexpanded = self.unexpanded
        return ChildState(
            self.occupancy.with_caller(occupancy),
            self.values.with_caller(values),
            unexpanded,
        )

    def occupancy_at(
        self, position: chained_name.ChainedNameTuple
    ) -> position_occupancy.ChildOccupancy | None:
        """Return a position's destruction-time occupancy, including what callees left there that was never expanded, if it is known."""
        occupancy = self.occupancy.get(position)
        if occupancy is not None:
            return occupancy
        is_below_new_particle, left = self._left_by_callees(position)
        if left is None:
            # The child positions of a new particle are empty until something
            # fills them.
            return position_occupancy.EMPTY_OCCUPANCY if is_below_new_particle else None
        if isinstance(left.guarantee, ErrorGuarantee):
            return position_occupancy.ERROR_OCCUPANCY
        return position_occupancy.ChildOccupancy(
            position_occupancy.PositionOccupancyState.OCCUPIED,
            filled_at=left.guarantee.caused_by.location,
        )

    def value_at(
        self, position: chained_name.ChainedNameTuple
    ) -> particle_info.ParticleValueState | None:
        """Return a position's destruction-time value state, including what callees left there that was never expanded, if it is known."""
        value = self.values.get(position)
        if value is not None:
            return value
        _, left = self._left_by_callees(position)
        if (
            left is not None
            and isinstance(left.guarantee, OccupiedByNewGuarantee)
            and left.guarantee.qualities.value_type is not None
        ):
            return left.guarantee.value_effect
        return None

    def _left_by_callees(
        self, position: chained_name.ChainedNameTuple
    ) -> tuple[bool, ParticleLeftBelow | None]:
        """Return whether ``position`` is below a new particle whose map was never expanded, and what that map says is in it."""
        # A map stays on the nearest position above that was tracked.
        for length in range(len(position) - 1, -1, -1):
            prefix = chained_name.ChainedNameTuple(position[:length])
            particles = self.unexpanded.get(prefix)
            if particles is not None:
                return True, particles.particle_left_below(position[length:])
            if self.occupancy.get(prefix) is not None:
                break
        return False, None


class DestructionContract(msgspec.Struct, frozen=True):
    """Records that an action destroyed a caller-passed particle in a contracted position (DLP 41).

    Callers higher in the stack use this to verify destructors they attach
    that the destroying action could not see.
    """

    propagated_destruction: destruction_contract_types.PropagatedDestruction
    # The position in the shared snapshot stays fixed when a caller expresses
    # the particle's contracted origin from its own perspective.
    position_in_child_state: chained_name.ChainedNameTuple
    # Verification belongs to a particle, not just a quality: different child
    # particles can have the same Destructor assigned to them.
    verified_destructors: quality_assignment.QualityAssignments


@dataclass(frozen=True, slots=True)
class DestructionContracts:
    """Contracts for particles sharing destruction-time state and propagation history."""

    particles: list[DestructionContract] = field(default_factory=list, init=False)
    # Callers repeatedly need membership checks while verifying child positions.
    positions: set[chained_name.ChainedNameTuple] = field(
        default_factory=set, init=False
    )
    # Particles destroyed together share their destruction-time occupancy.
    child_state: ChildState
    # The trigger hops, in execution order, from the verifying definition's
    # immediate callee down to the destroying action must remain available for
    # diagnostics without copying every earlier hop during propagation.
    propagation: PropagationHistory | None = None

    def append(self, contract: DestructionContract):
        """Add a particle's Destruction Contract to this collection."""
        self.particles.append(contract)
        self.positions.add(contract.position_in_child_state)

    def child_occupancy(
        self, contract: DestructionContract, position: chained_name.ChainedNameTuple
    ) -> position_occupancy.ChildOccupancy | None:
        """Look up child state relative to this contract's destroyed particle."""
        return self.child_state.occupancy.get(
            chained_name.with_prefix(position, contract.position_in_child_state)
        )

    def propagation_steps(self) -> Iterator[PropagationStep]:
        """Iterate from the immediate callee to the destroying action."""
        if self.propagation is not None:
            yield from self.propagation


class Destructor(msgspec.Struct, frozen=True):
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


class ActionContract(msgspec.Struct, frozen=True):
    """The automatically inferred requirements and guarantees for an action."""

    occupancy_requirements: list[PositionOccupancyRequirement]
    value_requirements: list[ValueRequirement]
    # What the action leaves in each contracted position whose parent
    # position holds no particle it created, and in each position holding a
    # particle from its caller, parent positions before child positions. A
    # position it leaves in the state it found it in is left out. What it
    # left below the particles it created is in their Guarantees.
    guarantees: list[GuaranteedPosition]
    destruction_contracts: list[DestructionContracts]
    # TODO: Support triggering on chained names?
    trigger_position_name: str
    # The action's transitively implied qualities.
    implied_quality_names: frozenset[str]

    def occupancy_requirements_in_caller(
        self, action_chain: ast.ActionReference
    ) -> list[PositionRequirementInCaller[PositionOccupancyRequirement]]:
        """Express occupancy requirements from the caller's perspective."""
        return self._requirements_in_caller(self.occupancy_requirements, action_chain)

    def value_requirements_in_caller(
        self, action_chain: ast.ActionReference
    ) -> list[PositionRequirementInCaller[ValueRequirement]]:
        """Express value requirements from the caller's perspective."""
        return self._requirements_in_caller(self.value_requirements, action_chain)

    @staticmethod
    def _requirements_in_caller[Requirement: PositionRequirement](
        requirements: list[Requirement], action_chain: ast.ActionReference
    ) -> list[PositionRequirementInCaller[Requirement]]:
        result: list[PositionRequirementInCaller[Requirement]] = []
        for requirement in requirements:
            result.append(
                PositionRequirementInCaller(
                    requirement=requirement,
                    caller_position=requirement.position.in_caller(action_chain),
                )
            )
        return result
