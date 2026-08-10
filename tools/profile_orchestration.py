"""Profile the Define compiler through a profiler's public entry point."""

from __future__ import annotations

import contextlib
import dataclasses
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import typing

import click

_PATH = click.Path(path_type=pathlib.Path)
_INHERITED_RUNTIME_VARIABLES = (
    "JAVA_RUNFILES",
    "PYTHON_RUNFILES",
    "RUNFILES_DIR",
    "RUNFILES_MANIFEST_FILE",
    "RUNFILES_MANIFEST_ONLY",
    "VIRTUAL_ENV",
)


@dataclasses.dataclass(frozen=True, slots=True)
class ProfileInvocation:
    """Generic inputs needed to run a target through a profiler command."""

    # PRF-012: Orchestration boundary.
    profiler_command: tuple[str, ...]
    profiler_working_directory: pathlib.Path
    target_command: tuple[str, ...]
    target_working_directory: pathlib.Path
    target_stdin_path: pathlib.Path | None
    workload_path: pathlib.Path
    profile_path: pathlib.Path
    environment: dict[str, str]


def _workspace() -> pathlib.Path:
    # PRF-012: Orchestration boundary.
    workspace = os.environ.get("BUILD_WORKSPACE_DIRECTORY")
    if workspace is not None:
        return pathlib.Path(workspace)
    return pathlib.Path(__file__).resolve().parent.parent


def _build_compiler(workspace: pathlib.Path) -> pathlib.Path:
    # PRF-012: Orchestration boundary.
    bazelisk_path = shutil.which("bazelisk")
    if bazelisk_path is None:
        raise FileNotFoundError("bazelisk is required to build the compiler")
    _ = subprocess.run(
        [
            bazelisk_path,
            "build",
            "--noshow_progress",
            "--ui_event_filters=-info",
            "//define/compiler:main",
        ],
        check=True,
        cwd=workspace,
    )
    return workspace / "bazel-bin/define/compiler/main"


def _target_environment() -> dict[str, str]:
    # PRF-012: Orchestration boundary.
    environment = os.environ.copy()
    for variable in _INHERITED_RUNTIME_VARIABLES:
        _ = environment.pop(variable, None)
    return environment


def record_profile(invocation: ProfileInvocation):
    """Run one prepared compiler invocation through a profiling command."""
    # PRF-012: Orchestration boundary.
    command = [
        *invocation.profiler_command,
        "--profile",
        str(invocation.profile_path),
        "--workload",
        str(invocation.workload_path),
        "--working-directory",
        str(invocation.target_working_directory),
        "--",
        *invocation.target_command,
    ]
    with contextlib.ExitStack() as contexts:
        source_stream = (
            contexts.enter_context(invocation.target_stdin_path.open("rb"))
            if invocation.target_stdin_path is not None
            else None
        )
        completed = subprocess.run(
            command,
            check=False,
            cwd=invocation.profiler_working_directory,
            env=invocation.environment,
            stdin=source_stream,
        )
    completed.check_returncode()


def _profile_invocation(
    *,
    workspace: pathlib.Path,
    compiler_path: pathlib.Path,
    source_path: pathlib.Path | None,
    project: pathlib.Path | None,
    entry: str,
    out_path: pathlib.Path,
    max_threads: int,
    output_dir: pathlib.Path,
) -> ProfileInvocation:
    # PRF-012: Orchestration boundary.
    if source_path is not None:
        workload_path = source_path.absolute()
        target_stdin_path: pathlib.Path | None = workload_path
        target_working_directory = workspace
        compiler_input: pathlib.Path | None = None
    else:
        target_working_directory = typing.cast("pathlib.Path", project).absolute()
        workload_path = target_working_directory / entry
        target_stdin_path = None
        compiler_input = workload_path

    target_command = [
        str(compiler_path),
        "compile",
        "--out",
        str(output_dir),
        "--max-threads",
        str(max_threads),
    ]
    if compiler_input is not None:
        target_command.append(str(compiler_input))
    return ProfileInvocation(
        profiler_command=(sys.executable, "-m", "tools.profiler"),
        profiler_working_directory=workspace,
        target_command=tuple(target_command),
        target_working_directory=target_working_directory,
        target_stdin_path=target_stdin_path,
        workload_path=workload_path,
        profile_path=out_path.absolute(),
        environment=_target_environment(),
    )


# PRF-012: Orchestration boundary. PRF-020: Machine and human interfaces.
@click.command(
    epilog=(
        "Examples:\n\n"
        "  run_profile --source SOURCE --out PROFILE\n\n"
        "  run_profile --project PROJECT --entry main.dfn --out PROFILE\n\n"
        "The profiler records continuous all-thread wall observations. Generated "
        "code goes to a temporary directory unless --output-dir is provided."
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
    help="Destination for the versioned raw wall profile.",
)
@click.option(
    "--max-threads",
    type=click.IntRange(min=1),
    default=1,
    show_default=True,
    help="Maximum threads used by each validation phase.",
)
@click.option(
    "--output-dir",
    type=_PATH,
    help="Code-generation directory. Defaults to a throwaway directory.",
)
def main(
    source_path: pathlib.Path | None,
    project: pathlib.Path | None,
    entry: str,
    out_path: pathlib.Path,
    max_threads: int,
    output_dir: pathlib.Path | None,
):
    """Capture the complete compiler pipeline with the wall profiler."""
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
        else:
            output_dir = output_dir.absolute()
        invocation = _profile_invocation(
            workspace=workspace,
            compiler_path=compiler_path,
            source_path=source_path,
            project=project,
            entry=entry,
            out_path=out_path,
            max_threads=max_threads,
            output_dir=output_dir,
        )
        record_profile(invocation)
