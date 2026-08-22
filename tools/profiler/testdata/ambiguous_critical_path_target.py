"""Event-controlled completion handoff with two producer candidates."""

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


def _off_path_work(release: threading.Event, finish: threading.Event) -> None:
    value = 0
    while not release.is_set():
        value += 1
    _ = finish.wait()


def _critical_work(
    release: threading.Event,
    status_stream: typing.BinaryIO,
    result_queue: queue.Queue[int],
    finish: threading.Event,
) -> None:
    result_queue.put(_controlled_work(release, status_stream, b"2", 0))
    _ = finish.wait()


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
    threading.Thread(target=_off_path_work, args=(_releases[0], _finish)).start()
    _result = _controlled_work(_releases[0], _status_stream, b"1", 0)
    threading.Thread(
        target=_critical_work,
        args=(_releases[1], _status_stream, _result_queue, _finish),
    ).start()
    _result += _result_queue.get()
    _result = _controlled_work(_releases[2], _status_stream, b"3", _result)
os._exit(0 if _result > 0 else 1)
