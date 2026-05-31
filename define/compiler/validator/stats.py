"""Timing statistics for validation phases."""

from __future__ import annotations

import time
from dataclasses import dataclass


@dataclass
class ValidationTimingStats:
    """Timing measurements for per-file and coordinator validation work."""

    file_loading: int = 0
    parse: int = 0
    file_validation: int = 0
    global_validation: int = 0
    queue_wait: int = 0

    @property
    def overall_compile(self) -> int:
        """Compile work total, excluding thread-pool wait time."""
        return (
            self.file_loading
            + self.parse
            + self.file_validation
            + self.global_validation
        )


class ValidationStatsTracker:
    """Records phase timestamps and produces ValidationTimingStats."""

    def __init__(self):
        """Start the compile-phase timer."""
        self._started_at: int = time.perf_counter_ns()
        self._file_loading_finished_at: int | None = None
        self._parse_finished_at: int | None = None
        self._file_validation_finished_at: int | None = None

    def mark_file_loading_finished(self):
        """Record the end of the file-loading phase."""
        self._file_loading_finished_at = time.perf_counter_ns()

    def mark_parse_finished(self):
        """Record the end of the parse phase."""
        self._parse_finished_at = time.perf_counter_ns()

    def mark_file_validation_finished(self):
        """Record the end of the per-file validation phase."""
        self._file_validation_finished_at = time.perf_counter_ns()

    def build(self) -> ValidationTimingStats:
        """Compute timing stats from whichever phases have completed."""
        last_timestamp = self._started_at

        file_loading = 0
        if self._file_loading_finished_at is not None:
            file_loading = self._file_loading_finished_at - last_timestamp
            last_timestamp = self._file_loading_finished_at

        parse = 0
        if self._parse_finished_at is not None:
            parse = self._parse_finished_at - last_timestamp
            last_timestamp = self._parse_finished_at

        file_validation = 0
        if self._file_validation_finished_at is not None:
            file_validation = self._file_validation_finished_at - last_timestamp
            last_timestamp = self._file_validation_finished_at

        return ValidationTimingStats(
            file_loading=file_loading,
            parse=parse,
            file_validation=file_validation,
        )
