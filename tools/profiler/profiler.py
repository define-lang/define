"""Capture randomized blocking all-thread Python stack observations."""

from __future__ import annotations

import contextlib
import dataclasses
import hashlib
import itertools
import json
import os
import pathlib
import platform
import queue
import random
import signal
import subprocess
import sys
import sysconfig
import tempfile
import threading
import time
import typing
from typing import Protocol, cast

import _remote_debugging  # pyright: ignore[reportMissingImports]
import click

from tools.profiler import cpu_profiler, process_events, schema

if typing.TYPE_CHECKING:
    import collections.abc

_PATH = click.Path(path_type=pathlib.Path)
_MAX_DISCARDED_RATE = 0.001

type _ProfilerEvent = typing.Literal[
    "launcher-recorded",
    "python-attached",
    "target-stopped",
    "successful-observation-persisted",
]

_PROFILER_EVENT_BYTES: dict[_ProfilerEvent, bytes] = {
    "launcher-recorded": b"launcher-recorded\n",
    "python-attached": b"python-attached\n",
    "target-stopped": b"target-stopped\n",
    "successful-observation-persisted": b"successful-observation-persisted\n",
}


# PRF-015: Full stacks. PRF-016: Source identity.
class _RemoteFrame(Protocol):
    filename: str
    funcname: str
    lineno: int


# PRF-013: Wall mode. PRF-015: Full stacks.
class _RemoteThread(Protocol):
    thread_id: int
    frame_info: list[_RemoteFrame]


# PRF-001: No call-correlated wall profiling work.
class _Unwinder(Protocol):
    def get_stack_trace(self) -> object: ...


# PRF-001: No call-correlated wall profiling work.
class _UnwinderConstructor(Protocol):
    def __call__(self, process_id: int, *, all_threads: bool) -> _Unwinder: ...


# PRF-001: No call-correlated wall profiling work.
# PRF-017: No compiler instrumentation.
_REMOTE_UNWINDER = cast(
    "_UnwinderConstructor",
    _remote_debugging.RemoteUnwinder,
)


class _CaptureInterrupted(BaseException):
    # PRF-024: Explicit failures.
    signal_number: int
    pause_duration_ns: int

    def __init__(self, signal_number: int):
        super().__init__(signal_number)
        self.signal_number = signal_number
        self.pause_duration_ns = 0


class _AttachmentError(Exception):
    # PRF-022: Launcher safety. PRF-024: Explicit failures.
    kind: schema.CaptureFailureKind

    def __init__(self, kind: schema.CaptureFailureKind, reason: str):
        super().__init__(reason)
        self.kind = kind


class _ProfilerEventError(Exception):
    # PRF-024: Explicit failures. PRF-049: Event-driven coordination.
    def __init__(self, reason: str):
        super().__init__(reason)
        self.pause_duration_ns: int = 0


class _ObservationProcessorError(Exception):
    # PRF-024: Explicit failures. PRF-051: Schedule-isolated persistence.
    kind: schema.CaptureFailureKind

    def __init__(self, kind: schema.CaptureFailureKind, reason: str):
        super().__init__(reason)
        self.kind = kind


class _TargetStopError(Exception):
    # PRF-024: Explicit failures.
    pass


class _TargetExitRaceError(Exception):
    # PRF-024: Explicit failures.
    pass


class _TargetResumeError(Exception):
    # PRF-023: Guaranteed resume. PRF-024: Explicit failures.
    pass


class _InconsistentStackObservationError(Exception):
    # PRF-007: Consistent stack.
    pass


type _ObservationFailure = (
    OSError
    | RuntimeError
    | ValueError
    | _InconsistentStackObservationError
    | _TargetExitRaceError
    | _TargetResumeError
    | _TargetStopError
)


def _observation_failure_kind(
    failure: _ObservationFailure,
) -> schema.ObservationFailureKind:
    # PRF-024: Explicit failures.
    match failure:
        case PermissionError():
            return schema.ObservationFailureKind.PERMISSION_DENIED
        case _InconsistentStackObservationError():
            return schema.ObservationFailureKind.INCONSISTENT_STACK
        case _TargetExitRaceError():
            return schema.ObservationFailureKind.TARGET_EXITED_DURING_OBSERVATION
        case _TargetResumeError():
            return schema.ObservationFailureKind.TARGET_RESUME_FAILED
        case _TargetStopError():
            return schema.ObservationFailureKind.TARGET_STOP_FAILED
        case RuntimeError():
            return schema.ObservationFailureKind.STACK_UNWIND_FAILED
        case ValueError():
            return schema.ObservationFailureKind.MALFORMED_OBSERVATION
        case OSError():
            return schema.ObservationFailureKind.OBSERVATION_SYSTEM_ERROR
    typing.assert_never(failure)


@dataclasses.dataclass(frozen=True, slots=True)
class _ThreadEvidence:
    # PRF-010: Raw-data preservation.
    start_time_ticks: int
    state: str
    wait_channel: str
    voluntary_context_switches: int
    nonvoluntary_context_switches: int


@dataclasses.dataclass(frozen=True, slots=True)
class _StoppedThread:
    # PRF-005: Lifecycle-bounded attribution. PRF-007: Consistent stack.
    start_time_ticks: int
    state: str
    scheduler_runtime_ns: int | None


@dataclasses.dataclass(frozen=True, slots=True)
class _CapturedFrame:
    filename: str
    function: str
    line: int


@dataclasses.dataclass(frozen=True, slots=True)
class _CapturedThread:
    # PRF-010: Raw-data preservation. PRF-014: CPU mode.
    os_thread_id: int
    evidence: _ThreadEvidence
    stopped_state: str
    stack: list[_CapturedFrame]
    scheduler_runtime_ns: int | None


@dataclasses.dataclass(frozen=True, slots=True)
class _ObservationTiming:
    # PRF-003: Pause exclusion.
    observation_index: int
    scheduled_interval_ns: int
    host_monotonic_ns: int
    target_running_ns: int
    pause_started_ns: int
    pause_ended_ns: int
    pause_duration_ns: int
    process_id: int


@dataclasses.dataclass(frozen=True, slots=True)
class _SuccessfulObservationResult(_ObservationTiming):
    # PRF-007: Consistent stack.
    threads: list[_CapturedThread]


@dataclasses.dataclass(frozen=True, slots=True)
class _RawObservation(_ObservationTiming):
    # PRF-010: Raw-data preservation. PRF-050: Minimal stopped section.
    evidence: dict[int, _ThreadEvidence]
    stopped_threads: dict[int, _StoppedThread]
    remote_threads: list[_RemoteThread]


@dataclasses.dataclass(frozen=True, slots=True)
class _FailedObservationResult(_ObservationTiming):
    # PRF-004: No stale-stack reuse. PRF-024: Explicit failures.
    status: typing.Literal["discarded", "missed"]
    failure_kind: schema.ObservationFailureKind
    failure_reason: str


