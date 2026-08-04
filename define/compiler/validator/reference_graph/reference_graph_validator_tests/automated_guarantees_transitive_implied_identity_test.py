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


def test_implied_to_implied_identity_preserved_through_transitive_implication(
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


def test_implied_to_implied_identity_blocks_move_to_unrelated_quality_through_transitive_implication(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.MoveViolatesConstraintsDiagnostic)
    assert all_diags[0].location.line == 28
    assert all_diags[0].location.column == 69
    assert all_diags[0].location.end_line == 28
    assert all_diags[0].location.end_column == 88
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].source_position == "position<box>::position</implied_b>"
    assert all_diags[0].target_position == "position<fail_dest>"
    assert all_diags[0].missing_qualities == [
        "position</other>",
    ]
    assert action_graph(result.operation_graphs) == [
        (_FORWARDER, _IMPLIED),
        (_IMPLIER, _FORWARDER),
        (_TEST, _IMPLIED),
        (_TEST, _IMPLIER),
    ]


def test_implied_to_interface_identity_preserved_through_transitive_implication(
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


def test_implied_to_interface_identity_blocks_move_to_unrelated_quality_through_transitive_implication(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.MoveViolatesConstraintsDiagnostic)
    assert all_diags[0].location.line == 27
    assert all_diags[0].location.column == 87
    assert all_diags[0].location.end_line == 27
    assert all_diags[0].location.end_column == 106
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert (
        all_diags[0].source_position
        == "position<box>::action</implied_action>::position<out>"
    )
    assert all_diags[0].target_position == "position<fail_dest>"
    assert all_diags[0].missing_qualities == [
        "position</other>",
    ]
    assert action_graph(result.operation_graphs) == [
        (_FORWARDER, _IMPLIED),
        (_IMPLIER, _FORWARDER),
        (_TEST, _IMPLIED),
        (_TEST, _IMPLIER),
    ]


def test_interface_to_interface_identity_preserved_through_transitive_implication(
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


def test_interface_to_interface_identity_blocks_move_to_unrelated_quality_through_transitive_implication(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.MoveViolatesConstraintsDiagnostic)
    assert all_diags[0].location.line == 26
    assert all_diags[0].location.column == 87
    assert all_diags[0].location.end_line == 26
    assert all_diags[0].location.end_column == 106
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert (
        all_diags[0].source_position
        == "position<box>::action</implied_action>::position<out>"
    )
    assert all_diags[0].target_position == "position<fail_dest>"
    assert all_diags[0].missing_qualities == [
        "position</other>",
    ]
    assert action_graph(result.operation_graphs) == [
        (_FORWARDER, _IMPLIED),
        (_IMPLIER, _FORWARDER),
        (_TEST, _IMPLIED),
        (_TEST, _IMPLIER),
    ]
