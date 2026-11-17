"""Association resolution of a logical operation's associations with Encoding Operations, and checks of the Encoding Operations that resolution chooses through them."""

from __future__ import annotations

from typing import TYPE_CHECKING

from crates.source_rendering.python import rendering
from define.compiler.errors import diagnostics
from define.compiler.validator.test_helpers import standard_library_file

if TYPE_CHECKING:
    from define.compiler.test_fixtures.validation_pipeline import (
        ValidateTestdataProjectWithReferenceGraph,
    )

pytest_plugins = ["define.compiler.test_fixtures.validation_pipeline"]


def test_encoding_operation_with_fewer_views(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_validation.all_diagnostics == [
        diagnostics.AssociationLogicalOperationViewCountDiagnostic(
            location=rendering.SourceLocation(
                line=6,
                column=16,
                end_line=6,
                end_column=49,
                file_path=".define/encodings/encoding_operations.defcl",
            ),
            encoding_operation_name="encoding_operation<standard:/number/integer/ascii/add>",
            view_count=3,
            logical_operation_name="logical_operation<my.domain.com:my_lib:/negate>",
            logical_operation_view_count=2,
            definition_location=rendering.SourceLocation(
                line=1, column=12, end_line=1, end_column=58, file_path="negate.dfn"
            ),
        )
    ]


def test_encoding_operation_with_different_view_name(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_validation.all_diagnostics == [
        diagnostics.AssociationLogicalOperationViewNameDiagnostic(
            location=rendering.SourceLocation(
                line=9,
                column=19,
                end_line=9,
                end_column=21,
                file_path=".define/encodings/encoding_operations.defcl",
            ),
            view_number=1,
            view_name="a",
            encoding_operation_name="encoding_operation<standard:/number/integer/ascii/negate>",
            logical_operation_name="logical_operation<my.domain.com:my_lib:/negate>",
            logical_operation_view_name="value",
            definition_location=rendering.SourceLocation(
                line=2, column=16, end_line=2, end_column=26, file_path="negate.dfn"
            ),
        )
    ]


def test_encoding_operation_with_different_view_direction(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_validation.all_diagnostics == [
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
                line=6,
                column=16,
                end_line=6,
                end_column=52,
                file_path=".define/encodings/encoding_operations.defcl",
            ),
        )
    ]


def test_encoding_operation_with_views_in_different_order(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_validation.all_diagnostics == [
        diagnostics.AssociationLogicalOperationViewNameDiagnostic(
            location=rendering.SourceLocation(
                line=9,
                column=19,
                end_line=9,
                end_column=21,
                file_path=".define/encodings/encoding_operations.defcl",
            ),
            view_number=1,
            view_name="a",
            encoding_operation_name="encoding_operation<standard:/number/integer/ascii/negate>",
            logical_operation_name="logical_operation<my.domain.com:my_lib:/negate>",
            logical_operation_view_name="result",
            definition_location=rendering.SourceLocation(
                line=2, column=16, end_line=2, end_column=27, file_path="negate.dfn"
            ),
        ),
        diagnostics.AssociationLogicalOperationViewNameDiagnostic(
            location=rendering.SourceLocation(
                line=13,
                column=19,
                end_line=13,
                end_column=26,
                file_path=".define/encodings/encoding_operations.defcl",
            ),
            view_number=2,
            view_name="result",
            encoding_operation_name="encoding_operation<standard:/number/integer/ascii/negate>",
            logical_operation_name="logical_operation<my.domain.com:my_lib:/negate>",
            logical_operation_view_name="a",
            definition_location=rendering.SourceLocation(
                line=5, column=16, end_line=5, end_column=22, file_path="negate.dfn"
            ),
        ),
    ]


def test_encoding_operations_with_same_encodings(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_validation.all_diagnostics == [
        diagnostics.DuplicateAssociatedEncodingOperationDiagnostic(
            location=rendering.SourceLocation(
                line=26,
                column=16,
                end_line=26,
                end_column=54,
                file_path=".define/encodings/encoding_operations.defcl",
            ),
            encoding_operation_name="encoding_operation<standard:/number/integer/ascii/multiply>",
            first_encoding_operation_name="encoding_operation<standard:/number/integer/ascii/add>",
            logical_operation_name="logical_operation<my.domain.com:my_lib:/combine>",
            first_association_location=rendering.SourceLocation(
                line=6,
                column=16,
                end_line=6,
                end_column=49,
                file_path=".define/encodings/encoding_operations.defcl",
            ),
        )
    ]


def test_encoding_operation_with_read_write_view(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_validation.all_diagnostics == [
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
                line=6,
                column=16,
                end_line=6,
                end_column=30,
                file_path=".define/encodings/encoding_operations.defcl",
            ),
        )
    ]


def test_encoding_operation_view_without_encoding(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_validation.all_diagnostics == [
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
    assert result.program_validation.all_diagnostics == [
        diagnostics.ReferencedFileNotFoundDiagnostic(
            location=rendering.SourceLocation(
                line=6,
                column=16,
                end_line=6,
                end_column=30,
                file_path=".define/encodings/encoding_operations.defcl",
            ),
            file_path="negate/missing.dfn",
        )
    ]


def test_unexecuted_logical_operation_does_not_load_encoding_operations(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_validation.all_diagnostics == []


def test_encoding_operation_in_unconfigured_universe(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_validation.all_diagnostics == [
        diagnostics.ExternalUniverseNotConfiguredDiagnostic(
            location=rendering.SourceLocation(
                line=6,
                column=16,
                end_line=6,
                end_column=36,
                file_path=".define/encodings/encoding_operations.defcl",
            ),
            universe="other.example.com:lib",
            current_universe_name="my.domain.com:my_lib",
        )
    ]


def test_association_with_fewer_views(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_validation.all_diagnostics == [
        diagnostics.AssociationLogicalOperationViewCountDiagnostic(
            location=rendering.SourceLocation(
                line=6,
                column=16,
                end_line=6,
                end_column=49,
                file_path=".define/encodings/encoding_operations.defcl",
            ),
            encoding_operation_name="encoding_operation<standard:/number/integer/ascii/add>",
            view_count=2,
            logical_operation_name="logical_operation<my.domain.com:my_lib:/combine>",
            logical_operation_view_count=3,
            definition_location=rendering.SourceLocation(
                line=1, column=12, end_line=1, end_column=59, file_path="combine.dfn"
            ),
        )
    ]


def test_association_with_different_view_name(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_validation.all_diagnostics == [
        diagnostics.AssociationLogicalOperationViewNameDiagnostic(
            location=rendering.SourceLocation(
                line=13,
                column=19,
                end_line=13,
                end_column=21,
                file_path=".define/encodings/encoding_operations.defcl",
            ),
            view_number=2,
            view_name="c",
            encoding_operation_name="encoding_operation<standard:/number/integer/ascii/add>",
            logical_operation_name="logical_operation<my.domain.com:my_lib:/combine>",
            logical_operation_view_name="b",
            definition_location=rendering.SourceLocation(
                line=5, column=16, end_line=5, end_column=22, file_path="combine.dfn"
            ),
        )
    ]


def test_association_with_different_encoding(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_validation.all_diagnostics == [
        diagnostics.AssociationViewEncodingDiagnostic(
            location=rendering.SourceLocation(
                line=14,
                column=24,
                end_line=14,
                end_column=53,
                file_path=".define/encodings/encoding_operations.defcl",
            ),
            view_name="view<b>",
            encoding_name="encoding<standard:/number/natural/ascii>",
            encoding_operation_name="encoding_operation<standard:/number/integer/ascii/add>",
            encoding_operation_encoding_name="encoding<standard:/number/integer/ascii>",
            definition_location=rendering.SourceLocation(
                line=11,
                column=24,
                end_line=11,
                end_column=54,
                file_path=standard_library_file("number/integer/ascii/add.dfn"),
            ),
        )
    ]


def test_encoding_operation_with_fewer_views_than_its_association(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_validation.all_diagnostics == [
        diagnostics.AssociationViewCountDiagnostic(
            location=rendering.SourceLocation(
                line=6,
                column=16,
                end_line=6,
                end_column=31,
                file_path=".define/encodings/encoding_operations.defcl",
            ),
            encoding_operation_name="encoding_operation<my.domain.com:my_lib:/combine/integer>",
            view_count=3,
            encoding_operation_view_count=2,
            definition_location=rendering.SourceLocation(
                line=1,
                column=12,
                end_line=1,
                end_column=68,
                file_path="combine/integer.dfn",
            ),
        )
    ]


def test_encoding_operation_with_different_view_name_than_its_association(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_validation.all_diagnostics == [
        diagnostics.AssociationViewNameDiagnostic(
            location=rendering.SourceLocation(
                line=13,
                column=19,
                end_line=13,
                end_column=21,
                file_path=".define/encodings/encoding_operations.defcl",
            ),
            view_number=2,
            view_name="b",
            encoding_operation_name="encoding_operation<my.domain.com:my_lib:/combine/integer>",
            encoding_operation_view_name="c",
            definition_location=rendering.SourceLocation(
                line=8,
                column=16,
                end_line=8,
                end_column=22,
                file_path="combine/integer.dfn",
            ),
        )
    ]


def test_unusable_encoding_operations_config(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_validation.all_diagnostics == [
        diagnostics.EncodingOperationsConfigNotFoundDiagnostic(
            location=rendering.SourceLocation(
                line=5,
                column=30,
                end_line=5,
                end_column=33,
                file_path=".define/project/config.defcl",
            ),
            encoding_operations_config_path=".define/encodings/encoding_operations.defcl",
        )
    ]
