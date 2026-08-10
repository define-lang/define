"""Public dispatch for wall and CPU profile analysis."""

from __future__ import annotations

import pathlib
from typing import cast

import click

from tools.profiler import (
    analyzer_model,
    cpu_analyzer,
    schema,
    wall_analyzer,
)


def analyze(
    profile: schema.RawProfile,
    filters: analyzer_model.AnalysisFilters = analyzer_model.DEFAULT_FILTERS,
) -> wall_analyzer.Analysis | cpu_analyzer.Analysis:
    """Derive attribution using the capture mode recorded in the profile."""
    # PRF-013: Wall mode. PRF-014: CPU mode.
    if profile.sampling["mode"] == "cpu":
        return cpu_analyzer.analyze(profile, filters)
    return wall_analyzer.analyze(profile, filters)


def emit_report(
    profile: schema.RawProfile,
    analysis: wall_analyzer.Analysis | cpu_analyzer.Analysis,
    limit: int,
):
    """Emit the report matching the profile's recorded capture mode."""
    # PRF-014: CPU mode. PRF-020: Machine and human interfaces.
    if profile.sampling["mode"] == "cpu":
        cpu_analyzer.emit_report(
            profile,
            cast("cpu_analyzer.Analysis", analysis),
            limit,
        )
        return
    wall_analyzer.emit_report(
        profile,
        cast("wall_analyzer.Analysis", analysis),
        limit,
    )


# PRF-014: CPU mode. PRF-020: Machine and human interfaces.
@click.command(
    epilog=(
        "Wall rows report unioned occupancy. CPU rows report additive external "
        "scheduler runtime. Sample hits and endpoints are observations, not calls."
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
    help="Raw JSON-record profile produced by //tools/profiler:__main__.",
)
@click.option("--thread", "thread_ids", type=int, multiple=True)
@click.option("--file", "filename", help="Show frames whose filename contains TEXT.")
@click.option("--function", help="Show frames whose function name contains TEXT.")
@click.option("--caller", help="Show relationships whose caller contains TEXT.")
@click.option("--callee", help="Show relationships whose callee contains TEXT.")
@click.option(
    "--compiler-only",
    is_flag=True,
    help="Show only frames under define/compiler.",
)
@click.option(
    "--limit",
    type=click.IntRange(min=1),
    default=25,
    show_default=True,
    help="Maximum rows in each attribution table.",
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
    try:
        profile = schema.load(profile_path)
    except ValueError as error:
        raise click.ClickException(str(error)) from error
    filters = analyzer_model.AnalysisFilters(
        thread_ids=frozenset(thread_ids),
        filename=filename,
        function=function,
        caller=caller,
        callee=callee,
        compiler_only=compiler_only,
    )
    report = analyze(profile, filters)
    emit_report(profile, report, limit)
