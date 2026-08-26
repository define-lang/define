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


# TODO: Move requirements currently create liveness immediately, which lets
# circular moves make otherwise-dead constraints appear alive. Record backward
# dependencies from destination constraints to the moved particle's origin
# constraints instead. References and action contract requirements or exposure
# should seed liveness; moves should only propagate that liveness so chains
# through local and child positions work while unseeded cycles stay dead.
# TODO: Decide whether implied constructors are allowed.
class DeadConstraintTracker:
    """The DLP 42 dead-constraint ledger.

    A candidate is registered for each of a local or interface position's
    directly-written constraints that resolves and is not a destructor, and
    removed once the constraint is proven alive: referenced, triggered, required
    by a move, or written on an interface position the action exposes as output.
    Whatever remains after a definition's body is analyzed is dead code.

    Implied actions must be triggered to be alive (which means destructors can
    never be implied).

    The tracker holds no particle or scope state of its own. The validator feeds
    it the facts it cannot compute (a moved particle's origin, the interface
    positions an action exposes as output, the resolved definitions behind a
    position's constraints), so it stays independently testable.
    """

    def __init__(self):
        """Initialize an empty ledger."""
        self._position_constraint_candidates: dict[
            tuple[str, str], DeadConstraintCandidate
        ] = {}
        self._action_constraint_candidates: dict[
            tuple[str, str], DeadConstraintCandidate
        ] = {}
        self._implied_action_candidates: dict[str, ast.GlobalTypedNameReference] = {}

    def register_constraint(
        self, position: ast.TypedName, constraint: ast.GlobalTypedNameReference
    ):
        """Register a directly-written constraint as a pending-dead candidate."""
        candidate = DeadConstraintCandidate(position=position, constraint=constraint)
        if constraint.name_type == ast.NameType.ACTION:
            self._action_constraint_candidates[candidate.key] = candidate
        else:
            self._position_constraint_candidates[candidate.key] = candidate

    def register_implied_action(
        self,
        implied_action: ast.GlobalTypedNameReference,
    ):
        """Register an action assigned by a Quality Implication Statement."""
        self._implied_action_candidates[implied_action.full_typed_name] = implied_action

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

    def has_position_constraint_candidates(self) -> bool:
        """Whether a position reference or guarantee can mark a candidate alive."""
        return bool(self._position_constraint_candidates)

    def _has_action_trigger_candidates(self) -> bool:
        """Whether an action trigger can mark a candidate alive."""
        return bool(
            self._action_constraint_candidates or self._implied_action_candidates
        )

    def has_move_candidates(self) -> bool:
        """Whether a move requirement can mark a candidate alive."""
        return bool(
            self._position_constraint_candidates or self._action_constraint_candidates
        )

    def mark_position_alive(self, chain: ast.PositionReference):
        """Keep a position constraint alive when a chain references it."""
        if not self.has_position_constraint_candidates():
            return
        if len(chain.typed_names) < 2:
            return
        position = chain.typed_names[0]
        constraint = chain.typed_names[1]
        if not isinstance(position, ast.LocalTypedNameReference):
            return
        _ = self._position_constraint_candidates.pop(
            (position.full_typed_name, constraint.full_typed_name), None
        )

    def mark_action_alive(self, chain: ast.ActionReference):
        """Keep an action constraint or implication alive when it is triggered.

        ``chain`` ends with the triggered action and does not include its trigger
        position. The final action can be an implied-action candidate in a chain of
        any length. A directly-written action constraint is eligible only when the
        chain consists of the local or interface position followed by that action.
        """
        if not self._has_action_trigger_candidates():
            return
        action = chain.typed_names[-1]
        _ = self._implied_action_candidates.pop(action.full_typed_name, None)
        if len(chain.typed_names) != 2:
            return
        position = chain.typed_names[0]
        if not isinstance(position, ast.LocalTypedNameReference):
            return
        _ = self._action_constraint_candidates.pop(
            (position.full_typed_name, action.full_typed_name), None
        )

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
        if not self.has_move_candidates():
            return
        origin_name = origin.canonical_chained_name
        for quality in required:
            key = (origin_name, quality.full_typed_name)
            _ = self._position_constraint_candidates.pop(key, None)
            _ = self._action_constraint_candidates.pop(key, None)

    def mark_position_constraints_alive(
        self,
        position: ast.TypedName,
        constraints: tuple[ast.GlobalTypedNameReference, ...],
    ):
        """Mark alive every directly-written position constraint on a position.

        When an action guarantees that an interface position is occupied, callers
        can rely on its particle having every directly-written position quality.
        Those position constraints are therefore alive even if the action contains
        no chained name that references them.
        """
        if not self.has_position_constraint_candidates():
            return
        for constraint in constraints:
            _ = self._position_constraint_candidates.pop(
                (position.full_typed_name, constraint.full_typed_name), None
            )

    def dead_position_constraints(self) -> Iterable[DeadConstraintCandidate]:
        """Return the dead directly-written position constraints (DLP 42)."""
        return self._position_constraint_candidates.values()

    def dead_action_constraints(self) -> Iterable[DeadConstraintCandidate]:
        """Return the dead directly-written action constraints (DLP 42)."""
        return self._action_constraint_candidates.values()

    def untriggered_implied_actions(
        self,
    ) -> Iterable[ast.GlobalTypedNameReference]:
        """Return implied actions not triggered by the action that implies them."""
        return self._implied_action_candidates.values()