_ObservationResult = _SuccessfulObservationResult | _FailedObservationResult
_ObservationWork = _RawObservation | _FailedObservationResult


@contextlib.contextmanager
def _blocked_interruption_signals() -> collections.abc.Generator[None, None, None]:
    # PRF-027: Incremental persistence.
    previous_mask = signal.pthread_sigmask(
        signal.SIG_BLOCK,
        {signal.SIGINT, signal.SIGTERM},
    )
    try:
        yield
    finally:
        _ = signal.pthread_sigmask(signal.SIG_SETMASK, previous_mask)


@dataclasses.dataclass(frozen=True, slots=True)
class _ObservationCapture:
    # PRF-022: Launcher safety.
    result: _ObservationWork
    unwinder: _Unwinder | None


@dataclasses.dataclass(frozen=True, slots=True)
class _AttachedRuntime:
    # PRF-011: Complete invocation. PRF-022: Launcher safety.
    runtime: schema.PythonRuntime
    observed_ns: int
    observed_target_running_ns: int
    attachment_pause_ns: int


@dataclasses.dataclass(slots=True)
class _CaptureState:
    # PRF-003: Pause exclusion. PRF-005: Lifecycle-bounded attribution.
    # PRF-014: CPU mode. PRF-024: Explicit failures.
    # PRF-027: Incremental persistence.
    random_generator: random.Random
    mode: schema.CaptureMode
    counts: schema.ObservationCounts
    observation_times: list[int] = dataclasses.field(default_factory=list)
    thread_lifecycles: dict[tuple[int, int], schema.ThreadLifecycle] = (
        dataclasses.field(default_factory=dict)
    )
    failures: list[schema.FailureRecord] = dataclasses.field(default_factory=list)
    attached_runtime: _AttachedRuntime | None = None
    retained_unwinder: _Unwinder | None = None
    total_pause_ns: int = 0
    observation_pause_ns: int = 0
    python_stack_observations: int = 0
    observation_index: int = 0
    runtime_recorded: bool = False
    interruption_signal: int | None = None


@dataclasses.dataclass(slots=True)
class _ProfileWriter:
    # PRF-027: Incremental persistence. PRF-028: Bounded storage.
    profile_file: typing.TextIO
    frame_ids: dict[tuple[str, str, int], int] = dataclasses.field(default_factory=dict)

    def append_records(self, records: list[schema.ProfileRecord]) -> None:
        with _blocked_interruption_signals():
            for record in records:
                _ = self.profile_file.write(
                    json.dumps(record, separators=(",", ":"), sort_keys=True) + "\n"
                )
            self.profile_file.flush()
            os.fsync(self.profile_file.fileno())

    def observation_record(
        self, result: _ObservationResult
    ) -> tuple[list[schema.ProfileRecord], schema.Observation]:
        if isinstance(result, _FailedObservationResult):
            failed: schema.FailedObservation = {
                **_observation_timing(result),
                "status": result.status,
                "failure_kind": result.failure_kind,
                "failure_reason": result.failure_reason,
            }
            return ([{"record_type": "observation", "observation": failed}], failed)

        frame_records: list[schema.ProfileRecord] = []
        threads: list[schema.SampledThreadObservation] = []
        for captured_thread in result.threads:
            stack: list[int] = []
            for captured_frame in captured_thread.stack:
                key = (
                    captured_frame.filename,
                    captured_frame.function,
                    captured_frame.line,
                )
                frame_id = self.frame_ids.get(key)
                if frame_id is None:
                    frame_id = len(self.frame_ids)
                    self.frame_ids[key] = frame_id
                    frame: schema.Frame = {
                        "frame_id": frame_id,
                        "filename": captured_frame.filename,
                        "function": captured_frame.function,
                        "line": captured_frame.line,
                    }
                    frame_records.append({"record_type": "frame", "frame": frame})
                stack.append(frame_id)
            thread_observation: schema.ThreadObservation = {
                "os_thread_id": captured_thread.os_thread_id,
                "start_time_ticks": captured_thread.evidence.start_time_ticks,
                "pre_stop_state": captured_thread.evidence.state,
                "wait_channel": captured_thread.evidence.wait_channel,
                "voluntary_context_switches": (
                    captured_thread.evidence.voluntary_context_switches
                ),
                "nonvoluntary_context_switches": (
                    captured_thread.evidence.nonvoluntary_context_switches
                ),
                "stopped_state": captured_thread.stopped_state,
                "stack": stack,
            }
            if captured_thread.scheduler_runtime_ns is not None:
                # PRF-010: Raw-data preservation. PRF-014: CPU mode.
                cpu_thread_observation: schema.CpuThreadObservation = {
                    **thread_observation,
                    "scheduler_runtime_ns": captured_thread.scheduler_runtime_ns,
                }
                threads.append(cpu_thread_observation)
            else:
                threads.append(thread_observation)
        successful: schema.SuccessfulObservation = {
            **_observation_timing(result),
            "status": "successful",
            "threads": threads,
        }
        frame_records.append({"record_type": "observation", "observation": successful})
        return frame_records, successful


def _interrupt(signal_number: int, _current_frame: object) -> None:
    # PRF-024: Explicit failures.
    raise _CaptureInterrupted(signal_number)


def _emit_profiler_event(
    event_file_descriptor: int | None,
    event: _ProfilerEvent,
):
    # PRF-049: Event-driven coordination.
    if event_file_descriptor is None:
        return
    try:
        _ = os.write(event_file_descriptor, _PROFILER_EVENT_BYTES[event])
    except OSError as error:
        raise _ProfilerEventError(str(error)) from error


def _sha256(path: pathlib.Path) -> str:
    # PRF-010: Raw-data preservation.
    digest = hashlib.sha256()
    with path.open("rb") as source_file:
        while chunk := source_file.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _python_runtime(
    executable: schema.ExecutableIdentity,
) -> schema.PythonRuntime:
    # PRF-021: Version match. Exact identity makes local metadata target metadata.
    return {
        "version": platform.python_version(),
        "minor_version": f"{sys.version_info.major}.{sys.version_info.minor}",
        "free_threaded": cast(
            "int | None",
            sysconfig.get_config_var("Py_GIL_DISABLED"),
        )
        == 1,
        "executable": executable,
    }


def _wait_for_python_executable(
    target_process: process_events.TargetProcess,
    expected_python: schema.ExecutableIdentity,
    attachment_timeout_seconds: float,
) -> tuple[schema.ExecutableIdentity, int]:
    # PRF-021: Version match. PRF-022: Launcher safety.
    # PRF-049: Event-driven coordination.
    try:
        result = process_events.wait_for_expected_executable(
            target_process,
            expected_python,
            attachment_timeout_seconds,
        )
    except process_events.ExecutableWaitTimeoutError as error:
        raise _AttachmentError(
            schema.CaptureFailureKind.ATTACHMENT_TIMEOUT,
            "the target did not execute the profiler's Python runtime",
        ) from error
    except process_events.ProcessExitedBeforeExecutableError as error:
        raise _AttachmentError(
            schema.CaptureFailureKind.TARGET_EXITED_BEFORE_ATTACHMENT,
            "the target exited before its launcher executed the Python runtime",
        ) from error
    return result.executable, result.pause_ns


