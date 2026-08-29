# pyright: reportUnusedCallResult=false
# Exception to CLAUDE.md "no docstrings in tests" rule: these tests have docstrings
# because the automated guarantee/requirement scenarios are complex enough to need
# prose explanations of what each test verifies.

from __future__ import annotations

from pathlib import PurePosixPath
from typing import TYPE_CHECKING

from define.compiler import diagnostics
from define.compiler.validator.reference_graph import action_contract
from define.compiler.validator.reference_graph.operation_graph_renderer import (
    action_graph_set,
)
from define.compiler.validator.reference_graph.reference_graph_validator_tests.test_helpers import (
    assert_propagation_chain,
)
from define.compiler.validator.test_helpers import assert_no_errors

if TYPE_CHECKING:
    from define.compiler.conftest import (
        ValidateTestdataProjectWithReferenceGraph,
    )

_TEST = "action<my.domain.com:my_lib:/test>"
_OTHER = "action<my.domain.com:my_lib:/other>"
_OUTER = "action<my.domain.com:my_lib:/outer>"


def test_error_interface_position_stays_error_after_trigger(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 2
    assert isinstance(all_diags[0], diagnostics.MoveFromEmptyPositionDiagnostic)
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].location.line == 16
    assert all_diags[0].location.column == 30
    assert all_diags[0].position_name == "position<src>"
    assert all_diags[0].is_action_interface_position is False
    assert all_diags[0].inferred_at is None
    assert isinstance(all_diags[1], diagnostics.MoveToOccupiedPositionDiagnostic)
    assert all_diags[1].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[1].location.line == 16
    assert all_diags[1].location.column == 47
    assert all_diags[1].position_name == "position<box>::action</other>::position<item>"
    assert all_diags[1].occupied_at is not None
    assert all_diags[1].occupied_at.line == 15
    assert all_diags[1].occupied_at.column == 47
    assert action_graph_set(result.operation_graphs) == {(_TEST, _OTHER)}


def test_post_trigger_error_guarantee_suppresses_create_diagnostic(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.MoveFromEmptyPositionDiagnostic)
    assert all_diags[0].location.file_path == PurePosixPath("other.dfn")
    assert all_diags[0].location.line == 11
    assert all_diags[0].location.column == 30
    assert all_diags[0].is_action_interface_position is False
    assert all_diags[0].inferred_at is None
    assert action_graph_set(result.operation_graphs) == {(_TEST, _OTHER)}


def test_post_trigger_error_guarantee_suppresses_move_from_diagnostic(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.MoveFromEmptyPositionDiagnostic)
    assert all_diags[0].location.file_path == PurePosixPath("other.dfn")
    assert all_diags[0].location.line == 11
    assert all_diags[0].location.column == 30
    assert all_diags[0].is_action_interface_position is False
    assert all_diags[0].inferred_at is None
    assert action_graph_set(result.operation_graphs) == {(_TEST, _OTHER)}


def test_post_trigger_error_guarantee_suppresses_move_to_diagnostic(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.MoveFromEmptyPositionDiagnostic)
    assert all_diags[0].location.file_path == PurePosixPath("other.dfn")
    assert all_diags[0].location.line == 11
    assert all_diags[0].location.column == 30
    assert all_diags[0].is_action_interface_position is False
    assert all_diags[0].inferred_at is None
    assert action_graph_set(result.operation_graphs) == {(_TEST, _OTHER)}


def test_post_trigger_error_chain_guarantee_suppresses_create_diagnostic(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.MoveFromEmptyPositionDiagnostic)
    assert all_diags[0].location.file_path == PurePosixPath("other.dfn")
    assert all_diags[0].location.line == 14
    assert all_diags[0].location.column == 30
    assert all_diags[0].is_action_interface_position is False
    assert all_diags[0].inferred_at is None
    assert action_graph_set(result.operation_graphs) == {(_TEST, _OTHER)}


def test_post_trigger_error_chain_guarantee_suppresses_move_from_diagnostic(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.MoveFromEmptyPositionDiagnostic)
    assert all_diags[0].location.file_path == PurePosixPath("other.dfn")
    assert all_diags[0].location.line == 14
    assert all_diags[0].location.column == 30
    assert all_diags[0].is_action_interface_position is False
    assert all_diags[0].inferred_at is None
    assert action_graph_set(result.operation_graphs) == {(_TEST, _OTHER)}


def test_post_trigger_error_chain_guarantee_suppresses_move_to_diagnostic(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.MoveFromEmptyPositionDiagnostic)
    assert all_diags[0].location.file_path == PurePosixPath("other.dfn")
    assert all_diags[0].location.line == 14
    assert all_diags[0].location.column == 30
    assert all_diags[0].is_action_interface_position is False
    assert all_diags[0].inferred_at is None
    assert action_graph_set(result.operation_graphs) == {(_TEST, _OTHER)}


