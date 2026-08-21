import os
import queue
import threading
from typing import ClassVar, override

import pytest

from define.runtime import literal


class _ContinuationExecution:
    destruction_connections: literal.DestructionConnections | None = None
    _continuation: literal.Task

    def __init__(self, continuation: literal.Task):
        self._continuation = continuation

    def first_continuation(self):
        self._continuation()

    def second_continuation(self):
        pass

    def absent_continuation(self):
        pass


def _assert_execution_thread_count(
    scheduler: literal.Scheduler,
    expected_count: int,
):
    barrier = threading.Barrier(expected_count)
    execution_threads: set[int] = set()
    execution_threads_lock = threading.Lock()

    def branch():
        with execution_threads_lock:
            execution_threads.add(threading.get_ident())
        _ = barrier.wait()

    class Entry(literal.EntryPoint):
        typed_name: ClassVar[str] = "action<entry>"

        @override
        def execute(self, scheduler: literal.Scheduler):
            for _ in range(expected_count - 1):
                scheduler.submit(branch)
            branch()

    scheduler.start(Entry)

    assert len(execution_threads) == expected_count


class TestScheduler:
    def test_default_max_threads_uses_environment(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setenv("DEFINE_MAX_THREADS", "2")

        _assert_execution_thread_count(literal.Scheduler(), 2)

    def test_explicit_max_threads_overrides_environment(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setenv("DEFINE_MAX_THREADS", "1")

        _assert_execution_thread_count(literal.Scheduler(max_threads=2), 2)

    @pytest.mark.parametrize("value", ["invalid", "0", "-1"])
    def test_rejects_invalid_environment_max_threads(
        self,
        monkeypatch: pytest.MonkeyPatch,
        value: str,
    ):
        monkeypatch.setenv("DEFINE_MAX_THREADS", value)

        with pytest.raises(ValueError, match="positive integer"):
            _ = literal.Scheduler()

    def test_default_max_threads_uses_process_count(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setattr(os, "process_cpu_count", lambda: 3)

        _assert_execution_thread_count(literal.Scheduler(), 3)

    @pytest.mark.parametrize("value", [0, -1])
    def test_rejects_invalid_max_threads(self, value: int):
        with pytest.raises(ValueError, match="positive integer"):
            _ = literal.Scheduler(max_threads=value)

    def test_scheduler_is_single_use(self):
        class Entry(literal.EntryPoint):
            typed_name: ClassVar[str] = "action<entry>"

            @override
            def execute(self, scheduler: literal.Scheduler):
                pass

        scheduler = literal.Scheduler(max_threads=1)
        scheduler.start(Entry)

        with pytest.raises(RuntimeError, match="only be started once"):
            scheduler.start(Entry)

    def test_calling_thread_counts_toward_max_threads(self):
        _assert_execution_thread_count(literal.Scheduler(max_threads=3), 3)

    def test_one_thread_drains_submitted_work_without_workers(self):
        scheduler = literal.Scheduler(max_threads=1)
        caller_thread = threading.get_ident()
        execution_threads: list[int] = []

        class Entry(literal.EntryPoint):
            typed_name: ClassVar[str] = "action<entry>"

            @override
            def execute(self, scheduler: literal.Scheduler):
                scheduler.submit(
                    lambda: execution_threads.append(threading.get_ident())
                )

        scheduler.start(Entry)

        assert execution_threads == [caller_thread]

    def test_worker_failure_is_raised_on_calling_thread(self):
        scheduler = literal.Scheduler(max_threads=2)

        def fail():
            raise ValueError("worker failed")

        class Entry(literal.EntryPoint):
            typed_name: ClassVar[str] = "action<entry>"

            @override
            def execute(self, scheduler: literal.Scheduler):
                scheduler.submit(fail)

        with pytest.raises(ValueError, match="worker failed"):
            scheduler.start(Entry)

    def test_continue_with_submits_all_but_the_final_method(self):
        scheduler = literal.Scheduler(max_threads=1)
        calls: list[str] = []

        def submitted():
            calls.append("submitted")

        def direct():
            calls.append("direct")

        class Entry(literal.EntryPoint):
            typed_name: ClassVar[str] = "action<entry>"

            @override
            def execute(self, scheduler: literal.Scheduler):
                scheduler.continue_with((submitted, direct))

        scheduler.start(Entry)

        assert calls == ["direct", "submitted"]

    def test_submit_all_submits_every_method(self):
        scheduler = literal.Scheduler(max_threads=1)
        calls: list[str] = []

        def first():
            calls.append("first")

        def second():
            calls.append("second")

        class Entry(literal.EntryPoint):
            typed_name: ClassVar[str] = "action<entry>"

            @override
            def execute(self, scheduler: literal.Scheduler):
                scheduler.submit_all((first, second))

        scheduler.start(Entry)

        assert calls == ["first", "second"]

    def test_default_operation_tracing_hooks_are_no_ops(self):
        scheduler = literal.Scheduler()

        execution = scheduler.execution_created(
            None,
            "test",
        )
        scheduler.create_completed(execution, "item", 1)
        scheduler.move_completed(execution, "item", "destination", 1)
        scheduler.destroy_completed(execution, "destination", 1)

        assert execution is None

    def test_simultaneous_submissions_execute_once_within_thread_limit(self):
        scheduler = literal.Scheduler(max_threads=5)
        submit_together = threading.Barrier(5)
        execution_threads: set[int] = set()
        execution_counts = [0] * 400
        results_lock = threading.Lock()

        def child(index: int):
            with results_lock:
                execution_threads.add(threading.get_ident())
                execution_counts[index] += 1

        def producer(offset: int):
            _ = submit_together.wait()
            for index in range(offset, offset + 100):
                scheduler.submit(lambda index=index: child(index))

        class Entry(literal.EntryPoint):
            typed_name: ClassVar[str] = "action<entry>"

            @override
            def execute(self, scheduler: literal.Scheduler):
                for offset in range(0, 400, 100):
                    scheduler.submit(lambda offset=offset: producer(offset))
                _ = submit_together.wait()

        scheduler.start(Entry)

        assert execution_counts == [1] * 400
        assert len(execution_threads) <= 5

    def test_recursively_submitted_tasks_finish_before_start_returns(self):
        scheduler = literal.Scheduler(max_threads=4)
        remaining = 1_000
        calls = 0
        state_lock = threading.Lock()

        def task():
            nonlocal calls, remaining
            with state_lock:
                calls += 1
                remaining -= 1
                submit_another = remaining > 0
            if submit_another:
                scheduler.submit(task)

        class Entry(literal.EntryPoint):
            typed_name: ClassVar[str] = "action<entry>"

            @override
            def execute(self, scheduler: literal.Scheduler):
                scheduler.submit(task)

        scheduler.start(Entry)

        assert calls == 1_000

    def test_idle_worker_is_reused(self, monkeypatch: pytest.MonkeyPatch):
        original_semaphore = threading.Semaphore
        idle_worker_available = threading.Event()

        class ObservedSemaphore:
            def __init__(self, value: int):
                self.semaphore: threading.Semaphore = original_semaphore(value)

            def acquire(self, *, blocking: bool = True):
                return self.semaphore.acquire(blocking=blocking)

            def release(self):
                self.semaphore.release()
                idle_worker_available.set()

        monkeypatch.setattr(threading, "Semaphore", ObservedSemaphore)
        scheduler = literal.Scheduler(max_threads=3)
        finish_together = threading.Barrier(2)
        child_finished = threading.Event()
        first_thread: list[int] = []
        child_thread: list[int] = []

        def first():
            first_thread.append(threading.get_ident())
            _ = finish_together.wait()

        def child():
            child_thread.append(threading.get_ident())
            child_finished.set()

        def submitter():
            _ = finish_together.wait()
            _ = idle_worker_available.wait()
            scheduler.submit(child)
            _ = child_finished.wait()

        class Entry(literal.EntryPoint):
            typed_name: ClassVar[str] = "action<entry>"

            @override
            def execute(self, scheduler: literal.Scheduler):
                scheduler.submit(first)
                scheduler.submit(submitter)
                _ = child_finished.wait()

        scheduler.start(Entry)

        assert child_thread == first_thread

    def test_empty_queue_does_not_finish_while_worker_can_submit(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        original_simple_queue = queue.SimpleQueue
        queue_observed_empty = threading.Event()

        class EmptyObservingQueue:
            def __init__(self):
                self.tasks: queue.SimpleQueue[literal.Task | None] = (
                    original_simple_queue()
                )

            def empty(self):
                empty = self.tasks.empty()
                if empty:
                    queue_observed_empty.set()
                return empty

            def get(self):
                return self.tasks.get()

            def get_nowait(self):
                return self.tasks.get_nowait()

            def put(self, task: literal.Task | None):
                self.tasks.put(task)

        monkeypatch.setattr(queue, "SimpleQueue", EmptyObservingQueue)
        scheduler = literal.Scheduler(max_threads=2)
        parent_started = threading.Event()
        calls: list[str] = []

        def child():
            calls.append("child")

        def parent():
            parent_started.set()
            _ = queue_observed_empty.wait()
            scheduler.submit(child)
            calls.append("parent")

        class Entry(literal.EntryPoint):
            typed_name: ClassVar[str] = "action<entry>"

            @override
            def execute(self, scheduler: literal.Scheduler):
                scheduler.submit(parent)
                _ = parent_started.wait()

        scheduler.start(Entry)

        assert sorted(calls) == ["child", "parent"]

    def test_completion_before_condition_wait_is_not_lost(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        original_simple_queue = queue.SimpleQueue
        finish_task = threading.Event()
        worker_requested_more_work = threading.Event()

        class CompletionObservingQueue:
            def __init__(self):
                self.tasks: queue.SimpleQueue[literal.Task | None] = (
                    original_simple_queue()
                )
                self.worker_gets: int = 0
                self.worker_gets_lock: threading.Lock = threading.Lock()

            def empty(self):
                empty = self.tasks.empty()
                if empty:
                    finish_task.set()
                    _ = worker_requested_more_work.wait()
                return empty

            def get(self):
                with self.worker_gets_lock:
                    self.worker_gets += 1
                    if self.worker_gets == 2:
                        worker_requested_more_work.set()
                return self.tasks.get()

            def get_nowait(self):
                return self.tasks.get_nowait()

            def put(self, task: literal.Task | None):
                self.tasks.put(task)

        monkeypatch.setattr(queue, "SimpleQueue", CompletionObservingQueue)
        scheduler = literal.Scheduler(max_threads=2)
        task_started = threading.Event()

        def task():
            task_started.set()
            _ = finish_task.wait()

        class Entry(literal.EntryPoint):
            typed_name: ClassVar[str] = "action<entry>"

            @override
            def execute(self, scheduler: literal.Scheduler):
                scheduler.submit(task)
                _ = task_started.wait()

        scheduler.start(Entry)

    def test_worker_winning_empty_queue_race_does_not_lose_task(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        original_simple_queue = queue.SimpleQueue
        allow_worker_get = threading.Event()
        worker_got_task = threading.Event()

        class RacingQueue:
            def __init__(self):
                self.tasks: queue.SimpleQueue[literal.Task | None] = (
                    original_simple_queue()
                )

            def empty(self):
                empty = self.tasks.empty()
                if not empty:
                    allow_worker_get.set()
                    _ = worker_got_task.wait()
                return empty

            def get(self):
                _ = allow_worker_get.wait()
                task = self.tasks.get()
                worker_got_task.set()
                return task

            def get_nowait(self):
                return self.tasks.get_nowait()

            def put(self, task: literal.Task | None):
                self.tasks.put(task)

        monkeypatch.setattr(queue, "SimpleQueue", RacingQueue)
        scheduler = literal.Scheduler(max_threads=2)
        calls: list[str] = []

        class Entry(literal.EntryPoint):
            typed_name: ClassVar[str] = "action<entry>"

            @override
            def execute(self, scheduler: literal.Scheduler):
                scheduler.submit(lambda: calls.append("task"))

        scheduler.start(Entry)

        assert calls == ["task"]

    def test_simultaneous_worker_failures_raise_one_failure(self):
        scheduler = literal.Scheduler(max_threads=3)
        fail_together = threading.Barrier(3)

        def fail(exception: Exception):
            _ = fail_together.wait()
            raise exception

        class Entry(literal.EntryPoint):
            typed_name: ClassVar[str] = "action<entry>"

            @override
            def execute(self, scheduler: literal.Scheduler):
                scheduler.submit(lambda: fail(ValueError("first")))
                scheduler.submit(lambda: fail(RuntimeError("second")))
                _ = fail_together.wait()

        with pytest.raises((ValueError, RuntimeError)):
            scheduler.start(Entry)

    def test_primary_failure_accounts_for_queued_tasks(self):
        scheduler = literal.Scheduler(max_threads=1)
        calls: list[str] = []

        class Entry(literal.EntryPoint):
            typed_name: ClassVar[str] = "action<entry>"

            @override
            def execute(self, scheduler: literal.Scheduler):
                for _ in range(100):
                    scheduler.submit(lambda: calls.append("task"))
                raise AssertionError("primary failed")

        with pytest.raises(AssertionError, match="primary failed"):
            scheduler.start(Entry)

        assert calls == []

    def test_worker_is_closed_after_failure(self):
        scheduler = literal.Scheduler(max_threads=2)
        execution_threads: list[threading.Thread] = []
        failure_started = threading.Event()

        def fail():
            execution_threads.append(threading.current_thread())
            failure_started.set()
            raise AssertionError("worker failed")

        class Entry(literal.EntryPoint):
            typed_name: ClassVar[str] = "action<entry>"

            @override
            def execute(self, scheduler: literal.Scheduler):
                scheduler.submit(fail)
                _ = failure_started.wait()

        with pytest.raises(AssertionError, match="worker failed"):
            scheduler.start(Entry)

        assert len(execution_threads) == 1
        assert not execution_threads[0].is_alive()

    def test_worker_is_closed_after_success(self):
        scheduler = literal.Scheduler(max_threads=2)
        execution_threads: list[threading.Thread] = []
        worker_finished = threading.Event()

        def finish():
            execution_threads.append(threading.current_thread())
            worker_finished.set()

        class Entry(literal.EntryPoint):
            typed_name: ClassVar[str] = "action<entry>"

            @override
            def execute(self, scheduler: literal.Scheduler):
                scheduler.submit(finish)
                _ = worker_finished.wait()

        scheduler.start(Entry)

        assert len(execution_threads) == 1
        assert not execution_threads[0].is_alive()


class TestJoin:
    def test_final_arrival_returns_true_once(self):
        join = literal.Join(3)

        assert not join.arrive()
        assert not join.arrive()
        assert join.arrive()

    def test_concurrent_arrivals_release_once(self):
        join = literal.Join(32)
        arrive_together = threading.Barrier(32)
        arrivals: list[bool] = []

        def arrive():
            _ = arrive_together.wait()
            arrivals.append(join.arrive())

        threads = [threading.Thread(target=arrive) for _ in range(32)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        assert arrivals.count(True) == 1
        assert arrivals.count(False) == 31


class TestDestructionConnection:
    def test_connection_starts_nonblocking_work_without_delaying_continuation(self):
        calls: list[str] = []

        class Entry(literal.EntryPoint):
            typed_name: ClassVar[str] = "action<entry>"

            @override
            def execute(self, scheduler: literal.Scheduler):
                connection = literal.DestructionConnection(
                    scheduler,
                    _ContinuationExecution.first_continuation,
                    0,
                    lambda: calls.append("work"),
                )
                connection.ready(
                    _ContinuationExecution(
                        lambda: calls.append("continuation")
                    ).first_continuation
                )

        literal.Scheduler(max_threads=1).start(Entry)

        assert calls == ["continuation", "work"]

    def test_nonblocking_connection_still_waits_for_forwarded_work(self):
        calls: list[str] = []

        class Entry(literal.EntryPoint):
            typed_name: ClassVar[str] = "action<entry>"

            @override
            def execute(self, scheduler: literal.Scheduler):
                destruction_continuation = _ContinuationExecution.first_continuation

                def forwarded_work():
                    calls.append("forwarded")
                    forwarded_connection.complete()

                forwarded_connection = literal.DestructionConnection(
                    scheduler,
                    destruction_continuation,
                    1,
                    forwarded_work,
                )
                local_connection = literal.DestructionConnection(
                    scheduler,
                    destruction_continuation,
                    0,
                    lambda: calls.append("local"),
                    forwarded_connection=forwarded_connection,
                )
                local_connection.ready(
                    _ContinuationExecution(
                        lambda: calls.append("continuation")
                    ).first_continuation
                )

        literal.Scheduler(max_threads=1).start(Entry)

        assert calls == ["forwarded", "continuation", "local"]

    def test_connection_waits_for_every_terminal_completion(self):
        calls: list[str] = []

        class Entry(literal.EntryPoint):
            typed_name: ClassVar[str] = "action<entry>"

            @override
            def execute(self, scheduler: literal.Scheduler):
                def first():
                    calls.append("first")
                    connection.complete()

                def second():
                    calls.append("second")
                    connection.complete()

                connection = literal.DestructionConnection(
                    scheduler,
                    _ContinuationExecution.first_continuation,
                    2,
                    first,
                    second,
                )
                connection.ready(
                    _ContinuationExecution(
                        lambda: calls.append("continuation")
                    ).first_continuation
                )

        literal.Scheduler(max_threads=2).start(Entry)

        assert set(calls[:2]) == {"first", "second"}
        assert calls[2] == "continuation"

    def test_connection_composes_local_and_forwarded_work(self):
        calls: list[str] = []

        class Entry(literal.EntryPoint):
            typed_name: ClassVar[str] = "action<entry>"

            @override
            def execute(self, scheduler: literal.Scheduler):
                destruction_continuation = _ContinuationExecution.first_continuation

                def higher_work():
                    calls.append("higher")
                    higher_connection.complete()

                higher_connection = literal.DestructionConnection(
                    scheduler,
                    destruction_continuation,
                    1,
                    higher_work,
                )

                def local_work():
                    calls.append("local")
                    local_connection.complete()

                local_connection = literal.DestructionConnection(
                    scheduler,
                    destruction_continuation,
                    1,
                    local_work,
                    forwarded_connection=higher_connection,
                )
                local_connection.ready(
                    _ContinuationExecution(
                        lambda: calls.append("continuation")
                    ).first_continuation
                )

        literal.Scheduler(max_threads=2).start(Entry)

        assert set(calls[:2]) == {"local", "higher"}
        assert calls[2] == "continuation"

    def test_connection_layers_override_only_their_local_continuations(self):
        scheduler = literal.Scheduler(max_threads=1)
        first_continuation = _ContinuationExecution.first_continuation
        second_continuation = _ContinuationExecution.second_continuation
        absent_continuation = _ContinuationExecution.absent_continuation
        first = literal.DestructionConnection(
            scheduler,
            first_continuation,
            1,
            lambda: None,
        )
        second = literal.DestructionConnection(
            scheduler,
            second_continuation,
            1,
            lambda: None,
        )
        direct = literal.DestructionConnections(first)
        local = literal.DestructionConnections(second, direct=direct)

        assert local.connection(first_continuation) is first
        assert local.connection(second_continuation) is second
        assert local.connection(absent_continuation) is None

    def test_connection_starts_tasks_concurrently(self):
        calls: list[str] = []
        first_started = threading.Event()
        second_started = threading.Event()

        class Entry(literal.EntryPoint):
            typed_name: ClassVar[str] = "action<entry>"

            @override
            def execute(self, scheduler: literal.Scheduler):
                def first():
                    first_started.set()
                    assert second_started.wait(timeout=5)
                    calls.append("first")
                    connection.complete()

                def second():
                    assert first_started.wait(timeout=5)
                    second_started.set()
                    calls.append("second")
                    connection.complete()

                connection = literal.DestructionConnection(
                    scheduler,
                    _ContinuationExecution.first_continuation,
                    2,
                    first,
                    second,
                )
                connection.ready(
                    _ContinuationExecution(
                        lambda: calls.append("continuation")
                    ).first_continuation
                )

        literal.Scheduler(max_threads=2).start(Entry)

        assert set(calls[:2]) == {"first", "second"}
        assert calls[2] == "continuation"

    def test_connection_starts_forwarded_layers_concurrently(self):
        calls: list[str] = []
        local_started = threading.Event()
        forwarded_started = threading.Event()

        class Entry(literal.EntryPoint):
            typed_name: ClassVar[str] = "action<entry>"

            @override
            def execute(self, scheduler: literal.Scheduler):
                destruction_continuation = _ContinuationExecution.first_continuation

                def forwarded_work():
                    forwarded_started.set()
                    assert local_started.wait(timeout=5)
                    calls.append("forwarded")
                    forwarded_connection.complete()

                forwarded_connection = literal.DestructionConnection(
                    scheduler,
                    destruction_continuation,
                    1,
                    forwarded_work,
                )

                def local_work():
                    local_started.set()
                    assert forwarded_started.wait(timeout=5)
                    calls.append("local")
                    local_connection.complete()

                local_connection = literal.DestructionConnection(
                    scheduler,
                    destruction_continuation,
                    1,
                    local_work,
                    forwarded_connection=forwarded_connection,
                )
                local_connection.ready(
                    _ContinuationExecution(
                        lambda: calls.append("continuation")
                    ).first_continuation
                )

        literal.Scheduler(max_threads=2).start(Entry)

        assert set(calls[:2]) == {"local", "forwarded"}
        assert calls[2] == "continuation"

    def test_continuation_runs_directly_without_connections(self):
        calls: list[str] = []

        class Entry(literal.EntryPoint):
            typed_name: ClassVar[str] = "action<entry>"
            destruction_connections: literal.DestructionConnections | None = None

            def continue_destroy(self):
                calls.append("continuation")

            @override
            def execute(self, _scheduler: literal.Scheduler):
                literal.continue_destruction(self.continue_destroy)

        literal.Scheduler(max_threads=1).start(Entry)

        assert calls == ["continuation"]

    def test_continuation_runs_directly_without_a_matching_connection(self):
        calls: list[str] = []

        class Entry(literal.EntryPoint):
            typed_name: ClassVar[str] = "action<entry>"
            destruction_connections: literal.DestructionConnections | None = None

            def continue_destroy(self):
                calls.append("continuation")

            def continue_other_destroy(self):
                calls.append("other continuation")

            @override
            def execute(self, scheduler: literal.Scheduler):
                def other_work():
                    calls.append("other work")
                    other_connection.complete()

                other_connection = literal.DestructionConnection(
                    scheduler,
                    Entry.continue_other_destroy,
                    1,
                    other_work,
                )
                self.destruction_connections = literal.DestructionConnections(
                    other_connection
                )
                literal.continue_destruction(self.continue_destroy)
                literal.continue_destruction(self.continue_other_destroy)

        literal.Scheduler(max_threads=1).start(Entry)

        assert calls == ["continuation", "other work", "other continuation"]

    def test_continuation_forwards_one_connection(self):
        calls: list[str] = []

        class Entry(literal.EntryPoint):
            typed_name: ClassVar[str] = "action<entry>"
            destruction_connections: literal.DestructionConnections | None = None

            def continue_destroy(self):
                calls.append("continuation")

            @override
            def execute(self, scheduler: literal.Scheduler):
                def work():
                    calls.append("work")
                    connection.complete()

                connection = literal.DestructionConnection(
                    scheduler,
                    Entry.continue_destroy,
                    1,
                    work,
                )
                self.destruction_connections = literal.DestructionConnections(
                    connection
                )
                literal.continue_destruction(self.continue_destroy)

        literal.Scheduler(max_threads=1).start(Entry)

        assert calls == ["work", "continuation"]