def _status_fields(status: str) -> dict[str, str]:
    return {
        name: value.strip()
        for line in status.splitlines()
        if ":" in line
        for name, value in [line.split(":", 1)]
    }


def _thread_stat(thread_directory: pathlib.Path) -> tuple[str, int]:
    # PRF-010: Raw-data preservation. A Linux TID can be reused after thread exit.
    stat = (thread_directory / "stat").read_text(encoding="utf-8")
    command_end = stat.rindex(")")
    fields_from_state = stat[command_end + 2 :].split()
    return fields_from_state[0], int(fields_from_state[19])


def _thread_evidence(process_id: int) -> dict[int, _ThreadEvidence]:
    # PRF-010: Raw-data preservation.
    evidence: dict[int, _ThreadEvidence] = {}
    for thread_directory in pathlib.Path(f"/proc/{process_id}/task").iterdir():
        fields = _status_fields(
            (thread_directory / "status").read_text(encoding="utf-8")
        )
        _, start_time_ticks = _thread_stat(thread_directory)
        evidence[int(thread_directory.name)] = _ThreadEvidence(
            start_time_ticks=start_time_ticks,
            state=fields["State"].split()[0],
            wait_channel=(thread_directory / "wchan")
            .read_text(encoding="utf-8")
            .strip(),
            voluntary_context_switches=int(fields["voluntary_ctxt_switches"]),
            nonvoluntary_context_switches=int(fields["nonvoluntary_ctxt_switches"]),
        )
    return evidence


def _stopped_threads(
    process_id: int,
    mode: schema.CaptureMode,
) -> dict[int, _StoppedThread]:
    # PRF-005: Lifecycle-bounded attribution. PRF-006: Complete-process stop.
    # PRF-014: CPU mode. PRF-050: Minimal stopped section.
    stopped_threads: dict[int, _StoppedThread] = {}
    for thread_directory in pathlib.Path(f"/proc/{process_id}/task").iterdir():
        state, start_time_ticks = _thread_stat(thread_directory)
        stopped_threads[int(thread_directory.name)] = _StoppedThread(
            start_time_ticks=start_time_ticks,
            state=state,
            scheduler_runtime_ns=(
                cpu_profiler.scheduler_runtime(thread_directory)
                if mode == "cpu"
                else None
            ),
        )
    return stopped_threads


def _capture_stopped_threads(
    target_process: process_events.TargetProcess,
    retained_unwinder: _Unwinder | None,
    mode: schema.CaptureMode,
    event_file_descriptor: int | None,
) -> tuple[dict[int, _StoppedThread], list[_RemoteThread], _Unwinder]:
    # PRF-006: Complete-process stop. PRF-007: Consistent stack.
    # PRF-013: Wall mode. PRF-015: Full stacks. PRF-016: Source identity.
    # PRF-050: Minimal stopped section.
    target = target_process.process
    waited_process_id, wait_status = os.waitpid(target.pid, os.WUNTRACED)
    if os.WIFEXITED(wait_status) or os.WIFSIGNALED(wait_status):
        target.returncode = os.waitstatus_to_exitcode(wait_status)
        raise _TargetExitRaceError(
            "target exited while the profiler was stopping it with status "
            + str(target.returncode)
        )
    if waited_process_id != target.pid or not os.WIFSTOPPED(wait_status):
        raise _TargetStopError("target exited while the profiler was stopping it")
    _emit_profiler_event(event_file_descriptor, "target-stopped")
    stopped_threads = _stopped_threads(target.pid, mode)
    if any(
        stopped_thread.state not in {"T", "t"}
        for stopped_thread in stopped_threads.values()
    ):
        # PRF-006: Complete-process stop. PRF-050: Minimal stopped section.
        # Unwinding before every thread has stopped can produce a torn snapshot.
        raise _TargetStopError("not every target thread reached a stopped state")
    observation_unwinder = retained_unwinder or _REMOTE_UNWINDER(
        target.pid,
        all_threads=True,
    )
    remote_threads = cast(
        "list[_RemoteThread]",
        observation_unwinder.get_stack_trace(),
    )
    return stopped_threads, remote_threads, observation_unwinder


def _normalize_observation(raw_observation: _RawObservation) -> _ObservationResult:
    # PRF-004: No stale-stack reuse. PRF-007: Consistent stack.
    # PRF-010: Raw-data preservation. PRF-050: Minimal stopped section.
    stopped_threads = raw_observation.stopped_threads
    evidence = raw_observation.evidence
    remote_threads = raw_observation.remote_threads
    remote_threads_by_id = {
        remote_thread.thread_id: remote_thread for remote_thread in remote_threads
    }
    for remote_thread in remote_threads:
        if (
            remote_thread.thread_id not in evidence
            or remote_thread.thread_id not in stopped_threads
        ):
            return _failed_observation_from_raw(
                raw_observation,
                _InconsistentStackObservationError(
                    "a Python thread changed identity during the observation"
                ),
            )
    captured_threads: list[_CapturedThread] = []
    for thread_id, stopped_thread in stopped_threads.items():
        thread_evidence = evidence.get(thread_id)
        if thread_evidence is None:
            return _failed_observation_from_raw(
                raw_observation,
                _InconsistentStackObservationError(
                    "an OS thread changed identity during the observation"
                ),
            )
        if thread_evidence.start_time_ticks != stopped_thread.start_time_ticks:
            return _failed_observation_from_raw(
                raw_observation,
                _InconsistentStackObservationError(
                    "an OS thread identifier was reused during the observation"
                ),
            )
        remote_thread = remote_threads_by_id.get(thread_id)
        stack = [
            _CapturedFrame(
                filename=frame.filename,
                function=frame.funcname,
                line=frame.lineno,
            )
            for frame in (
                reversed(remote_thread.frame_info) if remote_thread is not None else ()
            )
        ]
        captured_threads.append(
            _CapturedThread(
                os_thread_id=thread_id,
                evidence=thread_evidence,
                stopped_state=stopped_thread.state,
                stack=stack,
                scheduler_runtime_ns=stopped_thread.scheduler_runtime_ns,
            )
        )
    return _SuccessfulObservationResult(
        observation_index=raw_observation.observation_index,
        scheduled_interval_ns=raw_observation.scheduled_interval_ns,
        host_monotonic_ns=raw_observation.host_monotonic_ns,
        target_running_ns=raw_observation.target_running_ns,
        pause_started_ns=raw_observation.pause_started_ns,
        pause_ended_ns=raw_observation.pause_ended_ns,
        pause_duration_ns=raw_observation.pause_duration_ns,
        process_id=raw_observation.process_id,
        threads=captured_threads,
    )


