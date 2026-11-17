"""Reference graph validation of Logical Operation Execution Statements."""

from __future__ import annotations

from typing import TYPE_CHECKING

from crates.source_rendering.python import rendering
from define.compiler.errors import diagnostics
from define.compiler.validator.test_helpers import assert_no_errors

if TYPE_CHECKING:
    from define.compiler.test_fixtures.validation_pipeline import (
        ValidateTestdataProjectWithReferenceGraph,
    )

pytest_plugins = ["define.compiler.test_fixtures.validation_pipeline"]


def test_valid_execution(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_validation
    assert_no_errors(result)


def test_read_not_supported(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_validation
    assert result.all_diagnostics == [
        diagnostics.LogicalOperationReadNotSupportedDiagnostic(
            location=rendering.SourceLocation(
                line=18, column=41, end_line=18, end_column=52, file_path="test.dfn"
            ),
            looked_at_name="view<amount>",
            logical_operation_name="logical_operation</negate>",
            value_name="value</number>",
        )
    ]


def test_write_not_supported(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_validation
    assert result.all_diagnostics == [
        diagnostics.LogicalOperationWriteNotSupportedDiagnostic(
            location=rendering.SourceLocation(
                line=19, column=42, end_line=19, end_column=54, file_path="test.dfn"
            ),
            looked_at_name="view<negated>",
            logical_operation_name="logical_operation</negate>",
            value_name="value</number>",
        )
    ]


def test_logical_operation_not_supported(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_validation
    assert result.all_diagnostics == [
        diagnostics.LogicalOperationReadNotSupportedDiagnostic(
            location=rendering.SourceLocation(
                line=18, column=41, end_line=18, end_column=52, file_path="test.dfn"
            ),
            looked_at_name="view<amount>",
            logical_operation_name="logical_operation</negate>",
            value_name="value</number>",
        ),
        diagnostics.LogicalOperationWriteNotSupportedDiagnostic(
            location=rendering.SourceLocation(
                line=19, column=42, end_line=19, end_column=54, file_path="test.dfn"
            ),
            looked_at_name="view<negated>",
            logical_operation_name="logical_operation</negate>",
            value_name="value</number>",
        ),
    ]


def test_write_to_input_only_view(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_validation
    assert result.all_diagnostics == [
        diagnostics.WriteToInputOnlyViewDiagnostic(
            location=rendering.SourceLocation(
                line=19, column=42, end_line=19, end_column=52, file_path="test.dfn"
            ),
            looked_at_name="view<other>",
            view_name="view<result>",
            operation_name="logical_operation<standard:/number/negate>",
        )
    ]


def test_read_from_unwritten_output_view(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_validation
    assert result.all_diagnostics == [
        diagnostics.ReadFromUnwrittenOutputViewDiagnostic(
            location=rendering.SourceLocation(
                line=18, column=37, end_line=18, end_column=47, file_path="test.dfn"
            ),
            looked_at_name="view<first>",
            view_name="view<a>",
            operation_name="logical_operation<standard:/number/negate>",
        )
    ]


def test_undefined_logical_operation_view(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_validation
    assert result.all_diagnostics == [
        diagnostics.MissingOperationArgumentDiagnostic(
            location=rendering.SourceLocation(
                line=17, column=21, end_line=17, end_column=62, file_path="test.dfn"
            ),
            view_name="view<a>",
            operation_name="logical_operation<standard:/number/negate>",
        ),
        diagnostics.UndefinedOperationViewDiagnostic(
            location=rendering.SourceLocation(
                line=18, column=18, end_line=18, end_column=28, file_path="test.dfn"
            ),
            view_name="view<input>",
            operation_name="logical_operation<standard:/number/negate>",
            interface_view_names=["view<a>", "view<result>"],
        ),
    ]


def test_argument_order(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_validation
    assert result.all_diagnostics == [
        diagnostics.OperationArgumentOrderDiagnostic(
            location=rendering.SourceLocation(
                line=19, column=18, end_line=19, end_column=24, file_path="test.dfn"
            ),
            view_name="view<a>",
            operation_name="logical_operation<standard:/number/negate>",
            expected_order=["view<a>", "view<result>"],
        )
    ]


def test_missing_argument(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_validation
    assert result.all_diagnostics == [
        diagnostics.MissingOperationArgumentDiagnostic(
            location=rendering.SourceLocation(
                line=11, column=21, end_line=11, end_column=62, file_path="test.dfn"
            ),
            view_name="view<a>",
            operation_name="logical_operation<standard:/number/negate>",
        )
    ]


def test_looks_at_undefined_view(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_validation
    assert result.all_diagnostics == [
        diagnostics.UndefinedLocalNameDiagnostic(
            location=rendering.SourceLocation(
                line=12, column=37, end_line=12, end_column=49, file_path="test.dfn"
            ),
            local_name="view<missing>",
        )
    ]


def test_missing_logical_operation(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_validation
    assert result.all_diagnostics == [
        diagnostics.StandardDefinitionNotFoundDiagnostic(
            location=rendering.SourceLocation(
                line=17, column=21, end_line=17, end_column=63, file_path="test.dfn"
            ),
            definition_name="logical_operation<standard:/number/missing>",
        )
    ]


def test_missing_value(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_validation
    assert result.all_diagnostics == [
        diagnostics.StandardDefinitionNotFoundDiagnostic(
            location=rendering.SourceLocation(
                line=6, column=24, end_line=6, end_column=54, file_path="test.dfn"
            ),
            definition_name="value<standard:/number/missing>",
        )
    ]


def test_view_without_value_quality(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_validation
    assert result.all_diagnostics == [
        diagnostics.ViewMissingValueQualityDiagnostic(
            location=rendering.SourceLocation(
                line=3, column=16, end_line=3, end_column=27, file_path="test.dfn"
            ),
            view_name="view<amount>",
        ),
        diagnostics.ValueOperationViewEncodingDiagnostic(
            location=rendering.SourceLocation(
                line=6, column=24, end_line=6, end_column=63, file_path="test.dfn"
            ),
            quality_name="encoding<standard:/number/decimal/ascii>",
        ),
    ]
