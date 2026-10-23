from __future__ import annotations

import os
import shutil
from typing import TYPE_CHECKING
from unittest import mock

import pytest

from tools.profiler import perf_access

if TYPE_CHECKING:
    from pathlib import Path

_TRACEPOINT_NAMES = ("sched_waking", "sched_wakeup_new")


def _paranoid(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, level: int):
    paranoid_path = tmp_path / "perf_event_paranoid"
    _ = paranoid_path.write_text(f"{level}\n", encoding="utf-8", newline="\n")
    monkeypatch.setattr(perf_access, "_PARANOID_PATH", paranoid_path)


def _trace_root(tmp_path: Path) -> Path:
    trace_root = tmp_path / "events" / "sched"
    for tracepoint_name in _TRACEPOINT_NAMES:
        tracepoint_directory = trace_root / tracepoint_name
        tracepoint_directory.mkdir(parents=True)
        _ = (tracepoint_directory / "id").write_text(
            "1\n", encoding="utf-8", newline="\n"
        )
    return trace_root


# PRF-020: Machine and human interfaces.
def test_missing_perf_explains_how_to_install_it():
    with (
        mock.patch.object(shutil, "which", autospec=True, return_value=None),
        pytest.raises(perf_access.PerfAccessError) as error,
    ):
        _ = perf_access.perf_executable()

    assert str(error.value) == (
        "Linux perf is not installed or not on PATH. Install it, for example "
        + "with `sudo dnf install perf`."
    )


# PRF-020: Machine and human interfaces.
def test_cpu_access_allows_kernel_profiling(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    _paranoid(tmp_path, monkeypatch, 1)

    assert perf_access.require_cpu_access() is None


# PRF-020: Machine and human interfaces.
def test_cpu_access_explains_how_to_allow_kernel_profiling(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    _paranoid(tmp_path, monkeypatch, 2)

    with pytest.raises(perf_access.PerfAccessError) as error:
        perf_access.require_cpu_access()

    assert str(error.value) == (
        "CPU mode records kernel samples, which needs kernel.perf_event_paranoid "
        + "set to 1 or lower, but it is 2. To set it to -1, which every profiler "
        + "mode allows, run:\n"
        + "  echo 'kernel.perf_event_paranoid = -1' "
        + "| sudo tee /etc/sysctl.d/90-perf-profiling.conf\n"
        + "  sudo sysctl --system"
    )


# PRF-020: Machine and human interfaces.
def test_scheduler_access_allows_readable_tracepoints(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    _paranoid(tmp_path, monkeypatch, -1)

    with mock.patch.object(shutil, "which", autospec=True, return_value="perf"):
        assert (
            perf_access.require_scheduler_access(
                (tmp_path / "missing", _trace_root(tmp_path)), _TRACEPOINT_NAMES
            )
            is None
        )


# PRF-020: Machine and human interfaces.
def test_scheduler_access_needs_every_perf_event(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    _paranoid(tmp_path, monkeypatch, 0)

    with (
        mock.patch.object(shutil, "which", autospec=True, return_value="perf"),
        pytest.raises(perf_access.PerfAccessError) as error,
    ):
        perf_access.require_scheduler_access(
            (_trace_root(tmp_path),), _TRACEPOINT_NAMES
        )

    assert str(error.value).startswith(
        "Wall mode records scheduler tracepoints, which needs "
        + "kernel.perf_event_paranoid set to -1 or lower, but it is 0."
    )


# PRF-020: Machine and human interfaces.
def test_scheduler_access_explains_how_to_read_tracepoints(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    _paranoid(tmp_path, monkeypatch, -1)
    trace_root = _trace_root(tmp_path)
    (trace_root / "sched_waking" / "id").chmod(0)

    with (
        mock.patch.object(shutil, "which", autospec=True, return_value="perf"),
        pytest.raises(perf_access.PerfAccessError) as error,
    ):
        perf_access.require_scheduler_access((trace_root,), _TRACEPOINT_NAMES)

    group = os.getgid()
    assert str(error.value) == (
        f"Wall mode reads the scheduler tracepoints in {trace_root}, which the "
        + "current user cannot read. To let your group read them, add this line "
        + "to /etc/fstab:\n"
        + f"  tracefs /sys/kernel/tracing tracefs defaults,gid={group},mode=0750 0 0\n"
        + "and then run:\n"
        + "  sudo systemctl daemon-reload\n"
        + f"  sudo mount -o remount,gid={group},mode=0750 /sys/kernel/tracing"
    )


# PRF-020: Machine and human interfaces.
def test_scheduler_access_reports_missing_tracepoints(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    _paranoid(tmp_path, monkeypatch, -1)

    with (
        mock.patch.object(shutil, "which", autospec=True, return_value="perf"),
        pytest.raises(perf_access.PerfAccessError) as error,
    ):
        perf_access.require_scheduler_access((tmp_path / "missing",), _TRACEPOINT_NAMES)

    assert str(error.value) == (
        "Wall mode records scheduler tracepoints, but this kernel does not expose "
        + f"them in any of: {tmp_path / 'missing'}"
    )
