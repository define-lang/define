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

    from tools.bazel_mutation_testing.rust import crates

# It follows the repository's lints, so that only its test can fail.
_TEST = """
#[cfg(test)]
mod mutation_testing_canary {
    use googletest::prelude::*;

    #[gtest]
    fn fails() -> Result<()> {
        verify_that!(true, eq(false))
    }
}
"""


class NoCanaryCrateError(Exception):
    """No crate in the area has a rust_test that the run tests with."""


class Canary(msgspec.Struct, frozen=True):
    """A failing test appended to a crate root."""

    mutant: mutant.Mutant
    tests: tuple[str, ...]
    """The tests that run the failing test. A run's first failure must be one of
    them."""


def make(area_crates: Iterable[crates.Crate], workspace: pathlib.Path) -> Canary:
    """Return a canary in the first of `area_crates` that has tests.

    Raises:
        NoCanaryCrateError: No crate has tests.
    """
    crate = next((crate for crate in area_crates if crate.tests), None)
    if crate is None:
        raise NoCanaryCrateError
    lines = workspace.joinpath(crate.root).read_text(encoding="utf-8").splitlines()
    added = _TEST.splitlines()
    patch = "".join(
        [
            f"--- a/{crate.root}\n",
            f"+++ b/{crate.root}\n",
            f"@@ -{len(lines)},1 +{len(lines)},{len(added) + 1} @@\n",
            f" {lines[-1]}\n",
            *[f"+{line}\n" for line in added],
        ]
    )
    return Canary(
        mutant=mutant.Mutant(
            name=f"{crate.root}: canary test", path=crate.root, patch=patch
        ),
        tests=crate.tests,
    )
