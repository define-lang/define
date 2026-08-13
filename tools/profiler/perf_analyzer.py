"""Analyze weighted Python call chains directly from Linux perf data."""

from __future__ import annotations

import contextlib
import dataclasses
import fcntl
import itertools
import json
import math
import os
import pathlib
import re
import shutil
import subprocess
import typing

from tools.profiler import analyzer_model, perf_profiler

if typing.TYPE_CHECKING:
    import collections.abc

_HEADER_PATTERN = re.compile(r"^.*?\s+\d+/(?P<tid>\d+)\s+(?P<period>\d+)\s+\S+:\s*$")
_FRAME_PATTERN = re.compile(r"^\s+\S+\s+(?P<symbol>.*?)\s+\((?P<dso>.*)\)\s*$")
_EVENT_PATTERN = re.compile(
    r"^(?P<event>[^:]+)(?::[a-z]+)?: type: .*"
    + r"\{ sample_period, sample_freq \}: (?P<frequency_hz>\d+),.*\bfreq: 1,.*"
)
_PYTHON_MAP_PATTERN = re.compile(r"^/tmp/perf-\d+\.map$")


class PerfAnalysisError(Exception):
    """The native perf artifact could not be analyzed."""


def _perf_executable() -> str:
    executable = shutil.which("perf")
    if executable is None:
        raise PerfAnalysisError("Linux perf is not installed or not on PATH")
    return executable


@dataclasses.dataclass(frozen=True, slots=True)
class Sample:
    """One weighted call chain decoded from native perf data."""

    os_thread_id: int
    period_ns: int
    python_stack_leaf_first: tuple[analyzer_model.FunctionIdentity, ...]
    unresolved_python_frame_count: int = 0


@dataclasses.dataclass(frozen=True, slots=True)
class Profile:
    """Transient decoded view of a native perf artifact."""

    metadata: perf_profiler.Metadata
    event: str
    frequency_hz: int
    diagnostics: str
    samples: list[Sample]
    perf_script_warnings: list[str]

    @property
    def success(self) -> bool:
        """Whether the compiler completed without diagnostics."""
        return self.metadata["compiler_exit_status"] == 0 and not self.diagnostics


@dataclasses.dataclass(frozen=True, slots=True)
class FunctionRow:
    """CPU attribution for one Python function."""

    identity: analyzer_model.FunctionIdentity
    cpu_time_ns: int
    percentage: float
    confidence_95_ns: int
    sample_hits: int


@dataclasses.dataclass(frozen=True, slots=True)
class RelationshipRow:
    """CPU attribution for one sampled Python caller and callee."""

    caller: analyzer_model.FunctionIdentity
    callee: analyzer_model.FunctionIdentity
    cpu_time_ns: int
    percentage: float
    confidence_95_ns: int
    sample_hits: int


@dataclasses.dataclass(frozen=True, slots=True)
class ThreadRow:
    """Weighted perf CPU samples for one OS thread."""

    os_thread_id: int
    sampled_cpu_ns: int
    python_attributed_cpu_ns: int
    sample_count: int


@dataclasses.dataclass(frozen=True, slots=True)
class Analysis:
    """Derived CPU attribution from actual on-CPU perf samples."""

    self_function_rows: list[FunctionRow]
    cumulative_function_rows: list[FunctionRow]
    relationship_rows: list[RelationshipRow]
    thread_rows: list[ThreadRow]
    sampled_cpu_ns: int
    python_attributed_cpu_ns: int
    wall_window_ns: int
    sample_count: int
    effective_sample_count: float

    @property
    def unattributed_cpu_ns(self) -> int:
        """Sampled CPU without a resolved Python frame."""
        return self.sampled_cpu_ns - self.python_attributed_cpu_ns


@dataclasses.dataclass(slots=True)
class _Weight:
    cpu_time_ns: int = 0
    sample_hits: int = 0


