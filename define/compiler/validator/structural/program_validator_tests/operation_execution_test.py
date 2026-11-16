"""Structural validation of Operation Execution Statements within value operations.

Follow program validator test authoring rules in program_validator_tests/AGENTS.md.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from crates.source_rendering.python import rendering
from define.compiler.errors import diagnostics
from define.compiler.validator.test_helpers import assert_no_errors

if TYPE_CHECKING:
    from define.compiler.conftest import (
        ValidateTestdataStructural,
        ValidateTestdataStructuralNonFilesystem,
    )


def test_looks_at_undefined_view(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert result.all_diagnostics == [
        diagnostics.UndefinedLocalNameDiagnostic(
            location=rendering.SourceLocation(
                line=41, column=42, end_line=41, end_column=54, file_path=None
            ),
            local_name="view<missing>",
        )
    ]


def test_looks_at_invalid_view_name(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert result.all_diagnostics == [
        diagnostics.InvalidLocalNameFormatDiagnostic(
            location=rendering.SourceLocation(
                line=41, column=47, end_line=41, end_column=47, file_path=None
            ),
            chars=("R",),
            local_name="Result",
        )
    ]


def test_aliased_views(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert result.all_diagnostics == [
        diagnostics.AliasedViewDiagnostic(
            location=rendering.SourceLocation(
                line=35, column=42, end_line=35, end_column=53, file_path=None
            ),
            looked_at_name="view<number>",
            first_argument_line=34,
        )
    ]


def test_same_view_in_separate_executions(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert_no_errors(result)


def test_same_literal_twice(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert_no_errors(result)


def test_invalid_argument_view_name(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert result.all_diagnostics == [
        diagnostics.InvalidLocalNameFormatDiagnostic(
            location=rendering.SourceLocation(
                line=40, column=23, end_line=40, end_column=23, file_path=None
            ),
            chars=("S",),
            local_name="Source",
        )
    ]


def test_invalid_literal_name(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert result.all_diagnostics == [
        diagnostics.InvalidGlobalNamePathCharacterDiagnostic(
            location=rendering.SourceLocation(
                line=34, column=63, end_line=34, end_column=63, file_path=None
            ),
            chars=("-",),
            segment="bad-name",
        )
    ]


def test_invalid_operation_name(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.InvalidGlobalNamePathCharacterDiagnostic)
    assert diagnostic.location.file_path is None
    assert diagnostic.location.line == 5
    assert diagnostic.location.column == 35
    assert diagnostic.segment == "bad-name"
    assert diagnostic.chars == ("-",)


def test_requires_short_operation_name(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert result.all_diagnostics == [
        diagnostics.GlobalReferenceMustUseShortFormDiagnostic(
            location=rendering.SourceLocation(
                line=27, column=31, end_line=27, end_column=50, file_path=None
            ),
            fqun="my.domain.com:my_lib",
        )
    ]


def test_executes_itself(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.CircularGlobalReferenceDiagnostic)
    assert diagnostic.location.file_path is None
    assert diagnostic.location.line == 5
    assert diagnostic.location.column == 21
    assert diagnostic.cycle == [
        "operation<my.domain.com:my_lib:/double>",
        "operation<my.domain.com:my_lib:/double>",
    ]


def test_operation_in_other_file(
    validate_testdata_structural: ValidateTestdataStructural,
):
    result = validate_testdata_structural()
    assert_no_errors(result)


def test_missing_operation_file(
    validate_testdata_structural: ValidateTestdataStructural,
):
    result = validate_testdata_structural()
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.ReferencedFileNotFoundDiagnostic)
    assert diagnostic.location.file_path == "test.dfn"
    assert diagnostic.location.line == 11
    assert diagnostic.location.column == 31
    assert diagnostic.file_path == "copy.dfn"


def test_wrong_operation_definition_type(
    validate_testdata_structural: ValidateTestdataStructural,
):
    result = validate_testdata_structural()
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.ReferencedDefinitionNotFoundDiagnostic)
    assert diagnostic.location.file_path == "test.dfn"
    assert diagnostic.location.line == 11
    assert diagnostic.location.column == 21
    assert diagnostic.definition_name == "operation<my.domain.com:my_lib:/copy>"
    assert diagnostic.file_path == "copy.dfn"


def test_duplicate_argument(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert result.all_diagnostics == [
        diagnostics.DuplicateOperationArgumentDiagnostic(
            location=rendering.SourceLocation(
                line=41, column=18, end_line=41, end_column=29, file_path=None
            ),
            view_name="view<source>",
            first_argument_line=40,
        )
    ]
