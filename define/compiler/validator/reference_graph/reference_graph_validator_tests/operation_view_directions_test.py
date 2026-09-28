"""Reference graph validation of View Direction Statements."""

from __future__ import annotations

from typing import TYPE_CHECKING

from define.compiler import diagnostics
from define.compiler.validator.test_helpers import assert_no_errors

if TYPE_CHECKING:
    from define.compiler.conftest import (
        ValidateTestdataNonFilesystemWithReferenceGraph,
    )


def test_valid_composition(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert_no_errors(result)


def test_read_after_encoding_operation(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert_no_errors(result)


def test_unread_input_view(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.UnreadInputViewDiagnostic)
    assert diagnostic.location.file_path is None
    assert diagnostic.location.line == 21
    assert diagnostic.location.column == 21
    assert diagnostic.view_name == "view<number>"


def test_unwritten_output_view(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.UnwrittenOutputViewDiagnostic)
    assert diagnostic.location.file_path is None
    assert diagnostic.location.line == 15
    assert diagnostic.location.column == 21
    assert diagnostic.view_name == "view<number>"


def test_write_to_input_only_view(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.WriteToInputOnlyViewDiagnostic)
    assert diagnostic.location.file_path is None
    assert diagnostic.location.line == 31
    assert diagnostic.location.column == 41
    assert diagnostic.looked_at_name == "view<number>"
    assert diagnostic.view_name == "view<total>"
    assert diagnostic.operation_name == "operation</increment_by>"


def test_read_from_unwritten_output_view(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.ReadFromUnwrittenOutputViewDiagnostic)
    assert diagnostic.location.file_path is None
    assert diagnostic.location.line == 31
    assert diagnostic.location.column == 41
    assert diagnostic.looked_at_name == "view<number>"
    assert diagnostic.view_name == "view<total>"
    assert diagnostic.operation_name == "operation</increment_by>"


def test_output_view_looks_at_literal(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.OutputViewLooksAtLiteralDiagnostic)
    assert diagnostic.location.file_path is None
    assert diagnostic.location.line == 31
    assert diagnostic.location.column == 42
    assert diagnostic.view_name == "view<target>"
    assert diagnostic.operation_name == "operation</copy>"


def test_output_view_looks_at_literal_in_action(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.OutputViewLooksAtLiteralDiagnostic)
    assert diagnostic.location.file_path is None
    assert diagnostic.location.line == 33
    assert diagnostic.location.column == 42
    assert diagnostic.view_name == "view<target>"
    assert diagnostic.operation_name == "operation</copy>"


def test_unknown_view_use(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 2
    missing, undefined = result.all_diagnostics
    assert isinstance(missing, diagnostics.MissingOperationArgumentDiagnostic)
    assert missing.location.file_path is None
    assert missing.location.line == 25
    assert missing.location.column == 21
    assert missing.view_name == "view<value>"
    assert missing.operation_name == "operation</inspect>"
    assert isinstance(undefined, diagnostics.UndefinedOperationViewDiagnostic)
    assert undefined.location.file_path is None
    assert undefined.location.line == 26
    assert undefined.location.column == 18
    assert undefined.view_name == "view<other>"
    assert undefined.operation_name == "operation</inspect>"
    assert undefined.interface_view_names == ["view<value>"]


def test_output_view_sets_value_in_action(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert_no_errors(result)


def test_output_view_argument_error_in_destructor_does_not_report_changed_value(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(
        diagnostic, diagnostics.OperationArgumentViolatesConstraintsDiagnostic
    )
    assert diagnostic.location.file_path is None
    assert diagnostic.location.line == 33
    assert diagnostic.location.column == 42
    assert diagnostic.view_name == "view<target>"
    assert diagnostic.looked_at_name == "position</value>"
    assert diagnostic.looked_at_kind == diagnostics.LookedAtKind.POSITION
    assert diagnostic.missing_qualities == ["value<standard:/number/rational>"]


def test_read_and_written_view_requires_set_value_in_action(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.UnsetValueDiagnostic)
    assert diagnostic.location.file_path is None
    assert diagnostic.location.line == 32
    assert diagnostic.location.column == 41
    assert diagnostic.position_name == "position<total>"


def test_output_view_requires_no_caller_value(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert_no_errors(result)


def test_unreferenced_view(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.UnreferencedViewDiagnostic)
    assert diagnostic.location.file_path is None
    assert diagnostic.location.line == 21
    assert diagnostic.location.column == 21
    assert diagnostic.view_name == "view<unused>"


def test_output_views_set_values_in_action(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert_no_errors(result)


def test_callee_output_view_sets_caller_value(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert_no_errors(result)


def test_output_view_in_destructor_changes_contracted_value(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.DestructorChangesValueDiagnostic)
    assert diagnostic.location.file_path is None
    assert diagnostic.location.line == 32
    assert diagnostic.location.column == 42
    assert diagnostic.position_name == "position</value>"


def test_callee_output_view_sets_implied_value(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert_no_errors(result)


def test_callee_without_output_view_leaves_implied_value_unset(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.UnsetValueDiagnostic)
    assert diagnostic.location.file_path is None
    assert diagnostic.location.line == 35
    assert diagnostic.location.column == 44
    assert diagnostic.position_name == "position<box>::position</value>"
