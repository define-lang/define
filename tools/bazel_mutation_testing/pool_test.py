from __future__ import annotations

import concurrent.futures
import threading
from typing import final

import pytest

from tools.bazel_mutation_testing import coverage, mutant, pool, results


class _TesterFailedError(Exception):
    pass


class _SelectError(Exception):
    pass


def _mutant(name: str) -> mutant.Mutant:
    return mutant.Mutant(name=name, path="lib.rs", patch="", lines=(1, 1))


def _killed(mutated: mutant.Mutant) -> results.Result:
    return results.Result(
        name=mutated.name,
        outcome=results.Outcome.KILLED,
        culprit="//:test",
        seconds=0.0,
    )


def _errored(name: str) -> results.Result:
    return results.Result(
        name=name, outcome=results.Outcome.ERROR, culprit=name, seconds=0.0
    )


def _no_skipped_tests(_mutated: mutant.Mutant) -> coverage.Selection:
    return coverage.Selection(skipped=frozenset(), covering_tests=None)


def _skipped_tests(mutated: mutant.Mutant) -> coverage.Selection:
    skipped = f"//skipped:{mutated.name.replace(' ', '_')}"
    return coverage.Selection(skipped=frozenset({skipped}), covering_tests=1)


def _by_name(recorded: list[results.Result]) -> list[results.Result]:
    return sorted(recorded, key=lambda result: result.name)


@final
class _Tester:
    """Kills each mutant once every tester is testing one."""

    def __init__(self, all_testing: threading.Barrier):
        self.name = "worker"
        self.tested: list[str] = []
        self.skipped: list[coverage.Selection] = []
        self.interrupted = False
        self._all_testing = all_testing

    def test(
        self, mutated: mutant.Mutant, skipped: coverage.Selection
    ) -> results.Result:
        _ = self._all_testing.wait(timeout=10)
        self.tested.append(mutated.name)
        self.skipped.append(skipped)
        return _killed(mutated)

    def usable(self) -> bool:
        return True

    def interrupt(self):
        self.interrupted = True

    def kill(self):
        pass


@final
class _ScriptedTester:
    """Fails on the mutants named in `failing`, and kills the others."""

    def __init__(
        self,
        name: str,
        failing: frozenset[str],
        *,
        usable: bool = True,
        start: threading.Event | None = None,
    ):
        """Create the tester `name`, which waits for `start` before each mutant."""
        self.name = name
        self.failed = threading.Event()
        self._failing = failing
        self._usable = usable
        self._start = start
        self._failures = 0

    def test(
        self, mutated: mutant.Mutant, _skipped: coverage.Selection
    ) -> results.Result:
        if self._start is not None:
            _ = self._start.wait(timeout=10)
        if mutated.name not in self._failing:
            return _killed(mutated)
        self._failures += 1
        if self._failures == 2:
            self.failed.set()
        raise _TesterFailedError(mutated.name)

    def usable(self) -> bool:
        return self._usable

    def interrupt(self):
        pass

    def kill(self):
        pass


@final
class _BlockedTester:
    """Tests one mutant until it is interrupted."""

    def __init__(self, name: str):
        self.name = name
        self.interrupted = threading.Event()

    def test(
        self, mutated: mutant.Mutant, _skipped: coverage.Selection
    ) -> results.Result:
        _ = self.interrupted.wait(timeout=10)
        raise _TesterFailedError(mutated.name)

    def usable(self) -> bool:
        return False

    def interrupt(self):
        self.interrupted.set()

    def kill(self):
        pass


@final
class _RevertingTester:
    """Tests one mutant until it is interrupted, then reverts it."""

    def __init__(self, testing: threading.Event):
        self.name = "reverting"
        self.reverted = threading.Event()
        self._interrupted = threading.Event()
        self._testing = testing

    def test(
        self, mutated: mutant.Mutant, _skipped: coverage.Selection
    ) -> results.Result:
        self._testing.set()
        _ = self._interrupted.wait(timeout=10)
        self.reverted.set()
        raise _TesterFailedError(mutated.name)

    def usable(self) -> bool:
        return False

    def interrupt(self):
        self._interrupted.set()

    def kill(self):
        pass


