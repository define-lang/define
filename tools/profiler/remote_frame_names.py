"""Resolve invocation-specific names from a stopped remote CPython process."""

from __future__ import annotations

import ctypes
import dataclasses
import os
import pathlib
import typing
from typing import Protocol, cast

_DATACLASS_CONSTRUCTOR = "__create_fn__.<locals>.__init__"
_DEBUG_OFFSETS_SIZE = 448
_POINTER_SIZE = 8


class RemoteFrame(Protocol):
    """Describe a Python frame returned by the remote unwinder."""

    filename: str
    funcname: str
    lineno: int


class RemoteThread(Protocol):
    """Describe a Python thread returned by the remote unwinder."""

    thread_id: int
    frame_info: list[RemoteFrame]


class RemoteUnwinder(Protocol):
    """Provide stack traces from a stopped remote Python process."""

    def get_stack_trace(self) -> object:
        """Read every thread's current Python stack."""
        ...


class _Readable(Protocol):
    def fileno(self) -> int: ...


@dataclasses.dataclass(frozen=True, slots=True)
class _ResolvedFrame:
    filename: str
    funcname: str
    lineno: int


@dataclasses.dataclass(frozen=True, slots=True)
class _ResolvedThread:
    thread_id: int
    frame_info: list[_ResolvedFrame]


@dataclasses.dataclass(frozen=True, slots=True)
class _DebugOffsets:
    runtime_interpreters_head: int
    interpreter_next: int
    interpreter_threads_head: int
    thread_next: int
    thread_current_frame: int
    thread_native_id: int
    frame_previous: int
    frame_localsplus: int
    pyobject_type: int
    type_name: int


@typing.final
class QualifiedRemoteUnwinder:
    """Add runtime class names to generated dataclass constructor frames."""

    def __init__(self, process_id: int, unwinder: RemoteUnwinder):
        """Prepare to resolve frames in the unwinder's remote process."""
        self._process_id: int = process_id
        self._unwinder: RemoteUnwinder = unwinder
        self._runtime_address: int = _runtime_address(process_id)
        self._type_names: dict[int, str] = {}
        with _remote_memory(process_id) as memory:
            self._debug_offsets: _DebugOffsets = _read_debug_offsets(
                memory,
                self._runtime_address,
            )

    def get_stack_trace(self) -> object:
        """Read stack traces and qualify generated dataclass constructors."""
        remote_threads = self._unwinder.get_stack_trace()
        if not isinstance(remote_threads, list):
            raise TypeError("the remote unwinder did not return a thread list")
        return self._resolve_threads(cast("list[object]", remote_threads))

    def _resolve_threads(self, remote_threads: list[object]) -> list[_ResolvedThread]:
        thread_frames = self._thread_frames()
        resolved_threads: list[_ResolvedThread] = []
        with _remote_memory(self._process_id) as memory:
            for remote_thread_object in remote_threads:
                remote_thread = _remote_thread(remote_thread_object)
                frame_address = thread_frames.get(remote_thread.thread_id)
                resolved_frames: list[_ResolvedFrame] = []
                for remote_frame in remote_thread.frame_info:
                    function = remote_frame.funcname
                    if frame_address is None:
                        raise ValueError(
                            "the remote frame chain ended before the unwound stack"
                        )
                    if (
                        remote_frame.filename == "<string>"
                        and function == _DATACLASS_CONSTRUCTOR
                    ):
                        function = self._dataclass_constructor_name(
                            memory,
                            frame_address,
                        )
                    resolved_frames.append(
                        _ResolvedFrame(
                            filename=remote_frame.filename,
                            funcname=function,
                            lineno=remote_frame.lineno,
                        )
                    )
                    frame_address = (
                        _read_pointer(
                            memory,
                            frame_address + self._debug_offsets.frame_previous,
                        )
                        or None
                    )
                resolved_threads.append(
                    _ResolvedThread(
                        thread_id=remote_thread.thread_id,
                        frame_info=resolved_frames,
                    )
                )
        return resolved_threads

    def _thread_frames(self) -> dict[int, int | None]:
        offsets = self._debug_offsets
        frames: dict[int, int | None] = {}
        with _remote_memory(self._process_id) as memory:
            interpreter_address = _read_pointer(
                memory,
                self._runtime_address + offsets.runtime_interpreters_head,
            )
            while interpreter_address:
                thread_address = _read_pointer(
                    memory,
                    interpreter_address + offsets.interpreter_threads_head,
                )
                while thread_address:
                    native_thread_id = _read_pointer(
                        memory,
                        thread_address + offsets.thread_native_id,
                    )
                    current_frame = _read_pointer(
                        memory,
                        thread_address + offsets.thread_current_frame,
                    )
                    frames[native_thread_id] = current_frame or None
                    thread_address = _read_pointer(
                        memory,
                        thread_address + offsets.thread_next,
                    )
                interpreter_address = _read_pointer(
                    memory,
                    interpreter_address + offsets.interpreter_next,
                )
        return frames

    def _dataclass_constructor_name(
        self,
        memory: _Readable,
        frame_address: int,
    ) -> str:
        offsets = self._debug_offsets
        instance_reference = _read_pointer(
            memory,
            frame_address + offsets.frame_localsplus,
        )
        instance_address = instance_reference & ~1
        type_address = _read_pointer(
            memory,
            instance_address + offsets.pyobject_type,
        )
        type_name = self._type_names.get(type_address)
        if type_name is None:
            type_name_address = _read_pointer(
                memory,
                type_address + offsets.type_name,
            )
            type_name = _read_c_string(memory, type_name_address)
            self._type_names[type_address] = type_name
        return f"{type_name}.__init__"


