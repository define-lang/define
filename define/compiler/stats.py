"""Timing statistics for validation phases."""

from __future__ import annotations

import time
from dataclasses import dataclass


@dataclass
class ValidationTimingStats:
    """Timing measurements for config-load/file-load/parse/transform/validate steps."""

    overall: int
    config_loading: int
    file_loading: int | None
    parse: int | None
    transform: int | None
    validate: int | None


class ValidationStatsTracker:
    """Records phase timestamps and produces ValidationTimingStats."""

    def __init__(self):
        """Start the overall timer."""
        self._started_at: int = time.perf_counter_ns()
        self._config_loading_finished_at: int | None = None
        self._file_loading_finished_at: int | None = None
        self._parse_finished_at: int | None = None
        self._transform_finished_at: int | None = None
        self._validate_finished_at: int | None = None

    def mark_config_loading_finished(self):
        """Record the end of the config-loading phase."""
        self._config_loading_finished_at = time.perf_counter_ns()

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
        if self._config_loading_finished_at is None:
            raise ValueError(
                "Config loading timing was not recorded before building stats."
            )
        config_loading = self._config_loading_finished_at - self._started_at
        last_timestamp = self._config_loading_finished_at

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
            config_loading=config_loading,
            file_loading=file_loading,
            parse=parse,
            transform=transform,
            validate=validate,
        )
