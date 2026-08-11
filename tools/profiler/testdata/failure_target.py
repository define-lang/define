"""Failing process used by profiler integration tests."""

import ctypes
import sys
import time
import typing

# PRF-024: Explicit failures. PRF-041: Realistic tests.

_LIBC = ctypes.CDLL(None)
_LIBC.pthread_create.argtypes = [
    ctypes.POINTER(ctypes.c_ulong),
    ctypes.c_void_p,
    ctypes.c_void_p,
    ctypes.c_void_p,
]
_LIBC.pthread_create.restype = ctypes.c_int
_LIBC.pthread_detach.argtypes = [ctypes.c_ulong]
_LIBC.pthread_detach.restype = ctypes.c_int
_LIBC.sleep.argtypes = [ctypes.c_uint]
_LIBC.sleep.restype = ctypes.c_uint

# Native sleepers give CPU capture deterministic OS threads with no Python stack.
_sleep_function = ctypes.cast(_LIBC.sleep, ctypes.c_void_p)
for _ in range(8):
    _thread_id = ctypes.c_ulong()
    _create_result = typing.cast(
        "int",
        _LIBC.pthread_create(
            ctypes.byref(_thread_id),
            None,
            _sleep_function,
            ctypes.c_void_p(1),
        ),
    )
    if _create_result:
        raise OSError(_create_result, "pthread_create failed")
    _detach_result = typing.cast("int", _LIBC.pthread_detach(_thread_id))
    if _detach_result:
        raise OSError(_detach_result, "pthread_detach failed")
    time.sleep(0.01)

time.sleep(0.3)
print("target diagnostic", file=sys.stderr)
raise SystemExit(4)
