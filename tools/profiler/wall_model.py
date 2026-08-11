"""Shared sampled-wall interval model."""

from __future__ import annotations

import dataclasses
import typing

if typing.TYPE_CHECKING:
    from tools.profiler import schema


@dataclasses.dataclass(frozen=True, slots=True)
class Interval:
    """A target-running interval bounded in nanoseconds."""

    # PRF-005: Lifecycle-bounded attribution.
    start_ns: int
    end_ns: int

    @property
    def duration_ns(self) -> int:
        """Nanoseconds spanned by the interval."""
        return self.end_ns - self.start_ns


@dataclasses.dataclass(frozen=True, slots=True)
class ThreadIdentity:
    """The identity of one lifetime of an operating-system thread ID."""

    # PRF-047: Multi-threaded critical path.
    os_thread_id: int
    start_time_ticks: int


@dataclasses.dataclass(frozen=True, slots=True)
class ThreadSample:
    """One thread's state and stack over a sampled wall interval."""

    # PRF-005: Lifecycle-bounded attribution.
    # PRF-047: Multi-threaded critical path.
    identity: ThreadIdentity
    observation_index: int
    interval: Interval
    pre_stop_state: str
    wait_channel: str
    voluntary_context_switches: int
    nonvoluntary_context_switches: int
    stack: tuple[int, ...]

    @property
    def is_handoff_waiting(self) -> bool:
        """Whether the sample can represent a synchronization wait."""
        # PRF-047: Multi-threaded critical path.
        # Only interruptible sleeps can be synchronization waits;
        # uninterruptible I/O remains on the same thread's critical chain.
        return self.pre_stop_state == "S" and bool(self.stack)


def observation_intervals(profile: schema.RawProfile) -> list[ThreadSample]:
    """Calculate lifecycle-bounded target-running intervals for wall samples."""
    # PRF-003: Pause exclusion. PRF-004: No stale-stack reuse.
    # PRF-005: Lifecycle-bounded attribution.
    observations = profile.observations
    if not observations:
        return []
    python_started_ns = profile.lifecycle["python_observed_target_running_ns"]
    if python_started_ns is None:
        return []
    process_exited_ns = profile.lifecycle["exited_target_running_ns"]
    samples: list[ThreadSample] = []
    for index, observation in enumerate(observations):
        if observation["status"] != "successful":
            continue
        observation_time = observation["target_running_ns"]
        if index == 0:
            left_ns = max(
                python_started_ns,
                observation_time - observation["scheduled_interval_ns"] // 2,
            )
        else:
            left_ns = (
                observations[index - 1]["target_running_ns"] + observation_time
            ) // 2
        if index + 1 == len(observations):
            right_ns = observation_time + observation["scheduled_interval_ns"] // 2
            if process_exited_ns is not None:
                right_ns = min(right_ns, process_exited_ns)
        else:
            right_ns = (
                observation_time + observations[index + 1]["target_running_ns"]
            ) // 2
        interval = Interval(left_ns, right_ns)
        for thread in observation["threads"]:
            samples.append(
                ThreadSample(
                    identity=ThreadIdentity(
                        os_thread_id=thread["os_thread_id"],
                        start_time_ticks=thread["start_time_ticks"],
                    ),
                    observation_index=index,
                    interval=interval,
                    pre_stop_state=thread["pre_stop_state"],
                    wait_channel=thread["wait_channel"],
                    voluntary_context_switches=thread["voluntary_context_switches"],
                    nonvoluntary_context_switches=thread[
                        "nonvoluntary_context_switches"
                    ],
                    stack=tuple(thread["stack"]),
                )
            )
    return samples
