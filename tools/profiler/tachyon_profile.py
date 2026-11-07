"""Load Tachyon binary wall profiles into the wall sample model."""

from __future__ import annotations

import itertools
import typing

import _remote_debugging  # noqa: PLC2701
import msgspec
from profiling.sampling import (
    # Typeshed has no stubs for this module.
    binary_reader,  # pyright: ignore[reportAttributeAccessIssue, reportUnknownVariableType]
    collector,
)

from tools.profiler import call_tree, wall_model

if typing.TYPE_CHECKING:
    import collections.abc
    import os
    import pathlib

# Every main-thread stack starts with the frames that launch the target: Python
# running Tachyon's coordinator, which runs tachyon_target.py, which runs the
# target script through runpy. They say nothing about the target.
_LAUNCH_FILENAME_SUFFIXES = (
    "<frozen runpy>",
    "/runpy.py",
    "/profiling/sampling/_sync_coordinator.py",
    "/tools/profiler/tachyon_target.py",
)


class WallProfile(msgspec.Struct):
    """A Tachyon wall profile indexed for analysis."""

    python_version: str
    sample_interval_ns: int
    # Tachyon reports this as a percentage.
    failed_sample_percent: float
    main_thread_id: int
    started_ns: int
    ended_ns: int
    frames: list[wall_model.Frame]
    observation_count: int
    samples_by_thread: dict[int, list[wall_model.ThreadSample]]


class _BinaryInfo(typing.TypedDict):
    sample_interval_us: int
    python_version: tuple[int, int, int]
    # Tachyon reports this as a percentage.
    error_rate: float


class _BinaryReader(typing.Protocol):
    def __enter__(self) -> typing.Self: ...
    def __exit__(self, *exception: object): ...
    def get_info(self) -> _BinaryInfo: ...
    def replay_samples(self, collector: collector.Collector) -> int: ...


_BINARY_READER = typing.cast(
    "collections.abc.Callable[[str], _BinaryReader]",
    binary_reader.BinaryReader,
)


class _ObservationCollector(collector.Collector):
    """Gathers replayed per-thread samples into whole-process observations."""

    def __init__(self):
        self.frames: list[wall_model.Frame] = []
        self.threads_by_time_us: dict[int, dict[int, tuple[bool, tuple[int, ...]]]] = {}
        self.main_thread_ids: set[int] = set()
        self._frame_ids: dict[wall_model.Frame, int] = {}

    def _frame_id(self, frame: wall_model.Frame) -> int:
        frame_id = self._frame_ids.get(frame)
        if frame_id is None:
            frame_id = len(self.frames)
            self._frame_ids[frame] = frame_id
            self.frames.append(frame)
        return frame_id

    def _stack(
        self,
        frame_info: collections.abc.Sequence[collector._Frame],  # pyright: ignore[reportPrivateUsage]
    ) -> tuple[int, ...]:
        root_first: list[wall_model.Frame] = []
        # A frame is a FrameInfo or, in some replays, a plain tuple of its fields.
        for filename, location, function, _ in reversed(frame_info):
            root_first.append(
                wall_model.Frame(
                    filename=filename,
                    function=function,
                    # Synthetic frames, such as garbage collection, have line 0.
                    line=collector.extract_lineno(location) or None,
                )
            )
        target_frames = itertools.dropwhile(
            lambda frame: frame.filename.endswith(_LAUNCH_FILENAME_SUFFIXES),
            root_first,
        )
        return tuple(
            self._frame_id(frame)
            for frame in target_frames
            if not call_tree.is_import_machinery(frame.filename)
        )

    @typing.override
    def collect(
        self,
        stack_frames: (
            collections.abc.Sequence[_remote_debugging.InterpreterInfo]
            | collections.abc.Sequence[_remote_debugging.AwaitedInfo]
        ),
        timestamps_us: collections.abc.Sequence[int] | None = None,
    ):
        # Without async awareness, replay supplies interpreters, along with the
        # timestamps of the samples it groups.
        for interpreter in typing.cast(
            "collections.abc.Sequence[_remote_debugging.InterpreterInfo]", stack_frames
        ):
            for thread in interpreter.threads:
                running = bool(thread.status & _remote_debugging.THREAD_STATUS_HAS_GIL)
                stack = self._stack(thread.frame_info)
                if thread.status & _remote_debugging.THREAD_STATUS_MAIN_THREAD:
                    self.main_thread_ids.add(thread.thread_id)
                for timestamp_us in typing.cast(
                    "collections.abc.Sequence[int]", timestamps_us
                ):
                    self.threads_by_time_us.setdefault(timestamp_us, {})[
                        thread.thread_id
                    ] = (running, stack)

    @typing.override
    def export(
        self, filename: str | bytes | os.PathLike[str] | os.PathLike[bytes]
    ) -> typing.NoReturn:
        raise NotImplementedError


