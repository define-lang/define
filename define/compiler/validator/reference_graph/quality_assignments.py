"""Assigned particle qualities and their source-order implication provenance."""

from __future__ import annotations

import typing
from dataclasses import dataclass
from functools import cached_property

from define.compiler.data_structures import typed_name_dict

if typing.TYPE_CHECKING:
    from collections.abc import Callable, Iterator

    from define.compiler import ast

    type _ImplicationsFor = Callable[
        [ast.GlobalTypedNameReference],
        tuple[ast.GlobalTypedNameReference, ...],
    ]


@dataclass(frozen=True, slots=True)
class QualityAssignment:
    """A quality assigned by a constraint written on the particle's position."""

    quality: ast.GlobalTypedNameReference


@dataclass(frozen=True, slots=True)
class ImpliedQualityAssignment(QualityAssignment):
    """A quality assigned by another assigned quality."""

    caused_by: QualityAssignment


@typing.final
class QualityAssignments:
    """An immutable, ordered collection of qualities assigned to a particle."""

    assignments: tuple[QualityAssignment, ...]
    _direct_overrides: tuple[QualityAssignment, ...]

    def __init__(
        self,
        assignments: tuple[QualityAssignment, ...],
        direct_overrides: tuple[QualityAssignment, ...] = (),
    ):
        """Initialize from ordered assignment records and direct overrides."""
        self.assignments = assignments
        self._direct_overrides = direct_overrides

    @classmethod
    def expand_implications(
        cls,
        direct: tuple[ast.GlobalTypedNameReference, ...],
        implications_for: _ImplicationsFor,
    ) -> QualityAssignments:
        """Expand direct assignments depth-first in assignment order."""
        if not direct:
            return EMPTY_QUALITY_ASSIGNMENTS
        seen: dict[str, QualityAssignment] = {}
        assignments: list[QualityAssignment] = []
        direct_overrides: list[QualityAssignment] = []

        for direct_quality in direct:
            direct_assignment = QualityAssignment(direct_quality)
            existing = seen.get(direct_quality.full_typed_name)
            if existing is not None:
                if isinstance(existing, ImpliedQualityAssignment):
                    direct_overrides.append(direct_assignment)
                continue
            seen[direct_quality.full_typed_name] = direct_assignment
            cls._expand_depth_first(
                direct_assignment, implications_for, seen, assignments
            )
        return cls(tuple(assignments), tuple(direct_overrides))

    @staticmethod
    def _expand_depth_first(
        direct_assignment: QualityAssignment,
        implications_for: _ImplicationsFor,
        seen: dict[str, QualityAssignment],
        assignments: list[QualityAssignment],
    ):
        """Expand one direct assignment in semantic assignment order."""
        for implied_quality in implications_for(direct_assignment.quality):
            implied_name = implied_quality.full_typed_name
            if implied_name in seen:
                continue
            implied_assignment = ImpliedQualityAssignment(
                implied_quality, direct_assignment
            )
            seen[implied_name] = implied_assignment
            QualityAssignments._expand_depth_first(
                implied_assignment, implications_for, seen, assignments
            )
        assignments.append(direct_assignment)

    @cached_property
    def _preferred_assignments(
        self,
    ) -> typed_name_dict.TypedNameDict[ast.GlobalTypedNameReference, QualityAssignment]:
        assignment_by_quality: typed_name_dict.TypedNameDict[
            ast.GlobalTypedNameReference, QualityAssignment
        ] = typed_name_dict.TypedNameDict()
        for assignment in self.assignments:
            assignment_by_quality[assignment.quality] = assignment
        for assignment in self._direct_overrides:
            assignment_by_quality[assignment.quality] = assignment
        return assignment_by_quality

    def preferred_assignment_for(
        self, quality: ast.GlobalTypedNameReference
    ) -> QualityAssignment:
        """Return the assignment preferred for diagnostics.

        A direct assignment is preferred over an earlier implied assignment of
        the same quality. Otherwise, this returns the record in ``assignments``,
        which retains the first source-order implication path. Preferring a later
        direct assignment does not replace that record in ``assignments`` or
        change the paths of its descendants.
        """
        return self._preferred_assignments[quality]

    def has_quality(self, quality: ast.GlobalTypedNameReference) -> bool:
        """Return whether the quality is assigned."""
        return quality in self._preferred_assignments

    def __iter__(self) -> Iterator[ast.GlobalTypedNameReference]:
        """Iterate over assigned qualities in semantic assignment order."""
        return (assignment.quality for assignment in self.assignments)

    def __reversed__(self) -> Iterator[ast.GlobalTypedNameReference]:
        """Iterate over assigned qualities in reverse semantic assignment order."""
        return (assignment.quality for assignment in reversed(self.assignments))


EMPTY_QUALITY_ASSIGNMENTS = QualityAssignments(())
