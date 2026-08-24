"""Tests for generated-program Particle Operation dependency analysis."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from define.compiler.codegen import operation_dependency_analysis
from define.runtime import tracing

if TYPE_CHECKING:
    from pathlib import Path


def test_read_operation_dependencies(tmp_path: Path):
    dependencies_file = tmp_path / "operation_dependencies.json"
    _ = dependencies_file.write_text(
        json.dumps(
            [
                {
                    "operation": {
                        "execution": {
                            "caller": None,
                            "action_name": "test",
                        },
                        "operation_name": "create",
                        "target": "source",
                        "occurrence": 1,
                    },
                    "dependencies": [],
                },
                {
                    "operation": {
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
                    },
                    "dependencies": [
                        {
                            "execution": {
                                "caller": None,
                                "action_name": "test",
                            },
                            "operation_name": "create",
                            "target": "source",
                            "occurrence": 1,
                        }
                    ],
                },
            ]
        ),
        encoding="utf-8",
    )
    entry_execution = tracing.ActionExecutionIdentity(None, "test")
    create_source = tracing.OperationIdentity(
        entry_execution, "create", None, "source", 1
    )
    move_source = tracing.OperationIdentity(
        tracing.ActionExecutionIdentity(
            tracing.ActionExecutionIdentity(entry_execution, "middle"),
            "worker",
        ),
        "move",
        "source",
        "destination",
        2,
    )

    assert operation_dependency_analysis.read_operation_dependencies(
        dependencies_file
    ) == {
        create_source: (),
        move_source: (create_source,),
    }


def test_operation_dependencies_as_scheduling_table():
    execution = tracing.ActionExecutionIdentity(None, "test")
    first = tracing.OperationIdentity(execution, "create", None, "first", 1)
    second = tracing.OperationIdentity(execution, "create", None, "second", 1)
    third = tracing.OperationIdentity(execution, "create", None, "third", 1)
    fourth = tracing.OperationIdentity(execution, "create", None, "fourth", 1)

    dependencies = operation_dependency_analysis.OperationDependencies(
        {
            first: (),
            second: (first,),
            third: (first,),
            fourth: (third, second),
        }
    )

    assert dependencies.as_scheduling_table() == {
        first: (),
        second: (first,),
        third: (first,),
        fourth: (second, third),
    }
    assert dependencies.transitive_dependency_pairs() == {
        (second, first),
        (third, first),
        (fourth, first),
        (fourth, second),
        (fourth, third),
    }
