"""Analyze scheduler-runtime endpoints from CPU profiler observations."""

from __future__ import annotations

import dataclasses
import itertools
import math
from typing import cast

from tools.profiler import analyzer_model, schema


@dataclasses.dataclass(frozen=True, slots=True)
class FrameRow:
    """CPU attribution for one source-identified Python frame."""

    # PRF-014: CPU mode. PRF-016: Source identity.
    frame: schema.Frame
    cpu_time_ns: int
    confidence_95_ns: int
    endpoint_hits: int


@dataclasses.dataclass(frozen=True, slots=True)
class FunctionRow:
    """CPU attribution aggregated across sampled lines of one function."""

    # PRF-014: CPU mode.
    identity: analyzer_model.FunctionIdentity
    cpu_time_ns: int
    confidence_95_ns: int
    endpoint_hits: int


@dataclasses.dataclass(frozen=True, slots=True)
class RelationshipRow:
    """CPU attribution for one sampled caller-to-callee relationship."""

    # PRF-014: CPU mode.
    caller: analyzer_model.FunctionIdentity
    callee: analyzer_model.FunctionIdentity
    cpu_time_ns: int
    confidence_95_ns: int
    endpoint_hits: int


@dataclasses.dataclass(frozen=True, slots=True)
class ThreadRow:
    """Observed and Python-attributed CPU runtime for one OS thread."""

    # PRF-014: CPU mode. PRF-019: Concurrency semantics.
    os_thread_id: int
    observed_cpu_ns: int
    attributed_cpu_ns: int
    interval_count: int


@dataclasses.dataclass(frozen=True, slots=True)
class Analysis:
    """Derived CPU attribution from external scheduler-runtime endpoints."""

    # PRF-010: Raw-data preservation. PRF-014: CPU mode.
    # PRF-018: Focused analysis. PRF-019: Concurrency semantics.
    self_rows: list[FrameRow]
    cumulative_rows: list[FrameRow]
    self_function_rows: list[FunctionRow]
    cumulative_function_rows: list[FunctionRow]
    relationship_rows: list[RelationshipRow]
    thread_rows: list[ThreadRow]
    wall_window_ns: int
    observed_cpu_ns: int
    attributed_cpu_ns: int
    unattributed_cpu_ns: int
    unresolved_transitions: int
    effective_endpoint_count: float


@dataclasses.dataclass(frozen=True, slots=True)
class _WeightedStack:
    # PRF-010: Raw-data preservation. PRF-014: CPU mode.
    thread_id: int
    weight_ns: int
    endpoint_hits: int
    stack: tuple[int, ...]


@dataclasses.dataclass(frozen=True, slots=True)
class _ThreadInterval:
    observed_cpu_ns: int
    attributed_cpu_ns: int


def _threads_by_identity(
    observation: schema.SuccessfulObservation,
) -> dict[tuple[int, int], schema.CpuThreadObservation]:
    # PRF-005: Lifecycle-bounded attribution. PRF-014: CPU mode.
    threads: dict[tuple[int, int], schema.CpuThreadObservation] = {}
    for sampled_thread in observation["threads"]:
        thread = cast("schema.CpuThreadObservation", sampled_thread)
        threads[(thread["os_thread_id"], thread["start_time_ticks"])] = thread
    return threads


def _endpoint_weights(
    thread_id: int,
    cpu_delta_ns: int,
    earlier_stack: tuple[int, ...],
    later_stack: tuple[int, ...],
) -> list[_WeightedStack]:
    # PRF-010: Raw-data preservation. PRF-014: CPU mode.
    # Averaging independent endpoints avoids systematically favoring either side.
    earlier_weight_ns = cpu_delta_ns // 2
    return [
        _WeightedStack(
            thread_id=thread_id,
            weight_ns=earlier_weight_ns,
            endpoint_hits=1,
            stack=earlier_stack,
        ),
        _WeightedStack(
            thread_id=thread_id,
            weight_ns=cpu_delta_ns - earlier_weight_ns,
            endpoint_hits=1,
            stack=later_stack,
        ),
    ]


