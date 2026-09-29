"""Reference graph validation of which views Operation Argument Statements name."""

from __future__ import annotations

from pathlib import PurePosixPath
from typing import TYPE_CHECKING

from define.compiler.errors import diagnostics
from define.compiler.validator.test_helpers import assert_no_errors

if TYPE_CHECKING:
    from define.compiler.conftest import (
        ValidateTestdataNonFilesystemWithReferenceGraph,
        ValidateTestdataProjectWithReferenceGraph,
    )


def test_valid_arguments(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert_no_errors(result)


def test_no_views(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert_no_errors(result)


def test_undefined_view(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.UndefinedOperationViewDiagnostic)
    assert diagnostic.location.file_path is None
    assert diagnostic.location.line == 39
    assert diagnostic.location.column == 18
    assert diagnostic.view_name == "view<extra>"
    assert diagnostic.operation_name == "operation</sum>"
    assert diagnostic.interface_view_names == [
        "view<first>",
        "view<second>",
        "view<result>",
    ]


def test_arguments_for_operation_without_views(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(
        diagnostic, diagnostics.ArgumentsForOperationWithoutViewsDiagnostic
    )
    assert diagnostic.location.file_path is None
    assert diagnostic.location.line == 18
    assert diagnostic.location.column == 13
    assert diagnostic.operation_name == "operation</reset>"


def test_out_of_order(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.OperationArgumentOrderDiagnostic)
    assert diagnostic.location.file_path is None
    assert diagnostic.location.line == 37
    assert diagnostic.location.column == 18
    assert diagnostic.view_name == "view<source>"
    assert diagnostic.operation_name == "operation</copy>"
    assert diagnostic.expected_order == ["view<source>", "view<target>"]


def test_many_out_of_order(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.OperationArgumentOrderDiagnostic)
    assert diagnostic.location.file_path is None
    assert diagnostic.location.line == 43
    assert diagnostic.location.column == 18
    assert diagnostic.view_name == "view<third>"
    assert diagnostic.operation_name == "operation</sum>"
    assert diagnostic.expected_order == [
        "view<first>",
        "view<second>",
        "view<third>",
        "view<result>",
    ]


def test_missing_argument(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.MissingOperationArgumentDiagnostic)
    assert diagnostic.location.file_path is None
    assert diagnostic.location.line == 29
    assert diagnostic.location.column == 21
    assert diagnostic.view_name == "view<target>"
    assert diagnostic.operation_name == "operation</copy>"


def test_no_arguments_block(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 2
    source_diagnostic, target_diagnostic = result.all_diagnostics
    assert isinstance(source_diagnostic, diagnostics.MissingOperationArgumentDiagnostic)
    assert source_diagnostic.location.file_path is None
    assert source_diagnostic.location.line == 23
    assert source_diagnostic.location.column == 21
    assert source_diagnostic.view_name == "view<source>"
    assert source_diagnostic.operation_name == "operation</copy>"
    assert isinstance(target_diagnostic, diagnostics.MissingOperationArgumentDiagnostic)
    assert target_diagnostic.location.file_path is None
    assert target_diagnostic.location.line == 23
    assert target_diagnostic.location.column == 21
    assert target_diagnostic.view_name == "view<target>"
    assert target_diagnostic.operation_name == "operation</copy>"


def test_duplicate_argument(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.DuplicateOperationArgumentDiagnostic)
    assert diagnostic.location.file_path is None
    assert diagnostic.location.line == 37
    assert diagnostic.location.column == 18
    assert diagnostic.view_name == "view<source>"
    assert diagnostic.first_argument_line == 36


def test_invalid_argument_view_name(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.InvalidLocalNameFormatDiagnostic)
    assert diagnostic.location.file_path is None
    assert diagnostic.location.line == 36
    assert diagnostic.location.column == 23
    assert diagnostic.local_name == "Source"
    assert diagnostic.chars == ("S",)


def test_missing_operation(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_result
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.ReferencedDefinitionNotFoundDiagnostic)
    assert diagnostic.location.file_path == PurePosixPath("test.dfn")
    assert diagnostic.location.line == 11
    assert diagnostic.location.column == 31
    assert diagnostic.definition_name == "operation<my.domain.com:my_lib:/copy>"
    assert diagnostic.file_path == "copy.dfn"


def test_duplicate_executed_view(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.LocalNameConflictDiagnostic)
    assert diagnostic.location.file_path is None
    assert diagnostic.location.line == 9
    assert diagnostic.location.column == 21
    assert diagnostic.local_name == "source"
    assert diagnostic.first_definition_line == 3


def test_valid_arguments_in_action(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert_no_errors(result)


def test_undefined_view_in_action(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.UndefinedOperationViewDiagnostic)
    assert diagnostic.location.file_path is None
    assert diagnostic.location.line == 40
    assert diagnostic.location.column == 18
    assert diagnostic.view_name == "view<extra>"
    assert diagnostic.operation_name == "operation</copy>"
    assert diagnostic.interface_view_names == ["view<source>", "view<target>"]


def test_missing_argument_in_action(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.MissingOperationArgumentDiagnostic)
    assert diagnostic.location.file_path is None
    assert diagnostic.location.line == 31
    assert diagnostic.location.column == 21
    assert diagnostic.view_name == "view<target>"
    assert diagnostic.operation_name == "operation</copy>"


def test_out_of_order_in_action(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.OperationArgumentOrderDiagnostic)
    assert diagnostic.location.file_path is None
    assert diagnostic.location.line == 39
    assert diagnostic.location.column == 18
    assert diagnostic.view_name == "view<source>"
    assert diagnostic.operation_name == "operation</copy>"
    assert diagnostic.expected_order == ["view<source>", "view<target>"]


def test_duplicate_argument_in_action(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.DuplicateOperationArgumentDiagnostic)
    assert diagnostic.location.file_path is None
    assert diagnostic.location.line == 23
    assert diagnostic.location.column == 18
    assert diagnostic.view_name == "view<a>"
    assert diagnostic.first_argument_line == 22


def test_invalid_argument_view_name_in_action(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.InvalidLocalNameFormatDiagnostic)
    assert diagnostic.location.file_path is None
    assert diagnostic.location.line == 23
    assert diagnostic.location.column == 23
    assert diagnostic.local_name == "B"
    assert diagnostic.chars == ("B",)


def test_looks_at_view_in_action(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.OperationArgumentViewDiagnostic)
    assert diagnostic.location.file_path is None
    assert diagnostic.location.line == 22
    assert diagnostic.location.column == 37
    assert diagnostic.view_name == "view<first>"
