"""Structural validation of encoding operation definitions and their executions.

Follow program validator test authoring rules in program_validator_tests/AGENTS.md.
"""

from __future__ import annotations

from pathlib import PurePosixPath
from typing import TYPE_CHECKING

from define.compiler import ast, diagnostics
from define.compiler.validator.test_helpers import (
    BUILT_IN_DEFINITION_COUNT,
    assert_no_errors,
)

if TYPE_CHECKING:
    from define.compiler.conftest import (
        ValidateTestdataStructural,
        ValidateTestdataStructuralNonFilesystem,
    )


def test_valid_encoding_operation(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert_no_errors(result)
    assert len(result.definition_results) == 2 + BUILT_IN_DEFINITION_COUNT


def test_computer_operation_references_every_view(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert_no_errors(result)


def test_unreferenced_views(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 2
    first = result.all_diagnostics[0]
    assert isinstance(first, diagnostics.UnreferencedViewDiagnostic)
    assert first.location.file_path is None
    assert first.location.line == 27
    assert first.location.column == 21
    assert first.view_name == "view<unused>"
    assert first.operation_name_type == ast.NameType.ENCODING_OPERATION
    second = result.all_diagnostics[1]
    assert isinstance(second, diagnostics.UnreferencedViewDiagnostic)
    assert second.location.file_path is None
    assert second.location.line == 33
    assert second.location.column == 21
    assert second.view_name == "view<also_unused>"
    assert second.operation_name_type == ast.NameType.ENCODING_OPERATION


def test_view_missing_encoding_constraint(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 2
    missing = result.all_diagnostics[0]
    assert isinstance(missing, diagnostics.ViewMissingEncodingConstraintDiagnostic)
    assert missing.location.file_path is None
    assert missing.location.line == 3
    assert missing.location.column == 21
    assert missing.view_name == "view<number>"
    quality = result.all_diagnostics[1]
    assert isinstance(quality, diagnostics.ViewQualityConstraintDiagnostic)
    assert quality.location.file_path is None
    assert quality.location.line == 6
    assert quality.location.column == 24
    assert quality.constraint_name == "position</box>"


def test_view_value_constraint(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 2
    missing = result.all_diagnostics[0]
    assert isinstance(missing, diagnostics.ViewMissingEncodingConstraintDiagnostic)
    assert missing.location.file_path is None
    assert missing.location.line == 3
    assert missing.location.column == 21
    assert missing.view_name == "view<number>"
    value = result.all_diagnostics[1]
    assert isinstance(value, diagnostics.EncodingOperationViewValueConstraintDiagnostic)
    assert value.location.file_path is None
    assert value.location.line == 6
    assert value.location.column == 24
    assert value.constraint_name == "value<standard:/number/rational>"


def test_view_value_and_encoding_constraints(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(
        diagnostic, diagnostics.EncodingOperationViewValueConstraintDiagnostic
    )
    assert diagnostic.location.file_path is None
    assert diagnostic.location.line == 6
    assert diagnostic.location.column == 24
    assert diagnostic.constraint_name == "value<standard:/number/rational>"


def test_view_position_constraint(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.ViewQualityConstraintDiagnostic)
    assert diagnostic.location.file_path is None
    assert diagnostic.location.line == 7
    assert diagnostic.location.column == 24
    assert diagnostic.constraint_name == "position</box>"


def test_duplicate_view(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.LocalNameConflictDiagnostic)
    assert diagnostic.location.file_path is None
    assert diagnostic.location.line == 9
    assert diagnostic.location.column == 21
    assert diagnostic.local_name == "number"
    assert diagnostic.first_definition_line == 3


def test_duplicate_encoding_operation(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.DuplicateDefinitionDiagnostic)
    assert diagnostic.location.file_path is None
    assert diagnostic.location.line == 20
    assert diagnostic.location.column == 1
    assert diagnostic.definition_type == "encoding_operation"
    assert diagnostic.path == "/copy"
    assert diagnostic.first_definition_line == 2


def test_looks_at_position(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.OperationArgumentPositionDiagnostic)
    assert diagnostic.location.file_path is None
    assert diagnostic.location.line == 37
    assert diagnostic.location.column == 42
    assert diagnostic.position_name == "position<result>"


def test_aliased_views(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.AliasedViewDiagnostic)
    assert diagnostic.location.file_path is None
    assert diagnostic.location.line == 31
    assert diagnostic.location.column == 42
    assert diagnostic.looked_at_name == "view<number>"
    assert diagnostic.first_argument_line == 30


def test_looks_at_undefined_view(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.UndefinedLocalNameDiagnostic)
    assert diagnostic.location.file_path is None
    assert diagnostic.location.line == 37
    assert diagnostic.location.column == 42
    assert diagnostic.local_name == "view<missing>"


def test_executes_itself(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.CircularGlobalReferenceDiagnostic)
    assert diagnostic.location.file_path is None
    assert diagnostic.location.line == 5
    assert diagnostic.location.column == 21
    assert diagnostic.cycle == [
        "encoding_operation<my.domain.com:my_lib:/double>",
        "encoding_operation<my.domain.com:my_lib:/double>",
    ]


def test_encoding_operation_in_other_file(
    validate_testdata_structural: ValidateTestdataStructural,
):
    result = validate_testdata_structural()
    assert_no_errors(result)
    assert len(result.file_results) == 2
    assert len(result.definition_results) == 2 + BUILT_IN_DEFINITION_COUNT


def test_executes_value_operation(
    validate_testdata_structural: ValidateTestdataStructural,
):
    result = validate_testdata_structural()
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.ReferencedDefinitionNotFoundDiagnostic)
    assert diagnostic.location.file_path == PurePosixPath("test.dfn")
    assert diagnostic.location.line == 11
    assert diagnostic.location.column == 40
    assert (
        diagnostic.definition_name == "encoding_operation<my.domain.com:my_lib:/copy>"
    )
    assert diagnostic.file_path == "copy.dfn"


def test_value_operation_executes_encoding_operation(
    validate_testdata_structural: ValidateTestdataStructural,
):
    result = validate_testdata_structural()
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.ReferencedDefinitionNotFoundDiagnostic)
    assert diagnostic.location.file_path == PurePosixPath("test.dfn")
    assert diagnostic.location.line == 11
    assert diagnostic.location.column == 31
    assert diagnostic.definition_name == "operation<my.domain.com:my_lib:/copy>"
    assert diagnostic.file_path == "copy.dfn"
