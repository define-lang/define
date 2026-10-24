# pyright: reportUnusedCallResult=false
"""Duplicate quality assignment validation tests.

Follow program validator test authoring rules in program_validator_tests/AGENTS.md.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from define.compiler.errors import diagnostics
from define.compiler.validator.test_helpers import assert_no_errors

if TYPE_CHECKING:
    from define.compiler.conftest import ValidateTestdataStructuralNonFilesystem


def test_no_duplicate_quality_assignments_ok(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert_no_errors(result)


def test_duplicate_quality_assignment_in_global_position_error(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert result.all_exceptions == []
    results = result.file_results
    diags = results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.DuplicateQualityAssignmentDiagnostic)
    assert diags[0].location.file_path is None
    assert diags[0].quality_name == "position</foo>"
    assert diags[0].first_assignment_line == 4
    assert diags[0].location.line == 5
    assert diags[0].location.column == 20


def test_duplicate_quality_assignment_in_local_position_error(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert result.all_exceptions == []
    diags = result.file_results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.DuplicateQualityAssignmentDiagnostic)
    assert diags[0].location.file_path is None
    assert diags[0].quality_name == "position</foo>"
    assert diags[0].first_assignment_line == 5
    assert diags[0].location.line == 6
    assert diags[0].location.column == 24


def test_three_duplicates_two_errors(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert result.all_exceptions == []
    diags = result.file_results[0].diagnostics
    assert len(diags) == 2
    assert isinstance(diags[0], diagnostics.DuplicateQualityAssignmentDiagnostic)
    assert diags[0].location.file_path is None
    assert isinstance(diags[1], diagnostics.DuplicateQualityAssignmentDiagnostic)
    assert diags[1].location.file_path is None
    assert diags[0].quality_name == "position</foo>"
    assert diags[0].first_assignment_line == 4
    assert diags[0].location.line == 5
    assert diags[0].location.column == 20
    assert diags[1].quality_name == "position</foo>"
    assert diags[1].first_assignment_line == 4
    assert diags[1].location.line == 6
    assert diags[1].location.column == 20


def test_duplicate_via_full_form_and_short_form(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert result.all_exceptions == []
    diags = result.file_results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.GlobalReferenceMustUseShortFormDiagnostic)
    assert diags[0].location.column == 29
    assert diags[0].location.file_path is None
    assert diags[0].fqun == "my.domain.com:my_lib"
    assert diags[0].location.line == 5


def test_duplicate_full_fqun_cross_universe_error(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert result.all_exceptions == []
    diags = result.file_results[0].diagnostics
    assert len(diags) == 2
    assert isinstance(
        diags[0], diagnostics.NoProjectRootInNonFilesystemContextDiagnostic
    )
    assert diags[0].location.line == 3
    assert diags[0].location.column == 29
    assert diags[0].location.file_path is None
    assert diags[0].config_path == ".define/project/config.defcl"
    assert diags[0].universe == "other.example.com:other_lib"
    assert isinstance(diags[1], diagnostics.DuplicateQualityAssignmentDiagnostic)
    assert diags[1].location.file_path is None
    assert diags[1].quality_name == "position<other.example.com:other_lib:/foo>"
    assert diags[1].first_assignment_line == 3
    assert diags[1].location.line == 4
    assert diags[1].location.column == 20
