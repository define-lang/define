"""Diagnostic collection tests.

Follow program validator test authoring rules in program_validator_tests/AGENTS.md.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from define.compiler import diagnostics

if TYPE_CHECKING:
    from define.compiler.conftest import ValidateTestdataStructuralNonFilesystem


def test_multiple_diagnostics_collected(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert result.all_exceptions == []
    results = result.file_results
    diags = results[0].diagnostics
    assert len(diags) == 2
    assert isinstance(diags[0], diagnostics.ReservedUniverseNameDiagnostic)
    assert diags[0].location.line == 1
    assert diags[0].location.column == 31
    assert diags[0].reserved_name == "standard"
    assert isinstance(diags[1], diagnostics.ReservedUniverseNameDiagnostic)
    assert diags[1].location.line == 2
    assert diags[1].location.column == 31
    assert diags[1].reserved_name == "standard"


def test_diagnostics_in_source_order(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert result.all_exceptions == []
    results = result.file_results
    diags = results[0].diagnostics
    assert isinstance(diags[0], diagnostics.ReservedUniverseNameDiagnostic)
    assert diags[0].location.line == 1
    assert diags[0].location.column == 31
    assert diags[0].reserved_name == "standard"
    assert isinstance(diags[1], diagnostics.ReservedUniverseNameDiagnostic)
    assert diags[1].location.line == 2
    assert diags[1].location.column == 31
    assert diags[1].reserved_name == "standard"
