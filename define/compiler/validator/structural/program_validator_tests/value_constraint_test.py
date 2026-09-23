"""Structural validation of value constraints on positions."""

from __future__ import annotations

from typing import TYPE_CHECKING

from define.compiler import ast, diagnostics
from define.compiler.validator.test_helpers import assert_no_errors

if TYPE_CHECKING:
    from define.compiler.conftest import (
        ValidateTestdataStructural,
        ValidateTestdataStructuralNonFilesystem,
    )


def test_global_position(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert_no_errors(result)


def test_interface_and_body_positions(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert_no_errors(result)


def test_duplicate_value(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.DuplicatePositionConstraintDiagnostic)
    assert diagnostic.constraint_name == "value</number>"
    assert diagnostic.first_constraint_line == 5
    assert diagnostic.location.line == 6


def test_multiple_values(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 2
    first, second = result.all_diagnostics
    assert isinstance(first, diagnostics.MultipleValueConstraintsDiagnostic)
    assert isinstance(second, diagnostics.MultipleValueConstraintsDiagnostic)
    assert first.first_value_name == "value</number>"
    assert second.first_value_name == "value</number>"
    assert first.first_constraint_line == 7
    assert second.first_constraint_line == 7
    assert first.location.line == 8
    assert second.location.line == 9
    assert first.location.column == 20
    assert first.message == (
        "a position may only have one value constraint; "
        "'value</number>' was already declared on line 7"
    )


def test_multiple_values_in_local_position(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.MultipleValueConstraintsDiagnostic)
    assert diagnostic.first_value_name == "value</number>"
    assert diagnostic.first_constraint_line == 7
    assert diagnostic.location.line == 8
    assert diagnostic.location.column == 24


def test_invalid_name_does_not_count_as_value_constraint(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.InvalidGlobalNamePathCharacterDiagnostic)
    assert diagnostic.segment == "Bad"
    assert diagnostic.char == "B"


def test_same_fqun_requires_short_form(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.GlobalReferenceMustUseShortFormDiagnostic)
    assert diagnostic.fqun == "my.domain.com:my_lib"


def test_reference_to_value_file(
    validate_testdata_structural: ValidateTestdataStructural,
):
    result = validate_testdata_structural()
    assert_no_errors(result)
    assert len(result.file_results) == 2
    value_definitions = result.file_results[1].definition_results
    assert len(value_definitions) == 1
    assert isinstance(value_definitions[0].definition, ast.ValueDefinition)


def test_reference_to_wrong_type(
    validate_testdata_structural: ValidateTestdataStructural,
):
    result = validate_testdata_structural()
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.ReferencedDefinitionNotFoundDiagnostic)
    assert diagnostic.definition_name == "value<my.domain.com:my_lib:/number>"
    assert diagnostic.file_path == "number.dfn"


def test_cross_universe_value(
    validate_testdata_structural: ValidateTestdataStructural,
):
    result = validate_testdata_structural()
    assert_no_errors(result)
    assert len(result.file_results) == 2
