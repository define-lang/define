"""Assigned particle qualities in semantic assignment order."""

from __future__ import annotations

import typing
from functools import cached_property

if typing.TYPE_CHECKING:
    from collections.abc import Callable, Iterator

    from define.compiler import ast

    type _ImplicationsFor = Callable[
        [ast.GlobalTypedNameReference],
        tuple[ast.GlobalTypedNameReference, ...],
    ]


@typing.final
class QualityAssignments:
    """An immutable, ordered collection of qualities assigned to a particle."""

    assignments: tuple[ast.GlobalTypedNameReference, ...]

    def __init__(self, assignments: tuple[ast.GlobalTypedNameReference, ...]):
        """Initialize from ordered assigned qualities."""
        self.assignments = assignments

    @classmethod
    def expand_implications(
        cls,
        direct: tuple[ast.GlobalTypedNameReference, ...],
        implications_for: _ImplicationsFor,
    ) -> QualityAssignments:
        """Expand direct assignments depth-first in assignment order."""
        if not direct:
            return EMPTY_QUALITY_ASSIGNMENTS
        seen: set[str] = set()
        assignments: list[ast.GlobalTypedNameReference] = []

        for direct_quality in direct:
            if direct_quality.full_typed_name in seen:
                continue
            seen.add(direct_quality.full_typed_name)
            cls._expand_depth_first(direct_quality, implications_for, seen, assignments)
        return cls(tuple(assignments))

    @staticmethod
    def _expand_depth_first(
        quality: ast.GlobalTypedNameReference,
        implications_for: _ImplicationsFor,
        seen: set[str],
        assignments: list[ast.GlobalTypedNameReference],
    ):
        """Expand one assignment in semantic assignment order."""
        for implied_quality in implications_for(quality):
            implied_name = implied_quality.full_typed_name
            if implied_name in seen:
                continue
            seen.add(implied_name)
            QualityAssignments._expand_depth_first(
                implied_quality, implications_for, seen, assignments
            )
        assignments.append(quality)

    @cached_property
    def _quality_names(self) -> frozenset[str]:
        return frozenset(quality.full_typed_name for quality in self.assignments)

    def has_quality(self, quality: ast.GlobalTypedNameReference) -> bool:
        """Return whether the quality is assigned."""
        return quality.full_typed_name in self._quality_names

    def __iter__(self) -> Iterator[ast.GlobalTypedNameReference]:
        """Iterate over assigned qualities in semantic assignment order."""
        return iter(self.assignments)


EMPTY_QUALITY_ASSIGNMENTS = QualityAssignments(())
