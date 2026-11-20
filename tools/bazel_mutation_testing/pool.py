"""Test mutants on several workers at once."""

from __future__ import annotations

import collections
import concurrent.futures
import contextlib
import queue
import threading
import time
from typing import TYPE_CHECKING, NamedTuple, Protocol, final

from tools.bazel_mutation_testing import results

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence

    from tools.bazel_mutation_testing import coverage, mutant


class Tester(Protocol):
    """A worker that tests one mutant at a time."""

    name: str
    """The tester's name in the run's log."""

    def test(
        self, mutated: mutant.Mutant, selection: coverage.Selection, /
    ) -> results.Result:
        """Test `mutated` with the tests that `selection` chooses, and revert it."""
        ...

    def usable(self) -> bool:
        """Return whether the tester can test another mutant after it failed on one."""
        ...

    def interrupt(self):
        """Stop the current mutant's tests, and refuse to test any more."""
        ...

    def kill(self):
        """Kill what runs the current mutant's tests, which an interrupt did not stop."""
        ...


class RunFailedError(Exception):
    """The run's testers fail for a reason that they share."""


# An interrupted tester's tests normally stop within seconds. Tests that are
# still running after this long are stuck.
_STOP_SECONDS = 60

# A tester that fails on this many mutants that other testers then test is
# broken.
_STRIKES_TO_RETIRE = 2

# A mutant that fails on two testers rarely does so for a reason of its own.
# When this many mutants in a row fail on two testers each, they fail for a
# reason that every tester shares.
_ERRORS_TO_STOP = 3


def test_all(
    testers: Sequence[Tester],
    mutants: Sequence[mutant.Mutant],
    select: Callable[[mutant.Mutant], coverage.Selection],
    record: Callable[[results.Result], None],
    report: Callable[[str], None],
):
    """Test each of `mutants` on a free tester, and record each result as it finishes.

    Each mutant runs the tests that `select` chooses for it. `report` receives
    a message about each failure and each retired tester.

    A tester that fails on a mutant goes on to other mutants, and another
    tester tests the mutant again. A mutant that fails on two testers gets an
    error result, since the mutant causes the failure. A tester is retired when
    it is not usable after a failure, or when it has failed on mutants that
    other testers then tested.

    When the run fails or is interrupted, every tester stops its mutant without
    a result and reverts it. A resumed run then tests each stopped mutant
    again. A tester whose tests do not stop in time is killed.

    Raises:
        RunFailedError: Every tester was retired, or several mutants in a row
            failed on two testers each.
    """
    schedule = _Schedule(mutants)
    events: queue.SimpleQueue[_Event] = queue.SimpleQueue()

    def test_until_done(tester: Tester):
        try:
            while (mutated := schedule.take(tester)) is not None:
                if not test_one(tester, mutated):
                    break
        except BaseException as error:
            events.put(_Stopped(retired=False, error=error))
            raise
        events.put(_Stopped(retired=schedule.retired(tester), error=None))

    def test_one(tester: Tester, mutated: mutant.Mutant) -> bool:
        """Test `mutated` on `tester`, and return whether the tester goes on."""
        selection = select(mutated)
        try:
            result = tester.test(mutated, selection)
        # Every failure of a tester is handled alike, whatever its cause.
        except Exception as error:  # noqa: BLE001
            return report_failure(tester, mutated, error)
        events.put(result)
        failed_first = schedule.finish(mutated)
        if failed_first is not None:
            events.put(
                _Message(
                    f"{failed_first.name} is retired, since it failed on "
                    + f"{_STRIKES_TO_RETIRE} mutants that other workers then "
                    + "tested"
                )
            )
        return True

    def report_failure(
        tester: Tester, mutated: mutant.Mutant, error: Exception
    ) -> bool:
        """Report that `tester` failed on `mutated`, and return whether the tester goes on."""
        if schedule.fail(tester, mutated, error):
            events.put(_Errored(mutated, error))
        else:
            events.put(
                _Message(
                    f"{tester.name}: {mutated.name} failed, so another worker "
                    + f"tests it again: {_first_line(error)}"
                )
            )
        if tester.usable():
            return True
        schedule.retire(tester)
        events.put(
            _Message(f"{tester.name} is retired, since it is unusable after a failure")
        )
        return False

    with concurrent.futures.ThreadPoolExecutor(len(testers)) as executor:
        futures = {
            executor.submit(test_until_done, tester): tester for tester in testers
        }
        try:
            _record_run(events, schedule, len(testers), record, report)
        except BaseException:
            schedule.stop()
            for tester in testers:
                tester.interrupt()
            _wait_for_testers(futures)
            raise


