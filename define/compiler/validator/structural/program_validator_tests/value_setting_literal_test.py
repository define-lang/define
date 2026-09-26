"""Structural validation of literal sources in Value Setting Statements."""

from __future__ import annotations

from pathlib import PurePosixPath
from typing import TYPE_CHECKING

from define.compiler import diagnostics
from define.compiler.validator.test_helpers import assert_no_errors

if TYPE_CHECKING:
    from define.compiler.conftest import (
        ValidateTestdataStructural,
        ValidateTestdataStructuralNonFilesystem,
    )


def test_same_file_literal(validate_testdata_structural: ValidateTestdataStructural):
    result = validate_testdata_structural()
    assert_no_errors(result)
    assert len(result.file_results) == 1
    assert len(result.definition_results) == 3


def test_invalid_literal_name(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.InvalidGlobalNamePathCharacterDiagnostic)
    assert diagnostic.location.file_path is None
    assert diagnostic.segment == "bad-name"
    assert diagnostic.char == "-"
    assert diagnostic.location.line == 11
    assert diagnostic.location.column == 56


def test_same_universe_requires_short_form(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.GlobalReferenceMustUseShortFormDiagnostic)
    assert diagnostic.location.file_path is None
    assert diagnostic.fqun == "my.domain.com:my_lib"
    assert diagnostic.location.line == 11
    assert diagnostic.location.column == 52


def test_undefined_target(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.UndefinedLocalNameDiagnostic)
    assert diagnostic.location.file_path is None
    assert diagnostic.local_name == "position<missing>"
    assert diagnostic.location.line == 10
    assert diagnostic.location.column == 26


def test_invalid_target_and_literal(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 2
    target, literal = result.all_diagnostics
    assert isinstance(target, diagnostics.UndefinedLocalNameDiagnostic)
    assert target.location.file_path is None
    assert target.local_name == "position<missing>"
    assert target.location.line == 10
    assert target.location.column == 26
    assert isinstance(literal, diagnostics.InvalidGlobalNamePathCharacterDiagnostic)
    assert literal.location.file_path is None
    assert literal.segment == "bad-name"
    assert literal.char == "-"
    assert literal.location.line == 10
    assert literal.location.column == 59


def test_missing_literal_file(validate_testdata_structural: ValidateTestdataStructural):
    result = validate_testdata_structural()
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.ReferencedFileNotFoundDiagnostic)
    assert diagnostic.location.file_path == PurePosixPath("test.dfn")
    assert diagnostic.file_path == "missing.dfn"
    assert diagnostic.location.line == 7
    assert diagnostic.location.column == 52


def test_wrong_definition_type(
    validate_testdata_structural: ValidateTestdataStructural,
):
    result = validate_testdata_structural()
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.ReferencedDefinitionNotFoundDiagnostic)
    assert diagnostic.location.file_path == PurePosixPath("test.dfn")
    assert diagnostic.definition_name == "literal<my.domain.com:my_lib:/test>"
    assert diagnostic.file_path == "test.dfn"
    assert diagnostic.location.line == 8
    assert diagnostic.location.column == 52


def test_literal_must_precede_reference(
    validate_testdata_structural: ValidateTestdataStructural,
):
    result = validate_testdata_structural()
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.ReferencedDefinitionNotFoundDiagnostic)
    assert diagnostic.location.file_path == PurePosixPath("test.dfn")
    assert diagnostic.definition_name == "literal<my.domain.com:my_lib:/test>"
    assert diagnostic.file_path == "test.dfn"
    assert diagnostic.location.line == 8
    assert diagnostic.location.column == 52


def test_external_literal(validate_testdata_structural: ValidateTestdataStructural):
    result = validate_testdata_structural()
    assert_no_errors(result)
    assert len(result.file_results) == 2
    assert len(result.definition_results) == 3


def test_unconfigured_external_literal(
    validate_testdata_structural: ValidateTestdataStructural,
):
    result = validate_testdata_structural()
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.ExternalUniverseNotConfiguredDiagnostic)
    assert diagnostic.location.file_path == PurePosixPath("test.dfn")
    assert diagnostic.current_universe_name == "my.domain.com:my_lib"
    assert diagnostic.universe == "literals.org:literals"
    assert diagnostic.location.line == 7
    assert diagnostic.location.column == 52
