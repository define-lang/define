"""Concurrent lifecycle and sampling fixture for continuous wall profiling."""

import os
import threading
import time


def _retired_worker() -> None:
    # PRF-031: Retired-thread fixture.
    time.sleep(0.25)


def _deep_wait_level_two(release: threading.Event) -> None:
    # PRF-030: Stack-depth fixture. PRF-033: Waiting-thread fixture.
    _ = release.wait()


def _deep_wait_level_one(release: threading.Event) -> None:
    _deep_wait_level_two(release)


def _shallow_wait(release: threading.Event) -> None:
    # PRF-030: Stack-depth fixture. PRF-033: Waiting-thread fixture.
    _ = release.wait()


def _short_leaf(value: int) -> int:
    # PRF-029: Call-frequency fixture.
    return value + 1


def _high_call_frequency(deadline: float) -> None:
    value = 0
    while time.monotonic() < deadline:
        value = _short_leaf(value)


def _low_call_frequency(deadline: float) -> None:
    value = 0
    while time.monotonic() < deadline:
        for number in range(1000):
            value += number


# PRF-025: Failure threshold. The warmup yields a stress-sized denominator.
time.sleep(2.5)
_release = threading.Event()
_deadline = time.monotonic() + 2.2
_threads = [
    threading.Thread(target=_retired_worker),
    threading.Thread(target=_deep_wait_level_one, args=(_release,)),
    threading.Thread(target=_shallow_wait, args=(_release,)),
    threading.Thread(target=_high_call_frequency, args=(_deadline,)),
    threading.Thread(target=_low_call_frequency, args=(_deadline,)),
]
for _thread in _threads:
    _thread.start()
time.sleep(0.8)
_release.set()
for _thread in _threads:
    _thread.join()
time.sleep(0.2)
# A separate target owns shutdown races so this fixture isolates sampling bias.
os._exit(0)
