"""Reference graph validation of local views."""

from __future__ import annotations

from typing import TYPE_CHECKING

from define.compiler import ast
from define.compiler.errors import diagnostics
from define.compiler.validator.test_helpers import assert_no_errors

if TYPE_CHECKING:
    from define.compiler.conftest import (
        ValidateTestdataNonFilesystemWithReferenceGraph,
    )


def test_valid_logical_operation_execution(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert_no_errors(result)


def test_valid_operation_execution(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert_no_errors(result)


def test_read_before_write(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.all_exceptions == []
    assert result.all_diagnostics == [
        diagnostics.ReadFromUnwrittenLocalViewDiagnostic(
            location=ast.SourceLocation(line=63, column=41, end_line=63, end_column=53),
            looked_at_name="view<negated>",
            view_name="view<value>",
            operation_name="logical_operation</negate>",
        )
    ]


def test_written_twice(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.all_exceptions == []
    assert result.all_diagnostics == [
        diagnostics.LocalViewWrittenTwiceDiagnostic(
            location=ast.SourceLocation(line=68, column=42, end_line=68, end_column=54),
            looked_at_name="view<negated>",
            view_name="view<result>",
            operation_name="logical_operation</negate>",
            first_write=ast.SourceLocation(
                line=64, column=42, end_line=64, end_column=54
            ),
        )
    ]


def test_unread(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.all_exceptions == []
    assert result.all_diagnostics == [
        diagnostics.UnreadLocalViewDiagnostic(
            location=ast.SourceLocation(line=57, column=20, end_line=57, end_column=32),
            view_name="view<negated>",
        )
    ]


def test_write_not_supported(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.all_exceptions == []
    assert result.all_diagnostics == [
        diagnostics.LogicalOperationWriteNotSupportedDiagnostic(
            location=ast.SourceLocation(line=64, column=42, end_line=64, end_column=54),
            looked_at_name="view<negated>",
            logical_operation_name="logical_operation</negate>",
            value_name="value</read_only_number>",
        )
    ]


def test_value_quality_mismatch(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.all_exceptions == []
    assert result.all_diagnostics == [
        diagnostics.LogicalOperationWriteNotSupportedDiagnostic(
            location=ast.SourceLocation(line=64, column=42, end_line=64, end_column=54),
            looked_at_name="view<negated>",
            logical_operation_name="logical_operation</negate>",
            value_name="value</read_only_number>",
        ),
        diagnostics.OperationArgumentMissingQualitiesDiagnostic(
            location=ast.SourceLocation(line=67, column=41, end_line=67, end_column=53),
            view_name="view<value>",
            looked_at_name="view<negated>",
            looked_at_kind=diagnostics.LookedAtKind.VIEW,
            missing_qualities=["value</number>"],
        ),
    ]


def test_written_by_missing_logical_operation(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.all_exceptions == []
    assert result.all_diagnostics == [
        diagnostics.StandardDefinitionNotFoundDiagnostic(
            location=ast.SourceLocation(line=62, column=21, end_line=62, end_column=63),
            definition_name="logical_operation<standard:/number/missing>",
        )
    ]


def test_duplicate_name(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.all_exceptions == []
    assert result.all_diagnostics == [
        diagnostics.LocalNameConflictDiagnostic(
            location=ast.SourceLocation(line=62, column=20, end_line=62, end_column=32),
            local_name="negated",
            first_definition_line=57,
        )
    ]


def test_unreferenced(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.all_exceptions == []
    assert result.all_diagnostics == [
        diagnostics.UnreferencedLocalViewDiagnostic(
            location=ast.SourceLocation(line=62, column=20, end_line=62, end_column=31),
            view_name="view<unused>",
        )
    ]


def test_encoding_operation_with_local_view(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert_no_errors(result)


def test_missing_logical_operation_looks_at_undefined_view(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.all_exceptions == []
    assert result.all_diagnostics == [
        diagnostics.StandardDefinitionNotFoundDiagnostic(
            location=ast.SourceLocation(line=57, column=21, end_line=57, end_column=63),
            definition_name="logical_operation<standard:/number/missing>",
        ),
        diagnostics.UndefinedLocalNameDiagnostic(
            location=ast.SourceLocation(line=59, column=42, end_line=59, end_column=56),
            local_name="view<undefined>",
        ),
    ]


def test_written_twice_after_unknown_use(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.all_exceptions == []
    assert result.all_diagnostics == [
        diagnostics.NoProjectRootForDefinitionNotInSuppliedSourceDiagnostic(
            location=ast.SourceLocation(line=66, column=21, end_line=66, end_column=47),
            definition_name="logical_operation</missing>",
            config_path=".define/project/config.defcl",
        ),
        diagnostics.LocalViewWrittenTwiceDiagnostic(
            location=ast.SourceLocation(line=71, column=42, end_line=71, end_column=54),
            looked_at_name="view<negated>",
            view_name="view<result>",
            operation_name="logical_operation</negate>",
            first_write=ast.SourceLocation(
                line=64, column=42, end_line=64, end_column=54
            ),
        ),
    ]


def test_passed_to_read_write_view_after_write(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.all_exceptions == []
    assert result.all_diagnostics == [
        diagnostics.LocalViewPassedToReadWriteViewDiagnostic(
            location=ast.SourceLocation(line=75, column=41, end_line=75, end_column=53),
            looked_at_name="view<negated>",
            view_name="view<value>",
            operation_name="operation</negate_in_place>",
        ),
    ]


def test_passed_to_read_write_view_before_write(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.all_exceptions == []
    assert result.all_diagnostics == [
        diagnostics.LocalViewPassedToReadWriteViewDiagnostic(
            location=ast.SourceLocation(line=65, column=41, end_line=65, end_column=55),
            looked_at_name="view<unwritten>",
            view_name="view<value>",
            operation_name="operation</negate_in_place>",
        ),
    ]
