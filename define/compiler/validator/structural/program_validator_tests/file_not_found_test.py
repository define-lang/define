# pyright: reportUnusedCallResult=false
"""File not found validation tests.

Follow program validator test authoring rules in program_validator_tests/AGENTS.md.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from define.compiler import diagnostics, exceptions
from define.compiler.data_structures import define_path

if TYPE_CHECKING:
    from define.compiler.conftest import (
        ValidateTestdataStructural,
    )


def test_entrypoint_file_not_found(
    validate_testdata_structural: ValidateTestdataStructural,
):
    result = validate_testdata_structural(entry_file="nonexistent.dfn")
    assert len(result.all_exceptions) == 1
    assert isinstance(result.all_exceptions[0], exceptions.SourceFileNotFoundError)
    assert len(result.file_results) == 1
    assert result.file_results[0].diagnostics == []


def test_referenced_file_not_found(
    validate_testdata_structural: ValidateTestdataStructural,
):
    result = validate_testdata_structural()
    assert result.all_exceptions == []
    assert len(result.file_results[0].diagnostics) == 1
    diag = result.file_results[0].diagnostics[0]
    assert isinstance(diag, diagnostics.ReferencedFileNotFoundDiagnostic)
    assert diag.file_path == "missing.dfn"
    assert diag.location.line == 3
    assert diag.location.column == 29


def test_referenced_file_not_found_via_already_completed_target(
    validate_testdata_structural: ValidateTestdataStructural,
):
    result = validate_testdata_structural(max_workers=1)
    assert result.all_exceptions == []
    assert len(result.file_results) == 2
    assert result.file_results[0].file_path == define_path.DefinePath("test.dfn")
    assert result.file_results[0].exception is None
    assert len(result.file_results[0].diagnostics) == 1
    assert isinstance(
        result.file_results[0].diagnostics[0],
        diagnostics.ReferencedFileNotFoundDiagnostic,
    )
    assert result.file_results[0].diagnostics[0].file_path == "missing.dfn"
    assert result.file_results[1].file_path == define_path.DefinePath("target.dfn")
    assert result.file_results[1].exception is None
    assert len(result.file_results[1].diagnostics) == 1
    assert isinstance(
        result.file_results[1].diagnostics[0],
        diagnostics.ReferencedFileNotFoundDiagnostic,
    )
    assert result.file_results[1].diagnostics[0].file_path == "missing.dfn"


def test_referenced_file_not_found_for_two_definitions_in_same_file(
    validate_testdata_structural: ValidateTestdataStructural,
):
    program_result = validate_testdata_structural()
    assert program_result.all_exceptions == []
    result = program_result.file_results[0]
    assert result.exception is None
    diags = result.diagnostics
    assert len(diags) == 2
    assert isinstance(diags[0], diagnostics.ReferencedFileNotFoundDiagnostic)
    assert isinstance(diags[1], diagnostics.ReferencedFileNotFoundDiagnostic)
    assert diags[0].file_path == "missing.dfn"
    assert diags[0].location.line == 3
    assert diags[0].location.column == 29
    assert diags[1].file_path == "missing.dfn"
    assert diags[1].location.line == 12
    assert diags[1].location.column == 37


def test_same_missing_file_referenced_as_two_types_in_one_definition(
    validate_testdata_structural: ValidateTestdataStructural,
):
    program_result = validate_testdata_structural()
    assert program_result.all_exceptions == []
    result = program_result.file_results[0]
    assert result.exception is None
    diags = result.diagnostics
    assert len(diags) == 2
    assert isinstance(diags[0], diagnostics.ReferencedFileNotFoundDiagnostic)
    assert diags[0].file_path == "missing.dfn"
    assert diags[0].location.line == 3
    assert diags[0].location.column == 29
    assert isinstance(diags[1], diagnostics.ReferencedFileNotFoundDiagnostic)
    assert diags[1].file_path == "missing.dfn"
    assert diags[1].location.line == 4
    assert diags[1].location.column == 27
