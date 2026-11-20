"""Test mutants on several workers at once."""

from __future__ import annotations

import collections
import concurrent.futures
import contextlib
import queue
import threading
import time
from typing import TYPE_CHECKING, Protocol, final

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence

    from tools.bazel_mutation_testing import coverage, mutant, results


class Tester(Protocol):
    """A worker that tests one mutant at a time."""

    def test(
        self, mutated: mutant.Mutant, selection: coverage.Selection, /
    ) -> results.Result:
        """Test `mutated` with the tests that `selection` chooses, and revert it."""
        ...

    def interrupt(self):
        """Stop the current mutant's tests, and refuse to test any more."""
        ...

    def kill(self):
        """Kill what runs the current mutant's tests, which an interrupt did not stop."""
        ...


# An interrupted tester's tests normally stop within seconds. Tests that are
# still running after this long are stuck.
_STOP_SECONDS = 60


def test_all(
    testers: Sequence[Tester],
    mutants: Sequence[mutant.Mutant],
    select: Callable[[mutant.Mutant], coverage.Selection],
    record: Callable[[results.Result], None],
):
    """Test each of `mutants` on a free tester, and record each result as it finishes.

    Each mutant runs the tests that `select` chooses for it.

    When a tester fails or the run is interrupted, every tester stops its
    mutant without a result and reverts it, and the error is raised. A resumed
    run then tests each stopped mutant again. A tester whose tests do not stop
    in time is killed.
    """
    schedule = _Schedule(mutants)
    finished: queue.SimpleQueue[results.Result | _Stopped] = queue.SimpleQueue()

    def test_until_done(tester: Tester):
        path = None
        try:
            while (mutated := schedule.take(path)) is not None:
                path = mutated.path
                finished.put(tester.test(mutated, select(mutated)))
        except BaseException as error:
            finished.put(_Stopped(error))
            raise
        finished.put(_Stopped(None))

    with concurrent.futures.ThreadPoolExecutor(len(testers)) as executor:
        futures = {
            executor.submit(test_until_done, tester): tester for tester in testers
        }
        try:
            _record_until_stopped(finished, len(testers), record)
        except BaseException:
            schedule.stop()
            for tester in testers:
                tester.interrupt()
            _wait_for_testers(futures)
            raise


def _record_until_stopped(
    finished: queue.SimpleQueue[results.Result | _Stopped],
    testers: int,
    record: Callable[[results.Result], None],
):
    """Record each result in `finished` until all `testers` have stopped.

    Raises the error of the first tester that fails.
    """
    running = testers
    while running:
        result = finished.get()
        if not isinstance(result, _Stopped):
            record(result)
            continue
        if result.error is not None:
            raise result.error
        running -= 1


@final
class _Stopped:
    """A tester has stopped taking mutants, because none are left or because it failed."""

    def __init__(self, error: BaseException | None):
        self.error = error


@final
class _Schedule:
    """Hands each tester the mutants of one file at a time.

    A tester that tests a file's mutants one after another rebuilds and
    rechecks only that file's dependents, rather than also those of the file
    it tested last. Testers spread across files, so that they don't all rebuild
    one file's dependents at once.
    """

    def __init__(self, mutants: Sequence[mutant.Mutant]):
        self._lock = threading.Lock()
        self._by_path: dict[str, collections.deque[mutant.Mutant]] = {}
        for listed in mutants:
            self._by_path.setdefault(listed.path, collections.deque()).append(listed)
        self._testers_on: collections.Counter[str] = collections.Counter()
        self._stopped = False

    def take(self, path: str | None) -> mutant.Mutant | None:
        """Return the next mutant for a tester that last tested a mutant of `path`.

        Returns None when no mutants are left, or the schedule is stopped.
        """
        with self._lock:
            if self._stopped:
                return None
            if path is not None and self._by_path.get(path):
                return self._by_path[path].popleft()
            if path is not None:
                self._testers_on[path] -= 1
            remaining = [listed for listed, queued in self._by_path.items() if queued]
            if not remaining:
                return None
            # min keeps the listing order among files with as many testers.
            chosen = min(remaining, key=lambda listed: self._testers_on[listed])
            self._testers_on[chosen] += 1
            return self._by_path[chosen].popleft()

    def stop(self):
        """Hand out no more mutants."""
        with self._lock:
            self._stopped = True


def _wait_for_testers(futures: Mapping[concurrent.futures.Future[None], Tester]):
    """Wait until every interrupted tester, by its future, has stopped and reverted its mutant.

    Kills each tester that has not stopped in time.
    """
    deadline = time.monotonic() + _STOP_SECONDS
    killed = False
    # The run removes each worktree next. A second interrupt must not end the
    # wait, since a worktree whose tester is still reverting has changes.
    while True:
        with contextlib.suppress(KeyboardInterrupt):
            timeout = None if killed else max(0.0, deadline - time.monotonic())
            _, running = concurrent.futures.wait(futures, timeout=timeout)
            if not running:
                return
            for future in running:
                futures[future].kill()
            killed = True
