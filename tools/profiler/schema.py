"""Raw data structures for the Define compiler profiler."""

from __future__ import annotations

import dataclasses
import enum
import json
import typing
from typing import Literal, TypedDict, cast

if typing.TYPE_CHECKING:
    import collections.abc
    import pathlib

# PRF-010: Raw-data preservation. PRF-020: Machine and human interfaces.
SCHEMA_VERSION = 7
MAX_DISCARDED_RATE = 0.001

CaptureMode = Literal["wall", "cpu"]


class ObservationFailureKind(enum.StrEnum):
    """Stable machine-readable reasons an observation was not retained."""

    # PRF-004: No stale-stack reuse. PRF-024: Explicit failures.
    INCONSISTENT_STACK = "inconsistent-stack"
    MALFORMED_OBSERVATION = "malformed-observation"
    OBSERVATION_SYSTEM_ERROR = "observation-system-error"
    PERMISSION_DENIED = "permission-denied"
    STACK_UNWIND_FAILED = "stack-unwind-failed"
    TARGET_EXITED_BEFORE_SCHEDULED_OBSERVATION = (
        "target-exited-before-scheduled-observation"
    )
    TARGET_EXITED_DURING_OBSERVATION = "target-exited-during-observation"
    TARGET_RESUME_FAILED = "target-resume-failed"
    TARGET_STOP_FAILED = "target-stop-failed"
    THREAD_EVIDENCE_READ_FAILED = "thread-evidence-read-failed"


class CaptureFailureKind(enum.StrEnum):
    """Stable machine-readable reasons an entire capture failed."""

    # PRF-024: Explicit failures. PRF-026: No silent partial success.
    ATTACHMENT_TIMEOUT = "attachment-timeout"
    OBSERVATION_SERIALIZATION_FAILED = "observation-serialization-failed"
    PROFILE_WRITE_FAILED = "profile-write-failed"
    PROFILER_EVENT_WRITE_FAILED = "profiler-event-write-failed"
    PROFILER_INTERRUPTED = "profiler-interrupted"
    TARGET_EXITED_BEFORE_ATTACHMENT = "target-exited-before-attachment"
    TARGET_EXITED_BEFORE_VALID_STACK = "target-exited-before-valid-stack"


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
    free_threaded: bool
    executable: ExecutableIdentity


class Frame(TypedDict):
    """One interned Python frame."""

    # PRF-015: Full stacks. PRF-016: Source identity.
    filename: str
    function: str
    line: int


class ThreadObservation(TypedDict):
    """One stopped OS thread and its complete available Python stack."""

    # PRF-006: Complete-process stop. PRF-013: Wall mode.
    os_thread_id: int
    start_time_ticks: int
    pre_stop_state: str
    stack: list[int]


class CpuThreadObservation(ThreadObservation):
    """One stopped OS thread with synchronized scheduler runtime."""

    # PRF-010: Raw-data preservation. PRF-014: CPU mode.
    scheduler_runtime_ns: int


SampledThreadObservation = ThreadObservation | CpuThreadObservation


class ObservationBase(TypedDict):
    """Timing shared by successful and failed observation points."""

    # PRF-003: Pause exclusion. PRF-010: Raw-data preservation.
    scheduled_interval_ns: int
    target_running_ns: int
    pause_started_ns: int
    pause_ended_ns: int


class SuccessfulObservation(ObservationBase):
    """One coherent complete-process observation."""

    # PRF-007: Consistent stack. PRF-015: Full stacks.
    status: Literal["successful"]
    threads: list[SampledThreadObservation]


class FailedObservation(ObservationBase):
    """One discarded or missed observation with no retained stack."""

    # PRF-004: No stale-stack reuse. PRF-024: Explicit failures.
    status: Literal["discarded", "missed"]
    failure_kind: ObservationFailureKind
    failure_reason: str


Observation = SuccessfulObservation | FailedObservation


class FailureRecord(TypedDict):
    """An explicit capture failure encountered outside an observation."""

    # PRF-024: Explicit failures.
    host_monotonic_ns: int
    target_running_ns: int | None
    kind: CaptureFailureKind
    reason: str


class Lifecycle(TypedDict):
    """Observed host and target-running process lifecycle timestamps."""

    # PRF-003: Pause exclusion. PRF-011: Complete invocation.
    launched_ns: int
    python_observed_ns: int | None
    python_observed_target_running_ns: int | None
    exited_ns: int | None
    exited_target_running_ns: int | None


