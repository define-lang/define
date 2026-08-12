"""Public dispatch for wall and perf CPU profile analysis."""

from __future__ import annotations

import pathlib

import click

from tools.profiler import analyzer_model, perf_analyzer, schema, wall_analyzer


# PRF-014: CPU mode. PRF-020: Machine and human interfaces.
# PRF-047: Multi-threaded critical path.
@click.command(
    epilog=(
        "Wall work is sampled running time on the completion-critical chain; "
        "wait is blocking on that chain; uncertain is time whose producer or "
        "stack was not resolved. Occupancy unions sampled intervals and rows "
        "overlap; span is the longest continuous sampled interval. CPU rows "
        "report weighted Linux perf samples. Filters affect attribution "
        "rows while lifecycle totals and critical-path context remain global. "
        "Sample hits are observations, not calls."
    )
)
@click.option(
    "--profile",
    "profile_path",
    type=click.Path(
        path_type=pathlib.Path,
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
    ),
    required=True,
    help="Raw wall JSON records or native perf data from //tools/profiler:__main__.",
)
@click.option(
    "--thread",
    "thread_ids",
    type=int,
    multiple=True,
    help="Filter attribution rows to an OS thread ID; repeat as needed.",
)
@click.option(
    "--file",
    "filename",
    help="Filter attribution rows to filenames containing TEXT.",
)
@click.option(
    "--function",
    help="Filter attribution rows to function names containing TEXT.",
)
@click.option(
    "--caller",
    help="Filter relationship rows to callers containing TEXT.",
)
@click.option(
    "--callee",
    help="Filter relationship rows to callees containing TEXT.",
)
@click.option(
    "--compiler-only",
    is_flag=True,
    help="Filter attribution rows to frames under define/compiler.",
)
@click.option(
    "--limit",
    type=click.IntRange(min=1),
    default=5,
    show_default=True,
    help="Maximum rows, handoffs, and critical-path excerpts per section.",
)
def main(
    profile_path: pathlib.Path,
    thread_ids: tuple[int, ...],
    filename: str | None,
    function: str | None,
    caller: str | None,
    callee: str | None,
    *,
    compiler_only: bool,
    limit: int,
):
    """Analyze one continuous raw wall or CPU profile."""
    # PRF-018: Focused analysis. PRF-043: Analyzer at every checkpoint.
    filters = analyzer_model.AnalysisFilters(
        thread_ids=frozenset(thread_ids),
        filename=filename,
        function=function,
        caller=caller,
        callee=callee,
        compiler_only=compiler_only,
    )
    try:
        if perf_analyzer.is_perf_data(profile_path):
            perf_profile = perf_analyzer.load(profile_path)
            perf_report = perf_analyzer.analyze(perf_profile, filters)
            perf_analyzer.emit_report(perf_profile, perf_report, limit)
            return
        profile = schema.load(profile_path)
    except (ValueError, perf_analyzer.PerfAnalysisError) as error:
        raise click.ClickException(str(error)) from error
    report = wall_analyzer.analyze(profile, filters)
    wall_analyzer.emit_report(profile, report, limit)
