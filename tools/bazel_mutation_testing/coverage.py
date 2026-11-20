"""Which of the area's tests run each line of its sources."""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING, NamedTuple, final

if TYPE_CHECKING:
    import pathlib
    from collections.abc import Mapping


class Selection(NamedTuple):
    """The tests that a mutant runs."""

    skipped: frozenset[str]
    """The tests that record coverage but never run the mutant's lines."""
    covering_tests: int | None
    """How many tests that record coverage run the mutant's lines, or None when
    no coverage records them, so that every test runs."""


@final
class Coverage:
    """The lines that each test runs, from one coverage run of the area's tests."""

    def __init__(
        self,
        tests: frozenset[str],
        lines: Mapping[str, Mapping[int, frozenset[str]]],
        statement_starts: Mapping[str, Mapping[int, int]],
    ):
        """Create the coverage of `tests`.

        Args:
            tests: The tests that reported coverage.
            lines: For each workspace-relative path, the tests that ran each
                line that coverage recorded.
            statement_starts: For each Python path, the first line of each
                statement that spans several lines, by each of its lines.
        """
        self._tests = tests
        self._lines = lines
        self._statement_starts = statement_starts

    def select(self, path: str, lines: tuple[int, int]) -> Selection:
        """Return the tests that a mutant of `lines`, the first and last lines of `path`, runs.

        Lines that coverage recorded for no test, such as a Rust constant that
        the compiler evaluates, can still change what tests do, so no test
        skips them.
        """
        starts = self._statement_starts.get(path, {})
        recorded = self._lines.get(path, {})
        first, last = lines
        running: set[str] | None = None
        for line in range(first, last + 1):
            tests = recorded.get(starts.get(line, line))
            if tests is not None:
                running = set(tests) if running is None else running | tests
        if running is None:
            return Selection(skipped=frozenset(), covering_tests=None)
        return Selection(skipped=self._tests - running, covering_tests=len(running))


def from_reports(reports: Mapping[str, list[str]], workspace: pathlib.Path) -> Coverage:
    """Return the coverage that `reports` hold, lcov reports for each test.

    `workspace` holds the Python sources that the reports name.
    """
    tests: set[str] = set()
    lines: dict[str, dict[int, set[str]]] = {}
    for test, test_reports in reports.items():
        for report in test_reports:
            if report:
                tests.add(test)
            _add_report(test, report, lines)
    statement_starts = {
        path: _statement_starts((workspace / path).read_text(encoding="utf-8"))
        for path in lines
        if path.endswith(".py")
    }
    return Coverage(
        frozenset(tests),
        {
            path: {line: frozenset(running) for line, running in by_line.items()}
            for path, by_line in lines.items()
        },
        statement_starts,
    )


def _add_report(test: str, report: str, lines: dict[str, dict[int, set[str]]]):
    path = ""
    for record in report.splitlines():
        if record.startswith("SF:"):
            path = record.removeprefix("SF:")
        elif record.startswith("DA:"):
            number, hits = record.removeprefix("DA:").split(",")[:2]
            running = lines.setdefault(path, {}).setdefault(int(number), set())
            if int(hits) > 0:
                running.add(test)


def _statement_starts(source: str) -> dict[int, int]:
    """Return the first line of each Python statement, by each line of its header.

    Python coverage records a statement only on its first line, while a
    mutant can change any line of it. A compound statement's header ends
    before its body.
    """
    starts: dict[int, int] = {}
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.stmt) or node.end_lineno is None:
            continue
        header_end = node.end_lineno
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.stmt | ast.ExceptHandler | ast.match_case):
                header_end = min(header_end, _first_line(child) - 1)
        for line in range(node.lineno + 1, header_end + 1):
            # The innermost statement starts last.
            starts[line] = max(starts.get(line, node.lineno), node.lineno)
    return starts


def _first_line(node: ast.stmt | ast.ExceptHandler | ast.match_case) -> int:
    if isinstance(node, ast.match_case):
        return node.pattern.lineno
    return node.lineno