def is_perf_data(profile_path: pathlib.Path) -> bool:
    """Whether a file has perf's native file signature."""
    with profile_path.open("rb") as profile_file:
        return profile_file.read(8) == b"PERFILE2"


def _python_identity(symbol: str) -> analyzer_model.FunctionIdentity | None:
    if not symbol.startswith("py::"):
        return None
    identity = symbol.removeprefix("py::")
    try:
        function, filename = identity.rsplit(":", maxsplit=1)
    except ValueError as error:
        raise PerfAnalysisError(f"malformed Python perf symbol: {symbol}") from error
    return analyzer_model.FunctionIdentity(filename=filename, function=function)


def _parse_script_lines(
    lines: collections.abc.Iterable[str],
) -> collections.abc.Iterator[Sample]:
    os_thread_id: int | None = None
    period_ns = 0
    python_frames: list[analyzer_model.FunctionIdentity] = []
    unresolved_python_frame_count = 0
    for line in lines:
        if not line.strip():
            continue
        header_match = _HEADER_PATTERN.match(line)
        if header_match is not None:
            if os_thread_id is not None:
                yield Sample(
                    os_thread_id=os_thread_id,
                    period_ns=period_ns,
                    python_stack_leaf_first=tuple(python_frames),
                    unresolved_python_frame_count=unresolved_python_frame_count,
                )
            os_thread_id = int(header_match.group("tid"))
            period_ns = int(header_match.group("period"))
            python_frames = []
            unresolved_python_frame_count = 0
            continue
        frame_match = _FRAME_PATTERN.match(line)
        if os_thread_id is None or frame_match is None:
            raise PerfAnalysisError(f"malformed perf script line: {line.rstrip()}")
        symbol = frame_match.group("symbol")
        python_identity = _python_identity(symbol)
        if python_identity is not None:
            python_frames.append(python_identity)
        elif symbol == "[unknown]" and _PYTHON_MAP_PATTERN.fullmatch(
            frame_match.group("dso")
        ):
            unresolved_python_frame_count += 1
    if os_thread_id is not None:
        yield Sample(
            os_thread_id=os_thread_id,
            period_ns=period_ns,
            python_stack_leaf_first=tuple(python_frames),
            unresolved_python_frame_count=unresolved_python_frame_count,
        )


def _run_perf_script(
    profile_path: pathlib.Path, *arguments: str
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        (
            _perf_executable(),
            "--buildid-dir",
            os.fspath(perf_profiler.buildid_path(profile_path)),
            "script",
            "-i",
            os.fspath(profile_path),
            *arguments,
        ),
        check=False,
        capture_output=True,
        text=True,
    )


@contextlib.contextmanager
def _materialized_python_map(
    profile_path: pathlib.Path, target_pid: int
) -> collections.abc.Generator[None]:
    retained_map_path = perf_profiler.python_map_path(profile_path)
    if not retained_map_path.is_file() or retained_map_path.stat().st_size == 0:
        raise PerfAnalysisError("the retained CPython perf symbol map is missing")
    retained_map = retained_map_path.read_bytes()
    runtime_map_path = perf_profiler.runtime_python_map_path(target_pid)
    target_process_path = pathlib.Path("/proc") / str(target_pid)
    lock_path = runtime_map_path.with_name(runtime_map_path.name + ".define-lock")
    with lock_path.open("a+b") as lock_file:
        fcntl.flock(lock_file, fcntl.LOCK_EX)
        if target_process_path.exists():
            raise PerfAnalysisError(
                f"cannot safely restore symbols: process {target_pid} is live"
            )
        try:
            with runtime_map_path.open("xb") as runtime_map_file:
                _ = runtime_map_file.write(retained_map)
        except FileExistsError as error:
            raise PerfAnalysisError(
                f"cannot safely restore symbols: {runtime_map_path} already exists"
            ) from error
        runtime_map_inode = runtime_map_path.stat().st_ino
        if target_process_path.exists():
            runtime_map_path.unlink()
            raise PerfAnalysisError(
                f"cannot safely restore symbols: process {target_pid} was reused"
            )
        try:
            yield
        finally:
            current_inode = (
                runtime_map_path.stat().st_ino if runtime_map_path.exists() else None
            )
            map_changed = (
                current_inode != runtime_map_inode
                or runtime_map_path.read_bytes() != retained_map
                or target_process_path.exists()
            )
            if current_inode == runtime_map_inode:
                runtime_map_path.unlink()
            if map_changed:
                raise PerfAnalysisError(
                    "the restored CPython symbol map changed during perf analysis"
                )


