"""Structural validation of Operation Execution Statements within actions.

Follow program validator test authoring rules in program_validator_tests/AGENTS.md.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from define.compiler.errors import diagnostics
from define.compiler.validator.test_helpers import assert_no_errors

if TYPE_CHECKING:
    from define.compiler.conftest import ValidateTestdataStructuralNonFilesystem


def test_valid_arguments(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert_no_errors(result)


def test_looks_at_view(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.OperationArgumentViewDiagnostic)
    assert diagnostic.location.file_path is None
    assert diagnostic.location.line == 27
    assert diagnostic.location.column == 42
    assert diagnostic.view_name == "view<number>"


def test_aliased_positions(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.AliasedViewDiagnostic)
    assert diagnostic.location.file_path is None
    assert diagnostic.location.line == 27
    assert diagnostic.location.column == 42
    assert diagnostic.looked_at_name == "position<number>"
    assert diagnostic.first_argument_line == 26


def test_aliased_chained_positions(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.AliasedViewDiagnostic)
    assert diagnostic.location.file_path is None
    assert diagnostic.location.line == 28
    assert diagnostic.location.column == 42
    assert diagnostic.looked_at_name == "position<number>::position</child>"
    assert diagnostic.first_argument_line == 27


def test_same_position_in_separate_executions(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert_no_errors(result)


def test_parent_and_child_positions(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert_no_errors(result)


def test_undefined_positions(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 2
    first, second = result.all_diagnostics
    assert isinstance(first, diagnostics.UndefinedLocalNameDiagnostic)
    assert first.location.file_path is None
    assert first.location.line == 25
    assert first.location.column == 42
    assert first.local_name == "position<missing>"
    assert isinstance(second, diagnostics.UndefinedLocalNameDiagnostic)
    assert second.location.file_path is None
    assert second.location.line == 26
    assert second.location.column == 42
    assert second.local_name == "position<missing>"


def test_invalid_argument_view_name(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.InvalidLocalNameFormatDiagnostic)
    assert diagnostic.location.file_path is None
    assert diagnostic.location.line == 27
    assert diagnostic.location.column == 23
    assert diagnostic.local_name == "Source"
    assert diagnostic.chars == ("S",)


def test_duplicate_argument(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.DuplicateOperationArgumentDiagnostic)
    assert diagnostic.location.file_path is None
    assert diagnostic.location.line == 28
    assert diagnostic.location.column == 18
    assert diagnostic.view_name == "view<source>"
    assert diagnostic.first_argument_line == 27


def test_invalid_literal_name(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.InvalidGlobalNamePathCharacterDiagnostic)
    assert diagnostic.location.file_path is None
    assert diagnostic.location.line == 27
    assert diagnostic.location.column == 63
    assert diagnostic.segment == "bad-name"
    assert diagnostic.chars == ("-",)


def test_invalid_operation_name(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.InvalidGlobalNamePathCharacterDiagnostic)
    assert diagnostic.location.file_path is None
    assert diagnostic.location.line == 26
    assert diagnostic.location.column == 35
    assert diagnostic.segment == "bad-name"
    assert diagnostic.chars == ("-",)
