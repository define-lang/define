"""Record a py-spy profile of the Define compiler executable."""

from __future__ import annotations

import contextlib
import os
import pathlib
import shutil
import subprocess
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


def _record_profile(
    workspace: pathlib.Path,
    compiler_input: pathlib.Path | None,
    source_path: pathlib.Path | None,
    compiler_working_directory: pathlib.Path,
    out_path: pathlib.Path,
    max_threads: int,
    output_dir: pathlib.Path,
) -> None:
    uv_path = shutil.which("uv")
    if uv_path is None:
        raise FileNotFoundError("uv is required to run the py-spy dev dependency")

    command = [
        uv_path,
        "run",
        "--project",
        str(workspace),
        "py-spy",
        "record",
        "--format",
        "speedscope",
        "--full-filenames",
        "--output",
        str(out_path),
        "--",
        str(workspace / "bazel-bin/define/compiler/main"),
        "compile",
        "--out",
        str(output_dir),
        "--max-threads",
        str(max_threads),
    ]
    if compiler_input is not None:
        command.append(str(compiler_input))
    environment = os.environ.copy()
    for variable in _INHERITED_RUNTIME_VARIABLES:
        _ = environment.pop(variable, None)
    with contextlib.ExitStack() as contexts:
        source_stream = (
            contexts.enter_context(source_path.open("rb"))
            if source_path is not None
            else None
        )
        _ = subprocess.run(
            command,
            check=True,
            cwd=compiler_working_directory,
            env=environment,
            stdin=source_stream,
        )


@click.command(
    epilog=(
        "Examples:\n\n"
        "  run_profile --source SOURCE --out PROFILE\n\n"
        "  run_profile --project PROJECT --out PROFILE\n\n"
        "Both modes record a speedscope profile through py-spy. Generated code "
        "goes to a temporary directory unless --output-dir is provided."
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
    help="Destination speedscope JSON file.",
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
    help="Codegen directory. Defaults to a throwaway directory.",
)
def main(
    source_path: pathlib.Path | None,
    project: pathlib.Path | None,
    entry: str,
    out_path: pathlib.Path,
    max_threads: int,
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
        _record_profile(
            workspace,
            compiler_input,
            source_path,
            compiler_working_directory,
            out_path,
            max_threads,
            output_dir,
        )


if __name__ == "__main__":
    main()
