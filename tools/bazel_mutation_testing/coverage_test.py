from __future__ import annotations

from typing import TYPE_CHECKING

from tools.bazel_mutation_testing import coverage

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
    assert _coverage(tmp_path).tests_to_skip("pkg/choose.py", (7, 7)) == {
        "//pkg:first_test"
    }


def test_a_line_of_a_statement_counts_as_its_first_line(tmp_path: pathlib.Path):
    assert _coverage(tmp_path).tests_to_skip("pkg/choose.py", (4, 4)) == frozenset()


def test_a_body_line_is_its_own_statement(tmp_path: pathlib.Path):
    assert _coverage(tmp_path).tests_to_skip("pkg/choose.py", (6, 6)) == {
        "//pkg:second_test"
    }


def test_a_test_whose_reports_cover_different_files_runs_each(tmp_path: pathlib.Path):
    assert _coverage(tmp_path).tests_to_skip("pkg/lib.rs", (3, 3)) == {
        "//pkg:second_test"
    }


def test_an_unrecorded_line_skips_no_test(tmp_path: pathlib.Path):
    assert _coverage(tmp_path).tests_to_skip("pkg/lib.rs", (9, 9)) == frozenset()


def test_a_line_that_no_test_runs_skips_every_reporting_test(tmp_path: pathlib.Path):
    _write_source(tmp_path)
    covered = coverage.from_reports(
        {
            "//pkg:first_test": [_report("pkg/choose.py", {7: 0})],
            "//pkg:lint_test": [""],
        },
        tmp_path,
    )

    assert covered.tests_to_skip("pkg/choose.py", (7, 7)) == {"//pkg:first_test"}


def test_a_range_runs_the_tests_that_run_any_of_its_lines(tmp_path: pathlib.Path):
    assert _coverage(tmp_path).tests_to_skip("pkg/choose.py", (6, 7)) == frozenset()


def test_a_range_that_coverage_never_recorded_skips_no_test(tmp_path: pathlib.Path):
    assert _coverage(tmp_path).tests_to_skip("pkg/lib.rs", (8, 9)) == frozenset()
