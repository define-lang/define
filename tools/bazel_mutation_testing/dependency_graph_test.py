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
""",
    frozenset(),
    frozenset(),
)

# Each pyright_test depends on its list of checked files, as does the venv that
# rules_py makes beside it.
_PYRIGHT_GRAPH = dependency_graph.from_dot(
    """\
digraph mygraph {
  "//pkg:pyright_test" -> "//pkg:pyright_test_sources"
  "//pkg:_pyright_test.venv" -> "//pkg:pyright_test_sources"
  "//pkg:pyright_test_sources" -> "//pkg:lib"
  "//pkg:pyright_test_sources" -> "//pkg/sub:lib"
  "//pkg:lib" -> "//pkg:lib.py"
  "//pkg:lib" -> "//pkg:checked_only_here.py"
  "//pkg/sub:lib" -> "//pkg/sub:lib.py"
  "//pkg/sub:lib" -> "//pkg/sub:lib.rs"
  "//pkg/sub:lib" -> "//pkg:lib"
  "//pkg/sub:pyright_test" -> "//pkg/sub:pyright_test_sources"
  "//pkg/sub:pyright_test_sources" -> "//pkg/sub:lib"
  "//user:pyright_test" -> "//user:pyright_test_sources"
  "//user:pyright_test_sources" -> "//user:lib"
  "//user:lib" -> "//pkg:lib"
  "//user:lib" -> "//user:lib.py"
  "//pkg:unchecked_test" -> "//pkg:unchecked.py"
}
""",
    frozenset({"//pkg:pyright_test", "//pkg/sub:pyright_test", "//user:pyright_test"}),
    frozenset(
        {
            "//pkg:pyright_test_sources",
            "//pkg/sub:pyright_test_sources",
            "//user:pyright_test_sources",
        }
    ),
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


def test_a_pyright_test_of_another_package_does_not_check_a_file_it_imports():
    assert _PYRIGHT_GRAPH.pyright_tests_not_checking("pkg/lib.py") == {
        "//pkg/sub:pyright_test",
        "//user:pyright_test",
    }


def test_a_pyright_test_checks_the_packages_below_it_that_it_lists():
    assert _PYRIGHT_GRAPH.pyright_tests_not_checking("pkg/sub/lib.py") == {
        "//user:pyright_test"
    }


def test_no_pyright_test_checks_a_file_that_none_depends_on():
    assert _PYRIGHT_GRAPH.pyright_tests_not_checking("pkg/unchecked.py") == {
        "//pkg:pyright_test",
        "//pkg/sub:pyright_test",
        "//user:pyright_test",
    }


def test_no_pyright_test_checks_a_file_that_is_not_python():
    assert _PYRIGHT_GRAPH.pyright_tests_not_checking("pkg/sub/lib.rs") == {
        "//pkg:pyright_test",
        "//pkg/sub:pyright_test",
        "//user:pyright_test",
    }
