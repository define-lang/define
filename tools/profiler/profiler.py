"""Capture one externally inspected all-thread Python stack snapshot."""

from __future__ import annotations

import contextlib
import dataclasses
import hashlib
import json
import os
import pathlib
import platform
import signal
import subprocess
import sys
import sysconfig
import tempfile
import time
import typing
from typing import Protocol, cast

import _remote_debugging  # pyright: ignore[reportMissingImports]
import click

from tools.profiler import schema

if typing.TYPE_CHECKING:
    import collections.abc

_PATH = click.Path(path_type=pathlib.Path)
_ATTACHMENT_POLL_SECONDS = 0.005


# PRF-015: Full stacks. PRF-016: Source identity.
class _RemoteFrame(Protocol):
    filename: str
    funcname: str
    lineno: int


# PRF-013: Wall mode. PRF-015: Full stacks.
class _RemoteThread(Protocol):
    thread_id: int
    frame_info: list[_RemoteFrame]


# PRF-001: No call-correlated wall profiling work.
class _Unwinder(Protocol):
    def get_stack_trace(self) -> object: ...


# PRF-001: No call-correlated wall profiling work.
class _UnwinderConstructor(Protocol):
    def __call__(self, process_id: int, *, all_threads: bool) -> _Unwinder: ...


# PRF-001: No call-correlated wall profiling work.
# PRF-017: No compiler instrumentation.
_REMOTE_UNWINDER = cast(
    "_UnwinderConstructor",
    _remote_debugging.RemoteUnwinder,
)


class _CaptureInterrupted(BaseException):
    # PRF-024: Explicit failures.
    signal_number: int

    def __init__(self, signal_number: int):
        super().__init__(signal_number)
        self.signal_number = signal_number


class _TargetStopError(Exception):
    # PRF-024: Explicit failures.
    pass


class _InvalidStackSnapshotError(Exception):
    # PRF-007: Consistent stack.
    pass


# PRF-024: Explicit failures. PRF-026: No silent partial success.
@dataclasses.dataclass(frozen=True, slots=True)
class _ObservationResult:
    snapshot: schema.Snapshot | None
    python_runtime: schema.PythonRuntime | None
    python_observed_ns: int | None
    counts: schema.ObservationCounts
    interruption_signal: int | None


def _interrupt(_signal_number: int, _current_frame: object) -> None:
    # PRF-024: Explicit failures.
    raise _CaptureInterrupted(_signal_number)


def _sha256(path: pathlib.Path) -> str:
    # PRF-010: Raw-data preservation.
    digest = hashlib.sha256()
    with path.open("rb") as source_file:
        while chunk := source_file.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _executable_identity(process_id: int) -> schema.ExecutableIdentity:
    # PRF-021: Version match.
    executable_path = pathlib.Path(os.readlink(f"/proc/{process_id}/exe"))
    executable_stat = executable_path.stat()
    return {
        "path": str(executable_path),
        "device": executable_stat.st_dev,
        "inode": executable_stat.st_ino,
    }


def _same_executable(
    first: schema.ExecutableIdentity, second: schema.ExecutableIdentity
) -> bool:
    # PRF-021: Version match.
    return (first["device"], first["inode"]) == (
        second["device"],
        second["inode"],
    )


def _thread_states(process_id: int) -> dict[int, str]:
    # PRF-006: Complete-process stop.
    states: dict[int, str] = {}
    task_directory = pathlib.Path(f"/proc/{process_id}/task")
    for thread_directory in task_directory.iterdir():
        status = (thread_directory / "status").read_text(encoding="utf-8")
        state_line = next(
            line for line in status.splitlines() if line.startswith("State:")
        )
        states[int(thread_directory.name)] = state_line.split()[1]
    return states


