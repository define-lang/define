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
