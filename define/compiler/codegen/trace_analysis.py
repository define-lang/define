"""Parse and analyze operation traces from generated programs."""

from __future__ import annotations

import json
import typing

from define.compiler.validator.reference_graph import (
    operation_graph_labeler,
    operation_graph_resolver,
)
from define.runtime import tracing

if typing.TYPE_CHECKING:
    from pathlib import Path

    from define.compiler import ast
    from define.compiler.validator.reference_graph import operation_graph


def _deserialize_object(
    serialized: dict[str, object],
) -> tracing.ActionExecutionIdentity | tracing.OperationTraceRecord:
    if "action_name" in serialized:
        return tracing.ActionExecutionIdentity(
            typing.cast(
                "tracing.ActionExecutionIdentity | None",
                serialized["caller"],
            ),
            typing.cast("str", serialized["action_name"]),
        )
    return tracing.OperationTraceRecord(
        typing.cast("tracing.ActionExecutionIdentity", serialized["execution"]),
        typing.cast("str", serialized["operation_name"]),
        typing.cast("str | None", serialized.get("source")),
        typing.cast("str", serialized["target"]),
        typing.cast("int", serialized["occurrence"]),
    )


def read_operation_trace(trace_file: Path) -> list[tracing.OperationTraceRecord]:
    """Read an ordered operation trace from JSON."""
    with trace_file.open(encoding="utf-8") as trace_stream:
        return typing.cast(
            "list[tracing.OperationTraceRecord]",
            json.load(
                trace_stream,
                object_hook=_deserialize_object,
            ),
        )


def _execution_identity(
    execution: operation_graph_resolver.ActionExecution,
    labels: operation_graph_labeler.OperationGraphLabeler,
    identities: dict[
        operation_graph_resolver.ActionExecution,
        tracing.ActionExecutionIdentity,
    ],
) -> tracing.ActionExecutionIdentity:
    identity = identities.get(execution)
    if identity is not None:
        return identity
    triggered_by = execution.triggered_by
    if triggered_by is None:
        identity = tracing.ActionExecutionIdentity(
            None,
            labels.entry_action_execution_name(execution.action),
        )
    else:
        identity = tracing.ActionExecutionIdentity(
            _execution_identity(triggered_by.caller, labels, identities),
            labels.triggered_action_execution_name(
                triggered_by.caller.action,
                triggered_by.action_trigger.trigger,
            ).local_name,
        )
    identities[execution] = identity
    return identity


def resolved_operation_dependencies(
    operation_graphs: operation_graph.OperationGraphs,
    entry_action: ast.ActionDefinition,
) -> dict[tracing.OperationTraceRecord, tuple[tracing.OperationTraceRecord, ...]]:
    """Map each resolved operation's trace record to its direct dependency records."""
    resolved = operation_graph_resolver.ResolvedOperationGraphBuilder(
        operation_graphs,
        entry_action.typed_name,
    ).build()
    labels = operation_graph_labeler.OperationGraphLabeler(operation_graphs)
    identities: dict[
        operation_graph_resolver.ActionExecution,
        tracing.ActionExecutionIdentity,
    ] = {}
    records: dict[
        operation_graph_resolver.ResolvedOperation,
        tracing.OperationTraceRecord,
    ] = {}
    for operation in resolved.operations:
        local_label = labels.operation_label(
            operation.action_execution.action,
            operation.operation,
        )
        records[operation] = tracing.OperationTraceRecord(
            _execution_identity(operation.action_execution, labels, identities),
            local_label.operation_name,
            local_label.source,
            local_label.target,
            local_label.occurrence,
        )
    return {
        records[operation]: tuple(
            records[dependency] for dependency in operation.dependencies
        )
        for operation in resolved.operations
    }
