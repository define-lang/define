# pyright: reportUnusedCallResult=false

from __future__ import annotations

from pathlib import PurePosixPath
from typing import TYPE_CHECKING

from define.compiler import diagnostics

if TYPE_CHECKING:
    from define.compiler.conftest import (
        ValidateTestdataProjectWithReferenceGraph,
    )

_PARENT = "my.domain.com:parent_lib"
_CHILD = "my.domain.com:child_lib"


def test_move_interface_to_implied(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 2
    assert isinstance(
        all_diags[0], diagnostics.DestroyInEmptyInterfacePositionDiagnostic
    )
    assert all_diags[0].location.line == 14
    assert all_diags[0].location.column == 33
    assert all_diags[0].location.end_line == 14
    assert all_diags[0].location.end_column == 78
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].position_name == "position<box>::action</inner>::position<item>"
    assert all_diags[0].inferred_at is not None
    assert all_diags[0].inferred_at.line == 8
    assert all_diags[0].inferred_at.column == 30
    assert all_diags[0].inferred_at.end_line == 8
    assert all_diags[0].inferred_at.end_column == 44
    assert all_diags[0].inferred_at.file_path == PurePosixPath("inner.dfn")
    assert isinstance(all_diags[1], diagnostics.CreateInOccupiedPositionDiagnostic)
    assert all_diags[1].location.line == 15
    assert all_diags[1].location.column == 30
    assert all_diags[1].location.end_line == 15
    assert all_diags[1].location.end_column == 63
    assert all_diags[1].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[1].position_name == "position<box>::position</implied>"
    assert all_diags[1].populated_at.line == 8
    assert all_diags[1].populated_at.column == 48
    assert all_diags[1].populated_at.end_line == 8
    assert all_diags[1].populated_at.end_column == 66
    assert all_diags[1].populated_at.file_path == PurePosixPath("inner.dfn")


def test_move_implied_to_interface(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 2
    assert isinstance(all_diags[0], diagnostics.CreateInOccupiedPositionDiagnostic)
    assert all_diags[0].location.line == 13
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.end_line == 13
    assert all_diags[0].location.end_column == 75
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].position_name == "position<box>::action</inner>::position<item>"
    assert all_diags[0].populated_at.line == 9
    assert all_diags[0].populated_at.column == 52
    assert all_diags[0].populated_at.end_line == 9
    assert all_diags[0].populated_at.end_column == 66
    assert all_diags[0].populated_at.file_path == PurePosixPath("inner.dfn")
    assert isinstance(all_diags[1], diagnostics.DestroyInEmptyPositionDiagnostic)
    assert all_diags[1].location.line == 14
    assert all_diags[1].location.column == 33
    assert all_diags[1].location.end_line == 14
    assert all_diags[1].location.end_column == 66
    assert all_diags[1].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[1].position_name == "position<box>::position</implied>"


def test_move_interface_through_implied_back_to_interface(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 3
    assert isinstance(all_diags[0], diagnostics.CreateInOccupiedPositionDiagnostic)
    assert all_diags[0].location.line == 14
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.end_line == 14
    assert all_diags[0].location.end_column == 75
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].position_name == "position<box>::action</inner>::position<dest>"
    assert all_diags[0].populated_at.line == 10
    assert all_diags[0].populated_at.column == 52
    assert all_diags[0].populated_at.end_line == 10
    assert all_diags[0].populated_at.end_column == 66
    assert all_diags[0].populated_at.file_path == PurePosixPath("inner.dfn")
    assert isinstance(
        all_diags[1], diagnostics.DestroyInEmptyInterfacePositionDiagnostic
    )
    assert all_diags[1].location.line == 15
    assert all_diags[1].location.column == 33
    assert all_diags[1].location.end_line == 15
    assert all_diags[1].location.end_column == 77
    assert all_diags[1].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[1].position_name == "position<box>::action</inner>::position<src>"
    assert all_diags[1].inferred_at is not None
    assert all_diags[1].inferred_at.line == 9
    assert all_diags[1].inferred_at.column == 30
    assert all_diags[1].inferred_at.end_line == 9
    assert all_diags[1].inferred_at.end_column == 43
    assert all_diags[1].inferred_at.file_path == PurePosixPath("inner.dfn")
    assert isinstance(all_diags[2], diagnostics.DestroyInEmptyPositionDiagnostic)
    assert all_diags[2].location.line == 16
    assert all_diags[2].location.column == 33
    assert all_diags[2].location.end_line == 16
    assert all_diags[2].location.end_column == 66
    assert all_diags[2].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[2].position_name == "position<box>::position</implied>"


