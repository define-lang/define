"""Analyze py-spy Chrome traces for wall-critical-path or CPU time."""

from __future__ import annotations

import collections.abc
import enum
import json
import pathlib
from collections import defaultdict
from typing import TypedDict, cast

import click

type _ProfileKey = tuple[str, int, str]
type _FunctionIdentity = tuple[str, str]
type _Interval = tuple[float, float]
type _Segment = tuple[tuple[_ProfileKey, ...], float, float]
type _CpuSample = tuple[tuple[_ProfileKey, ...], float]
# Per-function (self wall occupancy, cumulative wall occupancy, longest span).
type _WallMetrics = tuple[float, float, float]
# Per-function (self CPU time, cumulative CPU time).
type _CpuMetrics = tuple[float, float]


class ProfileMode(enum.StrEnum):
    """Measurement emphasized by the report."""

    WALL = "wall"
    CPU = "cpu"


class _ChromeArgs(TypedDict):
    filename: str
    line: int


class _ChromeEvent(TypedDict):
    args: _ChromeArgs
    name: str
    ph: str
    tid: int
    ts: float


class _RawCpuProfile(TypedDict):
    format: str
    wall_time_seconds: float
    raw_samples: str


_CPU_PROFILE_FORMAT = "define-py-spy-cpu-v1"
_PY_SPY_DEFAULT_SAMPLE_RATE_HZ = 100


def short(function: _ProfileKey) -> str:
    """Render a sampled function as ``dir/file.py:line(name)``."""
    file, line, name = function
    parts = file.rsplit("/", 2)
    short_file = "/".join(parts[-2:]) if len(parts) >= 2 else file
    return f"{short_file}:{line}({name})"


def percent(part: float, total: float) -> float:
    """Calculate a percentage, treating an empty profile as zero percent."""
    return 100.0 * part / total if total else 0.0


def _record_function_line(
    lines: dict[_FunctionIdentity, int], function: _ProfileKey
) -> None:
    filename, line, name = function
    identity = (filename, name)
    current = lines.get(identity)
    if current is None or current == 0 or 0 < line < current:
        lines[identity] = line


def _normalize_stack(
    stack: tuple[_ProfileKey, ...], lines: dict[_FunctionIdentity, int]
) -> tuple[_ProfileKey, ...]:
    return tuple(
        (filename, lines[(filename, name)], name) for filename, _line, name in stack
    )


def load_segments(profile_path: pathlib.Path) -> tuple[float, int, list[_Segment]]:
    """Load timestamped per-thread stack segments from a py-spy Chrome trace."""
    with profile_path.open(encoding="utf-8") as profile_file:
        events = cast("list[_ChromeEvent]", json.load(profile_file))
    if not events:
        return 0.0, 0, []

    by_thread: dict[int, list[_ChromeEvent]] = defaultdict(list)
    function_lines: dict[_FunctionIdentity, int] = {}
    for event in events:
        by_thread[event["tid"]].append(event)
        _record_function_line(
            function_lines,
            (event["args"]["filename"], event["args"]["line"], event["name"]),
        )

    segments: list[_Segment] = []
    for thread_events in by_thread.values():
        thread_events.sort(key=lambda event: event["ts"])
        stack: list[_ProfileKey] = []
        index = 0
        while index < len(thread_events):
            timestamp = thread_events[index]["ts"]
            while (
                index < len(thread_events) and thread_events[index]["ts"] == timestamp
            ):
                event = thread_events[index]
                if event["ph"] == "B":
                    stack.append(
                        (
                            event["args"]["filename"],
                            function_lines[(event["args"]["filename"], event["name"])],
                            event["name"],
                        )
                    )
                else:
                    _ = stack.pop()
                index += 1
            if index == len(thread_events) or not stack:
                continue
            end = thread_events[index]["ts"]
            segments.append(
                (
                    tuple(stack),
                    timestamp / 1_000_000.0,
                    end / 1_000_000.0,
                )
            )

    timestamps = [event["ts"] for event in events]
    wall_time = (max(timestamps) - min(timestamps)) / 1_000_000.0
    return wall_time, len(by_thread), segments


