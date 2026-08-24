"""Operation tracing for instrumented literal Python programs.

The purpose of tracing is to accurately output the executed order of
operations at runtime, and nothing else. It does not fully track every method
in the generated code, just the order of actual Define operations.
"""

from __future__ import annotations

import dataclasses
import json
import os
import typing
from pathlib import Path
from typing import final, override

from define.runtime import literal

if typing.TYPE_CHECKING:
    import types
    from collections.abc import Sequence

_OPERATION_TRACE_FILE_ENV_VAR = "DEFINE_OPERATION_TRACE_FILE"


@dataclasses.dataclass(frozen=True, slots=True)
class ActionExecutionIdentity:
    """One Action Execution and the Action Execution that called it."""

    caller: ActionExecutionIdentity | None
    action_name: str


@dataclasses.dataclass(frozen=True, slots=True)
class OperationTraceRecord:
    """One successfully completed generated Position Operation."""

    execution: ActionExecutionIdentity
    operation_name: str
    source: str | None
    target: str
    occurrence: int


class _TraceExecutionProvider(typing.Protocol):
    trace_execution: ActionExecutionIdentity


@final
class DestructionConnection(literal.DestructionConnection):
    """A destruction connection associated with one logical Action Execution."""

    # ready() captures the identity before starting any connected work.
    _destroying_action_execution: ActionExecutionIdentity  # pyright: ignore[reportUninitializedInstanceVariable]

    @property
    @override
    def destroying_action_execution(self) -> ActionExecutionIdentity:
        """Return the destroying Action Execution's trace identity."""
        return self._destroying_action_execution

    @property
    def trace_execution(self) -> ActionExecutionIdentity:
        """Provide the trace identity to a forwarded tracing connection."""
        return self._destroying_action_execution

    @typing.override
    def ready(self, continuation: types.MethodType):
        """Capture the destroying Action Execution before starting connected work."""
        trace_execution_provider = typing.cast(
            "_TraceExecutionProvider", continuation.__self__
        )
        self._destroying_action_execution = trace_execution_provider.trace_execution
        super().ready(continuation)


@final
class TracingScheduler(literal.Scheduler):
    """A literal Scheduler that records completed operations."""

    def __init__(self, *, max_threads: int | None = None):
        """Initialize an empty operation trace."""
        super().__init__(max_threads=max_threads)
        self._records: list[OperationTraceRecord] = []

    @property
    def records(self) -> list[OperationTraceRecord]:
        """Return every completed generated Position Operation."""
        return self._records

    @override
    def create_destruction_connection(
        self,
        predecessor_count: int,
        *start_tasks: types.MethodType,
        forwarded_connection: literal.DestructionConnection | None = None,
    ) -> DestructionConnection:
        """Create a connection that propagates Action Execution identity."""
        return DestructionConnection(
            self,
            predecessor_count,
            *start_tasks,
            forwarded_connection=forwarded_connection,
        )

    @override
    def execution_created(
        self,
        caller: object | None,
        action_name: str,
        /,
    ) -> ActionExecutionIdentity:
        """Create the structural identity of an Action Execution."""
        return ActionExecutionIdentity(
            typing.cast("ActionExecutionIdentity | None", caller),
            action_name,
        )

    @override
    def create_completed(
        self,
        execution: object | None,
        position_name: str,
        occurrence: int,
        /,
    ):
        """Record a completed Create."""
        self._operation_completed(
            execution,
            "create",
            None,
            position_name,
            occurrence,
        )

    @override
    def move_completed(
        self,
        execution: object | None,
        source_name: str,
        destination_name: str,
        occurrence: int,
        /,
    ):
        """Record a completed Move."""
        self._operation_completed(
            execution,
            "move",
            source_name,
            destination_name,
            occurrence,
        )

    @override
    def destroy_completed(
        self,
        execution: object | None,
        position_name: str,
        occurrence: int,
        /,
    ):
        """Record a completed Destroy."""
        self._operation_completed(
            execution,
            "destroy",
            None,
            position_name,
            occurrence,
        )

    def _operation_completed(
        self,
        execution: object | None,
        operation_name: str,
        source: str | None,
        target: str,
        occurrence: int,
    ):
        if execution is None:
            raise ValueError("trace execution is required")
        if not isinstance(execution, ActionExecutionIdentity):
            raise TypeError("invalid trace execution type")
        self._records.append(
            OperationTraceRecord(
                execution,
                operation_name,
                source,
                target,
                occurrence,
            )
        )


def write_operation_trace(records: Sequence[OperationTraceRecord]):
    """Write ``records`` to the configured trace file, when requested."""
    trace_file = os.environ.get(_OPERATION_TRACE_FILE_ENV_VAR)
    if trace_file is None:
        return
    # TODO: Version this artifact and publish a JSON Schema before external
    # tools consume it.
    serialized_records: list[dict[str, object]] = []
    for record in records:
        serialized_record = dataclasses.asdict(record)
        if record.source is None:
            del serialized_record["source"]
        serialized_records.append(serialized_record)
    serialized = json.dumps(serialized_records, indent=2)
    _ = Path(trace_file).write_text(serialized + "\n")
