"""Print timelines, function tables, and call trees from compiler profiles."""

from __future__ import annotations

import pathlib

import click
import msgspec

from tools.profiler import (
    call_counter,
    call_tree,
    cpu_stacks,
    tachyon_profile,
    wall_timeline,
)

_TACHYON_MAGIC = b"HCAT"
_CALL_COUNTS_START = b'{"calls"'


@click.command(
    epilog=(
        "A wall profile is a Tachyon .bin file; a CPU profile is the collapsed "
        "stacks a CPU capture writes; a calls file from --mode calls prints "
        "the functions called most, or those containing --focus. Views: "
        "timeline (wall only, the default "
        "for wall) prints each thread's runs of work and waiting; "
        "critical-path (wall only) prints the runs the main thread's progress "
        "waited on, in order; functions "
        "(the default for CPU) prints the functions with the most cumulative "
        "and self time; tree prints the call tree; callers prints, for the "
        "function --focus names, the call paths that lead to it, inverted. "
        "--thread, --start-seconds, "
        "and --end-seconds select the samples every view uses, and --focus "
        "starts each stack at its outermost function containing TEXT, so the "
        "tables and tree show what that function spends its time on; "
        "critical-path always follows every thread. Each view begins with "
        "every thread's total, except with --focus. "
        "Percentages divide by the time of every selected sample, before "
        "--focus. Wall time per thread counts waiting too; 'work' is the share "
        "spent executing Python. A sample is an observation, not a call."
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
    help="Wall or CPU profile from run_profile.",
)
@click.option(
    "--view",
    type=click.Choice(["timeline", "critical-path", "functions", "tree", "callers"]),
    help="What to print. Defaults to timeline for wall and functions for CPU.",
)
@click.option(
    "--thread",
    "thread_ids",
    type=int,
    multiple=True,
    help="Use only an OS thread ID; repeat as needed.",
)
@click.option(
    "--start-seconds",
    type=click.FloatRange(min=0.0),
    help="Wall: use samples from this many seconds after the first sample.",
)
@click.option(
    "--end-seconds",
    type=click.FloatRange(min=0.0),
    help="Wall: use samples until this many seconds after the first sample.",
)
@click.option(
    "--focus",
    metavar="TEXT",
    help=(
        "Functions and tree: start each stack at a function containing TEXT. "
        + "Callers: the function whose callers to print."
    ),
)
@click.option(
    "--native",
    is_flag=True,
    help=(
        "CPU: keep the native frames below each stack's innermost Python "
        + "function, so self time shows the native functions."
    ),
)
@click.option(
    "--levels",
    type=click.IntRange(min=1),
    default=6,
    show_default=True,
    help="Callers: how many callers above the function to print.",
)
@click.option(
    "--depth",
    type=click.IntRange(min=1),
    default=1,
    show_default=True,
    help="Timeline and critical path: how many innermost functions a label shows.",
)
@click.option(
    "--minimum-run-ms",
    type=click.FloatRange(min=0.0),
    default=20.0,
    show_default=True,
    help="Timeline: runs shorter than this join or fold into their neighbors.",
)
@click.option(
    "--minimum-percent",
    type=click.FloatRange(min=0.0),
    default=1.0,
    show_default=True,
    help="Tree and callers: omit calls below this share of the selected time.",
)
@click.option(
    "--limit",
    type=click.IntRange(min=1),
    help="Labels per timeline run (default 5) or function rows (default 30).",
)
def main(  # noqa: PLR0913, PLR0917 - Click passes the declared command options.
    profile_path: pathlib.Path,
    view: str | None,
    thread_ids: tuple[int, ...],
    start_seconds: float | None,
    end_seconds: float | None,
    focus: str | None,
    depth: int,
    minimum_run_ms: float,
    minimum_percent: float,
    limit: int | None,
    levels: int,
    *,
    native: bool,
):
    """Analyze one wall or CPU profile."""
    if view == "callers" and focus is None:
        raise click.UsageError("--view callers needs --focus")
    request = _Request(
        view=view,
        thread_ids=frozenset(thread_ids),
        start_seconds=start_seconds,
        end_seconds=end_seconds,
        focus=focus,
        native=native,
        depth=depth,
        minimum_run_ms=minimum_run_ms,
    )
    with profile_path.open("rb") as profile_file:
        start = profile_file.read(len(_CALL_COUNTS_START))
    if start == _CALL_COUNTS_START:
        call_tree.emit_call_counts(call_counter.load(profile_path), focus, limit or 30)
        return
    is_wall = start.startswith(_TACHYON_MAGIC)
    try:
        selection = (
            _wall_selection(profile_path, request, limit or 5)
            if is_wall
            else _cpu_selection(profile_path, request)
        )
    except ValueError as error:
        raise click.ClickException(str(error)) from error
    if selection is None:
        return
    stacks, thread_names = selection
    if not stacks:
        raise click.ClickException("no samples match the selection")
    report = call_tree.Report(
        denominator_ns=sum(stack.total_ns for stack in stacks),
        shows_working=is_wall,
    )
    # A focused view is about one function, and with many workers the
    # threads' totals would run longer than the view itself.
    if focus is None:
        call_tree.emit_threads(stacks, report, thread_names)
    # The usage check above guarantees a focus for the callers view.
    if view == "callers" and focus is not None:
        try:
            call_tree.emit_callers(stacks, report, focus, minimum_percent, levels)
        except ValueError as error:
            raise click.ClickException(str(error)) from error
        return
    if focus is not None:
        stacks = call_tree.focused(stacks, focus)
        if not stacks:
            raise click.ClickException(f"no selected stack contains {focus!r}")
        print(f"\nFocus: stacks from the outermost function containing {focus!r}")
    if view == "tree":
        call_tree.emit_tree(stacks, report, minimum_percent)
    else:
        call_tree.emit_functions(stacks, report, limit or 30)


class _Request(msgspec.Struct, frozen=True):
    view: str | None
    thread_ids: frozenset[int]
    start_seconds: float | None
    end_seconds: float | None
    focus: str | None
    native: bool
    depth: int
    minimum_run_ms: float


type _Selection = tuple[list[call_tree.WeightedStack], dict[int, str]]


def _wall_selection(
    profile_path: pathlib.Path, request: _Request, label_limit: int
) -> _Selection | None:
    if request.native:
        raise click.UsageError("--native applies only to CPU profiles")
    profile = tachyon_profile.load(profile_path)
    start_ns = (
        None
        if request.start_seconds is None
        else profile.started_ns + round(request.start_seconds * 1_000_000_000)
    )
    end_ns = (
        None
        if request.end_seconds is None
        else profile.started_ns + round(request.end_seconds * 1_000_000_000)
    )
    if request.view in {None, "timeline", "critical-path"}:
        if request.focus is not None:
            raise click.UsageError("--focus applies only to functions and tree")
        options = wall_timeline.TimelineOptions(
            depth=request.depth,
            minimum_run_ns=round(request.minimum_run_ms * 1_000_000),
            start_ns=start_ns,
            end_ns=end_ns,
            thread_ids=request.thread_ids,
        )
        if request.view == "critical-path":
            if request.thread_ids:
                raise click.UsageError("the critical path follows every thread")
            wall_timeline.emit_critical_path(
                profile,
                wall_timeline.thread_runs(profile, options),
                request.depth,
            )
            return None
        wall_timeline.emit_report(
            profile,
            wall_timeline.thread_runs(profile, options),
            request.depth,
            label_limit,
        )
        return None
    wall_timeline.emit_header(profile)
    stacks = tachyon_profile.weighted_stacks(
        profile, request.thread_ids, start_ns, end_ns
    )
    return stacks, {profile.main_thread_id: "(main)"}


def _cpu_selection(profile_path: pathlib.Path, request: _Request) -> _Selection:
    if request.view in {"timeline", "critical-path"}:
        raise click.UsageError("a CPU profile has no timeline")
    if request.start_seconds is not None or request.end_seconds is not None:
        raise click.UsageError("a CPU profile has no sample times")
    loaded = cpu_stacks.load(profile_path, native=request.native)
    total_ns = sum(stack.total_ns for stack in loaded.stacks)
    print(
        f"Profile: Linux perf CPU samples at {cpu_stacks.SAMPLING_FREQUENCY_HZ} "
        + "Hz; times are sampled CPU time; "
        + f"{100 * loaded.truncated_ns / total_ns:.1f}% of samples have stacks "
        + "perf could not unwind to their thread's start, which appear under "
        + f"{cpu_stacks.NOT_UNWOUND}"
    )
    if loaded.other_processes:
        print(
            "Left out: samples of other processes perf followed: "
            + "; ".join(
                f"{name} {duration_ns / 1_000_000_000:.3f} s"
                for name, duration_ns in loaded.other_processes.items()
            )
        )
    stacks = [
        stack
        for stack in loaded.stacks
        if not request.thread_ids or stack.thread_id in request.thread_ids
    ]
    thread_names = dict(loaded.thread_names)
    thread_names[loaded.main_thread_id] += " (main)"
    return stacks, thread_names
