"""Capture Linux perf CPU samples as symbolized collapsed stacks."""

from __future__ import annotations

import os
import pathlib
import shlex
import subprocess
import tempfile
import typing

from tools.profiler import cpu_stacks, perf_access, python_target

_BAZEL_PYTHON_ENTRYPOINT_MARKER = "__PEX_PY_BINARY_ENTRYPOINT__"
_BAZEL_PYTHON_EXEC = 'exec "python3" '
# CPython and perf require this fixed exchange path rather than TMPDIR.
_PERF_MAP_DIRECTORY = pathlib.Path("/tmp")  # noqa: S108
# perf's default ring buffer for unprivileged users takes the user's entire
# perf_event_mlock_kb budget, so any concurrent perf record by the same user
# fails to start. Smaller buffers let concurrent sessions share that budget.
RING_BUFFER_PAGES = 32


def runtime_python_map_path(target_pid: int) -> pathlib.Path:
    """Return the path from which perf resolves one process's Python symbols."""
    return _PERF_MAP_DIRECTORY / f"perf-{target_pid}.map"


def _profiled_command(
    command: tuple[str, ...],
    temporary_directory: pathlib.Path,
    environment: dict[str, str],
) -> tuple[str, ...]:
    launcher_path = pathlib.Path(command[0])
    try:
        launcher = launcher_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        entry_point = python_target.bazel_entry_point(launcher_path, environment)
        if entry_point is not None:
            interpreter, main = entry_point
            return (
                os.fspath(interpreter),
                "-X",
                "perf",
                "-B",
                "-I",
                os.fspath(main),
                *command[1:],
            )
        return command
    if (
        _BAZEL_PYTHON_ENTRYPOINT_MARKER not in launcher
        or _BAZEL_PYTHON_EXEC not in launcher
    ):
        return command
    profiled_launcher = launcher.replace(
        _BAZEL_PYTHON_EXEC,
        _BAZEL_PYTHON_EXEC + "-X perf ",
        1,
    )
    profiled_launcher_path = temporary_directory / "python-launcher"
    _ = profiled_launcher_path.write_text(
        profiled_launcher, encoding="utf-8", newline="\n"
    )
    profiled_launcher_path.chmod(0o700)
    environment["RUNFILES_DIR"] = os.fspath(
        launcher_path.with_name(launcher_path.name + ".runfiles")
    )
    return (os.fspath(profiled_launcher_path), *command[1:])


def _target_command(
    command: tuple[str, ...], temporary_directory: pathlib.Path
) -> tuple[tuple[str, ...], pathlib.Path]:
    target_pid_path = temporary_directory / "target.pid"
    target_launcher_path = temporary_directory / "target-launcher"
    # The launcher owns this PID, so any preexisting map is necessarily stale.
    _ = target_launcher_path.write_text(
        "#!/bin/sh\n"
        + "printf '%s\\n' \"$$\" > "
        + shlex.quote(os.fspath(target_pid_path))
        + '\nrm -f "/tmp/perf-$$.map"\nexec "$@"\n',
        encoding="utf-8",
        newline="\n",
    )
    target_launcher_path.chmod(0o700)
    return (os.fspath(target_launcher_path), *command), target_pid_path


def _write_collapsed_stacks(
    perf_executable: str, recorded_data_path: pathlib.Path, profile_path: pathlib.Path
):
    exec_path = subprocess.run(
        (perf_executable, "--exec-path"),
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    with profile_path.open("w", encoding="utf-8", newline="\n") as profile_file:
        _ = subprocess.run(
            (
                perf_executable,
                "script",
                # Inline frames come from DWARF, which is slow to read and in
                # which perf finds many harmless faults to warn about.
                "--no-inline",
                "-i",
                os.fspath(recorded_data_path),
                "-s",
                os.fspath(pathlib.Path(exec_path) / "scripts/python/stackcollapse.py"),
                "--",
                "--include-pid",
                "--include-tid",
            ),
            check=True,
            stdout=profile_file,
        )


def capture(
    *,
    command: tuple[str, ...],
    profile_path: pathlib.Path,
    working_directory: pathlib.Path,
    environment: dict[str, str],
    stdin: typing.BinaryIO | None,
) -> int:
    """Run the complete target and write its symbolized CPU stacks.

    Each line of the profile is one distinct stack, from the thread's name and
    ID through native and `py::` frames, followed by its sample count.
    """
    perf_access.require_cpu_access()
    perf_executable = perf_access.perf_executable()
    with tempfile.TemporaryDirectory(prefix="define-perf-") as temporary_directory:
        temporary_directory_path = pathlib.Path(temporary_directory)
        recorded_data_path = temporary_directory_path / "perf.data"
        environment = {**environment, "PYTHONPERFSUPPORT": "1"}
        profiled_command = _profiled_command(
            command,
            temporary_directory_path,
            environment,
        )
        target_command, target_pid_path = _target_command(
            profiled_command, temporary_directory_path
        )
        completed = subprocess.run(
            (
                perf_executable,
                "record",
                "-q",
                "-e",
                "cpu-clock",
                "-F",
                str(cpu_stacks.SAMPLING_FREQUENCY_HZ),
                "-g",
                "--call-graph",
                "fp",
                "-m",
                str(RING_BUFFER_PAGES),
                "-o",
                os.fspath(recorded_data_path),
                "--",
                *target_command,
            ),
            cwd=working_directory,
            env=environment,
            stdin=stdin,
            check=False,
        )
        if not target_pid_path.is_file():
            raise RuntimeError(
                "perf record exited with status "
                + f"{completed.returncode} before launching the target"
            )
        runtime_map_path = runtime_python_map_path(
            int(target_pid_path.read_text(encoding="utf-8"))
        )
        if not runtime_map_path.is_file() or runtime_map_path.stat().st_size == 0:
            raise RuntimeError(
                "CPython did not create its perf symbol map; "
                + "the target must support -X perf"
            )
        # perf names Python frames from the map only while it is in place.
        try:
            _write_collapsed_stacks(perf_executable, recorded_data_path, profile_path)
        finally:
            runtime_map_path.unlink()
    return completed.returncode
