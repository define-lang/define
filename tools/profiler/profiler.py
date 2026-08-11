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
import random
import signal
import subprocess
import sys
import sysconfig
import tempfile
import time
import typing
from typing import Protocol, cast

import _remote_debugging  # pyright: ignore[reportMissingImports]
import click

from tools.profiler import cpu_profiler, schema

if typing.TYPE_CHECKING:
    import collections.abc

_PATH = click.Path(path_type=pathlib.Path)
_ATTACHMENT_POLL_SECONDS = 0.005
_MAX_DISCARDED_RATE = 0.001


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
    kind: str

    def __init__(self, kind: str, reason: str):
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
class _FailedObservationResult(_ObservationTiming):
    # PRF-004: No stale-stack reuse. PRF-024: Explicit failures.
    status: typing.Literal["discarded", "missed"]
    failure_kind: str
    failure_reason: str


_ObservationResult = _SuccessfulObservationResult | _FailedObservationResult


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
    result: _ObservationResult
    unwinder: _Unwinder | None


@dataclasses.dataclass(frozen=True, slots=True)
class _AttachedRuntime:
    # PRF-011: Complete invocation. PRF-022: Launcher safety.
    runtime: schema.PythonRuntime
    observed_ns: int
    observed_target_running_ns: int


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


def _sha256(path: pathlib.Path) -> str:
    # PRF-010: Raw-data preservation.
    digest = hashlib.sha256()
    with path.open("rb") as source_file:
        while chunk := source_file.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _executable_identity(process_id: int) -> schema.ExecutableIdentity:
    # PRF-021: Version match.
    executable_path = pathlib.Path(os.readlink(f"/proc/{process_id}/exe"))
    executable_stat = executable_path.stat()
    return {
        "path": str(executable_path),
        "device": executable_stat.st_dev,
        "inode": executable_stat.st_ino,
    }


def _same_executable(
    first: schema.ExecutableIdentity, second: schema.ExecutableIdentity
) -> bool:
    # PRF-021: Version match.
    return (first["device"], first["inode"]) == (
        second["device"],
        second["inode"],
    )


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
    target: subprocess.Popen[str],
    expected_python: schema.ExecutableIdentity,
    attachment_timeout_seconds: float,
) -> schema.ExecutableIdentity:
    # PRF-021: Version match. PRF-022: Launcher safety.
    attachment_deadline = time.monotonic() + attachment_timeout_seconds
    while target.poll() is None:
        current_executable = _executable_identity(target.pid)
        if _same_executable(current_executable, expected_python):
            return current_executable
        if time.monotonic() >= attachment_deadline:
            raise _AttachmentError(
                "attachment-timeout",
                "the target did not execute the profiler's Python runtime",
            )
        time.sleep(_ATTACHMENT_POLL_SECONDS)
    raise _AttachmentError(
        "target-exited-before-attachment",
        "the target exited before its launcher executed the Python runtime",
    )


def _status_fields(status: str) -> dict[str, str]:
    return {
        name: value.strip()
        for line in status.splitlines()
        if ":" in line
        for name, value in [line.split(":", 1)]
    }


def _thread_start_time_ticks(thread_directory: pathlib.Path) -> int:
    # PRF-010: Raw-data preservation. A Linux TID can be reused after thread exit.
    stat = (thread_directory / "stat").read_text(encoding="utf-8")
    command_end = stat.rindex(")")
    fields_from_state = stat[command_end + 2 :].split()
    return int(fields_from_state[19])


def _thread_evidence(process_id: int) -> dict[int, _ThreadEvidence]:
    # PRF-010: Raw-data preservation.
    evidence: dict[int, _ThreadEvidence] = {}
    for thread_directory in pathlib.Path(f"/proc/{process_id}/task").iterdir():
        fields = _status_fields(
            (thread_directory / "status").read_text(encoding="utf-8")
        )
        evidence[int(thread_directory.name)] = _ThreadEvidence(
            start_time_ticks=_thread_start_time_ticks(thread_directory),
            state=fields["State"].split()[0],
            wait_channel=(thread_directory / "wchan")
            .read_text(encoding="utf-8")
            .strip(),
            voluntary_context_switches=int(fields["voluntary_ctxt_switches"]),
            nonvoluntary_context_switches=int(fields["nonvoluntary_ctxt_switches"]),
        )
    return evidence


