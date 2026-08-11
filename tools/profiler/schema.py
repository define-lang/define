"""Raw data structures for the Define compiler profiler."""

from __future__ import annotations

import dataclasses
import json
import typing
from typing import Literal, TypedDict, cast

if typing.TYPE_CHECKING:
    import collections.abc
    import pathlib

# PRF-010: Raw-data preservation. PRF-020: Machine and human interfaces.
SCHEMA_VERSION = 3

CaptureMode = Literal["wall", "cpu"]


class ExecutableIdentity(TypedDict):
    """Identity of an executable observed through ``/proc``."""

    # PRF-021: Version match.
    path: str
    device: int
    inode: int


class PythonRuntime(TypedDict):
    """Properties of the sampled Python runtime."""

    # PRF-021: Version match.
    version: str
    minor_version: str
    free_threaded: bool
    executable: ExecutableIdentity


class Frame(TypedDict):
    """One interned Python frame."""

    # PRF-015: Full stacks. PRF-016: Source identity.
    frame_id: int
    filename: str
    function: str
    line: int


class ThreadObservation(TypedDict):
    """One stopped OS thread and its complete available Python stack."""

    # PRF-006: Complete-process stop. PRF-013: Wall mode.
    os_thread_id: int
    start_time_ticks: int
    pre_stop_state: str
    wait_channel: str
    voluntary_context_switches: int
    nonvoluntary_context_switches: int
    stopped_state: str
    stack: list[int]


class CpuThreadObservation(ThreadObservation):
    """One stopped OS thread with synchronized scheduler runtime."""

    # PRF-010: Raw-data preservation. PRF-014: CPU mode.
    scheduler_runtime_ns: int


SampledThreadObservation = ThreadObservation | CpuThreadObservation


class ObservationBase(TypedDict):
    """Timing shared by successful and failed observation points."""

    # PRF-003: Pause exclusion. PRF-010: Raw-data preservation.
    observation_index: int
    scheduled_interval_ns: int
    host_monotonic_ns: int
    target_running_ns: int
    pause_started_ns: int
    pause_ended_ns: int
    pause_duration_ns: int
    process_id: int


class SuccessfulObservation(ObservationBase):
    """One coherent complete-process observation."""

    # PRF-007: Consistent stack. PRF-015: Full stacks.
    status: Literal["successful"]
    threads: list[SampledThreadObservation]


class FailedObservation(ObservationBase):
    """One discarded or missed observation with no retained stack."""

    # PRF-004: No stale-stack reuse. PRF-024: Explicit failures.
    status: Literal["discarded", "missed"]
    failure_kind: str
    failure_reason: str


Observation = SuccessfulObservation | FailedObservation


class FailureRecord(TypedDict):
    """An explicit capture failure encountered outside an observation."""

    # PRF-024: Explicit failures.
    host_monotonic_ns: int
    target_running_ns: int | None
    kind: str
    reason: str


class Lifecycle(TypedDict):
    """Observed host and target-running process lifecycle timestamps."""

    # PRF-003: Pause exclusion. PRF-011: Complete invocation.
    launched_ns: int
    python_observed_ns: int | None
    python_observed_target_running_ns: int | None
    exited_ns: int | None
    exited_target_running_ns: int | None


class ThreadLifecycle(TypedDict):
    """First and final valid observations of one OS thread."""

    # PRF-005: Lifecycle-bounded attribution.
    os_thread_id: int
    start_time_ticks: int
    first_observation_index: int
    first_target_running_ns: int
    last_observation_index: int
    last_target_running_ns: int


class ObservationCounts(TypedDict):
    """Counts of attempted and retained process observations."""

    # PRF-024: Explicit failures. PRF-026: No silent partial success.
    attempted: int
    successful: int
    discarded: int
    missed: int


class SamplingConfigurationBase(TypedDict):
    """Configuration shared by randomized continuous sampling modes."""

    # PRF-002: Independent sampling schedule.
    schedule: Literal["poisson"]
    mean_interval_seconds: float
    random_seed: int
    attachment_timeout_seconds: float


