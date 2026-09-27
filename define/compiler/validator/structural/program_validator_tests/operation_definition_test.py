"""Structural validation of value operation definitions and their interface views.

Follow program validator test authoring rules in program_validator_tests/AGENTS.md.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from define.compiler import diagnostics
from define.compiler.validator.test_helpers import assert_no_errors

if TYPE_CHECKING:
    from define.compiler.conftest import ValidateTestdataStructuralNonFilesystem


def test_valid_operation(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert_no_errors(result)
    assert len(result.definition_results) == 2


def test_encoding_operation_references_every_view(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert_no_errors(result)


def test_unreferenced_views(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 2
    first = result.all_diagnostics[0]
    assert isinstance(first, diagnostics.UnreferencedViewDiagnostic)
    assert first.location.file_path is None
    assert first.location.line == 27
    assert first.location.column == 21
    assert first.view_name == "view<unused>"
    second = result.all_diagnostics[1]
    assert isinstance(second, diagnostics.UnreferencedViewDiagnostic)
    assert second.location.file_path is None
    assert second.location.line == 33
    assert second.location.column == 21
    assert second.view_name == "view<also_unused>"


def test_duplicate_view(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.LocalNameConflictDiagnostic)
    assert diagnostic.location.file_path is None
    assert diagnostic.location.line == 9
    assert diagnostic.location.column == 21
    assert diagnostic.local_name == "number"
    assert diagnostic.first_definition_line == 3


def test_invalid_view_name(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.InvalidLocalNameFormatDiagnostic)
    assert diagnostic.location.file_path is None
    assert diagnostic.location.line == 3
    assert diagnostic.location.column == 21
    assert diagnostic.local_name == "Number"
    assert diagnostic.char == "N"


def test_view_position_constraint(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.ViewQualityConstraintDiagnostic)
    assert diagnostic.location.file_path is None
    assert diagnostic.location.line == 7
    assert diagnostic.location.column == 24
    assert diagnostic.constraint_name == "position</box>"


def test_view_action_constraint(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.ViewQualityConstraintDiagnostic)
    assert diagnostic.location.file_path is None
    assert diagnostic.location.line == 7
    assert diagnostic.location.column == 24
    assert diagnostic.constraint_name == "action</run>"


def test_view_missing_value_constraint(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.ViewMissingValueConstraintDiagnostic)
    assert diagnostic.location.file_path is None
    assert diagnostic.location.line == 3
    assert diagnostic.location.column == 21
    assert diagnostic.view_name == "view<number>"


def test_view_multiple_value_constraints(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.ViewMultipleValueConstraintsDiagnostic)
    assert diagnostic.location.file_path is None
    assert diagnostic.location.line == 8
    assert diagnostic.location.column == 24
    assert diagnostic.first_value_name == "value<standard:/number/rational>"
    assert diagnostic.first_constraint_line == 7


def test_view_duplicate_constraint(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.DuplicatePositionConstraintDiagnostic)
    assert diagnostic.location.file_path is None
    assert diagnostic.location.line == 7
    assert diagnostic.location.column == 24
    assert diagnostic.constraint_name == "value<standard:/number/rational>"
    assert diagnostic.first_constraint_line == 6


def test_duplicate_operation(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.DuplicateDefinitionDiagnostic)
    assert diagnostic.location.file_path is None
    assert diagnostic.location.line == 20
    assert diagnostic.location.column == 1
    assert diagnostic.definition_type == "operation"
    assert diagnostic.path == "/copy"
    assert diagnostic.first_definition_line == 2
