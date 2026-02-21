# pyright: reportUnusedCallResult=false
from __future__ import annotations

from pathlib import PurePosixPath

import pytest

from define.compiler import path_tracker


class TestPathTracker:
    def test_is_tracked_unknown(self):
        tracker: path_tracker.PathTracker[str] = path_tracker.PathTracker()
        assert not tracker.is_tracked(PurePosixPath("a.def"))

    def test_mark_in_progress(self):
        tracker: path_tracker.PathTracker[str] = path_tracker.PathTracker()
        tracker.mark_in_progress(PurePosixPath("a.def"))
        assert tracker.is_tracked(PurePosixPath("a.def"))
        assert not tracker.has_result(PurePosixPath("a.def"))

    def test_set_and_get_result(self):
        tracker: path_tracker.PathTracker[str] = path_tracker.PathTracker()
        tracker.mark_in_progress(PurePosixPath("a.def"))
        tracker.set_result(PurePosixPath("a.def"), "ok")
        assert tracker.has_result(PurePosixPath("a.def"))
        assert tracker.get_result(PurePosixPath("a.def")) == "ok"

    def test_get_result_raises_when_in_progress(self):
        tracker: path_tracker.PathTracker[str] = path_tracker.PathTracker()
        tracker.mark_in_progress(PurePosixPath("a.def"))
        with pytest.raises(KeyError):
            tracker.get_result(PurePosixPath("a.def"))

    def test_completed_results_excludes_in_progress(self):
        tracker: path_tracker.PathTracker[str] = path_tracker.PathTracker()
        tracker.mark_in_progress(PurePosixPath("a.def"))
        tracker.set_result(PurePosixPath("a.def"), "done")
        tracker.mark_in_progress(PurePosixPath("b.def"))
        assert tracker.completed_results() == ["done"]

    def test_completed_results_excludes_not_found(self):
        tracker: path_tracker.PathTracker[str] = path_tracker.PathTracker()
        tracker.mark_in_progress(PurePosixPath("a.def"))
        tracker.set_result(PurePosixPath("a.def"), "done")
        tracker.mark_not_found(PurePosixPath("a.def"))
        assert tracker.completed_results() == []

    def test_completed_results_preserves_order(self):
        tracker: path_tracker.PathTracker[str] = path_tracker.PathTracker()
        for name in ["c.def", "a.def", "b.def"]:
            tracker.mark_in_progress(PurePosixPath(name))
            tracker.set_result(PurePosixPath(name), name)
        assert tracker.completed_results() == ["c.def", "a.def", "b.def"]

    def test_mark_not_found_does_not_affect_is_tracked(self):
        tracker: path_tracker.PathTracker[str] = path_tracker.PathTracker()
        tracker.mark_not_found(PurePosixPath("a.def"))
        assert not tracker.is_tracked(PurePosixPath("a.def"))


