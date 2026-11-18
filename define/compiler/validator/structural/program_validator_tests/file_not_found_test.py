# pyright: reportUnusedCallResult=false
"""File not found validation tests.

Follow program validator test authoring rules in program_validator_tests/AGENTS.md.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from define.compiler.data_structures import define_path
from define.compiler.errors import diagnostics, syntax_errors

if TYPE_CHECKING:
    from define.compiler.test_fixtures.structural_validation import (
        ValidateTestdataStructural,
    )

pytest_plugins = ["define.compiler.test_fixtures.structural_validation"]


def test_entrypoint_file_not_found(
    validate_testdata_structural: ValidateTestdataStructural,
):
    result = validate_testdata_structural(entry_file="nonexistent.dfn")
    assert result.sorted_diagnostics() == [
        syntax_errors.SourceFileNotFound(file_path="nonexistent.dfn")
    ]
    assert len(result.file_results) == 1


def test_referenced_file_not_found(
    validate_testdata_structural: ValidateTestdataStructural,
):
    result = validate_testdata_structural()
    diags = result.sorted_diagnostics()
    assert len(diags) == 1
    diag = diags[0]
    assert isinstance(diag, diagnostics.ReferencedFileNotFoundDiagnostic)
    assert diag.location.file_path == "test.dfn"
    assert diag.file_path == "missing.dfn"
    assert diag.location.line == 3
    assert diag.location.column == 29


def test_referenced_file_unreadable(
    validate_testdata_structural: ValidateTestdataStructural,
):
    result = validate_testdata_structural()
    (diagnostic,) = result.sorted_diagnostics()
    # The reason is the operating system's, whose words differ by platform.
    assert isinstance(diagnostic, diagnostics.ReferencedFileUnreadableDiagnostic)
    assert diagnostic.reason
    assert diagnostic.location.file_path == "test.dfn"
    assert diagnostic.location.line == 5
    assert diagnostic.location.column == 29
    assert diagnostic.file_path == "target.dfn"
    assert len(result.file_results) == 1


def test_referenced_file_not_found_via_already_completed_target(
    validate_testdata_structural: ValidateTestdataStructural,
):
    result = validate_testdata_structural(max_workers=1)
    assert len(result.file_results) == 2
    assert result.file_results[0].file_path == define_path.DefinePath("test.dfn")
    diags = result.sorted_diagnostics()
    assert len(diags) == 2
    assert isinstance(
        diags[0],
        diagnostics.ReferencedFileNotFoundDiagnostic,
    )
    assert diags[0].location.line == 3
    assert diags[0].location.column == 29
    assert diags[0].location.file_path == "target.dfn"
    assert diags[0].file_path == "missing.dfn"
    assert result.file_results[1].file_path == define_path.DefinePath("target.dfn")
    assert isinstance(
        diags[1],
        diagnostics.ReferencedFileNotFoundDiagnostic,
    )
    assert diags[1].location.line == 3
    assert diags[1].location.column == 29
    assert diags[1].location.file_path == "test.dfn"
    assert diags[1].file_path == "missing.dfn"


def test_referenced_file_not_found_for_two_definitions_in_same_file(
    validate_testdata_structural: ValidateTestdataStructural,
):
    diags = validate_testdata_structural().sorted_diagnostics()
    assert len(diags) == 2
    assert isinstance(diags[0], diagnostics.ReferencedFileNotFoundDiagnostic)
    assert diags[0].location.file_path == "test.dfn"
    assert isinstance(diags[1], diagnostics.ReferencedFileNotFoundDiagnostic)
    assert diags[1].location.file_path == "test.dfn"
    assert diags[0].file_path == "missing.dfn"
    assert diags[0].location.line == 3
    assert diags[0].location.column == 29
    assert diags[1].file_path == "missing.dfn"
    assert diags[1].location.line == 12
    assert diags[1].location.column == 37


def test_same_missing_file_referenced_as_two_types_in_one_definition(
    validate_testdata_structural: ValidateTestdataStructural,
):
    diags = validate_testdata_structural().sorted_diagnostics()
    assert len(diags) == 2
    assert isinstance(diags[0], diagnostics.ReferencedFileNotFoundDiagnostic)
    assert diags[0].location.file_path == "test.dfn"
    assert diags[0].file_path == "missing.dfn"
    assert diags[0].location.line == 3
    assert diags[0].location.column == 29
    assert isinstance(diags[1], diagnostics.ReferencedFileNotFoundDiagnostic)
    assert diags[1].location.file_path == "test.dfn"
    assert diags[1].file_path == "missing.dfn"
    assert diags[1].location.line == 4
    assert diags[1].location.column == 27
