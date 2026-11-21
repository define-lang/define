from __future__ import annotations

from typing import TYPE_CHECKING

from tools.bazel_mutation_testing import coverage, dependency_graph

if TYPE_CHECKING:
    import pathlib

_SOURCE = """\
def choose(first, second):
    if (
        first
        and second
    ):
        return first
    return second
"""

_GRAPH = dependency_graph.from_dot(
    """\
digraph mygraph {
  "//pkg:first_test" -> "//pkg:choose"
  "//pkg:second_test" -> "//pkg:choose"
  "//pkg:choose" -> "//pkg:choose.py"
  "//pkg:first_test" -> "//pkg:lib"
  "//pkg:lib" -> "//pkg:lib.rs"
}
""",
    frozenset(),
    frozenset(),
)

_PYRIGHT_GRAPH = dependency_graph.from_dot(
    """\
digraph mygraph {
  "//pkg:first_test" -> "//pkg:choose"
  "//pkg:choose" -> "//pkg:choose.py"
  "//pkg:first_test" -> "//pkg:lib"
  "//pkg:lib" -> "//pkg:lib.rs"
  "//pkg:pyright_test" -> "//pkg:pyright_test_sources"
  "//pkg:pyright_test_sources" -> "//pkg:choose"
  "//pkg:pyright_test_sources" -> "//pkg:lib"
  "//other:pyright_test" -> "//other:pyright_test_sources"
  "//other:pyright_test_sources" -> "//pkg:choose"
}
""",
    frozenset({"//pkg:pyright_test", "//other:pyright_test"}),
    frozenset({"//pkg:pyright_test_sources", "//other:pyright_test_sources"}),
)


def _report(path: str, hits: dict[int, int]) -> str:
    lines = [f"SF:{path}"]
    lines.extend(f"DA:{line},{count}" for line, count in hits.items())
    lines.append("end_of_record")
    return "\n".join(lines) + "\n"


def _write_source(tmp_path: pathlib.Path):
    (tmp_path / "pkg").mkdir()
    _ = (tmp_path / "pkg/choose.py").write_text(_SOURCE, encoding="utf-8", newline="\n")


def _coverage(tmp_path: pathlib.Path) -> coverage.Coverage:
    _write_source(tmp_path)
    return coverage.from_reports(
        {
            "//pkg:first_test": [
                _report("pkg/choose.py", {1: 1, 2: 1, 6: 1, 7: 0}),
                _report("pkg/lib.rs", {3: 1}),
            ],
            "//pkg:second_test": [_report("pkg/choose.py", {1: 1, 2: 1, 6: 0, 7: 1})],
            "//pkg:lint_test": [""],
        },
        tmp_path,
    )


def test_skips_the_tests_that_never_run_a_line(tmp_path: pathlib.Path):
    assert _coverage(tmp_path).select("pkg/choose.py", (7, 7), _GRAPH).skipped == {
        "//pkg:first_test"
    }


def test_a_line_of_a_statement_counts_as_its_first_line(tmp_path: pathlib.Path):
    assert (
        _coverage(tmp_path).select("pkg/choose.py", (4, 4), _GRAPH).skipped
        == frozenset()
    )


def test_a_body_line_is_its_own_statement(tmp_path: pathlib.Path):
    assert _coverage(tmp_path).select("pkg/choose.py", (6, 6), _GRAPH).skipped == {
        "//pkg:second_test"
    }


def test_a_test_whose_reports_cover_different_files_runs_each(tmp_path: pathlib.Path):
    assert _coverage(tmp_path).select("pkg/lib.rs", (3, 3), _GRAPH).skipped == {
        "//pkg:second_test"
    }


def test_an_unrecorded_line_skips_no_test(tmp_path: pathlib.Path):
    assert (
        _coverage(tmp_path).select("pkg/lib.rs", (9, 9), _GRAPH).skipped == frozenset()
    )


def test_a_line_that_no_test_runs_skips_every_reporting_test(tmp_path: pathlib.Path):
    _write_source(tmp_path)
    covered = coverage.from_reports(
        {
            "//pkg:first_test": [_report("pkg/choose.py", {7: 0})],
            "//pkg:lint_test": [""],
        },
        tmp_path,
    )

    assert covered.select("pkg/choose.py", (7, 7), _GRAPH) == coverage.Selection(
        skipped=frozenset({"//pkg:first_test"}), covering_tests=0, first_test=None
    )


