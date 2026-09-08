"""Tests for generated-file comparison diagnostics."""

from __future__ import annotations

from pathlib import Path

import pytest

from define.compiler.codegen import test_helpers


@pytest.mark.parametrize("compare_directory", [False, True])
def test_matching_files_pass(tmp_path: Path, *, compare_directory: bool):
    expected = tmp_path / "expected"
    generated = tmp_path / "generated"
    expected.mkdir()
    generated.mkdir()
    _ = (expected / "test.py").write_text("unchanged\n")
    _ = (generated / "test.py").write_text("unchanged\n")

    if compare_directory:
        test_helpers.assert_generated_directory_matches(expected, generated)
    else:
        _ = (generated / "other.py").write_text("not selected\n")
        test_helpers.assert_generated_files_match(
            expected, generated, {Path("test.py")}
        )


@pytest.mark.parametrize("compare_directory", [False, True])
def test_reports_all_diffs_in_filename_order(
    tmp_path: Path, *, compare_directory: bool
):
    expected = tmp_path / "expected"
    generated = tmp_path / "generated"
    expected.mkdir()
    generated.mkdir()
    for name in ("z.py", "a.py", "unchanged.py"):
        _ = (expected / name).write_text("before\n")
        _ = (generated / name).write_text(
            "before\n" if name == "unchanged.py" else "after\n"
        )

    if compare_directory:
        with pytest.raises(pytest.fail.Exception) as error:
            test_helpers.assert_generated_directory_matches(expected, generated)
    else:
        with pytest.raises(pytest.fail.Exception) as error:
            test_helpers.assert_generated_files_match(
                expected, generated, {Path("z.py"), Path("a.py"), Path("unchanged.py")}
            )

    assert str(error.value) == (
        "--- expected/a.py\n"
        "+++ generated/a.py\n"
        "@@ -1 +1 @@\n"
        "-before\n"
        "+after\n"
        "--- expected/z.py\n"
        "+++ generated/z.py\n"
        "@@ -1 +1 @@\n"
        "-before\n"
        "+after\n"
    )