def _stopped_threads(process_id: int) -> dict[int, _StoppedThread]:
    # PRF-005: Lifecycle-bounded attribution. PRF-006: Complete-process stop.
    stopped_threads: dict[int, _StoppedThread] = {}
    for thread_directory in pathlib.Path(f"/proc/{process_id}/task").iterdir():
        fields = _status_fields(
            (thread_directory / "status").read_text(encoding="utf-8")
        )
        stopped_threads[int(thread_directory.name)] = _StoppedThread(
            start_time_ticks=_thread_start_time_ticks(thread_directory),
            state=fields["State"].split()[0],
        )
    return stopped_threads


def _capture_stopped_threads(
    target: subprocess.Popen[str],
    evidence: dict[int, _ThreadEvidence],
    retained_unwinder: _Unwinder | None,
    mode: schema.CaptureMode,
) -> tuple[list[_CapturedThread], _Unwinder]:
    # PRF-006: Complete-process stop. PRF-007: Consistent stack.
    # PRF-013: Wall mode. PRF-015: Full stacks. PRF-016: Source identity.
    wait_result = os.waitid(
        os.P_PID,
        target.pid,
        os.WSTOPPED | os.WEXITED | os.WNOWAIT,
    )
    if wait_result is None or wait_result.si_code != os.CLD_STOPPED:
        raise _TargetExitRaceError(
            "target exited while the profiler was stopping it with status "
            + str(target.wait())
        )
    waited_process_id, wait_status = os.waitpid(target.pid, os.WUNTRACED)
    if waited_process_id != target.pid or not os.WIFSTOPPED(wait_status):
        raise _TargetStopError("target exited while the profiler was stopping it")
    stopped_threads = _stopped_threads(target.pid)
    if any(
        stopped_thread.state not in {"T", "t"}
        for stopped_thread in stopped_threads.values()
    ):
        raise _TargetStopError("not every target thread reached a stopped state")
    # PRF-006: Complete-process stop. PRF-014: CPU mode.
    scheduler_runtimes = (
        cpu_profiler.scheduler_runtimes(target.pid) if mode == "cpu" else None
    )
    observation_unwinder = retained_unwinder or _REMOTE_UNWINDER(
        target.pid,
        all_threads=True,
    )
    remote_threads = cast(
        "list[_RemoteThread]",
        observation_unwinder.get_stack_trace(),
    )
    remote_threads_by_id = {
        remote_thread.thread_id: remote_thread for remote_thread in remote_threads
    }
    for remote_thread in remote_threads:
        if (
            remote_thread.thread_id not in evidence
            or remote_thread.thread_id not in stopped_threads
        ):
            raise _InconsistentStackObservationError(
                "a Python thread changed identity during the observation"
            )
    captured_threads: list[_CapturedThread] = []
    for thread_id, stopped_thread in stopped_threads.items():
        thread_evidence = evidence.get(thread_id)
        if thread_evidence is None:
            raise _InconsistentStackObservationError(
                "an OS thread changed identity during the observation"
            )
        if thread_evidence.start_time_ticks != stopped_thread.start_time_ticks:
            raise _InconsistentStackObservationError(
                "an OS thread identifier was reused during the observation"
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
                scheduler_runtime_ns=(
                    scheduler_runtimes[thread_id]
                    if scheduler_runtimes is not None
                    else None
                ),
            )
        )
    return captured_threads, observation_unwinder


def _failed_observation_capture(
    target: subprocess.Popen[str],
    failure: Exception,
    observation_index: int,
    scheduled_interval_ns: int,
    launched_ns: int,
    total_pause_ns: int,
    pause_started_ns: int,
    pause_ended_ns: int,
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
                "target-exited-during-observation"
                if process_exit_confirmed
                else type(failure).__name__
            ),
            failure_reason=str(failure),
        ),
        unwinder=None,
    )


