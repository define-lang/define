"""Particle Operation tracing for instrumented literal Python programs.

Tracing records both the realized operation order and the runtime dependency
relation. It does not track generated methods that perform no Particle Operation.
"""

from __future__ import annotations

import contextvars
import dataclasses
import json
import os
import typing
from pathlib import Path
from typing import final, override

from define.runtime import literal

if typing.TYPE_CHECKING:
    import types

_OPERATION_TRACE_FILE_ENV_VAR = "DEFINE_OPERATION_TRACE_FILE"
_OPERATION_DEPENDENCIES_FILE_ENV_VAR = "DEFINE_OPERATION_DEPENDENCIES_FILE"


@dataclasses.dataclass(frozen=True, slots=True)
class ActionExecutionIdentity:
    """One Action Execution and the Action Execution that called it."""

    caller: ActionExecutionIdentity | None
    action_name: str


@dataclasses.dataclass(frozen=True, slots=True)
class OperationTraceRecord:
    """One successfully completed generated Particle Operation."""

    execution: ActionExecutionIdentity
    operation_name: str
    source: str | None
    target: str
    occurrence: int


type OperationTrace = dict[
    OperationTraceRecord,
    frozenset[OperationTraceRecord],
]


@final
class Join(literal.Join):
    """A traced Join that combines dependencies from every arrival."""

    def __init__(
        self,
        arrivals: int,
        current_operation_dependencies: contextvars.ContextVar[
            frozenset[OperationTraceRecord]
        ],
    ):
        """Initialize a traced Join requiring ``arrivals`` arrivals."""
        super().__init__(arrivals)
        self._current_operation_dependencies = current_operation_dependencies
        self._operation_dependencies: set[OperationTraceRecord] = set()

    @override
    def arrive(self) -> bool:
        """Combine dependencies and adopt them on the final arrival."""
        self._operation_dependencies.update(self._current_operation_dependencies.get())
        if not super().arrive():
            return False
        _ = self._current_operation_dependencies.set(
            frozenset(self._operation_dependencies)
        )
        return True


class _TraceExecutionProvider(typing.Protocol):
    trace_execution: ActionExecutionIdentity


@final
class DestructionConnection(literal.DestructionConnection):
    """A destruction connection associated with one logical Action Execution."""

    # ready() assigns this before any connected work can access it.
    trace_execution: ActionExecutionIdentity  # pyright: ignore[reportUninitializedInstanceVariable]

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
    """A literal Scheduler that records operations and runtime dependencies."""

    def __init__(self, *, max_threads: int | None = None):
        """Initialize an empty operation trace."""
        super().__init__(max_threads=max_threads)
        self._trace: OperationTrace = {}
        self._current_operation_dependencies = contextvars.ContextVar[
            frozenset[OperationTraceRecord]
        ](
            "current_operation_dependencies",
            default=frozenset(),
        )

    @property
    def trace(self) -> OperationTrace:
        """Return the realized operations and their runtime dependencies."""
        return self._trace

    @override
    def create_join(self, arrivals: int) -> Join:
        """Create a Join that records dependencies from every arrival."""
        return Join(arrivals, self._current_operation_dependencies)

    @override
    def submit(self, task: literal.Task):
        operation_dependencies = self._current_operation_dependencies.get()

        def run_with_operation_dependencies():
            token = self._current_operation_dependencies.set(operation_dependencies)
            try:
                task()
            finally:
                self._current_operation_dependencies.reset(token)

        super().submit(run_with_operation_dependencies)

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
        operation = OperationTraceRecord(
            execution,
            operation_name,
            source,
            target,
            occurrence,
        )
        operation_dependencies = self._current_operation_dependencies.get()
        self._trace[operation] = operation_dependencies
        _ = self._current_operation_dependencies.set(frozenset((operation,)))


def write_operation_trace(trace: OperationTrace):
    """Write the configured trace artifacts, when requested."""
    trace_file = os.environ.get(_OPERATION_TRACE_FILE_ENV_VAR)
    if trace_file is not None:
        serialized_operations = [_serialize_operation(operation) for operation in trace]
        _write_json(Path(trace_file), serialized_operations)
    dependencies_file = os.environ.get(_OPERATION_DEPENDENCIES_FILE_ENV_VAR)
    if dependencies_file is not None:
        operation_indices = {operation: index for index, operation in enumerate(trace)}
        serialized_dependencies: list[list[int]] = []
        for operation in trace:
            serialized_dependencies.append(
                sorted(operation_indices[dependency] for dependency in trace[operation])
            )
        _write_json(Path(dependencies_file), serialized_dependencies)


def _serialize_operation(operation: OperationTraceRecord) -> dict[str, object]:
    serialized_operation = dataclasses.asdict(operation)
    if operation.source is None:
        del serialized_operation["source"]
    return serialized_operation


def _write_json(trace_file: Path, value: object):
    # TODO: Version this artifact and publish a JSON Schema before external
    # tools consume it.
    _ = trace_file.write_text(json.dumps(value, indent=2) + "\n")
