# pyright: reportUnusedCallResult=false

from __future__ import annotations

from define.compiler import conftest, diagnostics
from define.compiler.validator.test_helpers import assert_no_errors

# --- Dead Child Positions ---


def test_unreferenced_child_position_on_local_is_dead(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.DeadChildPositionDiagnostic)
    assert all_diags[0].constraint_name == "position</thing>"
    assert all_diags[0].position_name == "position<box>"
    assert all_diags[0].location.line == 8
    assert all_diags[0].location.column == 28


def test_unreferenced_child_position_on_interface_is_dead(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.DeadChildPositionDiagnostic)
    assert all_diags[0].constraint_name == "position</thing>"
    assert all_diags[0].position_name == "position<run>"
    assert all_diags[0].location.line == 4
    assert all_diags[0].location.column == 24


def test_child_position_referenced_by_create_is_alive(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)


def test_child_position_referenced_as_move_source_is_alive(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)


def test_child_position_required_by_move_destination_is_alive(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)


def test_child_position_required_by_move_destination_through_multiple_hops_is_alive(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)


def test_redundant_destination_constraint_on_move_filled_position_is_dead(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.DeadChildPositionDiagnostic)
    assert all_diags[0].constraint_name == "position</thing>"
    assert all_diags[0].position_name == "position<dest>"
    assert all_diags[0].location.line == 13
    assert all_diags[0].location.column == 28


def test_constraint_on_interface_position_filled_by_create_is_alive(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)


def test_child_name_on_occupied_interface_position_is_alive_with_occupied_implied_position(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)


def test_constraint_on_interface_position_filled_then_destroyed_is_dead(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.DeadChildPositionDiagnostic)
    assert all_diags[0].constraint_name == "position</thing>"
    assert all_diags[0].position_name == "position<iface>"
    assert all_diags[0].location.line == 5
    assert all_diags[0].location.column == 24


def test_constraint_on_interface_position_filled_by_moving_new_particle_is_alive(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)


def test_constraint_on_interface_position_filled_by_moving_caller_particle_is_alive(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)


def test_unused_constraint_on_interface_position_with_inferred_occupied_requirement_is_dead_via_create(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.DeadChildPositionDiagnostic)
    assert all_diags[0].constraint_name == "position</c>"
    assert all_diags[0].position_name == "position<iface>"
    assert all_diags[0].location.line == 6
    assert all_diags[0].location.column == 24


def test_unused_constraint_on_interface_position_with_inferred_occupied_requirement_is_dead_via_move_from_local(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.DeadChildPositionDiagnostic)
    assert all_diags[0].constraint_name == "position</c>"
    assert all_diags[0].position_name == "position<iface>"
    assert all_diags[0].location.line == 6
    assert all_diags[0].location.column == 24


def test_unused_constraint_on_interface_position_with_inferred_occupied_requirement_is_dead_via_move_from_interface(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.DeadChildPositionDiagnostic)
    assert all_diags[0].constraint_name == "position</c>"
    assert all_diags[0].position_name == "position<iface>"
    assert all_diags[0].location.line == 7
    assert all_diags[0].location.column == 24


def test_dead_child_position_inside_constructor(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.DeadChildPositionDiagnostic)
    assert all_diags[0].constraint_name == "position</thing>"
    assert all_diags[0].position_name == "position<box>"
    assert all_diags[0].location.line == 7
    assert all_diags[0].location.column == 28


def test_one_child_position_dead_while_a_sibling_is_referenced(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.DeadChildPositionDiagnostic)
    assert all_diags[0].constraint_name == "position</b>"
    assert all_diags[0].position_name == "position<box>"
    assert all_diags[0].location.line == 9
    assert all_diags[0].location.column == 28


def test_constraint_that_only_provides_a_moved_quality_by_implication_is_dead(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.UntriggeredActionDiagnostic)
    assert all_diags[0].constraint_name == "action</construct>"
    assert all_diags[0].position_name == "position<box2>"
    assert all_diags[0].location.line == 13
    assert all_diags[0].location.column == 28


def test_implied_child_position_of_constructor_is_not_dead(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)


# --- Untriggered Actions ---


def test_untriggered_action_on_local_is_dead(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.UntriggeredActionDiagnostic)
    assert all_diags[0].constraint_name == "action</coin>"
    assert all_diags[0].position_name == "position<box>"
    assert all_diags[0].location.line == 8
    assert all_diags[0].location.column == 28


