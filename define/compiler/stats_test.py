# pyright: reportUnusedCallResult=false
from __future__ import annotations

import time
from unittest.mock import patch

from define.compiler import stats


def _make_tracker(timestamps: list[int]) -> stats.ValidationStatsTracker:
    with patch.object(time, "perf_counter_ns", autospec=True, side_effect=timestamps):
        return stats.ValidationStatsTracker()


class TestBuildWithNoPhases:
    def test_all_phases_are_none(self):
        tracker = _make_tracker([100])
        result = tracker.build()
        assert result.file_loading is None
        assert result.parse is None
        assert result.transform is None
        assert result.validate is None

    def test_overall_is_zero(self):
        tracker = _make_tracker([100])
        result = tracker.build()
        assert result.overall == 0


class TestBuildAfterFileLoading:
    def test_file_loading_is_set(self):
        tracker = _make_tracker([100])
        with patch.object(time, "perf_counter_ns", autospec=True, return_value=250):
            tracker.mark_file_loading_finished()
        result = tracker.build()
        assert result.file_loading == 150

    def test_later_phases_are_none(self):
        tracker = _make_tracker([100])
        with patch.object(time, "perf_counter_ns", autospec=True, return_value=250):
            tracker.mark_file_loading_finished()
        result = tracker.build()
        assert result.parse is None
        assert result.transform is None
        assert result.validate is None

    def test_overall_equals_file_loading(self):
        tracker = _make_tracker([100])
        with patch.object(time, "perf_counter_ns", autospec=True, return_value=250):
            tracker.mark_file_loading_finished()
        result = tracker.build()
        assert result.overall == 150


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

    def test_later_phases_are_none(self):
        tracker = _make_tracker([100])
        with patch.object(
            time, "perf_counter_ns", autospec=True, side_effect=[250, 400]
        ):
            tracker.mark_file_loading_finished()
            tracker.mark_parse_finished()
        result = tracker.build()
        assert result.transform is None
        assert result.validate is None


class TestBuildAfterTransform:
    def test_phases_through_transform_are_set(self):
        tracker = _make_tracker([100])
        with patch.object(
            time, "perf_counter_ns", autospec=True, side_effect=[250, 400, 600]
        ):
            tracker.mark_file_loading_finished()
            tracker.mark_parse_finished()
            tracker.mark_transform_finished()
        result = tracker.build()
        assert result.file_loading == 150
        assert result.parse == 150
        assert result.transform == 200

    def test_validate_is_none(self):
        tracker = _make_tracker([100])
        with patch.object(
            time, "perf_counter_ns", autospec=True, side_effect=[250, 400, 600]
        ):
            tracker.mark_file_loading_finished()
            tracker.mark_parse_finished()
            tracker.mark_transform_finished()
        result = tracker.build()
        assert result.validate is None


class TestBuildAfterAllPhases:
    def test_all_phases_are_set(self):
        tracker = _make_tracker([100])
        with patch.object(
            time,
            "perf_counter_ns",
            autospec=True,
            side_effect=[250, 400, 600, 800],
        ):
            tracker.mark_file_loading_finished()
            tracker.mark_parse_finished()
            tracker.mark_transform_finished()
            tracker.mark_validate_finished()
        result = tracker.build()
        assert result.file_loading == 150
        assert result.parse == 150
        assert result.transform == 200
        assert result.validate == 200

    def test_overall_equals_phase_sum(self):
        tracker = _make_tracker([100])
        with patch.object(
            time,
            "perf_counter_ns",
            autospec=True,
            side_effect=[250, 400, 600, 800],
        ):
            tracker.mark_file_loading_finished()
            tracker.mark_parse_finished()
            tracker.mark_transform_finished()
            tracker.mark_validate_finished()
        result = tracker.build()
        assert result.file_loading is not None
        assert result.parse is not None
        assert result.transform is not None
        assert result.validate is not None
        assert result.overall == (
            result.file_loading + result.parse + result.transform + result.validate
        )
