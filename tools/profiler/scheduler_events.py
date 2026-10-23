"""Capture non-weight-bearing Linux scheduler wake events."""

from __future__ import annotations

import pathlib
import re
import signal
import subprocess
import typing

import msgspec

from tools.profiler import perf_access, perf_profiler

if typing.TYPE_CHECKING:
    from tools.profiler import schema

_TRACEPOINT_NAMES = ("sched_waking", "sched_wakeup_new")
_TRACE_ROOTS = (
    pathlib.Path("/sys/kernel/tracing/events/sched"),
    pathlib.Path("/sys/kernel/debug/tracing/events/sched"),
)
_TIMESTAMP_PATTERN = re.compile(r"(?P<seconds>\d+)\.(?P<nanoseconds>\d{9}):")
_THREAD_PATTERN = re.compile(r"(?<![\d./])(?:\d+/)?(?P<thread_id>\d+)(?![\d./])")
# perf prints the woken thread either as fields, such as `comm=worker pid=402`,
# or as `worker:402 [120]`, depending on the event and the kernel's format.
_DOWNSTREAM_PATTERNS = (
    re.compile(r"(?:^|\s)pid=(?P<thread_id>\d+)(?:\s|$)"),
    re.compile(r":(?P<thread_id>\d+)\s+\[\d+\]"),
)
_LOST_PATTERN = re.compile(
    r"\blost(?:=|:|\s+)\s*(?P<count>\d+)\b",
    re.IGNORECASE,
)


class CaptureResult(msgspec.Struct, frozen=True):
    """Scheduler-event records and their collection status."""

    events: list[schema.SchedulerWakeEvent]
    summary: schema.CausalitySummary


def _failed(reason: str) -> CaptureResult:
    return CaptureResult(
        events=[],
        summary={
            "backend": "linux-perf-sched-waking",
            "status": "failed",
            "event_count": 0,
            "lost_event_count": 0,
            "reason": reason,
        },
    )


def require_access():
    """Require the access that recording scheduler events needs."""
    perf_access.require_scheduler_access(_TRACE_ROOTS, _TRACEPOINT_NAMES)


def _downstream_thread_match(payload: str) -> re.Match[str] | None:
    for pattern in _DOWNSTREAM_PATTERNS:
        match = pattern.search(payload)
        if match is not None:
            return match
    return None


def parse_script_output(output: str) -> tuple[list[schema.SchedulerWakeEvent], int]:
    """Parse the deliberately narrow perf-script scheduler event stream."""
    # PRF-052: Independent causal evidence. PRF-053: Causal diagnostics.
    events: list[schema.SchedulerWakeEvent] = []
    lost_event_count = 0
    for line in output.splitlines():
        if not line.strip():
            continue
        if "PERF_RECORD_LOST" in line:
            lost_match = _LOST_PATTERN.search(line)
            if lost_match is None:
                raise ValueError(f"malformed perf lost-event record: {line}")
            lost_event_count += int(lost_match.group("count"))
            continue
        if "sched:sched_waking:" in line:
            event_kind: typing.Literal["waking", "wakeup-new"] = "waking"
            event_marker = "sched:sched_waking:"
        elif "sched:sched_wakeup_new:" in line:
            event_kind = "wakeup-new"
            event_marker = "sched:sched_wakeup_new:"
        else:
            raise ValueError(f"unexpected perf scheduler record: {line}")
        timestamp_match = _TIMESTAMP_PATTERN.search(line)
        if timestamp_match is None:
            raise ValueError(f"scheduler event has no nanosecond timestamp: {line}")
        header = line[: timestamp_match.start()]
        thread_matches = list(_THREAD_PATTERN.finditer(header))
        if not thread_matches:
            raise ValueError(f"scheduler event has no waking thread: {line}")
        payload = line.split(event_marker, maxsplit=1)[1]
        downstream_match = _downstream_thread_match(payload)
        if downstream_match is None:
            raise ValueError(f"scheduler event has no woken thread: {line}")
        host_monotonic_ns = int(timestamp_match.group("seconds")) * 1_000_000_000 + int(
            timestamp_match.group("nanoseconds")
        )
        events.append(
            {
                "kind": event_kind,
                "host_monotonic_ns": host_monotonic_ns,
                "upstream_os_thread_id": int(thread_matches[-1].group("thread_id")),
                "downstream_os_thread_id": int(downstream_match.group("thread_id")),
            }
        )
    return events, lost_event_count


class Collector(msgspec.Struct):
    """An external perf scheduler-event collection process."""

    perf_executable: str
    perf_data_path: pathlib.Path
    process: subprocess.Popen[str]
    _result: CaptureResult | None = None

    def finish(self) -> CaptureResult:
        """Stop collection and convert its trace to profile-domain records."""
        # PRF-052: Independent causal evidence. PRF-053: Causal diagnostics.
        if self._result is not None:
            return self._result
        _, standard_error = self.process.communicate()
        if self.process.returncode != 0:
            reason = standard_error.strip() or (
                f"perf record exited with status {self.process.returncode}"
            )
            self._result = _failed(reason)
            return self._result
        script_result = subprocess.run(
            [
                self.perf_executable,
                "script",
                "--input",
                str(self.perf_data_path),
                "--ns",
                "--show-lost-events",
                "--fields=trace:pid,tid,time,event,trace",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if script_result.returncode != 0:
            self._result = _failed(
                script_result.stderr.strip()
                or f"perf script exited with status {script_result.returncode}"
            )
            return self._result
        try:
            events, lost_event_count = parse_script_output(script_result.stdout)
        except ValueError as error:
            self._result = _failed(str(error))
            return self._result
        self._result = CaptureResult(
            events=events,
            summary={
                "backend": "linux-perf-sched-waking",
                "status": "recorded",
                "event_count": len(events),
                "lost_event_count": lost_event_count,
                "reason": None,
            },
        )
        return self._result

    def __enter__(self) -> typing.Self:
        """Return the running collector."""
        return self

    def __exit__(
        self,
        _exception_type: type[BaseException] | None,
        _exception: BaseException | None,
        _traceback: object,
    ) -> typing.Literal[False]:
        """Stop an unfinished collector when its owner exits early."""
        if self._result is None and self.process.poll() is None:
            self.process.send_signal(signal.SIGINT)
        _ = self.finish()
        return False


def start(process_id: int, temporary_directory: pathlib.Path) -> Collector:
    """Start scheduler-event collection for a target and its future threads.

    The caller has already checked access with `require_access`.
    """
    # PRF-052: Independent causal evidence.
    perf_data_path = temporary_directory / "scheduler-events.perf.data"
    perf_executable = perf_access.perf_executable()
    process = subprocess.Popen(
        [
            perf_executable,
            "record",
            "--quiet",
            "--no-buildid",
            "--synth=no",
            "--clockid=mono",
            "--mmap-pages",
            str(perf_profiler.RING_BUFFER_PAGES),
            "--event",
            "sched:sched_waking",
            "--event",
            "sched:sched_wakeup_new",
            "--pid",
            str(process_id),
            "--output",
            str(perf_data_path),
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )
    return Collector(
        perf_executable=perf_executable,
        perf_data_path=perf_data_path,
        process=process,
    )