def test_error_from_move_to_occupied_interface_position(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.MoveToOccupiedPositionDiagnostic)
    assert all_diags[0].location.file_path == PurePosixPath("other.dfn")
    assert all_diags[0].location.line == 10
    assert all_diags[0].location.column == 49
    assert action_graph_set(result.operation_graphs) == {(_TEST, _OTHER)}


def test_error_from_constraint_violation_on_interface_position(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.MoveViolatesConstraintsDiagnostic)
    assert all_diags[0].location.file_path == PurePosixPath("other.dfn")
    assert all_diags[0].location.line == 13
    assert all_diags[0].location.column == 57
    assert action_graph_set(result.operation_graphs) == {(_TEST, _OTHER)}


def test_error_propagation_from_local_to_interface_position(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.MoveFromEmptyPositionDiagnostic)
    assert all_diags[0].location.file_path == PurePosixPath("other.dfn")
    assert all_diags[0].location.line == 11
    assert all_diags[0].location.column == 30
    assert all_diags[0].is_action_interface_position is False
    assert all_diags[0].inferred_at is None
    assert action_graph_set(result.operation_graphs) == {(_TEST, _OTHER)}


def test_error_from_prefix_move_on_interface_position(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.MoveIntoDefiningPositionDiagnostic)
    assert all_diags[0].location.file_path == PurePosixPath("outer.dfn")
    assert all_diags[0].location.line == 12
    assert all_diags[0].location.column == 66
    assert action_graph_set(result.operation_graphs) == {(_TEST, _OUTER)}


def test_unknown_global_chain_start_treats_action_guarantees_as_error(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 2
    assert isinstance(all_diags[0], diagnostics.UnknownGlobalNameDiagnostic)
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].source_global_name == "action</other>"
    assert all_diags[0].full_global_name == "action<my.domain.com:my_lib:/other>"
    assert all_diags[0].location.line == 7
    assert isinstance(all_diags[1], diagnostics.UnknownGlobalNameDiagnostic)
    assert all_diags[1].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[1].source_global_name == "action</other>"
    assert all_diags[1].full_global_name == "action<my.domain.com:my_lib:/other>"
    assert all_diags[1].location.line == 8


def test_post_trigger_error_guarantee_on_child_position(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.MoveFromEmptyPositionDiagnostic)
    assert all_diags[0].location.file_path == PurePosixPath("other.dfn")
    assert all_diags[0].location.line == 14
    assert all_diags[0].location.column == 30
    assert all_diags[0].is_action_interface_position is False
    assert all_diags[0].inferred_at is None
    assert action_graph_set(result.operation_graphs) == {(_TEST, _OTHER)}


def test_post_trigger_existing_guarantee_error_origin_with_children(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.MoveFromEmptyPositionDiagnostic)
    assert all_diags[0].location.file_path == PurePosixPath("other.dfn")
    assert all_diags[0].location.line == 19
    assert all_diags[0].location.column == 30
    assert all_diags[0].is_action_interface_position is False
    assert all_diags[0].inferred_at is None
    assert action_graph_set(result.operation_graphs) == {(_TEST, _OTHER)}


def test_caller_prefills_child_without_parent_then_triggers(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.ParentPositionNotOccupiedDiagnostic)
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].location.line == 17
    assert all_diags[0].location.column == 30
    assert (
        all_diags[0].position_name
        == "position<box>::action</other>::position<item>::position</child_q>"
    )
    assert (
        all_diags[0].parent_position_name
        == "position<box>::action</other>::position<item>"
    )
    assert action_graph_set(result.operation_graphs) == {(_TEST, _OTHER)}


def test_action_creates_child_but_caller_omits_parent(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert action_graph_set(result.operation_graphs) == {(_TEST, _OTHER)}


def test_swap_guarantee_both_positions_unfilled(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 2
    assert isinstance(all_diags[0], diagnostics.InferredRequirementViolationDiagnostic)
    assert all_diags[0].location.line == 18
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].action_name == "action<my.domain.com:my_lib:/other>"
    assert all_diags[0].required_empty is False
    assert all_diags[0].position_name == "position<box>::action</other>::position<a>"
    assert_propagation_chain(
        all_diags[0],
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _TEST,
            "triggered_quality_name": _OTHER,
            "line": 18,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": _OTHER,
            "triggered_quality_name": None,
            "line": 9,
            "column": 30,
            "file_path": "other.dfn",
        },
    )
    assert isinstance(all_diags[1], diagnostics.InferredRequirementViolationDiagnostic)
    assert all_diags[1].location.line == 18
    assert all_diags[1].location.column == 30
    assert all_diags[1].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[1].action_name == "action<my.domain.com:my_lib:/other>"
    assert all_diags[1].required_empty is False
    assert all_diags[1].position_name == "position<box>::action</other>::position<b>"
    assert_propagation_chain(
        all_diags[1],
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _TEST,
            "triggered_quality_name": _OTHER,
            "line": 18,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": _OTHER,
            "triggered_quality_name": None,
            "line": 10,
            "column": 30,
            "file_path": "other.dfn",
        },
    )
    assert action_graph_set(result.operation_graphs) == {(_TEST, _OTHER)}


