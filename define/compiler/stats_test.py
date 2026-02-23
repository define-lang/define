# pyright: reportUnusedCallResult=false
from __future__ import annotations

import time
from unittest.mock import patch

import pytest

from define.compiler import stats


def _make_tracker(timestamps: list[int]) -> stats.ValidationStatsTracker:
    with patch.object(time, "perf_counter_ns", autospec=True, side_effect=timestamps):
        return stats.ValidationStatsTracker()


class TestBuildAfterConfigLoadingOnly:
    def test_config_loading_is_set(self):
        tracker = _make_tracker([100])
        with patch.object(time, "perf_counter_ns", autospec=True, return_value=200):
            tracker.mark_config_loading_finished()
        result = tracker.build()
        assert result.config_loading == 100

    def test_later_phases_are_none(self):
        tracker = _make_tracker([100])
        with patch.object(time, "perf_counter_ns", autospec=True, return_value=200):
            tracker.mark_config_loading_finished()
        result = tracker.build()
        assert result.file_loading is None
        assert result.parse is None
        assert result.transform is None
        assert result.validate is None

    def test_overall_equals_config_loading(self):
        tracker = _make_tracker([100])
        with patch.object(time, "perf_counter_ns", autospec=True, return_value=200):
            tracker.mark_config_loading_finished()
        result = tracker.build()
        assert result.overall == 100


class TestBuildAfterFileLoading:
    def test_phases_through_file_loading_are_set(self):
        tracker = _make_tracker([100])
        with patch.object(
            time, "perf_counter_ns", autospec=True, side_effect=[200, 350]
        ):
            tracker.mark_config_loading_finished()
            tracker.mark_file_loading_finished()
        result = tracker.build()
        assert result.config_loading == 100
        assert result.file_loading == 150

    def test_later_phases_are_none(self):
        tracker = _make_tracker([100])
        with patch.object(
            time, "perf_counter_ns", autospec=True, side_effect=[200, 350]
        ):
            tracker.mark_config_loading_finished()
            tracker.mark_file_loading_finished()
        result = tracker.build()
        assert result.parse is None
        assert result.transform is None
        assert result.validate is None

    def test_overall_equals_phase_sum(self):
        tracker = _make_tracker([100])
        with patch.object(
            time, "perf_counter_ns", autospec=True, side_effect=[200, 350]
        ):
            tracker.mark_config_loading_finished()
            tracker.mark_file_loading_finished()
        result = tracker.build()
        assert result.file_loading is not None
        assert result.overall == result.config_loading + result.file_loading


class TestBuildAfterParse:
    def test_phases_through_parse_are_set(self):
        tracker = _make_tracker([100])
        with patch.object(
            time, "perf_counter_ns", autospec=True, side_effect=[200, 350, 500]
        ):
            tracker.mark_config_loading_finished()
            tracker.mark_file_loading_finished()
            tracker.mark_parse_finished()
        result = tracker.build()
        assert result.config_loading == 100
        assert result.file_loading == 150
        assert result.parse == 150

    def test_later_phases_are_none(self):
        tracker = _make_tracker([100])
        with patch.object(
            time, "perf_counter_ns", autospec=True, side_effect=[200, 350, 500]
        ):
            tracker.mark_config_loading_finished()
            tracker.mark_file_loading_finished()
            tracker.mark_parse_finished()
        result = tracker.build()
        assert result.transform is None
        assert result.validate is None


class TestBuildAfterTransform:
    def test_phases_through_transform_are_set(self):
        tracker = _make_tracker([100])
        with patch.object(
            time, "perf_counter_ns", autospec=True, side_effect=[200, 350, 500, 700]
        ):
            tracker.mark_config_loading_finished()
            tracker.mark_file_loading_finished()
            tracker.mark_parse_finished()
            tracker.mark_transform_finished()
        result = tracker.build()
        assert result.config_loading == 100
        assert result.file_loading == 150
        assert result.parse == 150
        assert result.transform == 200

    def test_validate_is_none(self):
        tracker = _make_tracker([100])
        with patch.object(
            time, "perf_counter_ns", autospec=True, side_effect=[200, 350, 500, 700]
        ):
            tracker.mark_config_loading_finished()
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
            side_effect=[200, 350, 500, 700, 900],
        ):
            tracker.mark_config_loading_finished()
            tracker.mark_file_loading_finished()
            tracker.mark_parse_finished()
            tracker.mark_transform_finished()
            tracker.mark_validate_finished()
        result = tracker.build()
        assert result.config_loading == 100
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
            side_effect=[200, 350, 500, 700, 900],
        ):
            tracker.mark_config_loading_finished()
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
            result.config_loading
            + result.file_loading
            + result.parse
            + result.transform
            + result.validate
        )


class TestBuildWithoutConfigLoadingRaises:
    def test_raises_value_error(self):
        tracker = _make_tracker([100])
        with pytest.raises(ValueError, match="Config loading timing was not recorded"):
            tracker.build()
