"""The DLP 42 dead quality assignment ledger: directly-written quality assignments pending a liveness check."""

from __future__ import annotations

import typing

import msgspec

from define.compiler import ast, name_types

if typing.TYPE_CHECKING:
    from collections.abc import Iterable

    from define.compiler.data_structures import typed_name_dict
    from define.compiler.validator import validation_result


# Quality assignments that a particle's use in a Value Setting Statement or Operation
# Execution Statement keeps alive.
VALUE_AND_ENCODING_NAME_TYPES = frozenset(
    (name_types.NameType.VALUE, name_types.NameType.ENCODING)
)


class DeadQualityAssignmentCandidate(msgspec.Struct, frozen=True):
    """A directly-written quality assignment on a local or interface position pending a DLP 42 liveness check."""

    # The local or interface position the quality assignment is written on.
    position: ast.TypedName[ast.NameContent]
    quality: ast.GlobalTypedNameReference

    @property
    def key(self) -> tuple[str, str]:
        """The position and quality names that identify this assignment."""
        return (self.position.full_typed_name, self.quality.full_typed_name)


class DeadQualityAssignmentTracker:
    """The DLP 42 dead quality assignment ledger.

    A candidate is registered for each of a local or interface position's
    directly-written quality assignments that resolves and is not a destructor,
    and removed once the quality assignment is proven alive by a child-position reference,
    a value or encoding use, an action trigger, or an action contract. Whatever remains after a
    definition's body is analyzed is dead code.

    Implied actions must be triggered to be alive (which means constructors and
    destructors can never be implied).

    The validator feeds the tracker the particle and scope facts it cannot
    determine itself, including particle positions and the quality assignments on
    contracted positions.
    """

    def __init__(self):
        """Initialize an empty ledger."""
        self._child_position_candidates: dict[
            tuple[str, str], DeadQualityAssignmentCandidate
        ] = {}
        self._child_position_candidate_counts: dict[str, int] = {}
        self._child_action_candidates: dict[
            tuple[str, str], DeadQualityAssignmentCandidate
        ] = {}
        self._value_and_encoding_candidates: dict[
            tuple[str, str], DeadQualityAssignmentCandidate
        ] = {}
        self._implied_action_candidates: dict[str, ast.GlobalTypedNameReference] = {}

    def register_quality_assignment(
        self,
        position: ast.TypedName[ast.NameContent],
        quality: ast.GlobalTypedNameReference,
    ):
        """Register a directly-written quality assignment as a pending-dead candidate."""
        candidate = DeadQualityAssignmentCandidate(position=position, quality=quality)
        if quality.name_type == name_types.NameType.ACTION:
            self._child_action_candidates[candidate.key] = candidate
        elif quality.name_type in VALUE_AND_ENCODING_NAME_TYPES:
            self._value_and_encoding_candidates[candidate.key] = candidate
        else:
            quality_name = quality.full_typed_name
            self._child_position_candidate_counts[quality_name] = (
                self._child_position_candidate_counts.get(quality_name, 0) + 1
            )
            self._child_position_candidates[candidate.key] = candidate

    def register_implied_action(
        self,
        implied_action: ast.GlobalTypedNameReference,
    ):
        """Register an action assigned by a Quality Implication Statement."""
        self._implied_action_candidates[implied_action.full_typed_name] = implied_action

    def register_position_quality_assignments(
        self,
        position_definition: ast.LocalPositionDefinition,
        definition_results: typed_name_dict.TypedNameDict[
            ast.GlobalTypedName[ast.GlobalNameContent[ast.Fqun | None]],
            validation_result.DefinitionValidationResult,
        ],
    ):
        """Register a local or interface position's directly-written quality assignments as pending-dead candidates (DLP 42).

        Skips an unresolved quality, whose load failure is reported elsewhere,
        and a destructor, which is never dead because every particle is eventually
        destroyed.
        """
        for quality in position_definition.assigned_qualities:
            definition_result = definition_results.get(quality)
            if definition_result is None:
                continue
            if (
                isinstance(definition_result.definition, ast.ActionDefinition)
                and definition_result.definition.is_destructor
            ):
                continue
            self.register_quality_assignment(position_definition.typed_name, quality)

    def has_child_position_candidates(self) -> bool:
        """Whether there are any remaining child position assignments to check."""
        return bool(self._child_position_candidates)

    def has_child_position_candidate(
        self, quality: ast.GlobalTypedNameReference
    ) -> bool:
        """Whether any pending-dead assignment names the referenced position."""
        # Callers need this check before constructing position prefixes and querying
        # particle occupancy; checking only in mark_position_alive is too late.
        # On the generated Particle Operations workload with one worker, this
        # reduced sampled CPU in the liveness-marking path from 2.72 s to 0.52 s
        # and total sampled compiler CPU by 5.66% in one profile pair.
        return quality.full_typed_name in self._child_position_candidate_counts

    def has_candidates(self) -> bool:
        """Whether there are any remaining quality assignments to check."""
        return bool(
            self._child_position_candidates
            or self._child_action_candidates
            or self._value_and_encoding_candidates
        )

    def mark_value_or_encoding_alive(
        self,
        origin_position: ast.PositionReference,
        quality: ast.GlobalTypedNameReference,
    ):
        """Keep a used value quality or encoding assignment alive on the particle's origin position."""
        _ = self._value_and_encoding_candidates.pop(
            (origin_position.canonical_chained_name, quality.full_typed_name), None
        )

    def mark_position_alive(
        self,
        current_position: ast.PositionReference | None,
        origin_position: ast.PositionReference | None,
        quality: ast.GlobalTypedNameReference,
    ):
        """Keep a directly referenced child position assignment alive."""
        quality_name = quality.full_typed_name
        if current_position is not None:
            self._mark_child_position_alive(current_position, quality_name)
        if origin_position is None or (
            current_position is not None
            and current_position.canonical_chained_name
            == origin_position.canonical_chained_name
        ):
            return
        self._mark_child_position_alive(origin_position, quality_name)

    def _mark_child_position_alive(
        self, position: ast.PositionReference, quality_name: str
    ):
        candidate = self._child_position_candidates.pop(
            (position.canonical_chained_name, quality_name), None
        )
        if candidate is None:
            return
        remaining_count = self._child_position_candidate_counts[quality_name] - 1
        if remaining_count:
            self._child_position_candidate_counts[quality_name] = remaining_count
        else:
            del self._child_position_candidate_counts[quality_name]

    def mark_implied_action_alive(self, action: ast.GlobalTypedNameReference):
        """Keep an implied action alive when it is triggered on this action's parent particle."""
        _ = self._implied_action_candidates.pop(action.full_typed_name, None)

    def mark_action_alive(
        self,
        action: ast.GlobalTypedNameReference,
        current_position: ast.PositionReference,
        origin_position: ast.PositionReference | None,
    ):
        """Keep a child action assignment alive when the action is triggered.

        ``action`` is the action that actually triggered. ``current_position`` is
        the position holding the particle to which the action is assigned, and
        ``origin_position`` is that particle's Origin Position, if it has one.
        """
        if not self._child_action_candidates:
            return
        self._mark_quality_assignment_alive(
            self._child_action_candidates,
            current_position,
            origin_position,
            action,
        )

    def mark_contract_quality_assignments_alive(
        self,
        current_position: ast.PositionReference | None,
        origin_position: ast.PositionReference | None,
        qualities: tuple[ast.GlobalTypedNameReference, ...],
    ):
        """Keep matching quality assignments alive through an action contract."""
        if not self.has_candidates():
            return
        for quality in qualities:
            if quality.name_type in VALUE_AND_ENCODING_NAME_TYPES:
                self._mark_quality_assignment_alive(
                    self._value_and_encoding_candidates,
                    current_position,
                    origin_position,
                    quality,
                )
                continue
            self.mark_position_alive(current_position, origin_position, quality)
            self._mark_quality_assignment_alive(
                self._child_action_candidates,
                current_position,
                origin_position,
                quality,
            )

    @staticmethod
    def _mark_quality_assignment_alive(
        candidates: dict[tuple[str, str], DeadQualityAssignmentCandidate],
        current_position: ast.PositionReference | None,
        origin_position: ast.PositionReference | None,
        quality: ast.GlobalTypedNameReference,
    ):
        if current_position is not None:
            _ = candidates.pop(
                (
                    current_position.canonical_chained_name,
                    quality.full_typed_name,
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
            (origin_position.canonical_chained_name, quality.full_typed_name), None
        )

    def dead_child_positions(self) -> Iterable[DeadQualityAssignmentCandidate]:
        """Return the dead directly-written child position assignments (DLP 42)."""
        return self._child_position_candidates.values()

    def dead_child_actions(self) -> Iterable[DeadQualityAssignmentCandidate]:
        """Return the dead directly-written child action assignments (DLP 42)."""
        return self._child_action_candidates.values()

    def dead_value_and_encoding_assignments(
        self,
    ) -> Iterable[DeadQualityAssignmentCandidate]:
        """Return unused directly-written value quality and encoding assignments."""
        return self._value_and_encoding_candidates.values()

    def untriggered_implied_actions(
        self,
    ) -> Iterable[ast.GlobalTypedNameReference]:
        """Return implied actions not triggered by the action that implies them."""
        return self._implied_action_candidates.values()
