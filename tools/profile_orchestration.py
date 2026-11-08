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
    call_counter,
    cpu_stacks,
    perf_access,
    perf_profiler,
    python_target,
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


class CompilerInvocation(msgspec.Struct, frozen=True):
    """A compile command and where it runs."""

    command: tuple[str, ...]
    working_directory: pathlib.Path
    stdin_path: pathlib.Path | None


def chdir_to_build_workspace():
    """Resolve CLI paths from the workspace when invoked through Bazel."""
    if workspace := os.environ.get("BUILD_WORKSPACE_DIRECTORY"):
        os.chdir(workspace)


def workspace_path() -> pathlib.Path:
    """Return the checkout this tool runs from."""
    workspace = os.environ.get("BUILD_WORKSPACE_DIRECTORY")
    if workspace is not None:
        return pathlib.Path(workspace)
    return pathlib.Path(__file__).resolve().parent.parent


def build_compiler(workspace: pathlib.Path) -> pathlib.Path:
    """Build the checkout's compiler for profiling and return its launcher."""
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
    launcher = workspace / "bazel-bin/define/compiler/main"
    _precompile_bytecode(launcher)
    return launcher


def _precompile_bytecode(launcher: pathlib.Path):
    # The launcher runs Python with -B, so a runfiles tree that lacks bytecode
    # recompiles every module on every run, and two checkouts compare unevenly.
    entry_point = python_target.bazel_entry_point(launcher, target_environment())
    if entry_point is None:
        raise ValueError(f"{launcher} is not a Bazel Python launcher")
    interpreter, _ = entry_point
    runfiles = launcher.with_name(launcher.name + ".runfiles")
    directories = [
        os.fspath(directory)
        for directory in sorted(runfiles.iterdir())
        # The interpreter ships its standard library's bytecode.
        if directory.is_dir() and "python_interpreters" not in directory.name
    ]
    _ = subprocess.run(
        [
            os.fspath(interpreter),
            "-I",
            "-m",
            "compileall",
            "-q",
            "-j",
            "0",
            *directories,
        ],
        check=True,
        stdout=subprocess.DEVNULL,
    )


def target_environment() -> dict[str, str]:
    """Return this process's environment without its own runfiles settings."""
    environment = os.environ.copy()
    for variable in _INHERITED_RUNTIME_VARIABLES:
        _ = environment.pop(variable, None)
    return environment


def compiler_invocation(  # noqa: PLR0913, PLR0917 - The compile command's inputs.
    workspace: pathlib.Path,
    compiler_path: pathlib.Path,
    source_path: pathlib.Path | None,
    project: pathlib.Path | None,
    entry: str,
    output_dir: pathlib.Path,
    max_threads: int | None,
) -> CompilerInvocation:
    """Return the command that compiles a source file or a project."""
    command = [str(compiler_path), "compile", "--out", str(output_dir)]
    if max_threads is not None:
        command += ["--max-threads", str(max_threads)]
    if source_path is not None:
        return CompilerInvocation(
            command=tuple(command),
            working_directory=workspace,
            stdin_path=source_path.absolute(),
        )
    # The command line requires exactly one of a source file and a project.
    project_path = typing.cast("pathlib.Path", project).absolute()
    return CompilerInvocation(
        command=(*command, str(project_path / entry)),
        working_directory=project_path,
        stdin_path=None,
    )


def _capture(
    profile_mode: str,
    invocation: CompilerInvocation,
    profile_path: pathlib.Path,
):
    environment = target_environment()
    with contextlib.ExitStack() as contexts:
        stdin = (
            None
            if invocation.stdin_path is None
            else contexts.enter_context(invocation.stdin_path.open("rb"))
        )
        if profile_mode == "calls":
            try:
                exit_status = call_counter.capture(
                    command=invocation.command,
                    counts_path=profile_path,
                    working_directory=invocation.working_directory,
                    environment=environment,
                    stdin=stdin,
                )
            except tachyon_profiler.CaptureError as error:
                raise click.ClickException(str(error)) from error
        elif profile_mode == "wall":
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
    if profile_mode == "calls":
        calls = call_counter.load(profile_path)
        click.echo(f"Calls: {sum(calls.values()):,} calls of {len(calls):,} functions")
    elif profile_mode == "wall":
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
        "with its sample count. Calls mode counts every Python function call "
        "on every thread, which slows the compile, so its times mean nothing. "
        "Generated code goes to a temporary directory unless --output-dir is "
        "provided.\n\n"
        "Machine setup: CPU mode needs kernel.perf_event_paranoid set to 1 or "
        "lower, for example in a file in /etc/sysctl.d/, and a CPython that "
        "runs with -X perf. It refuses to start without that access and says "
        "how to grant it. perf cuts stacks deeper than "
        "kernel.perf_event_max_stack frames, 127 by default; raising it, such "
        "as to 1024, unwinds deep compiler stacks."
    )
)
@click.option(
    "--mode",
    "profile_mode",
    type=click.Choice(["wall", "cpu", "calls"]),
    default="wall",
    show_default=True,
    help=(
        "Capture all-thread wall samples, sampled on-CPU time with Linux perf, "
        + "or exact call counts."
    ),
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
    help="Destination for Tachyon wall samples, collapsed CPU stacks, or call counts.",
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

    workspace = workspace_path()
    compiler_path = build_compiler(workspace)
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
            compiler_invocation(
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
