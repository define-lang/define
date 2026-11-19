"""Test mutants on several workers at once."""

from __future__ import annotations

import concurrent.futures
import contextlib
import queue
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from tools.bazel_mutation_testing import mutant, results


class Tester(Protocol):
    """A worker that tests one mutant at a time."""

    def test(self, mutated: mutant.Mutant) -> results.Result:
        """Test `mutated`, and revert it."""
        ...

    def interrupt(self):
        """Stop the current mutant's tests, and refuse to test any more."""
        ...


def test_all(
    testers: Sequence[Tester],
    mutants: Sequence[mutant.Mutant],
    record: Callable[[results.Result], None],
):
    """Test each of `mutants` on a free tester, and record each result as it finishes.

    When a tester fails or the run is interrupted, every tester stops its
    mutant without a result and reverts it, and the error is raised. A resumed
    run then tests each stopped mutant again.
    """
    idle: queue.SimpleQueue[Tester] = queue.SimpleQueue()
    for tester in testers:
        idle.put(tester)

    def test_on_idle_tester(mutated: mutant.Mutant) -> results.Result:
        # The pool runs as many mutants at once as there are testers, so a
        # tester is always idle here.
        tester = idle.get_nowait()
        try:
            return tester.test(mutated)
        finally:
            idle.put(tester)

    with concurrent.futures.ThreadPoolExecutor(len(testers)) as executor:
        futures = [executor.submit(test_on_idle_tester, mutated) for mutated in mutants]
        try:
            for future in concurrent.futures.as_completed(futures):
                record(future.result())
        except BaseException:
            for future in futures:
                _ = future.cancel()
            for tester in testers:
                tester.interrupt()
            _wait_for_testers(futures)
            raise


def _wait_for_testers(futures: Sequence[concurrent.futures.Future[results.Result]]):
    """Wait until every tester has stopped and reverted its mutant."""
    # The run removes each worktree next. A second interrupt must not end the
    # wait, since a worktree whose tester is still reverting has changes.
    while True:
        with contextlib.suppress(KeyboardInterrupt):
            _ = concurrent.futures.wait(futures)
            return
