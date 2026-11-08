"""Reference graph validation of View Direction Statements."""

from __future__ import annotations

from typing import TYPE_CHECKING

from define.compiler import name_types
from define.compiler.errors import diagnostics
from define.compiler.validator.test_helpers import assert_no_errors
from source_rendering.python import rendering

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
    assert diagnostic.location.column == 16
    assert diagnostic.view_name == "view<number>"
    assert diagnostic.operation_name_type == name_types.NameType.OPERATION


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
    assert diagnostic.location.column == 16
    assert diagnostic.view_name == "view<number>"
    assert diagnostic.operation_name_type == name_types.NameType.OPERATION


def test_executes_read_write_operation_with_input_only_view(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.all_exceptions == []
    assert result.all_diagnostics == [
        diagnostics.ExecutedOperationHasReadWriteViewDiagnostic(
            location=rendering.SourceLocation(
                line=30, column=21, end_line=30, end_column=44
            ),
            operation_name="operation</increment_by>",
            view_name="view<total>",
        ),
    ]


def test_executes_read_write_operation_with_output_only_view(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.all_exceptions == []
    assert result.all_diagnostics == [
        diagnostics.ExecutedOperationHasReadWriteViewDiagnostic(
            location=rendering.SourceLocation(
                line=30, column=21, end_line=30, end_column=44
            ),
            operation_name="operation</increment_by>",
            view_name="view<total>",
        ),
    ]


def test_write_to_input_only_view_is_not_also_unread(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.WriteToInputOnlyViewDiagnostic)
    assert diagnostic.location.file_path is None
    assert diagnostic.location.line == 24
    assert diagnostic.location.column == 42
    assert diagnostic.looked_at_name == "view<number>"
    assert diagnostic.view_name == "view<result>"
    assert diagnostic.operation_name == "operation</store>"


def test_read_from_unwritten_output_view_is_not_also_unwritten(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.ReadFromUnwrittenOutputViewDiagnostic)
    assert diagnostic.location.file_path is None
    assert diagnostic.location.line == 24
    assert diagnostic.location.column == 41
    assert diagnostic.looked_at_name == "view<number>"
    assert diagnostic.view_name == "view<input>"
    assert diagnostic.operation_name == "operation</show>"


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
        diagnostic, diagnostics.OperationArgumentMissingQualitiesDiagnostic
    )
    assert diagnostic.location.file_path is None
    assert diagnostic.location.line == 37
    assert diagnostic.location.column == 42
    assert diagnostic.view_name == "view<target>"
    assert diagnostic.looked_at_name == "position</value>"
    assert diagnostic.looked_at_kind == diagnostics.LookedAtKind.POSITION
    assert diagnostic.missing_qualities == ["value<standard:/number/natural>"]


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
    assert diagnostic.location.column == 16
    assert diagnostic.view_name == "view<unused>"
    assert diagnostic.operation_name_type == name_types.NameType.OPERATION


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
    assert diagnostic.location.column == 46
    assert diagnostic.position_name == "position<box>::position</value>"


def test_missing_operation_before_output_view_read(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.all_exceptions == []
    assert result.all_diagnostics == [
        diagnostics.StandardDefinitionNotFoundDiagnostic(
            location=rendering.SourceLocation(
                line=42, column=21, end_line=42, end_column=63
            ),
            definition_name="operation<standard:/number/natural/missing>",
        )
    ]


def test_output_view_written_twice(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.all_exceptions == []
    assert result.all_diagnostics == [
        diagnostics.InterfaceViewWrittenTwiceDiagnostic(
            location=rendering.SourceLocation(
                line=66, column=42, end_line=66, end_column=53
            ),
            looked_at_name="view<result>",
            view_name="view<target>",
            operation_name="operation</copy>",
            first_write=rendering.SourceLocation(
                line=62, column=42, end_line=62, end_column=53
            ),
        )
    ]


def test_read_write_view_written_twice(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.all_exceptions == []
    assert result.all_diagnostics == [
        diagnostics.InterfaceViewWrittenTwiceDiagnostic(
            location=rendering.SourceLocation(
                line=58, column=42, end_line=58, end_column=52
            ),
            looked_at_name="view<count>",
            view_name="view<target>",
            operation_name="operation</copy>",
            first_write=rendering.SourceLocation(
                line=54, column=42, end_line=54, end_column=52
            ),
        )
    ]


def test_read_from_written_read_write_view(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.all_exceptions == []
    assert result.all_diagnostics == [
        diagnostics.ReadFromWrittenReadWriteViewDiagnostic(
            location=rendering.SourceLocation(
                line=69, column=41, end_line=69, end_column=51
            ),
            looked_at_name="view<count>",
            view_name="view<value>",
            operation_name="operation</inspect>",
            write=rendering.SourceLocation(
                line=66, column=42, end_line=66, end_column=52
            ),
        )
    ]


def test_executes_read_write_operation(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.all_exceptions == []
    assert result.all_diagnostics == [
        diagnostics.ExecutedOperationHasReadWriteViewDiagnostic(
            location=rendering.SourceLocation(
                line=58, column=21, end_line=58, end_column=41
            ),
            operation_name="operation</increment>",
            view_name="view<value>",
        ),
    ]


def test_written_twice_after_unknown_use(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.all_exceptions == []
    assert result.all_diagnostics == [
        diagnostics.NoProjectRootForDefinitionNotInSuppliedSourceDiagnostic(
            location=rendering.SourceLocation(
                line=64, column=21, end_line=64, end_column=39
            ),
            definition_name="operation</missing>",
            config_path=".define/project/config.defcl",
        ),
        diagnostics.InterfaceViewWrittenTwiceDiagnostic(
            location=rendering.SourceLocation(
                line=69, column=42, end_line=69, end_column=53
            ),
            looked_at_name="view<result>",
            view_name="view<target>",
            operation_name="operation</copy>",
            first_write=rendering.SourceLocation(
                line=62, column=42, end_line=62, end_column=53
            ),
        ),
    ]


def test_read_from_written_read_write_view_after_unknown_use(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.all_exceptions == []
    assert result.all_diagnostics == [
        diagnostics.NoProjectRootForDefinitionNotInSuppliedSourceDiagnostic(
            location=rendering.SourceLocation(
                line=65, column=21, end_line=65, end_column=39
            ),
            definition_name="operation</missing>",
            config_path=".define/project/config.defcl",
        ),
        diagnostics.ReadFromWrittenReadWriteViewDiagnostic(
            location=rendering.SourceLocation(
                line=69, column=41, end_line=69, end_column=51
            ),
            looked_at_name="view<count>",
            view_name="view<value>",
            operation_name="operation</inspect>",
            write=rendering.SourceLocation(
                line=63, column=42, end_line=63, end_column=52
            ),
        ),
    ]


def test_written_after_encoding_operation(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.all_exceptions == []
    assert result.all_diagnostics == [
        diagnostics.InterfaceViewWrittenTwiceDiagnostic(
            location=rendering.SourceLocation(
                line=63, column=42, end_line=63, end_column=53
            ),
            looked_at_name="view<result>",
            view_name="view<target>",
            operation_name="operation</copy>",
            first_write=rendering.SourceLocation(
                line=60, column=9, end_line=60, end_column=39
            ),
        )
    ]
