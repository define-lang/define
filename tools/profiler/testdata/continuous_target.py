"""Event-controlled lifecycle fixture for continuous profiling."""

from __future__ import annotations

import os
import sys
import threading


def _retired_worker(start: threading.Event, retire: threading.Event) -> None:
    # PRF-031: Retired-thread fixture.
    _ = start.wait()
    _ = retire.wait()


def _deep_wait_level_two(start: threading.Event, finish: threading.Event) -> None:
    # PRF-030: Stack-depth fixture. PRF-033: Waiting-thread fixture.
    _ = start.wait()
    _ = finish.wait()


def _deep_wait_level_one(start: threading.Event, finish: threading.Event) -> None:
    _deep_wait_level_two(start, finish)


def _shallow_wait(start: threading.Event, finish: threading.Event) -> None:
    # PRF-030: Stack-depth fixture. PRF-033: Waiting-thread fixture.
    _ = start.wait()
    _ = finish.wait()


def _short_leaf(value: int) -> int:
    # PRF-029: Call-frequency fixture.
    return value + 1


def _high_call_frequency(start: threading.Event, finish: threading.Event) -> None:
    _ = start.wait()
    value = 0
    while not finish.is_set():
        value = _short_leaf(value)


def _low_call_frequency(start: threading.Event, finish: threading.Event) -> None:
    _ = start.wait()
    value = 0
    while not finish.is_set():
        for number in range(1000):
            value += number


_start = threading.Event()
_retire = threading.Event()
_finish = threading.Event()
_retired_thread = threading.Thread(
    target=_retired_worker,
    args=(_start, _retire),
)
_threads = [
    _retired_thread,
    threading.Thread(target=_deep_wait_level_one, args=(_start, _finish)),
    threading.Thread(target=_shallow_wait, args=(_start, _finish)),
    threading.Thread(target=_high_call_frequency, args=(_start, _finish)),
    threading.Thread(target=_low_call_frequency, args=(_start, _finish)),
]
for _thread in _threads:
    _thread.start()
_start.set()
if len(sys.argv) == 3:
    with (
        open(sys.argv[1], "wb", buffering=0) as _status_stream,
        open(sys.argv[2], "rb", buffering=0) as _control_stream,
    ):
        _ = _status_stream.write(b"1")
        _ = _control_stream.read(1)
        _retire.set()
        _retired_thread.join()
        _ = _status_stream.write(b"2")
        _ = _control_stream.read(1)
else:
    # Signal and profiler-error tests terminate this process externally.
    _ = threading.Event().wait()
os._exit(0)