def _weighted_stacks(
    profile: schema.RawProfile,
    filters: analyzer_model.AnalysisFilters,
) -> tuple[list[_WeightedStack], dict[int, list[_ThreadInterval]], int]:
    # PRF-004: No stale-stack reuse. PRF-005: Lifecycle-bounded attribution.
    # PRF-010: Raw-data preservation. PRF-014: CPU mode.
    weighted_stacks: list[_WeightedStack] = []
    thread_intervals: dict[int, list[_ThreadInterval]] = {}
    unresolved_transitions = 0
    for earlier, later in itertools.pairwise(profile.observations):
        if earlier["status"] != "successful" or later["status"] != "successful":
            unresolved_transitions += 1
            continue
        earlier_threads = _threads_by_identity(earlier)
        later_threads = _threads_by_identity(later)
        unresolved_transitions += len(earlier_threads.keys() ^ later_threads.keys())
        for identity in earlier_threads.keys() & later_threads.keys():
            thread_id = identity[0]
            if filters.thread_ids and thread_id not in filters.thread_ids:
                continue
            earlier_thread = earlier_threads[identity]
            later_thread = later_threads[identity]
            cpu_delta_ns = (
                later_thread["scheduler_runtime_ns"]
                - earlier_thread["scheduler_runtime_ns"]
            )
            if not earlier_thread["stack"] or not later_thread["stack"]:
                interval = _ThreadInterval(
                    observed_cpu_ns=cpu_delta_ns,
                    attributed_cpu_ns=0,
                )
                thread_intervals.setdefault(thread_id, []).append(interval)
                continue
            interval = _ThreadInterval(
                observed_cpu_ns=cpu_delta_ns,
                attributed_cpu_ns=cpu_delta_ns,
            )
            thread_intervals.setdefault(thread_id, []).append(interval)
            weighted_stacks.extend(
                _endpoint_weights(
                    thread_id,
                    cpu_delta_ns,
                    tuple(earlier_thread["stack"]),
                    tuple(later_thread["stack"]),
                )
            )
    return weighted_stacks, thread_intervals, unresolved_transitions


def _add_weight[Identity](
    weights: dict[Identity, int],
    hits: dict[Identity, int],
    identity: Identity,
    weighted_stack: _WeightedStack,
):
    # PRF-014: CPU mode.
    weights[identity] = weights.get(identity, 0) + weighted_stack.weight_ns
    hits[identity] = hits.get(identity, 0) + weighted_stack.endpoint_hits


def _confidence_95_ns(
    cpu_time_ns: int,
    attributed_cpu_ns: int,
    effective_endpoint_count: float,
) -> int:
    # PRF-029: Call-frequency fixture. PRF-036: Rate convergence.
    proportion = cpu_time_ns / attributed_cpu_ns
    standard_error = attributed_cpu_ns * math.sqrt(
        proportion * (1 - proportion) / effective_endpoint_count
    )
    return round(1.96 * standard_error)


def _frame_rows(
    weights_by_frame: dict[int, int],
    hits_by_frame: dict[int, int],
    frames: dict[int, schema.Frame],
    filters: analyzer_model.AnalysisFilters,
    attributed_cpu_ns: int,
    effective_endpoint_count: float,
) -> list[FrameRow]:
    # PRF-014: CPU mode. PRF-018: Focused analysis.
    rows: list[FrameRow] = []
    for frame_id, cpu_time_ns in weights_by_frame.items():
        frame = frames[frame_id]
        if not analyzer_model.matches_frame(frame, filters):
            continue
        rows.append(
            FrameRow(
                frame=frame,
                cpu_time_ns=cpu_time_ns,
                confidence_95_ns=_confidence_95_ns(
                    cpu_time_ns,
                    attributed_cpu_ns,
                    effective_endpoint_count,
                ),
                endpoint_hits=hits_by_frame[frame_id],
            )
        )
    return sorted(
        rows,
        key=lambda row: (
            -row.cpu_time_ns,
            row.frame["filename"],
            row.frame["line"],
            row.frame["function"],
        ),
    )


def _function_rows(
    weights_by_function: dict[analyzer_model.FunctionIdentity, int],
    hits_by_function: dict[analyzer_model.FunctionIdentity, int],
    filters: analyzer_model.AnalysisFilters,
    attributed_cpu_ns: int,
    effective_endpoint_count: float,
) -> list[FunctionRow]:
    # PRF-014: CPU mode. PRF-018: Focused analysis.
    rows: list[FunctionRow] = []
    for identity, cpu_time_ns in weights_by_function.items():
        if not analyzer_model.matches_function(identity, filters):
            continue
        rows.append(
            FunctionRow(
                identity=identity,
                cpu_time_ns=cpu_time_ns,
                confidence_95_ns=_confidence_95_ns(
                    cpu_time_ns,
                    attributed_cpu_ns,
                    effective_endpoint_count,
                ),
                endpoint_hits=hits_by_function[identity],
            )
        )
    return sorted(
        rows,
        key=lambda row: (
            -row.cpu_time_ns,
            row.identity.filename,
            row.identity.function,
        ),
    )