def _decode(
    profile_path: pathlib.Path, target_pid: int
) -> tuple[list[Sample], list[str]]:
    with _materialized_python_map(profile_path, target_pid):
        completed = _run_perf_script(
            profile_path,
            "-F",
            "comm,pid,tid,event,period,ip,sym,dso",
            "--no-inline",
        )
    if completed.returncode != 0:
        raise PerfAnalysisError(completed.stderr.strip() or "perf script failed")
    return list(_parse_script_lines(completed.stdout.splitlines())), [
        line for line in completed.stderr.splitlines() if line
    ]


def _configuration(profile_path: pathlib.Path) -> tuple[str, int]:
    completed = subprocess.run(
        (_perf_executable(), "evlist", "-i", os.fspath(profile_path), "-v"),
        check=True,
        capture_output=True,
        text=True,
    )
    match = _EVENT_PATTERN.fullmatch(completed.stdout.strip())
    if match is None:
        raise PerfAnalysisError("perf data does not contain one frequency event")
    return match.group("event"), int(match.group("frequency_hz"))


def load(profile_path: pathlib.Path) -> Profile:
    """Decode native perf data and its small Define metadata sidecar."""
    metadata = typing.cast(
        "perf_profiler.Metadata",
        json.loads(
            perf_profiler.metadata_path(profile_path).read_text(encoding="utf-8")
        ),
    )
    event, frequency_hz = _configuration(profile_path)
    samples, warnings = _decode(profile_path, metadata["target_pid"])
    if not samples:
        raise PerfAnalysisError("perf recorded no CPU samples")
    if not any(sample.python_stack_leaf_first for sample in samples):
        raise PerfAnalysisError(
            "perf recorded no Python frames; the target must use CPython perf support"
        )
    unresolved_samples = [
        sample for sample in samples if sample.unresolved_python_frame_count
    ]
    if unresolved_samples:
        sampled_cpu_ns = sum(sample.period_ns for sample in samples)
        unresolved_cpu_ns = sum(sample.period_ns for sample in unresolved_samples)
        raise PerfAnalysisError(
            "perf left CPython frames unresolved in "
            + f"{len(unresolved_samples)} of {len(samples)} samples "
            + f"({100 * unresolved_cpu_ns / sampled_cpu_ns:.4f}% of sampled CPU); "
            + "refusing potentially incorrect Python attribution"
        )
    return Profile(
        metadata=metadata,
        event=event,
        frequency_hz=frequency_hz,
        diagnostics=perf_profiler.diagnostics_path(profile_path).read_text(
            encoding="utf-8"
        ),
        samples=samples,
        perf_script_warnings=warnings,
    )


def _add_weight[Identity](
    weights: dict[Identity, _Weight], identity: Identity, period_ns: int
):
    weight = weights.get(identity)
    if weight is None:
        weight = _Weight()
        weights[identity] = weight
    weight.cpu_time_ns += period_ns
    weight.sample_hits += 1


def _confidence_95_ns(
    cpu_time_ns: int,
    sampled_cpu_ns: int,
    effective_sample_count: float,
) -> int:
    proportion = cpu_time_ns / sampled_cpu_ns
    standard_error = sampled_cpu_ns * math.sqrt(
        proportion * (1 - proportion) / effective_sample_count
    )
    return round(1.96 * standard_error)


