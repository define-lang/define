"""Shared integration-test support for the compiler profiler."""

import collections
import dataclasses
import os
import select
import sys
import time
from pathlib import Path

from python.runfiles import runfiles  # pyright: ignore[reportMissingTypeStubs]

from tools.profiler import schema


@dataclasses.dataclass(slots=True)
class ProfilerEventReader:
    """Read explicit profiler coordination events."""

    # PRF-041: Realistic tests. PRF-049: Event-driven coordination.
    file_descriptor: int
    buffered_events: collections.deque[str] = dataclasses.field(
        default_factory=collections.deque
    )
    incomplete_event: bytes = b""

    def wait_for(
        self,
        expected_event: str,
        count: int = 1,
        *,
        timeout_seconds: float = 5,
    ) -> bool:
        """Wait for an event count before the deadline."""
        deadline = time.monotonic() + timeout_seconds
        events_seen = 0
        while time.monotonic() < deadline:
            while self.buffered_events:
                event = self.buffered_events.popleft()
                if event == expected_event:
                    events_seen += 1
                    if events_seen == count:
                        return True
            readable, _, _ = select.select(
                [self.file_descriptor],
                [],
                [],
                deadline - time.monotonic(),
            )
            if not readable:
                return False
            event_bytes = os.read(self.file_descriptor, 4096)
            if not event_bytes:
                return False
            event_bytes = self.incomplete_event + event_bytes
            *complete_lines, self.incomplete_event = event_bytes.split(b"\n")
            self.buffered_events.extend(line.decode() for line in complete_lines)
        return False


def runfile(variable: str) -> Path:
    """Resolve a declared test runfile."""
    candidate = Path(os.environ[variable])
    if candidate.exists():
        return candidate
    runfiles_resolver = runfiles.Runfiles.Create()
    assert runfiles_resolver is not None
    resolved = runfiles_resolver.Rlocation(os.environ[variable])
    assert resolved is not None
    return Path(resolved)


def target_command(
    source_variable: str,
    target_arguments: tuple[str, ...] = (),
) -> tuple[str, ...]:
    """Build a launched target command."""
    source = runfile(source_variable)
    return (
        "/bin/sh",
        "-c",
        'exec "$@"',
        "profiler-test-launcher",
        sys.executable,
        str(source),
        *target_arguments,
    )


def gated_target_command(
    source_variable: str,
    launcher_gate: Path,
    target_arguments: tuple[str, ...] = (),
) -> tuple[str, ...]:
    """Build a target command held before its launcher executes Python."""
    # PRF-022: Launcher safety. PRF-049: Event-driven coordination.
    command = target_command(source_variable, target_arguments)
    return (
        "/bin/sh",
        "-c",
        'read -r _ < "$1"; shift; exec "$@"',
        "profiler-test-gated-launcher",
        str(launcher_gate),
        *command,
    )


def profile_command(
    profile_path: Path,
    source_variable: str,
    *,
    mode: schema.CaptureMode = "wall",
    mean_interval_seconds: float = 0.0001,
    event_file_descriptor: int | None = None,
    launcher_gate: Path | None = None,
    target_arguments: tuple[str, ...] = (),
) -> list[str]:
    """Build a public profiler command."""
    # PRF-002: Independent sampling schedule. PRF-020: Machine and human interfaces.
    source = runfile(source_variable)
    command = [
        str(runfile("PROFILER_BINARY")),
        "--mode",
        mode,
        "--profile",
        str(profile_path),
        "--workload",
        str(source),
        "--mean-interval-seconds",
        str(mean_interval_seconds),
    ]
    if event_file_descriptor is not None:
        command.extend(["--event-fd", str(event_file_descriptor)])
    target = (
        gated_target_command(source_variable, launcher_gate, target_arguments)
        if launcher_gate is not None
        else target_command(source_variable, target_arguments)
    )
    command.extend(["--", *target])
    return command


def assert_capture_summary(
    output: str,
    profile_path: Path,
    *,
    completeness: str = "complete",
    status: str = "successful",
):
    """Assert the complete public capture summary."""
    # PRF-020: Machine and human interfaces.
    assert output.startswith(
        f"Profile: {profile_path}\nCapture: {completeness}; {status};"
    )
    assert "\nObservations:" in output
    assert "discarded rate" in output


def assert_recorded_observations(
    observations: list[schema.Observation],
) -> tuple[list[schema.SuccessfulObservation], int]:
    """Assert and partition retained observation records."""
    successful: list[schema.SuccessfulObservation] = []
    discarded = 0
    for observation in observations:
        if observation["status"] == "successful":
            successful.append(observation)
        else:
            assert observation["status"] == "discarded"
            assert isinstance(
                observation["failure_kind"],
                schema.ObservationFailureKind,
            )
            assert observation["failure_reason"]
            exception_name, separator, _ = observation["failure_reason"].partition(": ")
            assert exception_name
            assert separator
            discarded += 1
    return successful, discarded


def assert_observations_through_exit(
    profile: schema.RawProfile,
) -> tuple[list[schema.SuccessfulObservation], int, int]:
    """Assert observations ending at the target lifecycle boundary."""
    observations = profile.observations
    if observations[-1]["status"] == "missed":
        successful, discarded = assert_recorded_observations(observations[:-1])
        return successful, discarded, 1
    successful, discarded = assert_recorded_observations(observations)
    return successful, discarded, 0
