# pyright: reportUnusedCallResult=false
"""Integration tests for code generation.

Each subdirectory under testdata/ is a valid Define project containing a
test.dfn entry point and an expected/ directory with the expected generated
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
from define.compiler.validator.test_helpers import assert_no_errors

_TESTDATA_ROOT = Path("define/compiler/codegen/testdata")

_TEST_CASES = sorted(
    d for d in _TESTDATA_ROOT.iterdir() if d.is_dir() and (d / "expected").is_dir()
)

# The codegen does not yet emit correct lookups for direct references to
# implied qualities. The compiler treats the first chain element as `self`
# with no bridging accessor, so `position</implied>` and
# `action</helper>::position<run>` collapse into method calls on the wrong
# object. These cases compile and produce expected/ output, but executing
# that output crashes.
_RUNTIME_BROKEN_IMPLIED_QUALITY_CODEGEN = frozenset(
    {
        "action_implies_action",
        "action_implies_position",
        "action_with_implied_qualities_and_multi_iface",
        "action_with_multiple_implications",
        "caller_overrides_implied_guarantee",
        "destroy_from_implied",
        "init_block_consumes_implied_action_interface",
        "multiple_implications_one_definition",
        "position_implies_action",
    }
)


_XFAIL_IMPLIED_QUALITY_CODEGEN = pytest.mark.xfail(
    reason="codegen emits self.<method>() for direct implied-quality references",
    strict=True,
)


def _marks_for(name: str) -> tuple[pytest.MarkDecorator, ...]:
    if name in _RUNTIME_BROKEN_IMPLIED_QUALITY_CODEGEN:
        return (_XFAIL_IMPLIED_QUALITY_CODEGEN,)
    return ()


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
    _TEST_CASES,
    ids=[d.name for d in _TEST_CASES],
)
def test_generates_expected_output(
    test_case_dir: Path, monkeypatch: pytest.MonkeyPatch
):
    expected_dir = (test_case_dir / "expected").resolve()

    monkeypatch.chdir(test_case_dir)
    output_dir = Path(tempfile.mkdtemp())
    result = driver.Driver().compile_program(Path("test.dfn"), output_dir)

    assert_no_errors(result.result)
    _assert_dirs_equal(expected_dir, output_dir)


@pytest.mark.parametrize(
    "test_case_dir",
    [pytest.param(d, id=d.name, marks=_marks_for(d.name)) for d in _TEST_CASES],
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
