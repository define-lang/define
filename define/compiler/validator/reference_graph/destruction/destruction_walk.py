"""Find the particles a Simultaneous Transitive Destruction destroys that one action knows about."""

from __future__ import annotations

import typing

import msgspec

from define.compiler import chained_name
from define.compiler.validator.reference_graph import (
    action_contract,
    position_occupancy,
    quality_assignment,
)
from define.compiler.validator.reference_graph.destruction import (
    destroyed_particles,
    destruction_contract,
)
from define.compiler.validator.reference_graph.particles import particle_info

if typing.TYPE_CHECKING:
    from define.compiler import ast
    from define.compiler.data_structures import typed_name_dict
    from define.compiler.validator import validation_result
    from define.compiler.validator.reference_graph import (
        reference_graph_validation_state,
    )
    from define.compiler.validator.reference_graph.particles import (
        particle_tracker,
    )


class DestructionRoot(msgspec.Struct, frozen=True):
    """A destroyed particle that one action walks a destruction from."""

    # From this action's perspective.
    position: ast.PositionReference
    particle: particle_info.ParticleInfo
    destruction_fact: destruction_contract.DestructionFact
    # The particle's name in the destruction's Child State.
    position_in_child_state: chained_name.ChainedNameTuple
    # The Destructors on the particle that an action below this one validated.
    validated_destructors: quality_assignment.QualityAssignments


class CalleeStateAtDestruction(msgspec.Struct, frozen=True):
    """The state at the moment of one callee destruction: what the callee and the actions below it recorded, completed with what this action knows."""

    callee_contracts: action_contract.DestructionContracts
    # The callee's Child State, completed with what this action knows.
    child_state: action_contract.ChildState
    # One for each particle of the callee's Destruction Contracts that this
    # action still has.
    contracted_roots: list[DestructionRoot]
    # The caller's particles at the moment of destruction, by Child State
    # position, which can differ from where the caller has them now when the
    # callee moved them.
    caller_particles: dict[chained_name.ChainedNameTuple, particle_info.ParticleInfo]
    # This action's trigger of the callee.
    trigger: action_contract.PropagationHistory

    def callee_destroys(
        self, position_in_child_state: chained_name.ChainedNameTuple
    ) -> bool:
        """Return whether the callee or an action below it destroys the particle in ``position_in_child_state``."""
        # The callee destroys the particle of each of its Destruction
        # Contracts, and every particle whose occupancy it recorded.
        return (
            position_in_child_state in self.callee_contracts.positions
            or self.callee_contracts.child_state.occupancy.get(position_in_child_state)
            is not None
        )

    def another_contract_starts_at(
        self, position_in_child_state: chained_name.ChainedNameTuple
    ) -> bool:
        """Return whether a Destruction Contract of this destruction starts at ``position_in_child_state``."""
        return position_in_child_state in self.callee_contracts.positions

    def records_empty(
        self, position_in_child_state: chained_name.ChainedNameTuple
    ) -> bool:
        """Return whether ``position_in_child_state`` was empty at the moment of destruction."""
        occupancy = self.child_state.occupancy.get(position_in_child_state)
        return (
            occupancy is not None
            and occupancy.state == position_occupancy.PositionOccupancyState.EMPTY
        )

    def caller_particle_at(
        self, position_in_child_state: chained_name.ChainedNameTuple
    ) -> particle_info.ParticleInfo | None:
        """Return the particle this action had at ``position_in_child_state`` at the moment of destruction, if it had one."""
        return self.caller_particles.get(position_in_child_state)

    def position_in_caller(
        self,
        position: ast.PositionReference,
        position_in_child_state: chained_name.ChainedNameTuple,
    ) -> ast.PositionReference:
        """Return where the position that ``position`` names at the moment of destruction was when this action triggered the callee."""
        # A callee can move a particle from this action below another one, so
        # the nearest contracted particle above the position decides where it
        # was.
        nearest: DestructionRoot | None = None
        for root in self.contracted_roots:
            start = root.position_in_child_state
            if position_in_child_state[: len(start)] == start and (
                nearest is None or len(start) > len(nearest.position_in_child_state)
            ):
                nearest = root
        # Every particle a destruction destroys is at or below a contracted one.
        nearest = typing.cast("DestructionRoot", nearest)
        names_below = len(position_in_child_state) - len(
            nearest.position_in_child_state
        )
        if names_below == 0:
            return nearest.position
        return nearest.position.with_position_suffix(
            *position.typed_names[-names_below:]
        )


