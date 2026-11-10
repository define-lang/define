from __future__ import annotations

from typing import TYPE_CHECKING

from define.compiler.data_structures import define_path
from define.compiler.errors import diagnostics

if TYPE_CHECKING:
    from define.compiler.conftest import (
        ValidateTestdataStructural,
        ValidateTestdataStructuralNonFilesystem,
    )


def test_move_from_a_position_to_itself(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    diags = result.all_diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.MoveToSamePositionDiagnostic)
    assert diags[0].location.line == 7
    assert diags[0].location.column == 45
    assert diags[0].location.file_path is None
    assert diags[0].position_name == "position<a>"


def test_move_from_a_chained_position_to_itself(
    validate_testdata_structural: ValidateTestdataStructural,
):
    result = validate_testdata_structural()
    all_diags = result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.MoveToSamePositionDiagnostic)
    assert all_diags[0].location.line == 11
    assert all_diags[0].location.column == 72
    assert all_diags[0].location.file_path == "test.dfn"
    assert all_diags[0].position_name == "position<a>::position</x>"


def test_move_to_chained_prefix_position(
    validate_testdata_structural: ValidateTestdataStructural,
):
    result = validate_testdata_structural()
    assert len(result.file_results) == 2
    assert result.file_results[0].file_path == define_path.DefinePath("test.dfn")
    assert result.file_results[1].file_path == define_path.DefinePath("target_pos.dfn")
    diags = result.all_diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.MoveIntoDefiningPositionDiagnostic)
    assert diags[0].location.line == 11
    assert diags[0].location.column == 74
    assert diags[0].location.file_path == "test.dfn"
    assert diags[0].source_position == "position<local_pos>"
    assert diags[0].target_position == "position<local_pos>::position</target_pos>"
