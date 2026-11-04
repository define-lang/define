"""Structural validation of Local View Definitions.

Follow program validator test authoring rules in program_validator_tests/AGENTS.md.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from define.compiler import ast
from define.compiler.errors import diagnostics
from define.compiler.validator.test_helpers import assert_no_errors

if TYPE_CHECKING:
    from define.compiler.conftest import ValidateTestdataStructuralNonFilesystem


def test_valid_local_view(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert_no_errors(result)


def test_missing_value_quality(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert result.all_exceptions == []
    assert result.all_diagnostics == [
        diagnostics.LocalViewMissingValueQualityDiagnostic(
            location=ast.SourceLocation(line=25, column=25, end_line=25, end_column=31),
            view_name="view<negated>",
        ),
        diagnostics.LocalViewNonValueQualityDiagnostic(
            location=ast.SourceLocation(line=27, column=28, end_line=27, end_column=61),
            quality_name="position<standard:/number/integer>",
        ),
    ]


def test_encoding(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert result.all_exceptions == []
    assert result.all_diagnostics == [
        diagnostics.LocalViewNonValueQualityDiagnostic(
            location=ast.SourceLocation(line=28, column=28, end_line=28, end_column=67),
            quality_name="encoding<standard:/number/decimal/ascii>",
        )
    ]


def test_multiple_value_qualities(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert result.all_exceptions == []
    assert result.all_diagnostics == [
        diagnostics.ViewMultipleValueQualitiesDiagnostic(
            location=ast.SourceLocation(line=28, column=28, end_line=28, end_column=58),
            first_value_name="value<standard:/number/integer>",
            first_assignment_line=27,
        )
    ]


def test_invalid_view_name(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert result.all_exceptions == []
    assert result.all_diagnostics == [
        diagnostics.InvalidLocalNameFormatDiagnostic(
            location=ast.SourceLocation(line=25, column=25, end_line=25, end_column=25),
            local_name="Negated",
            chars=("N",),
        ),
        diagnostics.UnreferencedLocalViewDiagnostic(
            location=ast.SourceLocation(line=25, column=25, end_line=25, end_column=31),
            view_name="view<Negated>",
        ),
    ]


def test_conflicts_with_interface_view(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert result.all_exceptions == []
    assert result.all_diagnostics == [
        diagnostics.LocalNameConflictDiagnostic(
            location=ast.SourceLocation(line=25, column=25, end_line=25, end_column=30),
            local_name="number",
            first_definition_line=11,
        )
    ]


def test_duplicate_local_view(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert result.all_exceptions == []
    assert result.all_diagnostics == [
        diagnostics.LocalNameConflictDiagnostic(
            location=ast.SourceLocation(line=30, column=25, end_line=30, end_column=31),
            local_name="negated",
            first_definition_line=25,
        )
    ]


def test_unreferenced_local_view(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert result.all_exceptions == []
    assert result.all_diagnostics == [
        diagnostics.UnreferencedLocalViewDiagnostic(
            location=ast.SourceLocation(line=30, column=25, end_line=30, end_column=30),
            view_name="view<unused>",
        )
    ]


def test_referenced_before_definition(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert result.all_exceptions == []
    assert result.all_diagnostics == [
        diagnostics.UndefinedLocalNameDiagnostic(
            location=ast.SourceLocation(line=27, column=42, end_line=27, end_column=54),
            local_name="view<negated>",
        )
    ]
