"""A thread pool whose results are handled on the thread that runs it."""

from __future__ import annotations

import functools
import os
import queue
import threading
import typing

if typing.TYPE_CHECKING:
    from collections.abc import Callable


def _raise(exception: BaseException, _pool: WorkPool):
    raise exception


@typing.final
class WorkPool:
    """Runs work on worker threads and handles each result on the coordinator thread.

    Only the coordinator thread may submit work or run the pool.
    """

    def __init__(self, max_workers: int | None = None):
        """Initialize with pool configuration only — no side effects."""
        if max_workers is None:
            # TODO: This is ThreadPoolExecutor's default, which suits threads
            # that mostly wait on I/O. This work mostly uses the CPU, so the
            # CPU count may suit it better. Change it together with the same
            # default in graphs/reference_graph_executor.py.
            max_workers = min(32, (os.process_cpu_count() or 1) + 4)
        self._max_workers = max_workers
        self._pending = 0
        # Each item is work, its arguments, and its result handler. None tells
        # a worker thread to exit.
        self._work: queue.SimpleQueue[
            tuple[
                Callable[..., typing.Any],
                tuple[object, ...],
                Callable[[typing.Any, WorkPool], None],
            ]
            | None
        ] = queue.SimpleQueue()
        self._completed: queue.SimpleQueue[Callable[[WorkPool], None]] = (
            queue.SimpleQueue()
        )
        self._threads: list[threading.Thread] = []

    def __enter__(self) -> typing.Self:
        """Return the pool for use in a with statement."""
        return self

    def __exit__(self, *args: object):
        """Wait for the worker threads to finish."""
        for _ in self._threads:
            self._work.put(None)
        for thread in self._threads:
            thread.join()

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
        self._pending += 1
        # Starting threads only as pending work outnumbers them keeps a small
        # program from paying for a full pool.
        if len(self._threads) < min(self._pending, self._max_workers):
            thread = threading.Thread(target=self._run_worker)
            thread.start()
            self._threads.append(thread)
        # We don't use concurrent.futures.ThreadPoolExecutor because it creates
        # a Future for every task, and that overhead made this pool's caller
        # the bottleneck in large programs.
        self._work.put((work, args, handle_result))

    def _run_worker(self):
        while (item := self._work.get()) is not None:
            work, args, handle_result = item
            try:
                handle = functools.partial(handle_result, work(*args))
            # The coordinator thread raises it when it would handle the result.
            # Anything this thread doesn't relay would leave the coordinator
            # waiting for a result forever, so this catches BaseException too.
            except BaseException as exception:  # noqa: BLE001
                handle = functools.partial(_raise, exception)
            self._completed.put(handle)

    def run_until_idle(self):
        """Handle results as work completes, until no submitted work remains.

        Handlers may submit more work, which this also waits for. An exception
        raised by work is raised here when its result would be handled.
        """
        while self._pending:
            handle = self._completed.get()
            self._pending -= 1
            handle(self)
