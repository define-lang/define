"""Count how many times each function of a Python target starts."""

from __future__ import annotations

import os
import pathlib
import subprocess
import tempfile
import typing

import msgspec

from tools.profiler import call_tree, tachyon_profiler

_TARGET_WRAPPER = pathlib.Path(__file__).with_name("call_count_target.py")


class _FunctionCalls(msgspec.Struct, frozen=True):
    function: str
    filename: str
    calls: int


class _CallCounts(msgspec.Struct, frozen=True):
    calls: list[_FunctionCalls]


def capture(
    *,
    command: tuple[str, ...],
    counts_path: pathlib.Path,
    working_directory: pathlib.Path,
    environment: dict[str, str],
    stdin: typing.BinaryIO | None,
) -> int:
    """Run the target to completion, write its call counts, and return its status."""
    interpreter, script, arguments = tachyon_profiler.interpreter_and_script(
        command, environment
    )
    with tempfile.TemporaryDirectory(prefix="define-calls-") as temporary_directory:
        status_path = pathlib.Path(temporary_directory) / "exit-status"
        _ = subprocess.run(
            (
                interpreter,
                # As the Bazel launcher runs the compiler: without the
                # wrapper's directory or user site-packages on sys.path, and
                # without writing bytecode.
                "-I",
                "-B",
                os.fspath(_TARGET_WRAPPER),
                os.fspath(counts_path),
                os.fspath(status_path),
                script,
                *arguments,
            ),
            cwd=working_directory,
            env=environment,
            stdin=stdin,
            stdout=subprocess.DEVNULL,
            check=False,
        )
        if not status_path.is_file():
            raise tachyon_profiler.CaptureError(
                "the target exited without reporting its exit status"
            )
        return int(status_path.read_text(encoding="utf-8"))


def load(counts_path: pathlib.Path) -> dict[str, int]:
    """Return each function's call count, named as the profiles name functions."""
    counts: dict[str, int] = {}
    loaded = msgspec.json.decode(counts_path.read_bytes(), type=_CallCounts)
    for entry in loaded.calls:
        if call_tree.is_import_machinery(entry.filename):
            continue
        name = call_tree.function_name(entry.function, entry.filename)
        counts[name] = counts.get(name, 0) + entry.calls
    return counts
