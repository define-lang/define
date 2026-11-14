"""Reference graph validation of the Encoding Operations associated with a logical operation."""

from __future__ import annotations

from typing import TYPE_CHECKING

from crates.source_rendering.python import rendering
from define.compiler.errors import diagnostics
from define.compiler.validator.test_helpers import standard_library_file

if TYPE_CHECKING:
    from define.compiler.conftest import (
        ValidateTestdataProjectWithReferenceGraph,
    )


def test_encoding_operation_with_fewer_views(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_diagnostics == [
        diagnostics.AssociatedEncodingOperationViewCountDiagnostic(
            location=rendering.SourceLocation(
                line=1,
                column=12,
                end_line=1,
                end_column=65,
                file_path=standard_library_file("number/integer/ascii/add.dfn"),
            ),
            encoding_operation_name="encoding_operation<standard:/number/integer/ascii/add>",
            view_count=3,
            logical_operation_name="logical_operation<my.domain.com:my_lib:/negate>",
            logical_operation_view_count=2,
            association_location=rendering.SourceLocation(
                line=5,
                column=28,
                end_line=5,
                end_column=61,
                file_path=".define/encodings/encoding_operations.defcl",
            ),
        )
    ]


def test_encoding_operation_with_different_view_name(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_diagnostics == [
        diagnostics.AssociatedEncodingOperationViewNameDiagnostic(
            location=rendering.SourceLocation(
                line=2,
                column=16,
                end_line=2,
                end_column=22,
                file_path=standard_library_file("number/integer/ascii/negate.dfn"),
            ),
            view_number=1,
            encoding_operation_name="encoding_operation<standard:/number/integer/ascii/negate>",
            view_name="view<a>",
            logical_operation_name="logical_operation<my.domain.com:my_lib:/negate>",
            logical_operation_view_name="view<value>",
            association_location=rendering.SourceLocation(
                line=5,
                column=28,
                end_line=5,
                end_column=64,
                file_path=".define/encodings/encoding_operations.defcl",
            ),
        )
    ]


def test_encoding_operation_with_different_view_direction(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_diagnostics == [
        diagnostics.AssociatedEncodingOperationViewDirectionDiagnostic(
            location=rendering.SourceLocation(
                line=2,
                column=16,
                end_line=2,
                end_column=22,
                file_path=standard_library_file("number/integer/ascii/negate.dfn"),
            ),
            view_name="view<a>",
            direction="read",
            encoding_operation_name="encoding_operation<standard:/number/integer/ascii/negate>",
            logical_operation_direction="written",
            logical_operation_name="logical_operation<my.domain.com:my_lib:/negate>",
            association_location=rendering.SourceLocation(
                line=5,
                column=28,
                end_line=5,
                end_column=64,
                file_path=".define/encodings/encoding_operations.defcl",
            ),
        )
    ]


def test_encoding_operation_with_views_in_different_order(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_diagnostics == [
        diagnostics.AssociatedEncodingOperationViewNameDiagnostic(
            location=rendering.SourceLocation(
                line=2,
                column=16,
                end_line=2,
                end_column=22,
                file_path=standard_library_file("number/integer/ascii/negate.dfn"),
            ),
            view_number=1,
            encoding_operation_name="encoding_operation<standard:/number/integer/ascii/negate>",
            view_name="view<a>",
            logical_operation_name="logical_operation<my.domain.com:my_lib:/negate>",
            logical_operation_view_name="view<result>",
            association_location=rendering.SourceLocation(
                line=5,
                column=28,
                end_line=5,
                end_column=64,
                file_path=".define/encodings/encoding_operations.defcl",
            ),
        ),
        diagnostics.AssociatedEncodingOperationViewNameDiagnostic(
            location=rendering.SourceLocation(
                line=8,
                column=16,
                end_line=8,
                end_column=27,
                file_path=standard_library_file("number/integer/ascii/negate.dfn"),
            ),
            view_number=2,
            encoding_operation_name="encoding_operation<standard:/number/integer/ascii/negate>",
            view_name="view<result>",
            logical_operation_name="logical_operation<my.domain.com:my_lib:/negate>",
            logical_operation_view_name="view<a>",
            association_location=rendering.SourceLocation(
                line=5,
                column=28,
                end_line=5,
                end_column=64,
                file_path=".define/encodings/encoding_operations.defcl",
            ),
        ),
    ]


def test_encoding_operations_with_same_encodings(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_diagnostics == [
        diagnostics.DuplicateAssociatedEncodingOperationDiagnostic(
            location=rendering.SourceLocation(
                line=1,
                column=12,
                end_line=1,
                end_column=70,
                file_path=standard_library_file("number/integer/ascii/multiply.dfn"),
            ),
            encoding_operation_name="encoding_operation<standard:/number/integer/ascii/multiply>",
            first_encoding_operation_name="encoding_operation<standard:/number/integer/ascii/add>",
            logical_operation_name="logical_operation<my.domain.com:my_lib:/combine>",
            association_location=rendering.SourceLocation(
                line=9,
                column=28,
                end_line=9,
                end_column=66,
                file_path=".define/encodings/encoding_operations.defcl",
            ),
            first_association_location=rendering.SourceLocation(
                line=5,
                column=28,
                end_line=5,
                end_column=61,
                file_path=".define/encodings/encoding_operations.defcl",
            ),
        )
    ]


def test_encoding_operation_with_read_write_view(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_diagnostics == [
        diagnostics.AssociatedEncodingOperationViewDirectionDiagnostic(
            location=rendering.SourceLocation(
                line=2,
                column=16,
                end_line=2,
                end_column=22,
                file_path="negate/integer.dfn",
            ),
            view_name="view<a>",
            direction="read/write",
            encoding_operation_name="encoding_operation<my.domain.com:my_lib:/negate/integer>",
            logical_operation_direction="read",
            logical_operation_name="logical_operation<my.domain.com:my_lib:/negate>",
            association_location=rendering.SourceLocation(
                line=5,
                column=28,
                end_line=5,
                end_column=42,
                file_path=".define/encodings/encoding_operations.defcl",
            ),
        )
    ]


def test_encoding_operation_view_without_encoding(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_diagnostics == [
        diagnostics.ViewMissingEncodingDiagnostic(
            location=rendering.SourceLocation(
                line=2,
                column=16,
                end_line=2,
                end_column=22,
                file_path="negate/integer.dfn",
            ),
            view_name="view<a>",
        ),
        diagnostics.EncodingOperationViewValueQualityDiagnostic(
            location=rendering.SourceLocation(
                line=5,
                column=24,
                end_line=5,
                end_column=37,
                file_path="negate/integer.dfn",
            ),
            quality_name="value</number>",
        ),
    ]


def test_associated_encoding_operation_not_defined(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_diagnostics == [
        diagnostics.ReferencedFileNotFoundDiagnostic(
            location=rendering.SourceLocation(
                line=5,
                column=28,
                end_line=5,
                end_column=42,
                file_path=".define/encodings/encoding_operations.defcl",
            ),
            file_path="negate/missing.dfn",
        )
    ]


def test_unexecuted_logical_operation_does_not_load_encoding_operations(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_diagnostics == []


def test_encoding_operation_in_unconfigured_universe(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_diagnostics == [
        diagnostics.ExternalUniverseNotConfiguredDiagnostic(
            location=rendering.SourceLocation(
                line=5,
                column=28,
                end_line=5,
                end_column=48,
                file_path=".define/encodings/encoding_operations.defcl",
            ),
            universe="other.example.com:lib",
            current_universe_name="my.domain.com:my_lib",
        )
    ]
