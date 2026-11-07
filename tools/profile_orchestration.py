"""Build the Define compiler and profile one compilation."""

from __future__ import annotations

import contextlib
import os
import pathlib
import shutil
import subprocess
import tempfile
import typing

import click
import msgspec

from tools.profiler import (
    cpu_stacks,
    perf_access,
    perf_profiler,
    tachyon_profile,
    tachyon_profiler,
)

_PATH = click.Path(path_type=pathlib.Path)
_INHERITED_RUNTIME_VARIABLES = (
    "JAVA_RUNFILES",
    "PYTHON_RUNFILES",
    "RUNFILES_DIR",
    "RUNFILES_MANIFEST_FILE",
    "RUNFILES_MANIFEST_ONLY",
    "VIRTUAL_ENV",
)


class _CompilerInvocation(msgspec.Struct, frozen=True):
    command: tuple[str, ...]
    working_directory: pathlib.Path
    stdin_path: pathlib.Path | None


def chdir_to_build_workspace():
    """Resolve CLI paths from the workspace when invoked through Bazel."""
    if workspace := os.environ.get("BUILD_WORKSPACE_DIRECTORY"):
        os.chdir(workspace)


def _workspace() -> pathlib.Path:
    workspace = os.environ.get("BUILD_WORKSPACE_DIRECTORY")
    if workspace is not None:
        return pathlib.Path(workspace)
    return pathlib.Path(__file__).resolve().parent.parent


def _build_compiler(workspace: pathlib.Path) -> pathlib.Path:
    bazelisk_path = shutil.which("bazelisk")
    if bazelisk_path is None:
        raise FileNotFoundError("bazelisk is required to build the compiler")
    click.echo("Building the compiler with --config=profiling")
    _ = subprocess.run(
        [
            bazelisk_path,
            "build",
            "--config=profiling",
            # The compiler runs from bazel-bin rather than through bazel run,
            # so its runfiles tree must be built even when a bazelrc turns
            # runfiles links off.
            "--build_runfile_links",
            "--noshow_progress",
            "--ui_event_filters=-info",
            "//define/compiler:main",
        ],
        check=True,
        cwd=workspace,
    )
    return workspace / "bazel-bin/define/compiler/main"


def _target_environment() -> dict[str, str]:
    environment = os.environ.copy()
    for variable in _INHERITED_RUNTIME_VARIABLES:
        _ = environment.pop(variable, None)
    return environment


def _compiler_invocation(  # noqa: PLR0913, PLR0917 - The compile command's inputs.
    workspace: pathlib.Path,
    compiler_path: pathlib.Path,
    source_path: pathlib.Path | None,
    project: pathlib.Path | None,
    entry: str,
    output_dir: pathlib.Path,
    max_threads: int,
) -> _CompilerInvocation:
    command = [
        str(compiler_path),
        "compile",
        "--out",
        str(output_dir),
        "--max-threads",
        str(max_threads),
    ]
    if source_path is not None:
        return _CompilerInvocation(
            command=tuple(command),
            working_directory=workspace,
            stdin_path=source_path.absolute(),
        )
    # The command line requires exactly one of a source file and a project.
    project_path = typing.cast("pathlib.Path", project).absolute()
    return _CompilerInvocation(
        command=(*command, str(project_path / entry)),
        working_directory=project_path,
        stdin_path=None,
    )


