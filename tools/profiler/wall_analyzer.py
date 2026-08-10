"""Analyze continuous wall observations from the Define compiler profiler."""

from __future__ import annotations

import dataclasses
import itertools

from tools.profiler import analyzer_model, schema


@dataclasses.dataclass(frozen=True, slots=True)
class _Interval:
    start_ns: int
    end_ns: int

    @property
    def duration_ns(self) -> int:
        return self.end_ns - self.start_ns


@dataclasses.dataclass(frozen=True, slots=True)
class _WeightedStack:
    thread_id: int
    interval: _Interval
    stack: tuple[int, ...]


@dataclasses.dataclass(frozen=True, slots=True)
class FrameRow:
    """Wall attribution for one source-identified Python frame."""

    frame: schema.Frame
    wall_occupancy_ns: int
    thread_time_ns: int
    longest_span_ns: int
    sample_hits: int


@dataclasses.dataclass(frozen=True, slots=True)
class FunctionRow:
    """Wall attribution aggregated across sampled lines of one function."""

    identity: analyzer_model.FunctionIdentity
    wall_occupancy_ns: int
    thread_time_ns: int
    longest_span_ns: int
    sample_hits: int


@dataclasses.dataclass(frozen=True, slots=True)
class StackPathRow:
    """Wall attribution for one complete caller-to-leaf function path."""

    stack_path: tuple[analyzer_model.FunctionIdentity, ...]
    wall_occupancy_ns: int
    thread_time_ns: int
    longest_span_ns: int
    sample_hits: int


@dataclasses.dataclass(frozen=True, slots=True)
class RelationshipRow:
    """Sampled caller-to-callee relationship."""

    caller: analyzer_model.FunctionIdentity
    callee: analyzer_model.FunctionIdentity
    wall_occupancy_ns: int
    thread_time_ns: int
    sample_hits: int


@dataclasses.dataclass(frozen=True, slots=True)
class ThreadRow:
    """Sampled occupancy for one OS thread."""

    os_thread_id: int
    occupancy_ns: int
    attributed_occupancy_ns: int
    sample_hits: int


@dataclasses.dataclass(frozen=True, slots=True)
class Analysis:
    """Derived wall attribution from raw independent observations."""

    # PRF-010: Raw-data preservation. PRF-018: Focused analysis.
    self_rows: list[FrameRow]
    cumulative_rows: list[FrameRow]
    self_function_rows: list[FunctionRow]
    cumulative_function_rows: list[FunctionRow]
    stack_path_rows: list[StackPathRow]
    relationship_rows: list[RelationshipRow]
    thread_rows: list[ThreadRow]
    wall_window_ns: int
    attributed_wall_ns: int
    unattributed_wall_ns: int


def _observation_intervals(profile: schema.RawProfile) -> list[_WeightedStack]:
    # PRF-003: Pause exclusion. PRF-004: No stale-stack reuse.
    # PRF-005: Lifecycle-bounded attribution.
    observations = profile.observations
    if not observations:
        return []
    python_started_ns = profile.lifecycle["python_observed_target_running_ns"]
    if python_started_ns is None:
        return []
    process_exited_ns = profile.lifecycle["exited_target_running_ns"]
    weighted_stacks: list[_WeightedStack] = []
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
        interval = _Interval(left_ns, right_ns)
        for thread in observation["threads"]:
            weighted_stacks.append(
                _WeightedStack(
                    thread_id=thread["os_thread_id"],
                    interval=interval,
                    stack=tuple(thread["stack"]),
                )
            )
    return weighted_stacks


def _merge_intervals(intervals: list[_Interval]) -> list[_Interval]:
    if not intervals:
        return []
    ordered = sorted(intervals, key=lambda interval: interval.start_ns)
    merged: list[_Interval] = [ordered[0]]
    for interval in ordered[1:]:
        previous = merged[-1]
        if interval.start_ns <= previous.end_ns:
            merged[-1] = _Interval(
                previous.start_ns,
                max(previous.end_ns, interval.end_ns),
            )
        else:
            merged.append(interval)
    return merged


def _union_duration(intervals: list[_Interval]) -> int:
    # PRF-019: Concurrency semantics.
    return sum(interval.duration_ns for interval in _merge_intervals(intervals))