def _record_run(
    events: queue.SimpleQueue[_Event],
    schedule: _Schedule,
    testers: int,
    record: Callable[[results.Result], None],
    report: Callable[[str], None],
):
    """Record each result in `events` until all `testers` have stopped, then record an error for each mutant that `schedule` could not test again.

    Raises:
        RunFailedError: Every tester was retired, or several mutants in a row
            failed on two testers each.
    """
    retired = _record_until_stopped(events, testers, record, report)
    if retired == testers:
        raise RunFailedError(
            "Every worker was retired, so they fail for a reason that they "
            + "share. The log shows each failure."
        )
    for mutated, error in schedule.untested_again():
        record(_error_result(mutated, error))
        report(
            f"{mutated.name} gets an error result, since no other worker was "
            + f"left to test it again:\n{error}"
        )


def _record_until_stopped(
    events: queue.SimpleQueue[_Event],
    testers: int,
    record: Callable[[results.Result], None],
    report: Callable[[str], None],
) -> int:
    """Record each result in `events` until all `testers` have stopped, and return how many were retired.

    Raises the error that stopped a tester outside its tests.

    Raises:
        RunFailedError: Several mutants in a row failed on two testers each.
    """
    running = testers
    retired = 0
    errors_in_row = 0
    while running:
        match events.get():
            case _Message(text):
                report(text)
            case _Errored(mutated, error):
                record(_error_result(mutated, error))
                report(
                    f"{mutated.name} failed on a second worker, so it gets an "
                    + f"error result:\n{error}"
                )
                errors_in_row += 1
                if errors_in_row == _ERRORS_TO_STOP:
                    raise RunFailedError(
                        f"{_ERRORS_TO_STOP} mutants in a row failed on two "
                        + "workers each, so they fail for a reason that every "
                        + "worker shares."
                    ) from error
            case _Stopped(stopped_retired, error):
                if error is not None:
                    raise error
                running -= 1
                retired += stopped_retired
            case result:
                record(result)
                errors_in_row = 0
    return retired


def _first_line(error: Exception) -> str:
    return str(error).partition("\n")[0]


def _error_result(mutated: mutant.Mutant, error: Exception) -> results.Result:
    return results.Result(
        name=mutated.name,
        outcome=results.Outcome.ERROR,
        culprit=_first_line(error),
        seconds=0.0,
    )


class _Message(NamedTuple):
    """A message for the run's log."""

    text: str


class _Errored(NamedTuple):
    """A mutant failed on a second tester."""

    mutated: mutant.Mutant
    error: Exception


class _Stopped(NamedTuple):
    """A tester has stopped taking mutants."""

    retired: bool
    error: BaseException | None
    """The error that stopped the tester outside its tests."""


type _Event = results.Result | _Message | _Errored | _Stopped


