"""Summarize a Tachyon wall profile as per-thread runs of work and waiting."""

from __future__ import annotations

import collections
import itertools
import operator
import pathlib
import typing

import msgspec

from tools.profiler import call_tree

if typing.TYPE_CHECKING:
    from tools.profiler import tachyon_profile, wall_model

_NO_STACK = "(no Python stack)"
_MIXED = "(mixed)"
_ELISION = "…"
_CRITICAL_PATH_LEGEND = """\
Critical path: the main thread's time, except that where it mostly waits, the
time of the threads that mostly work meanwhile, grouped into phases of
consecutive time on one thread. Phases that overlap ran in parallel. A
main-thread phase that mostly waits is time when no thread mostly worked, such
as a handoff between phases. Under each phase, each call holding at least a
tenth of the phase, shown through the calls that hold nearly all of its own
time, with its share of the phase and the share of it spent working; then each
other thread that worked for at least a tenth of the phase, with what it mostly
did. (self) is time in a function itself, including C code below it, such as
acquiring a lock or freeing objects as they go out of scope. A garbage
collection ([<GC>]) stops every thread, so it delays all of them for as long as
one thread's samples show. Other labels are as in the timeline."""
_LEGEND = """\
Times are seconds from the first sample. A thread works while it executes Python
and waits while it has released its Python thread state: in a lock, a queue, or
I/O. A garbage collection stops every thread: the one collecting works in [<GC>]
while the others wait. A run's state is
'work' or 'wait' when it is entirely one, and otherwise the share of it spent
working.
A run is labeled by the deepest compiler call path holding most of its time, from
the function that names its activity to its innermost function, with … for the
calls between. On the main thread, that first function is the first below the
calls nearly all of its time shares; on a worker, it is the worker's task.
  [NAME]             a call outside compiler code, such as file I/O, a lock, an
                     idle pool worker ([_worker]), or garbage collection ([<GC>])
  <module NAME>      a module's top-level code, mostly its import
  (self)             time in the path's last function itself, including C code
                     below it, such as acquiring a lock or freeing objects as
                     they go out of scope
  (mixed)            no call path holds most of the run's time
  (no Python stack)  the thread had no Python frames
The indented lines under a run split its time by the call where each stack
leaves the run's path, named with the function it leaves from when that is above
the path's last function."""

# The compiler functions of a stack, outermost first, then in brackets the
# function outside the compiler that the innermost one was calling, if any. A
# stack without compiler functions has only its innermost function, in brackets.
type Path = tuple[str, ...]


class Run(msgspec.Struct, frozen=True):
    """A stretch of one thread's time and what the thread did during it."""

    start_ns: int
    end_ns: int
    working_ns: int
    # The deepest path holding most of the run's time.
    path: Path
    # Time at each path within the run.
    path_durations: dict[Path, int]
    # Time working at each path within the run.
    path_working: dict[Path, int]

    @property
    def duration_ns(self) -> int:
        """Nanoseconds spanned by the run."""
        return self.end_ns - self.start_ns


class TimelineOptions(msgspec.Struct, frozen=True):
    """How finely to divide each thread's time into runs."""

    # How many innermost functions of a run's path its label shows.
    depth: int
    # Runs shorter than this join or fold into their neighbors.
    minimum_run_ns: int
    start_ns: int | None = None
    end_ns: int | None = None
    thread_ids: frozenset[int] = frozenset()


def is_compiler_filename(filename: str) -> bool:
    """Return whether a filename belongs to Define compiler source."""
    path_parts = pathlib.PurePath(filename).parts
    # The compiler's virtual environment lives beside its source in runfiles.
    if "site-packages" in path_parts:
        return False
    for index, path_part in enumerate(path_parts):
        if path_part.endswith(".runfiles"):
            # Bazel paths can contain package names before the runfiles source path.
            return path_parts[index + 1 : index + 4] == (
                "_main",
                "define",
                "compiler",
            )
    return any(
        parent == "define" and child == "compiler"
        for parent, child in itertools.pairwise(path_parts)
    )


