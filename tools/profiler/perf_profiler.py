"""Capture native Linux perf data for Python CPU analysis."""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import pathlib
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
import typing

_BAZEL_PYTHON_ENTRYPOINT_MARKER = "__PEX_PY_BINARY_ENTRYPOINT__"
_BAZEL_PYTHON_EXEC = 'exec "python3" '
# CPython and perf require this fixed exchange path rather than TMPDIR.
_PERF_MAP_DIRECTORY = pathlib.Path("/tmp")  # noqa: S108


class Metadata(typing.TypedDict):
    """Define invocation facts that Linux perf does not record."""

    command: list[str]
    working_directory: str
    workload_path: str
    workload_sha256: str
    started_ns: int
    ended_ns: int
    compiler_exit_status: int
    target_pid: int


def metadata_path(profile_path: pathlib.Path) -> pathlib.Path:
    """Return the Define metadata sidecar for a native perf data file."""
    return profile_path.with_name(profile_path.name + ".json")


def buildid_path(profile_path: pathlib.Path) -> pathlib.Path:
    """Return the native perf build-ID cache retained with a data file."""
    return profile_path.with_name(profile_path.name + ".buildid")


def python_map_path(profile_path: pathlib.Path) -> pathlib.Path:
    """Return the retained CPython perf symbol map for a data file."""
    return profile_path.with_name(profile_path.name + ".map")


def runtime_python_map_path(target_pid: int) -> pathlib.Path:
    """Return the path from which perf resolves one process's Python symbols."""
    return _PERF_MAP_DIRECTORY / f"perf-{target_pid}.map"


def diagnostics_path(profile_path: pathlib.Path) -> pathlib.Path:
    """Return the target diagnostics retained with a perf data file."""
    return profile_path.with_name(profile_path.name + ".stderr")


def _perf_executable() -> str:
    executable = shutil.which("perf")
    if executable is None:
        raise FileNotFoundError("Linux perf is not installed or not on PATH")
    return executable


def _sha256(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source_file:
        while chunk := source_file.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _profiled_command(
    command: tuple[str, ...],
    temporary_directory: pathlib.Path,
    environment: dict[str, str],
) -> tuple[str, ...]:
    launcher_path = pathlib.Path(command[0])
    try:
        launcher = launcher_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        runfiles_directory = environment.get("RUNFILES_DIR")
        launcher_runfile: pathlib.Path | None = None
        if runfiles_directory is None:
            runfiles_path = launcher_path.with_name(launcher_path.name + ".runfiles")
            try:
                bazel_bin_index = launcher_path.parts.index("bazel-bin")
            except ValueError:
                pass
            else:
                launcher_runfile = pathlib.Path("_main").joinpath(
                    *launcher_path.parts[bazel_bin_index + 1 :]
                )
        else:
            runfiles_path = pathlib.Path(runfiles_directory)
            with contextlib.suppress(ValueError):
                launcher_runfile = launcher_path.relative_to(runfiles_path)
        if launcher_runfile is not None:
            interpreter = (
                runfiles_path
                / launcher_runfile.parent
                / f"._{launcher_path.name}.venv/bin/python"
            )
            main = runfiles_path / launcher_runfile.with_suffix(".py")
            if interpreter.is_file() and main.is_file():
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
    _ = profiled_launcher_path.write_text(profiled_launcher, encoding="utf-8")
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
    )
    target_launcher_path.chmod(0o700)
    return (os.fspath(target_launcher_path), *command), target_pid_path


def _native_objects(
    buildid_output: str, runtime_map_path: pathlib.Path
) -> tuple[bool, list[str]]:
    recorded_python_map = False
    native_objects: list[str] = []
    for line in buildid_output.splitlines():
        fields = line.split(maxsplit=1)
        if fields == [os.fspath(runtime_map_path)]:
            recorded_python_map = True
            continue
        if len(fields) != 2:
            continue
        object_path = pathlib.Path(fields[1])
        if object_path.is_file():
            native_objects.append(fields[1])
    return recorded_python_map, native_objects


