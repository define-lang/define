# pyright: reportUnusedCallResult=false
"""Integration tests for code generation.

Each subdirectory under testdata/ is a valid Define project containing a
test.def entry point and an expected/ directory with the expected generated
output files. Simply adding a new directory to testdata/ will cause a new
test to be generated here.
"""

import difflib
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from define.compiler import driver

_TESTDATA_ROOT = Path("define/compiler/codegen/testdata")

_TEST_CASES = sorted(
    d for d in _TESTDATA_ROOT.iterdir() if d.is_dir() and (d / "expected").is_dir()
)

# These test cases reference chained child positions in action bodies
# without the parent position existing in the trie. They will pass once
# we infer OCCUPIED requirements on parent positions when children are
# accessed.
_XFAIL_PARENT_INFERENCE = {
    "move_from_chained",
    "move_from_interface",
    "move_from_local",
}


def _all_files(root: Path) -> dict[str, str]:
    return {
        str(p.relative_to(root)): p.read_text()
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


def _assert_dirs_equal(expected: Path, generated: Path):
    """Assert two directory trees are identical."""
    expected_files = _all_files(expected)
    generated_files = _all_files(generated)
    if expected_files == generated_files:
        return
    diffs: list[str] = []
    all_keys = sorted(set(expected_files) | set(generated_files))
    for key in all_keys:
        exp = expected_files.get(key, "")
        gen = generated_files.get(key, "")
        if exp != gen:
            diffs.extend(
                difflib.unified_diff(
                    exp.splitlines(keepends=True),
                    gen.splitlines(keepends=True),
                    fromfile=f"expected/{key}",
                    tofile=f"generated/{key}",
                )
            )
    pytest.fail("".join(diffs))


def test_test_cases_not_empty():
    assert _TEST_CASES


@pytest.mark.parametrize(
    "test_case_dir",
    [
        pytest.param(
            d,
            marks=pytest.mark.xfail(
                reason=(
                    "Requires inferring OCCUPIED requirements on parent "
                    "positions when child positions are accessed."
                ),
                raises=KeyError,
            ),
        )
        if d.name in _XFAIL_PARENT_INFERENCE
        else d
        for d in _TEST_CASES
    ],
    ids=[d.name for d in _TEST_CASES],
)
def test_generates_expected_output(
    test_case_dir: Path, monkeypatch: pytest.MonkeyPatch
):
    expected_dir = (test_case_dir / "expected").resolve()

    monkeypatch.chdir(test_case_dir)
    output_dir = Path(tempfile.mkdtemp())
    result = driver.Driver().compile_program(Path("test.def"), output_dir)

    assert not result.result.has_errors()
    _assert_dirs_equal(expected_dir, output_dir)


@pytest.mark.parametrize(
    "test_case_dir",
    _TEST_CASES,
    ids=[d.name for d in _TEST_CASES],
)
def test_expected_output_runs(test_case_dir: Path):
    expected_dir = test_case_dir / "expected"
    result = subprocess.run(
        [sys.executable, str(expected_dir / "__main__.py")],
        env={
            "PYTHONPATH": str(expected_dir) + ":" + ":".join(sys.path),
        },
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        pytest.fail(result.stderr)
