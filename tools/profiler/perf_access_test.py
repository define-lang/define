from __future__ import annotations

import shutil
from typing import TYPE_CHECKING
from unittest import mock

import pytest

from tools.profiler import perf_access

if TYPE_CHECKING:
    from pathlib import Path


def _paranoid(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, level: int):
    paranoid_path = tmp_path / "perf_event_paranoid"
    _ = paranoid_path.write_text(f"{level}\n", encoding="utf-8", newline="\n")
    monkeypatch.setattr(perf_access, "_PARANOID_PATH", paranoid_path)


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


def test_cpu_access_allows_kernel_profiling(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    _paranoid(tmp_path, monkeypatch, 1)

    assert perf_access.require_cpu_access() is None


def test_cpu_access_explains_how_to_allow_kernel_profiling(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    _paranoid(tmp_path, monkeypatch, 2)

    with pytest.raises(perf_access.PerfAccessError) as error:
        perf_access.require_cpu_access()

    assert str(error.value) == (
        "CPU mode records kernel samples, which needs kernel.perf_event_paranoid "
        + "set to 1 or lower, but it is 2. To set it to -1, run:\n"
        + "  echo 'kernel.perf_event_paranoid = -1' "
        + "| sudo tee /etc/sysctl.d/90-perf-profiling.conf\n"
        + "  sudo sysctl --system"
    )
