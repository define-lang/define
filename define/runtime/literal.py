"""Runtime library for literal Python transpilation of Define programs.

See ``define/compiler/operation_graph_execution_design.md`` and ``define/compiler/codegen/literal/python/execution_codegen_design.md`` for the shared design.
"""

from __future__ import annotations

import dataclasses
import itertools
import os
import queue
import threading
from abc import ABC, abstractmethod
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar, Protocol, cast, final, override

if TYPE_CHECKING:
    import types

_REPORT_OCCUPIED_POSITIONS_ENV_VAR = "DEFINE_REPORT_OCCUPIED_POSITIONS"
_MAX_THREADS_ENV_VAR = "DEFINE_MAX_THREADS"

type Task = Callable[[], None]
type Tasks = Sequence[Task]
type DestructionContinuation = Callable[..., None]


@dataclasses.dataclass(slots=True)
class Guarantee:
    """Tasks released when one Automated Action Guarantee is published."""

    inits: list[Task] = dataclasses.field(default_factory=list)
    consumers: list[Task] = dataclasses.field(default_factory=list)

    def publish(
        self,
        scheduler: Scheduler,
        *publication_consumers: Task,
    ):
        """Init Action Executions before releasing ordinary consumers."""
        for init in self.inits:
            init()
        scheduler.continue_with([*publication_consumers, *self.consumers])


class Join:
    """A dependency join that releases its continuation on the final arrival."""

    def __init__(self, arrivals: int):
        """Initialize a join requiring ``arrivals`` arrivals."""
        # CPython's count increment is atomic, including in free-threaded
        # builds. Join intentionally depends on that implementation detail
        # because it avoids lock contention between parallel arrivals.
        self._arrivals: itertools.count[int] = itertools.count(1)
        self._final_arrival: int = arrivals

    def arrive(self) -> bool:
        """Return true exactly once, on the final expected arrival."""
        return next(self._arrivals) == self._final_arrival


@final
class NoJoin(Join):
    """A continuation with no other arrivals to wait for."""

    def __init__(self):  # pyright: ignore[reportMissingSuperCall]
        """Init a continuation that is always ready."""

    @override
    def arrive(self) -> bool:
        return True


NO_JOIN = NoJoin()


@final
class _DestructionContinuationGate:
    """Run one continuation after it and every expected arrival are available."""

    _continuation: types.MethodType | None

    def __init__(self, scheduler: Scheduler, predecessor_count: int):
        # Reaching the callee Destroy is an arrival so earlier predecessor
        # completions cannot need the continuation before it is available.
        self._join = scheduler.create_join(predecessor_count + 1)
        self._continuation = None

    def ready(self, continuation: types.MethodType):
        """Record that the callee reached its Destroy."""
        self._continuation = continuation
        if self._join.arrive():
            continuation()

    def arrive(self):
        """Record one predecessor completion."""
        if self._join.arrive():
            cast("types.MethodType", self._continuation)()


class _DestructionExecution(Protocol):
    destruction_connections: DestructionConnections | None


def continue_destruction(continuation: types.MethodType):
    """Run a destruction continuation through its caller-contributed work."""
    execution = cast("_DestructionExecution", continuation.__self__)
    destruction_continuation = continuation.__func__
    if execution.destruction_connections is None:
        continuation()
        return
    connection = execution.destruction_connections.connection(destruction_continuation)
    if connection is None:
        continuation()
        return
    connection.ready(continuation)


