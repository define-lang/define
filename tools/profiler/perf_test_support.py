"""Host-capability checks for Linux perf integration tests."""

from __future__ import annotations

import shutil
import subprocess
import sys
from typing import TYPE_CHECKING

import pytest

from tools.profiler import perf_access, perf_profiler, scheduler_events

if TYPE_CHECKING:
    from pathlib import Path


def require_perf_recording(temporary_directory: Path):
    """Skip the current test when Linux perf cannot record CPU samples."""
    perf_executable = shutil.which("perf")
    if perf_executable is None:
        pytest.skip("Linux perf is not installed or not on PATH")
    completed = subprocess.run(
        (
            perf_executable,
            "record",
            "-q",
            "-e",
            "cpu-clock",
            "-g",
            "--call-graph",
            "fp",
            "-m",
            str(perf_profiler.RING_BUFFER_PAGES),
            "-o",
            str(temporary_directory / "perf-capability-check.data"),
            "--",
            sys.executable,
            "-c",
            "pass",
        ),
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode == 0:
        return
    diagnostic = completed.stderr.strip() or completed.stdout.strip()
    reason = f"Linux perf recording is unavailable (status {completed.returncode})"
    if diagnostic:
        reason += f": {diagnostic}"
    pytest.skip(reason)


def require_scheduler_events():
    """Skip the current test when this machine cannot record scheduler events."""
    try:
        scheduler_events.require_access()
    except perf_access.PerfAccessError as error:
        pytest.skip(str(error))
