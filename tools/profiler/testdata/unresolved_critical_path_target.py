"""Known completion handoff without a sampled stopped producer."""

import os
import queue
import threading
import time

_WORK_NS = 400_000_000
_PRE_HANDOFF_WORK_NS = 800_000_000
_POST_HANDOFF_WORK_NS = 800_000_000


def _cpu_work(duration_ns: int) -> int:
    # PRF-047: Multi-threaded critical path.
    deadline = time.thread_time_ns() + duration_ns
    value = 0
    while time.thread_time_ns() < deadline:
        value += 1
    return value


def _publish_then_continue(result_queue: queue.Queue[int]):
    # PRF-047: Multi-threaded critical path.
    time.sleep(0.2)
    result_queue.put(_cpu_work(_WORK_NS))
    _ = _cpu_work(_POST_HANDOFF_WORK_NS)


# PRF-047: Multi-threaded critical path.
_result_queue: queue.Queue[int] = queue.Queue()
_pre_handoff_result = _cpu_work(_PRE_HANDOFF_WORK_NS)
_worker = threading.Thread(target=_publish_then_continue, args=(_result_queue,))
_worker.start()
_published_result = _result_queue.get()
_result = _pre_handoff_result + _cpu_work(_WORK_NS) + _published_result
os._exit(0 if _result > 0 else 1)
