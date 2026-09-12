# pyright: reportUnusedCallResult=false
"""Tests for operation tracing."""

from __future__ import annotations

import typing

from define.runtime import literal, tracing

if typing.TYPE_CHECKING:
    import types
    from pathlib import Path

    import pytest


@typing.final
class _ContinuationExecution:
    def __init__(
        self,
        trace_execution: str,
        destruction_connections: literal.DestructionConnections,
    ):
        self.trace_execution = trace_execution
        self.destruction_connections = destruction_connections
        self.destroyed = False

    def continue_destroy(self):
        self.destroyed = True


@typing.final
class _BoundTask:
    def __init__(self, task: literal.Task):
        self._task = task

    def run(self):
        self._task()


def _bound_task(task: literal.Task) -> types.MethodType:
    return _BoundTask(task).run


def test_destruction_connection_propagates_execution_through_forwarded_connections():
    connections: list[tracing.DestructionConnection] = []
    executions: list[_ContinuationExecution] = []

    class Entry(literal.EntryPoint):
        @typing.override
        def execute(self, scheduler: literal.Scheduler):
            destruction_continuation = _ContinuationExecution.continue_destroy

            def complete_forwarded_connection():
                forwarded_connection.complete()

            forwarded_connection = tracing.DestructionConnection(
                scheduler, 1, _bound_task(complete_forwarded_connection)
            )

            def complete_current_connection():
                current_connection.complete()

            current_connection = tracing.DestructionConnection(
                scheduler,
                1,
                _bound_task(complete_current_connection),
                forwarded_connection=forwarded_connection,
            )
            trace_execution = scheduler.execution_created(None, "test")
            assert isinstance(trace_execution, str)
            execution = _ContinuationExecution(
                trace_execution,
                literal.DestructionConnections(
                    {destruction_continuation: current_connection}
                ),
            )
            connections.extend((current_connection, forwarded_connection))
            executions.append(execution)
            literal.continue_destruction(execution.continue_destroy)

    tracing.TracingScheduler(max_threads=2).start(Entry)
    assert executions[0].destroyed
    assert connections[0].trace_execution == executions[0].trace_execution
    assert connections[1].trace_execution == executions[0].trace_execution


def test_execution_created_returns_only_the_action_name():
    scheduler = tracing.TracingScheduler()
    entry = scheduler.execution_created(None, "test")
    first = scheduler.execution_created(entry, "first")
    worker = scheduler.execution_created(first, "worker")
    assert worker == "worker"


def test_completion_hooks_record_operation_order():
    scheduler = tracing.TracingScheduler()
    execution = scheduler.execution_created(None, "test")
    scheduler.operation_completed(execution, "create(item)")
    scheduler.operation_completed(execution, "move(item, destination)")
    scheduler.operation_completed(execution, "destroy(destination)")
    scheduler.operation_completed(execution, "create(item)")
    assert scheduler.operation_trace == [
        "test.create(item)",
        "test.move(item, destination)",
        "test.destroy(destination)",
        "test.create(item)",
    ]


def test_operation_trace_file_preserves_runtime_operation_order(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    trace_file = tmp_path / "operation_trace.txt"
    monkeypatch.setenv("DEFINE_OPERATION_TRACE_FILE", str(trace_file))
    scheduler = tracing.TracingScheduler()
    entry = scheduler.execution_created(None, "test")
    worker = scheduler.execution_created(entry, "worker")
    scheduler.operation_completed(entry, "create(gateway)")
    scheduler.operation_completed(worker, "create(scratch)")
    scheduler.operation_completed(worker, "move(scratch, destination)")
    tracing.write_operation_trace(scheduler.operation_trace)
    assert (
        trace_file.read_text()
        == """\
test.create(gateway)
worker.create(scratch)
worker.move(scratch, destination)
"""
    )


def test_write_operation_trace_does_nothing_without_environment_file(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.delenv("DEFINE_OPERATION_TRACE_FILE", raising=False)
    tracing.write_operation_trace([])
