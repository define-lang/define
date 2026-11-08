# This file holds only the tests of how WorkPool handles an exception from work,
# which no Define program can trigger. Do not add any other tests here. Test everything else about WorkPool through its callers'
# tests.
from __future__ import annotations

import pytest

from define.compiler import work_pool


# Not an Exception, so the test also covers what an `except Exception` misses.
class _WorkFailedError(BaseException):
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
