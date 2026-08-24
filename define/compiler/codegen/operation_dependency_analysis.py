"""Parse and analyze Particle Operation dependencies."""

from __future__ import annotations

import json
import typing
from collections import abc

from define.compiler.validator.reference_graph import (
    operation_graph_labeler,
    operation_graph_renderer,
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
        tracing.OperationIdentity,
        tuple[tracing.OperationIdentity, ...],
    ]
):
    """The direct dependencies between traced Particle Operations."""

    def __init__(
        self,
        direct_dependencies: dict[
            tracing.OperationIdentity,
            tuple[tracing.OperationIdentity, ...],
        ],
    ):
        """Initialize the direct dependencies."""
        self._direct_dependencies = direct_dependencies

    @typing.override
    def __getitem__(
        self,
        operation: tracing.OperationIdentity,
    ) -> tuple[tracing.OperationIdentity, ...]:
        return self._direct_dependencies[operation]

    @typing.override
    def __iter__(self) -> abc.Iterator[tracing.OperationIdentity]:
        return iter(self._direct_dependencies)

    @typing.override
    def __len__(self) -> int:
        return len(self._direct_dependencies)

    def as_scheduling_table(self) -> OperationDependencies:
        """Return these direct dependencies in canonical scheduling-table order."""
        canonical_dependencies: dict[
            tracing.OperationIdentity,
            tuple[tracing.OperationIdentity, ...],
        ] = {}
        for operation, direct_dependencies in self.items():
            # Dependency order is not part of the scheduling table;
            # canonicalizing only each dependency tuple makes equality independent
            # of traversal order without changing realized Particle Operation order.
            canonical_dependencies[operation] = tuple(
                sorted(direct_dependencies, key=_operation_sort_key)
            )
        return OperationDependencies(canonical_dependencies)

    def transitive_dependency_pairs(
        self,
    ) -> set[tuple[tracing.OperationIdentity, tracing.OperationIdentity]]:
        """Return every direct and indirect operation-dependency pair."""
        dependency_pairs: set[
            tuple[tracing.OperationIdentity, tracing.OperationIdentity]
        ] = set()
        for operation in self:
            remaining = list(self[operation])
            while remaining:
                dependency = remaining.pop()
                pair = (operation, dependency)
                # A transitively minimal DAG can still have converging paths, so a
                # shared dependency must not be traversed more than once.
                if pair in dependency_pairs:
                    continue
                dependency_pairs.add(pair)
                remaining.extend(self[dependency])
        return dependency_pairs


def _operation_sort_key(
    operation: tracing.OperationIdentity,
) -> tuple[tuple[str, ...], str, str, str, int]:
    action_names: list[str] = []
    execution: tracing.ActionExecutionIdentity | None = operation.execution
    while execution is not None:
        action_names.append(execution.action_name)
        execution = execution.caller
    return (
        tuple(reversed(action_names)),
        operation.operation_name,
        operation.source or "",
        operation.target,
        operation.occurrence,
    )


def _deserialize_object(
    serialized: dict[str, object],
) -> dict[str, object] | tracing.ActionExecutionIdentity | tracing.OperationIdentity:
    if "action_name" in serialized:
        return tracing.ActionExecutionIdentity(
            typing.cast(
                "tracing.ActionExecutionIdentity | None",
                serialized["caller"],
            ),
            typing.cast("str", serialized["action_name"]),
        )
    if "operation_name" in serialized:
        return tracing.OperationIdentity(
            typing.cast("tracing.ActionExecutionIdentity", serialized["execution"]),
            typing.cast("str", serialized["operation_name"]),
            typing.cast("str | None", serialized.get("source")),
            typing.cast("str", serialized["target"]),
            typing.cast("int", serialized["occurrence"]),
        )
    return serialized


def read_operation_dependencies(dependencies_file: Path) -> OperationDependencies:
    """Read operations and their direct dependencies from JSON."""
    with dependencies_file.open(encoding="utf-8") as dependencies_stream:
        serialized_dependencies = typing.cast(
            "list[dict[str, object]]",
            json.load(
                dependencies_stream,
                object_hook=_deserialize_object,
            ),
        )
    dependencies: dict[
        tracing.OperationIdentity,
        tuple[tracing.OperationIdentity, ...],
    ] = {}
    for serialized_entry in serialized_dependencies:
        operation = typing.cast(
            "tracing.OperationIdentity", serialized_entry["operation"]
        )
        operation_dependencies = typing.cast(
            "list[tracing.OperationIdentity]", serialized_entry["dependencies"]
        )
        dependencies[operation] = tuple(operation_dependencies)
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
        tracing.OperationIdentity,
    ] = {}
    for operation in resolved.operations:
        local_label = labels.operation_label(
            operation.action_execution.action,
            operation.operation,
        )
        records[operation] = tracing.OperationIdentity(
            _execution_identity(operation.action_execution, labels, identities),
            local_label.operation_name,
            local_label.source,
            local_label.target,
            local_label.occurrence,
        )
    return OperationDependencies(
        operation_graph_renderer.resolved_operation_scheduling_table(
            resolved,
            records,
        )
    )
