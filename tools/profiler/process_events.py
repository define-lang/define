"""Linux process events used by blocking profiler capture."""

from __future__ import annotations

import contextlib
import ctypes
import dataclasses
import enum
import os
import select
import signal
import time
import typing

if typing.TYPE_CHECKING:
    import collections.abc
    import subprocess

    from tools.profiler import schema

_PTRACE_CONT = 7
_PTRACE_DETACH = 17
_PTRACE_SEIZE = 0x4206
_PTRACE_INTERRUPT = 0x4207
_PTRACE_O_TRACEEXEC = 0x10
_PTRACE_EVENT_EXEC = 4
_PTRACE_EVENT_STOP = 128

_LIBC = ctypes.CDLL(None, use_errno=True)
_LIBC.ptrace.argtypes = [
    ctypes.c_uint,
    ctypes.c_uint,
    ctypes.c_void_p,
    ctypes.c_void_p,
]
_LIBC.ptrace.restype = ctypes.c_long
_LIBC.pidfd_open.argtypes = [ctypes.c_int, ctypes.c_uint]
_LIBC.pidfd_open.restype = ctypes.c_int


class ExecutableWaitError(Exception):
    """The target did not reach the expected executable."""


class ExecutableWaitTimeoutError(ExecutableWaitError):
    """The target did not reach the expected executable before the deadline."""


class ProcessExitedBeforeExecutableError(ExecutableWaitError):
    """The target exited before reaching the expected executable."""


class ScheduleEvent(enum.Enum):
    """Kernel event that ended a sampling wait."""

    # PRF-049: Event-driven coordination.
    # PRF-051: Schedule-isolated persistence.
    DEADLINE = enum.auto()
    PROCESSOR_FAILED = enum.auto()
    TARGET_EXITED = enum.auto()


@dataclasses.dataclass(slots=True)
class TargetProcess:
    """A launched process and its Linux event handles."""

    # PRF-011: Complete invocation. PRF-049: Event-driven coordination.
    process: subprocess.Popen[str]
    process_file_descriptor: int
    trace_attached: bool
    trace_stopped: bool = False


@dataclasses.dataclass(frozen=True, slots=True)
class ExecutableWaitResult:
    """A matched executable and profiler-induced attachment pause."""

    # PRF-003: Pause exclusion. PRF-021: Version match.
    executable: schema.ExecutableIdentity
    pause_ns: int


@contextlib.contextmanager
def blocked_child_signal() -> collections.abc.Generator[None, None, None]:
    """Reserve child state notifications for synchronous event handling."""
    # PRF-022: Launcher safety. PRF-049: Event-driven coordination.
    previous_mask = signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGCHLD})
    try:
        yield
    finally:
        _ = signal.pthread_sigmask(signal.SIG_SETMASK, previous_mask)


def executable_identity(process_id: int) -> schema.ExecutableIdentity:
    """Read the executable identity currently mapped by a process."""
    # PRF-021: Version match.
    executable_path = os.readlink(f"/proc/{process_id}/exe")
    executable_stat = os.stat(executable_path)
    return {
        "path": executable_path,
        "device": executable_stat.st_dev,
        "inode": executable_stat.st_ino,
    }


def same_executable(
    first: schema.ExecutableIdentity,
    second: schema.ExecutableIdentity,
) -> bool:
    """Compare executable identities by device and inode."""
    # PRF-021: Version match.
    return (first["device"], first["inode"]) == (
        second["device"],
        second["inode"],
    )


def _ptrace(request: int, process_id: int, data: int = 0):
    # PRF-022: Launcher safety. PRF-049: Event-driven coordination.
    result = typing.cast(
        "int",
        _LIBC.ptrace(
            request,
            process_id,
            None,
            ctypes.c_void_p(data),
        ),
    )
    if result == -1:
        error_number = ctypes.get_errno()
        raise OSError(error_number, os.strerror(error_number))


def _pidfd_open(process_id: int) -> int:
    # PRF-049: Event-driven coordination.
    process_file_descriptor = typing.cast("int", _LIBC.pidfd_open(process_id, 0))
    if process_file_descriptor == -1:
        error_number = ctypes.get_errno()
        raise OSError(error_number, os.strerror(error_number))
    return process_file_descriptor


def _record_wait_status(target: subprocess.Popen[str], wait_status: int):
    # PRF-011: Complete invocation. PRF-049: Event-driven coordination.
    target.returncode = os.waitstatus_to_exitcode(wait_status)


def attach_exec_notifications(target: subprocess.Popen[str]) -> TargetProcess:
    """Observe exec and exit events for a newly launched target."""
    # PRF-022: Launcher safety. PRF-049: Event-driven coordination.
    process_file_descriptor = _pidfd_open(target.pid)
    try:
        _ptrace(_PTRACE_SEIZE, target.pid, _PTRACE_O_TRACEEXEC)
        trace_attached = True
    except ProcessLookupError:
        trace_attached = False
    except OSError:
        os.close(process_file_descriptor)
        raise
    return TargetProcess(
        process=target,
        process_file_descriptor=process_file_descriptor,
        trace_attached=trace_attached,
    )