def _retain_native_objects(
    perf_executable: str,
    profile_path: pathlib.Path,
    native_objects: list[str],
):
    retained_buildid_path = buildid_path(profile_path)
    if retained_buildid_path.exists():
        shutil.rmtree(retained_buildid_path)
    retained_buildid_path.mkdir()
    if not native_objects:
        return
    _ = subprocess.run(
        (
            perf_executable,
            "--buildid-dir",
            os.fspath(retained_buildid_path),
            "buildid-cache",
            "--add",
            ",".join(native_objects),
        ),
        check=True,
        capture_output=True,
        text=True,
    )


def capture(
    *,
    command: tuple[str, ...],
    profile_path: pathlib.Path,
    workload_path: pathlib.Path,
    working_directory: pathlib.Path,
    frequency_hz: int,
) -> Metadata:
    """Run the complete target and retain perf data with its Python symbol map."""
    started_ns = time.monotonic_ns()
    perf_executable = _perf_executable()
    with (
        tempfile.TemporaryDirectory(prefix="define-perf-") as temporary_directory,
        tempfile.TemporaryFile(mode="w+", encoding="utf-8") as diagnostics_file,
    ):
        temporary_directory_path = pathlib.Path(temporary_directory)
        recorded_data_path = temporary_directory_path / "perf.data"
        environment = os.environ.copy()
        environment["PYTHONPERFSUPPORT"] = "1"
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
                str(frequency_hz),
                "-g",
                "--call-graph",
                "fp",
                "-o",
                os.fspath(recorded_data_path),
                "--",
                *target_command,
            ),
            cwd=working_directory,
            env=environment,
            check=False,
            stderr=diagnostics_file,
            text=True,
        )
        target_ended_ns = time.monotonic_ns()
        _ = diagnostics_file.seek(0)
        diagnostics = diagnostics_file.read()
        if not target_pid_path.is_file():
            diagnostic = diagnostics.strip()
            if diagnostic:
                raise RuntimeError("perf could not launch the target:\n" + diagnostic)
            raise RuntimeError(
                "perf record exited with status "
                + f"{completed.returncode} before launching the target"
            )
        target_pid = int(target_pid_path.read_text(encoding="utf-8"))
        runtime_map_path = runtime_python_map_path(target_pid)
        if not runtime_map_path.is_file() or runtime_map_path.stat().st_size == 0:
            raise RuntimeError(
                "CPython did not create its perf symbol map; "
                + "the target must support -X perf"
            )
        _ = shutil.copy2(runtime_map_path, python_map_path(profile_path))
        runtime_map_path.unlink()
        _ = shutil.move(recorded_data_path, profile_path)
        buildids = subprocess.run(
            (
                perf_executable,
                "buildid-list",
                "-i",
                os.fspath(profile_path),
                "--with-hits",
            ),
            check=True,
            capture_output=True,
            text=True,
        )
        recorded_python_map, native_objects = _native_objects(
            buildids.stdout, runtime_map_path
        )
        if not recorded_python_map:
            raise RuntimeError("perf data does not reference the target's Python map")
        _retain_native_objects(perf_executable, profile_path, native_objects)

    _ = diagnostics_path(profile_path).write_text(diagnostics, encoding="utf-8")
    profile_path.with_name(profile_path.name + ".inject.stderr").unlink(missing_ok=True)
    metadata: Metadata = {
        "command": list(command),
        "working_directory": os.fspath(working_directory),
        "workload_path": os.fspath(workload_path),
        "workload_sha256": _sha256(workload_path),
        "started_ns": started_ns,
        "ended_ns": target_ended_ns,
        "compiler_exit_status": completed.returncode,
        "target_pid": target_pid,
    }
    _ = metadata_path(profile_path).write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if diagnostics:
        _ = sys.stderr.write(diagnostics)
    return metadata
