# pyright: reportUnusedCallResult=false
"""Position constraint reference validation tests.

Follow program validator test authoring rules in program_validator_tests/AGENTS.md.
"""

from __future__ import annotations

from pathlib import PurePosixPath
from typing import TYPE_CHECKING

from define.compiler import diagnostics
from define.compiler.data_structures import define_path

if TYPE_CHECKING:
    from define.compiler.conftest import (
        ValidateTestdataStructural,
        ValidateTestdataStructuralNonFilesystem,
    )


def test_action_local_position_requires_missing_global(
    validate_testdata_structural: ValidateTestdataStructural,
):
    result = validate_testdata_structural()
    assert result.all_exceptions == []
    diags = result.all_diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.ReferencedDefinitionNotFoundDiagnostic)
    assert diags[0].file_path == "test.dfn"
    assert diags[0].definition_name == "position<mv:define-lang.org:test_files:/test>"
    assert diags[0].location.line == 4
    assert diags[0].location.column == 33
    assert diags[0].location.end_line == 4
    assert diags[0].location.end_column == 38
    assert diags[0].location.file_path == PurePosixPath("test.dfn")


def test_same_fqun_constraint_reference_in_global_position_must_use_short_form(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert result.all_exceptions == []
    diags = result.file_results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.GlobalReferenceMustUseShortFormDiagnostic)
    assert diags[0].fqun == "mv:define-lang.org:test_files"
    assert diags[0].location.line == 3
    assert diags[0].location.column == 29
    assert diags[0].location.end_line == 3
    assert diags[0].location.end_column == 58
    assert diags[0].location.file_path is None


def test_same_fqun_constraint_reference_in_move_must_use_short_form(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert result.all_exceptions == []
    diags = result.file_results[0].diagnostics
    assert len(diags) == 2
    assert isinstance(diags[0], diagnostics.GlobalReferenceMustUseShortFormDiagnostic)
    assert diags[0].fqun == "mv:define-lang.org:test_files"
    assert diags[0].location.line == 8
    assert diags[0].location.column == 37
    assert diags[0].location.end_line == 8
    assert diags[0].location.end_column == 66
    assert diags[0].location.file_path is None
    assert isinstance(diags[1], diagnostics.GlobalReferenceMustUseShortFormDiagnostic)
    assert diags[1].fqun == "mv:define-lang.org:test_files"
    assert diags[1].location.line == 12
    assert diags[1].location.column == 80
    assert diags[1].location.end_line == 12
    assert diags[1].location.end_column == 109
    assert diags[1].location.file_path is None


def test_position_constraint_reference_with_invalid_path(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert result.all_exceptions == []
    diags = result.file_results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.InvalidGlobalNamePathCharacterDiagnostic)
    assert diags[0].segment == "Bad"
    assert diags[0].char == "B"
    assert diags[0].location.line == 3
    assert diags[0].location.column == 30


def test_same_fqun_constraint_reference_must_use_short_form(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert result.all_exceptions == []
    diags = result.file_results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.GlobalReferenceMustUseShortFormDiagnostic)
    assert diags[0].fqun == "my.domain.com:my_lib"
    assert diags[0].location.line == 3
    assert diags[0].location.column == 29


def test_same_fqun_constraint_reference_in_local_position_must_use_short_form(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert result.all_exceptions == []
    diags = result.file_results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.GlobalReferenceMustUseShortFormDiagnostic)
    assert diags[0].fqun == "my.domain.com:my_lib"
    assert diags[0].location.line == 4
    assert diags[0].location.column == 33


def test_invalid_constraint_does_not_skip_remaining_constraints(
    validate_testdata_structural: ValidateTestdataStructural,
):
    result = validate_testdata_structural()
    assert result.all_exceptions == []
    assert len(result.file_results) == 2
    assert result.file_results[0].file_path == define_path.DefinePath("test.dfn")
    diags = result.file_results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.InvalidGlobalNamePathCharacterDiagnostic)
    assert diags[0].segment == "Bad"
    assert diags[0].char == "B"
    assert diags[0].location.line == 3
    assert diags[0].location.column == 30
    assert result.file_results[1].file_path == define_path.DefinePath("valid.dfn")
    assert result.file_results[1].diagnostics == []


def test_referenced_global_name_wrong_type_position(
    validate_testdata_structural: ValidateTestdataStructural,
):
    result = validate_testdata_structural()
    assert result.all_exceptions == []
    assert len(result.file_results) == 2
    assert result.file_results[0].file_path == define_path.DefinePath("test.dfn")
    diags = result.file_results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.ReferencedDefinitionNotFoundDiagnostic)
    assert diags[0].file_path == "target.dfn"
    assert (
        diags[0].definition_name
        == "position<mv:define-lang.org:test_walk_wrong_type:/target>"
    )
    assert diags[0].location.line == 3
    assert diags[0].location.column == 29


def test_referenced_global_name_wrong_type_for_two_definitions_in_same_file(
    validate_testdata_structural: ValidateTestdataStructural,
):
    result = validate_testdata_structural()
    assert result.all_exceptions == []
    assert len(result.file_results) == 2
    assert result.file_results[0].file_path == define_path.DefinePath("test.dfn")
    diags = result.file_results[0].diagnostics
    assert len(diags) == 2
    assert isinstance(diags[0], diagnostics.ReferencedDefinitionNotFoundDiagnostic)
    assert isinstance(diags[1], diagnostics.ReferencedDefinitionNotFoundDiagnostic)
    assert diags[0].file_path == "target.dfn"
    assert (
        diags[0].definition_name
        == "position<mv:define-lang.org:test_walk_wrong_type:/target>"
    )
    assert diags[0].location.line == 3
    assert diags[0].location.column == 29
    assert diags[1].file_path == "target.dfn"
    assert (
        diags[1].definition_name
        == "position<mv:define-lang.org:test_walk_wrong_type:/target>"
    )
    assert diags[1].location.line == 9
    assert diags[1].location.column == 33
