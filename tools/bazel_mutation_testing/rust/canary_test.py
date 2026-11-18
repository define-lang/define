from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING

import pytest

from tools.bazel_mutation_testing import bazel
from tools.bazel_mutation_testing.rust import canary, crates

if TYPE_CHECKING:
    import pathlib

_UNTESTED = crates.Crate(
    label="//crates/untested:untested",
    name="untested",
    root="crates/untested/lib.rs",
    tests=(),
)
_TESTED = crates.Crate(
    label="//crates/example:example",
    name="example",
    root="crates/example/lib.rs",
    tests=("//crates/example:example_test",),
)


def test_canary_goes_in_the_first_crate_with_tests(tmp_path: pathlib.Path):
    source = tmp_path / _TESTED.root
    source.parent.mkdir(parents=True)
    _ = source.write_text("pub const ONE: u32 = 1;\n", encoding="utf-8", newline="\n")

    made = canary.make([_UNTESTED, _TESTED], tmp_path)
    _ = subprocess.run(
        [bazel.executable("git"), "apply"],
        cwd=tmp_path,
        input=made.mutant.patch,
        text=True,
        check=True,
    )

    assert made.tests == _TESTED.tests
    assert made.mutant.path == _TESTED.root
    text = source.read_text(encoding="utf-8")
    assert text.startswith("pub const ONE: u32 = 1;\n\n#[cfg(test)]\n")
    assert "verify_that!(true, eq(false))" in text


def test_area_without_tested_crates_has_no_canary(tmp_path: pathlib.Path):
    with pytest.raises(canary.NoCanaryCrateError):
        _ = canary.make([_UNTESTED], tmp_path)
