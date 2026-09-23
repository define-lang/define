"""Structural validation of value definitions."""

from __future__ import annotations

from typing import TYPE_CHECKING

from define.compiler import ast, diagnostics
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
    assert diagnostic.segment == "bad-name"
    assert diagnostic.char == "-"


def test_duplicate_value(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.DuplicateDefinitionDiagnostic)
    assert diagnostic.definition_type == "value"
    assert diagnostic.path == "/number"
    assert diagnostic.first_definition_line == 2
    assert diagnostic.location.line == 3


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
    assert diagnostic.expected_path == "/test"
    assert diagnostic.actual_path == "/number"


def test_fqun_mismatch(validate_testdata_structural: ValidateTestdataStructural):
    result = validate_testdata_structural()
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.FqunMismatchDiagnostic)
    assert diagnostic.expected == "my.domain.com:my_lib"
    assert diagnostic.actual == "other.org:my_lib"