def _samples_by_thread(
    threads_by_time_us: dict[int, dict[int, tuple[bool, tuple[int, ...]]]],
    sample_interval_ns: int,
) -> dict[int, list[wall_model.ThreadSample]]:
    times_ns = [time_us * 1000 for time_us in sorted(threads_by_time_us)]
    samples_by_thread: dict[int, list[wall_model.ThreadSample]] = {}
    for index, observed_ns in enumerate(times_ns):
        # Each observation stands for the time to the midpoints between it and its
        # neighbors.
        start_ns = (
            observed_ns if index == 0 else (times_ns[index - 1] + observed_ns) // 2
        )
        end_ns = (
            observed_ns + sample_interval_ns // 2
            if index + 1 == len(times_ns)
            else (observed_ns + times_ns[index + 1]) // 2
        )
        interval = wall_model.Interval(start_ns, end_ns)
        for os_thread_id, (running, stack) in threads_by_time_us[
            observed_ns // 1000
        ].items():
            samples_by_thread.setdefault(os_thread_id, []).append(
                wall_model.ThreadSample(interval=interval, running=running, stack=stack)
            )
    return samples_by_thread


def load(profile_path: pathlib.Path) -> WallProfile:
    """Load a Tachyon binary profile captured with all threads."""
    observation_collector = _ObservationCollector()
    with _BINARY_READER(str(profile_path)) as reader:
        info = reader.get_info()
        _ = reader.replay_samples(observation_collector)
    if not observation_collector.threads_by_time_us:
        raise ValueError("profile contains no samples")
    if len(observation_collector.main_thread_ids) != 1:
        raise ValueError("profile does not identify exactly one main thread")
    sample_interval_ns = info["sample_interval_us"] * 1000
    threads_by_time_us = observation_collector.threads_by_time_us
    samples_by_thread = _samples_by_thread(threads_by_time_us, sample_interval_ns)
    first_time_us = min(threads_by_time_us)
    last_time_us = max(threads_by_time_us)
    return WallProfile(
        python_version=".".join(str(part) for part in info["python_version"]),
        sample_interval_ns=sample_interval_ns,
        failed_sample_percent=info["error_rate"],
        main_thread_id=next(iter(observation_collector.main_thread_ids)),
        started_ns=first_time_us * 1000,
        ended_ns=last_time_us * 1000 + sample_interval_ns // 2,
        frames=observation_collector.frames,
        observation_count=len(threads_by_time_us),
        samples_by_thread=samples_by_thread,
    )


def weighted_stacks(
    profile: WallProfile,
    thread_ids: frozenset[int],
    start_ns: int | None,
    end_ns: int | None,
) -> list[call_tree.WeightedStack]:
    """Return the selected threads' samples within the window as stacks."""
    stacks: list[call_tree.WeightedStack] = []
    for thread_id, samples in profile.samples_by_thread.items():
        if thread_ids and thread_id not in thread_ids:
            continue
        for sample in samples:
            sample_start_ns = sample.interval.start_ns
            sample_end_ns = sample.interval.end_ns
            if start_ns is not None:
                sample_start_ns = max(sample_start_ns, start_ns)
            if end_ns is not None:
                sample_end_ns = min(sample_end_ns, end_ns)
            if sample_end_ns <= sample_start_ns:
                continue
            duration_ns = sample_end_ns - sample_start_ns
            functions: list[str] = []
            for frame_id in sample.stack:
                frame = profile.frames[frame_id]
                functions.append(
                    call_tree.function_name(frame.function, frame.filename)
                )
            stacks.append(
                call_tree.WeightedStack(
                    thread_id=thread_id,
                    functions=tuple(functions),
                    total_ns=duration_ns,
                    working_ns=duration_ns if sample.is_working else 0,
                )
            )
    return stacks
