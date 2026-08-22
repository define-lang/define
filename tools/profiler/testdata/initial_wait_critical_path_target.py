"""Event-controlled critical worker waiting from the first observation."""

from __future__ import annotations

import os
import queue
import sys
import threading
import typing


def _controlled_work(
    release: threading.Event,
    status_stream: typing.BinaryIO,
    phase: bytes,
    value: int,
) -> int:
    _ = status_stream.write(phase)
    while not release.is_set():
        value += 1
    return value + 1


def _release_phases(
    control_stream: typing.BinaryIO,
    releases: tuple[threading.Event, ...],
) -> None:
    for release in releases:
        _ = control_stream.read(1)
        release.set()


def _waiting_worker(
    start: threading.Event,
    release: threading.Event,
    status_stream: typing.BinaryIO,
    result_queue: queue.Queue[int],
    finish: threading.Event,
) -> None:
    _ = start.wait()
    result_queue.put(_controlled_work(release, status_stream, b"2", 0))
    _ = finish.wait()


_start = threading.Event()
_finish = threading.Event()
_releases = tuple(threading.Event() for _ in range(3))
_result_queue: queue.Queue[int] = queue.Queue()
with (
    open(sys.argv[1], "wb", buffering=0) as _status_stream,
    open(sys.argv[2], "rb", buffering=0) as _control_stream,
):
    threading.Thread(
        target=_release_phases,
        args=(_control_stream, _releases),
    ).start()
    threading.Thread(
        target=_waiting_worker,
        args=(_start, _releases[1], _status_stream, _result_queue, _finish),
    ).start()
    _result = _controlled_work(_releases[0], _status_stream, b"1", 0)
    _start.set()
    _result += _result_queue.get()
    _result = _controlled_work(_releases[2], _status_stream, b"3", _result)
os._exit(0 if _result > 0 else 1)
