"""Parallel processing ordered by definition references."""

from __future__ import annotations

import functools
import typing

from define.compiler import work_pool

if typing.TYPE_CHECKING:
    from collections.abc import Callable

    from define.compiler import ast
    from define.compiler.graphs import reference_graph_order


@typing.final
class _ReferenceOrderProcessor[DefinitionT: ast.GlobalDefinition, ResultT]:
    """Runs definitions after their referenced definitions complete."""

    def __init__(
        self,
        order: reference_graph_order.ReferenceGraphOrder,
        requires_processing: Callable[
            [ast.GlobalDefinition], typing.TypeIs[DefinitionT]
        ],
        process_definition: Callable[[DefinitionT], ResultT],
        pool: work_pool.WorkPool,
    ):
        self._order = order
        self._requires_processing = requires_processing
        self._process_definition = process_definition
        self._pool = pool
        self._remaining_references = order.new_reference_counts()
        # One slot per definition, in definition order. Definitions finish in
        # whatever order the threads get to them, and each result goes straight
        # into its own slot, so nothing waits on another definition. This only
        # lets process() return the results in the same order every run, so
        # that the compiler's output doesn't depend on thread timing.
        self._results: list[ResultT | None] = [None] * len(order.definitions)
        # Kept apart from results because None is a valid result.
        self._processed = bytearray(len(order.definitions))

    def process(self) -> list[ResultT]:
        """Return the results of processed definitions in definition order.

        An exception from processing a definition is a compiler bug, so it is
        raised as soon as the coordinator thread sees it rather than after the
        remaining definitions are processed.
        """
        unprocessed_definitions: list[int] = []
        for definition_index in self._order.leaf_definition_indexes():
            self._release_definition(definition_index, unprocessed_definitions)
        self._complete_definitions(unprocessed_definitions)
        self._pool.run_until_idle()

        ordered_results: list[ResultT] = []
        for result, was_processed in zip(self._results, self._processed, strict=True):
            if was_processed:
                ordered_results.append(typing.cast("ResultT", result))
        return ordered_results

    def _handle_result(
        self, definition_index: int, result: ResultT, _pool: work_pool.WorkPool
    ):
        self._results[definition_index] = result
        self._processed[definition_index] = True
        self._complete_definitions([definition_index])

    def _release_definition(
        self, definition_index: int, unprocessed_definitions: list[int]
    ):
        """Submit a definition whose references have all completed."""
        definition = self._order.definitions[definition_index]
        if self._requires_processing(definition):
            self._pool.submit(
                self._process_definition,
                definition,
                handle_result=functools.partial(self._handle_result, definition_index),
            )
        else:
            unprocessed_definitions.append(definition_index)

    def _complete_definitions(self, completed_definitions: list[int]):
        """Release dependents of completed definitions.

        Dependents that do not require processing complete immediately.
        """
        remaining_references = self._remaining_references
        while completed_definitions:
            completed_index = completed_definitions.pop()
            for dependent_index in self._order.dependent_definition_indexes(
                completed_index
            ):
                remaining_references[dependent_index] -= 1
                if remaining_references[dependent_index] == 0:
                    self._release_definition(dependent_index, completed_definitions)


def process_definitions[DefinitionT: ast.GlobalDefinition, ResultT](
    order: reference_graph_order.ReferenceGraphOrder,
    requires_processing: Callable[[ast.GlobalDefinition], typing.TypeIs[DefinitionT]],
    process_definition: Callable[[DefinitionT], ResultT],
    *,
    max_workers: int | None = None,
) -> list[ResultT]:
    """Process selected definitions concurrently after their references complete.

    Definitions that do not require processing still complete in reference
    order, but produce no results.
    """
    with work_pool.WorkPool(max_workers) as pool:
        return _ReferenceOrderProcessor(
            order, requires_processing, process_definition, pool
        ).process()