def wait_for_expected_executable(
    target_process: TargetProcess,
    expected_executable: schema.ExecutableIdentity,
    timeout_seconds: float,
) -> ExecutableWaitResult:
    """Wait for an explicit exec event that identifies the target runtime."""
    # PRF-003: Pause exclusion. PRF-021: Version match.
    # PRF-022: Launcher safety. PRF-049: Event-driven coordination.
    deadline = time.monotonic() + timeout_seconds
    pause_ns = 0
    target = target_process.process
    try:
        current_executable = executable_identity(target.pid)
    except FileNotFoundError as error:
        raise ProcessExitedBeforeExecutableError from error
    executable_already_reached = same_executable(
        current_executable,
        expected_executable,
    )
    if executable_already_reached:
        try:
            _ptrace(_PTRACE_INTERRUPT, target.pid)
        except ProcessLookupError as error:
            target_process.trace_attached = False
            raise ProcessExitedBeforeExecutableError from error
    while True:
        remaining_seconds = deadline - time.monotonic()
        if remaining_seconds <= 0:
            raise ExecutableWaitTimeoutError
        child_event = signal.sigtimedwait({signal.SIGCHLD}, remaining_seconds)
        if child_event is None:
            raise ExecutableWaitTimeoutError
        waited_process_id, wait_status = os.waitpid(
            target.pid,
            os.WNOHANG | os.WUNTRACED | os.WCONTINUED,
        )
        if waited_process_id == 0 or os.WIFCONTINUED(wait_status):
            continue
        if os.WIFEXITED(wait_status) or os.WIFSIGNALED(wait_status):
            target_process.trace_attached = False
            _record_wait_status(target, wait_status)
            raise ProcessExitedBeforeExecutableError
        target_process.trace_stopped = True
        pause_started_ns = time.monotonic_ns()
        if executable_already_reached:
            _ptrace(_PTRACE_DETACH, target.pid)
            target_process.trace_attached = False
            target_process.trace_stopped = False
            pause_ns += time.monotonic_ns() - pause_started_ns
            return ExecutableWaitResult(current_executable, pause_ns)
        if wait_status >> 16 == _PTRACE_EVENT_EXEC:
            current_executable = executable_identity(target.pid)
            if same_executable(current_executable, expected_executable):
                _ptrace(_PTRACE_DETACH, target.pid)
                target_process.trace_attached = False
                target_process.trace_stopped = False
                pause_ns += time.monotonic_ns() - pause_started_ns
                return ExecutableWaitResult(current_executable, pause_ns)
        stop_signal = os.WSTOPSIG(wait_status)
        delivered_signal = (
            0
            if wait_status >> 16 in {_PTRACE_EVENT_EXEC, _PTRACE_EVENT_STOP}
            or stop_signal in {signal.SIGSTOP, signal.SIGTRAP}
            else stop_signal
        )
        _ptrace(_PTRACE_CONT, target.pid, delivered_signal)
        target_process.trace_stopped = False
        pause_ns += time.monotonic_ns() - pause_started_ns


def release_exec_notifications(target_process: TargetProcess) -> int:
    """Detach exec tracing and return the resulting stopped time."""
    # PRF-023: Guaranteed resume. PRF-049: Event-driven coordination.
    if not target_process.trace_attached:
        return 0
    target = target_process.process
    if not target_process.trace_stopped:
        try:
            _ptrace(_PTRACE_INTERRUPT, target.pid)
        except ProcessLookupError:
            target_process.trace_attached = False
            return 0
        while True:
            _ = signal.sigwaitinfo({signal.SIGCHLD})
            waited_process_id, wait_status = os.waitpid(
                target.pid,
                os.WNOHANG | os.WUNTRACED,
            )
            if waited_process_id == 0:
                continue
            if os.WIFEXITED(wait_status) or os.WIFSIGNALED(wait_status):
                target_process.trace_attached = False
                _record_wait_status(target, wait_status)
                return 0
            target_process.trace_stopped = True
            break
    pause_started_ns = time.monotonic_ns()
    _ptrace(_PTRACE_DETACH, target.pid)
    target_process.trace_attached = False
    target_process.trace_stopped = False
    return time.monotonic_ns() - pause_started_ns


def arm_schedule(timer_file_descriptor: int, interval_seconds: float):
    """Arm the next sampling deadline."""
    # PRF-002: Independent sampling schedule.
    # PRF-049: Event-driven coordination.
    _ = os.timerfd_settime(timer_file_descriptor, initial=interval_seconds)


def wait_for_schedule(
    target_process: TargetProcess,
    timer_file_descriptor: int,
    processor_failure_file_descriptor: int,
) -> ScheduleEvent:
    """Wait for a sampling deadline, target exit, or processor failure."""
    # PRF-002: Independent sampling schedule.
    # PRF-049: Event-driven coordination.
    # PRF-051: Schedule-isolated persistence.
    readable, _, _ = select.select(
        [
            target_process.process_file_descriptor,
            timer_file_descriptor,
            processor_failure_file_descriptor,
        ],
        [],
        [],
    )
    if processor_failure_file_descriptor in readable:
        return ScheduleEvent.PROCESSOR_FAILED
    if target_process.process_file_descriptor in readable:
        return ScheduleEvent.TARGET_EXITED
    _ = os.read(timer_file_descriptor, 8)
    return ScheduleEvent.DEADLINE
