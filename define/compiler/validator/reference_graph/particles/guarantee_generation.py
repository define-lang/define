"""Generate the Guarantees an action's contract makes about its contracted Positions."""

from __future__ import annotations

import typing

import msgspec

from define.compiler import ast, chained_name
from define.compiler.validator.reference_graph import (
    action_contract,
    position_occupancy,
)

if typing.TYPE_CHECKING:
    from define.compiler.validator.reference_graph.particles import (
        particle_info,
        particle_state_store,
    )


@typing.final
class GuaranteeGenerator:
    """Generates the Guarantees an action's contract makes about its contracted Positions."""

    def __init__(self, store: particle_state_store.ParticleStateStore):
        """Generate Guarantees from the particle state in ``store``."""
        self._store = store

    def contracted_position_guarantees(
        self,
        interface_names: tuple[ast.TypedName[ast.NameContent], ...],
        implied_quality_names: tuple[ast.GlobalTypedNameReference, ...],
        requirements: dict[
            chained_name.PositionReferenceTuple,
            action_contract.PositionOccupancyRequirement,
        ],
    ) -> dict[chained_name.PositionReferenceTuple, action_contract.PositionGuarantee]:
        """Collect and sort the guarantees for every contracted key that holds a particle or whose state the action changed."""
        include_names = {
            name.full_typed_name for name in (*interface_names, *implied_quality_names)
        }

        guarantees: list[
            tuple[
                chained_name.PositionReferenceTuple, action_contract.PositionGuarantee
            ]
        ] = []
        for key, state in self._store.positions_with_state():
            if not _is_contracted(key, include_names):
                continue
            guarantee = self._guarantee_for_key(key, state, requirements)
            if guarantee is not None:
                guarantees.append((key, guarantee))

        # Parent-before-child ordering: Our first sort is by the key length
        # (the number of names in a chain). To understand why this is necessary,
        # imagine we do this:
        #
        #   move position<item> to position<dest>.
        #   create a particle in position<dest>::position</child>.
        #
        # We have to process the move from item to dest first, to understand
        # that what's in dest is the particle that was originally in
        # item. Only _then_ should we process the creation in position</child>,
        # so that we understand that we are creating a particle in a child
        # of what was originally in "item." Sorting by key length guarantees this
        # property.
        #
        # Within the same key length, sorting by caused_by reports a
        # Destructor's forbidden Guarantees in source order. A caller takes out
        # every particle that moved before applying any Guarantee, so applying
        # them does not depend on this order.
        guarantees.sort(key=_guarantee_order)
        return dict(guarantees)

    def published_guarantees(
        self,
        action: ast.GlobalTypedName[ast.GlobalNameContent[ast.Fqun | None]],
        own_guarantees: dict[
            chained_name.PositionReferenceTuple, action_contract.PositionGuarantee
        ],
        on_destruction: dict[
            chained_name.PositionReferenceTuple, action_contract.OnDestruction
        ],
    ) -> list[action_contract.GuaranteedPosition]:
        """Return the Guarantees an action's contract publishes, with what it left below each particle it created in that particle's Guarantee."""
        action_chain = chained_name.action((action.full_typed_name,))
        published: list[action_contract.GuaranteedPosition] = []
        # What the action left in the child positions of each particle it
        # created, built before the particle's own Guarantee.
        left_below: dict[
            chained_name.PositionReferenceTuple,
            dict[str, action_contract.ParticleLeftBelow],
        ] = {}
        for key, own_guarantee in reversed(own_guarantees.items()):
            guarantee = self._with_left_in_child_positions(
                action, key, own_guarantee, left_below
            )
            position = chained_name.in_caller(action_chain, key)
            parent_position = chained_name.parent_position(key)
            if parent_position is not None and isinstance(
                own_guarantees.get(parent_position),
                action_contract.OccupiedByNewGuarantee,
            ):
                # Child positions of a new particle are empty unless
                # something is in them.
                if isinstance(guarantee, action_contract.EmptyGuarantee):
                    continue
                # A particle from the caller is always published as its own
                # Guarantee, so the caller places it when it applies them.
                if isinstance(
                    guarantee,
                    (
                        action_contract.OccupiedByNewGuarantee,
                        action_contract.ErrorGuarantee,
                    ),
                ):
                    left_below.setdefault(parent_position, {})[key[-1]] = (
                        _particle_left_below(guarantee, position, on_destruction)
                    )
                    continue
            published.append(action_contract.GuaranteedPosition(position, guarantee))
        published.reverse()
        return published

    def _with_left_in_child_positions(
        self,
        action: ast.GlobalTypedName[ast.GlobalNameContent[ast.Fqun | None]],
        key: chained_name.PositionReferenceTuple,
        guarantee: action_contract.PositionGuarantee,
        left_below: dict[
            chained_name.PositionReferenceTuple,
            dict[str, action_contract.ParticleLeftBelow],
        ],
    ) -> action_contract.PositionGuarantee:
        """Return ``guarantee``, the action's Guarantee for ``key``, with what the action left in the child positions of a particle it created there."""
        if not isinstance(guarantee, action_contract.OccupiedByNewGuarantee):
            return guarantee
        particles = left_below.pop(key, None)
        if particles is not None:
            left = action_contract.ChildPositionParticles(action, particles)
        else:
            # What a callee left there and this action never expanded goes on
            # as the callee published it.
            left = self._store.unexpanded_child_positions(key)
        return msgspec.structs.replace(guarantee, left_in_child_positions=left)

    def _is_below_starting_particle(
        self, key: chained_name.PositionReferenceTuple
    ) -> bool:
        """Return whether the particle this position is a child position of is the one that was there when the action started."""
        # A requirement is about the particle the caller passed. A different
        # particle in the parent position has its own child positions.
        parent_position = chained_name.parent_position(key)
        if parent_position is None:
            return True
        parent_particle = self._store.occupant_or_none(parent_position)
        return (
            parent_particle is not None
            and parent_particle.from_caller
            and parent_particle.origin_position.canonical_chained_name_tuple
            == parent_position
        )

    def _guarantee_for_key(
        self,
        key: chained_name.PositionReferenceTuple,
        state: particle_state_store.PositionState,
        requirements: dict[
            chained_name.PositionReferenceTuple,
            action_contract.PositionOccupancyRequirement,
        ],
    ) -> action_contract.PositionGuarantee | None:
        """Build a guarantee describing ``state``, the state of ``key``, or None for an empty position the action left in the state it found it in."""
        if state.has_error:
            return action_contract.ErrorGuarantee()

        info = state.particle
        if info is not None:
            if not info.from_caller:
                return action_contract.OccupiedByNewGuarantee(
                    qualities=info.qualities,
                    origin_position=info.origin_position,
                    caused_by=info.last_position,
                    value_effect=typing.cast(
                        "particle_info.ParticleValueState", info.value_state
                    ),
                )
            # Every particle from the caller gets a Guarantee, even one the
            # action never touched, including the trigger particle. Its
            # parent position may hold a different particle than when the
            # action started, and the caller has to know where it is.
            #
            # TODO: Should we simply require people to always touch the trigger
            # position? It eliminates a lot of "more than one way to do it."
            return action_contract.OccupiedByExistingGuarantee(
                origin_position=info.origin_position,
                caused_by=info.last_position,
                value_effect=info.value_effect(),
            )

        # positions_with_state returns an unoccupied Position without error
        # state only when it is known to be empty.
        caused_by = typing.cast("ast.PositionReference", state.emptied_by)
        requirement = requirements.get(key)
        if (
            requirement is not None
            and requirement.required_state
            == position_occupancy.PositionOccupancyState.EMPTY
            and self._is_below_starting_particle(key)
        ):
            # The position was required to be empty when this action started,
            # and it is empty again.
            return None
        return action_contract.EmptyGuarantee(
            caused_by=caused_by,
        )


