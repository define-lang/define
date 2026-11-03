"""A thread pool whose results are handled on the thread that runs it."""

from __future__ import annotations

import functools
import queue
import typing
from concurrent.futures import ThreadPoolExecutor

if typing.TYPE_CHECKING:
    from collections.abc import Callable
    from concurrent.futures import Future


def _handle_result[ResultT](
    handle_result: Callable[[ResultT, WorkPool], None],
    pool: WorkPool,
    done: Future[ResultT],
):
    handle_result(done.result(), pool)


@typing.final
class WorkPool:
    """Runs work on worker threads and handles each result on the coordinator thread.

    Only the coordinator thread may submit work or run the pool.
    """

    def __init__(self, max_workers: int | None = None):
        """Initialize with pool configuration only — no side effects."""
        self._pending = 0
        self._completed: queue.SimpleQueue[Callable[[], None]] = queue.SimpleQueue()
        self._executor = ThreadPoolExecutor(max_workers=max_workers)

    def __enter__(self) -> typing.Self:
        """Return the pool for use in a with statement."""
        return self

    def __exit__(self, *args: object):
        """Wait for the worker threads to finish."""
        self._executor.shutdown(wait=True)

    def submit[*ArgsT, ResultT](
        self,
        work: Callable[[*ArgsT], ResultT],
        *args: *ArgsT,
        handle_result: Callable[[ResultT, WorkPool], None],
    ):
        """Start work on a worker thread, and have the coordinator thread handle its result.

        handle_result receives the result and this pool, so that it can submit
        more work.
        """
        future = self._executor.submit(work, *args)
        self._pending += 1
        # add_done_callback pushes from the worker thread the moment work
        # finishes, so no completion waits on another one and collecting a
        # completion costs O(1). Scanning every still-pending future instead
        # made the coordinator quadratic in the number of files in the program.
        future.add_done_callback(
            lambda done: self._completed.put(
                functools.partial(_handle_result, handle_result, self, done)
            )
        )

    def run_until_idle(self):
        """Handle results as work completes, until no submitted work remains.

        Handlers may submit more work, which this also waits for. An exception
        raised by work is raised here when its result would be handled.
        """
        while self._pending:
            handle = self._completed.get()
            self._pending -= 1
            handle()