def _sample_path(stack: tuple[int, ...], frames: list[wall_model.Frame]) -> Path:
    if not stack:
        return (_NO_STACK,)
    path: list[str] = []
    callee_index = 0
    for index, frame_id in enumerate(stack):
        frame = frames[frame_id]
        if is_compiler_filename(frame.filename):
            function = call_tree.function_name(frame.function, frame.filename)
            # A recursive call's time counts toward its outermost call, so
            # that recursion depth does not split it.
            if function in path:
                del path[path.index(function) + 1 :]
            else:
                path.append(function)
            callee_index = index + 1
    if not path:
        # Threads outside the compiler, such as idle pool workers, are labeled
        # by what they are doing right now.
        return (f"[{frames[stack[-1]].function}]",)
    if callee_index < len(stack):
        # Time in library code, such as file I/O or waiting on a lock, is named
        # by the call the compiler made.
        callee = frames[stack[callee_index]]
        path.append(f"[{call_tree.function_name(callee.function, callee.filename)}]")
    return tuple(path)


def _deepest_path(path_durations: dict[Path, int], prefix: Path, share: float) -> Path:
    # Extend the prefix by its largest call while that call holds more than the
    # share of all the time.
    total_ns = sum(path_durations.values())
    while True:
        child_durations: collections.Counter[str] = collections.Counter()
        for path, duration_ns in path_durations.items():
            if len(path) > len(prefix) and path[: len(prefix)] == prefix:
                child_durations[path[len(prefix)]] += duration_ns
        if not child_durations:
            return prefix
        child, duration_ns = child_durations.most_common(1)[0]
        if duration_ns <= total_ns * share:
            return prefix
        prefix = (*prefix, child)


def dominant_path(path_durations: dict[Path, int], prefix: Path = ()) -> Path:
    """Return the deepest path, extending the prefix, holding most of the time."""
    return _deepest_path(path_durations, prefix, 0.5)


def _combine(runs: list[Run]) -> Run:
    path_durations: collections.Counter[Path] = collections.Counter()
    path_working: collections.Counter[Path] = collections.Counter()
    for run in runs:
        path_durations.update(run.path_durations)
        path_working.update(run.path_working)
    return Run(
        start_ns=runs[0].start_ns,
        end_ns=runs[-1].end_ns,
        working_ns=sum(run.working_ns for run in runs),
        path=dominant_path(path_durations),
        path_durations=dict(path_durations),
        path_working=dict(path_working),
    )


def _exact_runs(
    samples: list[wall_model.ThreadSample],
    frames: list[wall_model.Frame],
    options: TimelineOptions,
) -> list[Run]:
    runs: list[Run] = []
    for sample in samples:
        start_ns = sample.interval.start_ns
        end_ns = sample.interval.end_ns
        if options.start_ns is not None:
            start_ns = max(start_ns, options.start_ns)
        if options.end_ns is not None:
            end_ns = min(end_ns, options.end_ns)
        if end_ns <= start_ns:
            continue
        path = _sample_path(sample.stack, frames)
        working_ns = end_ns - start_ns if sample.is_working else 0
        run = Run(
            start_ns=start_ns,
            end_ns=end_ns,
            working_ns=working_ns,
            path=path,
            path_durations={path: end_ns - start_ns},
            path_working={path: working_ns},
        )
        previous = runs[-1] if runs else None
        if (
            previous is not None
            and previous.end_ns == run.start_ns
            and previous.path == run.path
            and (previous.working_ns == 0) == (run.working_ns == 0)
        ):
            runs[-1] = _combine([previous, run])
        else:
            runs.append(run)
    return runs


def _is_short(run: Run, options: TimelineOptions) -> bool:
    return run.duration_ns < options.minimum_run_ns


def _folded_short_runs(runs: list[Run], options: TimelineOptions) -> list[Run]:
    # Consecutive short runs become one run, so that a thread that switches
    # rapidly between functions, such as a loop calling a small helper, reads
    # as one stretch.
    result: list[Run] = []
    short_runs: list[Run] = []
    for run in runs:
        if short_runs and (
            not _is_short(run, options) or short_runs[-1].end_ns != run.start_ns
        ):
            result.append(_combine(short_runs))
            short_runs = []
        if _is_short(run, options):
            short_runs.append(run)
        else:
            result.append(run)
    if short_runs:
        result.append(_combine(short_runs))
    return result


def _is_interruption(
    before: Run, interruption: Run, after: Run, options: TimelineOptions
) -> bool:
    if before.end_ns != interruption.start_ns or interruption.end_ns != after.start_ns:
        return False
    return (
        before.path == after.path
        and _is_short(interruption, options)
        and not _is_short(before, options)
        and not _is_short(after, options)
    )


