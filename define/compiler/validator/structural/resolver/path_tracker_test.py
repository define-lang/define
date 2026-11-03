# pyright: reportUnusedCallResult=false
from __future__ import annotations

from pathlib import PurePosixPath

import pytest

from define.compiler import config, constants
from define.compiler.data_structures import define_path
from define.compiler.validator.structural.resolver import path_tracker


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
    def test_is_under_failed_root_returns_false_without_failed_root(self):
        tracker: path_tracker.PathTracker[str] = path_tracker.PathTracker()
        tracker.register_project_root(
            define_path.DefinePath("lib"),
            config.ProjectRootConfig(fqun="lib.uni", sub_roots={}),
        )
        assert not tracker.is_under_failed_root(define_path.DefinePath("lib"))
        assert not tracker.is_under_failed_root(define_path.DefinePath("lib/a.dfn"))

    def test_is_under_failed_root_returns_true_for_descendant(self):
        tracker: path_tracker.PathTracker[str] = path_tracker.PathTracker()
        tracker.mark_root_failed(define_path.DefinePath("lib"))
        assert tracker.is_under_failed_root(define_path.DefinePath("lib/a.dfn"))
        assert not tracker.is_under_failed_root(define_path.DefinePath("other/a.dfn"))

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


class TestSubRootDeclarations:
    def test_first_declaration_of_a_path_wins(self):
        tracker: path_tracker.PathTracker[str] = path_tracker.PathTracker()
        first = config.LocalDependencyEntry(
            PurePosixPath(".define/deps/local.defcl"), "first.universe", "lib"
        )
        second = config.LocalDependencyEntry(
            PurePosixPath(".define/deps/local.defcl"), "second.universe", "lib"
        )
        sub_root = define_path.DefinePath("lib")
        assert tracker.declare_sub_root(sub_root, first) is None
        assert tracker.declare_sub_root(sub_root, second) == first
        assert tracker.declared_sub_root_containing(
            define_path.EMPTY, define_path.DefinePath("lib/x.dfn")
        ) == (sub_root, first)

    def test_path_in_a_directory_under_a_declared_sub_root(self):
        tracker: path_tracker.PathTracker[str] = path_tracker.PathTracker()
        entry = config.LocalDependencyEntry(
            PurePosixPath(".define/deps/local.defcl"), "dep.universe", "a/b"
        )
        sub_root = define_path.DefinePath("a/b")
        tracker.declare_sub_root(sub_root, entry)
        assert tracker.declared_sub_root_containing(
            define_path.EMPTY, define_path.DefinePath("a/b/c/x.dfn")
        ) == (sub_root, entry)

    def test_path_beside_a_declared_sub_root(self):
        tracker: path_tracker.PathTracker[str] = path_tracker.PathTracker()
        entry = config.LocalDependencyEntry(
            PurePosixPath(".define/deps/local.defcl"), "dep.universe", "a/b"
        )
        tracker.declare_sub_root(define_path.DefinePath("a/b"), entry)
        assert (
            tracker.declared_sub_root_containing(
                define_path.EMPTY, define_path.DefinePath("a/c/x.dfn")
            )
            is None
        )


class TestUniverseRoot:
    def test_own_universe_is_the_referencing_root(self):
        tracker: path_tracker.PathTracker[str] = path_tracker.PathTracker()
        root = define_path.DefinePath("sub")
        assert tracker.universe_root(None, root) == root

    def test_configured_universe_is_under_the_referencing_root(self):
        tracker: path_tracker.PathTracker[str] = path_tracker.PathTracker()
        tracker.register_project_root(
            define_path.EMPTY,
            config.ProjectRootConfig(
                fqun="a.com:main",
                sub_roots={"b.com:lib": define_path.DefinePath("deps/lib")},
            ),
        )
        assert tracker.universe_root(
            "b.com:lib", define_path.EMPTY
        ) == define_path.DefinePath("deps/lib")

    def test_unconfigured_universe_has_no_root(self):
        tracker: path_tracker.PathTracker[str] = path_tracker.PathTracker()
        tracker.register_project_root(
            define_path.EMPTY, config.ProjectRootConfig(fqun="a.com:main", sub_roots={})
        )
        assert tracker.universe_root("b.com:lib", define_path.EMPTY) is None

    def test_standard_universe_needs_no_configuration(self):
        tracker: path_tracker.PathTracker[str] = path_tracker.PathTracker()
        tracker.register_project_root(
            define_path.EMPTY, config.ProjectRootConfig(fqun="a.com:main", sub_roots={})
        )
        assert (
            tracker.universe_root(constants.STANDARD_UNIVERSE, define_path.EMPTY)
            == constants.STANDARD_LIBRARY_ROOT
        )
