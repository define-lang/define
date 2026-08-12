"""Capture native Linux perf data for Python CPU analysis."""

from __future__ import annotations

import hashlib
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import time
import typing

_BAZEL_PYTHON_ENTRYPOINT_MARKER = "__PEX_PY_BINARY_ENTRYPOINT__"
_BAZEL_PYTHON_EXEC = 'exec "python3" '


class Metadata(typing.TypedDict):
    """Define invocation facts that Linux perf does not record."""

    command: list[str]
    working_directory: str
    workload_path: str
    workload_sha256: str
    started_ns: int
    ended_ns: int
    compiler_exit_status: int


def metadata_path(profile_path: pathlib.Path) -> pathlib.Path:
    """Return the Define metadata sidecar for a native perf data file."""
    return profile_path.with_name(profile_path.name + ".json")


def buildid_path(profile_path: pathlib.Path) -> pathlib.Path:
    """Return the native perf build-ID cache retained with a data file."""
    return profile_path.with_name(profile_path.name + ".buildid")


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
        return command
    if (
        _BAZEL_PYTHON_ENTRYPOINT_MARKER not in launcher
        or _BAZEL_PYTHON_EXEC not in launcher
    ):
        return command
    profiled_launcher = launcher.replace(
        _BAZEL_PYTHON_EXEC,
        _BAZEL_PYTHON_EXEC + "-X perf_jit ",
        1,
    )
    profiled_launcher_path = temporary_directory / "python-launcher"
    _ = profiled_launcher_path.write_text(profiled_launcher, encoding="utf-8")
    profiled_launcher_path.chmod(0o700)
    environment["RUNFILES_DIR"] = os.fspath(
        launcher_path.with_name(launcher_path.name + ".runfiles")
    )
    return (os.fspath(profiled_launcher_path), *command[1:])


def capture(
    *,
    command: tuple[str, ...],
    profile_path: pathlib.Path,
    workload_path: pathlib.Path,
    working_directory: pathlib.Path,
    frequency_hz: int,
) -> Metadata:
    """Run the complete target and retain perf's injected native data file."""
    started_ns = time.monotonic_ns()
    perf_executable = _perf_executable()
    with (
        tempfile.TemporaryDirectory(prefix="define-perf-") as temporary_directory,
        tempfile.TemporaryFile(mode="w+", encoding="utf-8") as diagnostics_file,
        tempfile.TemporaryFile(mode="w+", encoding="utf-8") as inject_file,
    ):
        temporary_directory_path = pathlib.Path(temporary_directory)
        recorded_data_path = temporary_directory_path / "perf.data"
        environment = os.environ.copy()
        environment["PYTHON_PERF_JIT_SUPPORT"] = "1"
        profiled_command = _profiled_command(
            command,
            temporary_directory_path,
            environment,
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
                "dwarf",
                "-k",
                "1",
                "-o",
                os.fspath(recorded_data_path),
                "--",
                *profiled_command,
            ),
            cwd=working_directory,
            env=environment,
            check=False,
            stderr=diagnostics_file,
            text=True,
        )
        target_ended_ns = time.monotonic_ns()
        _ = subprocess.run(
            (
                perf_executable,
                "inject",
                "-i",
                os.fspath(recorded_data_path),
                "--jit",
                "--output",
                os.fspath(profile_path),
            ),
            cwd=temporary_directory_path,
            check=True,
            stderr=inject_file,
            text=True,
        )
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
        jitted_objects: list[str] = []
        for line in buildids.stdout.splitlines():
            fields = line.split(maxsplit=1)
            if len(fields) != 2:
                continue
            object_path = pathlib.Path(fields[1])
            if object_path.name.startswith("jitted-") and object_path.suffix == ".so":
                jitted_objects.append(fields[1])
        _ = subprocess.run(
            (
                perf_executable,
                "--buildid-dir",
                os.fspath(buildid_path(profile_path)),
                "buildid-cache",
                "--add",
                ",".join(jitted_objects),
            ),
            check=True,
            capture_output=True,
            text=True,
        )
        _ = diagnostics_file.seek(0)
        diagnostics = diagnostics_file.read()
        _ = inject_file.seek(0)
        inject_diagnostics = inject_file.read() + buildids.stderr

    _ = diagnostics_path(profile_path).write_text(diagnostics, encoding="utf-8")
    _ = profile_path.with_name(profile_path.name + ".inject.stderr").write_text(
        inject_diagnostics, encoding="utf-8"
    )
    metadata: Metadata = {
        "command": list(command),
        "working_directory": os.fspath(working_directory),
        "workload_path": os.fspath(workload_path),
        "workload_sha256": _sha256(workload_path),
        "started_ns": started_ns,
        "ended_ns": target_ended_ns,
        "compiler_exit_status": completed.returncode,
    }
    _ = metadata_path(profile_path).write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if diagnostics:
        _ = sys.stderr.write(diagnostics)
    return metadata
