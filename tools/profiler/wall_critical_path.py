"""Reconstruct conservative sampled wall critical paths."""

from __future__ import annotations

import dataclasses
import itertools
import typing

from tools.profiler import analyzer_model, schema, wall_model


@dataclasses.dataclass(frozen=True, slots=True)
class DependentWait:
    """A completion-dependent thread observed waiting during critical work."""

    # PRF-047: Multi-threaded critical path.
    identity: wall_model.ThreadIdentity
    stack: tuple[int, ...]


@dataclasses.dataclass(frozen=True, slots=True)
class ResolvedSegment:
    """A sampled critical-path interval attributed to a Python stack."""

    # PRF-047: Multi-threaded critical path.
    kind: typing.Literal["work", "wait"]
    interval: wall_model.Interval
    identity: wall_model.ThreadIdentity
    stack: tuple[int, ...]
    dependent_wait: DependentWait | None
    parallel_off_path_threads: tuple[wall_model.ThreadIdentity, ...]


@dataclasses.dataclass(frozen=True, slots=True)
class UncertainSegment:
    """A critical-path interval that sampling could not attribute."""

    # PRF-047: Multi-threaded critical path.
    interval: wall_model.Interval
    reason: str


CriticalPathSegment = ResolvedSegment | UncertainSegment


@dataclasses.dataclass(frozen=True, slots=True)
class ResolvedHandoff:
    """A sampled cross-thread transition with one producer candidate."""

    # PRF-047: Multi-threaded critical path.
    target_running_ns: int
    upstream: wall_model.ThreadIdentity
    downstream: wall_model.ThreadIdentity
    upstream_stack: tuple[int, ...]
    downstream_stack: tuple[int, ...]
    downstream_wait_ns: int


@dataclasses.dataclass(frozen=True, slots=True)
class UnresolvedHandoff:
    """A sampled cross-thread transition without one producer candidate."""

    # PRF-047: Multi-threaded critical path.
    target_running_ns: int
    resolution: typing.Literal["ambiguous", "unobserved"]
    downstream: wall_model.ThreadIdentity
    downstream_stack: tuple[int, ...]
    downstream_wait_ns: int
    candidates: tuple[wall_model.ThreadIdentity, ...]


CriticalPathHandoff = ResolvedHandoff | UnresolvedHandoff


@dataclasses.dataclass(frozen=True, slots=True)
class FunctionRow:
    """Self or cumulative function attribution along the critical path."""

    # PRF-047: Multi-threaded critical path.
    identity: analyzer_model.FunctionIdentity
    work_ns: int
    wait_ns: int


@dataclasses.dataclass(frozen=True, slots=True)
class Analysis:
    """Sampled wall critical-path analysis."""

    # PRF-047: Multi-threaded critical path.
    segments: list[CriticalPathSegment]
    handoffs: list[CriticalPathHandoff]
    self_function_rows: list[FunctionRow]
    cumulative_function_rows: list[FunctionRow]
    terminal_thread: wall_model.ThreadIdentity | None
    work_ns: int
    wait_ns: int
    uncertain_ns: int
    parallel_off_path_ns: int


@dataclasses.dataclass(frozen=True, slots=True)
class _Transition:
    # PRF-047: Multi-threaded critical path.
    target_running_ns: int
    earlier_observation_index: int
    downstream: wall_model.ThreadIdentity
    downstream_stack: tuple[int, ...]
    downstream_wait_ns: int
    candidates: tuple[wall_model.ThreadIdentity, ...]
    candidate_stacks: tuple[tuple[int, ...], ...]


@dataclasses.dataclass(frozen=True, slots=True)
class _Phase:
    # PRF-047: Multi-threaded critical path.
    interval: wall_model.Interval
    actor: wall_model.ThreadIdentity
    waiter: wall_model.ThreadIdentity | None


