"""Capture all-thread wall samples of a Python target with Tachyon."""

from __future__ import annotations

import os
import pathlib
import subprocess
import tempfile
import typing

from tools.profiler import python_target

_TARGET_WRAPPER = pathlib.Path(__file__).with_name("tachyon_target.py")
# A rate that is not a round number does not stay in step with periodic work.
SAMPLING_FREQUENCY_HZ = 997


class CaptureError(Exception):
    """Raised when Tachyon could not capture the target."""


def _interpreter_and_script(
    command: tuple[str, ...], environment: dict[str, str]
) -> tuple[str, str, tuple[str, ...]]:
    entry_point = python_target.bazel_entry_point(pathlib.Path(command[0]), environment)
    if entry_point is not None:
        interpreter, main = entry_point
        return os.fspath(interpreter), os.fspath(main), command[1:]
    if len(command) < 2:
        raise CaptureError(
            "the command must be a Bazel Python binary or a Python interpreter "
            + "followed by a script"
        )
    return command[0], command[1], command[2:]


def capture(
    *,
    command: tuple[str, ...],
    profile_path: pathlib.Path,
    working_directory: pathlib.Path,
    environment: dict[str, str],
    stdin: typing.BinaryIO | None,
) -> int:
    """Profile the target until it exits and return its exit status."""
    interpreter, script, arguments = _interpreter_and_script(command, environment)
    with tempfile.TemporaryDirectory(prefix="define-tachyon-") as temporary_directory:
        status_path = pathlib.Path(temporary_directory) / "exit-status"
        completed = subprocess.run(
            (
                interpreter,
                "-m",
                "profiling.sampling",
                "run",
                # Stop every thread for each sample so that its stacks are
                # consistent with one another.
                "--blocking",
                "--all-threads",
                "--binary",
                # CPython on Windows cannot read zstd, so a profile captured on
                # Linux, such as a checked-in test profile, must not use it.
                "--compression",
                "none",
                "-o",
                os.fspath(profile_path),
                "--sampling-rate",
                str(SAMPLING_FREQUENCY_HZ),
                os.fspath(_TARGET_WRAPPER),
                os.fspath(status_path),
                script,
                *arguments,
            ),
            cwd=working_directory,
            env=environment,
            stdin=stdin,
            # Tachyon reports sample counts that count differently from the
            # analyzer's, and the compiler writes nothing to stdout.
            stdout=subprocess.DEVNULL,
            check=False,
        )
        if completed.returncode != 0:
            raise CaptureError(f"Tachyon exited with status {completed.returncode}")
        if not status_path.is_file():
            raise CaptureError("the target exited without reporting its exit status")
        return int(status_path.read_text(encoding="utf-8"))
