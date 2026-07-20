"""Local name conflict validation tests.

Follow program validator test authoring rules in program_validator_tests/AGENTS.md.
"""

from define.compiler import diagnostics
from define.compiler.conftest import ValidateTestdataStructuralNonFilesystem
from define.compiler.validator.test_helpers import assert_no_errors


def test_different_names_no_error(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert_no_errors(result)


def test_duplicate_name_error(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    results = validate_testdata_structural_non_filesystem().file_results
    diags = results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.LocalNameConflictDiagnostic)
    assert diags[0].local_name == "alpha"
    assert diags[0].first_definition_line == 2
    assert diags[0].location.line == 3
    assert diags[0].location.column == 25


def test_three_locals_two_same_one_diagnostic(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert result.all_exceptions == []
    diags = result.file_results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.LocalNameConflictDiagnostic)
    assert diags[0].local_name == "alpha"
    assert diags[0].first_definition_line == 2
    assert diags[0].location.line == 4
    assert diags[0].location.column == 25


def test_three_same_name_two_diagnostics(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert result.all_exceptions == []
    diags = result.file_results[0].diagnostics
    assert len(diags) == 2
    assert isinstance(diags[0], diagnostics.LocalNameConflictDiagnostic)
    assert isinstance(diags[1], diagnostics.LocalNameConflictDiagnostic)
    assert diags[0].local_name == "alpha"
    assert diags[0].first_definition_line == 2
    assert diags[0].location.line == 3
    assert diags[0].location.column == 25
    assert diags[1].local_name == "alpha"
    assert diags[1].first_definition_line == 2
    assert diags[1].location.line == 4
    assert diags[1].location.column == 25


def test_terminated_action_no_error(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert_no_errors(result)


def test_single_local_no_error(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert_no_errors(result)


def test_separate_actions_same_local_name_no_error(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert_no_errors(result)


def test_action_statements_local_name_no_error(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert_no_errors(result)


def test_action_statements_duplicate_name_error(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    results = validate_testdata_structural_non_filesystem().file_results
    diags = results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.LocalNameConflictDiagnostic)
    assert diags[0].local_name == "alpha"
    assert diags[0].first_definition_line == 6
    assert diags[0].location.line == 7
    assert diags[0].location.column == 29


def test_action_statements_name_conflicts_with_parent_scope(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    results = validate_testdata_structural_non_filesystem().file_results
    diags = results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.LocalNameConflictDiagnostic)
    assert diags[0].local_name == "alpha"
    assert diags[0].first_definition_line == 2
    assert diags[0].location.line == 6
    assert diags[0].location.column == 29


def test_action_statements_two_duplicates_point_to_parent_scope_definition(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert result.all_exceptions == []
    diags = result.file_results[0].diagnostics
    assert len(diags) == 2
    assert isinstance(diags[0], diagnostics.LocalNameConflictDiagnostic)
    assert isinstance(diags[1], diagnostics.LocalNameConflictDiagnostic)
    assert diags[0].local_name == "alpha"
    assert diags[1].local_name == "alpha"
    assert diags[0].first_definition_line == 2
    assert diags[1].first_definition_line == 2
    assert diags[0].location.line == 6
    assert diags[0].location.column == 29
    assert diags[1].location.line == 7
    assert diags[1].location.column == 29