@dataclasses.dataclass(frozen=True, slots=True)
class _PathSkeleton:
    # PRF-047: Multi-threaded critical path.
    phases: list[_Phase]
    uncertain_segments: list[UncertainSegment]
    handoffs: list[CriticalPathHandoff]
    terminal_thread: wall_model.ThreadIdentity | None
    trailing_uncertainty: UncertainSegment | None


def _is_working(sample: wall_model.ThreadSample) -> bool:
    # PRF-047: Multi-threaded critical path.
    return sample.pre_stop_state == "R" and bool(sample.stack)


def _is_waiting(sample: wall_model.ThreadSample) -> bool:
    # PRF-047: Multi-threaded critical path.
    return sample.pre_stop_state != "R" and bool(sample.stack)


def _samples_by_observation(
    samples: list[wall_model.ThreadSample],
) -> dict[int, dict[wall_model.ThreadIdentity, wall_model.ThreadSample]]:
    # PRF-047: Multi-threaded critical path.
    by_observation: dict[
        int,
        dict[wall_model.ThreadIdentity, wall_model.ThreadSample],
    ] = {}
    for sample in samples:
        by_observation.setdefault(sample.observation_index, {})[sample.identity] = (
            sample
        )
    return by_observation


def _wait_start(
    downstream: wall_model.ThreadIdentity,
    earlier_observation_index: int,
    samples_by_observation: dict[
        int,
        dict[wall_model.ThreadIdentity, wall_model.ThreadSample],
    ],
    profile: schema.RawProfile,
) -> tuple[int, int]:
    # PRF-047: Multi-threaded critical path.
    wait_start_ns = profile.observations[earlier_observation_index]["target_running_ns"]
    observation_index = earlier_observation_index
    while observation_samples := samples_by_observation.get(observation_index):
        sample = observation_samples.get(downstream)
        if sample is None or not sample.is_handoff_waiting:
            break
        wait_start_ns = sample.interval.start_ns
        observation_index -= 1
    return observation_index + 1, wait_start_ns


def _departed_working_candidates(
    downstream: wall_model.ThreadIdentity,
    wait_start_index: int,
    earlier_index: int,
    later_samples: dict[wall_model.ThreadIdentity, wall_model.ThreadSample],
    samples_by_observation: dict[
        int,
        dict[wall_model.ThreadIdentity, wall_model.ThreadSample],
    ],
) -> list[wall_model.ThreadSample]:
    # PRF-047: Multi-threaded critical path.
    # A worker that ran during the downstream wait and disappeared before the
    # wake is observable completion evidence even when its exit fell between
    # two samples.
    latest_working: dict[wall_model.ThreadIdentity, wall_model.ThreadSample] = {}
    for observation_index in range(wait_start_index, earlier_index + 1):
        for identity, sample in samples_by_observation[observation_index].items():
            if (
                identity != downstream
                and identity not in later_samples
                and _is_working(sample)
            ):
                latest_working[identity] = sample
    return list(latest_working.values())


