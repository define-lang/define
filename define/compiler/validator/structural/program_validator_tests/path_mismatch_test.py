"""Path mismatch validation tests.

Follow program validator test authoring rules in program_validator_tests/AGENTS.md.
"""

from __future__ import annotations

from pathlib import PurePosixPath
from typing import TYPE_CHECKING

from define.compiler import diagnostics
from define.compiler.validator.test_helpers import assert_no_errors

if TYPE_CHECKING:
    from define.compiler.conftest import ValidateTestdataStructural


def test_path_matches_file_no_error(
    validate_testdata_structural: ValidateTestdataStructural,
):
    result = validate_testdata_structural(entry_file="foo/bar.dfn")
    assert_no_errors(result)


def test_path_mismatch_error(
    validate_testdata_structural: ValidateTestdataStructural,
):
    result = validate_testdata_structural(entry_file="foo/bar.dfn")
    assert result.all_exceptions == []
    diags = result.file_results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.PathMismatchDiagnostic)
    assert diags[0].expected_path == "/foo/bar"
    assert diags[0].actual_path == "/wrong/path"
    assert diags[0].location.line == 1
    assert diags[0].location.column == 52
    assert diags[0].location.end_line == 1
    assert diags[0].location.end_column == 63
    assert diags[0].location.file_path == PurePosixPath("foo/bar.dfn")


def test_no_file_path_skips_validation(
    validate_testdata_structural: ValidateTestdataStructural,
):
    result = validate_testdata_structural(entry_file="any/path.dfn")
    assert_no_errors(result)


def test_nested_path_matches(
    validate_testdata_structural: ValidateTestdataStructural,
):
    result = validate_testdata_structural(entry_file="a/b/c.dfn")
    assert_no_errors(result)