class DestructionConnection:
    """Caller work connected to a callee destruction continuation."""

    _scheduler: Scheduler
    _start_tasks: tuple[types.MethodType, ...]
    # The destruction connection supplied by this Action Execution's caller.
    _forwarded_connection: DestructionConnection | None
    _continuation_gate: _DestructionContinuationGate

    def __init__(
        self,
        scheduler: Scheduler,
        predecessor_count: int,
        *start_tasks: types.MethodType,
        forwarded_connection: DestructionConnection | None = None,
    ):
        """Initialize this connection's work and an optional forwarded connection.

        ``predecessor_count`` is the number of this connection's completion
        arrivals that the callee Destroy must receive before its continuation
        runs. It is zero when the Destroy activates this connection's work but
        does not depend on any completion from that work.
        """
        self._scheduler = scheduler
        self._start_tasks = start_tasks
        self._forwarded_connection = forwarded_connection
        self._continuation_gate = _DestructionContinuationGate(
            scheduler, predecessor_count + (forwarded_connection is not None)
        )

    def ready(self, continuation: types.MethodType):
        """Start connected work and run ``continuation`` when its dependencies complete."""
        self._scheduler.submit_all(self._start_tasks)
        if self._forwarded_connection is not None:
            self._forwarded_connection.ready(self.complete)
        self._continuation_gate.ready(continuation)

    def complete(self):
        """Record one terminal completion from connected work."""
        self._continuation_gate.arrive()


@final
class DestructionConnections:
    """Destruction Connections supplied to an Action Execution by its callers."""

    def __init__(
        self,
        connections_by_continuation: dict[
            DestructionContinuation, DestructionConnection
        ],
        *,
        forwarded: DestructionConnections | None = None,
    ):
        """Combine one caller's connections with those it received from its caller."""
        self._forwarded = forwarded
        self._connections_by_continuation = connections_by_continuation

    def connection(
        self, destruction_continuation: DestructionContinuation
    ) -> DestructionConnection | None:
        """Return the nearest connection for a generated continuation."""
        current: DestructionConnections | None = self
        while current is not None:
            connection = current._connections_by_continuation.get(
                destruction_continuation
            )
            if connection is not None:
                return connection
            current = current._forwarded
        return None