class DestructorOnDestroyedParticle(msgspec.Struct, frozen=True):
    """A Destructor on a destroyed particle that this action is the lowest to know, with the contract it is triggered under."""

    # From this action's perspective.
    position: ast.PositionReference
    particle: particle_info.ParticleInfo
    contract: action_contract.ActionContract
    # From this action's perspective.
    action_chain: ast.ActionReference


class WalkedDestruction(msgspec.Struct):
    """What walking a destruction from one DestructionRoot finds."""

    # This action's part of destroying the particles the walk found.
    contribution: destruction_contract.DestructionContribution = msgspec.field(
        default_factory=destruction_contract.DestructionContribution
    )
    # Parents first, and in quality order on each particle.
    destructors: list[DestructorOnDestroyedParticle] = msgspec.field(
        default_factory=list
    )


@typing.final
class DestructionWalker:
    """Finds the particles that destructions destroy and that one action knows about."""

    def __init__(
        self,
        tracker: particle_tracker.ParticleTracker,
        definition_results: typed_name_dict.TypedNameDict[
            ast.GlobalTypedName[ast.GlobalNameContent[ast.Fqun | None]],
            validation_result.DefinitionValidationResult,
        ],
        validation_state: reference_graph_validation_state.ReferenceGraphValidationState,
    ):
        """Walk destructions in the particle state ``tracker`` holds."""
        self._destroyed_particles = destroyed_particles.DestroyedParticles(
            tracker, definition_results
        )
        self._validation_state = validation_state

    def walk(
        self, root: DestructionRoot, state: CalleeStateAtDestruction | None
    ) -> WalkedDestruction:
        """Find the particles that destroying ``root`` destroys and that this action knows about, with this action's part of destroying them.

        ``state`` is what the callee and the actions below it knew about the
        destruction, or None when this action is the destroyer.
        """
        return _Walk(
            self._destroyed_particles, self._validation_state, root, state
        ).walk()


