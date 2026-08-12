"""Analyze continuous wall observations from the Define compiler profiler."""

from __future__ import annotations

import collections
import dataclasses
import itertools
import typing

from tools.profiler import analyzer_model, schema, wall_critical_path, wall_model


@dataclasses.dataclass(frozen=True, slots=True)
class FrameRow:
    """Wall attribution for one source-identified Python frame."""

    frame: schema.Frame
    wall_occupancy_ns: int
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
    longest_span_ns: int
    sample_hits: int


@dataclasses.dataclass(frozen=True, slots=True)
class RelationshipRow:
    """Sampled caller-to-callee relationship."""

    caller: analyzer_model.FunctionIdentity
    callee: analyzer_model.FunctionIdentity
    wall_occupancy_ns: int
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
    cumulative_rows: list[FrameRow]
    self_function_rows: list[FunctionRow]
    cumulative_function_rows: list[FunctionRow]
    stack_path_rows: list[StackPathRow]
    relationship_rows: list[RelationshipRow]
    thread_rows: list[ThreadRow]
    critical_path: wall_critical_path.Analysis
    wall_window_ns: int
    attributed_wall_ns: int

    @property
    def unattributed_wall_ns(self) -> int:
        """Wall time not covered by a stack-bearing sample."""
        return max(0, self.wall_window_ns - self.attributed_wall_ns)


@dataclasses.dataclass(slots=True)
class _SpanMetrics:
    wall_occupancy_ns: int = 0
    sample_hits: int = 0
    longest_span_ns: int = 0
    _wall_end_ns: int | None = None
    _thread_spans: dict[int, tuple[int, int]] = dataclasses.field(default_factory=dict)

    def add(self, thread_id: int, interval: wall_model.Interval) -> None:
        self.sample_hits += 1
        added_ns, self._wall_end_ns = _wall_union_update(self._wall_end_ns, interval)
        self.wall_occupancy_ns += added_ns

        previous = self._thread_spans.get(thread_id)
        if previous is None or interval.start_ns > previous[0]:
            span_ns = interval.duration_ns
        else:
            span_ns = previous[1] + max(0, interval.end_ns - previous[0])
        self._thread_spans[thread_id] = (
            max(interval.end_ns, previous[0])
            if previous is not None
            else interval.end_ns,
            span_ns,
        )
        self.longest_span_ns = max(self.longest_span_ns, span_ns)


@dataclasses.dataclass(slots=True)
class _IntervalMetrics(_SpanMetrics):
    thread_time_ns: int = 0

    @typing.override
    def add(self, thread_id: int, interval: wall_model.Interval) -> None:
        super().add(thread_id, interval)
        self.thread_time_ns += interval.duration_ns


@dataclasses.dataclass(slots=True)
class _OccupancyMetrics:
    wall_occupancy_ns: int = 0
    sample_hits: int = 0
    _wall_end_ns: int | None = None

    def add(self, interval: wall_model.Interval) -> None:
        self.sample_hits += 1
        added_ns, self._wall_end_ns = _wall_union_update(self._wall_end_ns, interval)
        self.wall_occupancy_ns += added_ns


@dataclasses.dataclass(slots=True)
class _ThreadMetrics:
    occupancy: _OccupancyMetrics = dataclasses.field(default_factory=_OccupancyMetrics)
    attributed: _OccupancyMetrics = dataclasses.field(default_factory=_OccupancyMetrics)


def _wall_union_update(
    prior_end_ns: int | None,
    interval: wall_model.Interval,
) -> tuple[int, int]:
    if prior_end_ns is None or interval.start_ns > prior_end_ns:
        return interval.duration_ns, interval.end_ns
    return max(0, interval.end_ns - prior_end_ns), max(prior_end_ns, interval.end_ns)


