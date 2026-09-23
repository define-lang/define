"""Compact processing order for definition references."""

from __future__ import annotations

import typing
from array import array
from collections import deque

if typing.TYPE_CHECKING:
    from collections.abc import Iterator

    from define.compiler import ast
    from define.compiler.graphs import reference_graph


@typing.final
class ReferenceGraphOrder:
    """Definitions and their direct-reference-first processing order.

    Uses an internal, compact representation of the reference graph that
    occupies 10x less memory than the full ReferenceGraph.
    """

    def __init__(self, graph: reference_graph.ReferenceGraph):
        """Record the graph's definition order and direct references."""
        self.definitions = list(graph.dfs_postorder_all())
        (
            self._reference_counts,
            reference_indexes,
            dependent_counts,
            self._leaf_indexes,
        ) = self._collect_references(graph, self.definitions)
        self._dependent_indexes, self._dependent_end_offsets = self._build_dependents(
            self._reference_counts, reference_indexes, dependent_counts
        )

    def new_reference_counts(self) -> array[int]:
        """Return a fresh count of each definition's unfinished dependencies."""
        return array("Q", self._reference_counts)

    def leaf_definition_indexes(self) -> deque[int]:
        """Return a fresh queue of indexes for definitions with no dependencies."""
        return deque(self._leaf_indexes)

    def dependent_definition_indexes(self, definition_index: int) -> Iterator[int]:
        """Yield indexes of definitions that directly reference one definition."""
        start_offset = self._dependent_end_offsets[definition_index]
        end_offset = self._dependent_end_offsets[definition_index + 1]
        for dependent_offset in range(start_offset, end_offset):
            yield self._dependent_indexes[dependent_offset]

    @staticmethod
    def _collect_references(
        graph: reference_graph.ReferenceGraph,
        definitions: list[ast.QualityDefinition],
    ) -> tuple[array[int], array[int], array[int], array[int]]:
        """Collect reference counts, reference indexes, dependent counts, and leaves."""
        # Dense 64-bit buffers avoid a separate Python integer per reference.
        reference_counts = array("Q")
        reference_indexes = array("Q")
        dependent_counts = array("Q", [0]) * len(definitions)
        # Retain leaves to avoid scanning every definition on each processing pass.
        leaf_indexes = array("Q")
        definition_index_by_name: dict[str, int] = {}
        # Dependencies precede their users, so their indexes are already known
        # when we record each definition's references.
        for definition_index, definition in enumerate(definitions):
            definition_index_by_name[definition.typed_name.full_typed_name] = (
                definition_index
            )
            start_offset = len(reference_indexes)
            for referenced_definition in graph.referenced_definitions(definition):
                referenced_definition_index = definition_index_by_name[
                    referenced_definition.typed_name.full_typed_name
                ]
                reference_indexes.append(referenced_definition_index)
                dependent_counts[referenced_definition_index] += 1
            reference_count = len(reference_indexes) - start_offset
            reference_counts.append(reference_count)
            if reference_count == 0:
                leaf_indexes.append(definition_index)
        return reference_counts, reference_indexes, dependent_counts, leaf_indexes

    @staticmethod
    def _build_dependents(
        reference_counts: array[int],
        reference_indexes: array[int],
        dependent_counts: array[int],
    ) -> tuple[array[int], array[int]]:
        """Build the dependent-definition indexes and their boundary offsets."""
        # Store reverse edges so each completion touches only definitions that
        # can become ready, rather than registering a callback for every edge.
        dependent_end_offsets = array("Q", [0])
        for dependent_count in dependent_counts:
            dependent_end_offsets.append(dependent_end_offsets[-1] + dependent_count)
        next_dependent_offsets = array("Q", dependent_end_offsets[:-1])
        dependent_indexes = array("Q", [0]) * len(reference_indexes)
        reference_offset = 0
        for definition_index, reference_count in enumerate(reference_counts):
            for _ in range(reference_count):
                referenced_definition_index = reference_indexes[reference_offset]
                dependent_offset = next_dependent_offsets[referenced_definition_index]
                dependent_indexes[dependent_offset] = definition_index
                next_dependent_offsets[referenced_definition_index] += 1
                reference_offset += 1
        return dependent_indexes, dependent_end_offsets
