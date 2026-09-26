"""Structural validation of potential literal definitions."""

from __future__ import annotations

from pathlib import PurePosixPath
from typing import TYPE_CHECKING

from define.compiler import ast, diagnostics, parser_exceptions
from define.compiler.validator.test_helpers import assert_no_errors

if TYPE_CHECKING:
    from define.compiler.conftest import (
        ValidateTestdataProjectWithReferenceGraph,
        ValidateTestdataStructural,
        ValidateTestdataStructuralNonFilesystem,
    )


def test_valid_literal(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    full_result = validate_testdata_project_with_reference_graph()
    result = full_result.program_result
    assert_no_errors(result)
    assert len(result.file_results) == 2
    assert len(result.definition_results) == 2
    assert result.entry_action is None
    definition_result = result.file_results[0].definition_results[0]
    definition = definition_result.definition
    assert isinstance(definition, ast.PotentialLiteralDefinition)
    assert (
        definition.encoding.full_typed_name
        == "encoding<my.domain.com:my_lib:/decimal_text>"
    )
    ordered_definitions = result.definition_order.definitions
    assert isinstance(ordered_definitions[0], ast.EncodingDefinition)
    assert ordered_definitions[1] is definition


def test_same_name_different_types(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert_no_errors(result)
    assert len(result.definition_results) == 3


def test_cross_universe_encoding(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert_no_errors(result)
    assert len(result.definition_results) == 2


def test_duplicate_literal(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.DuplicateDefinitionDiagnostic)
    assert diagnostic.location.column == 1
    assert diagnostic.location.file_path is None
    assert diagnostic.definition_type == "literal"
    assert diagnostic.path == "/decimal"
    assert diagnostic.first_definition_line == 3
    assert diagnostic.location.line == 6


def test_invalid_name(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.InvalidGlobalNamePathCharacterDiagnostic)
    assert diagnostic.location.line == 3
    assert diagnostic.location.column == 55
    assert diagnostic.location.file_path is None
    assert diagnostic.segment == "bad-name"
    assert diagnostic.char == "-"


def test_invalid_encoding_name(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.InvalidGlobalNamePathCharacterDiagnostic)
    assert diagnostic.location.column == 29
    assert diagnostic.location.file_path is None
    assert diagnostic.segment == "bad-name"
    assert diagnostic.char == "-"
    assert diagnostic.location.line == 3


def test_requires_short_encoding_name(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.GlobalReferenceMustUseShortFormDiagnostic)
    assert diagnostic.location.line == 4
    assert diagnostic.location.column == 25
    assert diagnostic.location.file_path is None
    assert diagnostic.fqun == "my.domain.com:my_lib"


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
    assert exception.column == 30


def test_path_mismatch(validate_testdata_structural: ValidateTestdataStructural):
    result = validate_testdata_structural()
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.PathMismatchDiagnostic)
    assert diagnostic.location.line == 2
    assert diagnostic.location.column == 51
    assert diagnostic.location.file_path == PurePosixPath("test.dfn")
    assert diagnostic.expected_path == "/test"
    assert diagnostic.actual_path == "/decimal"


def test_missing_encoding_file(
    validate_testdata_structural: ValidateTestdataStructural,
):
    result = validate_testdata_structural()
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.ReferencedFileNotFoundDiagnostic)
    assert diagnostic.location.line == 3
    assert diagnostic.location.column == 25
    assert diagnostic.location.file_path == PurePosixPath("test.dfn")
    assert diagnostic.file_path == "decimal_text.dfn"


def test_wrong_encoding_definition_type(
    validate_testdata_structural: ValidateTestdataStructural,
):
    result = validate_testdata_structural()
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.ReferencedDefinitionNotFoundDiagnostic)
    assert diagnostic.location.line == 3
    assert diagnostic.location.column == 25
    assert diagnostic.location.file_path == PurePosixPath("test.dfn")
    assert diagnostic.definition_name == "encoding<my.domain.com:my_lib:/decimal_text>"
    assert diagnostic.file_path == "decimal_text.dfn"


def test_same_file_encoding(validate_testdata_structural: ValidateTestdataStructural):
    result = validate_testdata_structural()
    assert_no_errors(result)
    assert len(result.file_results) == 1
    assert len(result.definition_results) == 2


def test_same_file_encoding_must_precede_reference(
    validate_testdata_structural: ValidateTestdataStructural,
):
    result = validate_testdata_structural()
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.ReferencedDefinitionNotFoundDiagnostic)
    assert diagnostic.location.file_path == PurePosixPath("test.dfn")
    assert diagnostic.definition_name == "encoding<my.domain.com:my_lib:/test>"
    assert diagnostic.file_path == "test.dfn"
    assert diagnostic.location.line == 3
    assert diagnostic.location.column == 25


def test_configured_external_encoding(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_result
    assert_no_errors(result)
    assert len(result.file_results) == 2
    assert len(result.definition_results) == 2


def test_unconfigured_external_encoding(
    validate_testdata_structural: ValidateTestdataStructural,
):
    result = validate_testdata_structural()
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.ExternalUniverseNotConfiguredDiagnostic)
    assert diagnostic.location.line == 3
    assert diagnostic.location.column == 25
    assert diagnostic.location.file_path == PurePosixPath("test.dfn")
    assert diagnostic.current_universe_name == "my.domain.com:my_lib"
    assert diagnostic.universe == "encodings.org:encodings"


def test_non_filesystem_encoding_must_precede_reference(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.ReferencedFileNotFoundDiagnostic)
    assert diagnostic.location.line == 3
    assert diagnostic.location.column == 25
    assert diagnostic.location.file_path is None
    assert diagnostic.file_path == "decimal_text.dfn"