def _transitions(
    profile: schema.RawProfile,
    samples_by_observation: dict[
        int,
        dict[wall_model.ThreadIdentity, wall_model.ThreadSample],
    ],
) -> list[_Transition]:
    # PRF-047: Multi-threaded critical path.
    transitions: list[_Transition] = []
    successful_indices = sorted(samples_by_observation)
    for earlier_index, later_index in itertools.pairwise(successful_indices):
        earlier_observation = profile.observations[earlier_index]
        later_observation = profile.observations[later_index]
        earlier_samples = samples_by_observation[earlier_index]
        later_samples = samples_by_observation[later_index]
        stopped_working: list[wall_model.ThreadSample] = []
        for identity, earlier_sample in earlier_samples.items():
            if not _is_working(earlier_sample):
                continue
            later_sample = later_samples.get(identity)
            if later_sample is None or not _is_working(later_sample):
                stopped_working.append(earlier_sample)
        target_running_ns = (
            earlier_observation["target_running_ns"]
            + later_observation["target_running_ns"]
        ) // 2
        for downstream, later_sample in later_samples.items():
            if not _is_working(later_sample):
                continue
            earlier_sample = earlier_samples.get(downstream)
            if earlier_sample is not None and not earlier_sample.is_handoff_waiting:
                continue
            wait_start_index = earlier_index
            wait_start_ns = target_running_ns
            if earlier_sample is not None:
                wait_start_index, wait_start_ns = _wait_start(
                    downstream,
                    earlier_index,
                    samples_by_observation,
                    profile,
                )
            candidates = [
                candidate
                for candidate in stopped_working
                if candidate.identity != downstream
            ]
            if earlier_sample is not None and not candidates:
                candidates = _departed_working_candidates(
                    downstream,
                    wait_start_index,
                    earlier_index,
                    later_samples,
                    samples_by_observation,
                )
            if earlier_sample is not None and not candidates:
                # A producer can notify a waiter and continue running; the sole
                # working peer after the wake is then the only observed source.
                candidates = [
                    candidate
                    for identity, candidate in later_samples.items()
                    if identity != downstream and _is_working(candidate)
                ]
            if earlier_sample is None and not candidates:
                # A newly observed worker has one observable producer when
                # exactly one stack-bearing thread predates it.
                candidates = [
                    candidate
                    for candidate in earlier_samples.values()
                    if candidate.stack
                ]
            candidates.sort(
                key=lambda candidate: (
                    candidate.identity.os_thread_id,
                    candidate.identity.start_time_ticks,
                )
            )
            transitions.append(
                _Transition(
                    target_running_ns=target_running_ns,
                    earlier_observation_index=earlier_index,
                    downstream=downstream,
                    downstream_stack=(
                        earlier_sample.stack
                        if earlier_sample is not None
                        else later_sample.stack
                    ),
                    downstream_wait_ns=(
                        target_running_ns - wait_start_ns
                        if earlier_sample is not None
                        else 0
                    ),
                    candidates=tuple(candidate.identity for candidate in candidates),
                    candidate_stacks=tuple(candidate.stack for candidate in candidates),
                )
            )
    return transitions


def _terminal_sample(
    profile: schema.RawProfile,
    samples: list[wall_model.ThreadSample],
) -> wall_model.ThreadSample | None:
    # PRF-047: Multi-threaded critical path.
    # Linux process IDs identify the main thread in the target thread group.
    for sample in reversed(samples):
        observation = profile.observations[sample.observation_index]
        if sample.identity.os_thread_id == observation["process_id"] and sample.stack:
            return sample
    return None


def _latest_transition(
    transitions: list[_Transition],
    downstream: wall_model.ThreadIdentity,
    before_ns: int,
) -> _Transition | None:
    # PRF-047: Multi-threaded critical path.
    matching = [
        transition
        for transition in transitions
        if transition.downstream == downstream
        and transition.target_running_ns < before_ns
    ]
    return max(
        matching, key=lambda transition: transition.target_running_ns, default=None
    )