def _absorbed_interruptions(runs: list[Run], options: TimelineOptions) -> list[Run]:
    # A short run between two longer runs at the same label interrupts one
    # activity, such as a pool's dispatcher briefly waking, so all three become
    # one run at that label.
    result: list[Run] = []
    for run in runs:
        if len(result) >= 2 and _is_interruption(result[-2], result[-1], run, options):
            interruption = result.pop()
            interrupted = result.pop()
            result.append(_combine([interrupted, interruption, run]))
        else:
            result.append(run)
    return result


def _is_pure_work(run: Run) -> bool:
    return run.working_ns == run.duration_ns


def _can_join(earlier: Run, later: Run, options: TimelineOptions) -> bool:
    if earlier.path != later.path or earlier.end_ns != later.start_ns:
        return False
    if _is_short(earlier, options) or _is_short(later, options):
        return True
    # A long stretch of only work and a long stretch of only waiting stay
    # separate, because the moment one becomes the other matters.
    return not (
        (_is_pure_work(earlier) and later.working_ns == 0)
        or (earlier.working_ns == 0 and _is_pure_work(later))
    )


def _joined_runs(runs: list[Run], options: TimelineOptions) -> list[Run]:
    result: list[Run] = []
    for run in runs:
        if result and _can_join(result[-1], run, options):
            result[-1] = _combine([result[-1], run])
        else:
            result.append(run)
    return result


def thread_runs(
    profile: tachyon_profile.WallProfile, options: TimelineOptions
) -> dict[int, list[Run]]:
    """Return each selected thread's runs, the main thread first."""
    thread_ids = sorted(
        profile.samples_by_thread,
        key=lambda thread_id: (
            thread_id != profile.main_thread_id,
            profile.samples_by_thread[thread_id][0].interval.start_ns,
            thread_id,
        ),
    )
    runs_by_thread: dict[int, list[Run]] = {}
    for thread_id in thread_ids:
        if options.thread_ids and thread_id not in options.thread_ids:
            continue
        runs = _exact_runs(
            profile.samples_by_thread[thread_id], profile.frames, options
        )
        if not runs:
            continue
        runs = _folded_short_runs(runs, options)
        runs = _absorbed_interruptions(runs, options)
        runs_by_thread[thread_id] = _joined_runs(runs, options)
    return runs_by_thread


def _seconds(profile: tachyon_profile.WallProfile, time_ns: int) -> str:
    return f"{(time_ns - profile.started_ns) / 1_000_000_000:.3f}"


def _state(run: Run) -> str:
    if run.path == (_NO_STACK,):
        return "    "
    if run.working_ns == run.duration_ns:
        return "work"
    if run.working_ns == 0:
        return "wait"
    return f"{run.working_ns / run.duration_ns:4.0%}"


def _is_call_outside_compiler(function: str) -> bool:
    return function.startswith("[")


def _shown(functions: Path, depth: int) -> str:
    # The first function names the activity and the innermost show where its
    # time goes; the calls between them say little.
    shown = list(functions)
    call_outside: list[str] = []
    if len(shown) > 1 and _is_call_outside_compiler(shown[-1]):
        call_outside.append(shown.pop())
    if len(shown) > depth + 1:
        shown = [shown[0], _ELISION, *shown[-depth:]]
    return " > ".join(shown + call_outside)


def _common_length(first: Path, second: Path) -> int:
    length = 0
    for first_function, second_function in zip(first, second, strict=False):
        if first_function != second_function:
            break
        length += 1
    return length


def shared_prefix(runs: list[Run]) -> Path:
    """Return the path that nearly all of a thread's time shares.

    The main thread runs the command line and driver before any activity, so a
    run's label starts below them. A pool worker's outermost compiler function
    is the task it was given, which already names its activity.
    """
    path_durations: collections.Counter[Path] = collections.Counter()
    for run in runs:
        path_durations.update(run.path_durations)
    return _deepest_path(dict(path_durations), (), 0.9)


def run_label(path: Path, shared: Path, depth: int) -> str:
    """Label a run from the first function below the shared path."""
    if not path:
        return _MIXED
    compiler_length = len(path)
    if compiler_length > 1 and _is_call_outside_compiler(path[-1]):
        compiler_length -= 1
    start = min(_common_length(path, shared), max(compiler_length - depth, 0))
    return _shown(path[start:], depth)


