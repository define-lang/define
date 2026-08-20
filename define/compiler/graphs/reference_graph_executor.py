"""Parallel processing ordered by definition references."""

from __future__ import annotations

import threading
import typing
from array import array
from concurrent.futures import Future, ThreadPoolExecutor, wait

if typing.TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Iterator

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
        # Keep one referenced-definition index per Reference Edge in a dense
        # 64-bit buffer, avoiding a separate Python integer for every reference.
        reference_indexes = array("Q")
        # Delimit each definition's consecutive indexes in reference_indexes;
        # the extra initial offset makes definition N use offsets N and N + 1.
        reference_end_offsets = array("Q", [0])
        definition_index_by_name: dict[str, int] = {}
        for definition_index, definition in enumerate(self.definitions):
            definition_index_by_name[definition.typed_name.full_typed_name] = (
                definition_index
            )
            for referenced_definition in graph.referenced_definitions(definition):
                reference_indexes.append(
                    definition_index_by_name[
                        referenced_definition.typed_name.full_typed_name
                    ]
                )
            reference_end_offsets.append(len(reference_indexes))
        self._reference_indexes = reference_indexes
        self._reference_end_offsets = reference_end_offsets

    def referenced_definition_indexes(self, definition_index: int) -> Iterator[int]:
        """Yield indexes of definitions directly referenced by one definition."""
        start_offset = self._reference_end_offsets[definition_index]
        end_offset = self._reference_end_offsets[definition_index + 1]
        for reference_offset in range(start_offset, end_offset):
            yield self._reference_indexes[reference_offset]


@typing.final
class _PendingDefinition[ResultT]:
    """Starts one definition after its referenced definitions complete."""

    def __init__(
        self,
        definition: ast.QualityDefinition,
        reference_count: int,
        start_definition: Callable[[ast.QualityDefinition, Future[ResultT]], None],
    ):
        self._completion: Future[ResultT] = Future()
        self._definition = definition
        self._remaining_references: int | None = reference_count
        self._scheduling_lock = threading.Lock()
        self._start_definition = start_definition

    def start_when_references_complete(
        self,
        referenced_futures: list[Future[ResultT]],
    ):
        """Register referenced definitions and start when they are ready."""
        if not referenced_futures:
            self._start_definition(self._definition, self._completion)
            return
        for referenced_future in referenced_futures:
            referenced_future.add_done_callback(self._reference_completed)

    @property
    def future(self) -> Future[ResultT]:
        return self._completion

    def result(self) -> ResultT:
        return self._completion.result()

    def _reference_completed(self, referenced_future: Future[ResultT]):
        reference_completed_successfully = referenced_future.exception() is None
        start_definition = False
        with self._scheduling_lock:
            if self._remaining_references is None:
                return
            if not reference_completed_successfully:
                self._remaining_references = None
            else:
                self._remaining_references -= 1
                if self._remaining_references == 0:
                    self._remaining_references = None
                    start_definition = True

        if not reference_completed_successfully:
            # This completion future was not submitted to an executor, so
            # cancel() would never reach the CANCELLED_AND_NOTIFIED state that
            # concurrent.futures.wait() requires before it stops waiting. Thus
            # we use this sentinel exception to indicate completion in the error
            # case, instead of cancel().
            self._completion.set_exception(_ReferencedDefinitionError())
        elif start_definition:
            self._start_definition(self._definition, self._completion)


@typing.final
class _WorkPool[ResultT]:
    """Runs definitions after their referenced definitions complete."""

    def __init__(
        self,
        process_definition: Callable[[ast.QualityDefinition], ResultT],
        max_workers: int | None,
    ):
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._pending_definitions: list[_PendingDefinition[ResultT]] = []
        self._process_definition = process_definition

    def __enter__(self) -> typing.Self:
        return self

    def __exit__(self, *args: object):
        self._executor.shutdown(wait=True, cancel_futures=True)

    def submit(
        self,
        definition: ast.QualityDefinition,
        referenced_definition_indexes: Iterable[int],
    ):
        """Submit a definition to start after its references are ready."""
        referenced_futures = [
            self._pending_definitions[referenced_definition_index].future
            for referenced_definition_index in referenced_definition_indexes
        ]
        pending_definition = _PendingDefinition(
            definition,
            len(referenced_futures),
            self._start_definition,
        )
        self._pending_definitions.append(pending_definition)
        pending_definition.start_when_references_complete(referenced_futures)

    def wait(self):
        """Wait for every submitted definition to complete."""
        _ = wait(work.future for work in self._pending_definitions)

    def results(self) -> list[ResultT]:
        """Return completed results in definition order."""
        return [
            pending_definition.result()
            for pending_definition in self._pending_definitions
        ]

    def _start_definition(
        self,
        definition: ast.QualityDefinition,
        completion: Future[ResultT],
    ):
        executor_future = self._executor.submit(self._process_definition, definition)
        executor_future.add_done_callback(
            lambda completed_executor_future: self._complete_future(
                completed_executor_future, completion
            )
        )

    @staticmethod
    def _complete_future(
        executor_future: Future[ResultT],
        completion: Future[ResultT],
    ):
        exception = executor_future.exception()
        if exception is not None:
            completion.set_exception(exception)
        else:
            completion.set_result(executor_future.result())


def process_definitions[ResultT](
    order: ReferenceGraphOrder,
    process_definition: Callable[[ast.QualityDefinition], ResultT],
    *,
    max_workers: int | None = None,
) -> list[ResultT]:
    """Process definitions concurrently after their references complete."""
    with _WorkPool(process_definition, max_workers) as pool:
        for definition_index, definition in enumerate(order.definitions):
            pool.submit(
                definition,
                order.referenced_definition_indexes(definition_index),
            )
        pool.wait()
        return pool.results()
