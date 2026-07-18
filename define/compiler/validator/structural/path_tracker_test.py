# pyright: reportUnusedCallResult=false
from __future__ import annotations

import pytest

from define.compiler import config
from define.compiler.data_structures import define_path
from define.compiler.validator.structural import path_tracker


class TestPathTracker:
    def test_is_tracked_unknown(self):
        tracker: path_tracker.PathTracker[str] = path_tracker.PathTracker()
        assert not tracker.is_tracked(define_path.DefinePath("a.dfn"))

    def test_mark_in_progress(self):
        tracker: path_tracker.PathTracker[str] = path_tracker.PathTracker()
        tracker.mark_in_progress(define_path.DefinePath("a.dfn"))
        assert tracker.is_tracked(define_path.DefinePath("a.dfn"))

    def test_set_and_get_result(self):
        tracker: path_tracker.PathTracker[str] = path_tracker.PathTracker()
        tracker.mark_in_progress(define_path.DefinePath("a.dfn"))
        tracker.set_result(define_path.DefinePath("a.dfn"), "ok")
        assert tracker.get_result(define_path.DefinePath("a.dfn")) == "ok"

    def test_get_result_raises_when_in_progress(self):
        tracker: path_tracker.PathTracker[str] = path_tracker.PathTracker()
        tracker.mark_in_progress(define_path.DefinePath("a.dfn"))
        with pytest.raises(KeyError):
            tracker.get_result(define_path.DefinePath("a.dfn"))

    def test_completed_results_excludes_in_progress(self):
        tracker: path_tracker.PathTracker[str] = path_tracker.PathTracker()
        tracker.mark_in_progress(define_path.DefinePath("a.dfn"))
        tracker.set_result(define_path.DefinePath("a.dfn"), "done")
        tracker.mark_in_progress(define_path.DefinePath("b.dfn"))
        assert tracker.completed_results() == ["done"]

    def test_completed_results_excludes_not_found(self):
        tracker: path_tracker.PathTracker[str] = path_tracker.PathTracker()
        tracker.mark_in_progress(define_path.DefinePath("a.dfn"))
        tracker.set_result(define_path.DefinePath("a.dfn"), "done")
        tracker.mark_not_found(define_path.DefinePath("a.dfn"))
        assert tracker.completed_results() == []

    def test_completed_results_preserves_order(self):
        tracker: path_tracker.PathTracker[str] = path_tracker.PathTracker()
        for name in ["c.dfn", "a.dfn", "b.dfn"]:
            tracker.mark_in_progress(define_path.DefinePath(name))
            tracker.set_result(define_path.DefinePath(name), name)
        assert tracker.completed_results() == ["c.dfn", "a.dfn", "b.dfn"]

    def test_mark_not_found_does_not_affect_is_tracked(self):
        tracker: path_tracker.PathTracker[str] = path_tracker.PathTracker()
        tracker.mark_not_found(define_path.DefinePath("a.dfn"))
        assert not tracker.is_tracked(define_path.DefinePath("a.dfn"))


