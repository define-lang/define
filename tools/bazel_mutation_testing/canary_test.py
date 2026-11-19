from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tools.bazel_mutation_testing import canary
from tools.bazel_mutation_testing.python import sources
from tools.bazel_mutation_testing.rust import crates

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
_PYTHON_TEST = sources.PytestTest(
    label="//define/example:example_test", source="define/example/example_test.py"
)


def _write(workspace: pathlib.Path, path: str, text: str) -> pathlib.Path:
    source = workspace / path
    source.parent.mkdir(parents=True)
    _ = source.write_text(text, encoding="utf-8", newline="\n")
    return source


def test_canary_goes_in_the_first_crate_with_tests(tmp_path: pathlib.Path):
    source = _write(tmp_path, _TESTED.root, "pub const ONE: u32 = 1;\n")

    made = canary.make([_UNTESTED, _TESTED], [_PYTHON_TEST], tmp_path)
    made.mutant.apply(tmp_path)

    assert made.tests == _TESTED.tests
    assert made.mutant.path == _TESTED.root
    text = source.read_text(encoding="utf-8")
    assert text.startswith("pub const ONE: u32 = 1;\n\n#[cfg(test)]\n")
    assert "verify_that!(true, eq(false))" in text


def test_canary_goes_in_a_python_test_without_tested_crates(tmp_path: pathlib.Path):
    source = _write(tmp_path, _PYTHON_TEST.source, "def test_one():\n    pass\n")

    made = canary.make([_UNTESTED], [_PYTHON_TEST], tmp_path)
    made.mutant.apply(tmp_path)

    assert made.tests == (_PYTHON_TEST.label,)
    assert source.read_text(encoding="utf-8") == (
        "def test_one():\n    pass\n\n\n"
        + "def test_mutation_testing_canary():\n    assert not __name__\n"
    )


def test_area_without_tests_has_no_canary(tmp_path: pathlib.Path):
    with pytest.raises(canary.NoCanaryTestError):
        _ = canary.make([_UNTESTED], [], tmp_path)
