"""Reference graph validation of Logical Operation Execution Statements."""

from __future__ import annotations

from typing import TYPE_CHECKING

from define.compiler import ast
from define.compiler.errors import diagnostics
from define.compiler.validator.test_helpers import assert_no_errors

if TYPE_CHECKING:
    from define.compiler.conftest import (
        ValidateTestdataNonFilesystemWithReferenceGraph,
    )


def test_valid_execution(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert_no_errors(result)


def test_read_not_supported(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.all_exceptions == []
    assert result.all_diagnostics == [
        diagnostics.LogicalOperationReadNotSupportedDiagnostic(
            location=ast.SourceLocation(line=31, column=41, end_line=31, end_column=52),
            looked_at_name="view<amount>",
            logical_operation_name="logical_operation</negate>",
            value_name="value</number>",
        )
    ]


def test_write_not_supported(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.all_exceptions == []
    assert result.all_diagnostics == [
        diagnostics.LogicalOperationWriteNotSupportedDiagnostic(
            location=ast.SourceLocation(line=32, column=42, end_line=32, end_column=54),
            looked_at_name="view<negated>",
            logical_operation_name="logical_operation</negate>",
            value_name="value</number>",
        )
    ]


def test_logical_operation_not_supported(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.all_exceptions == []
    assert result.all_diagnostics == [
        diagnostics.LogicalOperationReadNotSupportedDiagnostic(
            location=ast.SourceLocation(line=40, column=41, end_line=40, end_column=52),
            looked_at_name="view<amount>",
            logical_operation_name="logical_operation</negate>",
            value_name="value</number>",
        ),
        diagnostics.LogicalOperationWriteNotSupportedDiagnostic(
            location=ast.SourceLocation(line=41, column=42, end_line=41, end_column=54),
            looked_at_name="view<negated>",
            logical_operation_name="logical_operation</negate>",
            value_name="value</number>",
        ),
    ]


def test_write_to_input_only_view(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.all_exceptions == []
    assert result.all_diagnostics == [
        diagnostics.WriteToInputOnlyViewDiagnostic(
            location=ast.SourceLocation(line=33, column=42, end_line=33, end_column=52),
            looked_at_name="view<other>",
            view_name="view<result>",
            operation_name="logical_operation</negate>",
        )
    ]


def test_read_from_unwritten_output_view(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.all_exceptions == []
    assert result.all_diagnostics == [
        diagnostics.ReadFromUnwrittenOutputViewDiagnostic(
            location=ast.SourceLocation(line=32, column=41, end_line=32, end_column=51),
            looked_at_name="view<first>",
            view_name="view<value>",
            operation_name="logical_operation</negate>",
        )
    ]


def test_undefined_logical_operation_view(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.all_exceptions == []
    assert result.all_diagnostics == [
        diagnostics.MissingOperationArgumentDiagnostic(
            location=ast.SourceLocation(line=31, column=21, end_line=31, end_column=46),
            view_name="view<value>",
            operation_name="logical_operation</negate>",
        ),
        diagnostics.UndefinedOperationViewDiagnostic(
            location=ast.SourceLocation(line=32, column=18, end_line=32, end_column=28),
            view_name="view<input>",
            operation_name="logical_operation</negate>",
            interface_view_names=["view<value>", "view<result>"],
        ),
    ]


def test_argument_order(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.all_exceptions == []
    assert result.all_diagnostics == [
        diagnostics.OperationArgumentOrderDiagnostic(
            location=ast.SourceLocation(line=33, column=18, end_line=33, end_column=28),
            view_name="view<value>",
            operation_name="logical_operation</negate>",
            expected_order=["view<value>", "view<result>"],
        )
    ]


def test_missing_argument(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.all_exceptions == []
    assert result.all_diagnostics == [
        diagnostics.MissingOperationArgumentDiagnostic(
            location=ast.SourceLocation(line=25, column=21, end_line=25, end_column=46),
            view_name="view<value>",
            operation_name="logical_operation</negate>",
        )
    ]


def test_looks_at_undefined_view(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.all_exceptions == []
    assert result.all_diagnostics == [
        diagnostics.UndefinedLocalNameDiagnostic(
            location=ast.SourceLocation(line=26, column=41, end_line=26, end_column=53),
            local_name="view<missing>",
        )
    ]


def test_missing_logical_operation(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.all_exceptions == []
    assert result.all_diagnostics == [
        diagnostics.StandardDefinitionNotFoundDiagnostic(
            location=ast.SourceLocation(line=31, column=21, end_line=31, end_column=63),
            definition_name="logical_operation<standard:/number/missing>",
        )
    ]


def test_missing_value(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.all_exceptions == []
    assert result.all_diagnostics == [
        diagnostics.StandardDefinitionNotFoundDiagnostic(
            location=ast.SourceLocation(line=20, column=24, end_line=20, end_column=54),
            definition_name="value<standard:/number/missing>",
        )
    ]


def test_view_without_value_quality(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.all_exceptions == []
    assert result.all_diagnostics == [
        diagnostics.ViewMissingValueQualityDiagnostic(
            location=ast.SourceLocation(line=17, column=21, end_line=17, end_column=26),
            view_name="view<amount>",
        ),
        diagnostics.ValueOperationViewEncodingDiagnostic(
            location=ast.SourceLocation(line=20, column=24, end_line=20, end_column=63),
            quality_name="encoding<standard:/number/decimal/ascii>",
        ),
    ]