def _parse_raw_frame(frame: str) -> _ProfileKey:
    name, separator, location = frame.rpartition(" (")
    if not separator or not location.endswith(")"):
        return "", 0, frame
    location = location[:-1]
    filename, line_separator, line_text = location.rpartition(":")
    if line_separator and line_text.isdigit():
        return filename, int(line_text), name
    return location, 0, name


def _is_no_python_stack(stack: tuple[_ProfileKey, ...]) -> bool:
    return any(
        function[2].casefold().strip(" <>[]") == "no python frame" for function in stack
    )


def load_cpu_samples(
    profile_path: pathlib.Path,
) -> tuple[float, int, int, list[_CpuSample]]:
    """Load weighted active-thread stacks from a run_profile CPU capture."""
    with profile_path.open(encoding="utf-8") as profile_file:
        profile = cast("_RawCpuProfile", json.load(profile_file))
    if profile["format"] != _CPU_PROFILE_FORMAT:
        raise ValueError(f"unsupported CPU profile format: {profile['format']}")

    retained_samples = 0
    omitted_samples = 0
    samples: list[_CpuSample] = []
    function_lines: dict[_FunctionIdentity, int] = {}
    for line in profile["raw_samples"].splitlines():
        folded_stack, separator, count_text = line.rpartition(" ")
        if not separator:
            raise ValueError(f"invalid raw CPU sample: {line!r}")
        count = int(count_text)
        if not folded_stack:
            omitted_samples += count
            continue
        stack = tuple(_parse_raw_frame(frame) for frame in folded_stack.split(";"))
        if _is_no_python_stack(stack):
            omitted_samples += count
            continue
        for function in stack:
            _record_function_line(function_lines, function)
        retained_samples += count
        samples.append((stack, count / _PY_SPY_DEFAULT_SAMPLE_RATE_HZ))
    normalized_samples = [
        (_normalize_stack(stack, function_lines), duration)
        for stack, duration in samples
    ]
    return (
        profile["wall_time_seconds"],
        retained_samples,
        omitted_samples,
        normalized_samples,
    )


def _merged_interval_metrics(intervals: list[_Interval]) -> tuple[float, float]:
    if not intervals:
        return 0.0, 0.0
    intervals.sort()
    merged_start, merged_end = intervals[0]
    total = 0.0
    longest = 0.0
    for start, end in intervals[1:]:
        if start <= merged_end:
            merged_end = max(merged_end, end)
            continue
        duration = merged_end - merged_start
        total += duration
        longest = max(longest, duration)
        merged_start, merged_end = start, end
    duration = merged_end - merged_start
    return total + duration, max(longest, duration)


def wall_metrics(segments: list[_Segment]) -> dict[_ProfileKey, _WallMetrics]:
    """Union overlapping sampled intervals into per-function wall occupancy."""
    self_intervals: dict[_ProfileKey, list[_Interval]] = defaultdict(list)
    cumulative_intervals: dict[_ProfileKey, list[_Interval]] = defaultdict(list)
    for stack, start, end in segments:
        interval = (start, end)
        self_intervals[stack[-1]].append(interval)
        for function in set(stack):
            cumulative_intervals[function].append(interval)

    metrics: dict[_ProfileKey, _WallMetrics] = {}
    for function in self_intervals.keys() | cumulative_intervals.keys():
        self_time, _self_longest = _merged_interval_metrics(self_intervals[function])
        cumulative_time, longest = _merged_interval_metrics(
            cumulative_intervals[function]
        )
        metrics[function] = (self_time, cumulative_time, longest)
    return metrics


def cpu_metrics(samples: list[_CpuSample]) -> dict[_ProfileKey, _CpuMetrics]:
    """Sum weighted active-thread samples into per-function CPU metrics."""
    metrics: dict[_ProfileKey, _CpuMetrics] = {}
    for stack, duration in samples:
        leaf = stack[-1]
        self_time, cumulative_time = metrics.get(leaf, (0.0, 0.0))
        metrics[leaf] = (self_time + duration, cumulative_time)
        for function in set(stack):
            self_time, cumulative_time = metrics.get(function, (0.0, 0.0))
            metrics[function] = (self_time, cumulative_time + duration)
    return metrics


