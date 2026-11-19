"""The canary: a mutant that only a failing test can kill.

A run whose tests do not fail on the canary could not tell a killed mutant from
a survivor.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import msgspec

from tools.bazel_mutation_testing import mutant

if TYPE_CHECKING:
    import pathlib
    from collections.abc import Iterable

    from tools.bazel_mutation_testing.python import sources
    from tools.bazel_mutation_testing.rust import crates

# Each test follows the repository's lints, so that only the test can fail.
_RUST_TEST = """
#[cfg(test)]
mod mutation_testing_canary {
    use googletest::prelude::*;

    #[gtest]
    fn fails() -> Result<()> {
        verify_that!(true, eq(false))
    }
}
"""
_PYTHON_TEST = """

def test_mutation_testing_canary():
    assert not __name__
"""


class NoCanaryTestError(Exception):
    """No crate or Python test in the area has a test that the run tests with."""


class Canary(msgspec.Struct, frozen=True):
    """A failing test appended to a source file."""

    mutant: mutant.Mutant
    tests: tuple[str, ...]
    """The tests that run the failing test. A run's first failure must be one of
    them."""


def _appended(
    path: str, added_text: str, workspace: pathlib.Path, tests: tuple[str, ...]
) -> Canary:
    lines = workspace.joinpath(path).read_text(encoding="utf-8").splitlines()
    added = added_text.splitlines()
    patch = "".join(
        [
            f"--- a/{path}\n",
            f"+++ b/{path}\n",
            f"@@ -{len(lines)},1 +{len(lines)},{len(added) + 1} @@\n",
            f" {lines[-1]}\n",
            *[f"+{line}\n" for line in added],
        ]
    )
    return Canary(
        mutant=mutant.Mutant(name=f"{path}: canary test", path=path, patch=patch),
        tests=tests,
    )


def make(
    area_crates: Iterable[crates.Crate],
    python_tests: Iterable[sources.PytestTest],
    workspace: pathlib.Path,
) -> Canary:
    """Return a canary in the first of `area_crates` that has tests.

    Without such a crate, the canary goes in the first of `python_tests`.

    Raises:
        NoCanaryTestError: No crate has tests, and there are no Python tests.
    """
    crate = next((crate for crate in area_crates if crate.tests), None)
    if crate is not None:
        return _appended(crate.root, _RUST_TEST, workspace, crate.tests)
    python_test = next(iter(python_tests), None)
    if python_test is not None:
        return _appended(
            python_test.source, _PYTHON_TEST, workspace, (python_test.label,)
        )
    raise NoCanaryTestError