def _capture_observation(
    target: subprocess.Popen[str],
    retained_unwinder: _Unwinder | None,
    observation_index: int,
    scheduled_interval_ns: int,
    launched_ns: int,
    total_pause_ns: int,
    mode: schema.CaptureMode,
) -> _ObservationCapture:
    # PRF-003: Pause exclusion. PRF-006: Complete-process stop.
    # PRF-007: Consistent stack. PRF-013: Wall mode.
    # PRF-015: Full stacks. PRF-016: Source identity.
    # PRF-023: Guaranteed resume.
    try:
        evidence = _thread_evidence(target.pid)
    except _CaptureInterrupted:
        raise
    except (OSError, UnicodeDecodeError, ValueError) as error:
        observation_ns = time.monotonic_ns()
        return _failed_observation_capture(
            target,
            error,
            observation_index,
            scheduled_interval_ns,
            launched_ns,
            total_pause_ns,
            observation_ns,
            observation_ns,
        )

    failure: Exception | None = None
    interruption: _CaptureInterrupted | None = None
    captured_threads: list[_CapturedThread] = []
    observation_unwinder: _Unwinder | None = None
    pause_started_ns = time.monotonic_ns()
    try:
        os.kill(target.pid, signal.SIGSTOP)
        captured_threads, observation_unwinder = _capture_stopped_threads(
            target,
            evidence,
            retained_unwinder,
            mode,
        )
    except _CaptureInterrupted as error:
        interruption = error
    except (
        OSError,
        RuntimeError,
        UnicodeDecodeError,
        ValueError,
        _InconsistentStackObservationError,
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
        )
    return _ObservationCapture(
        result=_SuccessfulObservationResult(
            observation_index=observation_index,
            scheduled_interval_ns=scheduled_interval_ns,
            host_monotonic_ns=pause_started_ns,
            target_running_ns=pause_started_ns - launched_ns - total_pause_ns,
            pause_started_ns=pause_started_ns,
            pause_ended_ns=pause_ended_ns,
            pause_duration_ns=pause_duration_ns,
            process_id=target.pid,
            threads=captured_threads,
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


def _wait_for_schedule(target: subprocess.Popen[str], interval_seconds: float) -> bool:
    # PRF-002: Independent sampling schedule.
    deadline = time.monotonic() + interval_seconds
    while target.poll() is None:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return True
        time.sleep(min(_ATTACHMENT_POLL_SECONDS, remaining))
    return False


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
        failure_kind="target-exited-before-scheduled-observation",
        failure_reason="the target exited before the scheduled stop",
    )


def _capture_failure(
    kind: str,
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


def _terminate_process_group(target: subprocess.Popen[str]) -> int:
    # PRF-023: Guaranteed resume. PRF-026: No silent partial success.
    try:
        os.killpg(target.pid, signal.SIGTERM)
        os.kill(target.pid, signal.SIGCONT)
    except ProcessLookupError:
        pass
    return target.wait()


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
) -> tuple[subprocess.Popen[str], int]:
    # PRF-010: Raw-data preservation. PRF-011: Complete invocation.
    launched_ns = time.monotonic_ns()
    target = subprocess.Popen(
        command,
        cwd=working_directory,
        stderr=diagnostics_file,
        start_new_session=True,
        text=True,
    )
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
                "launcher_executable": _executable_identity(target.pid),
                "launched_ns": launched_ns,
            }
        ]
    )
    return target, launched_ns


def _attach_runtime(
    target: subprocess.Popen[str],
    expected_python: schema.ExecutableIdentity,
    attachment_timeout_seconds: float,
    launched_ns: int,
) -> _AttachedRuntime:
    # PRF-011: Complete invocation. PRF-022: Launcher safety.
    python_executable = _wait_for_python_executable(
        target,
        expected_python,
        attachment_timeout_seconds,
    )
    observed_ns = time.monotonic_ns()
    return _AttachedRuntime(
        runtime=_python_runtime(python_executable),
        observed_ns=observed_ns,
        observed_target_running_ns=observed_ns - launched_ns,
    )


def _scheduled_observation(
    target: subprocess.Popen[str],
    state: _CaptureState,
    mean_interval_seconds: float,
    launched_ns: int,
) -> tuple[_ObservationResult, bool]:
    # PRF-002: Independent sampling schedule. PRF-004: No stale-stack reuse.
    interval_seconds = _next_interval_seconds(
        state.random_generator,
        mean_interval_seconds,
    )
    scheduled_interval_ns = round(interval_seconds * 1_000_000_000)
    target_exited = not _wait_for_schedule(target, interval_seconds)
    if target_exited:
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
        target,
        state.retained_unwinder,
        state.observation_index,
        scheduled_interval_ns,
        launched_ns,
        state.total_pause_ns,
        state.mode,
    )
    state.retained_unwinder = captured.unwinder
    return captured.result, False


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
    state.observation_times.append(observation["target_running_ns"])
    state.observation_index += 1
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
    result: _ObservationResult,
    attached_runtime: _AttachedRuntime,
):
    # PRF-022: Launcher safety. PRF-027: Incremental persistence.
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


