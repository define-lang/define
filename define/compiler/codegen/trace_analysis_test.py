"""Tests for generated-program operation trace analysis."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from define.compiler.codegen import trace_analysis
from define.runtime import tracing

if TYPE_CHECKING:
    from pathlib import Path


def test_read_operation_trace(tmp_path: Path):
    trace_file = tmp_path / "operation_trace.json"
    _ = trace_file.write_text(
        json.dumps(
            [
                {
                    "execution": {
                        "caller": {
                            "caller": {
                                "caller": None,
                                "action_name": "test",
                            },
                            "action_name": "middle",
                        },
                        "action_name": "worker",
                    },
                    "operation_name": "move",
                    "source": "source",
                    "target": "destination",
                    "occurrence": 2,
                }
            ]
        ),
        encoding="utf-8",
    )

    assert trace_analysis.read_operation_trace(trace_file) == [
        tracing.OperationTraceRecord(
            tracing.ActionExecutionIdentity(
                tracing.ActionExecutionIdentity(
                    tracing.ActionExecutionIdentity(None, "test"),
                    "middle",
                ),
                "worker",
            ),
            "move",
            "source",
            "destination",
            2,
        )
    ]


def test_read_operation_dependencies(tmp_path: Path):
    dependencies_file = tmp_path / "operation_dependencies.json"
    _ = dependencies_file.write_text(json.dumps([[], [0]]), encoding="utf-8")
    execution = tracing.ActionExecutionIdentity(None, "test")
    first = tracing.OperationTraceRecord(execution, "create", None, "first", 1)
    second = tracing.OperationTraceRecord(execution, "create", None, "second", 1)

    assert trace_analysis.read_operation_dependencies(
        dependencies_file, [first, second]
    ) == {
        first: frozenset(),
        second: frozenset((first,)),
    }


def test_operation_dependencies_transitive():
    execution = tracing.ActionExecutionIdentity(None, "test")
    first = tracing.OperationTraceRecord(execution, "create", None, "first", 1)
    second = tracing.OperationTraceRecord(execution, "create", None, "second", 1)
    third = tracing.OperationTraceRecord(execution, "create", None, "third", 1)

    assert trace_analysis.OperationDependencies(
        {
            first: frozenset(),
            second: frozenset((first,)),
            third: frozenset((second,)),
        }
    ).transitive() == {
        first: frozenset(),
        second: frozenset((first,)),
        third: frozenset((first, second)),
    }