def run_breakdown(run: Run, depth: int) -> list[tuple[str, int]]:
    """Return the time in each call where paths leave the run's path."""
    groups: dict[Path, dict[Path, int]] = collections.defaultdict(dict)
    for path, duration_ns in run.path_durations.items():
        groups[path[: _common_length(path, run.path) + 1]][path] = duration_ns
    if len(groups) < 2:
        return []
    breakdown: list[tuple[str, int]] = []
    for group, path_durations in groups.items():
        # A group the length of the run's path is time in its innermost function.
        if group == run.path:
            label = "(self)"
        else:
            label = _shown(
                dominant_path(path_durations, group)[len(group) - 1 :], depth
            )
            # A call that leaves the path above its last function is named
            # with the function it leaves from.
            if 1 < len(group) <= len(run.path):
                label = f"{group[-2]} > {label}"
        breakdown.append((label, sum(path_durations.values())))
    return sorted(breakdown, key=lambda item: -item[1])


def emit_header(profile: tachyon_profile.WallProfile):
    """Print what the wall profile covers."""
    print(
        f"Profile: Tachyon wall samples; Python {profile.python_version}; "
        + f"interval {profile.sample_interval_ns / 1_000_000:.1f} ms; "
        + f"{profile.observation_count} observations; "
        + f"failed samples {profile.failed_sample_percent:.1f}%"
    )
    print(
        f"Wall window: {_seconds(profile, profile.ended_ns)} s; "
        + f"{len(profile.samples_by_thread)} threads"
    )


def emit_report(
    profile: tachyon_profile.WallProfile,
    runs_by_thread: dict[int, list[Run]],
    depth: int,
    label_limit: int,
):
    """Print the per-thread timeline."""
    emit_header(profile)
    print(_LEGEND)
    main_runs = runs_by_thread.get(profile.main_thread_id)
    shared = () if main_runs is None else shared_prefix(main_runs)
    for thread_id, runs in runs_by_thread.items():
        main = " (main)" if thread_id == profile.main_thread_id else ""
        print(
            f"\nThread {thread_id}{main}: "
            + f"{_seconds(profile, runs[0].start_ns)}-"
            + f"{_seconds(profile, runs[-1].end_ns)}"
        )
        for run in runs:
            label = run_label(run.path, shared, depth)
            print(
                f"  {_seconds(profile, run.start_ns)}-{_seconds(profile, run.end_ns)}"
                + f"  {_state(run)}  {label}"
            )
            for call, duration_ns in run_breakdown(run, depth)[:label_limit]:
                print(f"{duration_ns / 1_000_000:23.1f} ms  {call}")


def _is_mostly_working(run: Run) -> bool:
    return run.working_ns * 2 >= run.duration_ns


class _Phase(msgspec.Struct):
    """Consecutive critical-path time on one thread."""

    thread: str
    start_ns: int
    end_ns: int
    working_ns: float
    path_durations: dict[Path, float]
    path_working: dict[Path, float]

    def add(self, run: Run, start_ns: int, end_ns: int):
        """Add the part of a run between the times."""
        share = (end_ns - start_ns) / run.duration_ns
        self.end_ns = max(self.end_ns, end_ns)
        self.working_ns += run.working_ns * share
        for path, duration_ns in run.path_durations.items():
            self.path_durations[path] = (
                self.path_durations.get(path, 0.0) + duration_ns * share
            )
            self.path_working[path] = (
                self.path_working.get(path, 0.0) + run.path_working[path] * share
            )


def _critical_rows(
    profile: tachyon_profile.WallProfile, runs_by_thread: dict[int, list[Run]]
) -> list[tuple[int, int, str, Run]]:
    rows: list[tuple[int, int, str, Run]] = []
    for run in runs_by_thread[profile.main_thread_id]:
        run_rows: list[tuple[int, int, str, Run]] = []
        if not _is_mostly_working(run):
            for thread_id, runs in runs_by_thread.items():
                if thread_id == profile.main_thread_id:
                    continue
                for other in runs:
                    start_ns = max(run.start_ns, other.start_ns)
                    end_ns = min(run.end_ns, other.end_ns)
                    if end_ns > start_ns and _is_mostly_working(other):
                        run_rows.append((start_ns, end_ns, str(thread_id), other))
        # Where no other thread mostly works, the main thread's own run is
        # what the compile waits on.
        covered_ns = run.start_ns
        for start_ns, end_ns, _, _ in sorted(run_rows, key=operator.itemgetter(0)):
            if start_ns > covered_ns:
                run_rows.append((covered_ns, start_ns, "main", run))
            covered_ns = max(covered_ns, end_ns)
        if covered_ns < run.end_ns:
            run_rows.append((covered_ns, run.end_ns, "main", run))
        rows.extend(sorted(run_rows, key=operator.itemgetter(0)))
    return rows


