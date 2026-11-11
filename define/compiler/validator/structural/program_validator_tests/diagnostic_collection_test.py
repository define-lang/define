"""Diagnostic collection tests.

Follow program validator test authoring rules in program_validator_tests/AGENTS.md.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from crates.source_rendering.python import rendering
from define.compiler.errors import diagnostics

if TYPE_CHECKING:
    from define.compiler.conftest import ValidateTestdataStructuralNonFilesystem


def test_multiple_diagnostics_collected(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    diags = result.all_diagnostics
    assert len(diags) == 2
    assert isinstance(diags[0], diagnostics.ReservedUniverseNameDiagnostic)
    assert diags[0].location.file_path is None
    assert diags[0].location.line == 1
    assert diags[0].location.column == 31
    assert diags[0].reserved_name == "standard"
    assert isinstance(diags[1], diagnostics.ReservedUniverseNameDiagnostic)
    assert diags[1].location.file_path is None
    assert diags[1].location.line == 2
    assert diags[1].location.column == 31
    assert diags[1].reserved_name == "standard"


def test_diagnostics_in_source_order(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    diags = result.all_diagnostics
    assert isinstance(diags[0], diagnostics.ReservedUniverseNameDiagnostic)
    assert diags[0].location.file_path is None
    assert diags[0].location.line == 1
    assert diags[0].location.column == 31
    assert diags[0].reserved_name == "standard"
    assert isinstance(diags[1], diagnostics.ReservedUniverseNameDiagnostic)
    assert diags[1].location.file_path is None
    assert diags[1].location.line == 2
    assert diags[1].location.column == 31
    assert diags[1].reserved_name == "standard"


def test_non_filesystem_source_reports_trailing_space_but_not_indentation(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert result.all_diagnostics == [
        diagnostics.TrailingWhitespaceDiagnostic(
            location=rendering.SourceLocation(
                line=9, column=60, end_line=9, end_column=61
            )
        )
    ]
