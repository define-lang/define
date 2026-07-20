# pyright: reportUnusedCallResult=false
from pathlib import PurePosixPath

from define.compiler import conftest, diagnostics
from define.compiler.validator.reference_graph.operation_graph_renderer import (
    action_graph,
)
from define.compiler.validator.test_helpers import assert_no_errors

_TEST = "action<my.domain.com:my_lib:/test>"
_OTHER = "action<my.domain.com:my_lib:/other>"
_ACT_B = "action<my.domain.com:my_lib:/act_b>"
_ACT_C = "action<my.domain.com:my_lib:/act_c>"
_P = "action<my.domain.com:my_lib:/p>"


class TestActionTriggering:
    def test_basic_cross_action_trigger(
        self,
        validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
    ):
        result = validate_testdata_project_with_reference_graph()
        assert_no_errors(result.program_result)
        assert action_graph(result.operation_graphs) == [(_TEST, _OTHER)]

    def test_create_and_move_trigger_other_action(
        self,
        validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
    ):
        result = validate_testdata_project_with_reference_graph()
        assert_no_errors(result.program_result)
        assert action_graph(result.operation_graphs) == [(_TEST, _OTHER)]

    def test_refilling_destroyed_trigger_position_retriggers(
        self,
        validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
    ):
        result = validate_testdata_project_with_reference_graph()
        assert_no_errors(result.program_result)
        assert action_graph(result.operation_graphs) == [
            (_TEST, _OTHER),
            (_TEST, _OTHER),
        ]

    def test_moving_between_two_trigger_positions_fires_both(
        self,
        validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
    ):
        result = validate_testdata_project_with_reference_graph()
        assert_no_errors(result.program_result)
        assert action_graph(result.operation_graphs) == [
            (_TEST, _OTHER),
            (_TEST, _ACT_B),
        ]

    def test_move_from_trigger_position_to_itself_does_not_retrigger(
        self,
        validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
    ):
        result = validate_testdata_project_with_reference_graph()
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

    def test_no_trigger_when_writing_to_non_trigger_position(
        self,
        validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
    ):
        result = validate_testdata_project_with_reference_graph()
        assert_no_errors(result.program_result)
        assert action_graph(result.operation_graphs) == []

    def test_assumed_occupied_trigger_position_does_not_fire_the_action(
        self,
        validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
    ):
        result = validate_testdata_project_with_reference_graph()
        assert action_graph(result.operation_graphs) == []
        all_diags = result.program_result.all_diagnostics
        assert len(all_diags) == 2
        untriggered = all_diags[0]
        assert isinstance(untriggered, diagnostics.UntriggeredActionDiagnostic)
        assert untriggered.constraint_name == "action</inner>"
        assert untriggered.position_name == "position<box>"
        assert untriggered.location.line == 8
        assert untriggered.location.column == 24
        assert untriggered.location.end_line == 8
        assert untriggered.location.end_column == 38
        assert untriggered.location.file_path == PurePosixPath("test.dfn")
        dead_child = all_diags[1]
        assert isinstance(dead_child, diagnostics.DeadChildPositionDiagnostic)
        assert dead_child.constraint_name == "position</a>"
        assert dead_child.position_name == "position<run>"
        assert dead_child.location.line == 4
        assert dead_child.location.column == 24
        assert dead_child.location.end_line == 4
        assert dead_child.location.end_column == 36
        assert dead_child.location.file_path == PurePosixPath("inner.dfn")

    def test_cross_file_triggering(
        self,
        validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
    ):
        result = validate_testdata_project_with_reference_graph()
        assert_no_errors(result.program_result)
        assert action_graph(result.operation_graphs) == [(_TEST, _ACT_B)]

    def test_trigger_chain(
        self,
        validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
    ):
        result = validate_testdata_project_with_reference_graph()
        assert_no_errors(result.program_result)
        assert action_graph(result.operation_graphs) == [
            (_ACT_B, _ACT_C),
            (_TEST, _ACT_B),
        ]

    def test_self_trigger(
        self,
        validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
    ):
        result = validate_testdata_project_with_reference_graph()
        assert len(result.program_result.all_diagnostics) == 1
        assert isinstance(
            result.program_result.all_diagnostics[0],
            diagnostics.ActionSelfTriggerDiagnostic,
        )
        assert action_graph(result.operation_graphs) == []

    def test_duplicate_action_does_not_add_trigger_edges(
        self,
        validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
    ):
        result = validate_testdata_project_with_reference_graph()
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
        self,
        validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
    ):
        result = validate_testdata_project_with_reference_graph()
        assert_no_errors(result.program_result)
        assert action_graph(result.operation_graphs) == [(_TEST, _OTHER)]

    def test_no_body_effect_when_create_target_has_error_state(
        self,
        validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
    ):
        result = validate_testdata_project_with_reference_graph()
        assert len(result.program_result.all_diagnostics) == 1
        assert isinstance(
            result.program_result.all_diagnostics[0],
            diagnostics.MoveFromEmptyPositionDiagnostic,
        )
        assert result.program_result.all_diagnostics[0].position_name == "position<a>"
        assert result.program_result.all_diagnostics[0].location.line == 8
        assert result.program_result.all_diagnostics[0].location.column == 30
        assert (
            result.program_result.all_diagnostics[0].is_action_interface_position
            is False
        )
        assert result.program_result.all_diagnostics[0].inferred_at is None

    def test_no_body_effect_when_move_target_has_error_state(
        self,
        validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
    ):
        result = validate_testdata_project_with_reference_graph()
        assert len(result.program_result.all_diagnostics) == 1
        assert isinstance(
            result.program_result.all_diagnostics[0],
            diagnostics.MoveFromEmptyPositionDiagnostic,
        )
        assert result.program_result.all_diagnostics[0].position_name == "position<a>"
        assert result.program_result.all_diagnostics[0].location.line == 8
        assert result.program_result.all_diagnostics[0].location.column == 30
        assert (
            result.program_result.all_diagnostics[0].is_action_interface_position
            is False
        )
        assert result.program_result.all_diagnostics[0].inferred_at is None


class TestUnknownGlobalNoTrigger:
    def test_no_trigger_edge_on_unknown_global_chain_start(
        self,
        validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
    ):
        result = validate_testdata_project_with_reference_graph()
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

    def test_constructor_no_edge_when_non_trigger_position(
        self,
        validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
    ):
        result = validate_testdata_project_with_reference_graph()
        assert_no_errors(result.program_result)
        assert action_graph(result.operation_graphs) == []

    def test_constructor_fired_via_constraint_records_edge(
        self,
        validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
    ):
        result = validate_testdata_project_with_reference_graph()
        assert_no_errors(result.program_result)
        assert action_graph(result.operation_graphs) == [(_TEST, _P)]


class TestCircularDependencyTriggering:
    def test_circular_dependency_skips_trigger_check(
        self,
        validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
    ):
        result = validate_testdata_project_with_reference_graph()
        all_diags = result.program_result.all_diagnostics
        assert len(all_diags) == 1
        assert isinstance(all_diags[0], diagnostics.CircularGlobalReferenceDiagnostic)
        assert all_diags[0].location.line == 3
        assert all_diags[0].location.column == 20