def _failed_observation_capture(
    target: subprocess.Popen[str],
    failure: Exception,
    observation_index: int,
    scheduled_interval_ns: int,
    launched_ns: int,
    total_pause_ns: int,
    pause_started_ns: int,
    pause_ended_ns: int,
    failure_kind: schema.ObservationFailureKind,
) -> _ObservationCapture:
    # PRF-004: No stale-stack reuse. PRF-024: Explicit failures.
    # PRF-025: Failure threshold.
    process_exit_confirmed = isinstance(failure, _TargetExitRaceError) or (
        target.poll() is not None
    )
    status: typing.Literal["discarded", "missed"] = (
        "missed" if process_exit_confirmed else "discarded"
    )
    return _ObservationCapture(
        result=_FailedObservationResult(
            observation_index=observation_index,
            scheduled_interval_ns=scheduled_interval_ns,
            host_monotonic_ns=pause_started_ns,
            target_running_ns=pause_started_ns - launched_ns - total_pause_ns,
            pause_started_ns=pause_started_ns,
            pause_ended_ns=pause_ended_ns,
            pause_duration_ns=pause_ended_ns - pause_started_ns,
            process_id=target.pid,
            status=status,
            failure_kind=(
                schema.ObservationFailureKind.TARGET_EXITED_DURING_OBSERVATION
                if process_exit_confirmed
                else failure_kind
            ),
            failure_reason=f"{type(failure).__name__}: {failure}",
        ),
        unwinder=None,
    )


def _failed_observation_from_raw(
    raw_observation: _RawObservation,
    failure: _InconsistentStackObservationError,
) -> _FailedObservationResult:
    # PRF-004: No stale-stack reuse. PRF-024: Explicit failures.
    # PRF-050: Minimal stopped section.
    return _FailedObservationResult(
        observation_index=raw_observation.observation_index,
        scheduled_interval_ns=raw_observation.scheduled_interval_ns,
        host_monotonic_ns=raw_observation.host_monotonic_ns,
        target_running_ns=raw_observation.target_running_ns,
        pause_started_ns=raw_observation.pause_started_ns,
        pause_ended_ns=raw_observation.pause_ended_ns,
        pause_duration_ns=raw_observation.pause_duration_ns,
        process_id=raw_observation.process_id,
        status="discarded",
        failure_kind=_observation_failure_kind(failure),
        failure_reason=f"{type(failure).__name__}: {failure}",
    )


def _capture_observation(
    target_process: process_events.TargetProcess,
    retained_unwinder: _Unwinder | None,
    observation_index: int,
    scheduled_interval_ns: int,
    launched_ns: int,
    total_pause_ns: int,
    mode: schema.CaptureMode,
    event_file_descriptor: int | None,
) -> _ObservationCapture:
    # PRF-003: Pause exclusion. PRF-006: Complete-process stop.
    # PRF-007: Consistent stack. PRF-013: Wall mode.
    # PRF-015: Full stacks. PRF-016: Source identity.
    # PRF-023: Guaranteed resume.
    target = target_process.process
    try:
        evidence = _thread_evidence(target.pid)
    except _CaptureInterrupted:
        raise
    except (OSError, UnicodeDecodeError, ValueError) as error:
        observation_ns = time.monotonic_ns()
        failure_kind = (
            schema.ObservationFailureKind.PERMISSION_DENIED
            if isinstance(error, PermissionError)
            else schema.ObservationFailureKind.THREAD_EVIDENCE_READ_FAILED
        )
        return _failed_observation_capture(
            target,
            error,
            observation_index,
            scheduled_interval_ns,
            launched_ns,
            total_pause_ns,
            observation_ns,
            observation_ns,
            failure_kind,
        )

    failure: _ObservationFailure | None = None
    interruption: _CaptureInterrupted | None = None
    profiler_event_error: _ProfilerEventError | None = None
    stopped_threads: dict[int, _StoppedThread] = {}
    remote_threads: list[_RemoteThread] = []
    observation_unwinder: _Unwinder | None = None
    pause_started_ns = time.monotonic_ns()
    try:
        os.kill(target.pid, signal.SIGSTOP)
        stopped_threads, remote_threads, observation_unwinder = (
            _capture_stopped_threads(
                target_process,
                retained_unwinder,
                mode,
                event_file_descriptor,
            )
        )
    except _CaptureInterrupted as error:
        interruption = error
    except _ProfilerEventError as error:
        profiler_event_error = error
    except (
        OSError,
        RuntimeError,
        UnicodeDecodeError,
        ValueError,
        _TargetExitRaceError,
        _TargetStopError,
    ) as error:
        failure = error
    finally:
        try:
            os.kill(target.pid, signal.SIGCONT)
        except OSError as error:
            failure = _TargetResumeError(str(error))
    pause_ended_ns = time.monotonic_ns()
    pause_duration_ns = pause_ended_ns - pause_started_ns
    if interruption is not None:
        interruption.pause_duration_ns += pause_duration_ns
        raise interruption
    if profiler_event_error is not None:
        profiler_event_error.pause_duration_ns += pause_duration_ns
        raise profiler_event_error
    if failure is not None:
        return _failed_observation_capture(
            target,
            failure,
            observation_index,
            scheduled_interval_ns,
            launched_ns,
            total_pause_ns,
            pause_started_ns,
            pause_ended_ns,
            _observation_failure_kind(failure),
        )
    return _ObservationCapture(
        result=_RawObservation(
            observation_index=observation_index,
            scheduled_interval_ns=scheduled_interval_ns,
            host_monotonic_ns=pause_started_ns,
            target_running_ns=pause_started_ns - launched_ns - total_pause_ns,
            pause_started_ns=pause_started_ns,
            pause_ended_ns=pause_ended_ns,
            pause_duration_ns=pause_duration_ns,
            process_id=target.pid,
            evidence=evidence,
            stopped_threads=stopped_threads,
            remote_threads=remote_threads,
        ),
        unwinder=observation_unwinder,
    )


def _observation_timing(result: _ObservationTiming) -> schema.ObservationBase:
    return {
        "observation_index": result.observation_index,
        "scheduled_interval_ns": result.scheduled_interval_ns,
        "host_monotonic_ns": result.host_monotonic_ns,
        "target_running_ns": result.target_running_ns,
        "pause_started_ns": result.pause_started_ns,
        "pause_ended_ns": result.pause_ended_ns,
        "pause_duration_ns": result.pause_duration_ns,
        "process_id": result.process_id,
    }


def _next_interval_seconds(
    random_generator: random.Random,
    mean_interval_seconds: float,
) -> float:
    # PRF-002: Independent sampling schedule.
    return random_generator.expovariate(1.0 / mean_interval_seconds)


