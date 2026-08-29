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
        """The position and constraint names that identify this assignment."""
        return (self.position.full_typed_name, self.constraint.full_typed_name)


class DeadConstraintTracker:
    """The DLP 42 dead-constraint ledger.

    A candidate is registered for each of a local or interface position's
    directly-written constraints that resolves and is not a destructor, and
    removed once the constraint is proven alive by a child-position reference,
    an action trigger, or an action contract. Whatever remains after a
    definition's body is analyzed is dead code.

    Implied actions must be triggered to be alive (which means constructors and
    destructors can never be implied).

    The validator feeds the tracker the particle and scope facts it cannot
    determine itself, including particle positions and the constraints on
    contracted positions.
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
        """Whether there are any remaining position constraints to check."""
        return bool(self._position_constraint_candidates)

    def _has_action_trigger_candidates(self) -> bool:
        """Whether there are any remaining implied or child actions to check."""
        return bool(
            self._action_constraint_candidates or self._implied_action_candidates
        )

    def has_constraint_candidates(self) -> bool:
        """Whether there are any remaining position or action constraints to check."""
        return bool(
            self._position_constraint_candidates or self._action_constraint_candidates
        )

    def mark_position_alive(
        self,
        current_position: ast.PositionReference,
        origin_position: ast.PositionReference | None,
        constraint: ast.GlobalTypedNameReference,
    ):
        """Keep a directly referenced child-position constraint alive."""
        if not self.has_position_constraint_candidates():
            return
        self._mark_constraint_alive(
            self._position_constraint_candidates,
            current_position,
            origin_position,
            constraint,
        )

    def mark_action_alive(
        self,
        action: ast.GlobalTypedNameReference,
        current_position: ast.PositionReference | None,
        origin_position: ast.PositionReference | None,
    ):
        """Keep an action constraint or implication alive when it is triggered.

        ``action`` is the action that actually triggered. ``current_position`` is
        the position holding the particle to which the action is assigned, or None
        when the action is implied by the current action. ``origin_position`` is
        that particle's origin position, or None for an implied action.
        """
        if not self._has_action_trigger_candidates():
            return
        _ = self._implied_action_candidates.pop(action.full_typed_name, None)
        self._mark_constraint_alive(
            self._action_constraint_candidates,
            current_position,
            origin_position,
            action,
        )

    def mark_contract_constraints_alive(
        self,
        current_position: ast.PositionReference | None,
        origin_position: ast.PositionReference,
        constraints: tuple[ast.GlobalTypedNameReference, ...],
    ):
        """Keep matching constraints alive through an action contract."""
        if not self.has_constraint_candidates():
            return
        for constraint in constraints:
            self._mark_constraint_alive(
                self._position_constraint_candidates,
                current_position,
                origin_position,
                constraint,
            )
            self._mark_constraint_alive(
                self._action_constraint_candidates,
                current_position,
                origin_position,
                constraint,
            )

    @staticmethod
    def _mark_constraint_alive(
        candidates: dict[tuple[str, str], DeadConstraintCandidate],
        current_position: ast.PositionReference | None,
        origin_position: ast.PositionReference | None,
        constraint: ast.GlobalTypedNameReference,
    ):
        if current_position is not None:
            _ = candidates.pop(
                (
                    current_position.canonical_chained_name,
                    constraint.full_typed_name,
                ),
                None,
            )
        if origin_position is None or (
            current_position is not None
            and origin_position.canonical_chained_name
            == current_position.canonical_chained_name
        ):
            return
        _ = candidates.pop(
            (origin_position.canonical_chained_name, constraint.full_typed_name), None
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
