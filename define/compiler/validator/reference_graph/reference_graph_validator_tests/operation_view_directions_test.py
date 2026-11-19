"""Reference graph validation of View Direction Statements."""

from __future__ import annotations

from typing import TYPE_CHECKING

from crates.source_rendering.python import rendering
from define.compiler.errors import reference_graph_diagnostics, structural_diagnostics
from define.compiler.validator.test_helpers import assert_no_errors

if TYPE_CHECKING:
    from define.compiler.test_fixtures.validation_pipeline import (
        ValidateTestdataNonFilesystemWithReferenceGraph,
        ValidateTestdataProjectWithReferenceGraph,
    )

pytest_plugins = ["define.compiler.test_fixtures.validation_pipeline"]


def test_valid_composition(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert_no_errors(result)


def test_unread_input_view(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.sorted_diagnostics() == [
        reference_graph_diagnostics.UnreadInputViewDiagnostic(
            location=rendering.SourceLocation(
                line=25, column=16, end_line=25, end_column=27, file_path=None
            ),
            view_name="view<number>",
        )
    ]


def test_unwritten_output_view(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.sorted_diagnostics() == [
        reference_graph_diagnostics.UnwrittenOutputViewDiagnostic(
            location=rendering.SourceLocation(
                line=25, column=16, end_line=25, end_column=27, file_path=None
            ),
            view_name="view<number>",
        )
    ]


def test_executes_read_write_operation_with_input_only_view(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.sorted_diagnostics() == [
        reference_graph_diagnostics.ExecutedOperationHasReadWriteViewDiagnostic(
            location=rendering.SourceLocation(
                line=40, column=21, end_line=40, end_column=44, file_path=None
            ),
            operation_name="operation</increment_by>",
            view_name="view<total>",
        )
    ]


def test_executes_read_write_operation_with_output_only_view(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.sorted_diagnostics() == [
        reference_graph_diagnostics.ExecutedOperationHasReadWriteViewDiagnostic(
            location=rendering.SourceLocation(
                line=40, column=21, end_line=40, end_column=44, file_path=None
            ),
            operation_name="operation</increment_by>",
            view_name="view<total>",
        )
    ]


def test_write_to_input_only_view_is_not_also_unread(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.sorted_diagnostics() == [
        reference_graph_diagnostics.WriteToInputOnlyViewDiagnostic(
            location=rendering.SourceLocation(
                line=28, column=42, end_line=28, end_column=53, file_path=None
            ),
            looked_at_name="view<number>",
            view_name="view<result>",
            operation_name="operation</store>",
        )
    ]


def test_read_from_unwritten_output_view_is_not_also_unwritten(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.sorted_diagnostics() == [
        reference_graph_diagnostics.ReadFromUnwrittenOutputViewDiagnostic(
            location=rendering.SourceLocation(
                line=40, column=41, end_line=40, end_column=52, file_path=None
            ),
            looked_at_name="view<number>",
            view_name="view<input>",
            operation_name="operation</show>",
        )
    ]


def test_output_view_looks_at_literal(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.sorted_diagnostics() == [
        reference_graph_diagnostics.OutputViewLooksAtLiteralDiagnostic(
            location=rendering.SourceLocation(
                line=35, column=42, end_line=35, end_column=69, file_path=None
            ),
            view_name="view<target>",
            operation_name="operation</copy>",
        )
    ]


def test_output_view_looks_at_literal_in_action(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.sorted_diagnostics() == [
        reference_graph_diagnostics.OutputViewLooksAtLiteralDiagnostic(
            location=rendering.SourceLocation(
                line=37, column=42, end_line=37, end_column=69, file_path=None
            ),
            view_name="view<target>",
            operation_name="operation</copy>",
        )
    ]


def test_unknown_view_use(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.sorted_diagnostics() == [
        reference_graph_diagnostics.MissingOperationArgumentDiagnostic(
            location=rendering.SourceLocation(
                line=41, column=21, end_line=41, end_column=39, file_path=None
            ),
            view_name="view<value>",
            operation_name="operation</inspect>",
        ),
        reference_graph_diagnostics.UndefinedOperationViewDiagnostic(
            location=rendering.SourceLocation(
                line=42, column=18, end_line=42, end_column=28, file_path=None
            ),
            view_name="view<other>",
            operation_name="operation</inspect>",
            interface_view_names=["view<value>", "view<result>"],
        ),
    ]


def test_output_view_sets_value_in_action(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert_no_errors(result)


def test_output_view_argument_error_in_destructor_does_not_report_changed_value(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_validation
    assert result.sorted_diagnostics() == [
        reference_graph_diagnostics.OperationArgumentMissingQualitiesDiagnostic(
            location=rendering.SourceLocation(
                line=8, column=42, end_line=8, end_column=57, file_path="cleanup.dfn"
            ),
            view_name="view<target>",
            looked_at_name="position</value>",
            looked_at_kind=reference_graph_diagnostics.LookedAtKind.POSITION,
            missing_qualities=["value<standard:/number/natural>"],
        )
    ]


def test_read_and_written_view_requires_set_value_in_action(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.sorted_diagnostics() == [
        reference_graph_diagnostics.UnsetValueDiagnostic(
            location=rendering.SourceLocation(
                line=42, column=41, end_line=42, end_column=55, file_path=None
            ),
            position_name="position<total>",
        )
    ]


def test_output_view_requires_no_caller_value(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert_no_errors(result)


def test_unreferenced_view(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.sorted_diagnostics() == [
        structural_diagnostics.UnreferencedViewDiagnostic(
            location=rendering.SourceLocation(
                line=31, column=16, end_line=31, end_column=27, file_path=None
            ),
            view_name="view<unused>",
        )
    ]


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
    assert result.sorted_diagnostics() == [
        reference_graph_diagnostics.DestructorChangesValueDiagnostic(
            location=rendering.SourceLocation(
                line=36, column=42, end_line=36, end_column=57, file_path=None
            ),
            position_name="position</value>",
        )
    ]


def test_callee_output_view_sets_implied_value(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert_no_errors(result)


def test_callee_without_output_view_leaves_implied_value_unset(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert len(result.sorted_diagnostics()) == 1
    diagnostic = result.sorted_diagnostics()[0]
    assert isinstance(diagnostic, reference_graph_diagnostics.UnsetValueDiagnostic)
    assert diagnostic.location.file_path is None
    assert diagnostic.location.line == 35
    assert diagnostic.location.column == 46
    assert diagnostic.position_name == "position<box>::position</value>"


def test_missing_operation_before_output_view_read(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.sorted_diagnostics() == [
        structural_diagnostics.StandardDefinitionNotFoundDiagnostic(
            location=rendering.SourceLocation(
                line=46, column=21, end_line=46, end_column=63, file_path=None
            ),
            definition_name="operation<standard:/number/natural/missing>",
        )
    ]


def test_output_view_written_twice(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.sorted_diagnostics() == [
        reference_graph_diagnostics.InterfaceViewWrittenTwiceDiagnostic(
            location=rendering.SourceLocation(
                line=90, column=42, end_line=90, end_column=53, file_path=None
            ),
            looked_at_name="view<result>",
            view_name="view<target>",
            operation_name="operation</copy>",
            first_write=rendering.SourceLocation(
                line=86, column=42, end_line=86, end_column=53, file_path=None
            ),
        )
    ]


def test_read_write_view_written_twice(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.sorted_diagnostics() == [
        reference_graph_diagnostics.InterfaceViewWrittenTwiceDiagnostic(
            location=rendering.SourceLocation(
                line=79, column=42, end_line=79, end_column=52, file_path=None
            ),
            looked_at_name="view<count>",
            view_name="view<target>",
            operation_name="operation</copy>",
            first_write=rendering.SourceLocation(
                line=75, column=42, end_line=75, end_column=52, file_path=None
            ),
        )
    ]


def test_read_from_written_read_write_view(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.sorted_diagnostics() == [
        reference_graph_diagnostics.ReadFromWrittenReadWriteViewDiagnostic(
            location=rendering.SourceLocation(
                line=106, column=41, end_line=106, end_column=51, file_path=None
            ),
            looked_at_name="view<count>",
            view_name="view<value>",
            operation_name="operation</inspect>",
            write=rendering.SourceLocation(
                line=103, column=42, end_line=103, end_column=52, file_path=None
            ),
        )
    ]


def test_executes_read_write_operation(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.sorted_diagnostics() == [
        reference_graph_diagnostics.ExecutedOperationHasReadWriteViewDiagnostic(
            location=rendering.SourceLocation(
                line=89, column=21, end_line=89, end_column=41, file_path=None
            ),
            operation_name="operation</increment>",
            view_name="view<value>",
        )
    ]


def test_written_twice_after_unknown_use(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.sorted_diagnostics() == [
        structural_diagnostics.NoProjectRootForDefinitionNotInSuppliedSourceDiagnostic(
            location=rendering.SourceLocation(
                line=88, column=21, end_line=88, end_column=39, file_path=None
            ),
            definition_name="operation</missing>",
            config_path=".define/project/config.defcl",
        ),
        reference_graph_diagnostics.InterfaceViewWrittenTwiceDiagnostic(
            location=rendering.SourceLocation(
                line=93, column=42, end_line=93, end_column=53, file_path=None
            ),
            looked_at_name="view<result>",
            view_name="view<target>",
            operation_name="operation</copy>",
            first_write=rendering.SourceLocation(
                line=86, column=42, end_line=86, end_column=53, file_path=None
            ),
        ),
    ]


def test_read_from_written_read_write_view_after_unknown_use(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.sorted_diagnostics() == [
        structural_diagnostics.NoProjectRootForDefinitionNotInSuppliedSourceDiagnostic(
            location=rendering.SourceLocation(
                line=95, column=21, end_line=95, end_column=39, file_path=None
            ),
            definition_name="operation</missing>",
            config_path=".define/project/config.defcl",
        ),
        reference_graph_diagnostics.ReadFromWrittenReadWriteViewDiagnostic(
            location=rendering.SourceLocation(
                line=99, column=41, end_line=99, end_column=51, file_path=None
            ),
            looked_at_name="view<count>",
            view_name="view<value>",
            operation_name="operation</inspect>",
            write=rendering.SourceLocation(
                line=93, column=42, end_line=93, end_column=52, file_path=None
            ),
        ),
    ]
