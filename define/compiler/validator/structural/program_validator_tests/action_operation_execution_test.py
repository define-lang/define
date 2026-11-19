"""Structural validation of Operation Execution Statements within actions.

Follow program validator test authoring rules in program_validator_tests/AGENTS.md.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from crates.source_rendering.python import rendering
from define.compiler.errors import structural_diagnostics
from define.compiler.validator.test_helpers import assert_no_errors

if TYPE_CHECKING:
    from define.compiler.test_fixtures.structural_validation import (
        ValidateTestdataStructuralNonFilesystem,
    )

pytest_plugins = ["define.compiler.test_fixtures.structural_validation"]


def test_valid_arguments(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert_no_errors(result)


def test_aliased_positions(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert result.sorted_diagnostics() == [
        structural_diagnostics.AliasedViewDiagnostic(
            location=rendering.SourceLocation(
                line=31, column=42, end_line=31, end_column=57, file_path=None
            ),
            looked_at_name="position<number>",
            first_argument_line=30,
        )
    ]


def test_aliased_chained_positions(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert result.sorted_diagnostics() == [
        structural_diagnostics.AliasedViewDiagnostic(
            location=rendering.SourceLocation(
                line=32, column=42, end_line=32, end_column=75, file_path=None
            ),
            looked_at_name="position<number>::position</child>",
            first_argument_line=31,
        )
    ]


def test_same_position_in_separate_executions(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert_no_errors(result)


def test_parent_and_child_positions(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert_no_errors(result)


def test_undefined_positions(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert result.sorted_diagnostics() == [
        structural_diagnostics.UndefinedLocalNameDiagnostic(
            location=rendering.SourceLocation(
                line=29, column=42, end_line=29, end_column=58, file_path=None
            ),
            local_name="position<missing>",
        ),
        structural_diagnostics.UndefinedLocalNameDiagnostic(
            location=rendering.SourceLocation(
                line=30, column=42, end_line=30, end_column=58, file_path=None
            ),
            local_name="position<missing>",
        ),
    ]


def test_invalid_argument_view_name(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert result.sorted_diagnostics() == [
        structural_diagnostics.InvalidLocalNameFormatDiagnostic(
            location=rendering.SourceLocation(
                line=31, column=23, end_line=31, end_column=23, file_path=None
            ),
            chars=("S",),
            local_name="Source",
        )
    ]


def test_duplicate_argument(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert result.sorted_diagnostics() == [
        structural_diagnostics.DuplicateOperationArgumentDiagnostic(
            location=rendering.SourceLocation(
                line=32, column=18, end_line=32, end_column=29, file_path=None
            ),
            view_name="view<source>",
            first_argument_line=31,
        )
    ]


def test_invalid_literal_name(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert result.sorted_diagnostics() == [
        structural_diagnostics.InvalidGlobalNamePathCharacterDiagnostic(
            location=rendering.SourceLocation(
                line=31, column=63, end_line=31, end_column=63, file_path=None
            ),
            chars=("-",),
            segment="bad-name",
        )
    ]


def test_invalid_operation_name(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert result.sorted_diagnostics() == [
        structural_diagnostics.InvalidGlobalNamePathCharacterDiagnostic(
            location=rendering.SourceLocation(
                line=30, column=35, end_line=30, end_column=35, file_path=None
            ),
            chars=("-",),
            segment="bad-name",
        )
    ]