def _missed_exit_observation(
    target: subprocess.Popen[str],
    observation_index: int,
    scheduled_interval_ns: int,
    launched_ns: int,
    total_pause_ns: int,
) -> _FailedObservationResult:
    # PRF-004: No stale-stack reuse. PRF-024: Explicit failures.
    host_monotonic_ns = time.monotonic_ns()
    return _FailedObservationResult(
        observation_index=observation_index,
        scheduled_interval_ns=scheduled_interval_ns,
        host_monotonic_ns=host_monotonic_ns,
        target_running_ns=host_monotonic_ns - launched_ns - total_pause_ns,
        pause_started_ns=host_monotonic_ns,
        pause_ended_ns=host_monotonic_ns,
        pause_duration_ns=0,
        process_id=target.pid,
        status="missed",
        failure_kind=(
            schema.ObservationFailureKind.TARGET_EXITED_BEFORE_SCHEDULED_OBSERVATION
        ),
        failure_reason="the target exited before the scheduled stop",
    )


def _capture_failure(
    kind: schema.CaptureFailureKind,
    reason: str,
    launched_ns: int,
    total_pause_ns: int,
    *,
    python_observed: bool,
) -> schema.FailureRecord:
    # PRF-024: Explicit failures.
    host_monotonic_ns = time.monotonic_ns()
    return {
        "host_monotonic_ns": host_monotonic_ns,
        "target_running_ns": (
            host_monotonic_ns - launched_ns - total_pause_ns
            if python_observed
            else None
        ),
        "kind": kind,
        "reason": reason,
    }


def _terminate_process_group(
    target_process: process_events.TargetProcess,
) -> tuple[int, int]:
    # PRF-023: Guaranteed resume. PRF-026: No silent partial success.
    trace_pause_ns = process_events.release_exec_notifications(target_process)
    target = target_process.process
    try:
        os.killpg(target.pid, signal.SIGTERM)
        os.kill(target.pid, signal.SIGCONT)
    except ProcessLookupError:
        pass
    return target.wait(), trace_pause_ns


def _update_thread_lifecycles(
    lifecycles: dict[tuple[int, int], schema.ThreadLifecycle],
    observation: schema.SuccessfulObservation,
) -> None:
    # PRF-005: Lifecycle-bounded attribution.
    for thread in observation["threads"]:
        thread_id = thread["os_thread_id"]
        start_time_ticks = thread["start_time_ticks"]
        identity = (thread_id, start_time_ticks)
        lifecycle = lifecycles.get(identity)
        if lifecycle is None:
            lifecycles[identity] = {
                "os_thread_id": thread_id,
                "start_time_ticks": start_time_ticks,
                "first_observation_index": observation["observation_index"],
                "first_target_running_ns": observation["target_running_ns"],
                "last_observation_index": observation["observation_index"],
                "last_target_running_ns": observation["target_running_ns"],
            }
        else:
            lifecycle["last_observation_index"] = observation["observation_index"]
            lifecycle["last_target_running_ns"] = observation["target_running_ns"]


def _sampling_statistics(
    observation_times: list[int],
    total_pause_ns: int,
    counts: schema.ObservationCounts,
) -> schema.SamplingStatistics:
    # PRF-003: Pause exclusion. PRF-025: Failure threshold.
    intervals = [
        later - earlier for earlier, later in itertools.pairwise(observation_times)
    ]
    attempted = counts["attempted"]
    return {
        "interval_count": len(intervals),
        "minimum_interval_ns": min(intervals) if intervals else None,
        "mean_interval_ns": sum(intervals) // len(intervals) if intervals else None,
        "maximum_interval_ns": max(intervals) if intervals else None,
        "total_pause_ns": total_pause_ns,
        "discarded_rate": counts["discarded"] / attempted if attempted else 0.0,
    }


@contextlib.contextmanager
def _interruption_handlers() -> collections.abc.Generator[None, None, None]:
    # PRF-024: Explicit failures.
    previous_sigint = signal.signal(signal.SIGINT, _interrupt)
    previous_sigterm = signal.signal(signal.SIGTERM, _interrupt)
    try:
        yield
    finally:
        _ = signal.signal(signal.SIGINT, previous_sigint)
        _ = signal.signal(signal.SIGTERM, previous_sigterm)


def _launch_target(
    command: tuple[str, ...],
    working_directory: pathlib.Path,
    workload_path: pathlib.Path,
    sampling: schema.SamplingConfiguration,
    diagnostics_file: typing.TextIO,
    writer: _ProfileWriter,
) -> tuple[process_events.TargetProcess, int]:
    # PRF-010: Raw-data preservation. PRF-011: Complete invocation.
    # PRF-022: Launcher safety. PRF-049: Event-driven coordination.
    launched_ns = time.monotonic_ns()
    target = subprocess.Popen(
        command,
        cwd=working_directory,
        stderr=diagnostics_file,
        start_new_session=True,
        text=True,
    )
    try:
        target_process = process_events.attach_exec_notifications(target)
    except OSError:
        with contextlib.suppress(ProcessLookupError):
            os.killpg(target.pid, signal.SIGTERM)
        _ = target.wait()
        raise
    writer.append_records(
        [
            {
                "record_type": "header",
                "schema_version": schema.SCHEMA_VERSION,
                "complete": False,
                "command": list(command),
                "working_directory": str(working_directory),
                "workload_path": str(workload_path),
                "workload_sha256": _sha256(workload_path),
                "sampling": sampling,
                "launcher_executable": process_events.executable_identity(target.pid),
                "launched_ns": launched_ns,
            }
        ]
    )
    return target_process, launched_ns


def _attach_runtime(
    target_process: process_events.TargetProcess,
    expected_python: schema.ExecutableIdentity,
    attachment_timeout_seconds: float,
    launched_ns: int,
) -> _AttachedRuntime:
    # PRF-011: Complete invocation. PRF-022: Launcher safety.
    python_executable, attachment_pause_ns = _wait_for_python_executable(
        target_process,
        expected_python,
        attachment_timeout_seconds,
    )
    observed_ns = time.monotonic_ns()
    return _AttachedRuntime(
        runtime=_python_runtime(python_executable),
        observed_ns=observed_ns,
        observed_target_running_ns=observed_ns - launched_ns - attachment_pause_ns,
        attachment_pause_ns=attachment_pause_ns,
    )


