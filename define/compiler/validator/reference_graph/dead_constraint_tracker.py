"""The DLP 42 dead-constraint ledger: directly-written constraints pending a liveness check."""

from __future__ import annotations

import typing
from dataclasses import dataclass

from define.compiler import ast

if typing.TYPE_CHECKING:
    from collections.abc import Iterable

    from define.compiler.data_structures import typed_name_dict
    from define.compiler.validator import validation_result


@dataclass(frozen=True, slots=True)
class DeadConstraintCandidate:
    """A directly-written constraint on a local or interface position pending a DLP 42 liveness check."""

    # The local or interface position the constraint is written on.
    position: ast.TypedName
    constraint: ast.GlobalTypedNameReference

    @property
    def key(self) -> tuple[str, str]:
        """The ledger key, matching the (origin, constraint) names a move marks alive."""
        return (self.position.full_typed_name, self.constraint.full_typed_name)


class DeadConstraintTracker:
    """The DLP 42 dead-constraint ledger.

    A candidate is registered for each of a local or interface position's
    directly-written constraints that resolves and is not a destructor, and
    removed once the constraint is proven alive: referenced, triggered, required
    by a move, or written on an interface position the action exposes as output.
    Whatever remains after a definition's body is analyzed is dead code.

    The tracker holds no particle or scope state of its own. The validator feeds
    it the facts it cannot compute (a moved particle's origin, the interface
    positions an action exposes as output, the resolved definitions behind a
    position's constraints), so it stays independently testable.
    """

    def __init__(self):
        """Initialize an empty ledger."""
        self._candidates: dict[tuple[str, str], DeadConstraintCandidate] = {}

    def register_constraint(
        self, position: ast.TypedName, constraint: ast.GlobalTypedNameReference
    ):
        """Register a directly-written constraint as a pending-dead candidate."""
        candidate = DeadConstraintCandidate(position=position, constraint=constraint)
        self._candidates[candidate.key] = candidate

    def register_position_constraints(
        self,
        position_definition: ast.LocalPositionDefinition,
        definition_results: typed_name_dict.TypedNameDict[
            ast.GlobalTypedName, validation_result.DefinitionValidationResult
        ],
    ):
        """Register a local or interface position's directly-written constraints as pending-dead candidates (DLP 42).

        Skips an unresolved constraint, whose load failure is reported elsewhere,
        and a destructor, which is never dead because every particle is eventually
        destroyed.
        """
        for constraint in position_definition.constraint_typed_names:
            definition_result = definition_results.get(constraint)
            if definition_result is None:
                continue
            if (
                isinstance(definition_result.definition, ast.ActionDefinition)
                and definition_result.definition.is_destructor
            ):
                continue
            self.register_constraint(position_definition.typed_name, constraint)

    def has_pending(self) -> bool:
        """Whether any candidate is still pending (not yet proven alive)."""
        return bool(self._candidates)

    def _remove(self, key: tuple[str, str]):
        """Drop a candidate once it is proven alive."""
        if key in self._candidates:
            del self._candidates[key]

    def mark_alive(self, chain: ast.ChainedName):
        """Keep a constraint alive when a chain references it as a child position or triggers it as an action.

        A child position stays alive when referenced through any chain rooted at
        its bearer. An action is a direct constraint only when triggered as
        exactly ``bearer::action``; a deeper chain triggers an action on some
        child, and merely filling an action's interface position is not a trigger.
        """
        if not self._candidates or len(chain.typed_names) < 2:
            return
        bearer = chain.typed_names[0]
        constraint = chain.typed_names[1]
        if not isinstance(bearer, ast.LocalTypedNameReference):
            return
        if constraint.name_type == ast.NameType.ACTION and len(chain.typed_names) != 2:
            return
        self._remove((bearer.full_typed_name, constraint.full_typed_name))

    def mark_move_required(
        self,
        origin: ast.PositionReference,
        required: tuple[ast.GlobalTypedNameReference, ...],
    ):
        """Mark alive the origin position's constraints that a move destination requires (DLP 42).

        ``origin`` is the position the moved particle was created in: a constraint
        is satisfied by a move only if it was written on that position. Matching is
        by name, without expanding implications -- a constraint needed only because
        it implies a required quality is itself dead, and the spec wants the
        implied quality declared directly.
        """
        if not self._candidates:
            return
        origin_name = origin.canonical_chained_name
        for quality in required:
            self._remove((origin_name, quality.full_typed_name))

    def mark_constraints_alive(
        self,
        position: ast.TypedName,
        constraints: tuple[ast.GlobalTypedNameReference, ...],
    ):
        """Mark alive every directly-written constraint on a position.

        Used for an interface position the action's contract guarantees as output
        (it ends occupied), whose constraints therefore define a particle a caller
        consumes -- the opposite of the "actions as containers" pattern.
        """
        if not self._candidates:
            return
        for constraint in constraints:
            self._remove((position.full_typed_name, constraint.full_typed_name))

    def dead_constraints(self) -> Iterable[DeadConstraintCandidate]:
        """Return the candidates still pending: the dead constraints (DLP 42)."""
        return self._candidates.values()