class TestSubRootTracking:
    def test_project_root_loaded_false_when_not_registered(self):
        tracker: path_tracker.PathTracker[str] = path_tracker.PathTracker()
        assert not tracker.project_root_loaded(define_path.DefinePath("ext/dep"))

    def test_project_root_loaded_true_after_register(self):
        tracker: path_tracker.PathTracker[str] = path_tracker.PathTracker()
        tracker.register_project_root(
            define_path.EMPTY,
            config.ProjectRootConfig(fqun="my.universe", sub_roots={}),
        )
        assert tracker.project_root_loaded(define_path.EMPTY)

    def test_register_and_fqun_for_root_empty_path(self):
        tracker: path_tracker.PathTracker[str] = path_tracker.PathTracker()
        tracker.register_project_root(
            define_path.EMPTY,
            config.ProjectRootConfig(
                fqun="my.universe",
                sub_roots={"dep": define_path.DefinePath("ext/dep")},
            ),
        )
        assert tracker.fqun_for_root(define_path.EMPTY) == "my.universe"

    def test_register_and_fqun_for_root_non_empty(self):
        tracker: path_tracker.PathTracker[str] = path_tracker.PathTracker()
        root = define_path.DefinePath("ext/dep")
        tracker.register_project_root(
            root, config.ProjectRootConfig(fqun="dep.universe", sub_roots={})
        )
        assert tracker.fqun_for_root(root) == "dep.universe"

    def test_root_for_fqun_returns_root(self):
        tracker: path_tracker.PathTracker[str] = path_tracker.PathTracker()
        tracker.register_project_root(
            define_path.EMPTY,
            config.ProjectRootConfig(
                fqun="my.universe",
                sub_roots={"dep": define_path.DefinePath("ext/dep")},
            ),
        )
        assert tracker.root_for_fqun("my.universe") == define_path.EMPTY

    def test_root_for_fqun_returns_none_when_no_match(self):
        tracker: path_tracker.PathTracker[str] = path_tracker.PathTracker()
        tracker.register_project_root(
            define_path.EMPTY,
            config.ProjectRootConfig(fqun="my.universe", sub_roots={}),
        )
        assert tracker.root_for_fqun("other.universe") is None

    def test_root_for_fqun_returns_none_when_empty(self):
        tracker: path_tracker.PathTracker[str] = path_tracker.PathTracker()
        assert tracker.root_for_fqun("my.universe") is None

    def test_fqun_for_root_none_when_not_registered(self):
        tracker: path_tracker.PathTracker[str] = path_tracker.PathTracker()
        assert tracker.fqun_for_root(define_path.DefinePath("ext/dep")) is None

    def test_config_for_root_returns_registered_config(self):
        tracker: path_tracker.PathTracker[str] = path_tracker.PathTracker()
        tracker.register_project_root(
            define_path.EMPTY,
            config.ProjectRootConfig(
                fqun="my.universe",
                sub_roots={"dep": define_path.DefinePath("ext/dep")},
            ),
        )
        root_config = tracker.config_for_root(define_path.EMPTY)
        assert root_config is not None
        assert root_config.fqun == "my.universe"
        assert root_config.sub_roots == {"dep": define_path.DefinePath("ext/dep")}

    def test_config_for_root_none_when_not_registered(self):
        tracker: path_tracker.PathTracker[str] = path_tracker.PathTracker()
        assert tracker.config_for_root(define_path.DefinePath("ext/dep")) is None

    def test_register_project_root_duplicate_root_raises(self):
        tracker: path_tracker.PathTracker[str] = path_tracker.PathTracker()
        tracker.register_project_root(
            define_path.EMPTY,
            config.ProjectRootConfig(fqun="my.universe", sub_roots={}),
        )
        with pytest.raises(ValueError, match="already registered"):
            tracker.register_project_root(
                define_path.EMPTY,
                config.ProjectRootConfig(fqun="other.universe", sub_roots={}),
            )

    def test_sub_root_location(self):
        tracker: path_tracker.PathTracker[str] = path_tracker.PathTracker()
        tracker.register_project_root(
            define_path.EMPTY,
            config.ProjectRootConfig(
                fqun="my.universe",
                sub_roots={"dep": define_path.DefinePath("ext/dep")},
            ),
        )
        assert tracker.sub_root_location(
            "dep", define_path.EMPTY
        ) == define_path.DefinePath("ext/dep")

    def test_sub_root_location_unregistered_parent_raises(self):
        tracker: path_tracker.PathTracker[str] = path_tracker.PathTracker()
        with pytest.raises(KeyError):
            tracker.sub_root_location("dep", define_path.DefinePath("not/registered"))

    def test_sub_root_location_unknown_fqun_raises(self):
        tracker: path_tracker.PathTracker[str] = path_tracker.PathTracker()
        tracker.register_project_root(
            define_path.EMPTY,
            config.ProjectRootConfig(fqun="my.universe", sub_roots={}),
        )
        with pytest.raises(KeyError):
            tracker.sub_root_location("unknown", define_path.EMPTY)


