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
    from define.compiler.conftest import (
        ValidateTestdataProjectWithReferenceGraph,
    )

_TEST = "action<my.domain.com:my_lib:/test>"
_CONSTRUCT = "action<my.domain.com:my_lib:/construct>"
_CONSTRUCT_A = "action<my.domain.com:my_lib:/construct_a>"
_CONSTRUCT_B = "action<my.domain.com:my_lib:/construct_b>"
_INNER = "action<my.domain.com:my_lib:/inner>"


def test_consumes_implied_action_interface(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    assert_no_errors(validate_testdata_project_with_reference_graph().program_result)


def test_minimal(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    assert_no_errors(validate_testdata_project_with_reference_graph().program_result)


def test_non_entry(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    assert_no_errors(validate_testdata_project_with_reference_graph().program_result)


def test_create_fires_constructor_via_constraint_on_local_position(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert action_graph(result.operation_graphs) == [(_TEST, _CONSTRUCT)]


def test_create_fires_constructor_via_constraint_on_interface_position(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert action_graph(result.operation_graphs) == [(_TEST, _CONSTRUCT)]


def test_create_in_position_child_fires_constructor(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert action_graph(result.operation_graphs) == [(_TEST, _CONSTRUCT)]


def test_create_in_action_child_interface_fires_constructor(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert action_graph(result.operation_graphs) == [
        (_INNER, _CONSTRUCT),
        (_TEST, _INNER),
    ]


def test_create_fires_multiple_constructors(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert action_graph(result.operation_graphs) == [
        (_TEST, _CONSTRUCT_A),
        (_TEST, _CONSTRUCT_B),
    ]


def test_create_does_not_fire_non_constructor_action_quality(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.UntriggeredActionDiagnostic)
    assert all_diags[0].constraint_name == "action</worker>"
    assert all_diags[0].position_name == "position<box>"
    assert action_graph(result.operation_graphs) == []


def test_move_into_position_does_not_fire_constructor(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert action_graph(result.operation_graphs) == [(_TEST, _CONSTRUCT)]


def test_missing_constructor_file_is_reported_and_skipped(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.ReferencedFileNotFoundDiagnostic)
    assert all_diags[0].file_path == "construct.dfn"
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert action_graph(result.operation_graphs) == []


def test_create_parent_not_occupied_does_not_fire_constructor(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 2
    assert isinstance(all_diags[0], diagnostics.UntriggeredActionDiagnostic)
    assert all_diags[0].constraint_name == "action</inner>"
    assert all_diags[0].position_name == "position<box>"
    assert isinstance(all_diags[1], diagnostics.ParentPositionNotOccupiedDiagnostic)
    assert all_diags[1].position_name == "position<box>::action</inner>::position<slot>"
    assert all_diags[1].parent_position_name == "position<box>"
    assert action_graph(result.operation_graphs) == [(_INNER, _CONSTRUCT)]
