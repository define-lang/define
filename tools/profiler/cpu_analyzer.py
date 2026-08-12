"""Analyze scheduler-runtime endpoints from CPU profiler observations."""

from __future__ import annotations

import dataclasses
import itertools
import math
from typing import cast

from tools.profiler import analyzer_model, schema


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
    self_function_rows: list[FunctionRow]
    cumulative_function_rows: list[FunctionRow]
    relationship_rows: list[RelationshipRow]
    thread_rows: list[ThreadRow]
    wall_window_ns: int
    unresolved_transitions: int
    effective_endpoint_count: float

    @property
    def observed_cpu_ns(self) -> int:
        """Scheduler runtime observed across analyzed threads."""
        return sum(row.observed_cpu_ns for row in self.thread_rows)

    @property
    def attributed_cpu_ns(self) -> int:
        """Observed scheduler runtime with Python stacks at both endpoints."""
        return sum(row.attributed_cpu_ns for row in self.thread_rows)

    @property
    def unattributed_cpu_ns(self) -> int:
        """Observed scheduler runtime lacking two Python stack endpoints."""
        return self.observed_cpu_ns - self.attributed_cpu_ns


@dataclasses.dataclass(slots=True)
class _ThreadTotals:
    observed_cpu_ns: int
    attributed_cpu_ns: int
    interval_count: int


@dataclasses.dataclass(slots=True)
class _Weight:
    cpu_time_ns: int = 0
    endpoint_hits: int = 0


@dataclasses.dataclass(slots=True)
class _Attribution:
    self_functions: dict[analyzer_model.FunctionIdentity, _Weight] = dataclasses.field(
        default_factory=dict
    )
    cumulative_functions: dict[analyzer_model.FunctionIdentity, _Weight] = (
        dataclasses.field(default_factory=dict)
    )
    relationships: dict[
        tuple[analyzer_model.FunctionIdentity, analyzer_model.FunctionIdentity],
        _Weight,
    ] = dataclasses.field(default_factory=dict)
    squared_endpoint_weights: int = 0


def _threads_by_identity(
    observation: schema.SuccessfulObservation,
) -> dict[tuple[int, int], schema.CpuThreadObservation]:
    # PRF-005: Lifecycle-bounded attribution. PRF-014: CPU mode.
    threads: dict[tuple[int, int], schema.CpuThreadObservation] = {}
    for sampled_thread in observation["threads"]:
        thread = cast("schema.CpuThreadObservation", sampled_thread)
        threads[(thread["os_thread_id"], thread["start_time_ticks"])] = thread
    return threads


def _add_weight[Identity](
    weights: dict[Identity, _Weight],
    identity: Identity,
    weight_ns: int,
):
    # PRF-014: CPU mode.
    weight = weights.get(identity)
    if weight is None:
        weight = _Weight()
        weights[identity] = weight
    weight.cpu_time_ns += weight_ns
    weight.endpoint_hits += 1


def _attribute_stack(
    stack: list[int],
    weight_ns: int,
    functions: dict[int, analyzer_model.FunctionIdentity],
    attribution: _Attribution,
) -> None:
    stack_path = tuple(functions[frame_id] for frame_id in stack)
    _add_weight(attribution.self_functions, stack_path[-1], weight_ns)
    for identity in set(stack_path):
        _add_weight(attribution.cumulative_functions, identity, weight_ns)
    for relationship in set(itertools.pairwise(stack_path)):
        _add_weight(attribution.relationships, relationship, weight_ns)
    attribution.squared_endpoint_weights += weight_ns**2


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