def _particle_left_below(
    guarantee: action_contract.OccupiedByNewGuarantee | action_contract.ErrorGuarantee,
    position: chained_name.PositionReferenceTuple,
    on_destruction: dict[
        chained_name.PositionReferenceTuple, action_contract.OnDestruction
    ],
) -> action_contract.ParticleLeftBelow:
    destruction = on_destruction.get(position, action_contract.OnDestruction.NOTHING)
    return action_contract.ParticleLeftBelow(
        guarantee=guarantee,
        on_destruction=destruction,
        guaranteed_particle_destructors_position=(
            position
            if destruction == action_contract.OnDestruction.RUN_DESTRUCTORS
            else None
        ),
    )


def _guarantee_order(
    item: tuple[chained_name.PositionReferenceTuple, action_contract.PositionGuarantee],
) -> tuple[int, int, int]:
    key, guarantee = item
    if not isinstance(
        guarantee,
        (
            action_contract.EmptyGuarantee,
            action_contract.OccupiedByExistingGuarantee,
            action_contract.OccupiedByNewGuarantee,
        ),
    ):
        return len(key), -1, -1
    location = guarantee.caused_by.location
    return len(key), location.line, location.column


def _is_contracted(
    key: chained_name.ChainedNameTuple, contracted_names: set[str]
) -> bool:
    # A callee's interface positions are visible only to the action that
    # triggered it, and must be empty when that action ends. An action that
    # leaves a particle in one is reported for it, and its callers never see
    # the particle.
    if any(chained_name.is_action_key(name) for name in key):
        return False
    # Any position that starts with a global is contracted, even if it was updated
    # by an implied action and we can't see it directly.
    return key[0] in contracted_names or chained_name.starts_with_global(key)
