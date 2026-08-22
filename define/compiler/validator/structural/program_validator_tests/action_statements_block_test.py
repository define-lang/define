# pyright: reportUnusedCallResult=false
from __future__ import annotations

from typing import TYPE_CHECKING

from define.compiler import diagnostics

if TYPE_CHECKING:
    from define.compiler.conftest import ValidateTestdataStructuralNonFilesystem


def test_undefined_local_position_in_create(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert result.all_exceptions == []
    results = result.file_results
    diags = results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.UndefinedLocalNameDiagnostic)
    assert diags[0].local_name == "position<undefined>"
    assert diags[0].location.line == 5
    assert diags[0].location.column == 30


def test_empty_action_statements_block(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert result.all_exceptions == []
    results = result.file_results
    diags = results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.EmptyActionStatementsBlockDiagnostic)