@final
class _StuckTester:
    """Tests one mutant until it is killed, since an interrupt does not stop it."""

    def __init__(self, testing: threading.Event):
        self.name = "stuck"
        self.killed = threading.Event()
        self._testing = testing

    def test(
        self, mutated: mutant.Mutant, _skipped: coverage.Selection
    ) -> results.Result:
        self._testing.set()
        _ = self.killed.wait(timeout=10)
        raise _TesterFailedError(mutated.name)

    def usable(self) -> bool:
        return False

    def interrupt(self):
        pass

    def kill(self):
        self.killed.set()


def _interrupt_after(testing: threading.Event):
    def record(result: results.Result):
        _ = testing.wait(timeout=10)
        raise KeyboardInterrupt(result.name)

    return record


def test_testers_test_every_mutant_once_at_the_same_time():
    all_testing = threading.Barrier(2)
    testers = [_Tester(all_testing), _Tester(all_testing)]
    mutants = [_mutant(f"mutant {index}") for index in range(6)]
    recorded: list[results.Result] = []

    pool.test_all(testers, mutants, _skipped_tests, recorded.append, print)

    assert _by_name(recorded) == [_killed(mutated) for mutated in mutants]
    assert [len(tester.tested) for tester in testers] == [3, 3]
    assert {skipped for tester in testers for skipped in tester.skipped} == {
        _skipped_tests(mutated) for mutated in mutants
    }
    assert not any(tester.interrupted for tester in testers)


def test_each_tester_keeps_to_one_file_while_it_has_mutants():
    all_testing = threading.Barrier(2)
    testers = [_Tester(all_testing), _Tester(all_testing)]
    mutants = [
        mutant.Mutant(name=f"{path} {index}", path=path, patch="", lines=(1, 1))
        for path in ("a.rs", "b.rs")
        for index in range(3)
    ]

    pool.test_all(testers, mutants, _no_skipped_tests, lambda _result: None, print)

    assert sorted(tester.tested for tester in testers) == [
        ["a.rs 0", "a.rs 1", "a.rs 2"],
        ["b.rs 0", "b.rs 1", "b.rs 2"],
    ]


def test_a_mutant_that_fails_on_two_testers_gets_an_error_result():
    recorded: list[results.Result] = []

    pool.test_all(
        [
            _ScriptedTester("worker-a", frozenset({"bad"})),
            _ScriptedTester("worker-b", frozenset({"bad"})),
        ],
        [_mutant("bad")],
        _no_skipped_tests,
        recorded.append,
        print,
    )

    assert recorded == [_errored("bad")]


def test_a_tester_whose_failed_mutants_pass_elsewhere_is_retired():
    mutants = [_mutant(f"mutant {index}") for index in range(4)]
    failing = _ScriptedTester(
        "worker-a", frozenset(mutated.name for mutated in mutants)
    )
    # The other tester waits until the failing one has failed twice, so that
    # it tests those mutants again.
    passing = _ScriptedTester("worker-b", frozenset(), start=failing.failed)
    recorded: list[results.Result] = []
    reported: list[str] = []

    pool.test_all(
        [failing, passing], mutants, _no_skipped_tests, recorded.append, reported.append
    )

    assert _by_name(recorded) == [_killed(mutated) for mutated in mutants]
    assert (
        "worker-a is retired, since it failed on 2 mutants that other workers "
        + "then tested"
    ) in reported


def test_an_unusable_tester_is_retired_and_its_mutant_tested_again():
    mutants = [_mutant("mutant 0"), _mutant("mutant 1")]
    unusable = _ScriptedTester(
        "worker-a", frozenset(mutated.name for mutated in mutants), usable=False
    )
    started = threading.Event()
    passing = _ScriptedTester("worker-b", frozenset(), start=started)
    recorded: list[results.Result] = []
    reported: list[str] = []

    def report(message: str):
        reported.append(message)
        started.set()

    pool.test_all(
        [unusable, passing], mutants, _no_skipped_tests, recorded.append, report
    )

    assert _by_name(recorded) == [_killed(mutated) for mutated in mutants]
    assert "worker-a is retired, since it is unusable after a failure" in reported


