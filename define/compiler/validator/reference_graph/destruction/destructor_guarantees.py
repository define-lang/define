"""Check that a Destructor leaves every contracted position as it found it (DLP 41)."""

from __future__ import annotations

import typing

from define.compiler import ast, chained_name
from define.compiler.errors import diagnostics
from define.compiler.validator.reference_graph import action_contract
from define.compiler.validator.reference_graph.particles import particle_info

if typing.TYPE_CHECKING:
    from define.compiler.validator.reference_graph.particles import (
        particle_tracker,
    )


# TODO: Consider a spec change that forbids Destructors from having empty or
# unset requirements on their contracted positions. Today two Destructors on
# one particle can require opposite states of a position whose state comes
# from the caller. Validating them one at a time then reports the second
# against the state the first's requirement made the action assume, and a
# contract cannot record both requirements on one position.
def check_destructor_guarantees(
    guarantees: dict[
        chained_name.PositionReferenceTuple,
        action_contract.PositionGuarantee,
    ],
    tracker: particle_tracker.ParticleTracker,
    enclosing_fqun: ast.Fqun,
) -> list[diagnostics.Diagnostic]:
    """Return a diagnostic for each of a Destructor's forbidden Guarantees, and replace them in ``guarantees`` with Error Guarantees.

    A destructor may not change any contracted position's state (DLP 41), so
    each guarantee it produces is a violation. The contract may not
    advertise such a guarantee, so each is replaced with an ErrorGuarantee
    that leaves the position's post-destructor state undetermined for any
    consumer of the contract. A change one of its callees makes shows in
    its own Guarantees, because a callee can only change a position that
    it or the Destructor requires something of, or one below a particle
    that is itself reported.

    A particle that is not from the caller, left below another such
    particle, is not reported: removing the upper one removes it too.
    """
    validation_diagnostics: list[diagnostics.Diagnostic] = []
    occupied_by_new_positions: set[chained_name.ChainedNameTuple] = set()
    for position, guarantee in guarantees.items():
        if isinstance(guarantee, action_contract.OccupiedByNewGuarantee):
            occupied_by_new_positions.add(position)
    for position, guarantee in guarantees.items():
        # A guarantee from a triggered action names its position the way that
        # callee wrote it. The key is the position's full chained name from
        # this Destructor's perspective, so report that instead.
        position_name = ast.source_form_chained_name(position, enclosing_fqun.canonical)
        match guarantee:
            case action_contract.EmptyGuarantee():
                validation_diagnostics.append(
                    diagnostics.DestructorProducesEmptyGuaranteeDiagnostic(
                        location=guarantee.caused_by.location,
                        position_name=position_name,
                    )
                )
            case action_contract.OccupiedByNewGuarantee():
                # Removing a particle that is not from the caller also
                # removes every such particle below it, so reporting
                # those too would only repeat the same error.
                if not any(
                    parent in occupied_by_new_positions
                    for parent in chained_name.proper_prefixes(position)
                ):
                    validation_diagnostics.append(
                        diagnostics.DestructorProducesOccupiedGuaranteeDiagnostic(
                            location=guarantee.caused_by.location,
                            position_name=position_name,
                        )
                    )
            case action_contract.OccupiedByExistingGuarantee() if (
                guarantee.origin_position.canonical_chained_name_tuple == position
            ):
                # A particle whose value did not change is where it started.
                # A change to the particle above it is reported on its own.
                if guarantee.value_effect in (
                    None,
                    particle_info.ParticleValueState.ERROR,
                ):
                    continue
                validation_diagnostics.append(
                    diagnostics.DestructorChangesValueDiagnostic(
                        location=tracker.value_written_at(position),
                        position_name=position_name,
                    )
                )
            case action_contract.OccupiedByExistingGuarantee():
                validation_diagnostics.append(
                    diagnostics.DestructorProducesOccupiedByExistingGuaranteeDiagnostic(
                        location=guarantee.caused_by.location,
                        position_name=position_name,
                        origin_name=guarantee.origin_position.source_form_in_universe(
                            enclosing_fqun
                        ),
                    )
                )
            case action_contract.ErrorGuarantee():
                continue
            case _:
                raise TypeError(f"unexpected guarantee type {type(guarantee).__name__}")
        guarantees[position] = action_contract.ErrorGuarantee()
    return validation_diagnostics
