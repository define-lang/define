# pyright: reportUnusedCallResult=false
from __future__ import annotations

from pathlib import PurePosixPath

from define.compiler import conftest, diagnostics
from define.compiler.validator.reference_graph.operation_graph_renderer import (
    action_graph,
)
from define.compiler.validator.test_helpers import assert_no_errors

_TEST = "action<my.domain.com:my_lib:/test>"
_OTHER = "action<my.domain.com:my_lib:/other>"
_ACT_A = "action<my.domain.com:my_lib:/act_a>"
_ACT_B = "action<my.domain.com:my_lib:/act_b>"
_ACT_C = "action<my.domain.com:my_lib:/act_c>"
_P = "action<my.domain.com:my_lib:/p>"
_SHARED = "action<my.domain.com:my_lib:/shared>"


def test_action_chain_cascade(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    assert_no_errors(validate_testdata_project_with_reference_graph().program_result)


def test_action_with_body(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    assert_no_errors(validate_testdata_project_with_reference_graph().program_result)


def test_constraints_and_init(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    assert_no_errors(validate_testdata_project_with_reference_graph().program_result)


def test_empty_action(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    assert_no_errors(validate_testdata_project_with_reference_graph().program_result)


def test_multi_interface_positions(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    assert_no_errors(validate_testdata_project_with_reference_graph().program_result)


def test_basic_cross_action_trigger(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert action_graph(result.operation_graphs) == [(_TEST, _OTHER)]


def test_create_and_move_trigger_other_action(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert action_graph(result.operation_graphs) == [(_TEST, _OTHER)]


def test_refilling_destroyed_trigger_position_retriggers(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert action_graph(result.operation_graphs) == [
        (_TEST, _OTHER),
        (_TEST, _OTHER),
    ]


def test_moving_between_two_trigger_positions_fires_both(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert action_graph(result.operation_graphs) == [
        (_TEST, _OTHER),
        (_TEST, _ACT_B),
    ]


def test_move_from_trigger_position_to_itself_does_not_retrigger(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.MoveToSamePositionDiagnostic)
    assert all_diags[0].location.line == 13
    assert all_diags[0].location.column == 125
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert (
        all_diags[0].position_name
        == "position<gateway>::action</other>::position<trigger_pos>"
    )
    assert action_graph(result.operation_graphs) == [(_TEST, _OTHER)]


def test_cross_file_triggering(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert action_graph(result.operation_graphs) == [(_TEST, _ACT_B)]


def test_trigger_chain(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert action_graph(result.operation_graphs) == [
        (_ACT_B, _ACT_C),
        (_TEST, _ACT_B),
    ]


def test_diamond_trigger_graph_preserves_both_paths(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert action_graph(result.operation_graphs) == [
        (_ACT_B, _SHARED),
        (_ACT_C, _SHARED),
        (_TEST, _ACT_B),
        (_TEST, _ACT_C),
    ]


def test_same_local_position_name_in_unrelated_action_does_not_trigger_it(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert action_graph(result.operation_graphs) == [(_ACT_B, _ACT_A)]


def test_self_trigger(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    assert len(result.program_result.all_diagnostics) == 1
    assert isinstance(
        result.program_result.all_diagnostics[0],
        diagnostics.ActionSelfTriggerDiagnostic,
    )
    assert action_graph(result.operation_graphs) == []


def test_duplicate_action_does_not_add_trigger_edges(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    assert len(result.program_result.all_diagnostics) == 1
    assert isinstance(
        result.program_result.all_diagnostics[0],
        diagnostics.DuplicateDefinitionDiagnostic,
    )
    assert result.program_result.all_diagnostics[0].definition_type == "action"
    assert result.program_result.all_diagnostics[0].path == "/test"
    assert result.program_result.all_diagnostics[0].first_definition_line == 1
    assert result.program_result.all_diagnostics[0].location.line == 10
    assert result.program_result.all_diagnostics[0].location.column == 1
    assert action_graph(result.operation_graphs) == []


def test_local_prefix_before_action_trigger(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert action_graph(result.operation_graphs) == [(_TEST, _OTHER)]


def test_no_body_effect_when_create_target_has_error_state(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    assert len(result.program_result.all_diagnostics) == 1
    assert isinstance(
        result.program_result.all_diagnostics[0],
        diagnostics.MoveFromEmptyPositionDiagnostic,
    )
    assert result.program_result.all_diagnostics[0].position_name == "position<a>"
    assert result.program_result.all_diagnostics[0].location.line == 8
    assert result.program_result.all_diagnostics[0].location.column == 30
    assert (
        result.program_result.all_diagnostics[0].is_action_interface_position is False
    )
    assert result.program_result.all_diagnostics[0].inferred_at is None


def test_no_body_effect_when_move_target_has_error_state(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    assert len(result.program_result.all_diagnostics) == 1
    assert isinstance(
        result.program_result.all_diagnostics[0],
        diagnostics.MoveFromEmptyPositionDiagnostic,
    )
    assert result.program_result.all_diagnostics[0].position_name == "position<a>"
    assert result.program_result.all_diagnostics[0].location.line == 8
    assert result.program_result.all_diagnostics[0].location.column == 30
    assert (
        result.program_result.all_diagnostics[0].is_action_interface_position is False
    )
    assert result.program_result.all_diagnostics[0].inferred_at is None


def test_no_trigger_edge_on_unknown_global_chain_start(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.UnknownGlobalNameDiagnostic)
    assert all_diags[0].source_global_name == "action</other>"
    assert all_diags[0].full_global_name == "action<my.domain.com:my_lib:/other>"
    assert action_graph(result.operation_graphs) == []


class TestConstructorTriggering:
    def test_constructor_create_triggers_action(
        self,
        validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
    ):
        result = validate_testdata_project_with_reference_graph()
        assert_no_errors(result.program_result)
        assert action_graph(result.operation_graphs) == [(_TEST, _OTHER)]

    def test_constructor_move_triggers_action(
        self,
        validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
    ):
        result = validate_testdata_project_with_reference_graph()
        assert_no_errors(result.program_result)
        assert action_graph(result.operation_graphs) == [(_TEST, _OTHER)]

    def test_constructor_fired_via_constraint_records_edge(
        self,
        validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
    ):
        result = validate_testdata_project_with_reference_graph()
        assert_no_errors(result.program_result)
        assert action_graph(result.operation_graphs) == [(_TEST, _P)]


def test_action_interface_reference_with_circular_contract_reports_circular_references(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 3
    assert isinstance(all_diags[0], diagnostics.CircularGlobalReferenceDiagnostic)
    assert all_diags[0].location.line == 11
    assert all_diags[0].location.column == 61
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert isinstance(all_diags[1], diagnostics.UntriggeredActionInterfaceDiagnostic)
    assert all_diags[1].action_name == "action</test>"
    assert (
        all_diags[1].position_name
        == "position<run>::position</pos>::action</test>::position<run>"
    )
    assert all_diags[1].location.line == 11
    assert all_diags[1].location.column == 61
    assert all_diags[1].location.file_path == PurePosixPath("test.dfn")
    assert isinstance(all_diags[2], diagnostics.CircularGlobalReferenceDiagnostic)
    assert all_diags[2].location.line == 3
    assert all_diags[2].location.column == 20
    assert all_diags[2].location.file_path == PurePosixPath("pos.dfn")