class ObservationCounts(TypedDict):
    """Counts of attempted and retained process observations."""

    # PRF-024: Explicit failures. PRF-026: No silent partial success.
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


SamplingConfiguration = WallSamplingConfiguration | CpuSamplingConfiguration


class SamplingStatistics(TypedDict):
    """Observed interval and profiler-pause statistics."""

    # PRF-003: Pause exclusion. PRF-025: Failure threshold.
    minimum_interval_ns: int | None
    mean_interval_ns: int | None
    maximum_interval_ns: int | None
    total_pause_ns: int


class SchedulerWakeEvent(TypedDict):
    """A non-weight-bearing kernel scheduler wake transition."""

    # PRF-052: Independent causal evidence.
    kind: Literal["waking", "wakeup-new"]
    host_monotonic_ns: int
    upstream_os_thread_id: int
    downstream_os_thread_id: int


class CausalitySummary(TypedDict):
    """Completeness of the independent causal event stream."""

    # PRF-052: Independent causal evidence. PRF-053: Causal diagnostics.
    backend: Literal["linux-perf-sched-waking"]
    status: Literal["recorded", "unavailable", "failed"]
    event_count: int
    lost_event_count: int
    reason: str | None


class HeaderRecord(TypedDict):
    """First record in every raw profile."""

    # PRF-027: Incremental persistence.
    record_type: Literal["header"]
    schema_version: int
    process_id: int
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
    frame_id: int
    frame: Frame


class ObservationRecord(TypedDict):
    """One incrementally persisted observation point."""

    # PRF-027: Incremental persistence.
    record_type: Literal["observation"]
    observation: Observation


class SchedulerWakeRecord(TypedDict):
    """One incrementally persisted scheduler wake transition."""

    # PRF-052: Independent causal evidence.
    record_type: Literal["scheduler-wake"]
    event: SchedulerWakeEvent


class CausalitySummaryRecord(TypedDict):
    """Final status of scheduler causal-event collection."""

    # PRF-053: Causal diagnostics.
    record_type: Literal["causality-summary"]
    causality: CausalitySummary


class FailureEventRecord(TypedDict):
    """One incrementally persisted capture-level failure."""

    # PRF-024: Explicit failures. PRF-027: Incremental persistence.
    record_type: Literal["failure"]
    failure: FailureRecord


class SummaryRecord(TypedDict):
    """Final record of a capture that shut down under profiler control."""

    # PRF-026: No silent partial success. PRF-027: Incremental persistence.
    record_type: Literal["summary"]
    exited_ns: int
    exited_target_running_ns: int
    compiler_exit_status: int
    diagnostics_status: Literal["none", "present"]
    interruption_signal: int | None


ProfileRecord = (
    HeaderRecord
    | RuntimeRecord
    | FrameRecord
    | ObservationRecord
    | SchedulerWakeRecord
    | CausalitySummaryRecord
    | FailureEventRecord
    | SummaryRecord
)


@dataclasses.dataclass(slots=True)
class RawProfile:
    """Loaded continuous wall or CPU profile artifact."""

    # PRF-010: Raw-data preservation. PRF-020: Machine and human interfaces.
    schema_version: int
    process_id: int
    command: list[str]
    working_directory: str
    workload_path: str
    workload_sha256: str
    sampling: SamplingConfiguration
    sampling_statistics: SamplingStatistics
    launcher_executable: ExecutableIdentity
    python_runtime: PythonRuntime | None
    lifecycle: Lifecycle
    frames: dict[int, Frame]
    observations: list[Observation]
    scheduler_wake_events: list[SchedulerWakeEvent]
    causality: CausalitySummary | None
    failures: list[FailureRecord]
    observation_counts: ObservationCounts
    compiler_exit_status: int | None
    diagnostics_status: Literal["none", "present", "unknown"]
    interruption_signal: int | None

    @property
    def complete(self) -> bool:
        """Whether capture ended under profiler control without interruption."""
        return (
            self.compiler_exit_status is not None and self.interruption_signal is None
        )

    @property
    def discarded_rate(self) -> float:
        """Fraction of attempted observations that were discarded."""
        attempted = (
            self.observation_counts["successful"] + self.observation_counts["discarded"]
        )
        return self.observation_counts["discarded"] / attempted if attempted else 0.0

    @property
    def success(self) -> bool:
        """Whether the captured artifact satisfies the profiler contract."""
        return (
            self.complete
            and any(
                observation["status"] == "successful"
                and any(thread["stack"] for thread in observation["threads"])
                for observation in self.observations
            )
            and self.discarded_rate <= MAX_DISCARDED_RATE
            and self.compiler_exit_status == 0
            and self.diagnostics_status == "none"
            and not self.failures
        )


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
        process_id=header["process_id"],
        command=header["command"],
        working_directory=header["working_directory"],
        workload_path=header["workload_path"],
        workload_sha256=header["workload_sha256"],
        sampling=header["sampling"],
        sampling_statistics={
            "minimum_interval_ns": None,
            "mean_interval_ns": None,
            "maximum_interval_ns": None,
            "total_pause_ns": 0,
        },
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
        scheduler_wake_events=[],
        causality=None,
        failures=[],
        observation_counts={
            "successful": 0,
            "discarded": 0,
            "missed": 0,
        },
        compiler_exit_status=None,
        diagnostics_status="unknown",
        interruption_signal=None,
    )


