"""Duplicate definition validation tests.

Follow program validator test authoring rules in program_validator_tests/AGENTS.md.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from define.compiler import diagnostics
from define.compiler.validator.test_helpers import assert_no_errors

if TYPE_CHECKING:
    from define.compiler.conftest import ValidateTestdataStructuralNonFilesystem


def test_no_duplicates_ok(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert_no_errors(result)


def test_duplicate_position_error(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert result.all_exceptions == []
    diags = result.file_results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.DuplicateDefinitionDiagnostic)
    assert diags[0].definition_type == "position"
    assert diags[0].path == "/same"
    assert diags[0].first_definition_line == 1
    assert diags[0].location.line == 2
    assert diags[0].location.column == 1


def test_duplicate_action_error(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert result.all_exceptions == []
    diags = result.file_results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.DuplicateDefinitionDiagnostic)
    assert diags[0].definition_type == "action"
    assert diags[0].path == "/same"
    assert diags[0].first_definition_line == 1
    assert diags[0].location.line == 10
    assert diags[0].location.column == 1


def test_same_path_different_types_ok(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert_no_errors(result)


def test_three_duplicates_two_errors(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert result.all_exceptions == []
    diags = result.file_results[0].diagnostics
    assert len(diags) == 2
    assert isinstance(diags[0], diagnostics.DuplicateDefinitionDiagnostic)
    assert isinstance(diags[1], diagnostics.DuplicateDefinitionDiagnostic)
    assert diags[0].definition_type == "position"
    assert diags[0].path == "/same"
    assert diags[0].first_definition_line == 1
    assert diags[0].location.line == 2
    assert diags[0].location.column == 1
    assert diags[1].definition_type == "position"
    assert diags[1].path == "/same"
    assert diags[1].first_definition_line == 1
    assert diags[1].location.line == 3
    assert diags[1].location.column == 1
