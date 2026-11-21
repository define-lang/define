# This file holds only the tests of how WorkPool handles an exception from work
# or from the coordinator thread, which no Define program can trigger. Do not add any other tests here. Test everything else about WorkPool through its callers'
# tests.
from __future__ import annotations

import pytest

from define.compiler import work_pool


# Not an Exception, so the test also covers what an `except Exception` misses.
class _WorkFailedError(BaseException):
    pass


# Not an Exception, like the KeyboardInterrupt that can stop the coordinator
# thread.
class _CoordinatorFailedError(BaseException):
    pass


def _fail():
    raise _WorkFailedError


def test_exception_from_work_is_raised_on_coordinator_thread():
    handled_results: list[None] = []

    def handle_result(result: None, _pool: work_pool.WorkPool):
        handled_results.append(result)

    with work_pool.WorkPool(max_workers=1) as pool:
        pool.submit(_fail, handle_result=handle_result)
        with pytest.raises(_WorkFailedError):
            pool.run_until_idle()
    assert handled_results == []


def test_queued_work_is_skipped_after_work_fails():
    ran: list[str] = []

    def record():
        ran.append("queued")

    def handle_result(_result: None, _pool: work_pool.WorkPool):
        pass

    with work_pool.WorkPool(max_workers=1) as pool:
        pool.submit(_fail, handle_result=handle_result)
        pool.submit(record, handle_result=handle_result)
        with pytest.raises(_WorkFailedError):
            pool.run_until_idle()
    assert ran == []


def test_queued_work_is_skipped_after_coordinator_fails():
    ran: list[str] = []

    def wait_for_failure(pool: work_pool.WorkPool):
        # The one worker thread runs this work until the pool records the
        # coordinator thread's failure, so the second work is still queued
        # when the failure is recorded. The timeout ends the wait when the
        # pool never records the failure.
        _ = pool._failed.wait(timeout=10)  # pyright: ignore[reportPrivateUsage]

    def record():
        ran.append("queued")

    def handle_result(_result: object, _pool: work_pool.WorkPool):
        pass

    def fail_with_queued_work():
        with work_pool.WorkPool(max_workers=1) as pool:
            pool.submit(wait_for_failure, pool, handle_result=handle_result)
            pool.submit(record, handle_result=handle_result)
            raise _CoordinatorFailedError

    with pytest.raises(_CoordinatorFailedError):
        fail_with_queued_work()
    assert ran == []