def _phases_and_handoffs(
    profile: schema.RawProfile,
    samples: list[wall_model.ThreadSample],
    transitions: list[_Transition],
) -> _PathSkeleton:
    # PRF-047: Multi-threaded critical path.
    terminal_sample = _terminal_sample(profile, samples)
    if terminal_sample is None:
        return _PathSkeleton([], [], [], None, None)
    python_started_ns = typing.cast(
        "int", profile.lifecycle["python_observed_target_running_ns"]
    )
    phases: list[_Phase] = []
    uncertain_segments: list[UncertainSegment] = []
    handoffs: list[CriticalPathHandoff] = []
    phase_end_ns = terminal_sample.interval.end_ns
    actor = terminal_sample.identity
    waiter: wall_model.ThreadIdentity | None = None
    while True:
        transition = _latest_transition(transitions, actor, phase_end_ns)
        if transition is None:
            phases.append(
                _Phase(
                    interval=wall_model.Interval(python_started_ns, phase_end_ns),
                    actor=actor,
                    waiter=waiter,
                )
            )
            break
        phases.append(
            _Phase(
                interval=wall_model.Interval(
                    transition.target_running_ns,
                    phase_end_ns,
                ),
                actor=actor,
                waiter=waiter,
            )
        )
        if len(transition.candidates) != 1:
            resolution = "unobserved" if not transition.candidates else "ambiguous"
            handoffs.append(
                UnresolvedHandoff(
                    target_running_ns=transition.target_running_ns,
                    resolution=resolution,
                    downstream=transition.downstream,
                    downstream_stack=transition.downstream_stack,
                    downstream_wait_ns=transition.downstream_wait_ns,
                    candidates=transition.candidates,
                )
            )
            if not transition.downstream_wait_ns:
                uncertain_segments.append(
                    _uncertain_segment(
                        python_started_ns,
                        transition.target_running_ns,
                        f"critical path before {resolution} handoff was not resolved",
                    )
                )
                break
            wait_start_ns = transition.target_running_ns - transition.downstream_wait_ns
            uncertain_segments.append(
                _uncertain_segment(
                    wait_start_ns,
                    transition.target_running_ns,
                    f"producer for {resolution} handoff was not resolved",
                )
            )
            phase_end_ns = wait_start_ns
            continue
        upstream = transition.candidates[0]
        handoffs.append(
            ResolvedHandoff(
                target_running_ns=transition.target_running_ns,
                upstream=upstream,
                downstream=transition.downstream,
                upstream_stack=transition.candidate_stacks[0],
                downstream_stack=transition.downstream_stack,
                downstream_wait_ns=transition.downstream_wait_ns,
            )
        )
        phase_end_ns = transition.target_running_ns
        waiter = actor
        actor = upstream
    phases.reverse()
    handoffs.reverse()
    process_exited_ns = profile.lifecycle["exited_target_running_ns"]
    trailing_uncertainty = (
        _uncertain_segment(
            terminal_sample.interval.end_ns,
            process_exited_ns,
            "process completion followed the last main-thread sample",
        )
        if process_exited_ns is not None
        and process_exited_ns > terminal_sample.interval.end_ns
        else None
    )
    return _PathSkeleton(
        phases,
        uncertain_segments,
        handoffs,
        terminal_sample.identity,
        trailing_uncertainty,
    )


def _uncertain_segment(start_ns: int, end_ns: int, reason: str) -> UncertainSegment:
    # PRF-047: Multi-threaded critical path.
    return UncertainSegment(
        interval=wall_model.Interval(start_ns, end_ns),
        reason=reason,
    )


def _resolved_segment(
    sample: wall_model.ThreadSample,
    interval: wall_model.Interval,
    phase: _Phase,
    samples_by_observation: dict[
        int,
        dict[wall_model.ThreadIdentity, wall_model.ThreadSample],
    ],
) -> ResolvedSegment:
    # PRF-047: Multi-threaded critical path.
    observation_samples = samples_by_observation[sample.observation_index]
    dependent_wait = None
    if phase.waiter is not None:
        waiter_sample = observation_samples.get(phase.waiter)
        if waiter_sample is not None and _is_waiting(waiter_sample):
            dependent_wait = DependentWait(
                identity=phase.waiter,
                stack=waiter_sample.stack,
            )
    excluded = {phase.actor}
    if phase.waiter is not None:
        excluded.add(phase.waiter)
    parallel_off_path_threads = tuple(
        sorted(
            (
                identity
                for identity, other_sample in observation_samples.items()
                if identity not in excluded and _is_working(other_sample)
            ),
            key=lambda identity: (
                identity.os_thread_id,
                identity.start_time_ticks,
            ),
        )
    )
    return ResolvedSegment(
        kind="work" if _is_working(sample) else "wait",
        interval=interval,
        identity=sample.identity,
        stack=sample.stack,
        dependent_wait=dependent_wait,
        parallel_off_path_threads=parallel_off_path_threads,
    )


