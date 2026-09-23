"""Parallel processing ordered by definition references."""

from __future__ import annotations

import os
import typing
from collections import deque
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait

if typing.TYPE_CHECKING:
    from array import array
    from collections.abc import Callable

    from define.compiler import ast
    from define.compiler.graphs import reference_graph_order


class _ReferencedDefinitionError(Exception):
    """A definition could not be processed because a reference failed."""


@typing.final
class _WorkPool[ResultT]:
    """Runs definitions after their referenced definitions complete."""

    def __init__(
        self,
        order: reference_graph_order.ReferenceGraphOrder,
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
    order: reference_graph_order.ReferenceGraphOrder,
    process_definition: Callable[[ast.QualityDefinition], ResultT],
    *,
    max_workers: int | None = None,
) -> list[ResultT]:
    """Process definitions concurrently after their references complete."""
    with _WorkPool(order, process_definition, max_workers) as pool:
        return pool.process()
