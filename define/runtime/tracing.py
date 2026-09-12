"""Particle Operation tracing for instrumented literal programs."""

from __future__ import annotations

import os
import threading
import typing
from pathlib import Path
from typing import final, override

from define.runtime import literal

if typing.TYPE_CHECKING:
    import types

_OPERATION_TRACE_FILE_ENV_VAR = "DEFINE_OPERATION_TRACE_FILE"

# TODO: Record operations directly in literal.py when tracing is enabled and
# remove this module.


class _TraceExecutionProvider(typing.Protocol):
    trace_execution: str


@final
class DestructionConnection(literal.DestructionConnection):
    """A destruction connection associated with one logical Action Execution."""

    # ready() assigns this before any connected work can access it.
    trace_execution: str  # pyright: ignore[reportUninitializedInstanceVariable]

    @typing.override
    def ready(self, continuation: types.MethodType):
        """Capture the destroying Action Execution before starting connected work."""
        trace_execution_provider = typing.cast(
            "_TraceExecutionProvider", continuation.__self__
        )
        self.trace_execution = trace_execution_provider.trace_execution
        super().ready(continuation)


@final
class TracingScheduler(literal.Scheduler):
    """A literal Scheduler that records completed operations in order."""

    def __init__(self, *, max_threads: int | None = None):
        """Initialize an empty operation trace."""
        super().__init__(max_threads=max_threads)
        self._operation_trace: list[str] = []
        self._trace_lock = threading.Lock()

    @property
    def operation_trace(self) -> list[str]:
        """Return completed operations in completion order."""
        return self._operation_trace

    @override
    def execution_created(
        self,
        _caller: object | None,
        action_name: str,
        /,
    ) -> str:
        """Return the name of the action being executed."""
        return action_name

    @override
    def operation_completed(
        self,
        execution: object | None,
        operation_label: str,
        /,
    ):
        """Record a completed Particle Operation."""
        if execution is None:
            raise ValueError("trace execution is required")
        if not isinstance(execution, str):
            raise TypeError("invalid trace execution type")
        with self._trace_lock:
            self._operation_trace.append(f"{execution}.{operation_label}")


def write_operation_trace(operation_trace: list[str]):
    """Write the configured operation trace, when requested."""
    trace_file = os.environ.get(_OPERATION_TRACE_FILE_ENV_VAR)
    if trace_file is None:
        return
    _ = Path(trace_file).write_text(
        "".join(f"{operation}\n" for operation in operation_trace)
    )
