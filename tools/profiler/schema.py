"""Raw data structures for the Define compiler profiler."""

from __future__ import annotations

import json
import typing
from typing import Literal, TypedDict, cast

if typing.TYPE_CHECKING:
    import pathlib

# PRF-010: Raw-data preservation. PRF-020: Machine and human interfaces.
SCHEMA_VERSION = 1


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
    """One Python frame in caller-to-leaf order."""

    # PRF-015: Full stacks. PRF-016: Source identity.
    filename: str
    function: str
    line: int


class ThreadSnapshot(TypedDict):
    """One stopped Python thread and its complete available stack."""

    # PRF-006: Complete-process stop. PRF-013: Wall mode.
    os_thread_id: int
    stopped_state: str
    stack: list[Frame]


class Snapshot(TypedDict):
    """One all-thread observation and its profiler pause timing."""

    # PRF-003: Pause exclusion.
    host_monotonic_ns: int
    target_running_ns: int
    pause_started_ns: int
    pause_ended_ns: int
    pause_duration_ns: int
    process_id: int
    threads: list[ThreadSnapshot]


class FailureRecord(TypedDict):
    """An explicit capture failure encountered during the real workflow."""

    # PRF-024: Explicit failures.
    host_monotonic_ns: int
    kind: str
    reason: str


class Lifecycle(TypedDict):
    """Observed target process lifecycle timestamps."""

    # PRF-011: Complete invocation.
    launched_ns: int
    python_observed_ns: int | None
    exited_ns: int


class ObservationCounts(TypedDict):
    """Counts of attempted and retained stack observations."""

    # PRF-024: Explicit failures. PRF-026: No silent partial success.
    attempted: int
    successful: int
    discarded: int
    missed: int


class SamplingConfiguration(TypedDict):
    """Configuration for the one-snapshot sampling schedule."""

    # PRF-002: Independent sampling schedule.
    mode: Literal["wall"]
    schedule: Literal["one-snapshot"]
    snapshot_delay_seconds: float
    attachment_timeout_seconds: float


class RawProfile(TypedDict):
    """Version 1 one-snapshot profile artifact."""

    # PRF-010: Raw-data preservation. PRF-020: Machine and human interfaces.
    schema_version: int
    complete: bool
    success: bool
    command: list[str]
    working_directory: str
    workload_path: str
    workload_sha256: str
    sampling: SamplingConfiguration
    launcher_executable: ExecutableIdentity
    python_runtime: PythonRuntime | None
    lifecycle: Lifecycle
    snapshot: Snapshot | None
    failures: list[FailureRecord]
    observation_counts: ObservationCounts
    compiler_exit_status: int
    diagnostics_status: Literal["none", "present"]
    interruption_signal: int | None


def load(profile_path: pathlib.Path) -> RawProfile:
    """Load a version 1 raw profile."""
    # PRF-039: Current design only.
    with profile_path.open(encoding="utf-8") as profile_file:
        profile = cast("RawProfile", json.load(profile_file))
    if profile["schema_version"] != SCHEMA_VERSION:
        raise ValueError(
            f"unsupported profiler schema version: {profile['schema_version']}"
        )
    return profile
