"""Tests for generated-program operation trace analysis."""

import json
from pathlib import Path

from define.compiler.codegen import trace_analysis
from define.runtime import tracing


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
