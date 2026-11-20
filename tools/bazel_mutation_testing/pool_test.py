from __future__ import annotations

import concurrent.futures
import threading
from typing import final

import pytest

from tools.bazel_mutation_testing import mutant, pool, results


class _TesterFailedError(Exception):
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


def _no_skipped_tests(_mutated: mutant.Mutant) -> frozenset[str]:
    return frozenset()


def _skipped_tests(mutated: mutant.Mutant) -> frozenset[str]:
    return frozenset({f"//skipped:{mutated.name.replace(' ', '_')}"})


@final
class _Tester:
    """Kills each mutant once every tester is testing one."""

    def __init__(self, all_testing: threading.Barrier):
        self.tested: list[str] = []
        self.skipped: list[frozenset[str]] = []
        self.interrupted = False
        self._all_testing = all_testing

    def test(self, mutated: mutant.Mutant, skipped: frozenset[str]) -> results.Result:
        _ = self._all_testing.wait(timeout=10)
        self.tested.append(mutated.name)
        self.skipped.append(skipped)
        return _killed(mutated)

    def interrupt(self):
        self.interrupted = True


@final
class _BlockedTester:
    """Tests one mutant until it is interrupted."""

    def __init__(self, testing: threading.Event):
        self.interrupted = threading.Event()
        self._testing = testing

    def test(self, mutated: mutant.Mutant, _skipped: frozenset[str]) -> results.Result:
        self._testing.set()
        _ = self.interrupted.wait(timeout=10)
        raise _TesterFailedError(mutated.name)

    def interrupt(self):
        self.interrupted.set()


@final
class _FailingTester:
    def __init__(self, testing: threading.Event):
        self._testing = testing

    def test(self, mutated: mutant.Mutant, _skipped: frozenset[str]) -> results.Result:
        _ = self._testing.wait(timeout=10)
        raise _TesterFailedError(mutated.name)

    def interrupt(self):
        pass


@final
class _RevertingTester:
    """Tests one mutant until it is interrupted, then reverts it."""

    def __init__(self, testing: threading.Event):
        self.reverted = threading.Event()
        self._interrupted = threading.Event()
        self._testing = testing

    def test(self, mutated: mutant.Mutant, _skipped: frozenset[str]) -> results.Result:
        self._testing.set()
        _ = self._interrupted.wait(timeout=10)
        self.reverted.set()
        raise _TesterFailedError(mutated.name)

    def interrupt(self):
        self._interrupted.set()


def test_testers_test_every_mutant_once_at_the_same_time():
    all_testing = threading.Barrier(2)
    testers = [_Tester(all_testing), _Tester(all_testing)]
    mutants = [_mutant(f"mutant {index}") for index in range(6)]
    recorded: list[results.Result] = []

    pool.test_all(testers, mutants, _skipped_tests, recorded.append)

    assert sorted(recorded, key=lambda result: result.name) == [
        _killed(mutated) for mutated in mutants
    ]
    assert [len(tester.tested) for tester in testers] == [3, 3]
    assert {skipped for tester in testers for skipped in tester.skipped} == {
        _skipped_tests(mutated) for mutated in mutants
    }
    assert not any(tester.interrupted for tester in testers)


def test_failed_tester_interrupts_the_others_and_records_nothing():
    testing = threading.Event()
    blocked = _BlockedTester(testing)
    recorded: list[results.Result] = []

    with pytest.raises(_TesterFailedError):
        pool.test_all(
            [blocked, _FailingTester(testing)],
            [_mutant("blocked"), _mutant("failing"), _mutant("third")],
            _no_skipped_tests,
            recorded.append,
        )

    assert blocked.interrupted.is_set()
    assert recorded == []


def test_second_interrupt_waits_for_testers_to_revert(monkeypatch: pytest.MonkeyPatch):
    testing = threading.Event()
    reverting = _RevertingTester(testing)
    waits: list[int] = []
    wait = concurrent.futures.wait

    def interrupted_once(
        futures: list[concurrent.futures.Future[results.Result]],
    ) -> object:
        waits.append(len(futures))
        if len(waits) == 1:
            raise KeyboardInterrupt
        return wait(futures)

    def interrupt_after_testing(result: results.Result):
        _ = testing.wait(timeout=10)
        raise KeyboardInterrupt(result.name)

    monkeypatch.setattr(concurrent.futures, "wait", interrupted_once)
    with pytest.raises(KeyboardInterrupt):
        pool.test_all(
            [reverting, _Tester(threading.Barrier(1))],
            [_mutant("reverting"), _mutant("killed")],
            _no_skipped_tests,
            interrupt_after_testing,
        )

    assert reverting.reverted.is_set()
    assert waits == [2, 2]
