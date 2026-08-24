"""Tests for operation tracing."""

from __future__ import annotations

import json
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
        trace_execution: tracing.ActionExecutionIdentity,
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
        typed_name: typing.ClassVar[str] = "action<entry>"

        @typing.override
        def execute(self, scheduler: literal.Scheduler):
            destruction_continuation = _ContinuationExecution.continue_destroy

            def complete_forwarded_connection():
                forwarded_connection.complete()

            forwarded_connection = tracing.DestructionConnection(
                scheduler,
                1,
                _bound_task(complete_forwarded_connection),
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
            assert isinstance(trace_execution, tracing.ActionExecutionIdentity)
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
    assert connections[0].trace_execution is executions[0].trace_execution
    assert connections[1].trace_execution is executions[0].trace_execution


def test_action_execution_identity_retains_each_caller():
    scheduler = tracing.TracingScheduler()

    entry = scheduler.execution_created(None, "test")
    first = scheduler.execution_created(entry, "first")
    worker = scheduler.execution_created(first, "worker")

    assert worker == tracing.ActionExecutionIdentity(
        tracing.ActionExecutionIdentity(
            tracing.ActionExecutionIdentity(None, "test"),
            "first",
        ),
        "worker",
    )


def test_completion_hooks_retain_every_operation_in_order():
    scheduler = tracing.TracingScheduler()
    execution = scheduler.execution_created(None, "test")

    scheduler.create_completed(execution, "item", 1)
    scheduler.move_completed(execution, "item", "destination", 1)
    scheduler.destroy_completed(execution, "destination", 1)
    scheduler.create_completed(execution, "item", 2)

    assert scheduler.records == [
        tracing.OperationTraceRecord(execution, "create", None, "item", 1),
        tracing.OperationTraceRecord(
            execution,
            "move",
            "item",
            "destination",
            1,
        ),
        tracing.OperationTraceRecord(
            execution,
            "destroy",
            None,
            "destination",
            1,
        ),
        tracing.OperationTraceRecord(execution, "create", None, "item", 2),
    ]


def test_trace_json_preserves_structural_execution_and_completion_order(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    trace_file = tmp_path / "trace.json"
    monkeypatch.setenv("DEFINE_OPERATION_TRACE_FILE", str(trace_file))
    scheduler = tracing.TracingScheduler()
    entry = scheduler.execution_created(None, "test")
    worker = scheduler.execution_created(entry, "worker")
    scheduler.create_completed(entry, "gateway", 1)
    scheduler.create_completed(worker, "scratch", 1)

    tracing.write_operation_trace(scheduler.records)

    assert json.loads(trace_file.read_text()) == [
        {
            "execution": {
                "caller": None,
                "action_name": "test",
            },
            "operation_name": "create",
            "target": "gateway",
            "occurrence": 1,
        },
        {
            "execution": {
                "caller": {
                    "caller": None,
                    "action_name": "test",
                },
                "action_name": "worker",
            },
            "operation_name": "create",
            "target": "scratch",
            "occurrence": 1,
        },
    ]


def test_write_operation_trace_does_nothing_without_environment_file(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.delenv("DEFINE_OPERATION_TRACE_FILE", raising=False)

    tracing.write_operation_trace(())