def test_untriggered_action_on_interface_is_dead(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.UntriggeredActionDiagnostic)
    assert all_diags[0].constraint_name == "action</coin>"
    assert all_diags[0].position_name == "position<run>"
    assert all_diags[0].location.line == 4
    assert all_diags[0].location.column == 24


def test_triggered_action_via_create_is_alive(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)


def test_triggered_action_via_move_is_alive(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)


def test_action_interface_filled_but_never_triggered_is_dead(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.UntriggeredActionDiagnostic)
    assert all_diags[0].constraint_name == "action</twoport>"
    assert all_diags[0].position_name == "position<box>"
    assert all_diags[0].location.line == 8
    assert all_diags[0].location.column == 28


def test_action_required_by_move_destination_is_alive(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)


def test_implied_action_of_constructor_is_not_dead(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)


def test_destructor_constraint_is_never_dead(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 2
    assert isinstance(all_diags[0], diagnostics.DeadChildPositionDiagnostic)
    assert all_diags[0].constraint_name == "position</thing>"
    assert all_diags[0].position_name == "position<box>"
    assert all_diags[0].location.line == 8
    assert all_diags[0].location.column == 28
    assert isinstance(all_diags[1], diagnostics.UntriggeredActionDiagnostic)
    assert all_diags[1].constraint_name == "action</coin>"
    assert all_diags[1].position_name == "position<box>"
    assert all_diags[1].location.line == 10
    assert all_diags[1].location.column == 28


def test_constructor_constraint_reached_only_by_move_is_dead(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.UntriggeredActionDiagnostic)
    assert all_diags[0].constraint_name == "action</construct>"
    assert all_diags[0].position_name == "position<box2>"
    assert all_diags[0].location.line == 17
    assert all_diags[0].location.column == 28


def test_constructor_on_local_position_alive_via_create(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)


def test_constructor_on_interface_position_alive_via_create(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)


def test_constructor_on_interface_position_dead_when_never_created(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.UntriggeredActionDiagnostic)
    assert all_diags[0].constraint_name == "action</construct>"
    assert all_diags[0].position_name == "position<run>"
    assert all_diags[0].location.line == 9
    assert all_diags[0].location.column == 24


# --- Combined and cross-definition cases ---


def test_dead_child_position_and_untriggered_action_on_same_position(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 2
    assert isinstance(all_diags[0], diagnostics.DeadChildPositionDiagnostic)
    assert all_diags[0].constraint_name == "position</thing>"
    assert all_diags[0].position_name == "position<box>"
    assert all_diags[0].location.line == 8
    assert all_diags[0].location.column == 28
    assert isinstance(all_diags[1], diagnostics.UntriggeredActionDiagnostic)
    assert all_diags[1].constraint_name == "action</coin>"
    assert all_diags[1].position_name == "position<box>"
    assert all_diags[1].location.line == 9
    assert all_diags[1].location.column == 28


def test_interface_constraint_referenced_only_in_another_definition_is_dead(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.DeadChildPositionDiagnostic)
    assert all_diags[0].constraint_name == "position</thing>"
    assert all_diags[0].position_name == "position<run>"
    assert all_diags[0].location.line == 4
    assert all_diags[0].location.column == 24
    assert all_diags[0].location.file_path is not None
    assert all_diags[0].location.file_path.name == "consumer.dfn"


def test_child_position_referenced_as_move_target_is_alive(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)


def test_child_position_referenced_only_as_inferred_requirement_intermediate_is_alive(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)


def test_two_child_positions_on_one_position_are_both_dead(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 2
    assert isinstance(all_diags[0], diagnostics.DeadChildPositionDiagnostic)
    assert all_diags[0].constraint_name == "position</a>"
    assert all_diags[0].position_name == "position<box>"
    assert all_diags[0].location.line == 8
    assert all_diags[0].location.column == 28
    assert isinstance(all_diags[1], diagnostics.DeadChildPositionDiagnostic)
    assert all_diags[1].constraint_name == "position</b>"
    assert all_diags[1].position_name == "position<box>"
    assert all_diags[1].location.line == 9
    assert all_diags[1].location.column == 28


def test_unreferenced_constraint_on_global_position_is_not_checked(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