def _longest_thread_span(entries: list[tuple[int, _Interval]]) -> int:
    intervals_by_thread: dict[int, list[_Interval]] = {}
    for thread_id, interval in entries:
        intervals_by_thread.setdefault(thread_id, []).append(interval)
    return max(
        (
            interval.duration_ns
            for intervals in intervals_by_thread.values()
            for interval in _merge_intervals(intervals)
        ),
        default=0,
    )


def _frame_rows(
    entries_by_frame: dict[int, list[tuple[int, _Interval]]],
    hits_by_frame: dict[int, int],
    frames: dict[int, schema.Frame],
    filters: analyzer_model.AnalysisFilters,
) -> list[FrameRow]:
    rows: list[FrameRow] = []
    for frame_id, entries in entries_by_frame.items():
        frame = frames[frame_id]
        if not analyzer_model.matches_frame(frame, filters):
            continue
        intervals = [interval for _, interval in entries]
        rows.append(
            FrameRow(
                frame=frame,
                wall_occupancy_ns=_union_duration(intervals),
                thread_time_ns=sum(interval.duration_ns for interval in intervals),
                longest_span_ns=_longest_thread_span(entries),
                sample_hits=hits_by_frame[frame_id],
            )
        )
    return sorted(
        rows,
        key=lambda row: (
            -row.wall_occupancy_ns,
            row.frame["filename"],
            row.frame["line"],
            row.frame["function"],
        ),
    )


def _function_rows(
    entries_by_function: dict[
        analyzer_model.FunctionIdentity,
        list[tuple[int, _Interval]],
    ],
    hits_by_function: dict[analyzer_model.FunctionIdentity, int],
    filters: analyzer_model.AnalysisFilters,
) -> list[FunctionRow]:
    rows: list[FunctionRow] = []
    for identity, entries in entries_by_function.items():
        if not analyzer_model.matches_function(identity, filters):
            continue
        intervals = [interval for _, interval in entries]
        rows.append(
            FunctionRow(
                identity=identity,
                wall_occupancy_ns=_union_duration(intervals),
                thread_time_ns=sum(interval.duration_ns for interval in intervals),
                longest_span_ns=_longest_thread_span(entries),
                sample_hits=hits_by_function[identity],
            )
        )
    return sorted(
        rows,
        key=lambda row: (
            -row.wall_occupancy_ns,
            row.identity.filename,
            row.identity.function,
        ),
    )


def _stack_path_rows(
    entries_by_path: dict[
        tuple[analyzer_model.FunctionIdentity, ...],
        list[tuple[int, _Interval]],
    ],
    hits_by_path: dict[tuple[analyzer_model.FunctionIdentity, ...], int],
    filters: analyzer_model.AnalysisFilters,
) -> list[StackPathRow]:
    # PRF-015: Full stacks.
    rows: list[StackPathRow] = []
    for stack_path, entries in entries_by_path.items():
        if not any(
            analyzer_model.matches_function(identity, filters)
            for identity in stack_path
        ):
            continue
        intervals = [interval for _, interval in entries]
        rows.append(
            StackPathRow(
                stack_path=stack_path,
                wall_occupancy_ns=_union_duration(intervals),
                thread_time_ns=sum(interval.duration_ns for interval in intervals),
                longest_span_ns=_longest_thread_span(entries),
                sample_hits=hits_by_path[stack_path],
            )
        )
    return sorted(
        rows,
        key=lambda row: (
            -row.longest_span_ns,
            tuple(
                (identity.filename, identity.function) for identity in row.stack_path
            ),
        ),
    )