@final
class _Schedule:
    """Hands each tester the mutants of one file at a time, and the mutants that another tester failed on.

    A tester that tests a file's mutants one after another rebuilds and
    rechecks only that file's dependents, rather than also those of the file
    it tested last. Testers spread across files, so that they don't all rebuild
    one file's dependents at once.
    """

    def __init__(self, mutants: Sequence[mutant.Mutant]):
        self._condition = threading.Condition()
        self._by_path: dict[str, collections.deque[mutant.Mutant]] = {}
        for listed in mutants:
            self._by_path.setdefault(listed.path, collections.deque()).append(listed)
        self._testers_on: collections.Counter[str] = collections.Counter()
        self._path_of: dict[Tester, str] = {}
        self._first_failures: dict[str, tuple[Tester, Exception]] = {}
        self._to_test_again: list[mutant.Mutant] = []
        self._strikes: collections.Counter[Tester] = collections.Counter()
        self._busy: set[Tester] = set()
        self._retired: set[Tester] = set()
        self._stopped = False

    def take(self, tester: Tester) -> mutant.Mutant | None:
        """Return the next mutant for `tester`.

        While another tester could still fail on a mutant that `tester` would
        then test again, `tester` waits. Returns None when no mutant is left
        for `tester`, `tester` is retired, or the schedule is stopped.
        """
        with self._condition:
            self._busy.discard(tester)
            self._condition.notify_all()
            while True:
                if self._stopped or tester in self._retired:
                    return None
                chosen = self._to_test_again_by(tester)
                if chosen is None:
                    chosen = self._listed_for(tester)
                if chosen is not None:
                    self._busy.add(tester)
                    return chosen
                if not self._busy:
                    return None
                _ = self._condition.wait()

    def fail(self, tester: Tester, mutated: mutant.Mutant, error: Exception) -> bool:
        """Record that `tester` failed on `mutated` with `error`, and return whether another tester failed on it first.

        After a first failure, another tester tests `mutated` again.
        """
        with self._condition:
            if self._first_failures.pop(mutated.name, None) is not None:
                return True
            self._first_failures[mutated.name] = (tester, error)
            self._to_test_again.append(mutated)
            self._condition.notify_all()
            return False

    def finish(self, mutated: mutant.Mutant) -> Tester | None:
        """Record that a tester finished `mutated`, and return the tester that this retires.

        A tester that failed on `mutated` first gets a strike, and is retired
        after enough of them.
        """
        with self._condition:
            first_failure = self._first_failures.pop(mutated.name, None)
            if first_failure is None:
                return None
            failed_first = first_failure[0]
            self._strikes[failed_first] += 1
            if (
                self._strikes[failed_first] < _STRIKES_TO_RETIRE
                or failed_first in self._retired
            ):
                return None
            self._retired.add(failed_first)
            self._condition.notify_all()
            return failed_first

    def retire(self, tester: Tester):
        """Hand `tester`, which tests nothing now, no more mutants."""
        with self._condition:
            self._retired.add(tester)
            # The tester takes no more mutants, which would mark it idle.
            self._busy.discard(tester)
            self._condition.notify_all()

    def retired(self, tester: Tester) -> bool:
        """Return whether `tester` is retired."""
        with self._condition:
            return tester in self._retired

    def untested_again(self) -> list[tuple[mutant.Mutant, Exception]]:
        """Return each mutant that no other tester was left to test again, with the error it failed with."""
        with self._condition:
            return [
                (mutated, self._first_failures[mutated.name][1])
                for mutated in self._to_test_again
            ]

    def stop(self):
        """Hand out no more mutants."""
        with self._condition:
            self._stopped = True
            self._condition.notify_all()

    def _to_test_again_by(self, tester: Tester) -> mutant.Mutant | None:
        for index, mutated in enumerate(self._to_test_again):
            if self._first_failures[mutated.name][0] is not tester:
                del self._to_test_again[index]
                return mutated
        return None

    def _listed_for(self, tester: Tester) -> mutant.Mutant | None:
        path = self._path_of.get(tester)
        if path is not None and self._by_path.get(path):
            return self._by_path[path].popleft()
        if path is not None:
            self._testers_on[path] -= 1
            del self._path_of[tester]
        remaining = [listed for listed, queued in self._by_path.items() if queued]
        if not remaining:
            return None
        # min keeps the listing order among files with as many testers.
        chosen = min(remaining, key=lambda listed: self._testers_on[listed])
        self._testers_on[chosen] += 1
        self._path_of[tester] = chosen
        return self._by_path[chosen].popleft()


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
