"""Create a critical worker that waits from the process's first observation."""

import os
import queue
import threading
import time

_WORK_NS = 500_000_000


def _cpu_work() -> int:
    # PRF-048: Critical-path fixture.
    deadline = time.thread_time_ns() + _WORK_NS
    value = 0
    while time.thread_time_ns() < deadline:
        value += 1
    return value


def _waiting_worker(start: threading.Event, result_queue: queue.Queue[int]):
    # PRF-048: Critical-path fixture.
    _ = start.wait()
    result_queue.put(_cpu_work())


# PRF-048: Critical-path fixture.
_start = threading.Event()
_result_queue: queue.Queue[int] = queue.Queue()
_worker = threading.Thread(target=_waiting_worker, args=(_start, _result_queue))
_worker.start()
_pre_work = _cpu_work()
_start.set()
_result = _pre_work + _result_queue.get() + _cpu_work()
os._exit(0 if _result > 0 else 1)
