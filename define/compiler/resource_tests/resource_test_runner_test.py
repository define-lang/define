from __future__ import annotations

import signal
import sys
from typing import TYPE_CHECKING

import pytest

from define.compiler import test_runfiles
from define.compiler.resource_tests import resource_test_runner

if TYPE_CHECKING:
    from pathlib import Path

_MIB = 1024**2


def _run(
    tmp_path: Path,
    program: str,
    *,
    cpu: int = 10,
    wall: float = 30,
    data: int = 512 * _MIB,
):
    source = tmp_path / "stdin"
    _ = source.write_text("input\n")
    artifacts = tmp_path / "artifacts"
    measured = resource_test_runner.run(
        [sys.executable, "-c", program],
        supervisor=test_runfiles.resolve_from_env("RESOURCE_TEST_RUNNER"),
        limiter=test_runfiles.resolve_from_env("RESOURCE_LIMIT_RUNNER"),
        directory=tmp_path,
        artifacts=artifacts,
        source=source,
        cpu_seconds=cpu,
        data_bytes=data,
        wall_seconds=wall,
    )
    return (
        measured,
        (artifacts / "stdout").read_text(),
        (artifacts / "stderr").read_text(),
    )


def test_success_and_standard_streams(tmp_path: Path):
    measured, stdout, stderr = _run(
        tmp_path,
        "import sys; print(sys.stdin.read(), end=''); print('diagnostic', file=sys.stderr)",
    )
    measured.check(rss_bytes=256 * _MIB, stderr=stderr)
    assert stdout == "input\n"
    assert stderr == "diagnostic\n"
    assert measured.cpu_seconds > 0
    assert measured.peak_rss_bytes > 0


def test_cpu_limit_stops_busy_child(tmp_path: Path):
    measured, _, stderr = _run(tmp_path, "while True: pass", cpu=1)
    assert measured.returncode == -signal.SIGXCPU
    with pytest.raises(resource_test_runner.CpuSafetyLimitExceededError):
        measured.check(rss_bytes=256 * _MIB, stderr=stderr)


def test_wall_deadline_stops_sleeping_child(tmp_path: Path):
    measured, _, stderr = _run(tmp_path, "import time; time.sleep(60)", wall=0.2)
    assert measured.returncode == -signal.SIGKILL
    with pytest.raises(resource_test_runner.WallDeadlineExceededError):
        measured.check(rss_bytes=256 * _MIB, stderr=stderr)


def test_memory_accounting_is_independent(tmp_path: Path):
    large = tmp_path / "large"
    large.mkdir()
    high, _, stderr = _run(large, "allocation = bytearray(128 * 1024**2)")
    with pytest.raises(resource_test_runner.MemoryBudgetExceededError):
        high.check(rss_bytes=100 * _MIB, stderr=stderr)
    small = tmp_path / "small"
    small.mkdir()
    low, _, stderr = _run(small, "pass")
    low.check(rss_bytes=100 * _MIB, stderr=stderr)
    assert high.peak_rss_bytes - low.peak_rss_bytes > 96 * _MIB


def test_allocation_limit_is_enforced(tmp_path: Path):
    measured, _, stderr = _run(
        tmp_path, "allocation = bytearray(512 * 1024**2)", data=128 * _MIB
    )
    assert "MemoryError" in stderr
    with pytest.raises(resource_test_runner.CommandFailedError):
        measured.check(rss_bytes=256 * _MIB, stderr=stderr)


def test_unrelated_failure_is_not_a_budget_failure(tmp_path: Path):
    measured, _, stderr = _run(tmp_path, "raise ValueError('broken')")
    with pytest.raises(
        resource_test_runner.CommandFailedError, match="ValueError: broken"
    ):
        measured.check(rss_bytes=1, stderr=stderr)


@pytest.mark.parametrize("speed_factor", [0.01, 1, 1000])
def test_uniform_cpu_slowdown_preserves_growth_result(speed_factor: float):
    control = resource_test_runner.Measurement(
        0, 2 * speed_factor, 1, 1, timed_out=False
    )
    within_allowance = resource_test_runner.Measurement(
        0, 8 * speed_factor, 1, 1, timed_out=False
    )
    within_allowance.check_cpu_growth(control, maximum_ratio=4, rss_bytes=1, stderr="")
    excessive = resource_test_runner.Measurement(
        0, 32 * speed_factor, 1, 1, timed_out=False
    )
    with pytest.raises(resource_test_runner.CpuGrowthExceededError):
        excessive.check_cpu_growth(control, maximum_ratio=4, rss_bytes=1, stderr="")


def test_stopped_run_can_prove_excessive_cpu_growth():
    control = resource_test_runner.Measurement(0, 1, 1, 1, timed_out=False)
    measured = resource_test_runner.Measurement(
        -signal.SIGXCPU, 20, 1, 20, timed_out=False
    )
    with pytest.raises(resource_test_runner.CpuGrowthExceededError):
        measured.check_cpu_growth(control, maximum_ratio=16, rss_bytes=1, stderr="")


def test_safety_stop_without_evidence_is_not_a_growth_failure():
    control = resource_test_runner.Measurement(0, 10, 1, 10, timed_out=False)
    measured = resource_test_runner.Measurement(
        -signal.SIGXCPU, 120, 1, 120, timed_out=False
    )
    with pytest.raises(resource_test_runner.CpuSafetyLimitExceededError):
        measured.check_cpu_growth(control, maximum_ratio=16, rss_bytes=1, stderr="")


@pytest.mark.parametrize(
    ("returncode", "rss_bytes", "timed_out", "expected"),
    [
        (1, 1, False, resource_test_runner.CommandFailedError),
        (0, 2, False, resource_test_runner.MemoryBudgetExceededError),
        (-signal.SIGKILL, 1, True, resource_test_runner.WallDeadlineExceededError),
    ],
)
def test_growth_check_preserves_other_failures(
    returncode: int,
    rss_bytes: int,
    expected: type[resource_test_runner.ResourceTestError],
    *,
    timed_out: bool,
):
    control = resource_test_runner.Measurement(0, 1, 1, 1, timed_out=False)
    measured = resource_test_runner.Measurement(
        returncode, 100, rss_bytes, 100, timed_out=timed_out
    )
    with pytest.raises(expected):
        measured.check_cpu_growth(control, maximum_ratio=16, rss_bytes=1, stderr="")


def test_unexplained_kill_is_not_cpu_exhaustion():
    measured = resource_test_runner.Measurement(
        -signal.SIGKILL, 1, 1, 1, timed_out=False
    )
    with pytest.raises(resource_test_runner.CommandFailedError):
        measured.check(rss_bytes=256 * _MIB, stderr="")


def test_cpu_exhaustion_does_not_hide_memory_regression():
    measured = resource_test_runner.Measurement(
        -signal.SIGXCPU, 10, 512 * _MIB, 10, timed_out=False
    )
    with pytest.raises(resource_test_runner.MemoryBudgetExceededError):
        measured.check(rss_bytes=256 * _MIB, stderr="")
