from __future__ import annotations

import pathlib

import pytest

from define.compiler import path_tracker


def _path(name: str) -> pathlib.PurePosixPath:
    return pathlib.PurePosixPath(name)


class TestPathTracker:
    def test_is_tracked_unknown(self):
        tracker: path_tracker.PathTracker[str] = path_tracker.PathTracker()
        assert not tracker.is_tracked(_path("a.def"))

    def test_mark_in_progress(self):
        tracker: path_tracker.PathTracker[str] = path_tracker.PathTracker()
        tracker.mark_in_progress(_path("a.def"))
        assert tracker.is_tracked(_path("a.def"))
        assert not tracker.has_result(_path("a.def"))

    def test_set_and_get_result(self):
        tracker: path_tracker.PathTracker[str] = path_tracker.PathTracker()
        tracker.mark_in_progress(_path("a.def"))
        tracker.set_result(_path("a.def"), "ok")
        assert tracker.has_result(_path("a.def"))
        assert tracker.get_result(_path("a.def")) == "ok"

    def test_get_result_raises_when_in_progress(self):
        tracker: path_tracker.PathTracker[str] = path_tracker.PathTracker()
        tracker.mark_in_progress(_path("a.def"))
        with pytest.raises(KeyError):
            _ = tracker.get_result(_path("a.def"))

    def test_completed_results_excludes_in_progress(self):
        tracker: path_tracker.PathTracker[str] = path_tracker.PathTracker()
        tracker.mark_in_progress(_path("a.def"))
        tracker.set_result(_path("a.def"), "done")
        tracker.mark_in_progress(_path("b.def"))
        assert tracker.completed_results() == ["done"]

    def test_completed_results_excludes_not_found(self):
        tracker: path_tracker.PathTracker[str] = path_tracker.PathTracker()
        tracker.mark_in_progress(_path("a.def"))
        tracker.set_result(_path("a.def"), "done")
        tracker.mark_not_found(_path("a.def"))
        assert tracker.completed_results() == []

    def test_completed_results_preserves_order(self):
        tracker: path_tracker.PathTracker[str] = path_tracker.PathTracker()
        for name in ["c.def", "a.def", "b.def"]:
            tracker.mark_in_progress(_path(name))
            tracker.set_result(_path(name), name)
        assert tracker.completed_results() == ["c.def", "a.def", "b.def"]

    def test_mark_not_found_does_not_affect_is_tracked(self):
        tracker: path_tracker.PathTracker[str] = path_tracker.PathTracker()
        tracker.mark_not_found(_path("a.def"))
        assert not tracker.is_tracked(_path("a.def"))