class TestConflictDetection:
    def test_find_enclosing_root_no_roots_raises(self):
        tracker: path_tracker.PathTracker[str] = path_tracker.PathTracker()
        with pytest.raises(KeyError, match="no project root registered"):
            tracker.find_enclosing_root(define_path.DefinePath("foo/bar.dfn"))

    def test_find_enclosing_root_returns_project_root(self):
        tracker: path_tracker.PathTracker[str] = path_tracker.PathTracker()
        tracker.register_project_root(
            define_path.EMPTY,
            config.ProjectRootConfig(fqun="root.uni", sub_roots={}),
        )
        assert (
            tracker.find_enclosing_root(define_path.DefinePath("foo/bar.dfn"))
            == define_path.EMPTY
        )

    def test_find_enclosing_root_returns_nested(self):
        tracker: path_tracker.PathTracker[str] = path_tracker.PathTracker()
        tracker.register_project_root(
            define_path.EMPTY,
            config.ProjectRootConfig(fqun="root.uni", sub_roots={}),
        )
        tracker.register_project_root(
            define_path.DefinePath("lib"),
            config.ProjectRootConfig(fqun="lib.uni", sub_roots={}),
        )
        assert tracker.find_enclosing_root(
            define_path.DefinePath("lib/foo.dfn")
        ) == define_path.DefinePath("lib")

    def test_find_enclosing_root_returns_most_specific(self):
        tracker: path_tracker.PathTracker[str] = path_tracker.PathTracker()
        tracker.register_project_root(
            define_path.EMPTY,
            config.ProjectRootConfig(fqun="root.uni", sub_roots={}),
        )
        tracker.register_project_root(
            define_path.DefinePath("lib"),
            config.ProjectRootConfig(fqun="lib.uni", sub_roots={}),
        )
        tracker.register_project_root(
            define_path.DefinePath("lib/inner"),
            config.ProjectRootConfig(fqun="inner.uni", sub_roots={}),
        )
        assert tracker.find_enclosing_root(
            define_path.DefinePath("lib/inner/x.dfn")
        ) == define_path.DefinePath("lib/inner")

    def test_first_tracked_file_under_no_files(self):
        tracker: path_tracker.PathTracker[str] = path_tracker.PathTracker()
        tracker.register_project_root(
            define_path.EMPTY,
            config.ProjectRootConfig(fqun="root.uni", sub_roots={}),
        )
        assert tracker.first_tracked_file_under(define_path.DefinePath("lib")) == (
            None,
            None,
        )

    def test_first_tracked_file_under_finds_conflict(self):
        tracker: path_tracker.PathTracker[str] = path_tracker.PathTracker()
        tracker.register_project_root(
            define_path.EMPTY,
            config.ProjectRootConfig(fqun="root.uni", sub_roots={}),
        )
        tracker.mark_in_progress(define_path.DefinePath("lib/target.dfn"))
        result = tracker.first_tracked_file_under(define_path.DefinePath("lib"))
        assert result == (define_path.DefinePath("lib/target.dfn"), "root.uni")

    def test_first_tracked_file_under_returns_nested_sub_root_owner(self):
        tracker: path_tracker.PathTracker[str] = path_tracker.PathTracker()
        tracker.register_project_root(
            define_path.EMPTY,
            config.ProjectRootConfig(fqun="root.uni", sub_roots={}),
        )
        tracker.register_project_root(
            define_path.DefinePath("lib/inner"),
            config.ProjectRootConfig(fqun="inner.uni", sub_roots={}),
        )
        tracker.mark_in_progress(define_path.DefinePath("lib/inner/x.dfn"))
        result = tracker.first_tracked_file_under(define_path.DefinePath("lib"))
        assert result == (define_path.DefinePath("lib/inner/x.dfn"), "inner.uni")
