"""Assigned particle qualities in semantic assignment order."""

from __future__ import annotations

import typing
from functools import cached_property

from define.compiler import name_types

if typing.TYPE_CHECKING:
    from collections.abc import Callable, Iterator, KeysView

    from define.compiler import ast

    type _ImplicationsFor = Callable[
        [ast.GlobalTypedNameReference],
        tuple[ast.GlobalTypedNameReference, ...],
    ]


VALUE_AND_ENCODING_NAME_TYPES = frozenset(
    (name_types.NameType.VALUE, name_types.NameType.ENCODING)
)


@typing.final
class QualityAssignments:
    """An immutable, ordered collection of qualities assigned to a particle."""

    # Quality assignments are retained for the whole compilation. A tuple is
    # smaller than the list it is built from, and every empty tuple is the same
    # shared object.
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
        # An explicit stack instead of recursion, because a Quality
        # Implication chain can be deeper than Python's recursion limit.
        pending = [(quality, iter(implications_for(quality)))]
        while pending:
            current, implied_qualities = pending[-1]
            for implied_quality in implied_qualities:
                implied_name = implied_quality.full_typed_name
                if implied_name in seen:
                    continue
                seen.add(implied_name)
                pending.append(
                    (implied_quality, iter(implications_for(implied_quality)))
                )
                break
            else:
                _ = pending.pop()
                assignments.append(current)

    @cached_property
    def _by_name(self) -> dict[str, ast.GlobalTypedNameReference]:
        return {quality.full_typed_name: quality for quality in self.assignments}

    @property
    def names(self) -> KeysView[str]:
        """The full typed names of the assigned qualities."""
        return self._by_name.keys()

    def has_quality(self, quality: ast.GlobalTypedNameReference) -> bool:
        """Return whether the quality is assigned."""
        return quality.full_typed_name in self._by_name

    def quality_named(self, name: str) -> ast.GlobalTypedNameReference:
        """Return the assigned quality whose full typed name is ``name``."""
        return self._by_name[name]

    @cached_property
    def value_quality(self) -> ast.GlobalTypedNameReference | None:
        """The value quality assigned to the particle."""
        for quality in self.assignments:
            if quality.name_type == name_types.NameType.VALUE:
                return quality
        return None

    @cached_property
    def value_and_encoding_qualities(self) -> tuple[ast.GlobalTypedNameReference, ...]:
        """The value qualities and encodings assigned to the particle, in assignment order."""
        # This is needed every time the particle's value is used. A particle
        # can have many qualities, so scanning them all on every use was slow.
        return tuple(
            quality
            for quality in self.assignments
            if quality.name_type in VALUE_AND_ENCODING_NAME_TYPES
        )

    def __iter__(self) -> Iterator[ast.GlobalTypedNameReference]:
        """Iterate over assigned qualities in semantic assignment order."""
        return iter(self.assignments)


EMPTY_QUALITY_ASSIGNMENTS = QualityAssignments(())
