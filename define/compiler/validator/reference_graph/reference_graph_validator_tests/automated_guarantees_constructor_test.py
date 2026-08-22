# pyright: reportUnusedCallResult=false

from __future__ import annotations

from pathlib import PurePosixPath
from typing import TYPE_CHECKING

from define.compiler import diagnostics
from define.compiler.validator.reference_graph.operation_graph_renderer import (
    action_graph,
)
from define.compiler.validator.test_helpers import assert_no_errors

if TYPE_CHECKING:
    from define.compiler.conftest import ValidateTestdataProjectWithReferenceGraph

_TEST = "action<my.domain.com:my_lib:/test>"
_CONSTRUCT = "action<my.domain.com:my_lib:/construct>"


def test_constructor_implied_position_guarantee_visible_to_caller(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert action_graph(result.operation_graphs) == [(_TEST, _CONSTRUCT)]


def test_constructor_occupied_guarantee_conflicts_with_caller_create(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.CreateInOccupiedPositionDiagnostic)
    assert all_diags[0].location.line == 15
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].position_name == "position<box>::position</color>"
    assert all_diags[0].populated_at.line == 6
    assert all_diags[0].populated_at.file_path == PurePosixPath("construct.dfn")
    assert action_graph(result.operation_graphs) == [(_TEST, _CONSTRUCT)]
