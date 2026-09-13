"""Parallel processing ordered by definition references."""

from __future__ import annotations

import os
import typing
from array import array
from collections import deque
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait

if typing.TYPE_CHECKING:
    from collections.abc import Callable, Iterator

    from define.compiler import ast
    from define.compiler.graphs import reference_graph


class _ReferencedDefinitionError(Exception):
    """A definition could not be processed because a reference failed."""


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


@typing.final
class _WorkPool[ResultT]:
    """Runs definitions after their referenced definitions complete."""

    def __init__(
        self,
        order: ReferenceGraphOrder,
        process_definition: Callable[[ast.QualityDefinition], ResultT],
        max_workers: int | None,
    ):
        if max_workers is None:
            max_workers = min(32, (os.process_cpu_count() or 1) + 4)
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._max_in_flight = max_workers
        self._order = order
        self._process_definition = process_definition

    def __enter__(self) -> typing.Self:
        return self

    def __exit__(self, *args: object):
        self._executor.shutdown(wait=True, cancel_futures=True)

    def process(self) -> list[ResultT]:
        """Process every definition and return results in definition order."""
        remaining_references = self._order.new_reference_counts()
        ready_definitions = self._order.leaf_definition_indexes()
        in_flight: dict[Future[ResultT], int] = {}
        results: list[ResultT | None] = [None] * len(self._order.definitions)
        exceptions: list[BaseException | None] = [None] * len(self._order.definitions)

        while ready_definitions or in_flight:
            self._submit_ready_definitions(ready_definitions, in_flight)

            completed_futures, _ = wait(
                in_flight,
                return_when=FIRST_COMPLETED,
            )
            for future in completed_futures:
                definition_index = in_flight.pop(future)
                exception = future.exception()
                if exception is None:
                    results[definition_index] = future.result()
                else:
                    exceptions[definition_index] = exception
                self._complete_dependents(
                    definition_index,
                    exception,
                    remaining_references,
                    ready_definitions,
                    exceptions,
                )

        return self._ordered_results(results, exceptions)

    def _submit_ready_definitions(
        self,
        ready_definitions: deque[int],
        in_flight: dict[Future[ResultT], int],
    ):
        """Submit ready definitions up to the worker limit."""
        while ready_definitions and len(in_flight) < self._max_in_flight:
            definition_index = ready_definitions.popleft()
            future = self._executor.submit(
                self._process_definition,
                self._order.definitions[definition_index],
            )
            in_flight[future] = definition_index

    @staticmethod
    def _ordered_results(
        results: list[ResultT | None],
        exceptions: list[BaseException | None],
    ) -> list[ResultT]:
        """Return results or raise the first error in definition order."""
        ordered_results: list[ResultT] = []
        for result, exception in zip(results, exceptions, strict=True):
            if exception is not None:
                raise exception
            ordered_results.append(typing.cast("ResultT", result))
        return ordered_results

    def _complete_dependents(
        self,
        definition_index: int,
        exception: BaseException | None,
        remaining_references: array[int],
        ready_definitions: deque[int],
        exceptions: list[BaseException | None],
    ):
        if exception is None:
            for dependent_index in self._order.dependent_definition_indexes(
                definition_index
            ):
                remaining_references[dependent_index] -= 1
                if remaining_references[dependent_index] == 0:
                    ready_definitions.append(dependent_index)
            return

        failed_definitions = deque(
            self._order.dependent_definition_indexes(definition_index)
        )
        while failed_definitions:
            failed_definition_index = failed_definitions.popleft()
            if exceptions[failed_definition_index] is not None:
                continue
            exceptions[failed_definition_index] = _ReferencedDefinitionError()
            failed_definitions.extend(
                self._order.dependent_definition_indexes(failed_definition_index)
            )


def process_definitions[ResultT](
    order: ReferenceGraphOrder,
    process_definition: Callable[[ast.QualityDefinition], ResultT],
    *,
    max_workers: int | None = None,
) -> list[ResultT]:
    """Process definitions concurrently after their references complete."""
    with _WorkPool(order, process_definition, max_workers) as pool:
        return pool.process()