def _phase_segments(
    phase: _Phase,
    samples_by_identity: dict[
        wall_model.ThreadIdentity,
        list[wall_model.ThreadSample],
    ],
    samples_by_observation: dict[
        int,
        dict[wall_model.ThreadIdentity, wall_model.ThreadSample],
    ],
) -> list[CriticalPathSegment]:
    # PRF-047: Multi-threaded critical path.
    segments: list[CriticalPathSegment] = []
    cursor_ns = phase.interval.start_ns
    for sample in samples_by_identity[phase.actor]:
        start_ns = max(cursor_ns, sample.interval.start_ns, phase.interval.start_ns)
        end_ns = min(sample.interval.end_ns, phase.interval.end_ns)
        if end_ns <= start_ns:
            continue
        if start_ns > cursor_ns:
            segments.append(
                _uncertain_segment(
                    cursor_ns,
                    start_ns,
                    "critical thread was not observed",
                )
            )
        interval = wall_model.Interval(start_ns, end_ns)
        if sample.stack:
            segments.append(
                _resolved_segment(
                    sample,
                    interval,
                    phase,
                    samples_by_observation,
                )
            )
        else:
            segments.append(
                _uncertain_segment(
                    start_ns,
                    end_ns,
                    "critical thread had no Python stack",
                )
            )
        cursor_ns = end_ns
        if cursor_ns == phase.interval.end_ns:
            return segments
    # A handoff can identify an actor whose first or final observation only
    # borders the inferred phase, leaving the phase without a sampled stack.
    segments.append(
        _uncertain_segment(
            cursor_ns,
            phase.interval.end_ns,
            "critical thread was not observed",
        )
    )
    return segments


def _merge_segments(segments: list[CriticalPathSegment]) -> list[CriticalPathSegment]:
    # PRF-047: Multi-threaded critical path.
    merged: list[CriticalPathSegment] = []
    for segment in segments:
        if not merged or merged[-1].interval.end_ns != segment.interval.start_ns:
            merged.append(segment)
            continue
        previous = merged[-1]
        interval = wall_model.Interval(
            previous.interval.start_ns,
            segment.interval.end_ns,
        )
        if (
            isinstance(previous, ResolvedSegment)
            and isinstance(segment, ResolvedSegment)
            and dataclasses.replace(previous, interval=segment.interval) == segment
        ) or (
            isinstance(previous, UncertainSegment)
            and isinstance(segment, UncertainSegment)
            and previous.reason == segment.reason
        ):
            merged[-1] = dataclasses.replace(previous, interval=interval)
        else:
            merged.append(segment)
    return merged


def _function_rows(
    segments: list[CriticalPathSegment],
    frames: dict[int, schema.Frame],
    filters: analyzer_model.AnalysisFilters,
    *,
    cumulative: bool,
) -> list[FunctionRow]:
    # PRF-047: Multi-threaded critical path.
    durations: dict[analyzer_model.FunctionIdentity, list[int]] = {}
    for segment in segments:
        if not isinstance(segment, ResolvedSegment):
            continue
        if (
            filters.thread_ids
            and segment.identity.os_thread_id not in filters.thread_ids
        ):
            continue
        frame_ids = set(segment.stack) if cumulative else {segment.stack[-1]}
        for frame_id in frame_ids:
            identity = analyzer_model.function_identity(frames[frame_id])
            if not analyzer_model.matches_function(identity, filters):
                continue
            duration = durations.setdefault(identity, [0, 0])
            duration[0 if segment.kind == "work" else 1] += segment.interval.duration_ns
    return sorted(
        (
            FunctionRow(identity=identity, work_ns=duration[0], wait_ns=duration[1])
            for identity, duration in durations.items()
        ),
        key=lambda row: (
            -(row.work_ns + row.wait_ns),
            row.identity.filename,
            row.identity.function,
        ),
    )


