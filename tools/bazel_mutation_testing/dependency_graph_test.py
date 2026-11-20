from __future__ import annotations

import pytest

from tools.bazel_mutation_testing import dependency_graph

_GRAPH = dependency_graph.from_dot(
    """\
digraph mygraph {
  node [shape=box];
  "//pkg:near_test"
  "//pkg:near_test" -> "//pkg:lib"
  "//pkg:also_near_test" -> "//pkg:lib"
  "//pkg:lib" -> "//pkg:sub/lib.rs"
  "//other:far_test" -> "//other:wrapper"
  "//other:wrapper" -> "//pkg:lib"
  "//:top_test" -> "//:top.py"
  "@external//:test" -> "//pkg:lib"
}
"""
)


def test_the_closest_test_has_the_fewest_dependencies_between_it_and_the_file():
    assert (
        _GRAPH.closest_test(
            "pkg/sub/lib.rs", frozenset({"//other:far_test", "//pkg:near_test"})
        )
        == "//pkg:near_test"
    )


def test_a_test_farther_away_is_closest_when_no_nearer_test_is_given():
    assert (
        _GRAPH.closest_test("pkg/sub/lib.rs", frozenset({"//other:far_test"}))
        == "//other:far_test"
    )


def test_of_tests_at_the_same_distance_the_first_by_label_is_closest():
    assert (
        _GRAPH.closest_test(
            "pkg/sub/lib.rs",
            frozenset({"//pkg:near_test", "//pkg:also_near_test"}),
        )
        == "//pkg:also_near_test"
    )


def test_a_file_in_the_top_package_has_a_closest_test():
    assert _GRAPH.closest_test("top.py", frozenset({"//:top_test"})) == "//:top_test"


def test_a_file_that_no_given_test_depends_on_has_no_closest_test():
    with pytest.raises(dependency_graph.NoDependentTestError):
        _ = _GRAPH.closest_test("top.py", frozenset({"//pkg:near_test"}))
