"""Shared sampled-wall interval model."""

from __future__ import annotations

import dataclasses
import typing

if typing.TYPE_CHECKING:
    import collections.abc

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


@dataclasses.dataclass(slots=True)
class ObservationSample:
    """One successful observation and all of its sampled threads."""

    observation_index: int
    interval: Interval
    threads: dict[ThreadIdentity, ThreadSample] = dataclasses.field(
        default_factory=dict,
        compare=False,
    )


@dataclasses.dataclass(slots=True)
class ThreadSample:
    """One thread's state and stack over a sampled wall interval."""

    # PRF-005: Lifecycle-bounded attribution.
    # PRF-047: Multi-threaded critical path.
    observation: ObservationSample
    identity: ThreadIdentity
    pre_stop_state: str
    stack: tuple[int, ...]

    @property
    def observation_index(self) -> int:
        """Index of the raw observation containing this thread sample."""
        return self.observation.observation_index

    @property
    def interval(self) -> Interval:
        """Wall interval represented by this thread sample."""
        return self.observation.interval

    @property
    def is_handoff_waiting(self) -> bool:
        """Whether the sample can represent a synchronization wait."""
        # PRF-047: Multi-threaded critical path.
        # Only interruptible sleeps can be synchronization waits;
        # uninterruptible I/O remains on the same thread's critical chain.
        return self.pre_stop_state == "S" and bool(self.stack)


@dataclasses.dataclass(slots=True)
class Samples:
    """Canonical wall samples indexed for the analyzers' access patterns."""

    observations: list[ObservationSample]
    by_identity: dict[ThreadIdentity, list[ThreadSample]]

    def __iter__(self) -> collections.abc.Iterator[ThreadSample]:
        """Iterate over every sampled thread in observation order."""
        for observation in self.observations:
            yield from observation.threads.values()


def observation_intervals(profile: schema.RawProfile) -> Samples:
    """Calculate and index lifecycle-bounded target-running wall samples."""
    # PRF-003: Pause exclusion. PRF-004: No stale-stack reuse.
    # PRF-005: Lifecycle-bounded attribution.
    observations = profile.observations
    sampled_observations: list[ObservationSample] = []
    by_identity: dict[ThreadIdentity, list[ThreadSample]] = {}
    if not observations:
        return Samples(sampled_observations, by_identity)
    python_started_ns = profile.lifecycle["python_observed_target_running_ns"]
    if python_started_ns is None:
        return Samples(sampled_observations, by_identity)
    process_exited_ns = profile.lifecycle["exited_target_running_ns"]
    identities: dict[tuple[int, int], ThreadIdentity] = {}
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
        observation_sample = ObservationSample(index, interval)
        sampled_observations.append(observation_sample)
        for thread in observation["threads"]:
            identity_key = (thread["os_thread_id"], thread["start_time_ticks"])
            identity = identities.get(identity_key)
            if identity is None:
                identity = ThreadIdentity(*identity_key)
                identities[identity_key] = identity
            sample = ThreadSample(
                observation=observation_sample,
                identity=identity,
                pre_stop_state=thread["pre_stop_state"],
                stack=tuple(thread["stack"]),
            )
            observation_sample.threads[identity] = sample
            by_identity.setdefault(identity, []).append(sample)
    return Samples(sampled_observations, by_identity)
