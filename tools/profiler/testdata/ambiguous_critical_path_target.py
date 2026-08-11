"""Create a completion handoff with two observable producer candidates."""

import os
import queue
import threading
import time

_PRE_WORK_NS = 500_000_000
_CRITICAL_WORK_NS = 800_000_000
_POST_WORK_NS = 500_000_000


def _cpu_work(duration_ns: int) -> int:
    # PRF-048: Critical-path fixture.
    deadline = time.thread_time_ns() + duration_ns
    value = 0
    while time.thread_time_ns() < deadline:
        value += 1
    return value


def _off_path_work(finish: threading.Event):
    # PRF-048: Critical-path fixture.
    _ = _cpu_work(_PRE_WORK_NS)
    _ = finish.wait()


def _critical_work(result_queue: queue.Queue[int]):
    # PRF-048: Critical-path fixture.
    result_queue.put(_cpu_work(_CRITICAL_WORK_NS))


# PRF-048: Critical-path fixture.
_finish = threading.Event()
_result_queue: queue.Queue[int] = queue.Queue()
_off_path_thread = threading.Thread(target=_off_path_work, args=(_finish,))
_off_path_thread.start()
_pre_work = _cpu_work(_PRE_WORK_NS)
_critical_thread = threading.Thread(target=_critical_work, args=(_result_queue,))
_critical_thread.start()
_result = _pre_work + _result_queue.get() + _cpu_work(_POST_WORK_NS)
_finish.set()
os._exit(0 if _result > 0 else 1)