class Scheduler:
    """One execution of a literally transpiled Define program."""

    # The core lifecycle matches the concepts from the Starting Define Programs
    # section of the spec, implemented in start().
    #
    # After creating the view point position and triggering its constructor,
    # that constructor will do some combination of executing in this thread
    # (the same thread that called start()) and submitting concurrent tasks.
    # If the start() thread finishes before the other submitted threads, it
    # waits on _finish_scheduled_work before terminating.
    #
    # Other work arrives via one of the various submit or continue_with methods.
    # Those create worker threads that drain a SimpleQueue for any available work.
    # Threads are spun up only on demand, under the belief that many workloads
    # will not need the full thread pool.
    #
    # We keep track of the total tasks currently running and the tasks in
    # the queue using _unfinished_tasks. The scheduler does not terminate until
    # that number hits 0. This design is fine for our Python implementation,
    # but in any native implementation that single counter would be a serious
    # scalability bottleneck (threading performance would be dominated by cache
    # coherence traffic in the CPU as threads contended for the task counter).
    # The mutex in _condition guards _unfinished_tasks and is used to notify
    # the main thread when there are no remaining tasks. (Only the main thread
    # calls wait().)
    #
    # Scheduler intentionally implements its own work pool instead of using
    # ThreadPoolExecutor. Generated branches can be extremely fine-grained and
    # can submit more branches recursively, so Scheduler must independently track
    # unfinished work and failures even if an executor manages the threads. An
    # executor would additionally allocate and synchronize a Future for every
    # branch, and its public API cannot let the caller execute queued work while
    # waiting. This shared queue and explicit worker lifecycle avoid that
    # duplicate infrastructure and was substantially faster for fine-grained
    # branches in benchmarks.

    def __init__(self, *, max_threads: int | None = None):
        """Initialize a single-use scheduler with a bounded execution thread count."""
        if max_threads is None:
            configured_max_threads = os.environ.get(_MAX_THREADS_ENV_VAR)
            if configured_max_threads is None:
                max_threads = os.process_cpu_count() or 1
            else:
                try:
                    max_threads = int(configured_max_threads)
                except ValueError:
                    raise ValueError(
                        "DEFINE_MAX_THREADS must be a positive integer"
                    ) from None
        if type(max_threads) is not int or max_threads < 1:
            raise ValueError("max_threads must be a positive integer or None")
        self._max_threads: int = max_threads
        self._started: bool = False
        self._queue: queue.SimpleQueue[Task | None] = queue.SimpleQueue()
        self._workers: list[threading.Thread] = []
        self._idle_workers: threading.Semaphore = threading.Semaphore(0)
        self._condition: threading.Condition = threading.Condition()
        self._unfinished_tasks: int = 0
        self._failure: Exception | None = None

    def create_join(self, arrivals: int) -> Join:
        """Create a dependency join for generated work."""
        return Join(arrivals)

    def submit(self, task: Task):
        """Make a generated parallel branch available for execution."""
        worker: threading.Thread | None = None
        # Normally, _condition only gates _unfinished_tasks. However, we also
        # need some mutex to reserve permission to create a new worker. We
        # could make a whole separate mutex, but it would be just for this
        # one location, so might as well just re-use _condition.
        with self._condition:
            self._unfinished_tasks += 1
            if (
                # There is no idle worker that can accept this job.
                not self._idle_workers.acquire(blocking=False)
                # We are not at our limit of workers.
                and len(self._workers) < self._max_threads - 1
            ):
                worker = threading.Thread(target=self._worker, daemon=True)
                self._workers.append(worker)
        if worker is not None:
            worker.start()
        self._queue.put(task)

    def submit_all(self, methods: Tasks):
        """Make every bound method available for parallel execution."""
        for method in methods:
            self.submit(method)

    def continue_with(self, methods: Tasks):
        """Submit all but one bound method and run the final one directly."""
        if not methods:
            return
        for index in range(len(methods) - 1):
            self.submit(methods[index])
        methods[-1]()

    def execution_created(
        self,
        _caller: object | None,
        _action_name: str,
        /,
    ) -> object | None:
        """Observe creation of an Action Execution."""
        return None

    def create_completed(
        self,
        _execution: object | None,
        _position_name: str,
        _occurrence: int,
        /,
    ):
        """Observe completion of a Create."""

    def move_completed(
        self,
        _execution: object | None,
        _source_name: str,
        _destination_name: str,
        _occurrence: int,
        /,
    ):
        """Observe completion of a Move."""

    def destroy_completed(
        self,
        _execution: object | None,
        _position_name: str,
        _occurrence: int,
        /,
    ):
        """Observe completion of a Destroy."""

    def start(self, entry_point: type[EntryPoint]):
        """Execute the Define program startup sequence once."""
        if self._started:
            raise RuntimeError("a Scheduler instance can only be started once")
        self._started = True
        view_point_position = LocalPosition(
            "position<view_point>", constraints=(entry_point,), scheduler=self
        )
        try:
            view_point_position.create_particle()
            view_point_position.particle.get_action(entry_point).execute(self)
        except Exception as exception:  # noqa: BLE001
            # Scheduler must finish and close workers before re-raising the failure.
            self._record_failure(exception)
        self._finish_scheduled_work()
        self._close_workers()
        if self._failure is not None:
            raise self._failure
        occupied_positions_file = os.environ.get(_REPORT_OCCUPIED_POSITIONS_ENV_VAR)
        if occupied_positions_file is not None:
            occupied_names = view_point_position.particle.occupied_position_names()
            _ = Path(occupied_positions_file).write_text(
                "".join(f"{chained_name}\n" for chained_name in occupied_names)
            )

    def _worker(self):
        while True:
            task = self._queue.get()
            # Sending None is how we signal the thread to shut down.
            if task is None:
                return
            self._run_task(task)
            self._idle_workers.release()

    def _run_task(self, task: Task):
        try:
            if self._failure is None:
                task()
        except Exception as exception:  # noqa: BLE001
            # Exceptions cannot propagate directly from a worker to the primary thread.
            self._record_failure(exception)
        finally:
            with self._condition:
                self._unfinished_tasks -= 1
                self._condition.notify()

    def _record_failure(self, exception: Exception):
        with self._condition:
            if self._failure is None:
                self._failure = exception

    def _finish_scheduled_work(self):
        while True:
            if not self._queue.empty():
                # The try/except exists only for the race where a worker
                # takes the final task after empty() reports false. Since
                # Python 3.11, entering a try that throws no exception is free.
                # However, throwing the exception is expensive, which is why we
                # do the cheaper empty() check above, first.
                try:
                    task = self._queue.get_nowait()
                except queue.Empty:
                    pass
                else:
                    self._run_task(cast("Task", task))
                    continue
            with self._condition:
                if self._unfinished_tasks == 0:
                    return
                _ = self._condition.wait()

    def _close_workers(self):
        for _ in self._workers:
            self._queue.put(None)
        for worker in self._workers:
            worker.join()


