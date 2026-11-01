# This file holds only the test that WorkPool raises an exception from work on
# the coordinator thread, which no Define program can trigger. Do not add any
# other tests here. Test everything else about WorkPool through the program
# validator tests, by validating Define programs.
from __future__ import annotations

import pytest

from define.compiler.validator.structural import work_pool


class _WorkFailedError(Exception):
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
