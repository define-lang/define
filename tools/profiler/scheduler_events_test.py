from __future__ import annotations

import shutil
import signal
import subprocess
from typing import TYPE_CHECKING
from unittest import mock

import pytest

from tools.profiler import scheduler_events

if TYPE_CHECKING:
    from pathlib import Path


# PRF-052: Independent causal evidence. PRF-053: Causal diagnostics.
def test_collector_converts_completed_perf_data(tmp_path: Path):
    perf_executable = tmp_path / "perf"
    _ = perf_executable.write_text(
        "#!/bin/sh\n"
        + "printf '%s\\n' '400/401 2398451.123456789: sched:sched_waking: comm=worker pid=402 prio=120 target_cpu=3'\n",
        encoding="utf-8",
        newline="\n",
    )
    perf_executable.chmod(0o755)
    with mock.patch.object(
        shutil,
        "which",
        autospec=True,
        return_value=str(perf_executable),
    ):
        collector = scheduler_events.start(1, tmp_path)

    result = collector.finish()

    assert result.events == [
        {
            "kind": "waking",
            "host_monotonic_ns": 2_398_451_123_456_789,
            "upstream_os_thread_id": 401,
            "downstream_os_thread_id": 402,
        }
    ]
    assert result.summary["status"] == "recorded"
    assert result.summary["event_count"] == 1


# PRF-053: Causal diagnostics.
def test_collector_reports_perf_record_failure(tmp_path: Path):
    record_process = subprocess.Popen(
        ["/bin/false"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )
    collector = scheduler_events.Collector(
        perf_executable="/bin/false",
        perf_data_path=tmp_path / "events.data",
        process=record_process,
    )

    result = collector.finish()

    assert result.summary["status"] == "failed"
    assert result.summary["reason"] == "perf record exited with status 1"


# PRF-053: Causal diagnostics.
def test_collector_reports_perf_script_failure(tmp_path: Path):
    record_process = subprocess.Popen(
        ["/bin/true"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )
    collector = scheduler_events.Collector(
        perf_executable="/bin/false",
        perf_data_path=tmp_path / "events.data",
        process=record_process,
    )

    result = collector.finish()

    assert result.summary["status"] == "failed"
    assert result.summary["reason"] == "perf script exited with status 1"


# PRF-052: Independent causal evidence.
def test_collector_stops_perf_when_capture_exits_early(tmp_path: Path):
    record_process = subprocess.Popen(
        ["/bin/sleep", "30"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )
    collector = scheduler_events.Collector(
        perf_executable="/bin/false",
        perf_data_path=tmp_path / "events.data",
        process=record_process,
    )

    with collector:
        pass

    assert record_process.returncode == -signal.SIGINT


# PRF-052: Independent causal evidence. PRF-053: Causal diagnostics.
def test_parse_script_output_preserves_direct_wake_identity_and_time():
    events, lost_event_count = scheduler_events.parse_script_output(
        """
        400/401 2398451.123456789: sched:sched_waking: comm=worker pid=402 prio=120 target_cpu=3
        400 2398452.000000001: sched:sched_wakeup_new: comm=worker pid=403 prio=120 target_cpu=4
        400/404 2398453.000000002: sched:sched_wakeup_new: python:405 [120] CPU:022
        PERF_RECORD_LOST lost=7
        """
    )

    assert events == [
        {
            "kind": "waking",
            "host_monotonic_ns": 2_398_451_123_456_789,
            "upstream_os_thread_id": 401,
            "downstream_os_thread_id": 402,
        },
        {
            "kind": "wakeup-new",
            "host_monotonic_ns": 2_398_452_000_000_001,
            "upstream_os_thread_id": 400,
            "downstream_os_thread_id": 403,
        },
        {
            "kind": "wakeup-new",
            "host_monotonic_ns": 2_398_453_000_000_002,
            "upstream_os_thread_id": 404,
            "downstream_os_thread_id": 405,
        },
    ]
    assert lost_event_count == 7


@pytest.mark.parametrize(
    "record",
    [
        "unexpected event",
        "400 sched:sched_waking: comm=worker pid=402",
        "2398451.123456789: sched:sched_waking: comm=worker pid=402",
        "400 2398451.123456789: sched:sched_waking: comm=worker",
        "PERF_RECORD_LOST without-a-count",
    ],
)
def test_parse_script_output_rejects_incomplete_evidence(record: str):
    with pytest.raises(ValueError, match=r"perf|scheduler"):
        _ = scheduler_events.parse_script_output(record)
