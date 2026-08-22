"""Entry point for the Define compiler."""

from __future__ import annotations

import functools
import io
import os
import stat
import sys
from collections.abc import Callable
from pathlib import Path

import click

from define.compiler import constants, driver, overall_stats

type _CommandFunction = Callable[..., None]
type _ClickWrappedFunction = Callable[..., None]


def _stdin_is_piped() -> bool:
    """Whether stdin is a pipe or redirected file, as opposed to a tty or device."""
    try:
        mode = os.fstat(sys.stdin.fileno()).st_mode
    except io.UnsupportedOperation:
        # Stdin has no inspectable OS file descriptor, so treat it as absent.
        return False
    return stat.S_ISFIFO(mode) or stat.S_ISREG(mode)


def _resolve_input_source(file: Path | None) -> str | None:
    """Resolve piped stdin into source text, rejecting ambiguous or absent input."""
    piped = _stdin_is_piped()
    if file is not None and piped:
        raise click.UsageError(
            "provide either a FILE argument or piped stdin, not both"
        )
    if file is None and not piped:
        raise click.UsageError("no input: pass a FILE or pipe source on stdin")
    # Only read stdin when it is the source; reading is skipped when a file is
    # given, so a file argument never blocks on an open pipe.
    return sys.stdin.read() if piped else None


def _common_options(f: _CommandFunction) -> _ClickWrappedFunction:
    @click.argument("file", type=click.Path(path_type=Path), required=False)
    @click.option(
        "--max-threads",
        type=click.IntRange(min=1),
        default=None,
        help=(
            "Maximum threads used by each validation phase. Defaults to a "
            "heuristic based on available CPU cores."
        ),
    )
    @click.option(
        "--stats",
        type=click.Choice([m.value for m in overall_stats.StatsMode]),
        is_flag=False,
        flag_value=overall_stats.StatsMode.OVERALL.value,
        default=None,
        help="Print timing stats.",
    )
    @click.pass_context
    @functools.wraps(f)
    def wrapper(
        ctx: click.Context,
        file: Path | None,
        max_threads: int | None,
        stats: str | None,
        **kwargs: object,
    ):
        f(ctx, file, max_threads, stats, **kwargs)

    return wrapper


@click.group(invoke_without_command=True)
@click.pass_context
def main(ctx: click.Context):
    """Run the Define compiler."""
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


def _run(
    ctx: click.Context,
    file: Path | None,
    max_threads: int | None,
    stats: str | None,
    mode: driver.DriverMode,
    output_dir: Path | None = None,
):
    source = _resolve_input_source(file)
    d = driver.Driver()
    stats_mode = overall_stats.StatsMode(stats) if stats else None
    stats_stream = sys.stdout if stats_mode is not None else None
    code = d.run(
        file,
        mode=mode,
        error_stream=sys.stderr,
        stats_stream=stats_stream,
        stats_mode=stats_mode or overall_stats.StatsMode.OVERALL,
        output_dir=output_dir,
        source=source,
        max_threads=max_threads,
    )
    ctx.exit(code)


@main.command()
@_common_options
def validate(
    ctx: click.Context,
    file: Path | None,
    max_threads: int | None,
    stats: str | None,
):
    """Validate a Define source file."""
    _run(ctx, file, max_threads, stats, driver.DriverMode.VALIDATE)


@main.command("compile")
@_common_options
@click.option(
    "--out",
    type=click.Path(path_type=Path),
    default=constants.DEFAULT_OUTPUT_DIR,
    show_default=True,
    help="Directory to write generated files into.",
)
def compile_cmd(
    ctx: click.Context,
    file: Path | None,
    max_threads: int | None,
    stats: str | None,
    out: Path,
):
    """Compile a Define source file."""
    _run(ctx, file, max_threads, stats, driver.DriverMode.COMPILE, output_dir=out)


if __name__ == "__main__":  # pragma: no cover
    main()