def _frame_rows(
    metrics_by_frame: dict[int, _SpanMetrics],
    frames: dict[int, schema.Frame],
    filters: analyzer_model.AnalysisFilters,
) -> list[FrameRow]:
    rows: list[FrameRow] = []
    for frame_id, metrics in metrics_by_frame.items():
        frame = frames[frame_id]
        if not analyzer_model.matches_frame(frame, filters):
            continue
        rows.append(
            FrameRow(
                frame=frame,
                wall_occupancy_ns=metrics.wall_occupancy_ns,
                longest_span_ns=metrics.longest_span_ns,
                sample_hits=metrics.sample_hits,
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
    metrics_by_function: dict[analyzer_model.FunctionIdentity, _IntervalMetrics],
    filters: analyzer_model.AnalysisFilters,
) -> list[FunctionRow]:
    rows: list[FunctionRow] = []
    for identity, metrics in metrics_by_function.items():
        if not analyzer_model.matches_function(identity, filters):
            continue
        rows.append(
            FunctionRow(
                identity=identity,
                wall_occupancy_ns=metrics.wall_occupancy_ns,
                thread_time_ns=metrics.thread_time_ns,
                longest_span_ns=metrics.longest_span_ns,
                sample_hits=metrics.sample_hits,
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
    metrics_by_path: dict[tuple[analyzer_model.FunctionIdentity, ...], _SpanMetrics],
    filters: analyzer_model.AnalysisFilters,
) -> list[StackPathRow]:
    # PRF-015: Full stacks.
    rows: list[StackPathRow] = []
    for stack_path, metrics in metrics_by_path.items():
        if not any(
            analyzer_model.matches_function(identity, filters)
            for identity in stack_path
        ):
            continue
        rows.append(
            StackPathRow(
                stack_path=stack_path,
                wall_occupancy_ns=metrics.wall_occupancy_ns,
                longest_span_ns=metrics.longest_span_ns,
                sample_hits=metrics.sample_hits,
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
    samples = wall_model.observation_intervals(profile)
    frames = profile.frames
    functions = {
        frame_id: analyzer_model.function_identity(frame)
        for frame_id, frame in frames.items()
    }
    cumulative_metrics: dict[int, _SpanMetrics] = collections.defaultdict(_SpanMetrics)
    self_function_metrics: dict[analyzer_model.FunctionIdentity, _IntervalMetrics] = (
        collections.defaultdict(_IntervalMetrics)
    )
    cumulative_function_metrics: dict[
        analyzer_model.FunctionIdentity, _IntervalMetrics
    ] = collections.defaultdict(_IntervalMetrics)
    stack_path_metrics: dict[
        tuple[analyzer_model.FunctionIdentity, ...], _SpanMetrics
    ] = collections.defaultdict(_SpanMetrics)
    relationship_metrics: dict[
        tuple[analyzer_model.FunctionIdentity, analyzer_model.FunctionIdentity],
        _OccupancyMetrics,
    ] = collections.defaultdict(_OccupancyMetrics)
    thread_metrics: dict[int, _ThreadMetrics] = {}
    attributed_metrics = _OccupancyMetrics()
    for sample in samples:
        thread_id = sample.identity.os_thread_id
        if filters.thread_ids and thread_id not in filters.thread_ids:
            continue
        metrics = thread_metrics.get(thread_id)
        if metrics is None:
            metrics = _ThreadMetrics()
            thread_metrics[thread_id] = metrics
        metrics.occupancy.add(sample.interval)
        if not sample.stack:
            continue
        metrics.attributed.add(sample.interval)
        attributed_metrics.add(sample.interval)
        leaf = sample.stack[-1]
        leaf_function = functions[leaf]
        self_function_metrics[leaf_function].add(thread_id, sample.interval)
        for frame_id in set(sample.stack):
            cumulative_metrics[frame_id].add(thread_id, sample.interval)
        stack_path = tuple(functions[frame_id] for frame_id in sample.stack)
        for identity in set(stack_path):
            cumulative_function_metrics[identity].add(thread_id, sample.interval)
        stack_path_metrics[stack_path].add(thread_id, sample.interval)
        for relationship in set(itertools.pairwise(stack_path)):
            relationship_metrics[relationship].add(sample.interval)

    relationship_rows: list[RelationshipRow] = []
    for relationship, metrics in relationship_metrics.items():
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
        relationship_rows.append(
            RelationshipRow(
                caller=caller,
                callee=callee,
                wall_occupancy_ns=metrics.wall_occupancy_ns,
                sample_hits=metrics.sample_hits,
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
                occupancy_ns=metrics.occupancy.wall_occupancy_ns,
                attributed_occupancy_ns=metrics.attributed.wall_occupancy_ns,
                sample_hits=metrics.occupancy.sample_hits,
            )
            for thread_id, metrics in thread_metrics.items()
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
    attributed_wall_ns = attributed_metrics.wall_occupancy_ns
    return Analysis(
        cumulative_rows=_frame_rows(
            cumulative_metrics,
            frames,
            filters,
        ),
        self_function_rows=_function_rows(
            self_function_metrics,
            filters,
        ),
        cumulative_function_rows=_function_rows(
            cumulative_function_metrics,
            filters,
        ),
        stack_path_rows=_stack_path_rows(
            stack_path_metrics,
            filters,
        ),
        relationship_rows=relationship_rows,
        thread_rows=thread_rows,
        critical_path=wall_critical_path.analyze(
            profile,
            filters,
            samples,
            functions,
        ),
        wall_window_ns=wall_window_ns,
        attributed_wall_ns=attributed_wall_ns,
    )


def _duration(duration_ns: int) -> str:
    return f"{duration_ns / 1_000_000_000:.6f} s"


def _frame_text(frame: schema.Frame) -> str:
    # PRF-016: Source identity.
    return (
        f"{analyzer_model.display_filename(frame['filename'])}:{frame['line']} "
        + f"({frame['function']})"
    )


def _function_text(identity: analyzer_model.FunctionIdentity) -> str:
    return f"{analyzer_model.display_filename(identity.filename)} ({identity.function})"


def _stack_function_text(identity: analyzer_model.FunctionIdentity) -> str:
    return (
        f"{analyzer_model.display_stack_filename(identity.filename)} "
        + f"({identity.function})"
    )


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
    attempted = counts["successful"] + counts["discarded"]
    print(
        "Observations: "
        + f"{counts['successful']} successful, {counts['discarded']} discarded, "
        + f"{counts['missed']} missed, {attempted} attempted"
    )
    statistics = profile.sampling_statistics
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
        + f"discarded rate {profile.discarded_rate:.3%}; "
        + f"profiler pause {_duration(statistics['total_pause_ns'])}"
    )
    causality = profile.causality
    if causality is None:
        print("Causality: sampled-transition inference; no scheduler event stream")
    elif causality["status"] == "recorded":
        print(
            "Causality: linux-perf-sched-waking; "
            + f"{causality['event_count']} wake events; "
            + f"{causality['lost_event_count']} lost"
        )
    else:
        print(
            "Causality: sampled-transition inference; scheduler events "
            + f"{causality['status']}: {causality['reason']}"
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

    wall_critical_path.emit_report(profile, analysis.critical_path, limit)

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
        path = " -> ".join(
            _stack_function_text(identity) for identity in row.stack_path
        )
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
        (index, observation)
        for index, observation in enumerate(profile.observations)
        if observation["status"] != "successful"
    ]
    if failed_observations:
        print(f"\nUnretained observations ({len(failed_observations)}):")
        for index, observation in failed_observations:
            print(
                f"  {index} {observation['status']}: "
                + f"{observation['failure_kind']}: {observation['failure_reason']}"
            )
