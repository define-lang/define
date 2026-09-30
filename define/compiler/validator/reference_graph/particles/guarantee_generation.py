"""Generate the Guarantees an action's contract makes about its contracted Positions."""

from __future__ import annotations

import typing

from define.compiler import ast, chained_name
from define.compiler.validator.reference_graph import (
    action_contract,
    position_occupancy,
)
from define.compiler.validator.reference_graph.particles import particle_info

if typing.TYPE_CHECKING:
    from define.compiler.validator.reference_graph.particles import (
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
        *,
        is_destructor: bool = False,
    ) -> dict[chained_name.PositionReferenceTuple, action_contract.PositionGuarantee]:
        """Collect and sort the guarantees for every contracted key, excluding the ones _guarantee_for_key reports as no-ops."""
        include_names = {
            name.full_typed_name for name in (*interface_names, *implied_quality_names)
        }

        # generate_own_guarantees excludes keys that came only from our caleees.
        # generate_destructor_guarantees includes callee-derived keys.
        all_keys = self._store.keys_for_guarantees(include_callee_derived=is_destructor)

        guarantees: list[
            tuple[
                chained_name.PositionReferenceTuple, action_contract.PositionGuarantee
            ]
        ] = []
        for key in all_keys:
            # Consuming a callee's Interface Position must also override its
            # nested Guarantee when our caller later applies that Guarantee.
            # Destructors resolve all nested Guarantees here, and their callees'
            # Interface Positions are not Positions they must preserve.
            if is_destructor and any(chained_name.is_action_key(name) for name in key):
                continue
            first_element = key[0]
            # Any position that starts with a global is contracted, even if it was updated
            # by an implied action and we can't see it directly.
            if (
                first_element not in include_names
                and not chained_name.starts_with_global(key)
            ):
                continue
            guarantee = self._guarantee_for_key(key, requirements)
            if guarantee is None:
                continue
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
        # Execution order: Within the same key length, sorting
        # by caused_by (source position) is also required. For example, if
        # an action does:
        #
        #   move position<item>::position</child> to position<dest>.
        #   move position<item> to position<_sink>.
        #
        # Both of these show up as guarantees in the final output about
        # single-item positions: position<dest> has a guarantee that it
        # contains what was originally in position<item>::position</child>,
        # and position<item> has a guarantee that it's empty. (Remember that
        # guarantees show up entirely using the names of the _final destinations_,
        # so there is no guarantee emitted here about position<item>::position</child>---
        # it's automatically emptied by position<item> being emptied.)
        #
        # Thus, we must process position</child> being in position<dest> before
        # we process that position<item> is empty. Otherwise we would delete
        # the particle in position</child> incorrectly.
        guarantees.sort(
            key=lambda item: (
                len(item[0]),
                item[1].caused_by.location.line,
                item[1].caused_by.location.column,
            ),
        )
        return dict(guarantees)

    def _guarantee_for_key(
        self,
        key: chained_name.PositionReferenceTuple,
        requirements: dict[
            chained_name.PositionReferenceTuple,
            action_contract.PositionOccupancyRequirement,
        ],
    ) -> action_contract.PositionGuarantee | None:
        """Build a guarantee describing the current tracker state, or None for no-ops.

        A position whose state is identical to the action's starting state, but
        that the action operated on, gets an UnchangedGuarantee. A position that
        was left in its assumed starting state without ever being written produces None.
        """
        error_caused_by = self._store.error_caused_by(key)
        if error_caused_by is not None:
            return action_contract.ErrorGuarantee(
                caused_by=error_caused_by,
            )

        info = self._store.occupant_or_none(key)
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
            if (
                key != info.origin_position.canonical_chained_name_tuple
                or info.value_written_at is not None
                or info.value_state == particle_info.ParticleValueState.ERROR
            ):
                return action_contract.OccupiedByExistingGuarantee(
                    origin_position=info.origin_position,
                    caused_by=info.last_position,
                    value_effect=info.value_effect(),
                )
            # The caller's particle is right where it started.
            if self._store.was_written(key):
                return action_contract.UnchangedGuarantee(
                    caused_by=info.last_position,
                )
            # An assumed particle can remain untouched, including the trigger particle.
            #
            # TODO: Should we simply require people to always touch the trigger
            # position? It eliminates a lot of "more than one way to do it."
            return None

        # keys_for_guarantees returns an unoccupied Position without error
        # state only when it is known to be empty.
        caused_by = typing.cast("ast.PositionReference", self._store.emptied_by(key))
        requirement = requirements.get(key)
        if (
            requirement is not None
            and requirement.required_state
            == position_occupancy.PositionOccupancyState.EMPTY
        ):
            # The position was required to be empty when this action started,
            # and it is empty again. Something wrote it in between: a
            # requirement from a callee's callee comes with a pending guarantee
            # that writes the position, and those are applied before this action
            # publishes its guarantees.
            return action_contract.UnchangedGuarantee(
                caused_by=caused_by,
            )
        return action_contract.EmptyGuarantee(
            caused_by=caused_by,
        )
