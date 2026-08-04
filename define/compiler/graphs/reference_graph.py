"""Directed graph of definition references."""

from __future__ import annotations

import typing
from dataclasses import dataclass

if typing.TYPE_CHECKING:
    from collections.abc import Iterable, Iterator

    from define.compiler import ast


@dataclass(frozen=True, slots=True)
class ReferenceEdge:
    """A reference made by one definition to a global name in another file."""

    enclosing_definition: ast.QualityDefinition
    global_name_reference: ast.GlobalTypedNameReference

    @property
    def target_full_typed_name(self) -> str:
        """The referenced definition's full typed name."""
        return self.global_name_reference.full_typed_name

    @property
    def source_full_typed_name(self) -> str:
        """The enclosing definition's source typed name."""
        return self.enclosing_definition.typed_name.source_typed_name


# A cycle is a sequence of full typed names that begins and ends with the same
# name. Each definition in the sequence references the definition after it.
type DetectedCycle = list[str]


class ReferenceGraph:
    """References between definitions, kept free of reference cycles.

    A reference that would create a cycle is rejected, and the shortest cycle
    containing that reference is returned.
    """

    def __init__(self):
        """Create an empty reference graph."""
        # The inner dictionaries are ordered sets. Adding the same reference
        # twice costs no additional memory, and traversals retain insertion
        # order.
        self._references_by_name: dict[str, dict[str, None]] = {}

        # Every definition has a smaller depth than every definition it
        # references. This lets try_add_edge accept most references by comparing
        # two integers. When the comparison fails, it increases the referenced
        # definition's depth and the depths of any definitions it references.
        # That forward walk also detects whether the new reference would create
        # a cycle. A reverse-reference map would make other cycle algorithms
        # possible, but would use about 1.1 GB for five million definitions with
        # three references each.
        self._depth_by_name: dict[str, int] = {}
        self._definition_by_name: dict[str, ast.QualityDefinition] = {}

    def add_definition(self, definition: ast.QualityDefinition):
        """Register a definition with the graph."""
        definition_name = definition.typed_name.source_typed_name
        self._add_name(definition_name)
        self._definition_by_name[definition_name] = definition

    # Algorithm: Incremental cycle detection using a topological numbering. The
    # stored depths form the numbering, but unlike a total topological order,
    # unrelated definitions may have the same depth.
    def try_add_edge(self, edge: ReferenceEdge) -> DetectedCycle | None:
        """Add a reference unless it would create a cycle.

        Returns the shortest cycle containing the reference, or ``None`` when
        the reference was added.
        """
        referencing_name = edge.source_full_typed_name
        referenced_name = edge.target_full_typed_name
        if referencing_name == referenced_name:
            return [referencing_name, referenced_name]

        self._add_name(referencing_name)
        if referenced_name not in self._references_by_name:
            # A name with no references cannot lead back to the definition
            # that references it.
            self._references_by_name[referenced_name] = {}
            self._depth_by_name[referenced_name] = (
                self._depth_by_name[referencing_name] + 1
            )
        elif self._depth_by_name[referencing_name] >= self._depth_by_name[
            referenced_name
        ] and self._increase_depths_or_find_cycle(referencing_name, referenced_name):
            path_back_to_referencing_definition = self._shortest_reference_path(
                referenced_name, referencing_name
            )
            return [*path_back_to_referencing_definition, referenced_name]

        self._references_by_name[referencing_name][referenced_name] = None
        return None

    def dfs_postorder_from(
        self, starting_definition: ast.QualityDefinition
    ) -> Iterator[ast.QualityDefinition]:
        """Yield referenced definitions before definitions that reference them.

        Only definitions reachable from ``starting_definition`` are yielded.
        """
        starting_name = starting_definition.typed_name.source_typed_name
        for definition_name in self._names_in_postorder([starting_name]):
            yield self._definition_by_name[definition_name]

    def dfs_postorder_all(self) -> Iterator[ast.QualityDefinition]:
        """Yield all referenced definitions before definitions that reference them."""
        for definition_name in self._names_in_postorder(self._references_by_name):
            if definition_name in self._definition_by_name:
                yield self._definition_by_name[definition_name]

    def _add_name(self, definition_name: str):
        if definition_name not in self._references_by_name:
            self._references_by_name[definition_name] = {}
            self._depth_by_name[definition_name] = 0

    # Algorithm: Worklist-based forward propagation of topological-depth
    # constraints.
    def _increase_depths_or_find_cycle(
        self, referencing_name: str, referenced_name: str
    ) -> bool:
        """Make the proposed reference satisfy the graph's depth ordering.

        Returns whether the referenced definition already leads back to the
        referencing definition. If it does, all depth changes are undone.
        """
        references_by_name = self._references_by_name
        depth_by_name = self._depth_by_name
        original_depth_by_name: dict[str, int] = {}
        pending_depth_changes = [(referenced_name, depth_by_name[referencing_name] + 1)]
        while pending_depth_changes:
            current_name, required_depth = pending_depth_changes.pop()
            if required_depth <= depth_by_name[current_name]:
                continue

            if current_name not in original_depth_by_name:
                original_depth_by_name[current_name] = depth_by_name[current_name]
            depth_by_name[current_name] = required_depth

            for next_referenced_name in references_by_name[current_name]:
                if next_referenced_name == referencing_name:
                    for changed_name, original_depth in original_depth_by_name.items():
                        depth_by_name[changed_name] = original_depth
                    return True
                if depth_by_name[next_referenced_name] <= required_depth:
                    pending_depth_changes.append(
                        (next_referenced_name, required_depth + 1)
                    )
        return False

    # Algorithm: Breadth-first search, with one list for each distance from the
    # starting definition.
    def _shortest_reference_path(
        self, starting_name: str, destination_name: str
    ) -> list[str]:
        """Find the shortest reference path between two connected definitions."""
        predecessor_by_name: dict[str, str | None] = {starting_name: None}
        names_at_current_distance = [starting_name]
        while names_at_current_distance and destination_name not in predecessor_by_name:
            names_at_next_distance: list[str] = []
            for current_name in names_at_current_distance:
                for referenced_name in self._references_by_name[current_name]:
                    if referenced_name not in predecessor_by_name:
                        predecessor_by_name[referenced_name] = current_name
                        names_at_next_distance.append(referenced_name)
            names_at_current_distance = names_at_next_distance
        return _build_path(predecessor_by_name, destination_name)

    # Algorithm: Iterative depth-first search in post-order. The stack replaces
    # the call stack so a long reference chain cannot exceed Python's recursion
    # limit.
    def _names_in_postorder(self, starting_names: Iterable[str]) -> Iterator[str]:
        """Yield reachable names in depth-first post-order."""
        visited_names: set[str] = set()
        for starting_name in starting_names:
            if starting_name in visited_names:
                continue

            visited_names.add(starting_name)
            stack = [(starting_name, iter(self._references_by_name[starting_name]))]
            while stack:
                current_name, remaining_referenced_names = stack[-1]
                for referenced_name in remaining_referenced_names:
                    if referenced_name not in visited_names:
                        visited_names.add(referenced_name)
                        stack.append(
                            (
                                referenced_name,
                                iter(self._references_by_name[referenced_name]),
                            )
                        )
                        break
                else:
                    # All references from this definition have been yielded, so
                    # the definition itself is ready.
                    _ = stack.pop()
                    yield current_name


# Algorithm: Predecessor-chain path reconstruction for breadth-first search.
def _build_path(
    predecessor_by_name: dict[str, str | None], destination_name: str
) -> list[str]:
    path: list[str] = []
    current_name: str | None = destination_name
    while current_name is not None:
        path.append(current_name)
        current_name = predecessor_by_name[current_name]
    path.reverse()
    return path