def analyze(
    profile: schema.RawProfile,
    filters: analyzer_model.AnalysisFilters,
) -> Analysis:
    """Recover the completion-critical sampled wall chain conservatively."""
    # PRF-047: Multi-threaded critical path.
    samples = wall_model.observation_intervals(profile)
    samples_by_observation = _samples_by_observation(samples)
    samples_by_identity: dict[
        wall_model.ThreadIdentity,
        list[wall_model.ThreadSample],
    ] = {}
    for sample in samples:
        samples_by_identity.setdefault(sample.identity, []).append(sample)
    skeleton = _phases_and_handoffs(
        profile,
        samples,
        _transitions(profile, samples_by_observation),
    )
    segments: list[CriticalPathSegment] = list(skeleton.uncertain_segments)
    for phase in skeleton.phases:
        segments.extend(
            _phase_segments(
                phase,
                samples_by_identity,
                samples_by_observation,
            )
        )
    if skeleton.trailing_uncertainty is not None:
        segments.append(skeleton.trailing_uncertainty)
    segments.sort(key=lambda segment: segment.interval.start_ns)
    segments = _merge_segments(segments)
    work_ns = sum(
        segment.interval.duration_ns
        for segment in segments
        if isinstance(segment, ResolvedSegment) and segment.kind == "work"
    )
    wait_ns = sum(
        segment.interval.duration_ns
        for segment in segments
        if isinstance(segment, ResolvedSegment) and segment.kind == "wait"
    )
    uncertain_ns = sum(
        segment.interval.duration_ns
        for segment in segments
        if isinstance(segment, UncertainSegment)
    )
    parallel_off_path_ns = sum(
        segment.interval.duration_ns
        for segment in segments
        if isinstance(segment, ResolvedSegment) and segment.parallel_off_path_threads
    )
    return Analysis(
        segments=segments,
        handoffs=skeleton.handoffs,
        self_function_rows=_function_rows(
            segments,
            profile.frames,
            filters,
            cumulative=False,
        ),
        cumulative_function_rows=_function_rows(
            segments,
            profile.frames,
            filters,
            cumulative=True,
        ),
        terminal_thread=skeleton.terminal_thread,
        work_ns=work_ns,
        wait_ns=wait_ns,
        uncertain_ns=uncertain_ns,
        parallel_off_path_ns=parallel_off_path_ns,
    )


def _duration(duration_ns: int) -> str:
    # PRF-020: Machine and human interfaces.
    return f"{duration_ns / 1_000_000_000:.6f} s"


def _identity_text(identity: wall_model.ThreadIdentity) -> str:
    # PRF-047: Multi-threaded critical path.
    return f"Thread {identity.os_thread_id}"


def _stack_text(stack: tuple[int, ...], frames: dict[int, schema.Frame]) -> str:
    # PRF-047: Multi-threaded critical path.
    return " -> ".join(
        f"{frames[frame_id]['function']} ("
        + analyzer_model.display_stack_filename(frames[frame_id]["filename"])
        + ":"
        + f"{frames[frame_id]['line']})"
        for frame_id in stack
    )


def _emit_segment(
    segment: CriticalPathSegment,
    frames: dict[int, schema.Frame],
) -> None:
    # PRF-020: Machine and human interfaces.
    # PRF-047: Multi-threaded critical path.
    if isinstance(segment, UncertainSegment):
        print(
            f"  {_duration(segment.interval.duration_ns)} uncertain: " + segment.reason
        )
        return
    off_path = ""
    if segment.parallel_off_path_threads:
        off_path = "; parallel off-path " + ", ".join(
            _identity_text(identity) for identity in segment.parallel_off_path_threads
        )
    print(
        f"  {_duration(segment.interval.duration_ns)} {segment.kind}; "
        + f"{_identity_text(segment.identity)}; "
        + _stack_text(segment.stack, frames)
        + off_path
    )
    if segment.dependent_wait is not None:
        print(
            "    dependent wait: "
            + f"{_identity_text(segment.dependent_wait.identity)}; "
            + _stack_text(segment.dependent_wait.stack, frames)
        )