def _snapshot(
    target: subprocess.Popen[str],
    launched_ns: int,
) -> schema.Snapshot:
    # PRF-003: Pause exclusion.
    # PRF-006: Complete-process stop.
    # PRF-007: Consistent stack.
    # PRF-013: Wall mode.
    # PRF-015: Full stacks. PRF-016: Source identity.
    # PRF-023: Guaranteed resume.
    pause_started_ns = time.monotonic_ns()
    os.kill(target.pid, signal.SIGSTOP)
    waited_process_id, wait_status = os.waitpid(target.pid, os.WUNTRACED)
    if waited_process_id != target.pid or not os.WIFSTOPPED(wait_status):
        raise _TargetStopError("target exited while the profiler was stopping it")
    try:
        states = _thread_states(target.pid)
        if any(state not in {"T", "t"} for state in states.values()):
            raise _TargetStopError("not every target thread reached a stopped state")
        unwinder = _REMOTE_UNWINDER(target.pid, all_threads=True)
        remote_threads = cast("list[_RemoteThread]", unwinder.get_stack_trace())
        threads: list[schema.ThreadSnapshot] = []
        for remote_thread in remote_threads:
            stack = [
                schema.Frame(
                    filename=frame.filename,
                    function=frame.funcname,
                    line=frame.lineno,
                )
                for frame in reversed(remote_thread.frame_info)
            ]
            threads.append(
                {
                    "os_thread_id": remote_thread.thread_id,
                    "stopped_state": states[remote_thread.thread_id],
                    "stack": stack,
                }
            )
        if any(not thread["stack"] for thread in threads):
            raise _InvalidStackSnapshotError(
                "the target returned an empty Python stack"
            )
        if not threads:
            raise _InvalidStackSnapshotError("the target had no readable Python stacks")
    finally:
        os.kill(target.pid, signal.SIGCONT)
    pause_ended_ns = time.monotonic_ns()
    return {
        "host_monotonic_ns": pause_started_ns,
        "target_running_ns": pause_started_ns - launched_ns,
        "pause_started_ns": pause_started_ns,
        "pause_ended_ns": pause_ended_ns,
        "pause_duration_ns": pause_ended_ns - pause_started_ns,
        "process_id": target.pid,
        "threads": threads,
    }


def _record_failure(
    failures: list[schema.FailureRecord], kind: str, reason: str
) -> None:
    # PRF-024: Explicit failures.
    failures.append(
        {"host_monotonic_ns": time.monotonic_ns(), "kind": kind, "reason": reason}
    )


def _terminate_process_group(target: subprocess.Popen[str]) -> int:
    # PRF-026: No silent partial success.
    os.killpg(target.pid, signal.SIGTERM)
    return target.wait()