def _scheduled_observation(
    target_process: process_events.TargetProcess,
    state: _CaptureState,
    processor: _ObservationProcessor,
    scheduled_interval_ns: int,
    launched_ns: int,
    timer_file_descriptor: int,
    event_file_descriptor: int | None,
) -> tuple[_ObservationWork, bool]:
    # PRF-002: Independent sampling schedule. PRF-004: No stale-stack reuse.
    # PRF-051: Schedule-isolated persistence.
    schedule_event = process_events.wait_for_schedule(
        target_process,
        timer_file_descriptor,
        processor.failure_file_descriptor,
    )
    target = target_process.process
    if schedule_event is process_events.ScheduleEvent.PROCESSOR_FAILED:
        processor.raise_failure()
    if schedule_event is process_events.ScheduleEvent.TARGET_EXITED:
        return (
            _missed_exit_observation(
                target,
                state.observation_index,
                scheduled_interval_ns,
                launched_ns,
                state.total_pause_ns,
            ),
            True,
        )
    captured = _capture_observation(
        target_process,
        state.retained_unwinder,
        state.observation_index,
        scheduled_interval_ns,
        launched_ns,
        state.total_pause_ns,
        state.mode,
        event_file_descriptor,
    )
    state.retained_unwinder = captured.unwinder
    target_exited = (
        isinstance(captured.result, _FailedObservationResult)
        and captured.result.status == "missed"
    )
    return captured.result, target_exited


def _has_python_stack(observation: schema.Observation) -> bool:
    # PRF-011: Complete invocation.
    if observation["status"] != "successful":
        return False
    return any(thread["stack"] for thread in observation["threads"])


def _update_observation_state(
    state: _CaptureState,
    observation: schema.Observation,
    *,
    has_python_stack: bool,
):
    # PRF-004: No stale-stack reuse. PRF-005: Lifecycle-bounded attribution.
    # PRF-024: Explicit failures.
    if observation["status"] == "successful":
        state.counts["attempted"] += 1
        state.counts["successful"] += 1
        if has_python_stack:
            state.python_stack_observations += 1
        _update_thread_lifecycles(state.thread_lifecycles, observation)
        return
    if observation["status"] == "discarded":
        state.counts["attempted"] += 1
        state.counts["discarded"] += 1
        return
    state.counts["missed"] += 1


def _persist_observation(
    writer: _ProfileWriter,
    state: _CaptureState,
    work: _ObservationWork,
    attached_runtime: _AttachedRuntime,
    event_file_descriptor: int | None,
):
    # PRF-022: Launcher safety. PRF-027: Incremental persistence.
    # PRF-050: Minimal stopped section. PRF-051: Schedule-isolated persistence.
    result = _normalize_observation(work) if isinstance(work, _RawObservation) else work
    records, observation = writer.observation_record(result)
    has_python_stack = _has_python_stack(observation)
    if has_python_stack and not state.runtime_recorded:
        records.insert(
            0,
            {
                "record_type": "runtime",
                "python_runtime": attached_runtime.runtime,
                "python_observed_ns": attached_runtime.observed_ns,
                "python_observed_target_running_ns": (
                    attached_runtime.observed_target_running_ns
                ),
            },
        )
        state.runtime_recorded = True
    writer.append_records(records)
    _update_observation_state(
        state,
        observation,
        has_python_stack=has_python_stack,
    )
    if observation["status"] == "successful":
        _emit_profiler_event(
            event_file_descriptor,
            "successful-observation-persisted",
        )


@typing.final
class _ObservationProcessor:
    def __init__(
        self,
        writer: _ProfileWriter,
        state: _CaptureState,
        attached_runtime: _AttachedRuntime,
        event_file_descriptor: int | None,
    ):
        # PRF-027: Incremental persistence.
        # PRF-051: Schedule-isolated persistence.
        self._writer = writer
        self._state = state
        self._attached_runtime = attached_runtime
        self._event_file_descriptor = event_file_descriptor
        self._work: queue.SimpleQueue[_ObservationWork | None] = queue.SimpleQueue()
        self._failure: _ProfilerEventError | _ObservationProcessorError | None = None
        self._failure_recorded = threading.Event()
        self.failure_file_descriptor = os.eventfd(
            0,
            os.EFD_CLOEXEC | os.EFD_NONBLOCK,
        )
        self._thread = threading.Thread(
            target=self._run,
            name="profiler-observation-processor",
        )
        self._thread.start()

    def __enter__(self) -> typing.Self:
        return self

    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        _exception: BaseException | None,
        _traceback: object,
    ) -> typing.Literal[False]:
        self._work.put(None)
        self._thread.join()
        try:
            if exception_type is None:
                self.raise_if_failed()
        finally:
            os.close(self.failure_file_descriptor)
        return False

    def submit(self, work: _ObservationWork):
        # PRF-051: Schedule-isolated persistence.
        self._work.put(work)

    def raise_if_failed(self):
        # PRF-024: Explicit failures. PRF-051: Schedule-isolated persistence.
        if not self._failure_recorded.is_set():
            return
        self.raise_failure()

    def raise_failure(self) -> typing.Never:
        # PRF-024: Explicit failures. PRF-051: Schedule-isolated persistence.
        failure = cast(
            "_ProfilerEventError | _ObservationProcessorError",
            self._failure,
        )
        raise failure

    def _record_failure(
        self,
        failure: _ProfilerEventError | _ObservationProcessorError,
    ):
        # PRF-024: Explicit failures. PRF-051: Schedule-isolated persistence.
        self._failure = failure
        self._failure_recorded.set()
        os.eventfd_write(self.failure_file_descriptor, 1)

    def _run(self):
        # PRF-027: Incremental persistence.
        # PRF-051: Schedule-isolated persistence.
        while (work := self._work.get()) is not None:
            if self._failure_recorded.is_set():
                continue
            try:
                _persist_observation(
                    self._writer,
                    self._state,
                    work,
                    self._attached_runtime,
                    self._event_file_descriptor,
                )
            except _ProfilerEventError as error:
                self._record_failure(error)
            except OSError as error:
                self._record_failure(
                    _ObservationProcessorError(
                        schema.CaptureFailureKind.PROFILE_WRITE_FAILED,
                        f"{type(error).__name__}: {error}",
                    )
                )
            except (TypeError, ValueError) as error:
                self._record_failure(
                    _ObservationProcessorError(
                        schema.CaptureFailureKind.OBSERVATION_SERIALIZATION_FAILED,
                        f"{type(error).__name__}: {error}",
                    )
                )


def _sample_until_exit(
    target_process: process_events.TargetProcess,
    writer: _ProfileWriter,
    state: _CaptureState,
    attached_runtime: _AttachedRuntime,
    mean_interval_seconds: float,
    launched_ns: int,
    timer_file_descriptor: int,
    event_file_descriptor: int | None,
):
    # PRF-002: Independent sampling schedule. PRF-003: Pause exclusion.
    # PRF-027: Incremental persistence. PRF-051: Schedule-isolated persistence.
    with _ObservationProcessor(
        writer,
        state,
        attached_runtime,
        event_file_descriptor,
    ) as processor:
        interval_seconds = _next_interval_seconds(
            state.random_generator,
            mean_interval_seconds,
        )
        scheduled_interval_ns = round(interval_seconds * 1_000_000_000)
        process_events.arm_schedule(timer_file_descriptor, interval_seconds)
        while True:
            result, target_exited = _scheduled_observation(
                target_process,
                state,
                processor,
                scheduled_interval_ns,
                launched_ns,
                timer_file_descriptor,
                event_file_descriptor,
            )
            if not target_exited:
                interval_seconds = _next_interval_seconds(
                    state.random_generator,
                    mean_interval_seconds,
                )
                scheduled_interval_ns = round(interval_seconds * 1_000_000_000)
                process_events.arm_schedule(timer_file_descriptor, interval_seconds)
            state.total_pause_ns += result.pause_duration_ns
            state.observation_pause_ns += result.pause_duration_ns
            state.observation_times.append(result.target_running_ns)
            state.observation_index += 1
            processor.submit(result)
            if target_exited:
                return


