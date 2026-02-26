"""Entry point for the Define compiler."""

import sys
from pathlib import Path

import click

from define.compiler import driver, overall_stats


@click.command()
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
def main(ctx: click.Context, file: Path, stats: str | None):
    """Run the Define compiler."""
    d = driver.Driver()
    stats_mode = overall_stats.StatsMode(stats) if stats else None
    stats_stream = sys.stdout if stats_mode is not None else None
    code = d.run(
        file,
        error_stream=sys.stderr,
        stats_stream=stats_stream,
        stats_mode=stats_mode or overall_stats.StatsMode.OVERALL,
    )
    ctx.exit(code)


if __name__ == "__main__":
    main()
