"""Reference graph validation of Encoding Operations."""

from __future__ import annotations

from pathlib import PurePosixPath
from typing import TYPE_CHECKING

from define.compiler import ast, name_types
from define.compiler.errors import diagnostics
from define.compiler.validator.test_helpers import assert_no_errors

if TYPE_CHECKING:
    from define.compiler.conftest import (
        ValidateTestdataNonFilesystemWithReferenceGraph,
        ValidateTestdataProjectWithReferenceGraph,
    )


def test_valid_composition(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert_no_errors(result)


def test_computer_operation_fulfills_directions(
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
    assert diagnostic.operation_name_type == name_types.NameType.ENCODING_OPERATION


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
    assert diagnostic.operation_name_type == name_types.NameType.ENCODING_OPERATION


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
    assert diagnostic.operation_name == "encoding_operation</increment_by>"


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
    assert diagnostic.operation_name == "encoding_operation</increment_by>"


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
    assert diagnostic.operation_name == "encoding_operation</copy>"
    assert diagnostic.expected_order == ["view<source>", "view<target>"]


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
    assert diagnostic.operation_name == "encoding_operation</copy>"


def test_missing_encoding(
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
    assert diagnostic.location.line == 38
    assert diagnostic.location.column == 42
    assert diagnostic.view_name == "view<source>"
    assert diagnostic.looked_at_name == "view<number>"
    assert diagnostic.looked_at_kind == diagnostics.LookedAtKind.VIEW
    assert diagnostic.missing_qualities == ["encoding</text>"]


def test_literal_in_decimal_ascii_encoding(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert_no_errors(result)


def test_literal_without_literal_parser(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.LiteralCannotBeConvertedDiagnostic)
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
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.InvalidLiteralContentDiagnostic)
    assert diagnostic.location.file_path is None
    assert diagnostic.location.line == 30
    assert diagnostic.location.column == 68
    assert diagnostic.content == "abc"
    assert diagnostic.potential_literal == "literal<standard:/number>"
    assert diagnostic.value_encoding == "encoding<standard:/number/decimal/ascii>"
    assert diagnostic.reason == "'a' is not allowed in a number"


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
    assert diagnostic.operation_name == "encoding_operation</copy>"


def test_statement_after_computer_operation(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert_no_errors(result)


def test_literal_in_every_view_encoding(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.LiteralCannotBeConvertedDiagnostic)
    assert diagnostic.location.file_path is None
    assert diagnostic.location.line == 32
    assert diagnostic.location.column == 42
    assert diagnostic.potential_literal == "literal<standard:/number>"
    assert diagnostic.literal_encoding == "encoding<standard:/number/decimal/ascii>"
    assert diagnostic.encoding == "encoding</text>"
    assert diagnostic.supported_encodings == []


def test_missing_potential_literal(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_result
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.ReferencedFileNotFoundDiagnostic)
    assert diagnostic.location.file_path == PurePosixPath("test.dfn")
    assert diagnostic.file_path == "missing.dfn"
    assert diagnostic.location.line == 12
    assert diagnostic.location.column == 50


def test_literal_for_view_with_value_quality(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(
        diagnostic, diagnostics.EncodingOperationViewValueQualityDiagnostic
    )
    assert diagnostic.location.file_path is None
    assert diagnostic.location.line == 6
    assert diagnostic.location.column == 24
    assert diagnostic.quality_name == "value<standard:/number/natural>"


def test_written_after_computer_operation(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.all_exceptions == []
    assert result.all_diagnostics == [
        diagnostics.InterfaceViewWrittenTwiceDiagnostic(
            location=ast.SourceLocation(line=63, column=42, end_line=63, end_column=53),
            looked_at_name="view<result>",
            view_name="view<target>",
            operation_name="encoding_operation</copy>",
            first_write=ast.SourceLocation(
                line=60, column=9, end_line=60, end_column=39
            ),
        )
    ]


def test_computer_operation_after_write(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.all_exceptions == []
    assert result.all_diagnostics == [
        diagnostics.InterfaceViewWrittenTwiceByAllViewsStatementDiagnostic(
            location=ast.SourceLocation(line=64, column=9, end_line=64, end_column=39),
            view_name="view<result>",
            operation_name_type=name_types.NameType.ENCODING_OPERATION,
            first_write=ast.SourceLocation(
                line=62, column=42, end_line=62, end_column=53
            ),
        )
    ]


def test_read_after_computer_operation_writes_read_write_view(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.all_exceptions == []
    assert result.all_diagnostics == [
        diagnostics.ReadFromWrittenReadWriteViewDiagnostic(
            location=ast.SourceLocation(line=57, column=41, end_line=57, end_column=51),
            looked_at_name="view<count>",
            view_name="view<value>",
            operation_name="encoding_operation</inspect>",
            write=ast.SourceLocation(line=55, column=9, end_line=55, end_column=39),
        )
    ]


def test_computer_operation_after_unknown_use(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.all_exceptions == []
    assert result.all_diagnostics == [
        diagnostics.NoProjectRootForDefinitionNotInSuppliedSourceDiagnostic(
            location=ast.SourceLocation(line=64, column=21, end_line=64, end_column=48),
            definition_name="encoding_operation</missing>",
            config_path=".define/project/config.defcl",
        ),
        diagnostics.InterfaceViewWrittenTwiceByAllViewsStatementDiagnostic(
            location=ast.SourceLocation(line=67, column=9, end_line=67, end_column=39),
            view_name="view<result>",
            operation_name_type=name_types.NameType.ENCODING_OPERATION,
            first_write=ast.SourceLocation(
                line=62, column=42, end_line=62, end_column=53
            ),
        ),
    ]