def _record_capture_failure(
    writer: _ProfileWriter,
    state: _CaptureState,
    kind: schema.CaptureFailureKind,
    reason: str,
    launched_ns: int,
    *,
    python_observed: bool,
):
    # PRF-024: Explicit failures. PRF-027: Incremental persistence.
    failure = _capture_failure(
        kind,
        reason,
        launched_ns,
        state.total_pause_ns,
        python_observed=python_observed,
    )
    state.failures.append(failure)
    writer.append_records([{"record_type": "failure", "failure": failure}])


def _capture_attached_process(
    target_process: process_events.TargetProcess,
    writer: _ProfileWriter,
    state: _CaptureState,
    expected_python: schema.ExecutableIdentity,
    attachment_timeout_seconds: float,
    mean_interval_seconds: float,
    launched_ns: int,
    timer_file_descriptor: int,
    event_file_descriptor: int | None,
) -> int:
    # PRF-011: Complete invocation. PRF-026: No silent partial success.
    _emit_profiler_event(event_file_descriptor, "launcher-recorded")
    attached_runtime = _attach_runtime(
        target_process,
        expected_python,
        attachment_timeout_seconds,
        launched_ns,
    )
    state.attached_runtime = attached_runtime
    state.total_pause_ns += attached_runtime.attachment_pause_ns
    _emit_profiler_event(event_file_descriptor, "python-attached")
    _sample_until_exit(
        target_process,
        writer,
        state,
        attached_runtime,
        mean_interval_seconds,
        launched_ns,
        timer_file_descriptor,
        event_file_descriptor,
    )
    if state.python_stack_observations == 0:
        _record_capture_failure(
            writer,
            state,
            schema.CaptureFailureKind.TARGET_EXITED_BEFORE_VALID_STACK,
            "the target exited before a valid Python stack was observed",
            launched_ns,
            python_observed=True,
        )
    return target_process.process.wait()


def _wait_after_attachment_failure(
    target_process: process_events.TargetProcess,
) -> tuple[int, int]:
    # PRF-023: Guaranteed resume. PRF-026: No silent partial success.
    trace_pause_ns = process_events.release_exec_notifications(target_process)
    target = target_process.process
    if target.poll() is None:
        exit_status, termination_pause_ns = _terminate_process_group(target_process)
        return exit_status, trace_pause_ns + termination_pause_ns
    return target.wait(), trace_pause_ns


def _capture_process(
    target_process: process_events.TargetProcess,
    writer: _ProfileWriter,
    state: _CaptureState,
    expected_python: schema.ExecutableIdentity,
    attachment_timeout_seconds: float,
    mean_interval_seconds: float,
    launched_ns: int,
    timer_file_descriptor: int,
    event_file_descriptor: int | None,
) -> int:
    # PRF-023: Guaranteed resume. PRF-024: Explicit failures.
    # PRF-026: No silent partial success. PRF-051: Schedule-isolated persistence.
    with _interruption_handlers():
        try:
            return _capture_attached_process(
                target_process,
                writer,
                state,
                expected_python,
                attachment_timeout_seconds,
                mean_interval_seconds,
                launched_ns,
                timer_file_descriptor,
                event_file_descriptor,
            )
        except _AttachmentError as error:
            _record_capture_failure(
                writer,
                state,
                error.kind,
                str(error),
                launched_ns,
                python_observed=False,
            )
            exit_status, trace_pause_ns = _wait_after_attachment_failure(target_process)
            state.total_pause_ns += trace_pause_ns
            return exit_status
        except _ProfilerEventError as error:
            _record_capture_failure(
                writer,
                state,
                schema.CaptureFailureKind.PROFILER_EVENT_WRITE_FAILED,
                str(error),
                launched_ns,
                python_observed=state.attached_runtime is not None,
            )
            exit_status, trace_pause_ns = _terminate_process_group(target_process)
            state.total_pause_ns += error.pause_duration_ns + trace_pause_ns
            state.observation_pause_ns += error.pause_duration_ns
            return exit_status
        except _ObservationProcessorError as error:
            exit_status, trace_pause_ns = _terminate_process_group(target_process)
            state.total_pause_ns += trace_pause_ns
            _record_capture_failure(
                writer,
                state,
                error.kind,
                str(error),
                launched_ns,
                python_observed=state.attached_runtime is not None,
            )
            return exit_status
        except _CaptureInterrupted as interruption:
            exit_status, trace_pause_ns = _terminate_process_group(target_process)
            state.total_pause_ns += interruption.pause_duration_ns + trace_pause_ns
            state.observation_pause_ns += interruption.pause_duration_ns
            state.interruption_signal = interruption.signal_number
            _record_capture_failure(
                writer,
                state,
                schema.CaptureFailureKind.PROFILER_INTERRUPTED,
                signal.Signals(interruption.signal_number).name,
                launched_ns,
                python_observed=state.attached_runtime is not None,
            )
            return exit_status


def _summary_record(
    state: _CaptureState,
    launched_ns: int,
    compiler_exit_status: int,
    diagnostics: str,
) -> schema.SummaryRecord:
    # PRF-025: Failure threshold. PRF-026: No silent partial success.
    exited_ns = time.monotonic_ns()
    statistics = _sampling_statistics(
        state.observation_times,
        state.observation_pause_ns,
        state.counts,
    )
    complete = state.interruption_signal is None
    success = (
        complete
        and state.python_stack_observations > 0
        and statistics["discarded_rate"] <= _MAX_DISCARDED_RATE
        and compiler_exit_status == 0
        and not diagnostics
        and not state.failures
    )
    attached_runtime = state.attached_runtime
    return {
        "record_type": "summary",
        "complete": complete,
        "success": success,
        "lifecycle": {
            "launched_ns": launched_ns,
            "python_observed_ns": (
                attached_runtime.observed_ns if attached_runtime is not None else None
            ),
            "python_observed_target_running_ns": (
                attached_runtime.observed_target_running_ns
                if attached_runtime is not None
                else None
            ),
            "exited_ns": exited_ns,
            "exited_target_running_ns": (
                exited_ns - launched_ns - state.total_pause_ns
            ),
        },
        "thread_lifecycles": sorted(
            state.thread_lifecycles.values(),
            key=lambda lifecycle: (
                lifecycle["os_thread_id"],
                lifecycle["start_time_ticks"],
            ),
        ),
        "sampling_statistics": statistics,
        "observation_counts": state.counts,
        "compiler_exit_status": compiler_exit_status,
        "diagnostics_status": "present" if diagnostics else "none",
        "interruption_signal": state.interruption_signal,
    }