def test_swap_guarantee_one_position_unfilled(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 2
    assert isinstance(all_diags[0], diagnostics.InferredRequirementViolationDiagnostic)
    assert all_diags[0].location.line == 21
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.end_line == 21
    assert all_diags[0].location.end_column == 82
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].action_name == "action<my.domain.com:my_lib:/other>"
    assert all_diags[0].required_empty is False
    assert all_diags[0].position_name == "position<box>::action</other>::position<b>"
    assert_propagation_chain(
        all_diags[0],
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _TEST,
            "triggered_quality_name": _OTHER,
            "line": 21,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": _OTHER,
            "triggered_quality_name": None,
            "line": 10,
            "column": 30,
            "file_path": "other.dfn",
        },
    )
    assert isinstance(all_diags[1], diagnostics.CreateInOccupiedPositionDiagnostic)
    assert all_diags[1].location.line == 23
    assert all_diags[1].location.column == 30
    assert all_diags[1].location.end_line == 23
    assert all_diags[1].location.end_column == 72
    assert all_diags[1].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[1].position_name == "position<box>::action</other>::position<b>"
    assert all_diags[1].populated_at.line == 11
    assert all_diags[1].populated_at.column == 47
    assert all_diags[1].populated_at.end_line == 11
    assert all_diags[1].populated_at.end_column == 58
    assert all_diags[1].populated_at.file_path == PurePosixPath("other.dfn")
    assert action_graph_set(result.operation_graphs) == {(_TEST, _OTHER)}


def test_each_unfilled_required_parent_independently_makes_caller_position_error(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 4
    assert isinstance(all_diags[0], diagnostics.InferredRequirementViolationDiagnostic)
    assert all_diags[0].location.line == 16
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.end_line == 16
    assert all_diags[0].location.end_column == 82
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].action_name == "action<my.domain.com:my_lib:/other>"
    assert all_diags[0].required_empty is False
    assert all_diags[0].position_name == "position<box>::action</other>::position<a>"
    assert_propagation_chain(
        all_diags[0],
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _TEST,
            "triggered_quality_name": _OTHER,
            "line": 16,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": _OTHER,
            "triggered_quality_name": None,
            "line": 18,
            "column": 30,
            "file_path": "other.dfn",
        },
    )
    assert isinstance(all_diags[1], diagnostics.InferredRequirementViolationDiagnostic)
    assert all_diags[1].location.line == 16
    assert all_diags[1].location.column == 30
    assert all_diags[1].location.end_line == 16
    assert all_diags[1].location.end_column == 82
    assert all_diags[1].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[1].action_name == "action<my.domain.com:my_lib:/other>"
    assert all_diags[1].required_empty is False
    assert (
        all_diags[1].position_name
        == "position<box>::action</other>::position<a>::position</c1>"
    )
    assert_propagation_chain(
        all_diags[1],
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _TEST,
            "triggered_quality_name": _OTHER,
            "line": 16,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": _OTHER,
            "triggered_quality_name": None,
            "line": 18,
            "column": 30,
            "file_path": "other.dfn",
        },
    )
    assert isinstance(all_diags[2], diagnostics.InferredRequirementViolationDiagnostic)
    assert all_diags[2].location.line == 16
    assert all_diags[2].location.column == 30
    assert all_diags[2].location.end_line == 16
    assert all_diags[2].location.end_column == 82
    assert all_diags[2].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[2].action_name == "action<my.domain.com:my_lib:/other>"
    assert all_diags[2].required_empty is False
    assert all_diags[2].position_name == "position<box>::action</other>::position<b>"
    assert_propagation_chain(
        all_diags[2],
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _TEST,
            "triggered_quality_name": _OTHER,
            "line": 16,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": _OTHER,
            "triggered_quality_name": None,
            "line": 19,
            "column": 30,
            "file_path": "other.dfn",
        },
    )
    assert isinstance(all_diags[3], diagnostics.InferredRequirementViolationDiagnostic)
    assert all_diags[3].location.line == 16
    assert all_diags[3].location.column == 30
    assert all_diags[3].location.end_line == 16
    assert all_diags[3].location.end_column == 82
    assert all_diags[3].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[3].action_name == "action<my.domain.com:my_lib:/other>"
    assert all_diags[3].required_empty is False
    assert (
        all_diags[3].position_name
        == "position<box>::action</other>::position<b>::position</c2>"
    )
    assert_propagation_chain(
        all_diags[3],
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _TEST,
            "triggered_quality_name": _OTHER,
            "line": 16,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": _OTHER,
            "triggered_quality_name": None,
            "line": 19,
            "column": 30,
            "file_path": "other.dfn",
        },
    )