@typing.final
class _Walk:
    """One walk of a destruction from one DestructionRoot."""

    def __init__(
        self,
        destroyed_particles: destroyed_particles.DestroyedParticles,
        validation_state: reference_graph_validation_state.ReferenceGraphValidationState,
        root: DestructionRoot,
        state: CalleeStateAtDestruction | None,
    ):
        """Walk from ``root``, with ``state`` None when this action is the destroyer."""
        self._destroyed_particles = destroyed_particles
        self._validation_state = validation_state
        self._root = root
        self._state = state
        self._is_destroyer = state is None

    def walk(self) -> WalkedDestruction:
        """Find what destroying the root destroys and that this action knows about."""
        walked = WalkedDestruction()
        self._add_particle(
            self._root.position,
            self._root.particle,
            self._root.position_in_child_state,
            walked,
        )
        return walked

    def _add_particle(
        self,
        position: ast.PositionReference,
        particle: particle_info.ParticleInfo,
        position_in_child_state: chained_name.ChainedNameTuple,
        walked: WalkedDestruction,
    ):
        """Add ``particle``, in ``position``, and every particle in its transitive child positions to ``walked``."""
        names_below_root = position.typed_names[len(self._root.position.typed_names) :]
        destruction_fact = _destruction_fact(self._root, names_below_root)
        # Only an action below this one can have validated Destructors, and
        # only on the particle its contract is for.
        validated_destructors = (
            quality_assignment.EMPTY_QUALITY_ASSIGNMENTS
            if names_below_root
            else self._root.validated_destructors
        )
        # A particle keeps its own qualities across Moves, so its qualities, not
        # the current position's constraints, decide what is below it.
        child_names, all_destructors = (
            self._destroyed_particles.child_names_and_destructors(
                particle.qualities.assignments
            )
        )
        destructors = [
            destructor
            for destructor in all_destructors
            if not validated_destructors.has_quality(destructor)
        ]
        self._add_destructors(position, particle, destructors, walked)
        for names in child_names:
            self._add_child(position, particle, position_in_child_state, names, walked)
        # A particle from the caller needs its own contract even when the
        # particle above it was created here: higher callers may know more
        # Destructors on it.
        if particle.source is particle_info.ParticleSource.CALLER:
            self._add_destruction_contract(
                particle,
                destruction_fact,
                position_in_child_state,
                _with_destructors(validated_destructors, destructors),
                walked,
            )
        if self._this_action_destroys(position_in_child_state):
            self._add_destroyed_position(position, destruction_fact, walked)

    def _add_destructors(
        self,
        position: ast.PositionReference,
        particle: particle_info.ParticleInfo,
        destructors: list[ast.GlobalTypedNameReference],
        walked: WalkedDestruction,
    ):
        """Add ``destructors``, the Destructors on ``particle`` in ``position`` that this action is the lowest to know, to ``walked``."""
        for destructor in destructors:
            contract = self._validation_state.get_contract_or_none(destructor)
            # A circular reference, already reported, leaves a Destructor's
            # contract unpublished.
            if contract is None:
                continue
            action_chain = position.with_action_suffix(destructor)
            walked.destructors.append(
                DestructorOnDestroyedParticle(
                    position=position,
                    particle=particle,
                    contract=contract,
                    action_chain=action_chain,
                )
            )
            walked.contribution.work.destructors.append(
                self._as_named_in_known_destruction_work(action_chain)
            )

    def _add_child(
        self,
        parent_position: ast.PositionReference,
        parent_particle: particle_info.ParticleInfo,
        parent_in_child_state: chained_name.ChainedNameTuple,
        names: tuple[ast.TypedNameReference, ...],
        walked: WalkedDestruction,
    ):
        """Add what destroying ``parent_particle`` destroys in its child position ``names`` to ``walked``."""
        position = parent_position.with_position_suffix(*names)
        found = self._particle_to_destroy_or_destructors_call_at(
            position, parent_particle
        )
        if found is None:
            return
        if isinstance(found, destruction_contract.RunGuaranteedParticleDestructors):
            walked.contribution.work.guaranteed_particle_destructors.append(
                msgspec.structs.replace(
                    found,
                    position=self._as_named_in_known_destruction_work(found.position),
                )
            )
            return
        position_in_child_state = chained_name.with_suffix(
            parent_in_child_state, *(name.full_typed_name for name in names)
        )
        # Another contract's walk covers the particles below it, and nothing
        # was destroyed below a position that was empty at the moment of
        # destruction.
        if self._state is not None and (
            self._state.another_contract_starts_at(position_in_child_state)
            or self._state.records_empty(position_in_child_state)
        ):
            return
        self._add_particle(position, found, position_in_child_state, walked)

    @staticmethod
    def _add_destruction_contract(
        particle: particle_info.ParticleInfo,
        destruction_fact: destruction_contract.DestructionFact,
        position_in_child_state: chained_name.ChainedNameTuple,
        validated_destructors: quality_assignment.QualityAssignments,
        walked: WalkedDestruction,
    ):
        """Add the Destruction Contract of ``particle``, which is from the caller, with ``validated_destructors``, every Destructor on it that this action or one below it validates."""
        walked.contribution.destruction_contracts.append(
            destruction_contract.DestructionContract(
                destruction_fact=destruction_fact,
                contracted_position=particle.origin_position,
                position_in_child_state=position_in_child_state,
                validated_destructors=validated_destructors,
            )
        )

    def _this_action_destroys(
        self, position_in_child_state: chained_name.ChainedNameTuple
    ) -> bool:
        """Return whether no action below this one destroys the particle in ``position_in_child_state``, so that destroying it is this action's work."""
        return self._state is None or not self._state.callee_destroys(
            position_in_child_state
        )

    def _add_destroyed_position(
        self,
        position: ast.PositionReference,
        destruction_fact: destruction_contract.DestructionFact,
        walked: WalkedDestruction,
    ):
        """Add destroying the particle in ``position`` to this action's work in ``walked``."""
        # A particle's children must remain accessible until their own Destroy
        # executes, so child positions come first.
        walked.contribution.work.positions.append(
            destruction_contract.DestroyedPosition(
                self._as_named_in_known_destruction_work(position),
                destruction_fact.destroyed_position_in_destroyer,
            )
        )

    def _as_named_in_known_destruction_work[Reference: ast.ChainedName](
        self, reference: Reference
    ) -> Reference:
        """Return ``reference``, a chained name from this action's perspective at or below the root's particle, as this action's KnownDestructionWork names it."""
        # A destroyer's work is in its own step, which names positions from
        # its perspective. Any other action's work is in the method its callee
        # calls, which names positions from the perspective of the particle the
        # callee destroyed.
        if self._is_destroyer:
            return reference
        return reference.without_prefix(self._root.position)

    def _particle_to_destroy_or_destructors_call_at(
        self,
        position: ast.PositionReference,
        parent_particle: particle_info.ParticleInfo,
    ) -> (
        particle_info.ParticleInfo
        | destruction_contract.RunGuaranteedParticleDestructors
        | None
    ):
        """Return what destroying ``parent_particle`` finds in ``position``, one of its child positions: the particle to destroy there, expanding what a callee left when it has to be expanded, the call that runs the Destructors of what a callee left, or None when nothing there needs anything."""
        found = self._destroyed_particles.particle_or_unexpanded_destruction_at(
            position, parent_particle
        )
        if found is None or isinstance(found, particle_info.ParticleInfo):
            return found
        if found == action_contract.OnDestruction.NOTHING:
            return None
        if found == action_contract.OnDestruction.EXPAND:
            # Reading the particle expands what the callee left there. Only a
            # particle has to be expanded to be destroyed, and the particle above
            # it is not in error.
            return typing.cast(
                "particle_info.ParticleInfo",
                self._destroyed_particles.particle_destroyed_at(position),
            )
        return typing.cast(
            "destruction_contract.RunGuaranteedParticleDestructors", found
        )


def _destruction_fact(
    root: DestructionRoot, names_below_root: tuple[ast.TypedNameReference, ...]
) -> destruction_contract.DestructionFact:
    """Return the Destruction Fact of the particle ``names_below_root`` below ``root``."""
    # No names below the root means this is the root's own particle.
    if not names_below_root:
        return root.destruction_fact
    return msgspec.structs.replace(
        root.destruction_fact,
        # The root can have a different name in the destroyer, but the names
        # below it are the same there.
        destroyed_position_in_destroyer=root.destruction_fact.destroyed_position_in_destroyer.with_position_suffix(
            *names_below_root
        ),
    )


def _with_destructors(
    validated_destructors: quality_assignment.QualityAssignments,
    destructors: list[ast.GlobalTypedNameReference],
) -> quality_assignment.QualityAssignments:
    """Return ``validated_destructors`` with ``destructors`` added."""
    # Particles whose Destructors were all validated below share the same
    # assignments.
    if not destructors:
        return validated_destructors
    return quality_assignment.QualityAssignments(
        (*validated_destructors.assignments, *destructors)
    )
