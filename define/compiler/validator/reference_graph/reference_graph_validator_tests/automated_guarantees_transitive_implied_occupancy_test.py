# pyright: reportUnusedCallResult=false
from pathlib import PurePosixPath

from define.compiler import diagnostics
from define.compiler.conftest import (
    ValidateTestdataProjectWithReferenceGraph,
)
from define.compiler.validator.reference_graph.operation_graph_renderer import (
    action_graph,
)
from define.compiler.validator.test_helpers import assert_no_errors

_TEST = "action<my.domain.com:my_lib:/test>"
_IMPLIED = "action<my.domain.com:my_lib:/implied_action>"
_IMPLIER = "action<my.domain.com:my_lib:/implier>"
_FORWARDER = "action<my.domain.com:my_lib:/forwarder>"
_MIDDLE = "action<my.domain.com:my_lib:/middle>"
_FILLER = "action<my.domain.com:my_lib:/filler>"


def test_occupied_guarantee_propagates_through_transitive_implication(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert action_graph(result.operation_graphs) == [
        (_FORWARDER, _IMPLIED),
        (_IMPLIER, _FORWARDER),
        (_TEST, _IMPLIED),
        (_TEST, _IMPLIER),
    ]


def test_empty_guarantee_propagates_through_transitive_implication(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert action_graph(result.operation_graphs) == [
        (_FORWARDER, _IMPLIED),
        (_IMPLIER, _FORWARDER),
        (_TEST, _IMPLIED),
        (_TEST, _IMPLIER),
    ]


def test_occupied_guarantee_blocks_create_through_transitive_implication(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.CreateInOccupiedPositionDiagnostic)
    assert all_diags[0].location.line == 14
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.end_line == 14
    assert all_diags[0].location.end_column == 86
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert (
        all_diags[0].position_name
        == "position<box>::action</implied_action>::position<output>"
    )
    assert all_diags[0].populated_at.line == 7
    assert all_diags[0].populated_at.column == 30
    assert all_diags[0].populated_at.end_line == 7
    assert all_diags[0].populated_at.end_column == 46
    assert all_diags[0].populated_at.file_path == PurePosixPath("implied_action.dfn")
    assert action_graph(result.operation_graphs) == [
        (_FORWARDER, _IMPLIED),
        (_IMPLIER, _FORWARDER),
        (_TEST, _IMPLIED),
        (_TEST, _IMPLIER),
    ]


def test_empty_guarantee_blocks_move_through_transitive_implication(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.MoveFromEmptyPositionDiagnostic)
    assert all_diags[0].location.line == 16
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.end_line == 16
    assert all_diags[0].location.end_column == 85
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert (
        all_diags[0].position_name
        == "position<box>::action</implied_action>::position<input>"
    )
    assert all_diags[0].is_action_interface_position is True
    assert all_diags[0].inferred_at is not None
    assert all_diags[0].inferred_at.line == 8
    assert all_diags[0].inferred_at.column == 30
    assert all_diags[0].inferred_at.end_line == 8
    assert all_diags[0].inferred_at.end_column == 45
    assert all_diags[0].inferred_at.file_path == PurePosixPath("implied_action.dfn")
    assert action_graph(result.operation_graphs) == [
        (_FORWARDER, _IMPLIED),
        (_IMPLIER, _FORWARDER),
        (_TEST, _IMPLIED),
        (_TEST, _IMPLIER),
    ]


def test_occupied_implied_position_guarantee_propagates_through_transitive_implication(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert action_graph(result.operation_graphs) == [
        (_FORWARDER, _IMPLIED),
        (_IMPLIER, _FORWARDER),
        (_TEST, _IMPLIED),
        (_TEST, _IMPLIER),
    ]


def test_empty_implied_position_guarantee_propagates_through_transitive_implication(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert action_graph(result.operation_graphs) == [
        (_FORWARDER, _IMPLIED),
        (_IMPLIER, _FORWARDER),
        (_TEST, _IMPLIED),
        (_TEST, _IMPLIER),
    ]


def test_occupied_implied_position_guarantee_blocks_create_through_transitive_implication(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.CreateInOccupiedPositionDiagnostic)
    assert all_diags[0].location.line == 15
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.end_line == 15
    assert all_diags[0].location.end_column == 67
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].position_name == "position<box>::position</implied_pos>"
    assert all_diags[0].populated_at.line == 7
    assert all_diags[0].populated_at.column == 30
    assert all_diags[0].populated_at.end_line == 7
    assert all_diags[0].populated_at.end_column == 52
    assert all_diags[0].populated_at.file_path == PurePosixPath("implied_action.dfn")
    assert action_graph(result.operation_graphs) == [
        (_FORWARDER, _IMPLIED),
        (_IMPLIER, _FORWARDER),
        (_TEST, _IMPLIED),
        (_TEST, _IMPLIER),
    ]


def test_empty_implied_position_guarantee_blocks_move_through_transitive_implication(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.MoveFromEmptyPositionDiagnostic)
    assert all_diags[0].location.line == 17
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.end_line == 17
    assert all_diags[0].location.end_column == 67
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].position_name == "position<box>::position</implied_pos>"
    assert all_diags[0].is_action_interface_position is False
    assert all_diags[0].inferred_at is None
    assert action_graph(result.operation_graphs) == [
        (_FORWARDER, _IMPLIED),
        (_IMPLIER, _FORWARDER),
        (_TEST, _IMPLIED),
        (_TEST, _IMPLIER),
    ]


def test_occupied_implied_position_guarantee_propagates_through_directly_implied_action_chain(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.CreateInOccupiedPositionDiagnostic)
    assert all_diags[0].location.line == 10
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.end_line == 10
    assert all_diags[0].location.end_column == 52
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].position_name == "position</implied_pos>"
    assert all_diags[0].populated_at.line == 7
    assert all_diags[0].populated_at.column == 30
    assert all_diags[0].populated_at.end_line == 7
    assert all_diags[0].populated_at.end_column == 52
    assert all_diags[0].populated_at.file_path == PurePosixPath("implied_action.dfn")
    assert action_graph(result.operation_graphs) == [
        (
            "action<my.domain.com:my_lib:/middle>",
            "action<my.domain.com:my_lib:/implied_action>",
        ),
        ("action<my.domain.com:my_lib:/test>", "action<my.domain.com:my_lib:/middle>"),
    ]


def test_empty_implied_position_guarantee_propagates_through_directly_implied_action_chain(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.MoveFromEmptyPositionDiagnostic)
    assert all_diags[0].location.line == 12
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.end_line == 12
    assert all_diags[0].location.end_column == 52
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].position_name == "position</implied_pos>"
    assert all_diags[0].is_action_interface_position is False
    assert all_diags[0].inferred_at is None
    assert action_graph(result.operation_graphs) == [
        (
            "action<my.domain.com:my_lib:/middle>",
            "action<my.domain.com:my_lib:/implied_action>",
        ),
        ("action<my.domain.com:my_lib:/test>", "action<my.domain.com:my_lib:/middle>"),
    ]