class WallSamplingConfiguration(SamplingConfigurationBase):
    """Configuration for continuous wall sampling."""

    # PRF-013: Wall mode.
    mode: Literal["wall"]


class CpuSamplingConfiguration(SamplingConfigurationBase):
    """Configuration for external scheduler-runtime CPU sampling."""

    # PRF-014: CPU mode.
    mode: Literal["cpu"]
    cpu_backend: Literal["linux-schedstat"]
    python_stack_trampolines: Literal[False]


SamplingConfiguration = WallSamplingConfiguration | CpuSamplingConfiguration


class SamplingStatistics(TypedDict):
    """Observed interval and profiler-pause statistics."""

    # PRF-003: Pause exclusion. PRF-025: Failure threshold.
    interval_count: int
    minimum_interval_ns: int | None
    mean_interval_ns: int | None
    maximum_interval_ns: int | None
    total_pause_ns: int
    discarded_rate: float


class HeaderRecord(TypedDict):
    """First record in every raw profile."""

    # PRF-027: Incremental persistence.
    record_type: Literal["header"]
    schema_version: int
    complete: Literal[False]
    command: list[str]
    working_directory: str
    workload_path: str
    workload_sha256: str
    sampling: SamplingConfiguration
    launcher_executable: ExecutableIdentity
    launched_ns: int


class RuntimeRecord(TypedDict):
    """Launcher-to-Python transition evidence."""

    # PRF-011: Complete invocation. PRF-022: Launcher safety.
    record_type: Literal["runtime"]
    python_runtime: PythonRuntime
    python_observed_ns: int
    python_observed_target_running_ns: int


class FrameRecord(TypedDict):
    """Definition of one frame referenced by later observations."""

    # PRF-028: Bounded storage.
    record_type: Literal["frame"]
    frame: Frame


class ObservationRecord(TypedDict):
    """One incrementally persisted observation point."""

    # PRF-027: Incremental persistence.
    record_type: Literal["observation"]
    observation: Observation


class FailureEventRecord(TypedDict):
    """One incrementally persisted capture-level failure."""

    # PRF-024: Explicit failures. PRF-027: Incremental persistence.
    record_type: Literal["failure"]
    failure: FailureRecord


class SummaryRecord(TypedDict):
    """Final record of a capture that shut down under profiler control."""

    # PRF-026: No silent partial success. PRF-027: Incremental persistence.
    record_type: Literal["summary"]
    complete: bool
    success: bool
    lifecycle: Lifecycle
    thread_lifecycles: list[ThreadLifecycle]
    sampling_statistics: SamplingStatistics
    observation_counts: ObservationCounts
    compiler_exit_status: int
    diagnostics_status: Literal["none", "present"]
    interruption_signal: int | None


ProfileRecord = (
    HeaderRecord
    | RuntimeRecord
    | FrameRecord
    | ObservationRecord
    | FailureEventRecord
    | SummaryRecord
)


@dataclasses.dataclass(slots=True)
class RawProfile:
    """Loaded version 3 continuous wall or CPU profile artifact."""

    # PRF-010: Raw-data preservation. PRF-020: Machine and human interfaces.
    schema_version: int
    complete: bool
    success: bool
    command: list[str]
    working_directory: str
    workload_path: str
    workload_sha256: str
    sampling: SamplingConfiguration
    sampling_statistics: SamplingStatistics | None
    launcher_executable: ExecutableIdentity
    python_runtime: PythonRuntime | None
    lifecycle: Lifecycle
    frames: dict[int, Frame]
    observations: list[Observation]
    failures: list[FailureRecord]
    thread_lifecycles: list[ThreadLifecycle]
    observation_counts: ObservationCounts
    compiler_exit_status: int | None
    diagnostics_status: Literal["none", "present", "unknown"]
    interruption_signal: int | None


