"""Concurrent lifecycle and sampling fixture for continuous wall profiling."""

import os
import sys
import threading
import time


def _retired_worker() -> None:
    # PRF-031: Retired-thread fixture.
    time.sleep(0.25)


def _start_retired_worker(start: threading.Event) -> None:
    _ = start.wait()
    _retired_worker()


def _deep_wait_level_two(start: threading.Event, release: threading.Event) -> None:
    # PRF-030: Stack-depth fixture. PRF-033: Waiting-thread fixture.
    _ = start.wait()
    _ = release.wait()


def _deep_wait_level_one(start: threading.Event, release: threading.Event) -> None:
    _deep_wait_level_two(start, release)


def _shallow_wait(start: threading.Event, release: threading.Event) -> None:
    # PRF-030: Stack-depth fixture. PRF-033: Waiting-thread fixture.
    _ = start.wait()
    _ = release.wait()


def _short_leaf(value: int) -> int:
    # PRF-029: Call-frequency fixture.
    return value + 1


def _high_call_frequency(start: threading.Event) -> None:
    _ = start.wait()
    deadline = time.monotonic() + 2.2
    value = 0
    while time.monotonic() < deadline:
        value = _short_leaf(value)


def _low_call_frequency(start: threading.Event) -> None:
    _ = start.wait()
    deadline = time.monotonic() + 2.2
    value = 0
    while time.monotonic() < deadline:
        for number in range(1000):
            value += number


def _cpu_warmup(duration_ns: int):
    # PRF-025: Failure threshold. Target CPU time excludes profiler pauses so
    # the fixture always yields a stress-sized observation denominator.
    deadline = time.thread_time_ns() + duration_ns
    while time.thread_time_ns() < deadline:
        pass


_cpu_warmup(4_000_000_000)
_start = threading.Event()
_release = threading.Event()
_threads = [
    threading.Thread(target=_start_retired_worker, args=(_start,)),
    threading.Thread(target=_deep_wait_level_one, args=(_start, _release)),
    threading.Thread(target=_shallow_wait, args=(_start, _release)),
    threading.Thread(target=_high_call_frequency, args=(_start,)),
    threading.Thread(target=_low_call_frequency, args=(_start,)),
]
for _thread in _threads:
    _thread.start()
if len(sys.argv) > 1:
    # The public-binary test releases this after observing every waiting worker.
    with open(sys.argv[1], "rb") as _profiler_gate:
        _ = _profiler_gate.read(1)
_start.set()
time.sleep(0.8)
_release.set()
for _thread in _threads:
    _thread.join()
time.sleep(0.2)
# A separate target owns shutdown races so this fixture isolates sampling bias.
os._exit(0)
