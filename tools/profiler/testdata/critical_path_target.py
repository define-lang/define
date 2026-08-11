"""Event-controlled cross-thread completion-critical chain."""

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
    # PRF-048: Tests choose observation boundaries instead of wall-clock budgets.
    _ = status_stream.write(phase)
    while not release.is_set():
        value += 1
    return value + 1


def _stage_one_work(
    release: threading.Event,
    status_stream: typing.BinaryIO,
) -> int:
    # PRF-048: Critical-path fixture.
    return _controlled_work(release, status_stream, b"1", 0)


def _stage_one_worker(
    output_queue: queue.Queue[int],
    release: threading.Event,
    status_stream: typing.BinaryIO,
    finish: threading.Event,
) -> None:
    # PRF-048: Critical-path fixture.
    output_queue.put(_stage_one_work(release, status_stream))
    _ = finish.wait()


def _stage_two_work(
    value: int,
    release: threading.Event,
    status_stream: typing.BinaryIO,
) -> int:
    # PRF-048: Critical-path fixture.
    return _controlled_work(release, status_stream, b"2", value)


def _stage_three_work(
    value: int,
    release: threading.Event,
    status_stream: typing.BinaryIO,
) -> int:
    # PRF-048: Critical-path fixture.
    return _controlled_work(release, status_stream, b"3", value)


def _final_work(
    value: int,
    release: threading.Event,
    status_stream: typing.BinaryIO,
) -> int:
    # PRF-048: Critical-path fixture.
    return _controlled_work(release, status_stream, b"4", value)


def _stage_two_worker(
    input_queue: queue.Queue[int],
    stage_three_queue: queue.Queue[int],
    release: threading.Event,
    status_stream: typing.BinaryIO,
    finish: threading.Event,
) -> None:
    # PRF-048: Critical-path fixture.
    value = input_queue.get()
    stage_three_queue.put(_stage_two_work(value, release, status_stream))
    _ = finish.wait()


def _stage_three_worker(
    input_queue: queue.Queue[int],
    output_queue: queue.Queue[int],
    release: threading.Event,
    status_stream: typing.BinaryIO,
    finish: threading.Event,
) -> None:
    # PRF-048: Critical-path fixture.
    value = input_queue.get()
    output_queue.put(_stage_three_work(value, release, status_stream))
    _ = finish.wait()


def _off_path_work(finish: threading.Event) -> None:
    # PRF-048: Critical-path fixture.
    value = 0
    while not finish.is_set():
        value += 1


def _release_phases(
    control_stream: typing.BinaryIO,
    releases: tuple[threading.Event, ...],
) -> None:
    for release in releases:
        _ = control_stream.read(1)
        release.set()


_stage_two_queue: queue.Queue[int] = queue.Queue()
_stage_three_queue: queue.Queue[int] = queue.Queue()
_result_queue: queue.Queue[int] = queue.Queue()
_finish = threading.Event()
_releases = tuple(threading.Event() for _ in range(4))
with (
    open(sys.argv[1], "wb", buffering=0) as _status_stream,
    open(sys.argv[2], "rb", buffering=0) as _control_stream,
):
    threading.Thread(
        target=_release_phases,
        args=(_control_stream, _releases),
    ).start()
    for _thread in (
        threading.Thread(
            target=_stage_two_worker,
            args=(
                _stage_two_queue,
                _stage_three_queue,
                _releases[1],
                _status_stream,
                _finish,
            ),
        ),
        threading.Thread(
            target=_stage_three_worker,
            args=(
                _stage_three_queue,
                _result_queue,
                _releases[2],
                _status_stream,
                _finish,
            ),
        ),
        threading.Thread(
            target=_stage_one_worker,
            args=(_stage_two_queue, _releases[0], _status_stream, _finish),
        ),
        threading.Thread(target=_off_path_work, args=(_finish,)),
    ):
        _thread.start()
    _result = _final_work(
        _result_queue.get(),
        _releases[3],
        _status_stream,
    )
os._exit(0 if _result > 0 else 1)