def test_move_from_emptied_origin_leaves_destination_error_in_caller(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.InferredRequirementViolationDiagnostic)
    assert all_diags[0].location.line == 30
    assert all_diags[0].location.column == 51
    assert all_diags[0].location.end_line == 30
    assert all_diags[0].location.end_column == 112
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].action_name == "action<my.domain.com:my_lib:/other>"
    assert all_diags[0].required_empty is False
    assert (
        all_diags[0].position_name
        == "position<other_holder>::action</other>::position<trigger_pos>::position</src>"
    )
    assert_propagation_chain(
        all_diags[0],
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _TEST,
            "triggered_quality_name": _OTHER,
            "line": 30,
            "column": 51,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": _OTHER,
            "triggered_quality_name": None,
            "line": 11,
            "column": 30,
            "file_path": "other.dfn",
        },
    )


def test_occupied_by_existing_destination_the_caller_filled_becomes_error(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 2

    assert isinstance(all_diags[0], diagnostics.InferredRequirementViolationDiagnostic)
    assert all_diags[0].location.line == 14
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.end_line == 14
    assert all_diags[0].location.end_column == 82
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].action_name == "action<my.domain.com:my_lib:/other>"
    assert all_diags[0].required_empty is False
    assert all_diags[0].position_name == "position<box>::action</other>::position<src>"
    assert_propagation_chain(
        all_diags[0],
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _TEST,
            "triggered_quality_name": _OTHER,
            "line": 14,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": _OTHER,
            "triggered_quality_name": None,
            "line": 8,
            "column": 30,
            "file_path": "other.dfn",
        },
    )

    assert isinstance(all_diags[1], diagnostics.InferredRequirementViolationDiagnostic)
    assert all_diags[1].location.line == 14
    assert all_diags[1].location.column == 30
    assert all_diags[1].location.end_line == 14
    assert all_diags[1].location.end_column == 82
    assert all_diags[1].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[1].action_name == "action<my.domain.com:my_lib:/other>"
    assert all_diags[1].required_empty is True
    assert all_diags[1].position_name == "position<box>::action</other>::position<dst>"
    assert_propagation_chain(
        all_diags[1],
        {
            "kind": action_contract.PropagationKind.FILL_SITE,
            "enclosing_quality_name": "position<box>::action</other>::position<dst>",
            "triggered_quality_name": None,
            "line": 13,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _TEST,
            "triggered_quality_name": _OTHER,
            "line": 14,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": _OTHER,
            "triggered_quality_name": None,
            "line": 8,
            "column": 47,
            "file_path": "other.dfn",
        },
    )


def test_swap_propagates_prior_error_state_from_origin_to_destination(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 2
    assert isinstance(all_diags[0], diagnostics.MoveFromEmptyPositionDiagnostic)
    assert all_diags[0].location.line == 19
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.end_line == 19
    assert all_diags[0].location.end_column == 49
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].position_name == "position<empty_src>"
    assert all_diags[0].is_action_interface_position is False
    assert all_diags[0].inferred_at is None
    assert isinstance(all_diags[1], diagnostics.MoveToOccupiedPositionDiagnostic)
    assert all_diags[1].location.line == 19
    assert all_diags[1].location.column == 53
    assert all_diags[1].location.end_line == 19
    assert all_diags[1].location.end_column == 95
    assert all_diags[1].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[1].position_name == "position<box>::action</other>::position<a>"
    assert all_diags[1].occupied_at is not None
    assert all_diags[1].occupied_at.line == 18
    assert all_diags[1].occupied_at.column == 30
    assert all_diags[1].occupied_at.end_line == 18
    assert all_diags[1].occupied_at.end_column == 72
    assert all_diags[1].occupied_at.file_path == PurePosixPath("test.dfn")
    assert action_graph_set(result.operation_graphs) == {(_TEST, _OTHER)}