def _relationship_rows(
    weights: dict[
        tuple[analyzer_model.FunctionIdentity, analyzer_model.FunctionIdentity], int
    ],
    hits: dict[
        tuple[analyzer_model.FunctionIdentity, analyzer_model.FunctionIdentity], int
    ],
    filters: analyzer_model.AnalysisFilters,
    attributed_cpu_ns: int,
    effective_endpoint_count: float,
) -> list[RelationshipRow]:
    # PRF-014: CPU mode. PRF-018: Focused analysis.
    rows: list[RelationshipRow] = []
    for relationship, cpu_time_ns in weights.items():
        caller, callee = relationship
        if filters.caller is not None and filters.caller not in caller.function:
            continue
        if filters.callee is not None and filters.callee not in callee.function:
            continue
        if not analyzer_model.matches_function(
            caller, filters
        ) and not analyzer_model.matches_function(callee, filters):
            continue
        rows.append(
            RelationshipRow(
                caller=caller,
                callee=callee,
                cpu_time_ns=cpu_time_ns,
                confidence_95_ns=_confidence_95_ns(
                    cpu_time_ns,
                    attributed_cpu_ns,
                    effective_endpoint_count,
                ),
                endpoint_hits=hits[relationship],
            )
        )
    return sorted(
        rows,
        key=lambda row: (
            -row.cpu_time_ns,
            row.caller.function,
            row.callee.function,
        ),
    )


def analyze(
    profile: schema.RawProfile,
    filters: analyzer_model.AnalysisFilters = analyzer_model.DEFAULT_FILTERS,
) -> Analysis:
    """Derive CPU self, cumulative, relationship, and thread attribution."""
    # PRF-014: CPU mode. PRF-018: Focused analysis.
    # PRF-019: Concurrency semantics.
    weighted_stacks, thread_intervals, unresolved_transitions = _weighted_stacks(
        profile, filters
    )
    frames = profile.frames
    self_weights: dict[int, int] = {}
    self_hits: dict[int, int] = {}
    cumulative_weights: dict[int, int] = {}
    cumulative_hits: dict[int, int] = {}
    self_function_weights: dict[analyzer_model.FunctionIdentity, int] = {}
    self_function_hits: dict[analyzer_model.FunctionIdentity, int] = {}
    cumulative_function_weights: dict[analyzer_model.FunctionIdentity, int] = {}
    cumulative_function_hits: dict[analyzer_model.FunctionIdentity, int] = {}
    relationship_weights: dict[
        tuple[analyzer_model.FunctionIdentity, analyzer_model.FunctionIdentity], int
    ] = {}
    relationship_hits: dict[
        tuple[analyzer_model.FunctionIdentity, analyzer_model.FunctionIdentity], int
    ] = {}
    for weighted_stack in weighted_stacks:
        leaf = weighted_stack.stack[-1]
        _add_weight(self_weights, self_hits, leaf, weighted_stack)
        leaf_function = analyzer_model.function_identity(frames[leaf])
        _add_weight(
            self_function_weights,
            self_function_hits,
            leaf_function,
            weighted_stack,
        )
        for frame_id in set(weighted_stack.stack):
            _add_weight(
                cumulative_weights,
                cumulative_hits,
                frame_id,
                weighted_stack,
            )
        stack_path = tuple(
            analyzer_model.function_identity(frames[frame_id])
            for frame_id in weighted_stack.stack
        )
        for identity in set(stack_path):
            _add_weight(
                cumulative_function_weights,
                cumulative_function_hits,
                identity,
                weighted_stack,
            )
        for relationship in set(itertools.pairwise(stack_path)):
            _add_weight(
                relationship_weights,
                relationship_hits,
                relationship,
                weighted_stack,
            )

    thread_rows: list[ThreadRow] = []
    for thread_id, intervals in thread_intervals.items():
        thread_rows.append(
            ThreadRow(
                os_thread_id=thread_id,
                observed_cpu_ns=sum(interval.observed_cpu_ns for interval in intervals),
                attributed_cpu_ns=sum(
                    interval.attributed_cpu_ns for interval in intervals
                ),
                interval_count=len(intervals),
            )
        )
    thread_rows.sort(key=lambda row: (-row.observed_cpu_ns, row.os_thread_id))
    observed_cpu_ns = sum(row.observed_cpu_ns for row in thread_rows)
    attributed_cpu_ns = sum(row.attributed_cpu_ns for row in thread_rows)
    squared_endpoint_weights = sum(
        weighted_stack.weight_ns**2 for weighted_stack in weighted_stacks
    )
    effective_endpoint_count = (
        attributed_cpu_ns**2 / squared_endpoint_weights
        if squared_endpoint_weights
        else 0.0
    )
    python_started_ns = profile.lifecycle["python_observed_target_running_ns"]
    process_exited_ns = profile.lifecycle["exited_target_running_ns"]
    wall_window_ns = (
        process_exited_ns - python_started_ns
        if python_started_ns is not None and process_exited_ns is not None
        else 0
    )
    return Analysis(
        self_rows=_frame_rows(
            self_weights,
            self_hits,
            frames,
            filters,
            attributed_cpu_ns,
            effective_endpoint_count,
        ),
        cumulative_rows=_frame_rows(
            cumulative_weights,
            cumulative_hits,
            frames,
            filters,
            attributed_cpu_ns,
            effective_endpoint_count,
        ),
        self_function_rows=_function_rows(
            self_function_weights,
            self_function_hits,
            filters,
            attributed_cpu_ns,
            effective_endpoint_count,
        ),
        cumulative_function_rows=_function_rows(
            cumulative_function_weights,
            cumulative_function_hits,
            filters,
            attributed_cpu_ns,
            effective_endpoint_count,
        ),
        relationship_rows=_relationship_rows(
            relationship_weights,
            relationship_hits,
            filters,
            attributed_cpu_ns,
            effective_endpoint_count,
        ),
        thread_rows=thread_rows,
        wall_window_ns=wall_window_ns,
        observed_cpu_ns=observed_cpu_ns,
        attributed_cpu_ns=attributed_cpu_ns,
        unattributed_cpu_ns=observed_cpu_ns - attributed_cpu_ns,
        unresolved_transitions=unresolved_transitions,
        effective_endpoint_count=effective_endpoint_count,
    )