def _function_rows(
    weights_by_function: dict[analyzer_model.FunctionIdentity, _Weight],
    filters: analyzer_model.AnalysisFilters,
    attributed_cpu_ns: int,
    effective_endpoint_count: float,
) -> list[FunctionRow]:
    # PRF-014: CPU mode. PRF-018: Focused analysis.
    rows: list[FunctionRow] = []
    for identity, weight in weights_by_function.items():
        if not analyzer_model.matches_function(identity, filters):
            continue
        rows.append(
            FunctionRow(
                identity=identity,
                cpu_time_ns=weight.cpu_time_ns,
                confidence_95_ns=_confidence_95_ns(
                    weight.cpu_time_ns,
                    attributed_cpu_ns,
                    effective_endpoint_count,
                ),
                endpoint_hits=weight.endpoint_hits,
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
        tuple[analyzer_model.FunctionIdentity, analyzer_model.FunctionIdentity],
        _Weight,
    ],
    filters: analyzer_model.AnalysisFilters,
    attributed_cpu_ns: int,
    effective_endpoint_count: float,
) -> list[RelationshipRow]:
    # PRF-014: CPU mode. PRF-018: Focused analysis.
    rows: list[RelationshipRow] = []
    for relationship, weight in weights.items():
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
                cpu_time_ns=weight.cpu_time_ns,
                confidence_95_ns=_confidence_95_ns(
                    weight.cpu_time_ns,
                    attributed_cpu_ns,
                    effective_endpoint_count,
                ),
                endpoint_hits=weight.endpoint_hits,
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
    functions = {
        frame_id: analyzer_model.function_identity(frame)
        for frame_id, frame in profile.frames.items()
    }
    attribution = _Attribution()
    thread_totals: dict[int, _ThreadTotals] = {}
    unresolved_transitions = 0
    observations = profile.observations
    earlier_threads = (
        _threads_by_identity(observations[0])
        if observations and observations[0]["status"] == "successful"
        else None
    )
    for later in observations[1:]:
        later_threads = (
            _threads_by_identity(later) if later["status"] == "successful" else None
        )
        if earlier_threads is None or later_threads is None:
            unresolved_transitions += 1
            earlier_threads = later_threads
            continue
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
            totals = thread_totals.get(thread_id)
            if totals is None:
                totals = _ThreadTotals(0, 0, 0)
                thread_totals[thread_id] = totals
            totals.observed_cpu_ns += cpu_delta_ns
            totals.interval_count += 1
            if not earlier_thread["stack"] or not later_thread["stack"]:
                continue
            totals.attributed_cpu_ns += cpu_delta_ns
            earlier_weight_ns = cpu_delta_ns // 2
            _attribute_stack(
                earlier_thread["stack"],
                earlier_weight_ns,
                functions,
                attribution,
            )
            _attribute_stack(
                later_thread["stack"],
                cpu_delta_ns - earlier_weight_ns,
                functions,
                attribution,
            )
        earlier_threads = later_threads

    thread_rows = [
        ThreadRow(
            os_thread_id=thread_id,
            observed_cpu_ns=totals.observed_cpu_ns,
            attributed_cpu_ns=totals.attributed_cpu_ns,
            interval_count=totals.interval_count,
        )
        for thread_id, totals in thread_totals.items()
    ]
    thread_rows.sort(key=lambda row: (-row.observed_cpu_ns, row.os_thread_id))
    attributed_cpu_ns = sum(row.attributed_cpu_ns for row in thread_rows)
    effective_endpoint_count = (
        attributed_cpu_ns**2 / attribution.squared_endpoint_weights
        if attribution.squared_endpoint_weights
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
        self_function_rows=_function_rows(
            attribution.self_functions,
            filters,
            attributed_cpu_ns,
            effective_endpoint_count,
        ),
        cumulative_function_rows=_function_rows(
            attribution.cumulative_functions,
            filters,
            attributed_cpu_ns,
            effective_endpoint_count,
        ),
        relationship_rows=_relationship_rows(
            attribution.relationships,
            filters,
            attributed_cpu_ns,
            effective_endpoint_count,
        ),
        thread_rows=thread_rows,
        wall_window_ns=wall_window_ns,
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
    attempted = counts["successful"] + counts["discarded"]
    print(
        "Observations: "
        + f"{counts['successful']} successful, {counts['discarded']} discarded, "
        + f"{counts['missed']} missed, {attempted} attempted"
    )
    print(f"CPU backend: {sampling['cpu_backend']}")
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