def analyze(
    profile: schema.RawProfile,
    filters: analyzer_model.AnalysisFilters = analyzer_model.DEFAULT_FILTERS,
) -> Analysis:
    """Derive wall self, cumulative, relationship, and thread attribution."""
    # PRF-018: Focused analysis. PRF-019: Concurrency semantics.
    weighted_stacks = [
        weighted_stack
        for weighted_stack in _observation_intervals(profile)
        if not filters.thread_ids or weighted_stack.thread_id in filters.thread_ids
    ]
    frames = profile.frames
    self_entries: dict[int, list[tuple[int, _Interval]]] = {}
    cumulative_entries: dict[int, list[tuple[int, _Interval]]] = {}
    self_function_entries: dict[
        analyzer_model.FunctionIdentity,
        list[tuple[int, _Interval]],
    ] = {}
    cumulative_function_entries: dict[
        analyzer_model.FunctionIdentity,
        list[tuple[int, _Interval]],
    ] = {}
    stack_path_entries: dict[
        tuple[analyzer_model.FunctionIdentity, ...],
        list[tuple[int, _Interval]],
    ] = {}
    relationship_entries: dict[
        tuple[analyzer_model.FunctionIdentity, analyzer_model.FunctionIdentity],
        list[tuple[int, _Interval]],
    ] = {}
    self_hits: dict[int, int] = {}
    cumulative_hits: dict[int, int] = {}
    self_function_hits: dict[analyzer_model.FunctionIdentity, int] = {}
    cumulative_function_hits: dict[analyzer_model.FunctionIdentity, int] = {}
    stack_path_hits: dict[tuple[analyzer_model.FunctionIdentity, ...], int] = {}
    relationship_hits: dict[
        tuple[analyzer_model.FunctionIdentity, analyzer_model.FunctionIdentity], int
    ] = {}
    thread_intervals: dict[int, list[_Interval]] = {}
    attributed_thread_intervals: dict[int, list[_Interval]] = {}
    thread_hits: dict[int, int] = {}
    for weighted_stack in weighted_stacks:
        thread_intervals.setdefault(weighted_stack.thread_id, []).append(
            weighted_stack.interval
        )
        thread_hits[weighted_stack.thread_id] = (
            thread_hits.get(weighted_stack.thread_id, 0) + 1
        )
        if not weighted_stack.stack:
            continue
        attributed_thread_intervals.setdefault(weighted_stack.thread_id, []).append(
            weighted_stack.interval
        )
        leaf = weighted_stack.stack[-1]
        self_entries.setdefault(leaf, []).append(
            (weighted_stack.thread_id, weighted_stack.interval)
        )
        self_hits[leaf] = self_hits.get(leaf, 0) + 1
        leaf_function = analyzer_model.function_identity(frames[leaf])
        self_function_entries.setdefault(leaf_function, []).append(
            (weighted_stack.thread_id, weighted_stack.interval)
        )
        self_function_hits[leaf_function] = self_function_hits.get(leaf_function, 0) + 1
        for frame_id in set(weighted_stack.stack):
            cumulative_entries.setdefault(frame_id, []).append(
                (weighted_stack.thread_id, weighted_stack.interval)
            )
            cumulative_hits[frame_id] = cumulative_hits.get(frame_id, 0) + 1
        function_identities = {
            analyzer_model.function_identity(frames[frame_id])
            for frame_id in weighted_stack.stack
        }
        for identity in function_identities:
            cumulative_function_entries.setdefault(identity, []).append(
                (weighted_stack.thread_id, weighted_stack.interval)
            )
            cumulative_function_hits[identity] = (
                cumulative_function_hits.get(identity, 0) + 1
            )
        stack_path = tuple(
            analyzer_model.function_identity(frames[frame_id])
            for frame_id in weighted_stack.stack
        )
        stack_path_entries.setdefault(stack_path, []).append(
            (weighted_stack.thread_id, weighted_stack.interval)
        )
        stack_path_hits[stack_path] = stack_path_hits.get(stack_path, 0) + 1
        for relationship in set(itertools.pairwise(stack_path)):
            relationship_entries.setdefault(relationship, []).append(
                (weighted_stack.thread_id, weighted_stack.interval)
            )
            relationship_hits[relationship] = relationship_hits.get(relationship, 0) + 1

    relationship_rows: list[RelationshipRow] = []
    for relationship, entries in relationship_entries.items():
        caller, callee = relationship
        if filters.caller is not None and filters.caller not in caller.function:
            continue
        if filters.callee is not None and filters.callee not in callee.function:
            continue
        if not analyzer_model.matches_function(
            caller, filters
        ) and not analyzer_model.matches_function(
            callee,
            filters,
        ):
            continue
        intervals = [interval for _, interval in entries]
        relationship_rows.append(
            RelationshipRow(
                caller=caller,
                callee=callee,
                wall_occupancy_ns=_union_duration(intervals),
                thread_time_ns=sum(interval.duration_ns for interval in intervals),
                sample_hits=relationship_hits[relationship],
            )
        )
    relationship_rows.sort(
        key=lambda row: (
            -row.wall_occupancy_ns,
            row.caller.function,
            row.callee.function,
        )
    )

    thread_rows = sorted(
        (
            ThreadRow(
                os_thread_id=thread_id,
                occupancy_ns=_union_duration(intervals),
                attributed_occupancy_ns=_union_duration(
                    attributed_thread_intervals.get(thread_id, [])
                ),
                sample_hits=thread_hits[thread_id],
            )
            for thread_id, intervals in thread_intervals.items()
        ),
        key=lambda row: (-row.occupancy_ns, row.os_thread_id),
    )
    python_started_ns = profile.lifecycle["python_observed_target_running_ns"]
    process_exited_ns = profile.lifecycle["exited_target_running_ns"]
    wall_window_ns = (
        process_exited_ns - python_started_ns
        if python_started_ns is not None and process_exited_ns is not None
        else 0
    )
    attributed_wall_ns = _union_duration(
        [
            weighted_stack.interval
            for weighted_stack in weighted_stacks
            if weighted_stack.stack
        ]
    )
    return Analysis(
        self_rows=_frame_rows(self_entries, self_hits, frames, filters),
        cumulative_rows=_frame_rows(
            cumulative_entries,
            cumulative_hits,
            frames,
            filters,
        ),
        self_function_rows=_function_rows(
            self_function_entries,
            self_function_hits,
            filters,
        ),
        cumulative_function_rows=_function_rows(
            cumulative_function_entries,
            cumulative_function_hits,
            filters,
        ),
        stack_path_rows=_stack_path_rows(
            stack_path_entries,
            stack_path_hits,
            filters,
        ),
        relationship_rows=relationship_rows,
        thread_rows=thread_rows,
        wall_window_ns=wall_window_ns,
        attributed_wall_ns=attributed_wall_ns,
        unattributed_wall_ns=max(0, wall_window_ns - attributed_wall_ns),
    )