def _duration(duration_ns: int) -> str:
    return f"{duration_ns / 1_000_000_000:.6f} s"


def _function_text(identity: analyzer_model.FunctionIdentity) -> str:
    return f"{analyzer_model.display_filename(identity.filename)} ({identity.function})"


def emit_report(profile: schema.RawProfile, analysis: Analysis, limit: int):
    """Print stable scheduler-runtime CPU attribution and diagnostics."""
    # PRF-014: CPU mode. PRF-020: Machine and human interfaces.
    # PRF-043: Analyzer at every checkpoint.
    sampling = cast("schema.CpuSamplingConfiguration", profile.sampling)
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
    trampoline_status = (
        "enabled" if sampling["python_stack_trampolines"] else "disabled"
    )
    print(
        f"CPU backend: {sampling['cpu_backend']}; "
        + f"Python stack trampolines: {trampoline_status}"
    )
    print(
        f"Wall window: {_duration(analysis.wall_window_ns)}; "
        + f"observed CPU {_duration(analysis.observed_cpu_ns)}; "
        + f"Python-attributed {_duration(analysis.attributed_cpu_ns)}; "
        + f"unattributed {_duration(analysis.unattributed_cpu_ns)}"
    )
    print(f"Unresolved CPU transitions: {analysis.unresolved_transitions}")
    print(
        "Confidence: "
        + f"{analysis.effective_endpoint_count:.1f} effective independent endpoints; "
        + "function intervals are approximate 95% Poisson confidence bounds"
    )
    print(
        f"Compiler exit status: {profile.compiler_exit_status}; "
        + f"diagnostics: {profile.diagnostics_status}"
    )
    print(
        "Resolution: CPU deltas are averaged across their two sampled endpoint "
        + "stacks; functions shorter than the sampling interval may not be resolved; "
        + "endpoint hits are observations, not calls."
    )

    print("\nSelf CPU attribution:")
    for row in analysis.self_function_rows[:limit]:
        print(
            f"  {_duration(row.cpu_time_ns)} CPU "
            + f"± {_duration(row.confidence_95_ns)}; "
            + f"{row.endpoint_hits} endpoints; "
            + _function_text(row.identity)
        )
    print("\nCumulative CPU attribution:")
    for row in analysis.cumulative_function_rows[:limit]:
        print(
            f"  {_duration(row.cpu_time_ns)} CPU "
            + f"± {_duration(row.confidence_95_ns)}; "
            + f"{row.endpoint_hits} endpoints; "
            + _function_text(row.identity)
        )
    print("\nSampled CPU caller -> callee relationships:")
    for row in analysis.relationship_rows[:limit]:
        print(
            f"  {_duration(row.cpu_time_ns)} CPU "
            + f"± {_duration(row.confidence_95_ns)}; "
            + f"{row.endpoint_hits} endpoints; "
            + f"{_function_text(row.caller)} -> {_function_text(row.callee)}"
        )
    print("\nPer-thread CPU attribution:")
    for row in analysis.thread_rows:
        print(
            f"  Thread {row.os_thread_id}: {_duration(row.observed_cpu_ns)} observed; "
            + f"attributed {_duration(row.attributed_cpu_ns)}; "
            + f"unattributed {_duration(row.observed_cpu_ns - row.attributed_cpu_ns)}; "
            + f"{row.interval_count} intervals"
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
        print(f"\nUnretained observations ({len(failed_observations)}):")
        for observation in failed_observations:
            print(
                f"  {observation['observation_index']} {observation['status']}: "
                + f"{observation['failure_kind']}: {observation['failure_reason']}"
            )