class DefineRuntimeError(Exception):
    """Base class for Define runtime errors."""

    message_format: ClassVar[str]

    def __init__(self, position_name: str):
        """Initialize with the position name and format the message."""
        self.position_name: str = position_name
        super().__init__(self.message_format.format(self=self))


class ParticleExistsError(DefineRuntimeError):
    """Raised when creating a particle in a position that already has one."""

    message_format: ClassVar[str] = (
        "Position '{self.position_name}' already contains a particle."
    )


class NoParticleError(DefineRuntimeError):
    """Raised when moving a particle from a position that has none."""

    message_format: ClassVar[str] = (
        "Position '{self.position_name}' does not contain a particle."
    )


class UnsatisfiedConstraintError(DefineRuntimeError):
    """Raised when moving a particle to a position whose constraints are not met."""

    message_format: ClassVar[str] = (
        "Cannot move particle to '{self.position_name}':"
        " unsatisfied constraint '{self.constraint_name}'."
    )

    def __init__(self, position_name: str, constraint_name: str):
        """Initialize with the destination position name and unsatisfied constraint name."""
        self.constraint_name: str = constraint_name
        super().__init__(position_name)


class DuplicateConstraintError(DefineRuntimeError):
    """Raised when a position declares the same quality as a constraint twice."""

    message_format: ClassVar[str] = (
        "Quality '{self.position_name}' is declared as a constraint more than once."
    )


class Quality:
    """A global position or action assigned to a particle."""

    TYPE_NAME: ClassVar[str]
    implied_qualities: ClassVar[tuple[type[Quality], ...]] = ()

    def __init__(self, on_particle: Particle):
        """Initialize with the particle this quality is assigned to."""
        self._on_particle: Particle = on_particle

    @classmethod
    def full_name(cls) -> str:
        """Return the runtime name derived from the full Python class path."""
        return f"{cls.TYPE_NAME}<{cls.__module__}.{cls.__name__}>"

    @property
    def name(self) -> str:
        """Return the Define name derived from this quality's Python class."""
        return type(self).full_name()

    @property
    def on_particle(self) -> Particle:
        """Return the particle this quality is assigned to."""
        return self._on_particle