def _read_records(
    profile_path: pathlib.Path,
) -> collections.abc.Iterator[dict[str, object]]:
    # PRF-027: Incremental persistence.
    with profile_path.open(encoding="utf-8") as profile_file:
        line_number = 1
        current_line = profile_file.readline()
        while current_line:
            next_line = profile_file.readline()
            try:
                record = cast("object", json.loads(current_line))
            except json.JSONDecodeError as error:
                if not next_line and not current_line.endswith("\n"):
                    return
                raise ValueError(
                    f"invalid profile record on line {line_number}: {error.msg}"
                ) from error
            if not isinstance(record, dict):
                raise TypeError(
                    f"profile record on line {line_number} is not an object"
                )
            yield cast("dict[str, object]", record)
            current_line = next_line
            line_number += 1


def _initial_profile(header: HeaderRecord) -> RawProfile:
    return RawProfile(
        schema_version=header["schema_version"],
        complete=False,
        success=False,
        command=header["command"],
        working_directory=header["working_directory"],
        workload_path=header["workload_path"],
        workload_sha256=header["workload_sha256"],
        sampling=header["sampling"],
        sampling_statistics=None,
        launcher_executable=header["launcher_executable"],
        python_runtime=None,
        lifecycle={
            "launched_ns": header["launched_ns"],
            "python_observed_ns": None,
            "python_observed_target_running_ns": None,
            "exited_ns": None,
            "exited_target_running_ns": None,
        },
        frames={},
        observations=[],
        failures=[],
        thread_lifecycles=[],
        observation_counts={
            "attempted": 0,
            "successful": 0,
            "discarded": 0,
            "missed": 0,
        },
        compiler_exit_status=None,
        diagnostics_status="unknown",
        interruption_signal=None,
    )


def load(profile_path: pathlib.Path) -> RawProfile:
    """Load a complete or incrementally persisted version 3 profile."""
    # PRF-027: Incremental persistence.
    records = iter(_read_records(profile_path))
    try:
        first_record = next(records)
    except StopIteration as error:
        raise ValueError("profile contains no complete records") from error
    if first_record.get("record_type") != "header":
        raise ValueError("the first profile record is not a header")
    header = cast("HeaderRecord", cast("object", first_record))
    if header["schema_version"] != SCHEMA_VERSION:
        raise ValueError(
            f"unsupported profiler schema version: {header['schema_version']}"
        )
    profile = _initial_profile(header)
    summary_seen = False
    for record_data in records:
        record_type = record_data.get("record_type")
        if summary_seen:
            raise ValueError("profile contains records after its summary")
        if record_type == "runtime":
            runtime_record = cast("RuntimeRecord", cast("object", record_data))
            profile.python_runtime = runtime_record["python_runtime"]
            profile.lifecycle["python_observed_ns"] = runtime_record[
                "python_observed_ns"
            ]
            profile.lifecycle["python_observed_target_running_ns"] = runtime_record[
                "python_observed_target_running_ns"
            ]
        elif record_type == "frame":
            frame = cast("FrameRecord", cast("object", record_data))["frame"]
            profile.frames[frame["frame_id"]] = frame
        elif record_type == "observation":
            observation = cast("ObservationRecord", cast("object", record_data))[
                "observation"
            ]
            profile.observations.append(observation)
        elif record_type == "failure":
            failure = cast("FailureEventRecord", cast("object", record_data))["failure"]
            profile.failures.append(failure)
        elif record_type == "summary":
            summary = cast("SummaryRecord", cast("object", record_data))
            profile.complete = summary["complete"]
            profile.success = summary["success"]
            profile.lifecycle = summary["lifecycle"]
            profile.thread_lifecycles = summary["thread_lifecycles"]
            profile.sampling_statistics = summary["sampling_statistics"]
            profile.observation_counts = summary["observation_counts"]
            profile.compiler_exit_status = summary["compiler_exit_status"]
            profile.diagnostics_status = summary["diagnostics_status"]
            profile.interruption_signal = summary["interruption_signal"]
            summary_seen = True
        else:
            raise ValueError(f"unknown profile record type: {record_type!r}")
    return profile
