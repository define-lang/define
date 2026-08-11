"""Known cross-thread completion-critical chain for wall profiling."""

import os
import queue
import sys
import threading
import time

_WORK_NS = 800_000_000
_OFF_PATH_WORK_NS = 5_000_000_000


def _cpu_work(duration_ns: int) -> int:
    # PRF-048: Critical-path fixture.
    deadline = time.thread_time_ns() + duration_ns
    value = 0
    while time.thread_time_ns() < deadline:
        value += 1
    return value


def _stage_one_work() -> int:
    # PRF-048: Critical-path fixture.
    return _cpu_work(_WORK_NS)


def _stage_one_worker(
    output_queue: queue.Queue[int],
    start: threading.Event,
):
    # PRF-048: Critical-path fixture.
    _ = start.wait()
    output_queue.put(_stage_one_work() + 1)


def _stage_two_work(value: int) -> int:
    # PRF-048: Critical-path fixture.
    return value + _cpu_work(_WORK_NS)


def _stage_three_work(value: int) -> int:
    # PRF-048: Critical-path fixture.
    return value + _cpu_work(_WORK_NS)


def _final_work(value: int) -> int:
    # PRF-048: Critical-path fixture.
    return value + _cpu_work(_WORK_NS)


def _stage_two_worker(
    input_queue: queue.Queue[int],
    stage_three_queue: queue.Queue[int],
    finish: threading.Event,
):
    # PRF-048: Critical-path fixture.
    value = input_queue.get()
    stage_three_queue.put(_stage_two_work(value))
    _ = finish.wait()


def _stage_three_worker(
    input_queue: queue.Queue[int],
    output_queue: queue.Queue[int],
):
    # PRF-048: Critical-path fixture.
    value = input_queue.get()
    output_queue.put(_stage_three_work(value))


def _off_path_work(finish: threading.Event):
    # PRF-048: Critical-path fixture.
    _ = _cpu_work(_OFF_PATH_WORK_NS)
    _ = finish.wait()


def _wait_for_final_result(result_queue: queue.Queue[int]) -> int:
    # PRF-048: Critical-path fixture.
    return result_queue.get()


# PRF-048: Critical-path fixture.
_stage_two_queue: queue.Queue[int] = queue.Queue()
_stage_three_queue: queue.Queue[int] = queue.Queue()
_result_queue: queue.Queue[int] = queue.Queue()
_finish = threading.Event()
_start = threading.Event()
for _thread in (
    threading.Thread(
        target=_stage_two_worker,
        args=(_stage_two_queue, _stage_three_queue, _finish),
    ),
    threading.Thread(
        target=_stage_three_worker,
        args=(_stage_three_queue, _result_queue),
    ),
    threading.Thread(target=_stage_one_worker, args=(_stage_two_queue, _start)),
):
    _thread.start()
# The profiler releases this gate after observing the waiting consumer so a
# short-lived producer provides unambiguous completion evidence under load.
with open(sys.argv[1], "rb") as _profiler_gate:
    _ = _profiler_gate.read(1)
_start.set()
threading.Thread(target=_off_path_work, args=(_finish,)).start()
_result = _final_work(_wait_for_final_result(_result_queue))
_finish.set()
os._exit(0 if _result > 0 else 1)
