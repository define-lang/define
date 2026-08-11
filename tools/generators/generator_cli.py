"""Click conventions shared by generator commands."""

import os
from collections.abc import Callable
from pathlib import Path

import click

OUTPUT_FILE = click.Path(path_type=Path, dir_okay=False)
OUTPUT_DIRECTORY = click.Path(path_type=Path, file_okay=False)
POSITIVE_INTEGER = click.IntRange(min=1)
NONNEGATIVE_INTEGER = click.IntRange(min=0)
FRACTION = click.FloatRange(min=0, max=1)


def invoke[T](generator: Callable[[], T]) -> T:
    """Invoke a generator, presenting invalid parameters as CLI usage errors."""
    # Bazel runs binaries from their runfiles tree, but CLI paths should remain
    # relative to the workspace from which the user invoked Bazel.
    if workspace := os.environ.get("BUILD_WORKSPACE_DIRECTORY"):
        os.chdir(workspace)
    try:
        return generator()
    except (FileExistsError, ValueError) as error:
        raise click.UsageError(str(error)) from error


def report_written(noun: str, count: int, output: Path):
    """Report the number of generated items and their destination."""
    click.echo(f"Wrote {count:,} {noun} to {output}")
