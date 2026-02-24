"""Timing statistics for validation phases."""

from __future__ import annotations

import time
from dataclasses import dataclass


@dataclass
class ValidationTimingStats:
    """Timing measurements for file-load/parse/transform/validate steps.

    TODO: Split validation timing into file_validation (per-file FileValidator
    work), global_validation (cross-file reference edge processing), and
    deferred_validation (deferred edge resolution). Each should measure only
    the actual work time for that file.

    TODO: Track config loading time separately (it currently happens in
    ProgramValidator, not per-file).

    TODO: Track wait time in the thread pool queue (time between submission
    and start of actual work).
    """

    overall: int
    file_loading: int | None
    parse: int | None
    transform: int | None
    validate: int | None


class ValidationStatsTracker:
    """Records phase timestamps and produces ValidationTimingStats."""

    def __init__(self):
        """Start the overall timer."""
        self._started_at: int = time.perf_counter_ns()
        self._file_loading_finished_at: int | None = None
        self._parse_finished_at: int | None = None
        self._transform_finished_at: int | None = None
        self._validate_finished_at: int | None = None

    def mark_file_loading_finished(self):
        """Record the end of the file-loading phase."""
        self._file_loading_finished_at = time.perf_counter_ns()

    def mark_parse_finished(self):
        """Record the end of the parse phase."""
        self._parse_finished_at = time.perf_counter_ns()

    def mark_transform_finished(self):
        """Record the end of the transform phase."""
        self._transform_finished_at = time.perf_counter_ns()

    def mark_validate_finished(self):
        """Record the end of the validate phase."""
        self._validate_finished_at = time.perf_counter_ns()

    def build(self) -> ValidationTimingStats:
        """Compute timing stats from whichever phases have completed."""
        last_timestamp = self._started_at

        file_loading: int | None = None
        if self._file_loading_finished_at is not None:
            file_loading = self._file_loading_finished_at - last_timestamp
            last_timestamp = self._file_loading_finished_at

        parse: int | None = None
        if self._parse_finished_at is not None:
            parse = self._parse_finished_at - last_timestamp
            last_timestamp = self._parse_finished_at

        transform: int | None = None
        if self._transform_finished_at is not None:
            transform = self._transform_finished_at - last_timestamp
            last_timestamp = self._transform_finished_at

        validate: int | None = None
        if self._validate_finished_at is not None:
            validate = self._validate_finished_at - last_timestamp
            last_timestamp = self._validate_finished_at

        return ValidationTimingStats(
            overall=last_timestamp - self._started_at,
            file_loading=file_loading,
            parse=parse,
            transform=transform,
            validate=validate,
        )
