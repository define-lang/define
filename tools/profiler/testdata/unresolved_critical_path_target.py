"""Event-controlled handoff whose producer is external to the target."""

import os
import sys
import threading
import typing


def _release_finish(
    control_stream: typing.BinaryIO,
    finish: threading.Event,
) -> None:
    _ = control_stream.read(1)
    finish.set()


def _wait_for_external_release(control_stream: typing.BinaryIO) -> None:
    _ = control_stream.read(1)


_finish = threading.Event()
with (
    open(sys.argv[1], "wb", buffering=0) as _status_stream,
    open(sys.argv[2], "rb", buffering=0) as _control_stream,
):
    _ = _status_stream.write(b"1")
    _wait_for_external_release(_control_stream)
    threading.Thread(
        target=_release_finish,
        args=(_control_stream, _finish),
    ).start()
    _ = _status_stream.write(b"2")
    _result = 0
    while not _finish.is_set():
        _result += 1
os._exit(0 if _result > 0 else 1)