class TestSubRootTracking:
    def test_set_and_seen_sub_root_empty_path(self):
        tracker: path_tracker.PathTracker[str] = path_tracker.PathTracker()
        root = PurePosixPath("")
        tracker.set_sub_root(root, "my.universe", {"dep": PurePosixPath("ext/dep")})
        assert tracker.seen_sub_root(root)

    def test_set_and_seen_sub_root_non_empty(self):
        tracker: path_tracker.PathTracker[str] = path_tracker.PathTracker()
        root = PurePosixPath("ext/dep")
        tracker.set_sub_root(root, "dep.universe", {})
        assert tracker.seen_sub_root(root)

    def test_seen_sub_root_false_when_not_set(self):
        tracker: path_tracker.PathTracker[str] = path_tracker.PathTracker()
        assert not tracker.seen_sub_root(PurePosixPath("ext/dep"))

    def test_set_sub_root_duplicate_root_raises(self):
        tracker: path_tracker.PathTracker[str] = path_tracker.PathTracker()
        root = PurePosixPath("")
        tracker.set_sub_root(root, "my.universe", {})
        with pytest.raises(ValueError, match="already registered"):
            tracker.set_sub_root(root, "other.universe", {})

    def test_set_sub_root_duplicate_fqun_raises(self):
        tracker: path_tracker.PathTracker[str] = path_tracker.PathTracker()
        tracker.set_sub_root(PurePosixPath(""), "my.universe", {})
        with pytest.raises(ValueError, match="already maps"):
            tracker.set_sub_root(PurePosixPath("ext/other"), "my.universe", {})

    def test_set_sub_root_unknown_fqun_raises(self):
        tracker: path_tracker.PathTracker[str] = path_tracker.PathTracker()
        tracker.mark_unknown_universe("bad.universe")
        with pytest.raises(ValueError, match="marked unknown"):
            tracker.set_sub_root(PurePosixPath(""), "bad.universe", {})

    def test_expected_universe_empty_root(self):
        tracker: path_tracker.PathTracker[str] = path_tracker.PathTracker()
        tracker.set_sub_root(PurePosixPath(""), "my.universe", {})
        assert tracker.expected_universe(PurePosixPath("foo/bar")) == "my.universe"

    def test_expected_universe_nested_sub_root(self):
        tracker: path_tracker.PathTracker[str] = path_tracker.PathTracker()
        tracker.set_sub_root(
            PurePosixPath(""), "my.universe", {"dep": PurePosixPath("ext/dep")}
        )
        tracker.set_sub_root(PurePosixPath("ext/dep"), "dep.universe", {})
        assert tracker.expected_universe(PurePosixPath("ext/dep/foo")) == "dep.universe"
        assert tracker.expected_universe(PurePosixPath("local/bar")) == "my.universe"

    def test_expected_universe_deeply_nested(self):
        tracker: path_tracker.PathTracker[str] = path_tracker.PathTracker()
        tracker.set_sub_root(PurePosixPath(""), "root", {"a": PurePosixPath("a")})
        tracker.set_sub_root(PurePosixPath("a"), "a.uni", {"b": PurePosixPath("a/b")})
        tracker.set_sub_root(PurePosixPath("a/b"), "b.uni", {})
        assert tracker.expected_universe(PurePosixPath("a/b/c/d")) == "b.uni"
        assert tracker.expected_universe(PurePosixPath("a/x")) == "a.uni"
        assert tracker.expected_universe(PurePosixPath("other")) == "root"

    def test_expected_universe_no_sub_root_raises(self):
        tracker: path_tracker.PathTracker[str] = path_tracker.PathTracker()
        with pytest.raises(KeyError):
            tracker.expected_universe(PurePosixPath("foo"))

    def test_path_to_universe_project_root(self):
        tracker: path_tracker.PathTracker[str] = path_tracker.PathTracker()
        tracker.set_sub_root(PurePosixPath(""), "my.universe", {})
        assert tracker.path_to_universe("my.universe") == PurePosixPath("")

    def test_path_to_universe_non_empty(self):
        tracker: path_tracker.PathTracker[str] = path_tracker.PathTracker()
        tracker.set_sub_root(PurePosixPath("ext/dep"), "dep.universe", {})
        assert tracker.path_to_universe("dep.universe") == PurePosixPath("ext/dep")

    def test_path_to_universe_unknown_raises(self):
        tracker: path_tracker.PathTracker[str] = path_tracker.PathTracker()
        with pytest.raises(KeyError):
            tracker.path_to_universe("nope")

    def test_mark_and_is_unknown_universe(self):
        tracker: path_tracker.PathTracker[str] = path_tracker.PathTracker()
        assert not tracker.is_unknown_universe("bad")
        tracker.mark_unknown_universe("bad")
        assert tracker.is_unknown_universe("bad")

    def test_universe_has_sub_root_in(self):
        tracker: path_tracker.PathTracker[str] = path_tracker.PathTracker()
        tracker.set_sub_root(
            PurePosixPath(""), "my.universe", {"dep": PurePosixPath("ext/dep")}
        )
        assert tracker.universe_has_sub_root_in("dep", PurePosixPath(""))

    def test_universe_has_sub_root_in_missing(self):
        tracker: path_tracker.PathTracker[str] = path_tracker.PathTracker()
        tracker.set_sub_root(PurePosixPath(""), "my.universe", {})
        assert not tracker.universe_has_sub_root_in("dep", PurePosixPath(""))

    def test_universe_has_sub_root_in_unregistered_root_raises(self):
        tracker: path_tracker.PathTracker[str] = path_tracker.PathTracker()
        with pytest.raises(KeyError):
            tracker.universe_has_sub_root_in("dep", PurePosixPath("not/registered"))
