# pyright: reportUnusedCallResult=false
from __future__ import annotations

from pathlib import PurePosixPath

import pytest

from define.compiler.validator import path_tracker


class TestPathTracker:
    def test_is_tracked_unknown(self):
        tracker: path_tracker.PathTracker[str] = path_tracker.PathTracker()
        assert not tracker.is_tracked(PurePosixPath("a.def"))

    def test_mark_in_progress(self):
        tracker: path_tracker.PathTracker[str] = path_tracker.PathTracker()
        tracker.mark_in_progress(PurePosixPath("a.def"))
        assert tracker.is_tracked(PurePosixPath("a.def"))

    def test_set_and_get_result(self):
        tracker: path_tracker.PathTracker[str] = path_tracker.PathTracker()
        tracker.mark_in_progress(PurePosixPath("a.def"))
        tracker.set_result(PurePosixPath("a.def"), "ok")
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
    def test_project_root_loaded_false_when_not_registered(self):
        tracker: path_tracker.PathTracker[str] = path_tracker.PathTracker()
        assert not tracker.project_root_loaded(PurePosixPath("ext/dep"))

    def test_project_root_loaded_true_after_register(self):
        tracker: path_tracker.PathTracker[str] = path_tracker.PathTracker()
        root = PurePosixPath("")
        tracker.register_project_root(root, "my.universe", {})
        assert tracker.project_root_loaded(root)

    def test_register_and_fqun_for_root_empty_path(self):
        tracker: path_tracker.PathTracker[str] = path_tracker.PathTracker()
        root = PurePosixPath("")
        tracker.register_project_root(
            root, "my.universe", {"dep": PurePosixPath("ext/dep")}
        )
        assert tracker.fqun_for_root(root) == "my.universe"

    def test_register_and_fqun_for_root_non_empty(self):
        tracker: path_tracker.PathTracker[str] = path_tracker.PathTracker()
        root = PurePosixPath("ext/dep")
        tracker.register_project_root(root, "dep.universe", {})
        assert tracker.fqun_for_root(root) == "dep.universe"

    def test_root_for_fqun_returns_root(self):
        tracker: path_tracker.PathTracker[str] = path_tracker.PathTracker()
        tracker.register_project_root(
            PurePosixPath(""), "my.universe", {"dep": PurePosixPath("ext/dep")}
        )
        assert tracker.root_for_fqun("my.universe") == PurePosixPath(".")

    def test_root_for_fqun_returns_none_when_no_match(self):
        tracker: path_tracker.PathTracker[str] = path_tracker.PathTracker()
        tracker.register_project_root(PurePosixPath(""), "my.universe", {})
        assert tracker.root_for_fqun("other.universe") is None

    def test_root_for_fqun_returns_none_when_empty(self):
        tracker: path_tracker.PathTracker[str] = path_tracker.PathTracker()
        assert tracker.root_for_fqun("my.universe") is None

    def test_fqun_for_root_none_when_not_registered(self):
        tracker: path_tracker.PathTracker[str] = path_tracker.PathTracker()
        assert tracker.fqun_for_root(PurePosixPath("ext/dep")) is None

    def test_register_project_root_duplicate_root_raises(self):
        tracker: path_tracker.PathTracker[str] = path_tracker.PathTracker()
        root = PurePosixPath("")
        tracker.register_project_root(root, "my.universe", {})
        with pytest.raises(ValueError, match="already registered"):
            tracker.register_project_root(root, "other.universe", {})

    def test_sub_root_location(self):
        tracker: path_tracker.PathTracker[str] = path_tracker.PathTracker()
        tracker.register_project_root(
            PurePosixPath(""), "my.universe", {"dep": PurePosixPath("ext/dep")}
        )
        assert tracker.sub_root_location("dep", PurePosixPath("")) == PurePosixPath(
            "ext/dep"
        )

    def test_sub_root_location_unregistered_parent_raises(self):
        tracker: path_tracker.PathTracker[str] = path_tracker.PathTracker()
        with pytest.raises(KeyError):
            tracker.sub_root_location("dep", PurePosixPath("not/registered"))

    def test_sub_root_location_unknown_fqun_raises(self):
        tracker: path_tracker.PathTracker[str] = path_tracker.PathTracker()
        tracker.register_project_root(PurePosixPath(""), "my.universe", {})
        with pytest.raises(KeyError):
            tracker.sub_root_location("unknown", PurePosixPath(""))


class TestConflictDetection:
    def test_find_enclosing_root_no_roots_raises(self):
        tracker: path_tracker.PathTracker[str] = path_tracker.PathTracker()
        with pytest.raises(KeyError, match="no project root registered"):
            tracker.find_enclosing_root(PurePosixPath("foo/bar.def"))

    def test_find_enclosing_root_returns_project_root(self):
        tracker: path_tracker.PathTracker[str] = path_tracker.PathTracker()
        tracker.register_project_root(PurePosixPath(""), "root.uni", {})
        assert tracker.find_enclosing_root(
            PurePosixPath("foo/bar.def")
        ) == PurePosixPath(".")

    def test_find_enclosing_root_returns_nested(self):
        tracker: path_tracker.PathTracker[str] = path_tracker.PathTracker()
        tracker.register_project_root(PurePosixPath(""), "root.uni", {})
        tracker.register_project_root(PurePosixPath("lib"), "lib.uni", {})
        assert tracker.find_enclosing_root(
            PurePosixPath("lib/foo.def")
        ) == PurePosixPath("lib")

    def test_find_enclosing_root_returns_most_specific(self):
        tracker: path_tracker.PathTracker[str] = path_tracker.PathTracker()
        tracker.register_project_root(PurePosixPath(""), "root.uni", {})
        tracker.register_project_root(PurePosixPath("lib"), "lib.uni", {})
        tracker.register_project_root(PurePosixPath("lib/inner"), "inner.uni", {})
        assert tracker.find_enclosing_root(
            PurePosixPath("lib/inner/x.def")
        ) == PurePosixPath("lib/inner")

    def test_first_tracked_file_under_no_files(self):
        tracker: path_tracker.PathTracker[str] = path_tracker.PathTracker()
        tracker.register_project_root(PurePosixPath(""), "root.uni", {})
        assert tracker.first_tracked_file_under(PurePosixPath("lib")) == (None, None)

    def test_first_tracked_file_under_finds_conflict(self):
        tracker: path_tracker.PathTracker[str] = path_tracker.PathTracker()
        tracker.register_project_root(PurePosixPath(""), "root.uni", {})
        tracker.mark_in_progress(PurePosixPath("lib/target.def"))
        result = tracker.first_tracked_file_under(PurePosixPath("lib"))
        assert result == (PurePosixPath("lib/target.def"), "root.uni")

    def test_first_tracked_file_under_returns_nested_sub_root_owner(self):
        tracker: path_tracker.PathTracker[str] = path_tracker.PathTracker()
        tracker.register_project_root(PurePosixPath(""), "root.uni", {})
        tracker.register_project_root(PurePosixPath("lib/inner"), "inner.uni", {})
        tracker.mark_in_progress(PurePosixPath("lib/inner/x.def"))
        result = tracker.first_tracked_file_under(PurePosixPath("lib"))
        assert result == (PurePosixPath("lib/inner/x.def"), "inner.uni")
