"""Structural validation of value definitions."""

from __future__ import annotations

from pathlib import PurePosixPath
from typing import TYPE_CHECKING

from define.compiler import ast
from define.compiler.errors import diagnostics
from define.compiler.validator.test_helpers import assert_no_errors

if TYPE_CHECKING:
    from define.compiler.conftest import (
        ValidateTestdataStructural,
        ValidateTestdataStructuralNonFilesystem,
    )


def test_valid_value(validate_testdata_structural: ValidateTestdataStructural):
    result = validate_testdata_structural()
    assert_no_errors(result)
    definitions = result.file_results[0].definition_results
    assert len(definitions) == 1
    assert isinstance(definitions[0].definition, ast.ValueDefinition)
    assert result.entry_action is None


def test_invalid_name(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.InvalidGlobalNamePathCharacterDiagnostic)
    assert diagnostic.location.line == 2
    assert diagnostic.location.column == 53
    assert diagnostic.location.file_path is None
    assert diagnostic.segment == "bad-name"
    assert diagnostic.chars == ("-",)


def test_duplicate_value(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.DuplicateDefinitionDiagnostic)
    assert diagnostic.location.column == 1
    assert diagnostic.location.file_path is None
    assert diagnostic.definition_type == "value"
    assert diagnostic.path == "/number"
    assert diagnostic.first_definition_line == 2
    assert diagnostic.location.line == 8


def test_same_name_different_quality(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert_no_errors(result)
    assert len(result.file_results[0].definition_results) == 2


def test_path_mismatch(validate_testdata_structural: ValidateTestdataStructural):
    result = validate_testdata_structural()
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.PathMismatchDiagnostic)
    assert diagnostic.location.line == 2
    assert diagnostic.location.column == 49
    assert diagnostic.location.file_path == PurePosixPath("test.dfn")
    assert diagnostic.expected_path == "/test"
    assert diagnostic.actual_path == "/number"


def test_fqun_mismatch(validate_testdata_structural: ValidateTestdataStructural):
    result = validate_testdata_structural()
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.FqunMismatchDiagnostic)
    assert diagnostic.location.line == 2
    assert diagnostic.location.column == 28
    assert diagnostic.location.file_path == PurePosixPath("test.dfn")
    assert diagnostic.expected == "my.domain.com:my_lib"
    assert diagnostic.actual == "other.org:my_lib"


def test_logical_operation_support(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert_no_errors(result)


def test_duplicate_logical_operation_support(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert result.all_exceptions == []
    assert result.all_diagnostics == [
        diagnostics.DuplicateLogicalOperationSupportDiagnostic(
            location=ast.SourceLocation(line=6, column=21, end_line=6, end_column=59),
            logical_operation_name="logical_operation<standard:/number/add>",
            first_support_line=3,
        )
    ]


def test_logical_operation_support_out_of_order(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert result.all_exceptions == []
    assert result.all_diagnostics == [
        diagnostics.LogicalOperationSupportOrderDiagnostic(
            location=ast.SourceLocation(line=6, column=21, end_line=6, end_column=60),
            logical_operation_name="logical_operation<standard:/boolean/and>",
            logical_operation_name_it_must_precede=(
                "logical_operation<standard:/text/equality>"
            ),
        ),
        diagnostics.LogicalOperationSupportOrderDiagnostic(
            location=ast.SourceLocation(line=9, column=21, end_line=9, end_column=59),
            logical_operation_name="logical_operation<standard:/number/add>",
            logical_operation_name_it_must_precede=(
                "logical_operation<standard:/text/equality>"
            ),
        ),
    ]


def test_logical_operation_support_order_uses_full_names(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert_no_errors(result)


def test_logical_operation_support_requires_short_form(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert result.all_exceptions == []
    assert result.all_diagnostics == [
        diagnostics.GlobalReferenceMustUseShortFormDiagnostic(
            location=ast.SourceLocation(line=8, column=39, end_line=8, end_column=58),
            fqun="my.domain.com:my_lib",
        )
    ]


def test_wrong_logical_operation_definition_type(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert result.all_exceptions == []
    assert result.all_diagnostics == [
        diagnostics.StandardDefinitionNotFoundDiagnostic(
            location=ast.SourceLocation(line=3, column=39, end_line=3, end_column=67),
            definition_name="logical_operation<standard:/text/unicode/scalar>",
        )
    ]


def test_missing_logical_operation_file(
    validate_testdata_structural: ValidateTestdataStructural,
):
    result = validate_testdata_structural()
    assert result.all_exceptions == []
    assert result.all_diagnostics == [
        diagnostics.ReferencedFileNotFoundDiagnostic(
            location=ast.SourceLocation(
                line=3,
                column=39,
                end_line=3,
                end_column=46,
                file_path=PurePosixPath("test.dfn"),
            ),
            file_path="missing.dfn",
        )
    ]