def _remote_thread(remote_thread: object) -> RemoteThread:
    if not hasattr(remote_thread, "thread_id") or not hasattr(
        remote_thread,
        "frame_info",
    ):
        raise ValueError("the remote unwinder returned malformed thread data")
    return cast("RemoteThread", remote_thread)


def _remote_memory(process_id: int) -> typing.BinaryIO:
    return cast(
        "typing.BinaryIO",
        pathlib.Path(f"/proc/{process_id}/mem").open("rb", buffering=0),
    )


def _read_exact(memory: _Readable, address: int, size: int) -> bytes:
    data = os.pread(memory.fileno(), size, address)
    if len(data) != size:
        raise ValueError(f"read {len(data)} remote bytes instead of {size}")
    return data


def _read_pointer(memory: _Readable, address: int) -> int:
    return int.from_bytes(_read_exact(memory, address, _POINTER_SIZE), "little")


def _read_c_string(memory: _Readable, address: int) -> str:
    value = _read_exact(memory, address, 512)
    terminator = value.find(b"\0")
    if terminator < 0:
        raise ValueError("a remote type name exceeded 511 bytes")
    return value[:terminator].decode("utf-8")


def _read_debug_offsets(memory: _Readable, runtime_address: int) -> _DebugOffsets:
    raw_offsets = _read_exact(memory, runtime_address, _DEBUG_OFFSETS_SIZE)
    cookie = raw_offsets[:8]
    if cookie != b"xdebugpy":
        raise ValueError("the Python runtime debug-offset cookie did not match")
    values = [
        int.from_bytes(raw_offsets[offset : offset + 8], "little")
        for offset in range(8, _DEBUG_OFFSETS_SIZE, 8)
    ]
    if values[1] != 1:
        raise ValueError("the profiler requires a free-threaded Python runtime")
    return _DebugOffsets(
        runtime_interpreters_head=values[4],
        interpreter_next=values[7],
        interpreter_threads_head=values[8],
        thread_next=values[23],
        thread_current_frame=values[25],
        thread_native_id=values[27],
        frame_previous=values[31],
        frame_localsplus=values[34],
        pyobject_type=values[50],
        type_name=values[52],
    )


def _runtime_address(process_id: int) -> int:
    local_runtime_address = ctypes.addressof(
        ctypes.c_char.in_dll(ctypes.pythonapi, "_PyRuntime")
    )
    local_executable_inode = pathlib.Path("/proc/self/exe").stat().st_ino
    runtime_file_offset: int | None = None
    for start, end, file_offset in _executable_mappings(
        os.getpid(),
        local_executable_inode,
    ):
        if start <= local_runtime_address < end:
            runtime_file_offset = file_offset + local_runtime_address - start
            break
    if runtime_file_offset is None:
        raise ValueError("the profiler's Python runtime was not mapped")

    target_executable_inode = pathlib.Path(f"/proc/{process_id}/exe").stat().st_ino
    for start, end, file_offset in _executable_mappings(
        process_id,
        target_executable_inode,
    ):
        if file_offset <= runtime_file_offset < file_offset + end - start:
            return start + runtime_file_offset - file_offset
    raise ValueError("the target's Python runtime was not mapped")


def _executable_mappings(
    process_id: int,
    executable_inode: int,
) -> list[tuple[int, int, int]]:
    mappings: list[tuple[int, int, int]] = []
    maps_path = pathlib.Path(f"/proc/{process_id}/maps")
    for line in maps_path.read_text(encoding="utf-8").splitlines():
        fields = line.split(maxsplit=5)
        if len(fields) < 5:
            raise ValueError("a process mapping did not contain five fields")
        address_range, _, mapped_offset, _device, inode = fields[:5]
        if int(inode) != executable_inode:
            continue
        start_text, end_text = address_range.split("-", maxsplit=1)
        mappings.append(
            (
                int(start_text, 16),
                int(end_text, 16),
                int(mapped_offset, 16),
            )
        )
    return mappings
