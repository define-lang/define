"""Validation of the Encoding Operations that association resolution loads."""

from __future__ import annotations

from typing import TYPE_CHECKING

from crates.source_rendering.python import rendering
from define.compiler.errors import (
    association_resolution_diagnostics,
    reference_graph_diagnostics,
    structural_diagnostics,
)
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


def test_computer_operation_fulfills_directions(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    # TODO: Once a standard Encoding Operation that executes the computer
    # operation has a read/write view, use it here instead of a user's
    # Encoding Operation that executes the computer operation, which the
    # compiler reports.
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.sorted_diagnostics() == [
        association_resolution_diagnostics.UnknownComputerOperationDiagnostic(
            location=rendering.SourceLocation(
                line=24, column=9, end_line=24, end_column=39
            ),
            encoding_operation_name="encoding_operation<my.domain.com:my_lib:/update>",
        ),
    ]


def test_unread_input_view(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert len(result.sorted_diagnostics()) == 1
    diagnostic = result.sorted_diagnostics()[0]
    assert isinstance(diagnostic, reference_graph_diagnostics.UnreadInputViewDiagnostic)
    assert diagnostic.location.file_path is None
    assert diagnostic.location.line == 24
    assert diagnostic.location.column == 16
    assert diagnostic.view_name == "view<number>"


def test_unwritten_output_view(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.sorted_diagnostics() == [
        reference_graph_diagnostics.UnwrittenOutputViewDiagnostic(
            location=rendering.SourceLocation(
                line=3, column=16, end_line=3, end_column=27
            ),
            view_name="view<number>",
        ),
    ]


def test_executes_read_write_operation_with_input_only_view(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.sorted_diagnostics() == [
        reference_graph_diagnostics.ExecutedOperationHasReadWriteViewDiagnostic(
            location=rendering.SourceLocation(
                line=40, column=21, end_line=40, end_column=53
            ),
            operation_name="encoding_operation</increment_by>",
            view_name="view<total>",
        ),
    ]


def test_executes_read_write_operation_with_output_only_view(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.sorted_diagnostics() == [
        reference_graph_diagnostics.ExecutedOperationHasReadWriteViewDiagnostic(
            location=rendering.SourceLocation(
                line=40, column=21, end_line=40, end_column=53
            ),
            operation_name="encoding_operation</increment_by>",
            view_name="view<total>",
        ),
    ]


def test_out_of_order(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert len(result.sorted_diagnostics()) == 1
    diagnostic = result.sorted_diagnostics()[0]
    assert isinstance(
        diagnostic, reference_graph_diagnostics.OperationArgumentOrderDiagnostic
    )
    assert diagnostic.location.file_path is None
    assert diagnostic.location.line == 40
    assert diagnostic.location.column == 18
    assert diagnostic.view_name == "view<source>"
    assert diagnostic.operation_name == "encoding_operation</copy>"
    assert diagnostic.expected_order == ["view<source>", "view<target>"]


def test_missing_argument(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert len(result.sorted_diagnostics()) == 1
    diagnostic = result.sorted_diagnostics()[0]
    assert isinstance(
        diagnostic, reference_graph_diagnostics.MissingOperationArgumentDiagnostic
    )
    assert diagnostic.location.file_path is None
    assert diagnostic.location.line == 32
    assert diagnostic.location.column == 21
    assert diagnostic.view_name == "view<target>"
    assert diagnostic.operation_name == "encoding_operation</copy>"


def test_missing_encoding(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert len(result.sorted_diagnostics()) == 1
    diagnostic = result.sorted_diagnostics()[0]
    assert isinstance(
        diagnostic,
        reference_graph_diagnostics.OperationArgumentMissingQualitiesDiagnostic,
    )
    assert diagnostic.location.file_path is None
    assert diagnostic.location.line == 41
    assert diagnostic.location.column == 42
    assert diagnostic.view_name == "view<source>"
    assert diagnostic.looked_at_name == "view<number>"
    assert diagnostic.looked_at_kind == reference_graph_diagnostics.LookedAtKind.VIEW
    assert diagnostic.missing_qualities == ["encoding</text>"]


def test_literal_in_decimal_ascii_encoding(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    # TODO: Once a standard Encoding Operation has views with the decimal
    # encoding, use it here instead of a user's Encoding Operation that
    # executes the computer operation, which the compiler reports.
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.sorted_diagnostics() == [
        association_resolution_diagnostics.UnknownComputerOperationDiagnostic(
            location=rendering.SourceLocation(
                line=17, column=9, end_line=17, end_column=39
            ),
            encoding_operation_name="encoding_operation<my.domain.com:my_lib:/copy>",
        ),
    ]


def test_literal_without_literal_parser(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    unknown_computer_operation, diagnostic = result.sorted_diagnostics()
    assert unknown_computer_operation == (
        association_resolution_diagnostics.UnknownComputerOperationDiagnostic(
            location=rendering.SourceLocation(
                line=18, column=9, end_line=18, end_column=39
            ),
            encoding_operation_name="encoding_operation<my.domain.com:my_lib:/copy>",
        )
    )
    assert isinstance(
        diagnostic,
        association_resolution_diagnostics.LiteralCannotBeConvertedDiagnostic,
    )
    assert diagnostic.location.file_path is None
    assert diagnostic.location.line == 31
    assert diagnostic.location.column == 42
    assert diagnostic.potential_literal == "literal<standard:/number>"
    assert diagnostic.literal_encoding == "encoding<standard:/number/decimal/ascii>"
    assert diagnostic.encoding == "encoding</text>"
    assert diagnostic.supported_encodings == []


def test_invalid_literal_content(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert len(result.sorted_diagnostics()) == 1
    diagnostic = result.sorted_diagnostics()[0]
    assert isinstance(
        diagnostic, association_resolution_diagnostics.InvalidLiteralContentDiagnostic
    )
    assert diagnostic.location.file_path is None
    assert diagnostic.location.line == 33
    assert diagnostic.location.column == 68
    assert diagnostic.content == "abc"
    assert diagnostic.potential_literal == "literal<standard:/number>"
    assert diagnostic.value_encoding == "encoding<standard:/number/integer/ascii>"
    assert diagnostic.reason == "'a' is not allowed in a number"


def test_output_view_looks_at_literal(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert len(result.sorted_diagnostics()) == 1
    diagnostic = result.sorted_diagnostics()[0]
    assert isinstance(
        diagnostic, reference_graph_diagnostics.OutputViewLooksAtLiteralDiagnostic
    )
    assert diagnostic.location.file_path is None
    assert diagnostic.location.line == 34
    assert diagnostic.location.column == 42
    assert diagnostic.view_name == "view<target>"
    assert diagnostic.operation_name == "encoding_operation</copy>"


def test_literal_in_every_view_encoding(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert len(result.sorted_diagnostics()) == 1
    diagnostic = result.sorted_diagnostics()[0]
    assert isinstance(
        diagnostic,
        association_resolution_diagnostics.LiteralCannotBeConvertedDiagnostic,
    )
    assert diagnostic.location.file_path is None
    assert diagnostic.location.line == 35
    assert diagnostic.location.column == 42
    assert diagnostic.potential_literal == "literal<standard:/number>"
    assert diagnostic.literal_encoding == "encoding<standard:/number/decimal/ascii>"
    assert diagnostic.encoding == "encoding</text>"
    assert diagnostic.supported_encodings == []


def test_missing_potential_literal(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_validation
    assert len(result.sorted_diagnostics()) == 1
    diagnostic = result.sorted_diagnostics()[0]
    assert isinstance(
        diagnostic, structural_diagnostics.ReferencedFileNotFoundDiagnostic
    )
    assert diagnostic.location.file_path == "test.dfn"
    assert diagnostic.file_path == "missing.dfn"
    assert diagnostic.location.line == 12
    assert diagnostic.location.column == 50


def test_literal_for_view_with_value_quality(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert len(result.sorted_diagnostics()) == 1
    diagnostic = result.sorted_diagnostics()[0]
    assert isinstance(
        diagnostic, structural_diagnostics.EncodingOperationViewValueQualityDiagnostic
    )
    assert diagnostic.location.file_path is None
    assert diagnostic.location.line == 6
    assert diagnostic.location.column == 24
    assert diagnostic.quality_name == "value<standard:/number/natural>"


def test_local_view(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert_no_errors(result)


def test_local_view_read_before_write(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.sorted_diagnostics() == [
        reference_graph_diagnostics.ReadFromUnwrittenLocalViewDiagnostic(
            location=rendering.SourceLocation(
                line=35, column=37, end_line=35, end_column=49
            ),
            looked_at_name="view<smaller>",
            view_name="view<a>",
            operation_name="encoding_operation<standard:/number/natural/ascii/minimum>",
        ),
    ]


def test_view_setting(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert_no_errors(result)


def test_view_setting_read_write_target(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert_no_errors(result)


def test_executes_read_write_operation(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.sorted_diagnostics() == [
        reference_graph_diagnostics.ExecutedOperationHasReadWriteViewDiagnostic(
            location=rendering.SourceLocation(
                line=35, column=21, end_line=35, end_column=50
            ),
            operation_name="encoding_operation</increment>",
            view_name="view<value>",
        ),
    ]