def _function_rows(
    weights: dict[analyzer_model.FunctionIdentity, _Weight],
    filters: analyzer_model.AnalysisFilters,
    sampled_cpu_ns: int,
    effective_sample_count: float,
) -> list[FunctionRow]:
    rows = [
        FunctionRow(
            identity=identity,
            cpu_time_ns=weight.cpu_time_ns,
            percentage=(100 * weight.cpu_time_ns / sampled_cpu_ns),
            confidence_95_ns=_confidence_95_ns(
                weight.cpu_time_ns, sampled_cpu_ns, effective_sample_count
            ),
            sample_hits=weight.sample_hits,
        )
        for identity, weight in weights.items()
        if analyzer_model.matches_function(identity, filters)
    ]
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
    sampled_cpu_ns: int,
    effective_sample_count: float,
) -> list[RelationshipRow]:
    rows: list[RelationshipRow] = []
    for (caller, callee), weight in weights.items():
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
                percentage=100 * weight.cpu_time_ns / sampled_cpu_ns,
                confidence_95_ns=_confidence_95_ns(
                    weight.cpu_time_ns, sampled_cpu_ns, effective_sample_count
                ),
                sample_hits=weight.sample_hits,
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
    profile: Profile,
    filters: analyzer_model.AnalysisFilters = analyzer_model.DEFAULT_FILTERS,
) -> Analysis:
    """Derive self, cumulative, relationship, and thread CPU attribution."""
    sampled_cpu_ns = sum(sample.period_ns for sample in profile.samples)
    squared_periods = sum(sample.period_ns**2 for sample in profile.samples)
    effective_sample_count = (
        sampled_cpu_ns**2 / squared_periods if squared_periods else 0.0
    )
    self_functions: dict[analyzer_model.FunctionIdentity, _Weight] = {}
    cumulative_functions: dict[analyzer_model.FunctionIdentity, _Weight] = {}
    relationships: dict[
        tuple[analyzer_model.FunctionIdentity, analyzer_model.FunctionIdentity],
        _Weight,
    ] = {}
    thread_weights: dict[int, _Weight] = {}
    thread_python_cpu: dict[int, int] = {}
    python_attributed_cpu_ns = 0
    for sample in profile.samples:
        period_ns = sample.period_ns
        _add_weight(thread_weights, sample.os_thread_id, period_ns)
        stack = tuple(reversed(sample.python_stack_leaf_first))
        if stack:
            python_attributed_cpu_ns += period_ns
            thread_python_cpu[sample.os_thread_id] = (
                thread_python_cpu.get(sample.os_thread_id, 0) + period_ns
            )
        if filters.thread_ids and sample.os_thread_id not in filters.thread_ids:
            continue
        if not stack:
            continue
        _add_weight(self_functions, stack[-1], period_ns)
        for identity in set(stack):
            _add_weight(cumulative_functions, identity, period_ns)
        for relationship in set(itertools.pairwise(stack)):
            _add_weight(relationships, relationship, period_ns)

    thread_rows = [
        ThreadRow(
            os_thread_id=thread_id,
            sampled_cpu_ns=weight.cpu_time_ns,
            python_attributed_cpu_ns=thread_python_cpu.get(thread_id, 0),
            sample_count=weight.sample_hits,
        )
        for thread_id, weight in thread_weights.items()
        if not filters.thread_ids or thread_id in filters.thread_ids
    ]
    thread_rows.sort(key=lambda row: (-row.sampled_cpu_ns, row.os_thread_id))
    return Analysis(
        self_function_rows=_function_rows(
            self_functions, filters, sampled_cpu_ns, effective_sample_count
        ),
        cumulative_function_rows=_function_rows(
            cumulative_functions, filters, sampled_cpu_ns, effective_sample_count
        ),
        relationship_rows=_relationship_rows(
            relationships, filters, sampled_cpu_ns, effective_sample_count
        ),
        thread_rows=thread_rows,
        sampled_cpu_ns=sampled_cpu_ns,
        python_attributed_cpu_ns=python_attributed_cpu_ns,
        wall_window_ns=profile.metadata["ended_ns"] - profile.metadata["started_ns"],
        sample_count=len(profile.samples),
        effective_sample_count=effective_sample_count,
    )