def _capture(
    profile_mode: str, invocation: _CompilerInvocation, profile_path: pathlib.Path
):
    environment = _target_environment()
    with contextlib.ExitStack() as contexts:
        stdin = (
            None
            if invocation.stdin_path is None
            else contexts.enter_context(invocation.stdin_path.open("rb"))
        )
        if profile_mode == "wall":
            try:
                exit_status = tachyon_profiler.capture(
                    command=invocation.command,
                    profile_path=profile_path,
                    working_directory=invocation.working_directory,
                    environment=environment,
                    stdin=stdin,
                )
            except tachyon_profiler.CaptureError as error:
                raise click.ClickException(str(error)) from error
        else:
            try:
                exit_status = perf_profiler.capture(
                    command=invocation.command,
                    profile_path=profile_path,
                    working_directory=invocation.working_directory,
                    environment=environment,
                    stdin=stdin,
                )
            except (
                OSError,
                subprocess.SubprocessError,
                perf_access.PerfAccessError,
            ) as error:
                raise click.ClickException(str(error)) from error
    click.echo(f"Profile: {profile_path}")
    click.echo(f"Capture: compiler exit {exit_status}")
    if profile_mode == "wall":
        profile = tachyon_profile.load(profile_path)
        click.echo(
            f"Samples: {(profile.ended_ns - profile.started_ns) / 1e9:.2f} s of "
            + f"wall time; {len(profile.samples_by_thread)} threads; failed "
            + f"samples {profile.failed_sample_percent:.1f}%"
        )
    else:
        stacks = cpu_stacks.load(profile_path, native=False)
        cpu_ns = sum(stack.total_ns for stack in stacks.stacks)
        click.echo(
            f"Samples: {cpu_ns / 1e9:.2f} s of CPU time; "
            + f"{len(stacks.thread_names)} threads; stacks not unwound "
            + f"{100 * stacks.truncated_ns / cpu_ns:.1f}%"
        )
    if exit_status != 0:
        raise click.ClickException("profile capture was not successful")


@click.command(
    epilog=(
        "Examples:\n\n"
        "  run_profile --source SOURCE --out PROFILE\n\n"
        "  run_profile --project PROJECT --entry main.dfn --out PROFILE\n\n"
        "Wall mode records all-thread samples with Tachyon, CPython's sampling "
        "profiler. CPU mode records Linux perf CPU samples, including native "
        "frames, as collapsed stacks: one line per distinct stack and thread "
        "with its sample count. Generated code goes to a temporary directory unless "
        "--output-dir is provided.\n\n"
        "Machine setup: CPU mode needs kernel.perf_event_paranoid set to 1 or "
        "lower, for example in a file in /etc/sysctl.d/, and a CPython that "
        "runs with -X perf. It refuses to start without that access and says "
        "how to grant it."
    )
)
@click.option(
    "--mode",
    "profile_mode",
    type=click.Choice(["wall", "cpu"]),
    default="wall",
    show_default=True,
    help="Capture all-thread wall samples or sampled on-CPU time with Linux perf.",
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
    help="Compile one .dfn file.",
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
    help="Compile a project directory.",
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
    help="Destination for Tachyon wall samples or collapsed CPU stacks.",
)
@click.option(
    "--max-threads",
    type=click.IntRange(min=1),
    default=1,
    show_default=True,
    help=(
        "Maximum worker threads for each validation and code-generation phase; "
        "each phase runs its own pool beside the main thread."
    ),
)
@click.option(
    "--output-dir",
    type=_PATH,
    help="Code-generation directory. Defaults to a throwaway directory.",
)
def main(  # noqa: PLR0913, PLR0917 - Click passes the declared command options.
    profile_mode: str,
    source_path: pathlib.Path | None,
    project: pathlib.Path | None,
    entry: str,
    out_path: pathlib.Path,
    max_threads: int,
    output_dir: pathlib.Path | None,
):
    """Capture the complete compiler pipeline with the selected profiler mode."""
    if (source_path is None) == (project is None):
        raise click.UsageError("provide exactly one of --source or --project")

    workspace = _workspace()
    compiler_path = _build_compiler(workspace)
    with contextlib.ExitStack() as contexts:
        if output_dir is None:
            output_dir = pathlib.Path(
                contexts.enter_context(
                    tempfile.TemporaryDirectory(prefix="define_profile_codegen_")
                )
            )
            # Where generated code goes affects the cost of writing it.
            click.echo(f"Generated code directory: {output_dir} (deleted afterward)")
        _capture(
            profile_mode,
            _compiler_invocation(
                workspace,
                compiler_path,
                source_path,
                project,
                entry,
                output_dir.absolute(),
                max_threads,
            ),
            out_path.absolute(),
        )
        generated_files = [path for path in output_dir.rglob("*") if path.is_file()]
        generated_bytes = sum(path.stat().st_size for path in generated_files)
        click.echo(
            f"Generated code: {len(generated_files)} files; "
            + f"{generated_bytes / 1_000_000:.1f} MB"
        )
