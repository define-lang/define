"""Run cProfile over the Define compiler compiling a source file or a project.

With ``--source`` this profiles ``driver.compile_source`` — the in-process,
non-filesystem compile path, the same code that ``main compile`` runs when
source is piped on stdin. Profiling in-process (rather than spawning the CLI)
keeps cProfile's view free of process-startup and click-dispatch noise.

With ``--project`` it profiles a whole directory of files through
``validate_program`` instead, for source shapes whose entry point is a position
rather than a constructor action.

Requires the repo root on PYTHONPATH so ``define.compiler`` imports resolve, and
that ``uv run tools/setup_local_dev.py`` has been run at least once. Invoke as:

    PYTHONPATH=<repo-root> uv run python tools/run_profile.py \
        --source <file.dfn> --out <file.prof>
"""

from __future__ import annotations

import argparse
import contextlib
import cProfile
import os
import pathlib
import tempfile
from typing import cast

from define.compiler import driver
from define.compiler.validator.reference_graph import reference_graph_validator
from define.compiler.validator.structural import program_validator


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
    project: pathlib.Path, entry: str
) -> tuple[cProfile.Profile, bool]:
    """Profile every file a project's entry file reaches, code generation aside.

    Code generation is skipped because a project's entry point can be a
    position rather than a constructor action.

    Returns the profiler and whether validation reported errors.
    """
    os.chdir(project)

    profiler = cProfile.Profile()
    profiler.enable()
    # Structural validation runs files on a thread pool. cProfile is built on
    # sys.monitoring, whose profiler tool is process-global, so a single
    # profiler already sees the worker threads — but two threads interleaving
    # into its shared call stack would scramble the timings. Pinning the pool to
    # one worker also keeps these numbers comparable with --source profiles.
    structural = program_validator.ProgramStructuralValidator().validate_program(
        path=pathlib.PurePosixPath(entry), max_workers=1
    )
    _ = reference_graph_validator.ReferenceGraphValidator(
        structural.reference_graph, structural.definition_results
    ).validate()
    profiler.disable()
    return profiler, structural.has_errors()


def main() -> None:
    """Parse arguments, profile the compile, and write the .prof file."""
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    _ = mode.add_argument(
        "--source", type=pathlib.Path, help="Single .dfn file to compile."
    )
    _ = mode.add_argument(
        "--project", type=pathlib.Path, help="Project root directory to validate."
    )
    _ = parser.add_argument(
        "--entry",
        default="test.dfn",
        help="Entry file within --project (default: test.dfn).",
    )
    _ = parser.add_argument("--out", type=pathlib.Path, required=True)
    _ = parser.add_argument(
        "--output-dir",
        type=pathlib.Path,
        default=None,
        help="Codegen output dir for --source (defaults to a throwaway temp dir).",
    )
    args = parser.parse_args()
    source_path = cast("pathlib.Path | None", args.source)
    entry = cast("str", args.entry)
    output_dir = cast("pathlib.Path | None", args.output_dir)
    # Resolved before --project can change the working directory out from under it.
    out_path = cast("pathlib.Path", args.out).absolute()

    if source_path is not None:
        profiler, has_errors = _profile_source(source_path, output_dir)
    else:
        project_path = cast("pathlib.Path", args.project)
        profiler, has_errors = _profile_project(project_path.absolute(), entry)
    profiler.dump_stats(str(out_path))

    # A clean (0-diagnostic) run means the profile reflects the full pipeline;
    # a failed one may have short-circuited and is not comparable.
    print(f"has_errors={has_errors}")
    print(f"profile written to {out_path}")


if __name__ == "__main__":
    main()
