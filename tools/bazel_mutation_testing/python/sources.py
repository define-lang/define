"""Find the Python sources and tests in an area."""

from __future__ import annotations

from typing import TYPE_CHECKING

import msgspec

from tools.bazel_mutation_testing import bazel

if TYPE_CHECKING:
    import pathlib

# rules_py's py_binary and py_test rules.
_LIBRARY_RULES = frozenset({"py_library", "py_venv_exec"})
_TEST_RULE = "py_venv_exec_test"
# A py_test runs its sources with pytest through this main.
_PYTEST_MAIN = "@rules_py//py/private:pytest_main.py"
# A mutation run never runs tests with these tags. `bazel test` leaves out
# manual tests when a wildcard pattern matches them, and each run passes
# --test_tag_filters=-no-coverage.
_SKIPPED_TEST_TAGS = frozenset({"manual", "no-coverage"})


class PytestTest(msgspec.Struct, frozen=True):
    """A py_test that runs its sources with pytest, and that a run tests with."""

    label: str
    source: str
    """The workspace-relative path of the test's first source."""


class Sources(msgspec.Struct, frozen=True):
    """An area's Python sources and pytest tests."""

    paths: list[str]
    """The workspace-relative paths of the sources that the tester mutates,
    sorted."""
    tests: list[PytestTest]


def find(workspace: pathlib.Path, patterns: list[str]) -> Sources:
    """Return the Python sources and tests that the target patterns `patterns` match.

    Unlike `bazel test`, this includes targets tagged `manual`. As in `bazel
    test`, the tests include the tests of the test suites that the patterns
    match.
    """
    expression = bazel.query_expression(patterns)
    return from_query(
        bazel.run_checked(
            workspace,
            [
                "query",
                "--output=streamed_jsonproto",
                f'kind("^py_(library|venv_exec) rule$", {expression}) + '
                + f'kind("^py_venv_exec_test rule$", tests({expression}))',
            ],
        )
    )


def from_query(output: str) -> Sources:
    """Return the sources and tests in a query's `streamed_jsonproto` output.

    The query names Python libraries, binaries and tests. The sources are the
    `.py` sources of the libraries and binaries that are not `testonly` and not
    tagged `no-mutation`. Test helpers are not what the tests check, and a
    generator's mutants only change code that the tests check through the
    generated code.
    """
    paths: set[str] = set()
    tests: list[PytestTest] = []
    for rule in bazel.rules(output):
        sources = rule.value("srcs").string_list_value
        if rule.rule_class in _LIBRARY_RULES:
            if rule.value("testonly").boolean_value or (
                bazel.NO_MUTATION_TAG in rule.value("tags").string_list_value
            ):
                continue
            for source in sources:
                if source.startswith("//") and source.endswith(".py"):
                    paths.add(bazel.source_path(source))
            continue
        # A test that gets its module through `args`, such as each codegen
        # case's test, has no source to append a canary test to.
        if (
            rule.rule_class == _TEST_RULE
            and sources
            and rule.value("main").string_value == _PYTEST_MAIN
            and _SKIPPED_TEST_TAGS.isdisjoint(rule.value("tags").string_list_value)
        ):
            tests.append(
                PytestTest(label=rule.name, source=bazel.source_path(sources[0]))
            )
    return Sources(paths=sorted(paths), tests=tests)
