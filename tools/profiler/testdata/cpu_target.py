"""Event-controlled scheduler-runtime fixture for CPU profiling."""

import os
import sys
import threading


def _tiny_leaf(value: int) -> int:
    # PRF-029: Call-frequency fixture.
    return value + 1


def _high_call_frequency(start: threading.Event, finish: threading.Event) -> None:
    _ = start.wait()
    value = 0
    while not finish.is_set():
        value = _tiny_leaf(value)


def _low_call_frequency(start: threading.Event, finish: threading.Event) -> None:
    _ = start.wait()
    value = 0
    while not finish.is_set():
        for number in range(1000):
            value += number


def _deep_work_level_two(finish: threading.Event) -> None:
    # PRF-030: Stack-depth fixture.
    value = 0
    while not finish.is_set():
        value += 1


def _deep_work_level_one(start: threading.Event, finish: threading.Event) -> None:
    _ = start.wait()
    _deep_work_level_two(finish)


def _shallow_work(start: threading.Event, finish: threading.Event) -> None:
    # PRF-030: Stack-depth fixture.
    _ = start.wait()
    value = 0
    while not finish.is_set():
        value += 1


def _short_leaf(value: int) -> int:
    # PRF-035: Short-function fixture.
    return value + 1


def _repeated_short_leaves(start: threading.Event, finish: threading.Event) -> None:
    _ = start.wait()
    value = 0
    while not finish.is_set():
        value = _short_leaf(value)


def _parallel_worker_one(start: threading.Event, finish: threading.Event) -> None:
    # PRF-034: Parallel-CPU fixture.
    _ = start.wait()
    value = 0
    while not finish.is_set():
        value += 1


def _parallel_worker_two(start: threading.Event, finish: threading.Event) -> None:
    # PRF-034: Parallel-CPU fixture.
    _ = start.wait()
    value = 0
    while not finish.is_set():
        value += 1


def _waiting_worker(start: threading.Event, finish: threading.Event) -> None:
    # PRF-033: Waiting-thread fixture.
    _ = start.wait()
    _ = finish.wait()


_start = threading.Event()
_finish = threading.Event()
_workers = (
    _high_call_frequency,
    _low_call_frequency,
    _deep_work_level_one,
    _shallow_work,
    _repeated_short_leaves,
    _parallel_worker_one,
    _parallel_worker_two,
    _waiting_worker,
)
_threads = [
    threading.Thread(target=worker, args=(_start, _finish)) for worker in _workers
]
for _thread in _threads:
    _thread.start()
_start.set()
with open(sys.argv[1], "rb") as _finish_gate:
    _ = _finish_gate.read(1)
os._exit(0)