def test_a_range_runs_the_tests_that_run_any_of_its_lines(tmp_path: pathlib.Path):
    assert (
        _coverage(tmp_path).select("pkg/choose.py", (6, 7), _GRAPH).skipped
        == frozenset()
    )


def test_a_range_that_coverage_never_recorded_skips_no_test(tmp_path: pathlib.Path):
    assert (
        _coverage(tmp_path).select("pkg/lib.rs", (8, 9), _GRAPH).skipped == frozenset()
    )


def test_a_selection_counts_the_tests_that_run_its_lines(tmp_path: pathlib.Path):
    covered = _coverage(tmp_path)

    assert covered.select("pkg/choose.py", (7, 7), _GRAPH) == coverage.Selection(
        skipped=frozenset({"//pkg:first_test"}),
        covering_tests=1,
        first_test="//pkg:second_test",
    )
    assert covered.select("pkg/lib.rs", (9, 9), _GRAPH) == coverage.Selection(
        skipped=frozenset(), covering_tests=None, first_test=None
    )


def _pyright_coverage(tmp_path: pathlib.Path) -> coverage.Coverage:
    _write_source(tmp_path)
    return coverage.from_reports(
        {
            "//pkg:first_test": [
                _report("pkg/choose.py", {7: 1}),
                _report("pkg/lib.rs", {3: 1}),
            ],
            "//pkg:pyright_test": [""],
            "//other:pyright_test": [""],
        },
        tmp_path,
    )


def test_a_python_mutant_runs_only_the_pyright_tests_that_check_its_file(
    tmp_path: pathlib.Path,
):
    assert _pyright_coverage(tmp_path).select(
        "pkg/choose.py", (7, 7), _PYRIGHT_GRAPH
    ) == coverage.Selection(
        skipped=frozenset({"//other:pyright_test"}),
        covering_tests=1,
        first_test="//pkg:first_test",
    )


def test_a_rust_mutant_runs_no_pyright_test(tmp_path: pathlib.Path):
    assert _pyright_coverage(tmp_path).select(
        "pkg/lib.rs", (3, 3), _PYRIGHT_GRAPH
    ) == coverage.Selection(
        skipped=frozenset({"//pkg:pyright_test", "//other:pyright_test"}),
        covering_tests=1,
        first_test="//pkg:first_test",
    )


def test_a_line_that_coverage_never_recorded_skips_only_pyright_tests(
    tmp_path: pathlib.Path,
):
    assert _pyright_coverage(tmp_path).select(
        "pkg/choose.py", (1, 1), _PYRIGHT_GRAPH
    ) == coverage.Selection(
        skipped=frozenset({"//other:pyright_test"}),
        covering_tests=None,
        first_test=None,
    )


def test_a_line_that_no_test_runs_skips_the_pyright_tests_that_do_not_check_it(
    tmp_path: pathlib.Path,
):
    _write_source(tmp_path)
    covered = coverage.from_reports(
        {"//pkg:first_test": [_report("pkg/choose.py", {7: 0})]}, tmp_path
    )

    assert covered.select(
        "pkg/choose.py", (7, 7), _PYRIGHT_GRAPH
    ) == coverage.Selection(
        skipped=frozenset({"//pkg:first_test", "//other:pyright_test"}),
        covering_tests=0,
        first_test=None,
    )


def test_a_pyright_test_closer_to_the_file_does_not_run_first(tmp_path: pathlib.Path):
    graph = dependency_graph.from_dot(
        """\
digraph mygraph {
  "//pkg:pyright_test" -> "//pkg:choose.py"
  "//pkg:far_test" -> "//pkg:wrapper"
  "//pkg:wrapper" -> "//pkg:choose.py"
}
""",
        frozenset({"//pkg:pyright_test"}),
        frozenset(),
    )
    _write_source(tmp_path)
    covered = coverage.from_reports(
        {
            "//pkg:far_test": [_report("pkg/choose.py", {7: 1})],
            "//pkg:pyright_test": [""],
        },
        tmp_path,
    )

    assert covered.select("pkg/choose.py", (7, 7), graph).first_test == "//pkg:far_test"