class Particle:
    """A particle in the Define universe."""

    def __init__(self, scheduler: Scheduler | None = None):
        """Initialize with empty positions and actions dictionaries."""
        self._scheduler: Scheduler = scheduler if scheduler is not None else Scheduler()
        self._positions: dict[type[GlobalPosition], GlobalPosition] = {}
        self._actions: dict[type[Action], Action] = {}
        self._assigned_qualities: list[Quality] = []

    @property
    def scheduler(self) -> Scheduler:
        """Return the Scheduler executing operations on this particle."""
        return self._scheduler

    def assign_position(self, position_class: type[GlobalPosition]):
        """Assign a position to this particle, or do nothing if already present."""
        # A quality is set at most once; a repeat assignment (e.g. a constraint
        # also reached through another constraint's implication) is a no-op.
        # Genuinely duplicate constraints are rejected when a position is built.
        if position_class in self._positions:
            return
        self._assign_implied_qualities(position_class)
        position = position_class(self)
        self._assigned_qualities.append(position)
        self._positions[position_class] = position

    def assign_action(self, action_class: type[Action]):
        """Assign an action to this particle, or do nothing if already present."""
        if action_class in self._actions:
            return
        self._assign_implied_qualities(action_class)
        action = action_class(self)
        self._assigned_qualities.append(action)
        self._actions[action_class] = action

    def _assign_implied_qualities(self, quality_class: type[Quality]):
        for implied_class in quality_class.implied_qualities:
            if issubclass(implied_class, GlobalPosition):
                self.assign_position(implied_class)
            elif issubclass(implied_class, Action):
                self.assign_action(implied_class)

    def get_position[PositionType: GlobalPosition](
        self, position_class: type[PositionType]
    ) -> PositionType:
        """Return the assigned position of the given type."""
        return cast("PositionType", self._positions[position_class])

    def get_action[ActionType: Action](
        self, action_class: type[ActionType]
    ) -> ActionType:
        """Return the assigned action of the given type."""
        return cast("ActionType", self._actions[action_class])

    # TODO: Cache this?
    @property
    def quality_types(self) -> frozenset[type[Quality]]:
        """Return the set of constraint types satisfied by this particle."""
        return frozenset(type(q) for q in self._assigned_qualities)

    def occupied_position_names(self) -> list[str]:
        """Return chained names of occupied positions reachable from this particle.

        Names are returned depth-first, each parent position before the
        positions nested within its particle, in quality-assignment order.
        """
        # TODO: Render occupied position names with Define syntax instead of
        # Python class paths.
        return self._occupied_position_names(())

    def _occupied_position_names(self, prefix: tuple[str, ...]) -> list[str]:
        names: list[str] = []
        for quality in self._assigned_qualities:
            if isinstance(quality, GlobalPosition):
                chain = (*prefix, quality.name)
                if quality.has_particle:
                    names.append("::".join(chain))
                    names.extend(quality.particle._occupied_position_names(chain))
            elif isinstance(quality, Action):
                action_chain = (*prefix, quality.name)
                for interface_position in quality.interface_positions:
                    chain = (*action_chain, interface_position.name)
                    if interface_position.has_particle:
                        names.append("::".join(chain))
                        names.extend(
                            interface_position.particle._occupied_position_names(chain)
                        )
        return names


class Position(ABC):
    """Abstract base class for positions that can contain a particle."""

    _particle: Particle | None = None

    @property
    @abstractmethod
    def scheduler(self) -> Scheduler:
        """Return the Scheduler executing operations on this position."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the name of this position."""

    @abstractmethod
    def _get_constraints(self) -> tuple[type[Quality], ...]:
        """Return the constraint types for this position."""

    @property
    def has_particle(self) -> bool:
        """Return whether this position contains a particle."""
        return self._particle is not None

    @property
    def particle(self) -> Particle:
        """Return the particle, raising NoParticleError if none exists."""
        if self._particle is None:
            raise NoParticleError(self.name)
        return self._particle

    def create_particle(self):
        """Create a particle in this position. Raises if one exists."""
        if self._particle is not None:
            raise ParticleExistsError(self.name)
        self._particle = Particle(self.scheduler)
        for constraint_type in self._get_constraints():
            if issubclass(constraint_type, GlobalPosition):
                self._particle.assign_position(constraint_type)
            elif issubclass(constraint_type, Action):
                self._particle.assign_action(constraint_type)
        self._after_particle_arrived()

    def move_particle_to(self, destination: Position):
        """Move the particle from this position to destination."""
        if self._particle is None:
            raise NoParticleError(self.name)
        if destination._particle is not None:
            raise ParticleExistsError(destination.name)
        for constraint_type in destination._get_constraints():
            if constraint_type not in self._particle.quality_types:
                raise UnsatisfiedConstraintError(
                    destination.name, constraint_type.full_name()
                )
        destination._particle = self._particle
        self._particle = None
        destination._after_particle_arrived()

    def destroy_particle(self):
        """Destroy the particle in this position."""
        if self._particle is None:
            raise NoParticleError(self.name)
        self._particle = None

    def _after_particle_arrived(self):  # noqa: B027
        """Run after a particle arrives. Override in subclasses."""


