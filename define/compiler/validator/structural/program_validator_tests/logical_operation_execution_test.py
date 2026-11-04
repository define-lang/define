"""Structural validation of Logical Operation Execution Statements.

Follow program validator test authoring rules in program_validator_tests/AGENTS.md.
"""

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


def test_valid_execution(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert_no_errors(result)


def test_looks_at_undefined_view(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert result.all_exceptions == []
    assert result.all_diagnostics == [
        diagnostics.UndefinedLocalNameDiagnostic(
            location=ast.SourceLocation(line=21, column=42, end_line=21, end_column=54),
            local_name="view<missing>",
        )
    ]


def test_aliased_views(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert result.all_exceptions == []
    assert result.all_diagnostics == [
        diagnostics.AliasedViewDiagnostic(
            location=ast.SourceLocation(line=21, column=42, end_line=21, end_column=53),
            looked_at_name="view<number>",
            first_argument_line=20,
        )
    ]


def test_duplicate_argument(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert result.all_exceptions == []
    assert result.all_diagnostics == [
        diagnostics.DuplicateOperationArgumentDiagnostic(
            location=ast.SourceLocation(line=27, column=18, end_line=27, end_column=28),
            view_name="view<value>",
            first_argument_line=26,
        )
    ]


def test_invalid_argument_view_name(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert result.all_exceptions == []
    assert result.all_diagnostics == [
        diagnostics.InvalidLocalNameFormatDiagnostic(
            location=ast.SourceLocation(line=26, column=23, end_line=26, end_column=23),
            local_name="Value",
            chars=("V",),
        )
    ]


def test_invalid_logical_operation_name(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert result.all_exceptions == []
    assert result.all_diagnostics == [
        diagnostics.InvalidGlobalNamePathCharacterDiagnostic(
            location=ast.SourceLocation(line=25, column=43, end_line=25, end_column=43),
            segment="bad-name",
            chars=("-",),
        )
    ]


def test_requires_short_logical_operation_name(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert result.all_exceptions == []
    assert result.all_diagnostics == [
        diagnostics.GlobalReferenceMustUseShortFormDiagnostic(
            location=ast.SourceLocation(line=25, column=39, end_line=25, end_column=58),
            fqun="my.domain.com:my_lib",
        )
    ]


def test_logical_operation_in_other_file(
    validate_testdata_structural: ValidateTestdataStructural,
):
    result = validate_testdata_structural()
    assert_no_errors(result)


def test_missing_logical_operation_file(
    validate_testdata_structural: ValidateTestdataStructural,
):
    result = validate_testdata_structural()
    assert result.all_exceptions == []
    assert result.all_diagnostics == [
        diagnostics.ReferencedFileNotFoundDiagnostic(
            location=ast.SourceLocation(
                line=17,
                column=39,
                end_line=17,
                end_column=45,
                file_path=PurePosixPath("test.dfn"),
            ),
            file_path="negate.dfn",
        )
    ]


def test_wrong_logical_operation_definition_type(
    validate_testdata_structural: ValidateTestdataStructural,
):
    result = validate_testdata_structural()
    assert result.all_exceptions == []
    assert result.all_diagnostics == [
        diagnostics.ReferencedDefinitionNotFoundDiagnostic(
            location=ast.SourceLocation(
                line=17,
                column=21,
                end_line=17,
                end_column=46,
                file_path=PurePosixPath("test.dfn"),
            ),
            file_path="negate.dfn",
            definition_name="logical_operation<my.domain.com:my_lib:/negate>",
        )
    ]
