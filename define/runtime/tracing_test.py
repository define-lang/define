"""Tests for operation tracing."""

import json
from pathlib import Path

import pytest

from define.runtime import tracing


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
