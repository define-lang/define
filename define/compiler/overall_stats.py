"""Formatting and aggregation of compilation timing statistics."""

from __future__ import annotations

import enum
import typing
from dataclasses import dataclass

if typing.TYPE_CHECKING:
    from collections.abc import Sequence

    from define.compiler.data_structures import define_path
    from define.compiler.validator import stats as validation_stats
    from define.compiler.validator import validation_result


@dataclass(frozen=True, slots=True)
class FileTiming:
    """The validation timing retained for one compiled file."""

    file_path: define_path.DefinePath
    stats: validation_stats.ValidationTimingStats


class StatsMode(enum.StrEnum):
    """Controls how much timing detail to display."""

    OVERALL = "overall"
    PER_FILE = "per-file"


@dataclass
class OverallStats:
    """Aggregated timing totals across all compiled files."""

    config_loading: int = 0
    file_count: int = 0
    file_loading: int = 0
    parse: int = 0
    file_validation: int = 0
    global_validation: int = 0
    avg_queue_wait: int = 0
    max_queue_wait: int = 0
    overall_compile: int = 0


def calculate_overall_stats(
    results: Sequence[validation_result.FileValidationResult],
    config_loading_time_ns: int,
) -> OverallStats:
    """Sum per-file stats into program-level totals."""
    s = OverallStats(config_loading=config_loading_time_ns)
    total_queue_wait = 0

    for result in results:
        fs = result.stats
        s.file_loading += fs.file_loading
        s.parse += fs.parse
        s.file_validation += fs.file_validation
        s.global_validation += fs.global_validation
        total_queue_wait += fs.queue_wait
        s.max_queue_wait = max(s.max_queue_wait, fs.queue_wait)

    s.file_count = len(results)
    s.avg_queue_wait = total_queue_wait // s.file_count if s.file_count > 0 else 0
    s.overall_compile = (
        s.file_loading + s.parse + s.file_validation + s.global_validation
    )
    return s


def format_ns(nanoseconds: int) -> str:
    """Format nanoseconds as milliseconds, showing <0.01 ms for tiny non-zero values."""
    if nanoseconds == 0:
        return "0.00 ms"
    ms = nanoseconds / 1_000_000
    if ms < 0.005:
        return "<0.01 ms"
    return f"{ms:.2f} ms"


def _format_section(title: str, rows: list[tuple[str, str]]) -> str:
    """Format a section with a title and right-justified label rows."""
    max_label_width = max(len(label) for label, _ in rows)
    lines = [f"-- {title} --"]
    for label, value in rows:
        lines.append(f"{label:>{max_label_width}}:  {value}")
    return "\n".join(lines)


def _format_overall_section(stats: OverallStats) -> str:
    """Format the Overall section."""
    return _format_section(
        "Overall",
        [
            ("Files compiled", str(stats.file_count)),
            ("Overall compile", format_ns(stats.overall_compile)),
            ("Config loading", format_ns(stats.config_loading)),
            ("Avg queue wait", format_ns(stats.avg_queue_wait)),
            ("Max queue wait", format_ns(stats.max_queue_wait)),
        ],
    )


def _format_breakdown_section(stats: OverallStats) -> str:
    """Format the Breakdown section."""
    return _format_section(
        "Breakdown",
        [
            ("File loading", format_ns(stats.file_loading)),
            ("Parse", format_ns(stats.parse)),
            ("File validation", format_ns(stats.file_validation)),
            ("Global validation", format_ns(stats.global_validation)),
        ],
    )


def _format_per_file_section(
    results: Sequence[FileTiming],
) -> str:
    """Format the Per File section, sorted slowest first."""
    sorted_results = sorted(
        results, key=lambda r: r.stats.overall_compile, reverse=True
    )
    lines = ["-- Per File (slowest first) --"]
    for result in sorted_results:
        s = result.stats
        lines.append(f"  {result.file_path}")
        file_rows = [
            ("Overall compile", format_ns(s.overall_compile)),
            ("File loading", format_ns(s.file_loading)),
            ("Parse", format_ns(s.parse)),
            ("File validation", format_ns(s.file_validation)),
            ("Global validation", format_ns(s.global_validation)),
            ("Queue wait", format_ns(s.queue_wait)),
        ]
        max_label_width = max(len(label) for label, _ in file_rows)
        for label, value in file_rows:
            lines.append(f"    {label:>{max_label_width}}:  {value}")
    return "\n".join(lines)


def format_stats(
    stats: OverallStats,
    results: Sequence[FileTiming],
    mode: StatsMode,
) -> str:
    """Format timing stats for the given mode."""
    sections = [
        "--- Compilation Stats ---",
        "",
        _format_overall_section(stats),
        "",
        _format_breakdown_section(stats),
    ]

    if mode == StatsMode.PER_FILE:
        sections.append("")
        sections.append(_format_per_file_section(results))

    return "\n".join(sections) + "\n"
