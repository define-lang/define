# pyright: reportUnusedCallResult=false
"""Integration tests for code generation.

Each subdirectory under testdata/ is a valid Define project containing a
test.def entry point and an expected.py with the expected generated output.
Simply adding a new directory to testdata/ will cause a new test to be
generated here.
"""

from pathlib import Path

import pytest

from define.compiler import driver

_TESTDATA_ROOT = Path("define/compiler/codegen/testdata")

_TEST_CASES = sorted(
    d for d in _TESTDATA_ROOT.iterdir() if d.is_dir() and (d / "expected.py").exists()
)


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
    expected = (test_case_dir / "expected.py").read_text()

    monkeypatch.chdir(test_case_dir)
    result = driver.Driver().compile_program(Path("test.def"))

    assert result.generated_code == expected