def without_file(
    samples: collections.abc.Sequence[_CpuSample], excluded_file: str
) -> list[_CpuSample]:
    """Remove sampled stacks that pass through ``excluded_file``."""
    return [
        sample
        for sample in samples
        if all(excluded_file not in function[0] for function in sample[0])
    ]


def compiler_metrics(
    metrics: dict[_ProfileKey, _WallMetrics],
) -> dict[_ProfileKey, _WallMetrics]:
    """Limit wall metrics to Define compiler source files."""
    return {
        function: function_metrics
        for function, function_metrics in metrics.items()
        if "/_main/define/compiler/" in function[0]
        or "/projects/define/define/compiler/" in function[0]
    }


def compiler_cpu_metrics(
    metrics: dict[_ProfileKey, _CpuMetrics],
) -> dict[_ProfileKey, _CpuMetrics]:
    """Limit CPU metrics to Define compiler source files."""
    return {
        function: function_metrics
        for function, function_metrics in metrics.items()
        if "/_main/define/compiler/" in function[0]
        or "/projects/define/define/compiler/" in function[0]
    }


def emit_wall_table(
    metrics: dict[_ProfileKey, _WallMetrics],
    *,
    key: str,
    n: int,
    wall_time: float,
    title: str,
) -> None:
    """Print sampled function wall occupancy or longest continuous spans."""
    index = {"self": 0, "cumulative": 1, "longest": 2}[key]
    rows = sorted(metrics.items(), key=lambda item: item[1][index], reverse=True)
    print(f"\n=== {title} (top {n} by {key}) ===")
    print(f"{'self':>9} {'%wall':>6} {'cumulative':>10} {'longest':>9}  function")
    for function, (self_time, cumulative_time, longest) in rows[:n]:
        print(
            f"{self_time:9.3f} {percent(self_time, wall_time):5.1f}% "
            + f"{cumulative_time:10.3f} {longest:9.3f}  {short(function)}"
        )


def emit_cpu_table(
    metrics: dict[_ProfileKey, _CpuMetrics],
    *,
    key: str,
    n: int,
    cpu_time: float,
    title: str,
) -> None:
    """Print sampled function CPU time ranked by self or cumulative time."""
    index = 0 if key == "self" else 1
    rows = sorted(metrics.items(), key=lambda item: item[1][index], reverse=True)
    print(f"\n=== {title} (top {n} by {key}) ===")
    print(f"{'self':>9} {'%cpu':>6} {'cumulative':>10}  function")
    for function, (self_time, cumulative_time) in rows[:n]:
        print(
            f"{self_time:9.3f} {percent(self_time, cpu_time):5.1f}% "
            + f"{cumulative_time:10.3f}  {short(function)}"
        )


def emit_wall_report(profile_path: pathlib.Path, top: int) -> None:
    """Print the primary wall-time and longest-pole report."""
    wall_time, thread_count, segments = load_segments(profile_path)
    metrics = wall_metrics(segments)
    define_compiler_metrics = compiler_metrics(metrics)
    print(
        f"Wall time: {wall_time:.3f}s; sampled threads: {thread_count}; "
        + f"functions: {len(metrics)}"
    )
    print(
        "NOTE: wall occupancy is the union of timestamped sampled intervals "
        + "across threads; function rows overlap and do not sum to wall time."
    )
    for key in ("self", "longest", "cumulative"):
        emit_wall_table(
            metrics,
            key=key,
            n=top,
            wall_time=wall_time,
            title="PYTHON WALL",
        )
    if define_compiler_metrics:
        for key in ("self", "longest"):
            emit_wall_table(
                define_compiler_metrics,
                key=key,
                n=top,
                wall_time=wall_time,
                title="DEFINE COMPILER WALL",
            )


