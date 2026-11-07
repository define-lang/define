"""Sampled wall time of each thread."""

from __future__ import annotations

import msgspec


class Frame(msgspec.Struct, frozen=True):
    """The source identity of one sampled Python frame."""

    filename: str
    function: str
    # Synthetic frames, such as garbage collection, have no source line.
    line: int | None


class Interval(msgspec.Struct, frozen=True):
    """A sampled wall interval bounded in nanoseconds."""

    start_ns: int
    end_ns: int


class ThreadSample(msgspec.Struct, frozen=True):
    """One thread's state and stack over a sampled wall interval."""

    interval: Interval
    # Whether the thread was executing Python, as opposed to blocked with its
    # Python thread state released.
    running: bool
    stack: tuple[int, ...]

    @property
    def is_working(self) -> bool:
        """Whether the thread was running Python code."""
        return self.running and bool(self.stack)