def test_constructor_transitively_implied_occupancy_conflicts_with_caller_create(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.CreateInOccupiedPositionDiagnostic)
    assert all_diags[0].location.line == 13
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.end_line == 13
    assert all_diags[0].location.end_column == 78
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert (
        all_diags[0].position_name == "position<box>::position</slot>::position</color>"
    )
    assert all_diags[0].populated_at.line == 6
    assert all_diags[0].populated_at.column == 30
    assert all_diags[0].populated_at.end_line == 6
    assert all_diags[0].populated_at.end_column == 46
    assert all_diags[0].populated_at.file_path == PurePosixPath("filler.dfn")
    assert action_graph(result.operation_graphs) == [
        (_IMPLIER, _FILLER),
        (_TEST, _IMPLIER),
    ]


def test_constructor_transitively_implied_occupancy_conflicts_through_deeper_chain(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.CreateInOccupiedPositionDiagnostic)
    assert all_diags[0].location.line == 13
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.end_line == 13
    assert all_diags[0].location.end_column == 107
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert (
        all_diags[0].position_name
        == "position<box>::position</slot_outer>::position</slot_inner>::position</color>"
    )
    assert all_diags[0].populated_at.line == 6
    assert all_diags[0].populated_at.column == 30
    assert all_diags[0].populated_at.end_line == 6
    assert all_diags[0].populated_at.end_column == 46
    assert all_diags[0].populated_at.file_path == PurePosixPath("filler.dfn")
    assert action_graph(result.operation_graphs) == [
        (_MIDDLE, _FILLER),
        (_IMPLIER, _MIDDLE),
        (_TEST, _IMPLIER),
    ]


def test_inner_action_guarantee_through_implied_action_chain_attaches_to_full_caller_prefix(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.CreateInOccupiedPositionDiagnostic)
    assert all_diags[0].location.line == 22
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.end_line == 22
    assert all_diags[0].location.end_column == 108
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert (
        all_diags[0].position_name
        == "position<host>::position</mid>::action</nested>::position<iface>::position</x>"
    )
    assert all_diags[0].populated_at.line == 8
    assert all_diags[0].populated_at.column == 30
    assert all_diags[0].populated_at.end_line == 8
    assert all_diags[0].populated_at.end_column == 76
    assert all_diags[0].populated_at.file_path == PurePosixPath("inner.dfn")


def test_sibling_action_guarantee_and_requirement_share_implied_position_key(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
