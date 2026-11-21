from __future__ import annotations

import threading
import typing
from collections import UserDict

from define.compiler.data_structures import computed_once

if typing.TYPE_CHECKING:
    import pytest


def test_a_thread_that_needs_a_value_being_computed_waits_for_it(
    monkeypatch: pytest.MonkeyPatch,
):
    values: computed_once.ComputedOnce[str, int] = computed_once.ComputedOnce()
    first_is_computing = threading.Event()
    finish_first = threading.Event()
    second_is_waiting = threading.Event()
    computations: list[str] = []

    def compute_slowly() -> int:
        computations.append("key")
        # A second computation fails the test, so only the first one waits.
        if len(computations) == 1:
            first_is_computing.set()
            _ = finish_first.wait()
        return 1

    class _Locks(UserDict[str, threading.Lock]):
        """Signals when a thread gets a key's lock while another thread computes the key's value."""

        @typing.override
        def setdefault(self, key: str, default: threading.Lock) -> threading.Lock:
            lock = super().setdefault(key, default)
            if first_is_computing.is_set():
                second_is_waiting.set()
            return lock

    monkeypatch.setattr(values, "_locks", _Locks())
    results: list[int] = []

    def get_then_set(finished: threading.Event):
        # A thread that ends without reaching the step that sets its event
        # still sets the event, so that the test fails instead of hanging.
        try:
            results.append(values.get("key", compute_slowly))
        finally:
            finished.set()

    first = threading.Thread(target=get_then_set, args=(first_is_computing,))
    first.start()
    _ = first_is_computing.wait()
    # The second thread finds no value yet, so it waits for the first thread's
    # lock, and then finds the value that the first thread stored.
    second = threading.Thread(target=get_then_set, args=(second_is_waiting,))
    second.start()
    _ = second_is_waiting.wait()
    finish_first.set()
    first.join()
    second.join()

    assert computations == ["key"]
    assert results == [1, 1]


def test_a_value_of_none_is_computed_once():
    values: computed_once.ComputedOnce[str, None] = computed_once.ComputedOnce()
    computations: list[str] = []

    def compute():
        computations.append("key")

    _ = values.get("key", compute)
    _ = values.get("key", compute)

    assert computations == ["key"]
    assert list(values.items()) == [("key", None)]