def capture(
    *,
    command: tuple[str, ...],
    profile_path: pathlib.Path,
    workload_path: pathlib.Path,
    working_directory: pathlib.Path,
    mean_interval_seconds: float,
    random_seed: int,
    attachment_timeout_seconds: float,
    mode: schema.CaptureMode,
    event_file_descriptor: int | None = None,
) -> schema.RawProfile:
    """Launch a target and capture continuous blocking observations."""
    # PRF-011: Complete invocation. PRF-014: CPU mode.
    # PRF-020: Machine and human interfaces.
    expected_python = process_events.executable_identity(os.getpid())
    sampling_base: schema.SamplingConfigurationBase = {
        "schedule": "poisson",
        "mean_interval_seconds": mean_interval_seconds,
        "random_seed": random_seed,
        "attachment_timeout_seconds": attachment_timeout_seconds,
    }
    if mode == "cpu":
        sampling: schema.SamplingConfiguration = cpu_profiler.sampling_configuration(
            sampling_base
        )
    else:
        sampling = {**sampling_base, "mode": "wall"}
    # Reproducible statistical schedules do not require cryptographic randomness.
    random_generator = random.Random(random_seed)  # noqa: S311
    state = _CaptureState(
        random_generator=random_generator,
        mode=mode,
        counts={
            "attempted": 0,
            "successful": 0,
            "discarded": 0,
            "missed": 0,
        },
    )

    if event_file_descriptor is not None:
        _ = os.fstat(event_file_descriptor)

    with (
        process_events.blocked_child_signal(),
        contextlib.ExitStack() as file_descriptors,
        tempfile.TemporaryFile(mode="w+", encoding="utf-8") as diagnostics_file,
        profile_path.open("w", encoding="utf-8") as profile_file,
    ):
        timer_file_descriptor = os.timerfd_create(
            time.CLOCK_MONOTONIC,
            flags=os.TFD_CLOEXEC,
        )
        _ = file_descriptors.callback(os.close, timer_file_descriptor)
        writer = _ProfileWriter(profile_file)
        target_process, launched_ns = _launch_target(
            command,
            working_directory,
            workload_path,
            sampling,
            diagnostics_file,
            writer,
        )
        _ = file_descriptors.callback(
            os.close,
            target_process.process_file_descriptor,
        )
        compiler_exit_status = _capture_process(
            target_process,
            writer,
            state,
            expected_python,
            attachment_timeout_seconds,
            mean_interval_seconds,
            launched_ns,
            timer_file_descriptor,
            event_file_descriptor,
        )
        _ = diagnostics_file.seek(0)
        diagnostics = diagnostics_file.read()
        writer.append_records(
            [_summary_record(state, launched_ns, compiler_exit_status, diagnostics)]
        )

    if diagnostics:
        _ = sys.stderr.write(diagnostics)
    return schema.load(profile_path)


# PRF-014: CPU mode. PRF-020: Machine and human interfaces.
@click.command(
    context_settings={"ignore_unknown_options": True},
    epilog=(
        "Place -- before the target command. The profiler waits for the shell "
        "launcher to execute the matching Python 3.14t runtime, then takes "
        "randomized blocking all-thread observations until target exit."
    ),
)
@click.option(
    "--mode",
    type=click.Choice(["wall", "cpu"]),
    default="wall",
    show_default=True,
    help="Capture wall occupancy or external per-thread CPU runtime.",
)
@click.option(
    "--profile",
    "profile_path",
    type=_PATH,
    required=True,
    help="Destination for the versioned raw JSON-record profile.",
)
@click.option(
    "--workload",
    "workload_path",
    type=click.Path(
        path_type=pathlib.Path,
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
    ),
    required=True,
    help="Workload file whose content digest identifies this capture.",
)
@click.option(
    "--working-directory",
    type=click.Path(
        path_type=pathlib.Path,
        exists=True,
        file_okay=False,
        dir_okay=True,
        readable=True,
    ),
    default=".",
    show_default=True,
    help="Working directory for the target command.",
)
@click.option(
    "--mean-interval-seconds",
    type=click.FloatRange(min=0.0, min_open=True),
    default=0.01,
    show_default=True,
    help="Mean target-running time between observations.",
)
@click.option(
    "--attachment-timeout-seconds",
    type=click.FloatRange(min=0.0, min_open=True),
    default=10.0,
    show_default=True,
    help="Maximum time to wait for the launcher to execute matching Python.",
)
@click.option(
    "--event-fd",
    "event_file_descriptor",
    type=click.IntRange(min=0),
    help="Write profiler coordination events as newline-delimited names.",
)
@click.argument("command", nargs=-1, type=click.UNPROCESSED, required=True)
def main(
    mode: schema.CaptureMode,
    profile_path: pathlib.Path,
    workload_path: pathlib.Path,
    working_directory: pathlib.Path,
    mean_interval_seconds: float,
    attachment_timeout_seconds: float,
    event_file_descriptor: int | None,
    command: tuple[str, ...],
):
    """Capture a continuous blocking wall or CPU profile of a Python target."""
    # PRF-002: Independent sampling schedule. PRF-014: CPU mode.
    # PRF-020: Machine and human interfaces. PRF-025: Failure threshold.
    # PRF-049: Event-driven coordination.
    profile = capture(
        command=command,
        profile_path=profile_path.absolute(),
        workload_path=workload_path.absolute(),
        working_directory=working_directory.absolute(),
        mean_interval_seconds=mean_interval_seconds,
        random_seed=random.SystemRandom().randrange(2**63),
        attachment_timeout_seconds=attachment_timeout_seconds,
        mode=mode,
        event_file_descriptor=event_file_descriptor,
    )
    counts = profile.observation_counts
    statistics = cast("schema.SamplingStatistics", profile.sampling_statistics)
    discarded_rate = statistics["discarded_rate"]
    status = "successful" if profile.success else "unsuccessful"
    completeness = "complete" if profile.complete else "incomplete"
    click.echo(f"Profile: {profile_path.absolute()}")
    click.echo(
        f"Capture: {completeness}; {status}; "
        + f"compiler exit {profile.compiler_exit_status}; "
        + f"diagnostics {profile.diagnostics_status}"
    )
    click.echo(
        f"Observations: {counts['successful']} successful, "
        + f"{counts['discarded']} discarded, {counts['missed']} missed; "
        + f"discarded rate {discarded_rate:.3%}"
    )
    if not profile.complete:
        raise click.Abort
    if not profile.success:
        raise click.ClickException("profile capture was not successful")