def test_interface_to_implied_propagates_across_fqun(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 2
    assert isinstance(
        all_diags[0], diagnostics.DestroyInEmptyInterfacePositionDiagnostic
    )
    assert all_diags[0].location.line == 14
    assert all_diags[0].location.column == 33
    assert all_diags[0].location.end_line == 14
    assert all_diags[0].location.end_column == 102
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert (
        all_diags[0].position_name
        == f"position<box>::action<{_CHILD}:/inner>::position<item>"
    )
    assert all_diags[0].inferred_at is not None
    assert all_diags[0].inferred_at.line == 8
    assert all_diags[0].inferred_at.column == 30
    assert all_diags[0].inferred_at.end_line == 8
    assert all_diags[0].inferred_at.end_column == 44
    assert all_diags[0].inferred_at.file_path == PurePosixPath("lib/inner.dfn")
    assert isinstance(all_diags[1], diagnostics.CreateInOccupiedPositionDiagnostic)
    assert all_diags[1].location.line == 15
    assert all_diags[1].location.column == 30
    assert all_diags[1].location.end_line == 15
    assert all_diags[1].location.end_column == 87
    assert all_diags[1].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[1].position_name == f"position<box>::position<{_CHILD}:/implied>"
    assert all_diags[1].populated_at.line == 8
    assert all_diags[1].populated_at.column == 48
    assert all_diags[1].populated_at.end_line == 8
    assert all_diags[1].populated_at.end_column == 66
    assert all_diags[1].populated_at.file_path == PurePosixPath("lib/inner.dfn")


def test_action_creates_in_both_interface_and_implied(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 2
    assert isinstance(all_diags[0], diagnostics.CreateInOccupiedPositionDiagnostic)
    assert all_diags[0].location.line == 13
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.end_line == 13
    assert all_diags[0].location.end_column == 75
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].position_name == "position<box>::action</inner>::position<item>"
    assert all_diags[0].populated_at.line == 8
    assert all_diags[0].populated_at.column == 30
    assert all_diags[0].populated_at.end_line == 8
    assert all_diags[0].populated_at.end_column == 44
    assert all_diags[0].populated_at.file_path == PurePosixPath("inner.dfn")
    assert isinstance(all_diags[1], diagnostics.CreateInOccupiedPositionDiagnostic)
    assert all_diags[1].location.line == 14
    assert all_diags[1].location.column == 30
    assert all_diags[1].location.end_line == 14
    assert all_diags[1].location.end_column == 63
    assert all_diags[1].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[1].position_name == "position<box>::position</implied>"
    assert all_diags[1].populated_at.line == 9
    assert all_diags[1].populated_at.column == 30
    assert all_diags[1].populated_at.end_line == 9
    assert all_diags[1].populated_at.end_column == 48
    assert all_diags[1].populated_at.file_path == PurePosixPath("inner.dfn")


def test_swap_interface_and_implied_via_local(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 2
    assert isinstance(all_diags[0], diagnostics.CreateInOccupiedPositionDiagnostic)
    assert all_diags[0].location.line == 14
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.end_line == 14
    assert all_diags[0].location.end_column == 75
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].position_name == "position<box>::action</inner>::position<item>"
    assert all_diags[0].populated_at.line == 11
    assert all_diags[0].populated_at.column == 52
    assert all_diags[0].populated_at.end_line == 11
    assert all_diags[0].populated_at.end_column == 66
    assert all_diags[0].populated_at.file_path == PurePosixPath("inner.dfn")
    assert isinstance(all_diags[1], diagnostics.CreateInOccupiedPositionDiagnostic)
    assert all_diags[1].location.line == 15
    assert all_diags[1].location.column == 30
    assert all_diags[1].location.end_line == 15
    assert all_diags[1].location.end_column == 63
    assert all_diags[1].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[1].position_name == "position<box>::position</implied>"
    assert all_diags[1].populated_at.line == 12
    assert all_diags[1].populated_at.column == 48
    assert all_diags[1].populated_at.end_line == 12
    assert all_diags[1].populated_at.end_column == 66
    assert all_diags[1].populated_at.file_path == PurePosixPath("inner.dfn")