def _derive_observation_data(profile: RawProfile) -> None:
    counts: ObservationCounts = {
        "successful": 0,
        "discarded": 0,
        "missed": 0,
    }
    previous_observation_time: int | None = None
    interval_count = 0
    interval_total_ns = 0
    minimum_interval_ns: int | None = None
    maximum_interval_ns: int | None = None
    total_pause_ns = 0
    for observation in profile.observations:
        observation_time = observation["target_running_ns"]
        if previous_observation_time is not None:
            interval_ns = observation_time - previous_observation_time
            interval_count += 1
            interval_total_ns += interval_ns
            minimum_interval_ns = (
                interval_ns
                if minimum_interval_ns is None
                else min(minimum_interval_ns, interval_ns)
            )
            maximum_interval_ns = (
                interval_ns
                if maximum_interval_ns is None
                else max(maximum_interval_ns, interval_ns)
            )
        previous_observation_time = observation_time
        total_pause_ns += (
            observation["pause_ended_ns"] - observation["pause_started_ns"]
        )
        if observation["status"] == "successful":
            counts["successful"] += 1
        elif observation["status"] == "discarded":
            counts["discarded"] += 1
        else:
            counts["missed"] += 1

    profile.observation_counts = counts
    profile.sampling_statistics = {
        "minimum_interval_ns": minimum_interval_ns,
        "mean_interval_ns": (
            interval_total_ns // interval_count if interval_count else None
        ),
        "maximum_interval_ns": maximum_interval_ns,
        "total_pause_ns": total_pause_ns,
    }


def load(profile_path: pathlib.Path) -> RawProfile:
    """Load a complete or incrementally persisted profile."""
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
            frame_record = cast("FrameRecord", cast("object", record_data))
            profile.frames[frame_record["frame_id"]] = frame_record["frame"]
        elif record_type == "observation":
            observation = cast("ObservationRecord", cast("object", record_data))[
                "observation"
            ]
            if observation["status"] != "successful":
                observation["failure_kind"] = ObservationFailureKind(
                    observation["failure_kind"]
                )
            profile.observations.append(observation)
        elif record_type == "scheduler-wake":
            wake_record = cast("SchedulerWakeRecord", cast("object", record_data))
            profile.scheduler_wake_events.append(wake_record["event"])
        elif record_type == "causality-summary":
            causality_record = cast(
                "CausalitySummaryRecord", cast("object", record_data)
            )
            profile.causality = causality_record["causality"]
        elif record_type == "failure":
            failure = cast("FailureEventRecord", cast("object", record_data))["failure"]
            failure["kind"] = CaptureFailureKind(failure["kind"])
            profile.failures.append(failure)
        elif record_type == "summary":
            summary = cast("SummaryRecord", cast("object", record_data))
            profile.lifecycle["exited_ns"] = summary["exited_ns"]
            profile.lifecycle["exited_target_running_ns"] = summary[
                "exited_target_running_ns"
            ]
            profile.compiler_exit_status = summary["compiler_exit_status"]
            profile.diagnostics_status = summary["diagnostics_status"]
            profile.interruption_signal = summary["interruption_signal"]
            summary_seen = True
        else:
            raise ValueError(f"unknown profile record type: {record_type!r}")
    _derive_observation_data(profile)
    return profile