def _sample_until_exit(
    target: subprocess.Popen[str],
    writer: _ProfileWriter,
    state: _CaptureState,
    attached_runtime: _AttachedRuntime,
    mean_interval_seconds: float,
    launched_ns: int,
):
    # PRF-002: Independent sampling schedule. PRF-003: Pause exclusion.
    # PRF-027: Incremental persistence.
    while target.poll() is None:
        result, target_exited = _scheduled_observation(
            target,
            state,
            mean_interval_seconds,
            launched_ns,
        )
        state.total_pause_ns += result.pause_duration_ns
        with _blocked_interruption_signals():
            _persist_observation(writer, state, result, attached_runtime)
        if target_exited:
            return


def _record_capture_failure(
    writer: _ProfileWriter,
    state: _CaptureState,
    kind: str,
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
    target: subprocess.Popen[str],
    writer: _ProfileWriter,
    state: _CaptureState,
    expected_python: schema.ExecutableIdentity,
    attachment_timeout_seconds: float,
    mean_interval_seconds: float,
    launched_ns: int,
) -> int:
    # PRF-011: Complete invocation. PRF-026: No silent partial success.
    attached_runtime = _attach_runtime(
        target,
        expected_python,
        attachment_timeout_seconds,
        launched_ns,
    )
    state.attached_runtime = attached_runtime
    _sample_until_exit(
        target,
        writer,
        state,
        attached_runtime,
        mean_interval_seconds,
        launched_ns,
    )
    if state.python_stack_observations == 0:
        _record_capture_failure(
            writer,
            state,
            "target-exited-before-valid-stack",
            "the target exited before a valid Python stack was observed",
            launched_ns,
            python_observed=True,
        )
    return target.wait()


def _wait_after_attachment_failure(target: subprocess.Popen[str]) -> int:
    # PRF-023: Guaranteed resume. PRF-026: No silent partial success.
    if target.poll() is None:
        return _terminate_process_group(target)
    return target.wait()


def _capture_process(
    target: subprocess.Popen[str],
    writer: _ProfileWriter,
    state: _CaptureState,
    expected_python: schema.ExecutableIdentity,
    attachment_timeout_seconds: float,
    mean_interval_seconds: float,
    launched_ns: int,
) -> int:
    # PRF-023: Guaranteed resume. PRF-024: Explicit failures.
    # PRF-026: No silent partial success.
    with _interruption_handlers():
        try:
            return _capture_attached_process(
                target,
                writer,
                state,
                expected_python,
                attachment_timeout_seconds,
                mean_interval_seconds,
                launched_ns,
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
            return _wait_after_attachment_failure(target)
        except _CaptureInterrupted as interruption:
            state.total_pause_ns += interruption.pause_duration_ns
            state.interruption_signal = interruption.signal_number
            _record_capture_failure(
                writer,
                state,
                "profiler-interrupted",
                signal.Signals(interruption.signal_number).name,
                launched_ns,
                python_observed=state.attached_runtime is not None,
            )
            return _terminate_process_group(target)


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
        state.total_pause_ns,
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
) -> schema.RawProfile:
    """Launch a target and capture continuous blocking observations."""
    # PRF-011: Complete invocation. PRF-014: CPU mode.
    # PRF-020: Machine and human interfaces.
    expected_python = _executable_identity(os.getpid())
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

    with (
        tempfile.TemporaryFile(mode="w+", encoding="utf-8") as diagnostics_file,
        profile_path.open("w", encoding="utf-8") as profile_file,
    ):
        writer = _ProfileWriter(profile_file)
        target, launched_ns = _launch_target(
            command,
            working_directory,
            workload_path,
            sampling,
            diagnostics_file,
            writer,
        )
        compiler_exit_status = _capture_process(
            target,
            writer,
            state,
            expected_python,
            attachment_timeout_seconds,
            mean_interval_seconds,
            launched_ns,
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
@click.argument("command", nargs=-1, type=click.UNPROCESSED, required=True)
def main(
    mode: schema.CaptureMode,
    profile_path: pathlib.Path,
    workload_path: pathlib.Path,
    working_directory: pathlib.Path,
    mean_interval_seconds: float,
    attachment_timeout_seconds: float,
    command: tuple[str, ...],
):
    """Capture a continuous blocking wall or CPU profile of a Python target."""
    # PRF-002: Independent sampling schedule. PRF-014: CPU mode.
    # PRF-020: Machine and human interfaces. PRF-025: Failure threshold.
    profile = capture(
        command=command,
        profile_path=profile_path.absolute(),
        workload_path=workload_path.absolute(),
        working_directory=working_directory.absolute(),
        mean_interval_seconds=mean_interval_seconds,
        random_seed=random.SystemRandom().randrange(2**63),
        attachment_timeout_seconds=attachment_timeout_seconds,
        mode=mode,
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
