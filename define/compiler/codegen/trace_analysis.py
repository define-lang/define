"""Parse and analyze operation traces from generated programs."""

from __future__ import annotations

import json
import typing
from collections import abc

from define.compiler.validator.reference_graph import (
    operation_graph_labeler,
    operation_graph_resolver,
)
from define.runtime import tracing

if typing.TYPE_CHECKING:
    from pathlib import Path

    from define.compiler import ast
    from define.compiler.validator.reference_graph import operation_graph


@typing.final
class OperationDependencies(
    abc.Mapping[
        tracing.OperationTraceRecord,
        frozenset[tracing.OperationTraceRecord],
    ]
):
    """The direct dependencies between traced Particle Operations."""

    def __init__(
        self,
        direct_dependencies: dict[
            tracing.OperationTraceRecord,
            frozenset[tracing.OperationTraceRecord],
        ],
    ):
        """Initialize the direct dependencies."""
        self._direct_dependencies = direct_dependencies

    @typing.override
    def __getitem__(
        self,
        operation: tracing.OperationTraceRecord,
    ) -> frozenset[tracing.OperationTraceRecord]:
        return self._direct_dependencies[operation]

    @typing.override
    def __iter__(self) -> abc.Iterator[tracing.OperationTraceRecord]:
        return iter(self._direct_dependencies)

    @typing.override
    def __len__(self) -> int:
        return len(self._direct_dependencies)

    def transitive(self) -> OperationDependencies:
        """Include every direct and indirect dependency of each operation."""
        transitive_dependencies: dict[
            tracing.OperationTraceRecord,
            frozenset[tracing.OperationTraceRecord],
        ] = {}
        for operation in self:
            dependencies: set[tracing.OperationTraceRecord] = set()
            remaining = list(self[operation])
            while remaining:
                dependency = remaining.pop()
                if dependency in dependencies:
                    continue
                dependencies.add(dependency)
                remaining.extend(self[dependency])
            transitive_dependencies[operation] = frozenset(dependencies)
        return OperationDependencies(transitive_dependencies)


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


def read_operation_dependencies(
    dependencies_file: Path,
    operations: list[tracing.OperationTraceRecord],
) -> OperationDependencies:
    """Read the runtime dependencies for an ordered operation trace."""
    with dependencies_file.open(encoding="utf-8") as dependencies_stream:
        dependency_indices_by_operation = typing.cast(
            "list[list[int]]", json.load(dependencies_stream)
        )
    dependencies: dict[
        tracing.OperationTraceRecord,
        frozenset[tracing.OperationTraceRecord],
    ] = {}
    for operation, dependency_indices in zip(
        operations, dependency_indices_by_operation, strict=True
    ):
        operation_dependencies: set[tracing.OperationTraceRecord] = set()
        for dependency_index in dependency_indices:
            operation_dependencies.add(operations[dependency_index])
        dependencies[operation] = frozenset(operation_dependencies)
    return OperationDependencies(dependencies)


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
    if isinstance(execution, operation_graph_resolver.TriggeredActionExecution):
        identity = tracing.ActionExecutionIdentity(
            _execution_identity(execution.caller, labels, identities),
            labels.triggered_action_execution_name(
                execution.direct_execution_caller.action,
                execution.direct_execution.execution,
            ).local_name,
        )
    else:
        identity = tracing.ActionExecutionIdentity(
            None,
            labels.entry_action_execution_name(execution.action),
        )
    identities[execution] = identity
    return identity


def resolved_operation_dependencies(
    operation_graphs: operation_graph.OperationGraphs,
    entry_action: ast.ActionDefinition,
) -> OperationDependencies:
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
    direct_dependencies: dict[
        tracing.OperationTraceRecord,
        frozenset[tracing.OperationTraceRecord],
    ] = {}
    for operation in resolved.operations:
        direct_dependencies[records[operation]] = frozenset(
            records[dependency] for dependency in operation.dependencies
        )
    return OperationDependencies(direct_dependencies)