def emit_cpu_report(profile_path: pathlib.Path, excluded_file: str, top: int) -> None:
    """Print the sampled CPU-time hotspot report."""
    wall_time, sample_count, omitted_samples, samples = load_cpu_samples(profile_path)
    non_lark_samples = without_file(samples, excluded_file)
    cpu_time = sum(weight for _stack, weight in samples)
    non_lark_time = sum(weight for _stack, weight in non_lark_samples)
    excluded_time = cpu_time - non_lark_time
    print(
        f"Attributed CPU time: {cpu_time:.3f}s; wall time: {wall_time:.3f}s; "
        + f"active Python samples: {sample_count}"
    )
    print(
        "NOTE: CPU time weights active-thread samples by the recording rate; it "
        + "can exceed wall time when workers execute concurrently."
    )
    if omitted_samples:
        print(f"Omitted samples without a Python stack: {omitted_samples}")
    print(
        f"\n'{excluded_file}' subtree: {excluded_time:.3f}s sampled time "
        + f"({percent(excluded_time, cpu_time):.1f}%)"
    )
    print(
        f"Non-Lark work: {non_lark_time:.3f}s sampled time "
        + f"({percent(non_lark_time, cpu_time):.1f}%)"
    )
    metrics = cpu_metrics(samples)
    non_lark = cpu_metrics(non_lark_samples)
    define_compiler = compiler_cpu_metrics(metrics)
    emit_cpu_table(metrics, key="self", n=top, cpu_time=cpu_time, title="PYTHON")
    emit_cpu_table(metrics, key="cumulative", n=top, cpu_time=cpu_time, title="PYTHON")
    emit_cpu_table(
        non_lark,
        key="self",
        n=top,
        cpu_time=cpu_time,
        title=f"WITHOUT {excluded_file} subtree",
    )
    emit_cpu_table(
        non_lark,
        key="cumulative",
        n=top,
        cpu_time=cpu_time,
        title=f"WITHOUT {excluded_file} subtree",
    )
    if define_compiler:
        emit_cpu_table(
            define_compiler,
            key="self",
            n=top,
            cpu_time=cpu_time,
            title="DEFINE COMPILER",
        )
        emit_cpu_table(
            define_compiler,
            key="cumulative",
            n=top,
            cpu_time=cpu_time,
            title="DEFINE COMPILER",
        )


@click.command(
    epilog=(
        "Pass the same --profile-mode used when recording the profile. Wall "
        "mode is the primary report: it shows self and cumulative wall "
        "occupancy plus longest continuous spans. Function wall rows can "
        "overlap and must not be added together. CPU mode weights active-thread "
        "samples by the recording rate, so CPU time can exceed wall time under "
        "parallel execution. Samples without a Python stack are omitted from "
        "CPU totals."
    )
)
@click.option(
    "--profile",
    "profile_path",
    type=click.Path(path_type=pathlib.Path),
    required=True,
    help="Profile produced by run_profile in the selected mode.",
)
@click.option(
    "--profile-mode",
    type=click.Choice([mode.value for mode in ProfileMode]),
    default=ProfileMode.WALL.value,
    show_default=True,
    help="Analyze the trace using the mode with which it was recorded.",
)
@click.option(
    "--exclude-file",
    "excluded_file",
    default="lark_standalone.py",
    show_default=True,
    help=(
        "In CPU mode, also report metrics after removing stacks that pass "
        "through this filename."
    ),
)
@click.option(
    "--top",
    type=click.IntRange(min=1),
    default=30,
    show_default=True,
    help="Maximum rows in each metric table.",
)
def main(
    profile_path: pathlib.Path, profile_mode: str, excluded_file: str, top: int
) -> None:
    """Print a wall-critical-path or CPU-time report."""
    if ProfileMode(profile_mode) is ProfileMode.WALL:
        emit_wall_report(profile_path, top)
    else:
        emit_cpu_report(profile_path, excluded_file, top)


if __name__ == "__main__":
    main()