def _duration(duration_ns: int) -> str:
    return f"{duration_ns / 1_000_000_000:.6f} s"


def _frame_text(frame: schema.Frame) -> str:
    # PRF-016: Source identity.
    return f"{frame['filename']}:{frame['line']} ({frame['function']})"


def _function_text(identity: analyzer_model.FunctionIdentity) -> str:
    return f"{identity.filename} ({identity.function})"


def emit_report(profile: schema.RawProfile, analysis: Analysis, limit: int) -> None:
    """Print stable continuous-wall attribution tables and diagnostics."""
    # PRF-020: Machine and human interfaces. PRF-043: Analyzer at every checkpoint.
    status = "successful" if profile.success else "unsuccessful"
    completeness = "complete" if profile.complete else "incomplete"
    print(f"Profile schema: {profile.schema_version}; {completeness}; {status}")
    print(f"Command: {' '.join(profile.command)}")
    print(f"Working directory: {profile.working_directory}")
    print(f"Workload: {profile.workload_path} " + f"(sha256 {profile.workload_sha256})")
    runtime = profile.python_runtime
    if runtime is None:
        print("Python runtime: not observed")
    else:
        threading_mode = "free-threaded" if runtime["free_threaded"] else "GIL-enabled"
        print(
            f"Python runtime: {runtime['version']} {threading_mode}; "
            + runtime["executable"]["path"]
        )
    counts = profile.observation_counts
    print(
        "Observations: "
        + f"{counts['successful']} successful, {counts['discarded']} discarded, "
        + f"{counts['missed']} missed, {counts['attempted']} attempted"
    )
    statistics = profile.sampling_statistics
    if statistics is not None:
        minimum_interval = statistics["minimum_interval_ns"]
        mean_interval = statistics["mean_interval_ns"]
        maximum_interval = statistics["maximum_interval_ns"]
        print(
            f"Sampling: {profile.sampling['schedule']}; "
            + (
                "observed interval min/mean/max "
                + f"{_duration(minimum_interval)}/"
                + f"{_duration(mean_interval)}/"
                + f"{_duration(maximum_interval)}; "
                if minimum_interval is not None
                and mean_interval is not None
                and maximum_interval is not None
                else "no observed intervals; "
            )
            + f"discarded rate {statistics['discarded_rate']:.3%}; "
            + f"profiler pause {_duration(statistics['total_pause_ns'])}"
        )
    print(f"Threads observed: {len(analysis.thread_rows)}")
    print(
        f"Wall window: {_duration(analysis.wall_window_ns)}; "
        + f"attributed {_duration(analysis.attributed_wall_ns)}; "
        + f"unattributed {_duration(analysis.unattributed_wall_ns)}"
    )
    print(
        f"Compiler exit status: {profile.compiler_exit_status}; "
        + f"diagnostics: {profile.diagnostics_status}"
    )
    print(
        "Resolution: sample hits are observations, not calls; failed observations "
        + "and lifecycle boundaries remain unattributed gaps."
    )

    print("\nSelf wall occupancy (union across threads):")
    for row in analysis.self_function_rows[:limit]:
        print(
            f"  {_duration(row.wall_occupancy_ns)} wall; "
            + f"{_duration(row.thread_time_ns)} thread; "
            + f"span {_duration(row.longest_span_ns)}; "
            + f"{row.sample_hits} hits; {_function_text(row.identity)}"
        )
    print("\nCumulative wall occupancy (union across threads):")
    for row in analysis.cumulative_function_rows[:limit]:
        print(
            f"  {_duration(row.wall_occupancy_ns)} wall; "
            + f"{_duration(row.thread_time_ns)} thread; "
            + f"span {_duration(row.longest_span_ns)}; "
            + f"{row.sample_hits} hits; {_function_text(row.identity)}"
        )
    print("\nLongest sampled stack paths:")
    for row in analysis.stack_path_rows[:limit]:
        path = " -> ".join(_function_text(identity) for identity in row.stack_path)
        print(
            f"  span {_duration(row.longest_span_ns)}; "
            + f"{_duration(row.wall_occupancy_ns)} wall; "
            + f"{row.sample_hits} hits; {path}"
        )
    print("\nLongest sampled source-identified frames:")
    frame_span_rows = sorted(
        analysis.cumulative_rows,
        key=lambda row: (
            -row.longest_span_ns,
            row.frame["filename"],
            row.frame["line"],
            row.frame["function"],
        ),
    )
    for row in frame_span_rows[:limit]:
        print(
            f"  span {_duration(row.longest_span_ns)}; "
            + f"{_duration(row.wall_occupancy_ns)} wall; "
            + f"{row.sample_hits} hits; {_frame_text(row.frame)}"
        )
    print("\nSampled caller -> callee relationships:")
    for row in analysis.relationship_rows[:limit]:
        print(
            f"  {_duration(row.wall_occupancy_ns)} wall; "
            + f"{row.sample_hits} hits; {_function_text(row.caller)}"
            + f" -> {_function_text(row.callee)}"
        )
    print("\nPer-thread sampled occupancy:")
    for row in analysis.thread_rows:
        print(
            f"  Thread {row.os_thread_id}: {_duration(row.occupancy_ns)}; "
            + f"attributed {_duration(row.attributed_occupancy_ns)}; "
            + "unattributed "
            + f"{_duration(row.occupancy_ns - row.attributed_occupancy_ns)}; "
            + f"{row.sample_hits} hits"
        )
    if profile.failures:
        print(f"\nCapture failures ({len(profile.failures)}):")
        for failure in profile.failures:
            print(f"  {failure['kind']}: {failure['reason']}")
    failed_observations = [
        observation
        for observation in profile.observations
        if observation["status"] != "successful"
    ]
    if failed_observations:
        print(f"\nFailed observations ({len(failed_observations)}):")
        for observation in failed_observations:
            print(
                f"  {observation['observation_index']}: "
                + f"{observation['failure_kind']}: {observation['failure_reason']}"
            )
