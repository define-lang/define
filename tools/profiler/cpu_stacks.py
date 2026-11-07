"""Load the collapsed CPU stacks that a perf capture writes."""

from __future__ import annotations

import collections
import typing

import msgspec

from tools.profiler import call_tree

if typing.TYPE_CHECKING:
    import pathlib

# A rate that is not a round number does not stay in step with periodic work.
SAMPLING_FREQUENCY_HZ = 997
_PYTHON_FRAME_PREFIX = "py::"
NOT_UNWOUND = "(stack not unwound to its thread's start)"
# The functions where glibc starts a process's main thread and its other threads.
_THREAD_ENTRY_FUNCTIONS = frozenset({"_start", "__GI___clone3", "clone3", "__clone"})


class CpuStacks(msgspec.Struct, frozen=True):
    """Every sampled CPU stack, with what perf recorded about its threads."""

    stacks: list[call_tree.WeightedStack]
    # Each thread's name for most of its samples. Linux truncates thread names
    # to 15 bytes.
    thread_names: dict[int, str]
    main_thread_id: int
    # Samples whose stacks perf could not unwind to the thread's start, which
    # begin at an arbitrary function instead.
    truncated_ns: int


def _functions(frames: list[str], *, native: bool) -> tuple[str, ...]:
    functions: list[str] = []
    for frame in frames:
        if not frame.startswith(_PYTHON_FRAME_PREFIX):
            if native:
                functions.append(frame)
            continue
        # CPython's perf map names a Python frame py::<function>:<file>.
        function, _, filename = frame.removeprefix(_PYTHON_FRAME_PREFIX).partition(":")
        if not call_tree.is_import_machinery(filename):
            functions.append(call_tree.function_name(function, filename))
    return tuple(functions)


class _Line(msgspec.Struct, frozen=True):
    thread_name: str
    process_id: int
    thread_id: int
    # Outermost first.
    frames: list[str]
    count: int


def _parse(line_number: int, line: str) -> _Line:
    stack, _, count_text = line.rstrip("\n").rpartition(" ")
    thread, *frames = stack.split(";")
    # perf writes each thread as <name>-<process ID>/<thread ID>.
    thread_name, _, ids = thread.rpartition("-")
    process_id_text, _, thread_id_text = ids.partition("/")
    try:
        return _Line(
            thread_name=thread_name,
            process_id=int(process_id_text),
            thread_id=int(thread_id_text),
            frames=frames,
            count=int(count_text),
        )
    except ValueError as error:
        raise ValueError(
            f"line {line_number} is not a collapsed stack: {line.strip()}"
        ) from error


def load(profile_path: pathlib.Path, *, native: bool) -> CpuStacks:
    """Load collapsed stacks, keeping native frames only when requested."""
    stacks: list[call_tree.WeightedStack] = []
    # A thread's name can change, such as when the launcher executes Python.
    name_durations: dict[int, collections.Counter[str]] = collections.defaultdict(
        collections.Counter
    )
    process_ids: set[int] = set()
    truncated_ns = 0
    with profile_path.open(encoding="utf-8") as profile_file:
        for line_number, text in enumerate(profile_file, start=1):
            line = _parse(line_number, text)
            duration_ns = round(line.count * 1_000_000_000 / SAMPLING_FREQUENCY_HZ)
            process_ids.add(line.process_id)
            name_durations[line.thread_id][line.thread_name] += duration_ns
            functions = _functions(line.frames, native=native)
            if not line.frames or line.frames[0] not in _THREAD_ENTRY_FUNCTIONS:
                truncated_ns += duration_ns
                # Grouped apart, so its outermost function is not mistaken for
                # a caller.
                functions = (NOT_UNWOUND, *functions)
            stacks.append(
                call_tree.WeightedStack(
                    thread_id=line.thread_id,
                    functions=functions,
                    total_ns=duration_ns,
                    working_ns=duration_ns,
                )
            )
    if not stacks:
        raise ValueError("profile contains no stacks")
    if len(process_ids) != 1:
        raise ValueError("profile does not contain exactly one process")
    thread_names: dict[int, str] = {}
    for thread_id, durations in name_durations.items():
        thread_names[thread_id] = durations.most_common(1)[0][0]
    return CpuStacks(
        stacks=stacks,
        thread_names=thread_names,
        # A process's ID is its main thread's ID.
        main_thread_id=next(iter(process_ids)),
        truncated_ns=truncated_ns,
    )
