# pyright: reportUnusedCallResult=false
from __future__ import annotations

import time
from unittest.mock import patch

from define.compiler.validator import stats


def _make_tracker(timestamps: list[int]) -> stats.ValidationStatsTracker:
    with patch.object(time, "perf_counter_ns", autospec=True, side_effect=timestamps):
        return stats.ValidationStatsTracker()


class TestBuildWithNoPhases:
    def test_all_phases_are_zero(self):
        tracker = _make_tracker([100])
        result = tracker.build()
        assert result.file_loading == 0
        assert result.parse == 0
        assert result.file_validation == 0
        assert result.global_validation == 0
        assert result.queue_wait == 0

    def test_overall_compile_is_zero(self):
        tracker = _make_tracker([100])
        result = tracker.build()
        assert result.overall_compile == 0


class TestBuildAfterFileLoading:
    def test_file_loading_is_set(self):
        tracker = _make_tracker([100])
        with patch.object(time, "perf_counter_ns", autospec=True, return_value=250):
            tracker.mark_file_loading_finished()
        result = tracker.build()
        assert result.file_loading == 150

    def test_later_phases_are_zero(self):
        tracker = _make_tracker([100])
        with patch.object(time, "perf_counter_ns", autospec=True, return_value=250):
            tracker.mark_file_loading_finished()
        result = tracker.build()
        assert result.parse == 0
        assert result.file_validation == 0

    def test_overall_compile_equals_file_loading(self):
        tracker = _make_tracker([100])
        with patch.object(time, "perf_counter_ns", autospec=True, return_value=250):
            tracker.mark_file_loading_finished()
        result = tracker.build()
        assert result.overall_compile == 150


class TestBuildAfterParse:
    def test_phases_through_parse_are_set(self):
        tracker = _make_tracker([100])
        with patch.object(
            time, "perf_counter_ns", autospec=True, side_effect=[250, 400]
        ):
            tracker.mark_file_loading_finished()
            tracker.mark_parse_finished()
        result = tracker.build()
        assert result.file_loading == 150
        assert result.parse == 150

    def test_later_phases_are_zero(self):
        tracker = _make_tracker([100])
        with patch.object(
            time, "perf_counter_ns", autospec=True, side_effect=[250, 400]
        ):
            tracker.mark_file_loading_finished()
            tracker.mark_parse_finished()
        result = tracker.build()
        assert result.file_validation == 0


class TestBuildAfterAllFilePhases:
    def test_all_file_phases_are_set(self):
        tracker = _make_tracker([100])
        with patch.object(
            time,
            "perf_counter_ns",
            autospec=True,
            side_effect=[250, 400, 600],
        ):
            tracker.mark_file_loading_finished()
            tracker.mark_parse_finished()
            tracker.mark_file_validation_finished()
        result = tracker.build()
        assert result.file_loading == 150
        assert result.parse == 150
        assert result.file_validation == 200

    def test_overall_compile_equals_file_phase_sum(self):
        tracker = _make_tracker([100])
        with patch.object(
            time,
            "perf_counter_ns",
            autospec=True,
            side_effect=[250, 400, 600],
        ):
            tracker.mark_file_loading_finished()
            tracker.mark_parse_finished()
            tracker.mark_file_validation_finished()
        result = tracker.build()
        assert result.overall_compile == (
            result.file_loading + result.parse + result.file_validation
        )


class TestOverallCompileProperty:
    def test_queue_wait_does_not_change_overall_compile(self):
        tracker = _make_tracker([100])
        with patch.object(
            time,
            "perf_counter_ns",
            autospec=True,
            side_effect=[250, 400, 600],
        ):
            tracker.mark_file_loading_finished()
            tracker.mark_parse_finished()
            tracker.mark_file_validation_finished()
        result = tracker.build()
        assert result.overall_compile == 500

        result.queue_wait = 500

        assert result.queue_wait == 500
        assert result.overall_compile == 500

    def test_global_validation_is_included(self):
        tracker = _make_tracker([100])
        with patch.object(
            time,
            "perf_counter_ns",
            autospec=True,
            side_effect=[250, 400, 600],
        ):
            tracker.mark_file_loading_finished()
            tracker.mark_parse_finished()
            tracker.mark_file_validation_finished()
        result = tracker.build()
        result.global_validation = 23
        result.queue_wait = 100

        assert result.overall_compile == 523