def _emit_handoff(
    handoff: CriticalPathHandoff,
    frames: dict[int, schema.Frame],
) -> None:
    # PRF-020: Machine and human interfaces.
    # PRF-047: Multi-threaded critical path.
    if isinstance(handoff, ResolvedHandoff):
        downstream_status = (
            "downstream waited " + _duration(handoff.downstream_wait_ns)
            if handoff.downstream_wait_ns
            else "downstream first observed working"
        )
        print(
            f"  {_identity_text(handoff.upstream)} -> "
            + f"{_identity_text(handoff.downstream)}; {downstream_status}"
        )
        print("    producer: " + _stack_text(handoff.upstream_stack, frames))
        downstream_label = "waiter" if handoff.downstream_wait_ns else "receiver"
        print(
            f"    {downstream_label}: " + _stack_text(handoff.downstream_stack, frames)
        )
        return
    candidates = (
        ", ".join(_identity_text(candidate) for candidate in handoff.candidates)
        if handoff.candidates
        else "none observed"
    )
    downstream_status = (
        " after waiting " + _duration(handoff.downstream_wait_ns)
        if handoff.downstream_wait_ns
        else ""
    )
    print(
        f"  {handoff.resolution}: wake of {_identity_text(handoff.downstream)}"
        + downstream_status
        + f"; candidate producers: {candidates}"
    )
    print("    receiver: " + _stack_text(handoff.downstream_stack, frames))


def emit_report(
    profile: schema.RawProfile,
    analysis: Analysis,
    limit: int,
) -> None:
    """Print the ordered sampled wall critical path and its attribution."""
    # PRF-020: Machine and human interfaces.
    # PRF-047: Multi-threaded critical path.
    print("\nSampled wall critical path:")
    if analysis.terminal_thread is None:
        print("  unavailable: no main-thread Python stack was observed")
        return
    print(
        f"  terminal {_identity_text(analysis.terminal_thread)}; "
        + f"work {_duration(analysis.work_ns)}; wait {_duration(analysis.wait_ns)}; "
        + f"uncertain {_duration(analysis.uncertain_ns)}; parallel off-path overlap "
        + _duration(analysis.parallel_off_path_ns)
    )
    significant_segments = sorted(
        sorted(
            analysis.segments,
            key=lambda segment: -segment.interval.duration_ns,
        )[:limit],
        key=lambda segment: segment.interval.start_ns,
    )
    for segment in significant_segments:
        _emit_segment(segment, profile.frames)
    if len(analysis.segments) > limit:
        print(f"  ... {len(analysis.segments) - limit} shorter segments")

    print("\nCritical-path cross-thread handoffs:")
    if not analysis.handoffs:
        print("  none resolved or observed")
    for handoff in analysis.handoffs[:limit]:
        _emit_handoff(handoff, profile.frames)

    print("\nCritical-path self attribution:")
    for row in analysis.self_function_rows[:limit]:
        print(
            f"  work {_duration(row.work_ns)}; wait {_duration(row.wait_ns)}; "
            + f"{analyzer_model.display_filename(row.identity.filename)} "
            + f"({row.identity.function})"
        )
    print("\nCritical-path cumulative attribution:")
    for row in analysis.cumulative_function_rows[:limit]:
        print(
            f"  work {_duration(row.work_ns)}; wait {_duration(row.wait_ns)}; "
            + f"{analyzer_model.display_filename(row.identity.filename)} "
            + f"({row.identity.function})"
        )