def test_a_run_whose_testers_are_all_retired_fails():
    recorded: list[results.Result] = []

    with pytest.raises(pool.RunFailedError):
        pool.test_all(
            [
                _ScriptedTester("worker-a", frozenset({"bad"}), usable=False),
                _ScriptedTester("worker-b", frozenset({"bad"}), usable=False),
            ],
            [_mutant("bad")],
            _no_skipped_tests,
            recorded.append,
            print,
        )

    assert recorded == [_errored("bad")]


def test_mutants_that_fail_on_two_testers_in_a_row_stop_the_run():
    names = frozenset(f"mutant {index}" for index in range(3))
    recorded: list[results.Result] = []

    with pytest.raises(pool.RunFailedError):
        pool.test_all(
            [_ScriptedTester("worker-a", names), _ScriptedTester("worker-b", names)],
            [_mutant(name) for name in sorted(names)],
            _no_skipped_tests,
            recorded.append,
            print,
        )

    assert _by_name(recorded) == [_errored(name) for name in sorted(names)]


def test_a_lone_tester_gives_a_mutant_it_failed_on_an_error_result():
    recorded: list[results.Result] = []

    pool.test_all(
        [_ScriptedTester("worker-a", frozenset({"bad"}))],
        [_mutant("bad"), _mutant("good")],
        _no_skipped_tests,
        recorded.append,
        print,
    )

    assert _by_name(recorded) == [_errored("bad"), _killed(_mutant("good"))]


def test_an_error_outside_the_tests_stops_every_tester():
    testers = [_BlockedTester("worker-a"), _BlockedTester("worker-b")]
    recorded: list[results.Result] = []

    def select(mutated: mutant.Mutant) -> coverage.Selection:
        if mutated.name == "broken":
            raise _SelectError(mutated.name)
        return _no_skipped_tests(mutated)

    with pytest.raises(_SelectError):
        pool.test_all(
            testers,
            [_mutant("blocked"), _mutant("broken")],
            select,
            recorded.append,
            print,
        )

    assert all(tester.interrupted.is_set() for tester in testers)
    assert recorded == []


def test_second_interrupt_waits_for_testers_to_revert(monkeypatch: pytest.MonkeyPatch):
    testing = threading.Event()
    reverting = _RevertingTester(testing)
    waits: list[int] = []
    wait = concurrent.futures.wait

    def interrupted_once(
        futures: list[concurrent.futures.Future[None]], timeout: float | None
    ) -> tuple[
        set[concurrent.futures.Future[None]], set[concurrent.futures.Future[None]]
    ]:
        waits.append(len(futures))
        if len(waits) == 1:
            raise KeyboardInterrupt
        return wait(futures, timeout=timeout)

    monkeypatch.setattr(concurrent.futures, "wait", interrupted_once)
    with pytest.raises(KeyboardInterrupt):
        pool.test_all(
            [reverting, _Tester(threading.Barrier(1))],
            [_mutant("reverting"), _mutant("killed")],
            _no_skipped_tests,
            _interrupt_after(testing),
            print,
        )

    assert reverting.reverted.is_set()
    assert waits == [2, 2]


def test_a_tester_that_does_not_stop_in_time_is_killed(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(pool, "_STOP_SECONDS", 0)
    testing = threading.Event()
    stuck = _StuckTester(testing)

    with pytest.raises(KeyboardInterrupt):
        pool.test_all(
            [stuck, _Tester(threading.Barrier(1))],
            [_mutant("stuck"), _mutant("killed")],
            _no_skipped_tests,
            _interrupt_after(testing),
            print,
        )

    assert stuck.killed.is_set()