def _phases(rows: list[tuple[int, int, str, Run]]) -> list[_Phase]:
    phases: list[_Phase] = []
    for start_ns, end_ns, thread, run in rows:
        if not phases or phases[-1].thread != thread:
            phases.append(
                _Phase(
                    thread=thread,
                    start_ns=start_ns,
                    end_ns=end_ns,
                    working_ns=0.0,
                    path_durations={},
                    path_working={},
                )
            )
        phases[-1].add(run, start_ns, end_ns)
    return phases


def _emit_calls(
    phase: _Phase, path_durations: dict[Path, float], prefix: Path, indent: int
):
    # Calls below the prefix holding at least a tenth of the phase, each shown
    # through the calls that hold nearly all of its own time.
    phase_ns = sum(phase.path_durations.values())
    groups: dict[str, dict[Path, float]] = collections.defaultdict(dict)
    for path, duration_ns in path_durations.items():
        if len(path) > len(prefix) and path[: len(prefix)] == prefix:
            groups[path[len(prefix)]][path] = duration_ns
    lines: list[tuple[float, str, Path, dict[Path, float]]] = []
    for call, call_durations in groups.items():
        call_ns = sum(call_durations.values())
        if call_ns * 10 < phase_ns:
            continue
        chain = _deepest_path(
            {path: round(ns) for path, ns in call_durations.items()},
            (*prefix, call),
            0.9,
        )
        lines.append((call_ns, _shown(chain[len(prefix) :], 1), chain, call_durations))
    self_ns = path_durations.get(prefix, 0.0)
    # Self time says something only beside the calls it is compared with.
    if lines and self_ns * 10 >= phase_ns:
        lines.append((self_ns, "(self)", prefix, {prefix: self_ns}))
    for call_ns, label, chain, call_durations in sorted(
        lines, key=operator.itemgetter(0), reverse=True
    ):
        working_ns = sum(phase.path_working[path] for path in call_durations)
        print(
            f"{' ' * indent}{call_ns / 1_000_000:9.1f} ms "
            + f"{100 * call_ns / phase_ns:3.0f}%  work {working_ns / call_ns:4.0%}"
            + f"  {label}"
        )
        if label != "(self)":
            _emit_calls(phase, call_durations, chain, indent + 2)


def emit_critical_path(
    profile: tachyon_profile.WallProfile,
    runs_by_thread: dict[int, list[Run]],
    depth: int,
):
    """Print the phases that the main thread's progress waited on, in order."""
    emit_header(profile)
    print(_CRITICAL_PATH_LEGEND)
    shared = shared_prefix(runs_by_thread[profile.main_thread_id])
    for phase in _phases(_critical_rows(profile, runs_by_thread)):
        phase_ns = phase.end_ns - phase.start_ns
        path = dominant_path(
            {path: round(ns) for path, ns in phase.path_durations.items()}
        )
        print(
            f"\n{_seconds(profile, phase.start_ns)}-{_seconds(profile, phase.end_ns)}"
            + f"  {phase_ns / 1_000_000_000:6.3f} s  thread {phase.thread}"
            + f"  work {phase.working_ns / phase_ns:4.0%}"
            + f"  {run_label(path, shared, depth)}"
        )
        _emit_calls(phase, phase.path_durations, (), 2)
        for thread_id, runs in runs_by_thread.items():
            thread = "main" if thread_id == profile.main_thread_id else str(thread_id)
            if thread == phase.thread:
                continue
            other = _Phase(
                thread=thread,
                start_ns=phase.start_ns,
                end_ns=phase.start_ns,
                working_ns=0.0,
                path_durations={},
                path_working={},
            )
            for run in runs:
                start_ns = max(run.start_ns, phase.start_ns)
                end_ns = min(run.end_ns, phase.end_ns)
                if end_ns > start_ns:
                    other.add(run, start_ns, end_ns)
            if other.working_ns * 10 >= phase_ns:
                other_path = dominant_path(
                    {path: round(ns) for path, ns in other.path_working.items()}
                )
                print(
                    f"  meanwhile thread {thread} worked "
                    + f"{other.working_ns / phase_ns:.0%} of this phase in "
                    + run_label(other_path, shared, depth)
                )
