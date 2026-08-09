"""Multithreaded process used by profiler integration tests."""

import threading
import time

# PRF-013: Wall mode. PRF-041: Realistic tests.


def _wait_in_first_worker(barrier: threading.Barrier) -> None:
    _ = barrier.wait()
    time.sleep(2.0)


def _wait_in_second_worker(barrier: threading.Barrier) -> None:
    _ = barrier.wait()
    time.sleep(2.0)


_barrier = threading.Barrier(3)
_first_thread = threading.Thread(target=_wait_in_first_worker, args=(_barrier,))
_second_thread = threading.Thread(target=_wait_in_second_worker, args=(_barrier,))
_first_thread.start()
_second_thread.start()
_ = _barrier.wait()
time.sleep(2.0)
_first_thread.join()
_second_thread.join()
