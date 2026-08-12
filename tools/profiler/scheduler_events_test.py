import shutil
import signal
import subprocess
from pathlib import Path
from unittest import mock

import pytest

from tools.profiler import scheduler_events


def _trace_root(tmp_path: Path) -> Path:
    trace_root = tmp_path / "events" / "sched"
    for tracepoint_name in ("sched_waking", "sched_wakeup_new"):
        tracepoint_directory = trace_root / tracepoint_name
        tracepoint_directory.mkdir(parents=True)
        _ = (tracepoint_directory / "id").write_text("1\n", encoding="utf-8")
    return trace_root


# PRF-052: Independent causal evidence.
def test_cpu_mode_does_not_start_scheduler_event_collection(tmp_path: Path):
    collector = scheduler_events.start(1, tmp_path, enabled=False)

    result = collector.finish()

    assert result.events == []
    assert result.summary == {
        "backend": "linux-perf-sched-waking",
        "status": "unavailable",
        "event_count": 0,
        "lost_event_count": 0,
        "reason": "scheduler causality is collected only in wall mode",
    }
    assert collector.finish() is result


# The real scheduler tracepoint boundary is permission-restricted in ordinary CI.
# PRF-052: Independent causal evidence. PRF-053: Causal diagnostics.
def test_collector_converts_completed_perf_data(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    perf_executable = tmp_path / "perf"
    _ = perf_executable.write_text(
        "#!/bin/sh\n"
        + "printf '%s\\n' '400/401 2398451.123456789: sched:sched_waking: comm=worker pid=402 prio=120 target_cpu=3'\n",
        encoding="utf-8",
    )
    perf_executable.chmod(0o755)
    monkeypatch.setattr(scheduler_events, "_TRACE_ROOTS", (_trace_root(tmp_path),))
    with mock.patch.object(
        shutil,
        "which",
        autospec=True,
        return_value=str(perf_executable),
    ):
        collector = scheduler_events.start(1, tmp_path, enabled=True)

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
        unavailable_reason=None,
    )

    result = collector.finish()

    assert result.summary["status"] == "unavailable"
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
        unavailable_reason=None,
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
        unavailable_reason=None,
    )

    with collector:
        pass

    assert record_process.returncode == -signal.SIGINT


# PRF-053: Causal diagnostics.
def test_start_reports_missing_perf(tmp_path: Path):
    with mock.patch.object(
        shutil,
        "which",
        autospec=True,
        return_value=None,
    ):
        collector = scheduler_events.start(1, tmp_path, enabled=True)

    assert collector.finish().summary["reason"] == "perf is not installed"


# PRF-053: Causal diagnostics.
def test_tracepoint_availability_distinguishes_missing_and_readable(tmp_path: Path):
    tracepoint_access_error = scheduler_events._tracepoint_access_error  # pyright: ignore[reportPrivateUsage]

    assert tracepoint_access_error((tmp_path / "missing",)) == (
        "the kernel does not expose the required scheduler tracepoints"
    )
    assert tracepoint_access_error((_trace_root(tmp_path),)) is None


# PRF-052: Independent causal evidence. PRF-053: Causal diagnostics.
def test_parse_script_output_preserves_direct_wake_identity_and_time():
    events, lost_event_count = scheduler_events.parse_script_output(
        """
        400/401 2398451.123456789: sched:sched_waking: comm=worker pid=402 prio=120 target_cpu=3
        400 2398452.000000001: sched:sched_wakeup_new: comm=worker pid=403 prio=120 target_cpu=4
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