def _write_profile(profile_path: pathlib.Path, profile: schema.RawProfile) -> None:
    # PRF-020: Machine and human interfaces.
    _ = profile_path.write_text(
        json.dumps(profile, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def _python_runtime(
    executable: schema.ExecutableIdentity,
) -> schema.PythonRuntime:
    # PRF-021: Version match. Exact identity makes local metadata target metadata.
    return {
        "version": platform.python_version(),
        "minor_version": f"{sys.version_info.major}.{sys.version_info.minor}",
        "free_threaded": cast(
            "int | None",
            sysconfig.get_config_var("Py_GIL_DISABLED"),
        )
        == 1,
        "executable": executable,
    }


def _wait_for_python_executable(
    target: subprocess.Popen[str],
    expected_python: schema.ExecutableIdentity,
    attachment_timeout_seconds: float,
    failures: list[schema.FailureRecord],
) -> schema.ExecutableIdentity | None:
    # PRF-021: Version match. PRF-022: Launcher safety.
    attachment_deadline = time.monotonic() + attachment_timeout_seconds
    while target.poll() is None:
        current_executable = _executable_identity(target.pid)
        if _same_executable(current_executable, expected_python):
            return current_executable
        if time.monotonic() >= attachment_deadline:
            _record_failure(
                failures,
                "attachment-timeout",
                "the target did not execute the profiler's Python runtime",
            )
            return None
        time.sleep(_ATTACHMENT_POLL_SECONDS)
    _record_failure(
        failures,
        "target-exited-before-snapshot",
        "the target exited before a valid Python stack was observed",
    )
    return None


def _record_interruption(
    failures: list[schema.FailureRecord], interruption: _CaptureInterrupted
) -> int:
    # PRF-024: Explicit failures.
    _record_failure(
        failures,
        "profiler-interrupted",
        signal.Signals(interruption.signal_number).name,
    )
    return interruption.signal_number


def _observe_target(
    target: subprocess.Popen[str],
    expected_python: schema.ExecutableIdentity,
    launched_ns: int,
    snapshot_delay_seconds: float,
    attachment_timeout_seconds: float,
    failures: list[schema.FailureRecord],
) -> _ObservationResult:
    # PRF-004: No stale-stack reuse.
    # PRF-011: Complete invocation. PRF-024: Explicit failures.
    snapshot: schema.Snapshot | None = None
    runtime: schema.PythonRuntime | None = None
    python_observed_ns: int | None = None
    attempted = 0
    discarded = 0
    missed = 0
    interruption_signal: int | None = None
    try:
        python_executable = _wait_for_python_executable(
            target,
            expected_python,
            attachment_timeout_seconds,
            failures,
        )
        if python_executable is None:
            missed = 1
        else:
            python_observed_ns = time.monotonic_ns()
            runtime = _python_runtime(python_executable)
            delay_deadline = time.monotonic() + snapshot_delay_seconds
            while target.poll() is None and time.monotonic() < delay_deadline:
                time.sleep(_ATTACHMENT_POLL_SECONDS)
            if target.poll() is not None:
                missed = 1
                _record_failure(
                    failures,
                    "target-exited-before-snapshot",
                    "the target exited before a valid Python stack was observed",
                )
            else:
                attempted = 1
                try:
                    snapshot = _snapshot(target, launched_ns)
                except (
                    OSError,
                    RuntimeError,
                    UnicodeDecodeError,
                    _TargetStopError,
                    _InvalidStackSnapshotError,
                ) as error:
                    discarded = 1
                    _record_failure(
                        failures,
                        "stack-observation-failed",
                        f"{type(error).__name__}: {error}",
                    )
    except _CaptureInterrupted as interruption:
        interruption_signal = _record_interruption(failures, interruption)
    successful = 1 if snapshot is not None else 0
    return _ObservationResult(
        snapshot=snapshot,
        python_runtime=runtime,
        python_observed_ns=python_observed_ns,
        counts={
            "attempted": attempted,
            "successful": successful,
            "discarded": discarded,
            "missed": missed,
        },
        interruption_signal=interruption_signal,
    )


def _finish_target(
    target: subprocess.Popen[str],
    observation: _ObservationResult,
    failures: list[schema.FailureRecord],
) -> tuple[int, int | None]:
    # PRF-026: No silent partial success.
    if observation.interruption_signal is not None:
        return _terminate_process_group(target), observation.interruption_signal
    if observation.snapshot is None and target.poll() is None:
        return _terminate_process_group(target), None
    try:
        return target.wait(), None
    except _CaptureInterrupted as interruption:
        interruption_signal = _record_interruption(failures, interruption)
        return _terminate_process_group(target), interruption_signal


@contextlib.contextmanager
def _interruption_handlers() -> collections.abc.Generator[None, None, None]:
    # PRF-024: Explicit failures.
    previous_sigint = signal.signal(signal.SIGINT, _interrupt)
    previous_sigterm = signal.signal(signal.SIGTERM, _interrupt)
    try:
        yield
    finally:
        _ = signal.signal(signal.SIGINT, previous_sigint)
        _ = signal.signal(signal.SIGTERM, previous_sigterm)


def capture(
    *,
    command: tuple[str, ...],
    profile_path: pathlib.Path,
    workload_path: pathlib.Path,
    working_directory: pathlib.Path,
    snapshot_delay_seconds: float,
    attachment_timeout_seconds: float,
) -> schema.RawProfile:
    """Launch a target and capture one blocking all-thread wall snapshot."""
    # PRF-011: Complete invocation. PRF-020: Machine and human interfaces.
    expected_python = _executable_identity(os.getpid())
    failures: list[schema.FailureRecord] = []

    with tempfile.TemporaryFile(mode="w+", encoding="utf-8") as diagnostics_file:
        launched_ns = time.monotonic_ns()
        target = subprocess.Popen(
            command,
            cwd=working_directory,
            stderr=diagnostics_file,
            start_new_session=True,
            text=True,
        )
        launcher_executable = _executable_identity(target.pid)
        with _interruption_handlers():
            observation = _observe_target(
                target,
                expected_python,
                launched_ns,
                snapshot_delay_seconds,
                attachment_timeout_seconds,
                failures,
            )
            compiler_exit_status, interruption_signal = _finish_target(
                target, observation, failures
            )
        exited_ns = time.monotonic_ns()
        _ = diagnostics_file.seek(0)
        diagnostics = diagnostics_file.read()

    if diagnostics:
        _ = sys.stderr.write(diagnostics)
    complete = interruption_signal is None
    counts = observation.counts
    # PRF-026: No silent partial success.
    success = (
        complete
        and counts["successful"] == 1
        and counts["discarded"] == 0
        and counts["missed"] == 0
        and compiler_exit_status == 0
        and not diagnostics
    )
    profile: schema.RawProfile = {
        "schema_version": schema.SCHEMA_VERSION,
        "complete": complete,
        "success": success,
        "command": list(command),
        "working_directory": str(working_directory),
        "workload_path": str(workload_path),
        "workload_sha256": _sha256(workload_path),
        "sampling": {
            "mode": "wall",
            "schedule": "one-snapshot",
            "snapshot_delay_seconds": snapshot_delay_seconds,
            "attachment_timeout_seconds": attachment_timeout_seconds,
        },
        "launcher_executable": launcher_executable,
        "python_runtime": observation.python_runtime,
        "lifecycle": {
            "launched_ns": launched_ns,
            "python_observed_ns": observation.python_observed_ns,
            "exited_ns": exited_ns,
        },
        "snapshot": observation.snapshot,
        "failures": failures,
        "observation_counts": counts,
        "compiler_exit_status": compiler_exit_status,
        "diagnostics_status": "present" if diagnostics else "none",
        "interruption_signal": interruption_signal,
    }
    _write_profile(profile_path, profile)
    return profile


# PRF-020: Machine and human interfaces.
@click.command(
    context_settings={"ignore_unknown_options": True},
    epilog=(
        "Place -- before the target command. The profiler launches the target, "
        "waits for its shell launcher to execute the matching Python 3.14t "
        "runtime, stops every target thread, captures one complete available "
        "Python stack per thread, and resumes the target before waiting for it."
    ),
)
@click.option(
    "--profile",
    "profile_path",
    type=_PATH,
    required=True,
    help="Destination for the versioned raw JSON profile.",
)
@click.option(
    "--workload",
    "workload_path",
    type=click.Path(
        path_type=pathlib.Path,
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
    ),
    required=True,
    help="Workload file whose content digest identifies this capture.",
)
@click.option(
    "--working-directory",
    type=click.Path(
        path_type=pathlib.Path,
        exists=True,
        file_okay=False,
        dir_okay=True,
        readable=True,
    ),
    default=".",
    show_default=True,
    help="Working directory for the target command.",
)
@click.option(
    "--snapshot-delay-seconds",
    type=click.FloatRange(min=0.0),
    default=0.1,
    show_default=True,
    help="Independent delay after the matching Python executable is observed.",
)
@click.option(
    "--attachment-timeout-seconds",
    type=click.FloatRange(min=0.0, min_open=True),
    default=10.0,
    show_default=True,
    help="Maximum time to wait for the launcher to execute matching Python.",
)
@click.argument("command", nargs=-1, type=click.UNPROCESSED, required=True)
def main(
    profile_path: pathlib.Path,
    workload_path: pathlib.Path,
    working_directory: pathlib.Path,
    snapshot_delay_seconds: float,
    attachment_timeout_seconds: float,
    command: tuple[str, ...],
):
    """Capture a blocking wall snapshot of a launched Python target."""
    # PRF-020: Machine and human interfaces.
    profile = capture(
        command=command,
        profile_path=profile_path.absolute(),
        workload_path=workload_path.absolute(),
        working_directory=working_directory.absolute(),
        snapshot_delay_seconds=snapshot_delay_seconds,
        attachment_timeout_seconds=attachment_timeout_seconds,
    )
    if not profile["complete"]:
        raise click.Abort
    if not profile["success"]:
        raise click.ClickException("profile capture was not successful")