def _duration(duration_ns: int) -> str:
    return f"{duration_ns / 1_000_000_000:.6f} s"


def _function_text(identity: analyzer_model.FunctionIdentity) -> str:
    return f"{analyzer_model.display_filename(identity.filename)} ({identity.function})"


def emit_report(profile: Profile, analysis: Analysis, limit: int):
    """Print stable perf CPU attribution and capture diagnostics."""
    status = "successful" if profile.success else "unsuccessful"
    metadata = profile.metadata
    print(f"Native perf profile: complete; {status}")
    print(f"Command: {' '.join(metadata['command'])}")
    print(f"Working directory: {metadata['working_directory']}")
    print(
        f"Workload: {metadata['workload_path']} "
        + f"(sha256 {metadata['workload_sha256']})"
    )
    print(
        f"CPU backend: linux-perf; {profile.event} at {profile.frequency_hz} Hz; "
        + "frame-pointer call graph; CPython perf-map symbols"
    )
    print(
        f"Wall window: {_duration(analysis.wall_window_ns)}; "
        + f"sampled CPU {_duration(analysis.sampled_cpu_ns)}; "
        + f"Python-attributed {_duration(analysis.python_attributed_cpu_ns)}; "
        + f"unattributed {_duration(analysis.unattributed_cpu_ns)}"
    )
    print(
        f"Samples: {analysis.sample_count}; "
        + f"{analysis.effective_sample_count:.1f} effective weighted samples; "
        + "function intervals are approximate 95% sampling confidence bounds"
    )
    print(
        f"Compiler exit status: {metadata['compiler_exit_status']}; "
        + f"diagnostics: {'present' if profile.diagnostics else 'none'}"
    )
    print(
        "Resolution: percentages use all sampled CPU as the denominator; "
        + "all sampled CPython trampoline frames resolved; "
        + "sample hits are observations, not calls."
    )

    print("\nSelf CPU attribution:")
    for row in analysis.self_function_rows[:limit]:
        print(
            f"  {_duration(row.cpu_time_ns)} CPU; {row.percentage:.2f}%; "
            + f"± {_duration(row.confidence_95_ns)}; {row.sample_hits} samples; "
            + _function_text(row.identity)
        )
    print("\nCumulative CPU attribution:")
    for row in analysis.cumulative_function_rows[:limit]:
        print(
            f"  {_duration(row.cpu_time_ns)} CPU; {row.percentage:.2f}%; "
            + f"± {_duration(row.confidence_95_ns)}; {row.sample_hits} samples; "
            + _function_text(row.identity)
        )
    print("\nSampled CPU caller -> callee relationships:")
    for row in analysis.relationship_rows[:limit]:
        print(
            f"  {_duration(row.cpu_time_ns)} CPU; {row.percentage:.2f}%; "
            + f"± {_duration(row.confidence_95_ns)}; {row.sample_hits} samples; "
            + f"{_function_text(row.caller)} -> {_function_text(row.callee)}"
        )
    print("\nPer-thread CPU attribution:")
    for row in analysis.thread_rows:
        print(
            f"  Thread {row.os_thread_id}: {_duration(row.sampled_cpu_ns)} sampled; "
            + f"Python-attributed {_duration(row.python_attributed_cpu_ns)}; "
            + f"{row.sample_count} samples"
        )
    if profile.perf_script_warnings:
        print("\nPerf script warnings:")
        for warning in profile.perf_script_warnings:
            print(f"  {warning}")
