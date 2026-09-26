"""Structural validation of encoding definitions."""

from __future__ import annotations

from pathlib import PurePosixPath
from typing import TYPE_CHECKING

from define.compiler import ast, diagnostics, parser_exceptions
from define.compiler.validator.test_helpers import assert_no_errors

if TYPE_CHECKING:
    from define.compiler.conftest import (
        ValidateTestdataStructural,
        ValidateTestdataStructuralNonFilesystem,
    )


def test_valid_encoding(validate_testdata_structural: ValidateTestdataStructural):
    result = validate_testdata_structural()
    assert_no_errors(result)
    definitions = result.file_results[0].definition_results
    assert len(definitions) == 1
    assert isinstance(definitions[0].definition, ast.EncodingDefinition)
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
    assert diagnostic.location.column == 46
    assert diagnostic.location.file_path is None
    assert diagnostic.segment == "bad-name"
    assert diagnostic.char == "-"


def test_duplicate_encoding(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.DuplicateDefinitionDiagnostic)
    assert diagnostic.location.column == 1
    assert diagnostic.location.file_path is None
    assert diagnostic.definition_type == "encoding"
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
    assert diagnostic.location.line == 2
    assert diagnostic.location.column == 42
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
    assert diagnostic.location.column == 21
    assert diagnostic.location.file_path == PurePosixPath("test.dfn")
    assert diagnostic.expected == "my.domain.com:my_lib"
    assert diagnostic.actual == "other.org:my_lib"


def test_requires_fqun(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert result.all_diagnostics == []
    assert len(result.all_exceptions) == 1
    exception = result.all_exceptions[0]
    assert isinstance(
        exception, parser_exceptions.DefinitionGlobalNameContentRequiresFqun
    )
    assert exception.line == 2
    assert exception.column == 21
