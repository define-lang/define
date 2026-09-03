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


def test_caller_destructor_not_preceding_callee_destroy_preserves_destroy_dependency():
    class Entry(literal.EntryPoint):
        typed_name: typing.ClassVar[str] = "action<entry>"

        @typing.override
        def execute(self, scheduler: literal.Scheduler):
            dependency_execution = scheduler.execution_created(None, "test")
            assert isinstance(dependency_execution, tracing.ActionExecutionIdentity)
            destroying_execution = scheduler.execution_created(
                dependency_execution,
                "callee",
            )
            assert isinstance(destroying_execution, tracing.ActionExecutionIdentity)
            destructor_execution = scheduler.execution_created(
                destroying_execution,
                "destructor",
            )
            assert isinstance(destructor_execution, tracing.ActionExecutionIdentity)
            scheduler.move_completed(
                dependency_execution,
                "source",
                "target",
                1,
            )

            @typing.final
            class ContinuationExecution:
                def __init__(
                    self,
                    destruction_connections: literal.DestructionConnections,
                ):
                    self.trace_execution = destroying_execution
                    self.destruction_connections = destruction_connections

                def continue_destroy(self):
                    scheduler.destroy_completed(
                        destroying_execution,
                        "target",
                        1,
                    )

            def run_destructor():
                scheduler.create_completed(
                    destructor_execution,
                    "_noop",
                    1,
                )

            # This Destructor runs at the callee Destroy but does not precede it.
            connection = tracing.DestructionConnection(
                scheduler,
                0,
                _bound_task(run_destructor),
            )
            execution = ContinuationExecution(
                literal.DestructionConnections(
                    {ContinuationExecution.continue_destroy: connection}
                )
            )
            literal.continue_destruction(execution.continue_destroy)

    scheduler = tracing.TracingScheduler(max_threads=2)
    scheduler.start(Entry)

    dependency_execution = tracing.ActionExecutionIdentity(None, "test")
    destroying_execution = tracing.ActionExecutionIdentity(
        dependency_execution,
        "callee",
    )
    move = tracing.OperationIdentity(
        dependency_execution,
        "move",
        "source",
        "target",
        1,
    )
    destroy = tracing.OperationIdentity(
        destroying_execution,
        "destroy",
        None,
        "target",
        1,
    )
    assert scheduler.operation_dependencies[destroy] == (move,)


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


def test_completion_hooks_record_operation_dependencies():
    scheduler = tracing.TracingScheduler()
    execution = scheduler.execution_created(None, "test")

    scheduler.create_completed(execution, "item", 1)
    scheduler.move_completed(execution, "item", "destination", 1)
    scheduler.destroy_completed(execution, "destination", 1)
    scheduler.create_completed(execution, "item", 2)

    first = tracing.OperationIdentity(execution, "create", None, "item", 1)
    second = tracing.OperationIdentity(
        execution,
        "move",
        "item",
        "destination",
        1,
    )
    third = tracing.OperationIdentity(
        execution,
        "destroy",
        None,
        "destination",
        1,
    )
    fourth = tracing.OperationIdentity(execution, "create", None, "item", 2)
    assert scheduler.operation_dependencies == {
        first: (),
        second: (first,),
        third: (second,),
        fourth: (third,),
    }


def test_submitted_tasks_retain_only_their_submission_dependencies():
    class Entry(literal.EntryPoint):
        typed_name: typing.ClassVar[str] = "action<entry>"

        @typing.override
        def execute(self, scheduler: literal.Scheduler):
            execution = scheduler.execution_created(None, "test")

            def create_first():
                scheduler.create_completed(execution, "first", 1)

            def create_second():
                scheduler.create_completed(execution, "second", 1)

            scheduler.submit(create_first)
            scheduler.submit(create_second)

    scheduler = tracing.TracingScheduler(max_threads=1)
    scheduler.start(Entry)

    execution = tracing.ActionExecutionIdentity(None, "test")
    first = tracing.OperationIdentity(execution, "create", None, "first", 1)
    second = tracing.OperationIdentity(execution, "create", None, "second", 1)
    assert scheduler.operation_dependencies == {
        first: (),
        second: (),
    }


def test_join_combines_dependencies_from_every_arrival():
    class Entry(literal.EntryPoint):
        typed_name: typing.ClassVar[str] = "action<entry>"

        @typing.override
        def execute(self, scheduler: literal.Scheduler):
            execution = scheduler.execution_created(None, "test")
            join = scheduler.create_join(2)

            def complete_branch(position_name: str):
                scheduler.create_completed(execution, position_name, 1)
                if join.arrive():
                    scheduler.destroy_completed(execution, "parent", 1)

            scheduler.submit(lambda: complete_branch("first"))
            scheduler.submit(lambda: complete_branch("second"))

    scheduler = tracing.TracingScheduler(max_threads=1)
    scheduler.start(Entry)

    execution = tracing.ActionExecutionIdentity(None, "test")
    first = tracing.OperationIdentity(execution, "create", None, "first", 1)
    second = tracing.OperationIdentity(execution, "create", None, "second", 1)
    parent = tracing.OperationIdentity(execution, "destroy", None, "parent", 1)
    assert scheduler.operation_dependencies == {
        first: (),
        second: (),
        parent: (first, second),
    }


def test_operation_dependency_json_preserves_runtime_operation_order(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    dependencies_file = tmp_path / "operation_dependencies.json"
    monkeypatch.setenv(
        "DEFINE_OPERATION_DEPENDENCIES_FILE",
        str(dependencies_file),
    )
    scheduler = tracing.TracingScheduler()
    entry = scheduler.execution_created(None, "test")
    worker = scheduler.execution_created(entry, "worker")
    scheduler.create_completed(entry, "gateway", 1)
    scheduler.create_completed(worker, "scratch", 1)
    scheduler.move_completed(worker, "scratch", "destination", 1)

    tracing.write_operation_dependencies(scheduler.operation_dependencies)

    assert json.loads(dependencies_file.read_text()) == [
        {
            "operation": {
                "execution": {
                    "caller": None,
                    "action_name": "test",
                },
                "operation_name": "create",
                "target": "gateway",
                "occurrence": 1,
            },
            "dependencies": [],
        },
        {
            "operation": {
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
            "dependencies": [
                {
                    "execution": {
                        "caller": None,
                        "action_name": "test",
                    },
                    "operation_name": "create",
                    "target": "gateway",
                    "occurrence": 1,
                }
            ],
        },
        {
            "operation": {
                "execution": {
                    "caller": {
                        "caller": None,
                        "action_name": "test",
                    },
                    "action_name": "worker",
                },
                "operation_name": "move",
                "source": "scratch",
                "target": "destination",
                "occurrence": 1,
            },
            "dependencies": [
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
                }
            ],
        },
    ]


def test_write_operation_dependencies_does_nothing_without_environment_file(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.delenv("DEFINE_OPERATION_DEPENDENCIES_FILE", raising=False)

    tracing.write_operation_dependencies({})
