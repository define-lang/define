"""Reference graph validation of which views Operation Argument Statements name."""

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


def test_valid_arguments(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert_no_errors(result)


def test_undefined_view(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.sorted_diagnostics() == [
        reference_graph_diagnostics.UndefinedOperationViewDiagnostic(
            location=rendering.SourceLocation(
                line=43, column=18, end_line=43, end_column=28, file_path=None
            ),
            view_name="view<extra>",
            operation_name="operation</sum>",
            interface_view_names=["view<first>", "view<second>", "view<result>"],
        )
    ]


def test_undefined_looked_at_view_before_defined_view(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.sorted_diagnostics() == [
        structural_diagnostics.UndefinedLocalNameDiagnostic(
            location=rendering.SourceLocation(
                line=20, column=37, end_line=20, end_column=49, file_path=None
            ),
            local_name="view<missing>",
        )
    ]


def test_out_of_order(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.sorted_diagnostics() == [
        reference_graph_diagnostics.OperationArgumentOrderDiagnostic(
            location=rendering.SourceLocation(
                line=41, column=18, end_line=41, end_column=29, file_path=None
            ),
            view_name="view<source>",
            operation_name="operation</copy>",
            expected_order=["view<source>", "view<target>"],
        )
    ]


def test_many_out_of_order(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.sorted_diagnostics() == [
        reference_graph_diagnostics.OperationArgumentOrderDiagnostic(
            location=rendering.SourceLocation(
                line=57, column=18, end_line=57, end_column=28, file_path=None
            ),
            view_name="view<third>",
            operation_name="operation</sum>",
            expected_order=[
                "view<first>",
                "view<second>",
                "view<third>",
                "view<result>",
            ],
        )
    ]


def test_missing_argument(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.sorted_diagnostics() == [
        reference_graph_diagnostics.MissingOperationArgumentDiagnostic(
            location=rendering.SourceLocation(
                line=33, column=21, end_line=33, end_column=36, file_path=None
            ),
            view_name="view<target>",
            operation_name="operation</copy>",
        )
    ]


def test_duplicate_argument(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.sorted_diagnostics() == [
        structural_diagnostics.DuplicateOperationArgumentDiagnostic(
            location=rendering.SourceLocation(
                line=41, column=18, end_line=41, end_column=29, file_path=None
            ),
            view_name="view<source>",
            first_argument_line=40,
        )
    ]


def test_invalid_argument_view_name(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.sorted_diagnostics() == [
        structural_diagnostics.InvalidLocalNameFormatDiagnostic(
            location=rendering.SourceLocation(
                line=40, column=23, end_line=40, end_column=23, file_path=None
            ),
            chars=("S",),
            local_name="Source",
        )
    ]


def test_invalid_argument_view_name_in_encoding_operation(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.sorted_diagnostics() == [
        structural_diagnostics.InvalidLocalNameFormatDiagnostic(
            location=rendering.SourceLocation(
                line=39, column=23, end_line=39, end_column=23, file_path=None
            ),
            chars=("S",),
            local_name="Source",
        )
    ]


def test_missing_operation(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_validation
    assert len(result.sorted_diagnostics()) == 1
    diagnostic = result.sorted_diagnostics()[0]
    assert isinstance(
        diagnostic, structural_diagnostics.ReferencedDefinitionNotFoundDiagnostic
    )
    assert diagnostic.location.file_path == "test.dfn"
    assert diagnostic.location.line == 11
    assert diagnostic.location.column == 21
    assert diagnostic.definition_name == "operation<my.domain.com:my_lib:/copy>"
    assert diagnostic.file_path == "copy.dfn"


def test_missing_standard_operation_with_literal_argument(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.sorted_diagnostics() == [
        structural_diagnostics.StandardDefinitionNotFoundDiagnostic(
            location=rendering.SourceLocation(
                line=13, column=21, end_line=13, end_column=55
            ),
            definition_name="operation<standard:/number/missing>",
        )
    ]


def test_duplicate_executed_view(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert len(result.sorted_diagnostics()) == 1
    diagnostic = result.sorted_diagnostics()[0]
    assert isinstance(diagnostic, structural_diagnostics.LocalNameConflictDiagnostic)
    assert diagnostic.location.file_path is None
    assert diagnostic.location.line == 9
    assert diagnostic.location.column == 16
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
    assert result.sorted_diagnostics() == [
        reference_graph_diagnostics.UndefinedOperationViewDiagnostic(
            location=rendering.SourceLocation(
                line=44, column=18, end_line=44, end_column=28, file_path=None
            ),
            view_name="view<extra>",
            operation_name="operation</copy>",
            interface_view_names=["view<source>", "view<target>"],
        )
    ]


def test_missing_argument_in_action(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.sorted_diagnostics() == [
        reference_graph_diagnostics.MissingOperationArgumentDiagnostic(
            location=rendering.SourceLocation(
                line=35, column=21, end_line=35, end_column=36, file_path=None
            ),
            view_name="view<target>",
            operation_name="operation</copy>",
        )
    ]


def test_out_of_order_in_action(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.sorted_diagnostics() == [
        reference_graph_diagnostics.OperationArgumentOrderDiagnostic(
            location=rendering.SourceLocation(
                line=43, column=18, end_line=43, end_column=29, file_path=None
            ),
            view_name="view<source>",
            operation_name="operation</copy>",
            expected_order=["view<source>", "view<target>"],
        )
    ]


def test_duplicate_argument_in_action(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert len(result.sorted_diagnostics()) == 1
    diagnostic = result.sorted_diagnostics()[0]
    assert isinstance(
        diagnostic, structural_diagnostics.DuplicateOperationArgumentDiagnostic
    )
    assert diagnostic.location.file_path is None
    assert diagnostic.location.line == 23
    assert diagnostic.location.column == 18
    assert diagnostic.view_name == "view<a>"
    assert diagnostic.first_argument_line == 22


def test_invalid_argument_view_name_in_action(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert len(result.sorted_diagnostics()) == 1
    diagnostic = result.sorted_diagnostics()[0]
    assert isinstance(
        diagnostic, structural_diagnostics.InvalidLocalNameFormatDiagnostic
    )
    assert diagnostic.location.file_path is None
    assert diagnostic.location.line == 23
    assert diagnostic.location.column == 23
    assert diagnostic.local_name == "B"
    assert diagnostic.chars == ("B",)
