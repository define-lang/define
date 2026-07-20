# pyright: reportUnusedCallResult=false
"""Duplicate quality constraint validation tests.

Follow program validator test authoring rules in program_validator_tests/AGENTS.md.
"""

from define.compiler import diagnostics
from define.compiler.conftest import ValidateTestdataStructuralNonFilesystem
from define.compiler.validator.test_helpers import assert_no_errors


def test_no_duplicate_constraints_ok(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert_no_errors(result)


def test_duplicate_constraint_in_global_position_error(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    results = validate_testdata_structural_non_filesystem().file_results
    diags = results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.DuplicatePositionConstraintDiagnostic)
    assert diags[0].constraint_name == "position</foo>"
    assert diags[0].first_constraint_line == 4
    assert diags[0].location.line == 5
    assert diags[0].location.column == 20


def test_duplicate_constraint_in_local_position_error(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert result.all_exceptions == []
    diags = result.file_results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.DuplicatePositionConstraintDiagnostic)
    assert diags[0].constraint_name == "position</foo>"
    assert diags[0].first_constraint_line == 5
    assert diags[0].location.line == 6
    assert diags[0].location.column == 24


def test_three_duplicates_two_errors(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert result.all_exceptions == []
    diags = result.file_results[0].diagnostics
    assert len(diags) == 2
    assert isinstance(diags[0], diagnostics.DuplicatePositionConstraintDiagnostic)
    assert isinstance(diags[1], diagnostics.DuplicatePositionConstraintDiagnostic)
    assert diags[0].constraint_name == "position</foo>"
    assert diags[0].first_constraint_line == 4
    assert diags[0].location.line == 5
    assert diags[0].location.column == 20
    assert diags[1].constraint_name == "position</foo>"
    assert diags[1].first_constraint_line == 4
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
    assert diags[0].fqun == "my.domain.com:my_lib"
    assert diags[0].location.line == 5


def test_duplicate_full_fqun_cross_universe_error(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert result.all_exceptions == []
    diags = result.file_results[0].diagnostics
    assert len(diags) == 2
    assert isinstance(diags[0], diagnostics.DuplicatePositionConstraintDiagnostic)
    assert diags[0].constraint_name == "position<other.example.com:other_lib:/foo>"
    assert diags[0].first_constraint_line == 3
    assert diags[0].location.line == 4
    assert diags[0].location.column == 20
    assert isinstance(
        diags[1], diagnostics.NoProjectRootInNonFilesystemContextDiagnostic
    )
    assert diags[1].universe == "other.example.com:other_lib"
