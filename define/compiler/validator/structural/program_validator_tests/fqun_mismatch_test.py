"""FQUN mismatch validation tests.

Follow program validator test authoring rules in program_validator_tests/AGENTS.md.
"""

from pathlib import PurePosixPath

from define.compiler import diagnostics
from define.compiler.conftest import ValidateTestdataStructural
from define.compiler.validator.test_helpers import assert_no_errors


def test_matching_authority_universe(
    validate_testdata_structural: ValidateTestdataStructural,
):
    result = validate_testdata_structural(entry_file="path.dfn")
    assert_no_errors(result)


def test_mismatched_universe(
    validate_testdata_structural: ValidateTestdataStructural,
):
    result = validate_testdata_structural(entry_file="path.dfn")
    assert result.all_exceptions == []
    diags = result.file_results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.FqunMismatchDiagnostic)
    assert diags[0].expected == "my.domain.com:my_lib"
    assert diags[0].actual == "my.domain.com:wrong_lib"
    assert diags[0].location.line == 1
    assert diags[0].location.column == 31
    assert diags[0].location.end_line == 1
    assert diags[0].location.end_column == 54
    assert diags[0].location.file_path == PurePosixPath("path.dfn")


def test_mismatched_authority(
    validate_testdata_structural: ValidateTestdataStructural,
):
    result = validate_testdata_structural(entry_file="path.dfn")
    assert result.all_exceptions == []
    diags = result.file_results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.FqunMismatchDiagnostic)
    assert diags[0].expected == "my.domain.com:my_lib"
    assert diags[0].actual == "other.org:my_lib"
    assert diags[0].location.line == 1
    assert diags[0].location.column == 31


def test_mismatched_multiverse(
    validate_testdata_structural: ValidateTestdataStructural,
):
    result = validate_testdata_structural(entry_file="path.dfn")
    assert result.all_exceptions == []
    diags = result.file_results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.FqunMismatchDiagnostic)
    assert diags[0].expected == "mv:my.domain.com:my_lib"
    assert diags[0].actual == "other_mv:my.domain.com:my_lib"
    assert diags[0].location.line == 1
    assert diags[0].location.column == 31
    assert diags[0].location.end_line == 1
    assert diags[0].location.end_column == 60


def test_none_skips_check(
    validate_testdata_structural: ValidateTestdataStructural,
):
    result = validate_testdata_structural(entry_file="path.dfn")
    assert_no_errors(result)


def test_standard_universe_matching(
    validate_testdata_structural: ValidateTestdataStructural,
):
    result = validate_testdata_structural(entry_file="path.dfn")
    assert result.all_exceptions == []
    diags = result.file_results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.ReservedUniverseNameDiagnostic)
    assert diags[0].reserved_name == "standard"
    assert diags[0].location.line == 1
    assert diags[0].location.column == 31
    assert diags[0].location.end_line == 1
    assert diags[0].location.end_column == 39


def test_authority_with_path(
    validate_testdata_structural: ValidateTestdataStructural,
):
    result = validate_testdata_structural(entry_file="path.dfn")
    assert_no_errors(result)


def test_authority_with_path_mismatch(
    validate_testdata_structural: ValidateTestdataStructural,
):
    result = validate_testdata_structural(entry_file="path.dfn")
    assert result.all_exceptions == []
    diags = result.file_results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.FqunMismatchDiagnostic)
    assert diags[0].expected == "my.domain.com:my_lib"
    assert diags[0].actual == "my.domain.com/org:my_lib"
    assert diags[0].location.line == 1
    assert diags[0].location.column == 31


def test_multiverse_matching(
    validate_testdata_structural: ValidateTestdataStructural,
):
    result = validate_testdata_structural(entry_file="path.dfn")
    assert_no_errors(result)
