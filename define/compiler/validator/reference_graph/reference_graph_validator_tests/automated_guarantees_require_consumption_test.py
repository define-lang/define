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

_CHILD = "action<my.domain.com:my_lib:/child>"
_CONSTRUCT = "action<my.domain.com:my_lib:/construct>"
_PARENT = "action<my.domain.com:my_lib:/parent>"
_TEST = "action<my.domain.com:my_lib:/test>"
_WORKER = "action<my.domain.com:my_lib:/worker>"


def test_triggered_action_interface_particle_must_depart_before_caller_ends(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    diagnostic = all_diags[0]
    assert isinstance(diagnostic, diagnostics.UnconsumedActionInterfaceDiagnostic)
    assert diagnostic.action_name == "action</worker>"
    assert (
        diagnostic.position_name == "position<box>::action</worker>::position<result>"
    )
    assert diagnostic.location.line == 11
    assert diagnostic.location.column == 45
    assert diagnostic.location.file_path == PurePosixPath("test.dfn")
    assert action_graph(result.operation_graphs) == [(_TEST, _WORKER)]


def test_same_action_on_two_particles_requires_both_interfaces_consumed(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 2
    first_diagnostic = all_diags[0]
    assert isinstance(first_diagnostic, diagnostics.UnconsumedActionInterfaceDiagnostic)
    assert first_diagnostic.action_name == "action</worker>"
    assert (
        first_diagnostic.position_name
        == "position<box_a>::action</worker>::position<result>"
    )
    assert first_diagnostic.location.line == 16
    assert first_diagnostic.location.column == 47
    assert first_diagnostic.location.file_path == PurePosixPath("test.dfn")
    second_diagnostic = all_diags[1]
    assert isinstance(
        second_diagnostic, diagnostics.UnconsumedActionInterfaceDiagnostic
    )
    assert second_diagnostic.action_name == "action</worker>"
    assert (
        second_diagnostic.position_name
        == "position<box_b>::action</worker>::position<result>"
    )
    assert second_diagnostic.location.line == 18
    assert second_diagnostic.location.column == 47
    assert second_diagnostic.location.file_path == PurePosixPath("test.dfn")
    assert action_graph(result.operation_graphs) == [
        (_TEST, _WORKER),
        (_TEST, _WORKER),
    ]


def test_consuming_one_of_two_instances_of_same_action_leaves_other_unconsumed(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    diagnostic = all_diags[0]
    assert isinstance(diagnostic, diagnostics.UnconsumedActionInterfaceDiagnostic)
    assert diagnostic.action_name == "action</worker>"
    assert (
        diagnostic.position_name == "position<box_b>::action</worker>::position<result>"
    )
    assert diagnostic.location.line == 18
    assert diagnostic.location.column == 47
    assert diagnostic.location.file_path == PurePosixPath("test.dfn")
    assert action_graph(result.operation_graphs) == [
        (_TEST, _WORKER),
        (_TEST, _WORKER),
    ]


def test_destroyed_action_parent_does_not_duplicate_replacement_diagnostic(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    diagnostic = all_diags[0]
    assert isinstance(diagnostic, diagnostics.UnconsumedActionInterfaceDiagnostic)
    assert diagnostic.action_name == "action</worker>"
    assert (
        diagnostic.position_name == "position<box>::action</worker>::position<result>"
    )
    assert diagnostic.location.line == 14
    assert diagnostic.location.column == 45
    assert diagnostic.location.file_path == PurePosixPath("test.dfn")
    assert action_graph(result.operation_graphs) == [
        (_TEST, _WORKER),
        (_TEST, _WORKER),
    ]


def test_retriggered_action_interface_particle_may_depart_before_caller_ends(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert action_graph(result.operation_graphs) == [
        (_TEST, _WORKER),
        (_TEST, _WORKER),
    ]


def test_retriggered_action_interface_particle_must_depart_before_caller_ends(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    diagnostic = all_diags[0]
    assert isinstance(diagnostic, diagnostics.UnconsumedActionInterfaceDiagnostic)
    assert diagnostic.action_name == "action</worker>"
    assert diagnostic.position_name == "position<box>::action</worker>::position<input>"
    assert diagnostic.location.line == 13
    assert diagnostic.location.column == 45
    assert diagnostic.location.file_path == PurePosixPath("test.dfn")
    assert action_graph(result.operation_graphs) == [
        (_TEST, _WORKER),
        (_TEST, _WORKER),
    ]


def test_caller_move_between_callee_interfaces_does_not_consume_particle(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    diagnostic = all_diags[0]
    assert isinstance(diagnostic, diagnostics.UnconsumedActionInterfaceDiagnostic)
    assert diagnostic.action_name == "action</worker>"
    assert (
        diagnostic.position_name == "position<box>::action</worker>::position<result>"
    )
    assert diagnostic.location.line == 14
    assert diagnostic.location.column == 45
    assert diagnostic.location.file_path == PurePosixPath("test.dfn")
    assert action_graph(result.operation_graphs) == [
        (_TEST, _WORKER),
        (_TEST, _WORKER),
    ]


def test_callee_move_between_its_interfaces_requires_caller_consumption(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    diagnostic = all_diags[0]
    assert isinstance(diagnostic, diagnostics.UnconsumedActionInterfaceDiagnostic)
    assert diagnostic.action_name == "action</worker>"
    assert (
        diagnostic.position_name == "position<box>::action</worker>::position<result>"
    )
    assert diagnostic.location.line == 11
    assert diagnostic.location.column == 45
    assert diagnostic.location.file_path == PurePosixPath("test.dfn")
    assert action_graph(result.operation_graphs) == [(_TEST, _WORKER)]


def test_constructor_interface_particle_must_depart_before_caller_ends(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    diagnostic = all_diags[0]
    assert isinstance(diagnostic, diagnostics.UnconsumedActionInterfaceDiagnostic)
    assert diagnostic.action_name == "action</construct>"
    assert (
        diagnostic.position_name
        == "position<box>::action</construct>::position<result>"
    )
    assert diagnostic.location.line == 4
    assert diagnostic.location.column == 24
    assert diagnostic.location.file_path == PurePosixPath("test.dfn")
    assert action_graph(result.operation_graphs) == [(_TEST, _CONSTRUCT)]


def test_local_parent_auto_destruction_consumes_action_interface_particle(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert action_graph(result.operation_graphs) == [(_TEST, _WORKER)]


def test_deeper_action_implied_position_can_leave_with_interface_particle(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert action_graph(result.operation_graphs) == [
        (_TEST, _PARENT),
        (_TEST, _CHILD),
    ]


def test_child_guarantee_must_be_consumed_before_parent_triggers(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diagnostics = result.program_result.all_diagnostics
    assert len(all_diagnostics) == 1
    diagnostic = all_diagnostics[0]
    assert isinstance(
        diagnostic,
        diagnostics.OccupiedActionInterfaceWhenActionTriggersDiagnostic,
    )
    assert diagnostic.action_name == "action</parent>"
    assert (
        diagnostic.position_name
        == "position<box>::action</parent>::position<iface>::action</child>::position<result>"
    )
    assert diagnostic.location.line == 13
    assert diagnostic.location.column == 79
    assert diagnostic.location.file_path == PurePosixPath("test.dfn")
    assert action_graph(result.operation_graphs) == [
        (_PARENT, _CHILD),
        (_TEST, _CHILD),
        (_TEST, _PARENT),
    ]


def test_particle_with_child_guarantee_must_be_clean_before_moving_to_parent_interface(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diagnostics = result.program_result.all_diagnostics
    assert len(all_diagnostics) == 1
    diagnostic = all_diagnostics[0]
    assert isinstance(
        diagnostic,
        diagnostics.OccupiedActionInterfaceWhenActionTriggersDiagnostic,
    )
    assert diagnostic.action_name == "action</parent>"
    assert (
        diagnostic.position_name
        == "position<box>::action</parent>::position<iface>::action</child>::position<result>"
    )
    assert diagnostic.location.line == 19
    assert diagnostic.location.column == 50
    assert diagnostic.location.file_path == PurePosixPath("test.dfn")
    assert action_graph(result.operation_graphs) == [
        (_PARENT, _CHILD),
        (_TEST, _CHILD),
        (_TEST, _PARENT),
    ]


def test_one_move_of_multiple_occupied_child_action_interfaces_reports_each_position(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diagnostics = result.program_result.all_diagnostics
    assert len(all_diagnostics) == 2
    first_diagnostic = all_diagnostics[0]
    assert isinstance(
        first_diagnostic,
        diagnostics.OccupiedActionInterfaceWhenActionTriggersDiagnostic,
    )
    assert first_diagnostic.action_name == "action</parent>"
    assert (
        first_diagnostic.position_name
        == "position<box>::action</parent>::position<iface>::action</child>::position<result_a>"
    )
    assert first_diagnostic.location.line == 20
    assert first_diagnostic.location.column == 50
    assert first_diagnostic.location.file_path == PurePosixPath("test.dfn")
    second_diagnostic = all_diagnostics[1]
    assert isinstance(
        second_diagnostic,
        diagnostics.OccupiedActionInterfaceWhenActionTriggersDiagnostic,
    )
    assert second_diagnostic.action_name == "action</parent>"
    assert (
        second_diagnostic.position_name
        == "position<box>::action</parent>::position<iface>::action</child>::position<result_b>"
    )
    assert second_diagnostic.location.line == 20
    assert second_diagnostic.location.column == 50
    assert second_diagnostic.location.file_path == PurePosixPath("test.dfn")
    assert action_graph(result.operation_graphs) == [
        (_PARENT, _CHILD),
        (_TEST, _CHILD),
        (_TEST, _PARENT),
    ]


def test_child_guarantee_after_parent_move_is_diagnostic_source(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diagnostics = result.program_result.all_diagnostics
    assert len(all_diagnostics) == 2
    diagnostic = all_diagnostics[0]
    assert isinstance(
        diagnostic,
        diagnostics.OccupiedActionInterfaceWhenActionTriggersDiagnostic,
    )
    assert diagnostic.action_name == "action</parent>"
    assert (
        diagnostic.position_name
        == "position<box>::action</parent>::position<iface>::position</branch>::action</child>::position<result>"
    )
    assert diagnostic.location.line == 19
    assert diagnostic.location.column == 98
    assert diagnostic.location.file_path == PurePosixPath("test.dfn")
    requirement_diagnostic = all_diagnostics[1]
    assert isinstance(
        requirement_diagnostic,
        diagnostics.InferredRequirementViolationDiagnostic,
    )
    assert requirement_diagnostic.action_name == "action<my.domain.com:my_lib:/parent>"
    assert requirement_diagnostic.required_empty is True
    assert (
        requirement_diagnostic.position_name
        == "position<box>::action</parent>::position<iface>::position</branch>::action</child>::position<result>"
    )
    assert requirement_diagnostic.location.line == 20
    assert requirement_diagnostic.location.column == 30
    assert requirement_diagnostic.location.file_path == PurePosixPath("test.dfn")
    assert action_graph(result.operation_graphs) == [
        (_PARENT, _CHILD),
        (_TEST, _CHILD),
        (_TEST, _PARENT),
    ]


def test_action_on_position_child_must_be_clean_before_parent_triggers(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diagnostics = result.program_result.all_diagnostics
    assert len(all_diagnostics) == 1
    diagnostic = all_diagnostics[0]
    assert isinstance(
        diagnostic,
        diagnostics.OccupiedActionInterfaceWhenActionTriggersDiagnostic,
    )
    assert diagnostic.action_name == "action</parent>"
    assert (
        diagnostic.position_name
        == "position<box>::action</parent>::position<iface>::position</branch>::action</child>::position<result>"
    )
    assert diagnostic.location.line == 14
    assert diagnostic.location.column == 98
    assert diagnostic.location.file_path == PurePosixPath("test.dfn")
    assert action_graph(result.operation_graphs) == [
        (_PARENT, _CHILD),
        (_TEST, _CHILD),
        (_TEST, _PARENT),
    ]


def test_child_guarantee_on_callers_interface_particle_must_be_consumed_before_parent_triggers(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diagnostics = result.program_result.all_diagnostics
    assert len(all_diagnostics) == 1
    diagnostic = all_diagnostics[0]
    assert isinstance(
        diagnostic,
        diagnostics.OccupiedActionInterfaceWhenActionTriggersDiagnostic,
    )
    assert diagnostic.action_name == "action</parent>"
    assert (
        diagnostic.position_name
        == "position<box>::action</parent>::position<iface>::action</child>::position<result>"
    )
    assert diagnostic.location.line == 12
    assert diagnostic.location.column == 79
    assert diagnostic.location.file_path == PurePosixPath("test.dfn")
    assert action_graph(result.operation_graphs) == [
        (_PARENT, _CHILD),
        (_TEST, _CHILD),
        (_TEST, _PARENT),
    ]


def test_existing_particle_guarantee_must_be_consumed_before_parent_triggers(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diagnostics = result.program_result.all_diagnostics
    assert len(all_diagnostics) == 1
    diagnostic = all_diagnostics[0]
    assert isinstance(
        diagnostic,
        diagnostics.OccupiedActionInterfaceWhenActionTriggersDiagnostic,
    )
    assert diagnostic.action_name == "action</parent>"
    assert (
        diagnostic.position_name
        == "position<box>::action</parent>::position<iface>::action</child>::position<result>"
    )
    assert diagnostic.location.line == 12
    assert diagnostic.location.column == 30
    assert diagnostic.location.file_path == PurePosixPath("test.dfn")
    assert action_graph(result.operation_graphs) == [
        (_PARENT, _CHILD),
        (_TEST, _CHILD),
        (_TEST, _PARENT),
    ]


def test_unchanged_guarantee_preserves_caller_move_as_diagnostic_source(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diagnostics = result.program_result.all_diagnostics
    assert len(all_diagnostics) == 1
    diagnostic = all_diagnostics[0]
    assert isinstance(
        diagnostic,
        diagnostics.OccupiedActionInterfaceWhenActionTriggersDiagnostic,
    )
    assert diagnostic.action_name == "action</parent>"
    assert (
        diagnostic.position_name
        == "position<box>::action</parent>::position<iface>::action</child>::position<result>"
    )
    assert diagnostic.location.line == 14
    assert diagnostic.location.column == 50
    assert diagnostic.location.file_path == PurePosixPath("test.dfn")
    assert action_graph(result.operation_graphs) == [
        (_PARENT, _CHILD),
        (_TEST, _CHILD),
        (_TEST, _PARENT),
    ]


def test_error_on_action_interface_suppresses_unconsumed_diagnostic(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diagnostics = result.program_result.all_diagnostics
    assert len(all_diagnostics) == 1
    diagnostic = all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.MoveToOccupiedPositionDiagnostic)
    assert (
        diagnostic.position_name == "position<box>::action</worker>::position<result>"
    )
    assert diagnostic.location.line == 14
    assert diagnostic.location.column == 50
    assert diagnostic.location.file_path == PurePosixPath("test.dfn")
    assert diagnostic.occupied_at is not None
    assert diagnostic.occupied_at.line == 7
    assert diagnostic.occupied_at.column == 30
    assert diagnostic.occupied_at.file_path == PurePosixPath("worker.dfn")
    assert action_graph(result.operation_graphs) == [(_TEST, _WORKER)]


def test_error_on_action_parent_suppresses_unconsumed_diagnostic(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diagnostics = result.program_result.all_diagnostics
    assert len(all_diagnostics) == 1
    diagnostic = all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.MoveToOccupiedPositionDiagnostic)
    assert diagnostic.position_name == "position<occupied>"
    assert diagnostic.location.line == 14
    assert diagnostic.location.column == 47
    assert diagnostic.location.file_path == PurePosixPath("test.dfn")
    assert diagnostic.occupied_at is not None
    assert diagnostic.occupied_at.line == 12
    assert diagnostic.occupied_at.column == 30
    assert diagnostic.occupied_at.file_path == PurePosixPath("test.dfn")
    assert action_graph(result.operation_graphs) == [(_TEST, _WORKER)]


def test_error_on_occupied_child_action_interface_suppresses_parent_trigger_diagnostic(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diagnostics = result.program_result.all_diagnostics
    assert len(all_diagnostics) == 1
    diagnostic = all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.MoveToOccupiedPositionDiagnostic)
    assert (
        diagnostic.position_name
        == "position<box>::action</parent>::position<iface>::action</child>::position<result>"
    )
    assert diagnostic.location.line == 15
    assert diagnostic.location.column == 50
    assert diagnostic.location.file_path == PurePosixPath("test.dfn")
    assert diagnostic.occupied_at is not None
    assert diagnostic.occupied_at.line == 7
    assert diagnostic.occupied_at.column == 30
    assert diagnostic.occupied_at.file_path == PurePosixPath("child.dfn")
    assert action_graph(result.operation_graphs) == [
        (_PARENT, _CHILD),
        (_TEST, _CHILD),
        (_TEST, _PARENT),
    ]


def test_implied_parent_action_must_receive_clean_interface_particle(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diagnostics = result.program_result.all_diagnostics
    assert len(all_diagnostics) == 1
    diagnostic = all_diagnostics[0]
    assert isinstance(
        diagnostic,
        diagnostics.OccupiedActionInterfaceWhenActionTriggersDiagnostic,
    )
    assert diagnostic.action_name == "action</parent>"
    assert (
        diagnostic.position_name
        == "action</parent>::position<iface>::action</child>::position<result>"
    )
    assert diagnostic.location.line == 8
    assert diagnostic.location.column == 64
    assert diagnostic.location.file_path == PurePosixPath("test.dfn")
    assert action_graph(result.operation_graphs) == [
        (_PARENT, _CHILD),
        (_TEST, _CHILD),
        (_TEST, _PARENT),
    ]


def test_action_on_deeper_position_descendant_must_be_clean_before_parent_triggers(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diagnostics = result.program_result.all_diagnostics
    assert len(all_diagnostics) == 1
    diagnostic = all_diagnostics[0]
    assert isinstance(
        diagnostic,
        diagnostics.OccupiedActionInterfaceWhenActionTriggersDiagnostic,
    )
    assert diagnostic.action_name == "action</parent>"
    assert (
        diagnostic.position_name
        == "position<box>::action</parent>::position<iface>::position</branch>::position</leaf>::action</child>::position<result>"
    )
    assert diagnostic.location.line == 15
    assert diagnostic.location.column == 115
    assert diagnostic.location.file_path == PurePosixPath("test.dfn")
    assert action_graph(result.operation_graphs) == [
        (_PARENT, _CHILD),
        (_TEST, _CHILD),
        (_TEST, _PARENT),
    ]


def test_each_parent_instance_receiving_dirty_particle_is_diagnosed(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diagnostics = result.program_result.all_diagnostics
    assert len(all_diagnostics) == 2
    first_diagnostic = all_diagnostics[0]
    assert isinstance(
        first_diagnostic,
        diagnostics.OccupiedActionInterfaceWhenActionTriggersDiagnostic,
    )
    assert first_diagnostic.action_name == "action</parent>"
    assert (
        first_diagnostic.position_name
        == "position<box_a>::action</parent>::position<iface>::action</child>::position<result>"
    )
    assert first_diagnostic.location.line == 18
    assert first_diagnostic.location.column == 81
    assert first_diagnostic.location.file_path == PurePosixPath("test.dfn")
    second_diagnostic = all_diagnostics[1]
    assert isinstance(
        second_diagnostic,
        diagnostics.OccupiedActionInterfaceWhenActionTriggersDiagnostic,
    )
    assert second_diagnostic.action_name == "action</parent>"
    assert (
        second_diagnostic.position_name
        == "position<box_b>::action</parent>::position<iface>::action</child>::position<result>"
    )
    assert second_diagnostic.location.line == 23
    assert second_diagnostic.location.column == 81
    assert second_diagnostic.location.file_path == PurePosixPath("test.dfn")
    assert action_graph(result.operation_graphs) == [
        (_PARENT, _CHILD),
        (_TEST, _CHILD),
        (_TEST, _PARENT),
        (_TEST, _CHILD),
        (_TEST, _PARENT),
    ]


def test_action_interface_entry_rule_is_checked_at_each_parent_trigger(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diagnostics = result.program_result.all_diagnostics
    assert len(all_diagnostics) == 1
    diagnostic = all_diagnostics[0]
    assert isinstance(
        diagnostic,
        diagnostics.OccupiedActionInterfaceWhenActionTriggersDiagnostic,
    )
    assert diagnostic.action_name == "action</parent>"
    assert (
        diagnostic.position_name
        == "position<box>::action</parent>::position<iface>::action</child>::position<result>"
    )
    assert diagnostic.location.line == 13
    assert diagnostic.location.column == 79
    assert diagnostic.location.file_path == PurePosixPath("test.dfn")
    assert action_graph(result.operation_graphs) == [
        (_TEST, _PARENT),
        (_TEST, _CHILD),
        (_TEST, _PARENT),
    ]


def test_each_invalid_trigger_of_same_parent_instance_is_diagnosed(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diagnostics = result.program_result.all_diagnostics
    assert len(all_diagnostics) == 2
    first_diagnostic = all_diagnostics[0]
    assert isinstance(
        first_diagnostic,
        diagnostics.OccupiedActionInterfaceWhenActionTriggersDiagnostic,
    )
    assert first_diagnostic.action_name == "action</parent>"
    assert (
        first_diagnostic.position_name
        == "position<box>::action</parent>::position<iface>::action</child>::position<result>"
    )
    assert first_diagnostic.location.line == 12
    assert first_diagnostic.location.column == 79
    assert first_diagnostic.location.file_path == PurePosixPath("test.dfn")
    second_diagnostic = all_diagnostics[1]
    assert isinstance(
        second_diagnostic,
        diagnostics.OccupiedActionInterfaceWhenActionTriggersDiagnostic,
    )
    assert second_diagnostic.action_name == "action</parent>"
    assert (
        second_diagnostic.position_name
        == "position<box>::action</parent>::position<iface>::action</child>::position<result>"
    )
    assert second_diagnostic.location.line == 14
    assert second_diagnostic.location.column == 79
    assert second_diagnostic.location.file_path == PurePosixPath("test.dfn")
    assert action_graph(result.operation_graphs) == [
        (_TEST, _CHILD),
        (_TEST, _PARENT),
        (_TEST, _CHILD),
        (_TEST, _PARENT),
    ]


def test_one_child_interface_create_before_two_parent_triggers_is_diagnosed_once(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diagnostics = result.program_result.all_diagnostics
    assert len(all_diagnostics) == 1
    diagnostic = all_diagnostics[0]
    assert isinstance(
        diagnostic,
        diagnostics.OccupiedActionInterfaceWhenActionTriggersDiagnostic,
    )
    assert diagnostic.action_name == "action</parent>"
    assert (
        diagnostic.position_name
        == "position<box>::action</parent>::position<iface>::action</child>::position<result>"
    )
    assert diagnostic.location.line == 12
    assert diagnostic.location.column == 30
    assert diagnostic.location.file_path == PurePosixPath("test.dfn")
    assert action_graph(result.operation_graphs) == [
        (_TEST, _PARENT),
        (_TEST, _PARENT),
        (_TEST, _CHILD),
    ]


def test_each_occupied_child_action_interface_position_is_diagnosed(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diagnostics = result.program_result.all_diagnostics
    assert len(all_diagnostics) == 2
    first_diagnostic = all_diagnostics[0]
    assert isinstance(
        first_diagnostic,
        diagnostics.OccupiedActionInterfaceWhenActionTriggersDiagnostic,
    )
    assert first_diagnostic.action_name == "action</parent>"
    assert (
        first_diagnostic.position_name
        == "position<box>::action</parent>::position<iface>::action</child>::position<result_a>"
    )
    assert first_diagnostic.location.line == 14
    assert first_diagnostic.location.column == 79
    assert first_diagnostic.location.file_path == PurePosixPath("test.dfn")
    second_diagnostic = all_diagnostics[1]
    assert isinstance(
        second_diagnostic,
        diagnostics.OccupiedActionInterfaceWhenActionTriggersDiagnostic,
    )
    assert second_diagnostic.action_name == "action</parent>"
    assert (
        second_diagnostic.position_name
        == "position<box>::action</parent>::position<iface>::action</child>::position<result_b>"
    )
    assert second_diagnostic.location.line == 14
    assert second_diagnostic.location.column == 79
    assert second_diagnostic.location.file_path == PurePosixPath("test.dfn")
    assert action_graph(result.operation_graphs) == [
        (_PARENT, _CHILD),
        (_TEST, _CHILD),
        (_TEST, _PARENT),
    ]


def test_consumed_child_guarantee_allows_parent_to_trigger(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert action_graph(result.operation_graphs) == [
        (_PARENT, _CHILD),
        (_TEST, _CHILD),
        (_TEST, _PARENT),
    ]


def test_child_guarantee_moved_out_of_interface_allows_parent_to_trigger(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert action_graph(result.operation_graphs) == [
        (_PARENT, _CHILD),
        (_TEST, _CHILD),
        (_TEST, _PARENT),
    ]


def test_consumed_action_interface_on_position_child_allows_parent_to_trigger(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert action_graph(result.operation_graphs) == [
        (_PARENT, _CHILD),
        (_TEST, _CHILD),
        (_TEST, _PARENT),
    ]
