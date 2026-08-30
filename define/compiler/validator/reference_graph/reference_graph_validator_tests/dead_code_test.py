# pyright: reportUnusedCallResult=false

from __future__ import annotations

from pathlib import PurePosixPath

from define.compiler import conftest, diagnostics
from define.compiler.validator.reference_graph.operation_graph_renderer import (
    action_graph,
)
from define.compiler.validator.test_helpers import assert_no_errors

_RUNNER = "action<my.domain.com:my_lib:/runner>"
_MIDDLE = "action<my.domain.com:my_lib:/middle>"
_GRANDCHILD = "action<my.domain.com:my_lib:/grandchild>"
_TEST = "action<my.domain.com:my_lib:/test>"
_WORKER = "action<my.domain.com:my_lib:/worker>"

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


def test_unresolved_constraint_is_not_reported_as_dead(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.ReferencedFileNotFoundDiagnostic)
    assert all_diags[0].file_path == "missing.dfn"
    assert all_diags[0].location.line == 5
    assert all_diags[0].location.column == 33
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")


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


def test_position_constraint_moved_through_locals_to_contract_is_alive(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert action_graph(result.operation_graphs) == []


def test_position_constraint_moved_through_locals_to_child_contract_is_alive(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert action_graph(result.operation_graphs) == []


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


def test_back_and_forth_moves_do_not_make_position_constraints_alive(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 2
    assert isinstance(all_diags[0], diagnostics.DeadChildPositionDiagnostic)
    assert all_diags[0].constraint_name == "position</thing>"
    assert all_diags[0].position_name == "position<first>"
    assert all_diags[0].location.line == 8
    assert all_diags[0].location.column == 28
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert isinstance(all_diags[1], diagnostics.DeadChildPositionDiagnostic)
    assert all_diags[1].constraint_name == "position</thing>"
    assert all_diags[1].position_name == "position<second>"
    assert all_diags[1].location.line == 13
    assert all_diags[1].location.column == 28
    assert all_diags[1].location.file_path == PurePosixPath("test.dfn")
    assert action_graph(result.operation_graphs) == []


def test_constraint_on_interface_position_filled_by_create_is_alive(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)


def test_multiple_constraints_on_guaranteed_interface_position_are_alive(
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
    assert len(all_diags) == 2
    assert isinstance(all_diags[0], diagnostics.UntriggeredActionDiagnostic)
    assert all_diags[0].constraint_name == "action</twoport>"
    assert all_diags[0].position_name == "position<box>"
    assert all_diags[0].location.line == 8
    assert all_diags[0].location.column == 28
    assert isinstance(all_diags[1], diagnostics.UntriggeredActionInterfaceDiagnostic)
    assert all_diags[1].action_name == "action</twoport>"
    assert all_diags[1].position_name == (
        "position<box>::action</twoport>::position<slot>"
    )
    assert all_diags[1].location.line == 12
    assert all_diags[1].location.column == 45
    assert all_diags[1].location.file_path == PurePosixPath("test.dfn")


def test_action_interface_occupation_requires_trigger_when_constraint_is_alive_via_guarantee(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.UntriggeredActionInterfaceDiagnostic)
    assert all_diags[0].action_name == "action</worker>"
    assert all_diags[0].position_name == (
        "position<box>::action</worker>::position<input>"
    )
    assert all_diags[0].location.line == 12
    assert all_diags[0].location.column == 45
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert action_graph(result.operation_graphs) == []


def test_action_interface_occupation_survives_particle_move_out_without_trigger(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.UntriggeredActionInterfaceDiagnostic)
    assert all_diags[0].action_name == "action</worker>"
    assert all_diags[0].position_name == (
        "position<box>::action</worker>::position<input>"
    )
    assert all_diags[0].location.line == 15
    assert all_diags[0].location.column == 65
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert action_graph(result.operation_graphs) == []


def test_action_interface_occupation_survives_parent_and_particle_moves_without_trigger(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.UntriggeredActionInterfaceDiagnostic)
    assert all_diags[0].action_name == "action</worker>"
    assert all_diags[0].position_name == (
        "position<source>::action</worker>::position<input>"
    )
    assert all_diags[0].location.line == 20
    assert all_diags[0].location.column == 68
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert action_graph(result.operation_graphs) == []


def test_action_trigger_after_interface_particle_replacement_is_alive(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(
        all_diags[0],
        diagnostics.UntriggeredActionInterfaceDiagnostic,
    )
    assert all_diags[0].action_name == "action</worker>"
    assert all_diags[0].position_name == (
        "position<box>::action</worker>::position<input>"
    )
    assert all_diags[0].location.line == 15
    assert all_diags[0].location.column == 60
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert action_graph(result.operation_graphs) == [(_TEST, _WORKER)]


def test_action_interface_particle_can_depart_after_trigger(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert action_graph(result.operation_graphs) == [(_TEST, _WORKER)]


def test_action_interface_particle_arriving_after_trigger_cannot_depart_before_next_trigger(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(
        all_diags[0],
        diagnostics.UntriggeredActionInterfaceDiagnostic,
    )
    assert all_diags[0].action_name == "action</worker>"
    assert all_diags[0].position_name == (
        "position<box>::action</worker>::position<input>"
    )
    assert all_diags[0].location.line == 17
    assert all_diags[0].location.column == 45
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert action_graph(result.operation_graphs) == [
        (_TEST, _WORKER),
        (_TEST, _WORKER),
    ]


def test_action_interface_particle_arriving_after_last_trigger_is_dead(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.UntriggeredActionInterfaceDiagnostic)
    assert all_diags[0].action_name == "action</worker>"
    assert all_diags[0].position_name == (
        "position<box>::action</worker>::position<input>"
    )
    assert all_diags[0].location.line == 14
    assert all_diags[0].location.column == 45
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert action_graph(result.operation_graphs) == [(_TEST, _WORKER)]


def test_guaranteed_interface_particle_departure_leaves_pending_arrival(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.UntriggeredActionInterfaceDiagnostic)
    assert all_diags[0].action_name == "action</worker>"
    assert all_diags[0].position_name == (
        "position<box>::action</worker>::position<input>"
    )
    assert all_diags[0].location.line == 15
    assert all_diags[0].location.column == 45
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert action_graph(result.operation_graphs) == [(_TEST, _WORKER)]


def test_action_trigger_only_satisfies_arrivals_for_its_parent_particle(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.UntriggeredActionInterfaceDiagnostic)
    assert all_diags[0].action_name == "action</worker>"
    assert all_diags[0].position_name == (
        "position<box>::action</worker>::position<input>"
    )
    assert all_diags[0].location.line == 13
    assert all_diags[0].location.column == 45
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert action_graph(result.operation_graphs) == [(_TEST, _WORKER)]


def test_action_interface_child_destroyed_before_trigger_is_dead(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.UntriggeredActionInterfaceDiagnostic)
    assert all_diags[0].action_name == "action</worker>"
    assert all_diags[0].position_name == (
        "position<box>::action</worker>::position<input>::position</child>"
    )
    assert all_diags[0].location.line == 13
    assert all_diags[0].location.column == 45
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert action_graph(result.operation_graphs) == [(_TEST, _WORKER)]


def test_action_interface_child_destroyed_with_parent_before_trigger_is_dead(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 2
    assert isinstance(all_diags[0], diagnostics.UntriggeredActionInterfaceDiagnostic)
    assert all_diags[0].action_name == "action</worker>"
    assert all_diags[0].position_name == (
        "position<box>::action</worker>::position<input>"
    )
    assert all_diags[0].location.line == 12
    assert all_diags[0].location.column == 45
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert isinstance(all_diags[1], diagnostics.UntriggeredActionInterfaceDiagnostic)
    assert all_diags[1].action_name == "action</worker>"
    assert all_diags[1].position_name == (
        "position<box>::action</worker>::position<input>::position</child>"
    )
    assert all_diags[1].location.line == 13
    assert all_diags[1].location.column == 45
    assert all_diags[1].location.file_path == PurePosixPath("test.dfn")
    assert action_graph(result.operation_graphs) == [(_TEST, _WORKER)]


def test_action_interface_child_moved_before_trigger_is_dead(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.UntriggeredActionInterfaceDiagnostic)
    assert all_diags[0].action_name == "action</worker>"
    assert all_diags[0].position_name == (
        "position<box>::action</worker>::position<input>::position</child>"
    )
    assert all_diags[0].location.line == 16
    assert all_diags[0].location.column == 65
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert action_graph(result.operation_graphs) == [(_TEST, _WORKER)]


def test_action_interface_child_survives_until_trigger(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert action_graph(result.operation_graphs) == [(_TEST, _WORKER)]


def test_action_on_occupied_interface_referenced_but_never_triggered_is_dead(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 2
    assert isinstance(all_diags[0], diagnostics.UntriggeredActionDiagnostic)
    assert all_diags[0].constraint_name == "action</worker>"
    assert all_diags[0].position_name == "position<box>"
    assert all_diags[0].location.line == 5
    assert all_diags[0].location.column == 24
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert isinstance(all_diags[1], diagnostics.UntriggeredActionInterfaceDiagnostic)
    assert all_diags[1].action_name == "action</worker>"
    assert (
        all_diags[1].position_name == "position<box>::action</worker>::position<input>"
    )
    assert all_diags[1].location.line == 12
    assert all_diags[1].location.column == 45
    assert all_diags[1].location.file_path == PurePosixPath("test.dfn")
    assert action_graph(result.operation_graphs) == []


def test_move_from_empty_action_interface_does_not_mark_action_alive(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 2
    assert isinstance(all_diags[0], diagnostics.UntriggeredActionDiagnostic)
    assert all_diags[0].constraint_name == "action</worker>"
    assert all_diags[0].position_name == "position<box>"
    assert all_diags[0].location.line == 5
    assert all_diags[0].location.column == 24
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert isinstance(all_diags[1], diagnostics.MoveFromEmptyPositionDiagnostic)
    assert (
        all_diags[1].position_name == "position<box>::action</worker>::position<input>"
    )
    assert all_diags[1].is_action_interface_position is True
    assert all_diags[1].inferred_at is None
    assert all_diags[1].location.line == 12
    assert all_diags[1].location.column == 30
    assert all_diags[1].location.file_path == PurePosixPath("test.dfn")
    assert action_graph(result.operation_graphs) == []


def test_transitive_action_interface_occupied_without_trigger_is_dead(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 2
    assert isinstance(
        all_diags[0],
        diagnostics.OccupiedActionInterfaceWhenActionTriggersDiagnostic,
    )
    assert all_diags[0].action_name == "action</middle>"
    assert (
        all_diags[0].position_name
        == "position<wrapper>::action</middle>::position<box>::action</worker>::position<input>"
    )
    assert all_diags[0].location.line == 12
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("runner.dfn")
    assert isinstance(all_diags[1], diagnostics.UntriggeredActionInterfaceDiagnostic)
    assert all_diags[1].action_name == "action</worker>"
    assert (
        all_diags[1].position_name
        == "position<wrapper>::action</middle>::position<box>::action</worker>::position<input>"
    )
    assert all_diags[1].location.line == 12
    assert all_diags[1].location.column == 81
    assert all_diags[1].location.file_path == PurePosixPath("runner.dfn")
    assert action_graph(result.operation_graphs) == [
        (_MIDDLE, _WORKER),
        (_RUNNER, _MIDDLE),
        (_TEST, _RUNNER),
    ]


def test_transitive_action_interface_particle_destroyed_before_trigger_is_dead(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.UntriggeredActionInterfaceDiagnostic)
    assert all_diags[0].action_name == "action</worker>"
    assert all_diags[0].position_name == (
        "position<wrapper>::action</middle>::position<box>::action</worker>::position<input>"
    )
    assert all_diags[0].location.line == 12
    assert all_diags[0].location.column == 81
    assert all_diags[0].location.file_path == PurePosixPath("runner.dfn")
    assert action_graph(result.operation_graphs) == [
        (_MIDDLE, _WORKER),
        (_RUNNER, _MIDDLE),
        (_TEST, _RUNNER),
    ]


def test_child_action_interface_arrival_does_not_require_parent_to_trigger_again(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert action_graph(result.operation_graphs) == [
        (_RUNNER, _MIDDLE),
        (_RUNNER, _WORKER),
        (_TEST, _RUNNER),
    ]


def test_grandchild_action_interface_arrival_does_not_require_ancestors_to_trigger_again(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert action_graph(result.operation_graphs) == [
        (_RUNNER, _MIDDLE),
        (_RUNNER, _WORKER),
        (_RUNNER, _GRANDCHILD),
        (_TEST, _RUNNER),
    ]


def test_implied_action_referenced_but_never_triggered_is_dead(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 2
    assert isinstance(all_diags[0], diagnostics.UntriggeredImpliedActionDiagnostic)
    assert all_diags[0].implied_action_name == "action</worker>"
    assert all_diags[0].location.line == 2
    assert all_diags[0].location.column == 25
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert isinstance(all_diags[1], diagnostics.UntriggeredActionInterfaceDiagnostic)
    assert all_diags[1].action_name == "action</worker>"
    assert all_diags[1].position_name == "action</worker>::position<input>"
    assert all_diags[1].location.line == 7
    assert all_diags[1].location.column == 30
    assert all_diags[1].location.file_path == PurePosixPath("test.dfn")
    assert action_graph(result.operation_graphs) == []


def test_implied_action_interface_child_without_trigger_is_dead(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 3
    assert isinstance(all_diags[0], diagnostics.UntriggeredImpliedActionDiagnostic)
    assert all_diags[0].implied_action_name == "action</worker>"
    assert all_diags[0].location.line == 2
    assert all_diags[0].location.column == 25
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert isinstance(all_diags[1], diagnostics.UntriggeredActionInterfaceDiagnostic)
    assert all_diags[1].action_name == "action</worker>"
    assert all_diags[1].position_name == "action</worker>::position<input>"
    assert all_diags[1].location.line == 7
    assert all_diags[1].location.column == 30
    assert all_diags[1].location.file_path == PurePosixPath("test.dfn")
    assert isinstance(all_diags[2], diagnostics.UntriggeredActionInterfaceDiagnostic)
    assert all_diags[2].action_name == "action</worker>"
    assert all_diags[2].position_name == (
        "action</worker>::position<input>::position</child>"
    )
    assert all_diags[2].location.line == 8
    assert all_diags[2].location.column == 30
    assert all_diags[2].location.file_path == PurePosixPath("test.dfn")
    assert action_graph(result.operation_graphs) == []


def test_implied_action_interface_child_then_triggered_is_alive(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert action_graph(result.operation_graphs) == [(_TEST, _WORKER)]


def test_multiple_implied_actions_referenced_but_never_triggered_are_dead(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 4
    assert isinstance(all_diags[0], diagnostics.UntriggeredImpliedActionDiagnostic)
    assert all_diags[0].implied_action_name == "action</first>"
    assert all_diags[0].location.line == 2
    assert all_diags[0].location.column == 25
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert isinstance(all_diags[1], diagnostics.UntriggeredImpliedActionDiagnostic)
    assert all_diags[1].implied_action_name == "action</second>"
    assert all_diags[1].location.line == 3
    assert all_diags[1].location.column == 25
    assert all_diags[1].location.file_path == PurePosixPath("test.dfn")
    assert isinstance(all_diags[2], diagnostics.UntriggeredActionInterfaceDiagnostic)
    assert all_diags[2].action_name == "action</first>"
    assert all_diags[2].position_name == "action</first>::position<input>"
    assert all_diags[2].location.line == 8
    assert all_diags[2].location.column == 30
    assert all_diags[2].location.file_path == PurePosixPath("test.dfn")
    assert isinstance(all_diags[3], diagnostics.UntriggeredActionInterfaceDiagnostic)
    assert all_diags[3].action_name == "action</second>"
    assert all_diags[3].position_name == "action</second>::position<input>"
    assert all_diags[3].location.line == 9
    assert all_diags[3].location.column == 30
    assert all_diags[3].location.file_path == PurePosixPath("test.dfn")
    assert action_graph(result.operation_graphs) == []


def test_destructor_cannot_be_implied(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 2
    assert isinstance(all_diags[0], diagnostics.UntriggeredImpliedActionDiagnostic)
    assert all_diags[0].implied_action_name == "action</cleanup>"
    assert all_diags[0].location.line == 2
    assert all_diags[0].location.column == 25
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert isinstance(all_diags[1], diagnostics.UntriggeredActionInterfaceDiagnostic)
    assert all_diags[1].action_name == "action</cleanup>"
    assert all_diags[1].position_name == "action</cleanup>::position<child>"
    assert all_diags[1].location.line == 7
    assert all_diags[1].location.column == 30
    assert all_diags[1].location.file_path == PurePosixPath("test.dfn")
    assert action_graph(result.operation_graphs) == []


def test_nested_trigger_marks_only_final_implied_action_alive(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 2
    assert isinstance(all_diags[0], diagnostics.UntriggeredImpliedActionDiagnostic)
    assert all_diags[0].implied_action_name == "action</runner>"
    assert all_diags[0].location.line == 2
    assert all_diags[0].location.column == 25
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert isinstance(all_diags[1], diagnostics.UntriggeredActionInterfaceDiagnostic)
    assert all_diags[1].action_name == "action</runner>"
    assert all_diags[1].position_name == "action</runner>::position<iface>"
    assert all_diags[1].location.line == 7
    assert all_diags[1].location.column == 30
    assert all_diags[1].location.file_path == PurePosixPath("test.dfn")
    assert action_graph(result.operation_graphs) == [
        (_RUNNER, _WORKER),
        (_TEST, _WORKER),
    ]


def test_nested_non_trigger_marks_no_implied_action_alive(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 3
    assert isinstance(all_diags[0], diagnostics.UntriggeredImpliedActionDiagnostic)
    assert all_diags[0].implied_action_name == "action</runner>"
    assert all_diags[0].location.line == 2
    assert all_diags[0].location.column == 25
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert isinstance(all_diags[1], diagnostics.UntriggeredActionInterfaceDiagnostic)
    assert all_diags[1].action_name == "action</runner>"
    assert all_diags[1].position_name == "action</runner>::position<iface>"
    assert all_diags[1].location.line == 7
    assert all_diags[1].location.column == 30
    assert all_diags[1].location.file_path == PurePosixPath("test.dfn")
    assert isinstance(all_diags[2], diagnostics.UntriggeredActionInterfaceDiagnostic)
    assert all_diags[2].action_name == "action</worker>"
    assert all_diags[2].position_name == (
        "action</runner>::position<iface>::action</worker>::position<non_trigger>"
    )
    assert all_diags[2].location.line == 8
    assert all_diags[2].location.column == 64
    assert all_diags[2].location.file_path == PurePosixPath("test.dfn")
    assert action_graph(result.operation_graphs) == [(_RUNNER, _WORKER)]


def test_action_required_by_move_destination_is_alive(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)


def test_position_constraint_moved_to_untriggered_action_contract_is_dead(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 3
    assert isinstance(all_diags[0], diagnostics.UntriggeredActionDiagnostic)
    assert all_diags[0].constraint_name == "action</consumer>"
    assert all_diags[0].position_name == "position<holder>"
    assert all_diags[0].location.line == 8
    assert all_diags[0].location.column == 28
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert isinstance(all_diags[1], diagnostics.DeadChildPositionDiagnostic)
    assert all_diags[1].constraint_name == "position</thing>"
    assert all_diags[1].position_name == "position<source>"
    assert all_diags[1].location.line == 13
    assert all_diags[1].location.column == 28
    assert all_diags[1].location.file_path == PurePosixPath("test.dfn")
    assert isinstance(all_diags[2], diagnostics.UntriggeredActionInterfaceDiagnostic)
    assert all_diags[2].action_name == "action</consumer>"
    assert all_diags[2].position_name == (
        "position<holder>::action</consumer>::position<input>"
    )
    assert all_diags[2].location.line == 18
    assert all_diags[2].location.column == 68
    assert all_diags[2].location.file_path == PurePosixPath("test.dfn")
    assert action_graph(result.operation_graphs) == []


def test_position_constraint_moved_to_triggered_action_contract_is_alive(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert action_graph(result.operation_graphs) == [
        (_TEST, "action<my.domain.com:my_lib:/consumer>")
    ]


def test_action_constraint_moved_to_triggered_action_contract_is_alive(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert action_graph(result.operation_graphs) == [
        ("action<my.domain.com:my_lib:/consumer>", _WORKER),
        (_TEST, "action<my.domain.com:my_lib:/consumer>"),
    ]


def test_back_and_forth_moves_do_not_make_action_constraints_alive(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 2
    assert isinstance(all_diags[0], diagnostics.UntriggeredActionDiagnostic)
    assert all_diags[0].constraint_name == "action</worker>"
    assert all_diags[0].position_name == "position<first>"
    assert all_diags[0].location.line == 8
    assert all_diags[0].location.column == 28
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert isinstance(all_diags[1], diagnostics.UntriggeredActionDiagnostic)
    assert all_diags[1].constraint_name == "action</worker>"
    assert all_diags[1].position_name == "position<second>"
    assert all_diags[1].location.line == 13
    assert all_diags[1].location.column == 28
    assert all_diags[1].location.file_path == PurePosixPath("test.dfn")
    assert action_graph(result.operation_graphs) == []


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
