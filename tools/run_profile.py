"""Run cProfile over the Define compiler compiling a source file or a project.

With ``--source`` this profiles ``driver.compile_source`` — the in-process,
non-filesystem compile path, the same code that ``main compile`` runs when
source is piped on stdin. Profiling in-process (rather than spawning the CLI)
keeps cProfile's view free of process-startup and click-dispatch noise.

With ``--project`` it profiles ``driver.compile_program`` over a whole directory
of files. Both modes include code generation.

Invoke through its Bazel target so generated compiler dependencies and the
profiling interpreter are consistent:

    bazelisk run //tools:run_profile -- \
        --source <file.dfn> --out <file.prof>
"""

from __future__ import annotations

import contextlib
import cProfile
import os
import pathlib
import tempfile

import click

from define.compiler import driver


def _profile_source(
    source_path: pathlib.Path, output_dir: pathlib.Path | None
) -> tuple[cProfile.Profile, bool]:
    """Profile a single-file compile, code generation included.

    Returns the profiler and whether the compile reported errors.
    """
    source = source_path.read_text(encoding="utf-8")

    # A passed --output-dir is left in place; the default throwaway dir is
    # removed once profiling is done so repeated runs don't leak codegen output.
    out_dir_ctx = (
        contextlib.nullcontext(output_dir)
        if output_dir is not None
        else tempfile.TemporaryDirectory(prefix="cg_profile_")
    )
    with out_dir_ctx as out_dir_name:
        out_dir = pathlib.Path(out_dir_name)
        d = driver.Driver()
        profiler = cProfile.Profile()
        profiler.enable()
        result = d.compile_source(source, out_dir)
        profiler.disable()
    return profiler, result.result.has_errors()


def _profile_project(
    project: pathlib.Path,
    entry: str,
    output_dir: pathlib.Path | None,
) -> tuple[cProfile.Profile, bool]:
    """Profile compilation of every file a project's entry file reaches.

    Returns the profiler and whether compilation reported errors.
    """
    os.chdir(project)

    out_dir_ctx = (
        contextlib.nullcontext(output_dir)
        if output_dir is not None
        else tempfile.TemporaryDirectory(prefix="cg_profile_")
    )
    with out_dir_ctx as out_dir_name:
        out_dir = pathlib.Path(out_dir_name)
        d = driver.Driver()
        profiler = cProfile.Profile()
        profiler.enable()
        result = d.compile_program(pathlib.Path(entry), out_dir)
        profiler.disable()
    return profiler, result.result.has_errors()


_PATH = click.Path(path_type=pathlib.Path)


# TODO: Add --max-threads, defaulting to 1, after main.py and Driver expose a
# compiler-wide thread limit. It should control both structural and reference
# graph validation, with higher values available for intentionally profiling
# concurrent compilation.
@click.command(
    epilog=(
        "Examples:\n\n"
        "  run_profile --source SOURCE --out PROFILE\n\n"
        "  run_profile --project PROJECT --out PROFILE\n\n"
        "Both modes compile in process. Generated code goes to a temporary "
        "directory unless --output-dir is provided. Each run reports whether "
        "the compilation had errors and writes a cProfile .prof file."
    )
)
@click.option(
    "--source",
    "source_path",
    type=click.Path(
        path_type=pathlib.Path,
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
    ),
    help="Compile one .dfn file through Driver.compile_source.",
)
@click.option(
    "--project",
    type=click.Path(
        path_type=pathlib.Path,
        exists=True,
        file_okay=False,
        dir_okay=True,
        readable=True,
    ),
    help="Compile a project directory through Driver.compile_program.",
)
@click.option(
    "--entry",
    default="test.dfn",
    show_default=True,
    help="Entry file within --project. Ignored by --source.",
)
@click.option(
    "--out",
    "out_path",
    type=_PATH,
    required=True,
    help="Destination cProfile .prof file.",
)
@click.option(
    "--output-dir",
    type=_PATH,
    help="Codegen output directory. Defaults to a throwaway directory.",
)
def main(
    source_path: pathlib.Path | None,
    project: pathlib.Path | None,
    entry: str,
    out_path: pathlib.Path,
    output_dir: pathlib.Path | None,
):
    """Profile the complete driver pipeline, including code generation.

    Pass exactly one of --source or --project.
    """
    if source_path is not None and project is not None:
        raise click.UsageError("provide exactly one of --source or --project")

    if output_dir is not None:
        output_dir = output_dir.absolute()
    # Resolved before --project can change the working directory out from under it.
    out_path = out_path.absolute()

    if source_path is not None:
        profiler, has_errors = _profile_source(source_path, output_dir)
    elif project is not None:
        profiler, has_errors = _profile_project(project.absolute(), entry, output_dir)
    else:
        raise click.UsageError("provide exactly one of --source or --project")
    profiler.dump_stats(str(out_path))

    # A clean (0-diagnostic) run means the profile reflects the full pipeline;
    # a failed one may have short-circuited and is not comparable.
    click.echo(f"has_errors={has_errors}")
    click.echo(f"profile written to {out_path}")


if __name__ == "__main__":
    main()
