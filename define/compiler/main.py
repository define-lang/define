"""Entry point for the Define compiler."""

import functools
import sys
from collections.abc import Callable
from pathlib import Path

import click

from define.compiler import driver, overall_stats

type _CommandFunction = Callable[[click.Context, Path, str | None], None]
type _ClickWrappedFunction = Callable[[Path, str | None], None]


def _common_options(f: _CommandFunction) -> _ClickWrappedFunction:
    @click.argument("file", type=click.Path(path_type=Path))
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
    def wrapper(ctx: click.Context, file: Path, stats: str | None):
        f(ctx, file, stats)

    return wrapper


@click.group(invoke_without_command=True)
@click.pass_context
def main(ctx: click.Context):
    """Run the Define compiler."""
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


def _run(ctx: click.Context, file: Path, stats: str | None, mode: driver.DriverMode):
    d = driver.Driver()
    stats_mode = overall_stats.StatsMode(stats) if stats else None
    stats_stream = sys.stdout if stats_mode is not None else None
    code = d.run(
        file,
        mode=mode,
        error_stream=sys.stderr,
        stats_stream=stats_stream,
        stats_mode=stats_mode or overall_stats.StatsMode.OVERALL,
    )
    ctx.exit(code)


@main.command()
@_common_options
def validate(ctx: click.Context, file: Path, stats: str | None):
    """Validate a Define source file."""
    _run(ctx, file, stats, driver.DriverMode.VALIDATE)


@main.command("compile")
@_common_options
def compile_cmd(ctx: click.Context, file: Path, stats: str | None):
    """Compile a Define source file."""
    _run(ctx, file, stats, driver.DriverMode.COMPILE)


if __name__ == "__main__":
    main()