def _reject_duplicate_constraints(constraints: tuple[type[Quality], ...]):
    """Raise if the same quality appears more than once in a constraint list."""
    seen: set[type[Quality]] = set()
    for constraint in constraints:
        if constraint in seen:
            raise DuplicateConstraintError(constraint.full_name())
        seen.add(constraint)


class GlobalPosition(Quality, Position):
    """A globally-defined position with constraints."""

    constraints: ClassVar[tuple[type[Quality], ...]] = ()
    TYPE_NAME: ClassVar[str] = "position"

    @property
    @override
    def scheduler(self) -> Scheduler:
        """Return the Scheduler executing operations on this position."""
        return self.on_particle.scheduler

    def __init_subclass__(cls, **kwargs: object):
        """Reject duplicate constraints when a global position class is defined."""
        super().__init_subclass__(**kwargs)
        _reject_duplicate_constraints(cls.constraints)

    @override
    def _get_constraints(self) -> tuple[type[Quality], ...]:
        """Return the constraint types from the class variable."""
        return type(self).constraints


class LocalPosition(Position):
    """A locally-defined position with a runtime name and optional constraints."""

    def __init__(
        self,
        name: str,
        constraints: tuple[type[Quality], ...] = (),
        *,
        scheduler: Scheduler,
    ):
        """Initialize a local position in the given scheduler."""
        super().__init__()
        _reject_duplicate_constraints(constraints)
        self._name: str = name
        self._constraints: tuple[type[Quality], ...] = constraints
        self._scheduler: Scheduler = scheduler

    @property
    @override
    def scheduler(self) -> Scheduler:
        """Return the Scheduler executing operations on this position."""
        return self._scheduler

    @property
    @override
    def name(self) -> str:
        """Return the name of this position."""
        return self._name

    @override
    def _get_constraints(self) -> tuple[type[Quality], ...]:
        """Return the constraint types for this position."""
        return self._constraints


class Action(Quality):
    """A globally-defined action."""

    TYPE_NAME: ClassVar[str] = "action"

    def __init__(
        self,
        on_particle: Particle,
        interface_positions: Sequence[LocalPosition] = (),
    ):
        """Initialize with the assigned particle and its interface positions."""
        super().__init__(on_particle)
        self._interface_positions: dict[str, LocalPosition] = {
            position.name: position for position in interface_positions
        }

    def get_interface_position(self, name: str) -> LocalPosition:
        """Return the interface position with the given name."""
        return self._interface_positions[name]

    @property
    def interface_positions(self) -> tuple[LocalPosition, ...]:
        """Return this action's interface positions, in declaration order."""
        return tuple(self._interface_positions.values())


class EntryPoint(Action):
    """An action that starts a Scheduler."""

    def execute(self, _scheduler: Scheduler) -> None:
        """Execute this entry point."""
        raise NotImplementedError


def start(entry_point: type[EntryPoint], scheduler: Scheduler | None = None):
    """Execute the Define program startup sequence (DLP 33).

    Creates the anonymous view point position and particle, assigns the entry
    action, and executes it.
    """
    if scheduler is None:
        scheduler = Scheduler()
    scheduler.start(entry_point)
