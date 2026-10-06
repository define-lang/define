"""Parallel processing ordered by definition references."""

from __future__ import annotations

import os
import queue
import typing
from collections import deque
from concurrent.futures import ThreadPoolExecutor

if typing.TYPE_CHECKING:
    from array import array
    from collections.abc import Callable
    from concurrent.futures import Future

    from define.compiler import ast
    from define.compiler.graphs import reference_graph_order


class _ReferencedDefinitionError(Exception):
    """A definition could not be processed because a reference failed."""


@typing.final
class _WorkPool[DefinitionT: ast.GlobalDefinition, ResultT]:
    """Runs definitions after their referenced definitions complete."""

    def __init__(
        self,
        order: reference_graph_order.ReferenceGraphOrder,
        requires_processing: Callable[
            [ast.GlobalDefinition], typing.TypeIs[DefinitionT]
        ],
        process_definition: Callable[[DefinitionT], ResultT],
        max_workers: int | None,
    ):
        if max_workers is None:
            max_workers = min(32, (os.process_cpu_count() or 1) + 4)
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._max_in_flight = max_workers
        self._order = order
        self._requires_processing = requires_processing
        self._process_definition = process_definition
        self._completed: queue.SimpleQueue[Future[ResultT]] = queue.SimpleQueue()

    def __enter__(self) -> typing.Self:
        return self

    def __exit__(self, *args: object):
        self._executor.shutdown(wait=True, cancel_futures=True)

    def process(self) -> list[ResultT]:
        """Return the results of processed definitions in definition order."""
        remaining_references = self._order.new_reference_counts()
        ready_definitions: deque[int] = deque()
        unprocessed_definitions: list[int] = []
        for definition_index in self._order.leaf_definition_indexes():
            self._release_definition(
                definition_index, ready_definitions, unprocessed_definitions
            )
        self._complete_definitions(
            unprocessed_definitions, remaining_references, ready_definitions
        )
        in_flight: dict[Future[ResultT], int] = {}
        results: list[ResultT | None] = [None] * len(self._order.definitions)
        # Kept apart from results because None is a valid result.
        processed = bytearray(len(self._order.definitions))
        exceptions: list[BaseException | None] = [None] * len(self._order.definitions)

        while ready_definitions or in_flight:
            self._submit_ready_definitions(ready_definitions, in_flight)

            future = self._completed.get()
            definition_index = in_flight.pop(future)
            exception = future.exception()
            if exception is None:
                results[definition_index] = future.result()
                processed[definition_index] = True
            else:
                exceptions[definition_index] = exception
            self._complete_dependents(
                definition_index,
                exception,
                remaining_references,
                ready_definitions,
                exceptions,
            )

        return self._ordered_results(results, processed, exceptions)

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
                # _release_definition only queues definitions that
                # requires_processing narrowed to DefinitionT.
                typing.cast("DefinitionT", self._order.definitions[definition_index]),
            )
            in_flight[future] = definition_index
            future.add_done_callback(self._completed.put)

    @staticmethod
    def _ordered_results(
        results: list[ResultT | None],
        processed: bytearray,
        exceptions: list[BaseException | None],
    ) -> list[ResultT]:
        """Return processed results or raise the first error in definition order."""
        ordered_results: list[ResultT] = []
        for result, was_processed, exception in zip(
            results, processed, exceptions, strict=True
        ):
            if exception is not None:
                raise exception
            if was_processed:
                ordered_results.append(typing.cast("ResultT", result))
        return ordered_results

    def _release_definition(
        self,
        definition_index: int,
        ready_definitions: deque[int],
        unprocessed_definitions: list[int],
    ):
        """Queue a definition whose references have all completed."""
        if self._requires_processing(self._order.definitions[definition_index]):
            ready_definitions.append(definition_index)
        else:
            unprocessed_definitions.append(definition_index)

    def _complete_definitions(
        self,
        completed_definitions: list[int],
        remaining_references: array[int],
        ready_definitions: deque[int],
    ):
        """Release dependents of completed definitions.

        Dependents that do not require processing complete immediately.
        """
        while completed_definitions:
            completed_index = completed_definitions.pop()
            for dependent_index in self._order.dependent_definition_indexes(
                completed_index
            ):
                remaining_references[dependent_index] -= 1
                if remaining_references[dependent_index] == 0:
                    self._release_definition(
                        dependent_index, ready_definitions, completed_definitions
                    )

    def _complete_dependents(
        self,
        definition_index: int,
        exception: BaseException | None,
        remaining_references: array[int],
        ready_definitions: deque[int],
        exceptions: list[BaseException | None],
    ):
        if exception is None:
            self._complete_definitions(
                [definition_index], remaining_references, ready_definitions
            )
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


def _requires_every_definition(
    _definition: ast.GlobalDefinition,
) -> typing.TypeIs[ast.GlobalDefinition]:
    return True


def process_definitions[ResultT](
    order: reference_graph_order.ReferenceGraphOrder,
    process_definition: Callable[[ast.GlobalDefinition], ResultT],
    *,
    max_workers: int | None = None,
) -> list[ResultT]:
    """Process definitions concurrently after their references complete."""
    return process_selected_definitions(
        order,
        _requires_every_definition,
        process_definition,
        max_workers=max_workers,
    )


def process_selected_definitions[DefinitionT: ast.GlobalDefinition, ResultT](
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
    with _WorkPool(order, requires_processing, process_definition, max_workers) as pool:
        return pool.process()
