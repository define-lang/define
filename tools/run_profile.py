"""Record a py-spy profile of the Define compiler executable."""

from __future__ import annotations

import contextlib
import enum
import json
import os
import pathlib
import shutil
import subprocess
import tempfile
import time
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


class ProfileMode(enum.StrEnum):
    """Measurement emphasized by the profile capture."""

    WALL = "wall"
    CPU = "cpu"


def _workspace() -> pathlib.Path:
    workspace = os.environ.get("BUILD_WORKSPACE_DIRECTORY")
    if workspace is not None:
        return pathlib.Path(workspace)
    return pathlib.Path(__file__).resolve().parent.parent


def _build_compiler(workspace: pathlib.Path) -> None:
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


def record_profile(
    py_spy_command: tuple[str, ...],
    compiler_path: pathlib.Path,
    compiler_input: pathlib.Path | None,
    source_path: pathlib.Path | None,
    compiler_working_directory: pathlib.Path,
    out_path: pathlib.Path,
    max_threads: int,
    output_dir: pathlib.Path,
    profile_mode: ProfileMode,
) -> None:
    """Record one compiler invocation under py-spy."""
    command = [
        *py_spy_command,
        "record",
        "--format",
        "chrometrace" if profile_mode is ProfileMode.WALL else "raw",
        "--full-filenames",
    ]
    if profile_mode is ProfileMode.WALL:
        command.append("--idle")
    # TODO: Reconsider native frames after py-spy PR #831 is released; its
    # Python 3.14 frame-owner bug currently corrupts merged stacks.
    with contextlib.ExitStack() as contexts:
        py_spy_output = out_path
        if profile_mode is ProfileMode.CPU:
            py_spy_output = (
                pathlib.Path(
                    contexts.enter_context(
                        tempfile.TemporaryDirectory(prefix="define_profile_")
                    )
                )
                / "samples.txt"
            )
        command.extend(
            [
                "--output",
                str(py_spy_output),
                "--",
            ]
        )
        command.append(str(compiler_path))
        command.extend(
            [
                "compile",
                "--out",
                str(output_dir),
                "--max-threads",
                str(max_threads),
            ]
        )
        if compiler_input is not None:
            command.append(str(compiler_input))
        environment = os.environ.copy()
        for variable in _INHERITED_RUNTIME_VARIABLES:
            _ = environment.pop(variable, None)
        source_stream = (
            contexts.enter_context(source_path.open("rb"))
            if source_path is not None
            else None
        )
        started = time.monotonic()
        completed = subprocess.run(
            command,
            check=False,
            cwd=compiler_working_directory,
            env=environment,
            stdin=source_stream,
        )
        wall_time = time.monotonic() - started
        if profile_mode is ProfileMode.CPU and py_spy_output.exists():
            profile = {
                "wall_time_seconds": wall_time,
                "raw_samples": py_spy_output.read_text(encoding="utf-8"),
            }
            _ = out_path.write_text(json.dumps(profile), encoding="utf-8")
        completed.check_returncode()


@click.command(
    epilog=(
        "The profile mode must match the mode later passed to analyze_profile. "
        "Wall mode records idle time and all Python threads for critical-path "
        "analysis. CPU mode records active work across Python threads.\n\n"
        "Examples:\n\n"
        "  run_profile --source SOURCE --out PROFILE\n\n"
        "  run_profile --project PROJECT --out PROFILE\n\n"
        "  run_profile --source SOURCE --out CPU_PROFILE --profile-mode cpu\n\n"
        "  run_profile --source SOURCE --out PARALLEL_PROFILE "
        "--profile-mode cpu --max-threads 4\n\n"
        "Wall mode records a Chrome trace. CPU mode records active raw samples "
        "plus the profiled wall duration. Generated code goes to a temporary "
        "directory unless --output-dir is provided."
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
    help="Destination profile: Chrome trace in wall mode, JSON in CPU mode.",
)
@click.option(
    "--max-threads",
    type=click.IntRange(min=1),
    default=1,
    show_default=True,
    help=("Maximum threads used by each validation phase."),
)
@click.option(
    "--profile-mode",
    type=click.Choice([mode.value for mode in ProfileMode]),
    default=ProfileMode.WALL.value,
    show_default=True,
    help=(
        "Capture wall-time critical-path or CPU-time data. Pass the same mode "
        "to analyze_profile."
    ),
)
@click.option(
    "--output-dir",
    type=_PATH,
    help="Codegen directory. Defaults to a throwaway directory.",
)
def main(
    source_path: pathlib.Path | None,
    project: pathlib.Path | None,
    entry: str,
    out_path: pathlib.Path,
    max_threads: int,
    profile_mode: str,
    output_dir: pathlib.Path | None,
):
    """Profile the complete compiler pipeline, including code generation."""
    if (source_path is None) == (project is None):
        raise click.UsageError("provide exactly one of --source or --project")

    workspace = _workspace()
    _build_compiler(workspace)
    out_path = out_path.absolute()
    with contextlib.ExitStack() as contexts:
        if source_path is not None:
            compiler_input = None
            source_path = source_path.absolute()
            compiler_working_directory = workspace
        else:
            compiler_working_directory = typing.cast("pathlib.Path", project).absolute()
            compiler_input = compiler_working_directory / entry

        if output_dir is None:
            output_dir = pathlib.Path(
                contexts.enter_context(
                    tempfile.TemporaryDirectory(prefix="cg_profile_")
                )
            )
        else:
            output_dir = output_dir.absolute()
        selected_profile_mode = ProfileMode(profile_mode)
        record_profile(
            ("uv", "run", "--project", str(workspace), "py-spy"),
            workspace / "bazel-bin/define/compiler/main",
            compiler_input,
            source_path,
            compiler_working_directory,
            out_path,
            max_threads,
            output_dir,
            selected_profile_mode,
        )


if __name__ == "__main__":
    main()
