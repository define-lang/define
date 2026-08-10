"""Deterministic scheduler-runtime accuracy fixture for CPU profiling."""

import collections.abc
import os
import threading
import time

_CPU_BUDGET_NS = 400_000_000
_PARALLEL_CPU_BUDGET_NS = 8_000_000_000
_SHORT_LEAF_NS = 300_000


def _tiny_leaf(value: int) -> int:
    # PRF-029: Call-frequency fixture.
    return value + 1


def _high_call_frequency(start: threading.Event):
    _ = start.wait()
    deadline = time.thread_time_ns() + _CPU_BUDGET_NS
    value = 0
    while time.thread_time_ns() < deadline:
        value = _tiny_leaf(value)


def _low_call_frequency(start: threading.Event):
    _ = start.wait()
    deadline = time.thread_time_ns() + _CPU_BUDGET_NS
    value = 0
    while time.thread_time_ns() < deadline:
        for number in range(1000):
            value += number


def _deep_work_level_two(deadline: int):
    # PRF-030: Stack-depth fixture.
    value = 0
    while time.thread_time_ns() < deadline:
        value += 1


def _deep_work_level_one(start: threading.Event):
    _ = start.wait()
    _deep_work_level_two(time.thread_time_ns() + _CPU_BUDGET_NS)


def _shallow_work(start: threading.Event):
    # PRF-030: Stack-depth fixture.
    _ = start.wait()
    deadline = time.thread_time_ns() + _CPU_BUDGET_NS
    value = 0
    while time.thread_time_ns() < deadline:
        value += 1


def _short_leaf():
    # PRF-035: Short-function fixture.
    deadline = time.thread_time_ns() + _SHORT_LEAF_NS
    value = 0
    while time.thread_time_ns() < deadline:
        value += 1


def _repeated_short_leaves(start: threading.Event):
    _ = start.wait()
    deadline = time.thread_time_ns() + _CPU_BUDGET_NS
    while time.thread_time_ns() < deadline:
        _short_leaf()


def _parallel_worker_one(start: threading.Event):
    # PRF-034: Parallel-CPU fixture.
    _ = start.wait()
    deadline = time.thread_time_ns() + _PARALLEL_CPU_BUDGET_NS
    value = 0
    while time.thread_time_ns() < deadline:
        value += 1


def _parallel_worker_two(start: threading.Event):
    # PRF-034: Parallel-CPU fixture.
    _ = start.wait()
    deadline = time.thread_time_ns() + _PARALLEL_CPU_BUDGET_NS
    value = 0
    while time.thread_time_ns() < deadline:
        value += 1


def _waiting_worker(start: threading.Event, finish: threading.Event):
    # PRF-033: Waiting-thread fixture.
    _ = start.wait()
    _ = finish.wait()


def _run_cpu_worker(
    worker: collections.abc.Callable[[threading.Event], None],
    start: threading.Event,
    done: threading.Event,
    finish: threading.Event,
):
    worker(start)
    done.set()
    # Keeping completed workers alive isolates CPU accuracy from retirement races.
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
)
_done_events = [threading.Event() for _worker in _workers]
_cpu_threads = [
    threading.Thread(
        target=_run_cpu_worker,
        args=(worker, _start, done, _finish),
    )
    for worker, done in zip(_workers, _done_events, strict=True)
]
_waiting_thread = threading.Thread(
    target=_waiting_worker,
    args=(_start, _finish),
)
for _thread in [*_cpu_threads, _waiting_thread]:
    _thread.start()
_start.set()
for _done in _done_events:
    _ = _done.wait()
# Process-wide exit prevents fixture cleanup from becoming measured CPU work.
os._exit(0)
