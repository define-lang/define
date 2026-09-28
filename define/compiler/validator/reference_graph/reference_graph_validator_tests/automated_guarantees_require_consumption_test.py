# pyright: reportUnusedCallResult=false

from __future__ import annotations

from pathlib import PurePosixPath
from typing import TYPE_CHECKING

from define.compiler import diagnostics
from define.compiler.validator.reference_graph.test_helpers import (
    action_graph,
)
from define.compiler.validator.test_helpers import assert_no_errors

if TYPE_CHECKING:
    from define.compiler.conftest import (
        ValidateTestdataProjectWithReferenceGraph,
    )

_CHILD = "action<my.domain.com:my_lib:/child>"
_CONSTRUCT = "action<my.domain.com:my_lib:/construct>"
_FOO = "action<my.domain.com:my_lib:/foo>"
_HELPER = "action<my.domain.com:my_lib:/helper>"
_INNER = "action<my.domain.com:my_lib:/inner>"
_OUTER = "action<my.domain.com:my_lib:/outer>"
_OUTER_A = "action<my.domain.com:my_lib:/outer_a>"
_OUTER_B = "action<my.domain.com:my_lib:/outer_b>"
_PARENT = "action<my.domain.com:my_lib:/parent>"
_TEST = "action<my.domain.com:my_lib:/test>"
_WORKER = "action<my.domain.com:my_lib:/worker>"


def test_triggered_action_interface_particle_must_depart_before_caller_ends(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph(
        allow_entry_action_interface_positions=True
    )
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
    assert action_graph(result.reference_graph_result) == [(_TEST, _WORKER)]


def test_same_action_on_two_particles_requires_both_interfaces_consumed(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph(
        allow_entry_action_interface_positions=True
    )
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
    assert action_graph(result.reference_graph_result) == [
        (_TEST, _WORKER),
        (_TEST, _WORKER),
    ]


def test_consuming_one_of_two_instances_of_same_action_leaves_other_unconsumed(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph(
        allow_entry_action_interface_positions=True
    )
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
    assert action_graph(result.reference_graph_result) == [
        (_TEST, _WORKER),
        (_TEST, _WORKER),
    ]


def test_destroyed_action_parent_does_not_duplicate_replacement_diagnostic(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph(
        allow_entry_action_interface_positions=True
    )
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
    assert action_graph(result.reference_graph_result) == [
        (_TEST, _WORKER),
        (_TEST, _WORKER),
    ]


def test_retriggered_action_interface_particle_may_depart_before_caller_ends(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert action_graph(result.reference_graph_result) == [
        (_TEST, _WORKER),
        (_TEST, _WORKER),
    ]


def test_retriggered_action_interface_particle_must_depart_before_caller_ends(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph(
        allow_entry_action_interface_positions=True
    )
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
    assert action_graph(result.reference_graph_result) == [
        (_TEST, _WORKER),
        (_TEST, _WORKER),
    ]


def test_caller_move_between_callee_interfaces_does_not_consume_particle(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph(
        allow_entry_action_interface_positions=True
    )
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
    assert action_graph(result.reference_graph_result) == [
        (_TEST, _WORKER),
        (_TEST, _WORKER),
    ]


def test_callee_move_between_its_interfaces_requires_caller_consumption(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph(
        allow_entry_action_interface_positions=True
    )
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
    assert action_graph(result.reference_graph_result) == [(_TEST, _WORKER)]


def test_constructor_interface_particle_must_depart_before_caller_ends(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph(
        allow_entry_action_interface_positions=True
    )
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
    assert action_graph(result.reference_graph_result) == [(_TEST, _CONSTRUCT)]


def test_local_parent_auto_destruction_consumes_action_interface_particle(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert action_graph(result.reference_graph_result) == [(_TEST, _WORKER)]


def test_moved_particle_callee_interface_must_be_consumed_in_interface_position(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph(
        allow_entry_action_interface_positions=True
    )
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    diagnostic = all_diags[0]
    assert isinstance(diagnostic, diagnostics.UnconsumedActionInterfaceDiagnostic)
    assert diagnostic.action_name == "action</worker>"
    assert (
        diagnostic.position_name
        == "position<destination>::action</worker>::position<result>"
    )
    assert diagnostic.location.line == 16
    assert diagnostic.location.column == 45
    assert diagnostic.location.file_path == PurePosixPath("test.dfn")
    assert action_graph(result.reference_graph_result) == [(_TEST, _WORKER)]


def test_moved_particle_callee_interface_must_be_consumed_in_implied_position(
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
        diagnostic.position_name
        == "position</store>::action</worker>::position<result>"
    )
    assert diagnostic.location.line == 12
    assert diagnostic.location.column == 45
    assert diagnostic.location.file_path == PurePosixPath("test.dfn")
    assert action_graph(result.reference_graph_result) == [(_TEST, _WORKER)]


def test_implied_action_interface_must_be_consumed_by_implying_action(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    diagnostic = all_diags[0]
    assert isinstance(diagnostic, diagnostics.UnconsumedActionInterfaceDiagnostic)
    assert diagnostic.action_name == "action</foo>"
    assert diagnostic.position_name == "action</foo>::position<result>"
    assert diagnostic.location.line == 7
    assert diagnostic.location.column == 30
    assert diagnostic.location.file_path == PurePosixPath("outer.dfn")
    assert action_graph(result.reference_graph_result) == [
        (_OUTER, _FOO),
        (_TEST, _OUTER),
    ]


def test_consumed_implied_action_interface_allows_implying_action_to_end(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert action_graph(result.reference_graph_result) == [
        (_OUTER, _FOO),
        (_TEST, _OUTER),
    ]


def test_deeper_action_implied_position_can_leave_with_interface_particle(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph(
        allow_entry_action_interface_positions=True
    )
    assert_no_errors(result.program_result)
    assert action_graph(result.reference_graph_result) == [
        (_TEST, _PARENT),
        (_TEST, _CHILD),
    ]


def test_callee_implied_position_on_interface_particle_may_stay_occupied(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph(
        allow_entry_action_interface_positions=True
    )
    assert_no_errors(result.program_result)
    assert action_graph(result.reference_graph_result) == [(_TEST, _FOO)]


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
    assert diagnostic.location.line == 12
    assert diagnostic.location.column == 79
    assert diagnostic.location.file_path == PurePosixPath("test.dfn")
    assert action_graph(result.reference_graph_result) == [
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
    assert diagnostic.location.line == 18
    assert diagnostic.location.column == 50
    assert diagnostic.location.file_path == PurePosixPath("test.dfn")
    assert action_graph(result.reference_graph_result) == [
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
    assert first_diagnostic.location.line == 18
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
    assert second_diagnostic.location.line == 18
    assert second_diagnostic.location.column == 50
    assert second_diagnostic.location.file_path == PurePosixPath("test.dfn")
    assert action_graph(result.reference_graph_result) == [
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
    assert diagnostic.location.line == 19
    assert diagnostic.location.column == 98
    assert diagnostic.location.file_path == PurePosixPath("test.dfn")
    assert action_graph(result.reference_graph_result) == [
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
    assert diagnostic.location.line == 13
    assert diagnostic.location.column == 98
    assert diagnostic.location.file_path == PurePosixPath("test.dfn")
    assert action_graph(result.reference_graph_result) == [
        (_PARENT, _CHILD),
        (_TEST, _CHILD),
        (_TEST, _PARENT),
    ]


def test_child_guarantee_on_callers_interface_particle_must_be_consumed_before_parent_triggers(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph(
        allow_entry_action_interface_positions=True
    )
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
    assert diagnostic.location.line == 11
    assert diagnostic.location.column == 79
    assert diagnostic.location.file_path == PurePosixPath("test.dfn")
    assert action_graph(result.reference_graph_result) == [
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
    assert action_graph(result.reference_graph_result) == [
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
    assert action_graph(result.reference_graph_result) == [
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
    assert action_graph(result.reference_graph_result) == [(_TEST, _WORKER)]


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
    assert action_graph(result.reference_graph_result) == [(_TEST, _WORKER)]


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
    assert action_graph(result.reference_graph_result) == [
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
    assert diagnostic.location.line == 7
    assert diagnostic.location.column == 64
    assert diagnostic.location.file_path == PurePosixPath("test.dfn")
    assert action_graph(result.reference_graph_result) == [
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
    assert diagnostic.location.line == 14
    assert diagnostic.location.column == 115
    assert diagnostic.location.file_path == PurePosixPath("test.dfn")
    assert action_graph(result.reference_graph_result) == [
        (_PARENT, _CHILD),
        (_TEST, _CHILD),
        (_TEST, _PARENT),
    ]


def test_action_interface_two_actions_below_callee_interface_occupied_when_callee_triggers(
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
        == "position<box>::action</parent>::position<iface>::action</child>::position<holder>"
    )
    assert first_diagnostic.location.line == 12
    assert first_diagnostic.location.column == 30
    assert first_diagnostic.location.file_path == PurePosixPath("test.dfn")
    second_diagnostic = all_diagnostics[1]
    assert isinstance(
        second_diagnostic,
        diagnostics.OccupiedActionInterfaceWhenActionTriggersDiagnostic,
    )
    assert second_diagnostic.action_name == "action</parent>"
    assert (
        second_diagnostic.position_name
        == "position<box>::action</parent>::position<iface>::action</child>::position<holder>::action</worker>::position<result>"
    )
    assert second_diagnostic.location.line == 14
    assert second_diagnostic.location.column == 113
    assert second_diagnostic.location.file_path == PurePosixPath("test.dfn")
    assert action_graph(result.reference_graph_result) == [
        (_CHILD, _WORKER),
        (_PARENT, _CHILD),
        (_TEST, _CHILD),
        (_TEST, _WORKER),
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
    assert first_diagnostic.location.line == 17
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
    assert second_diagnostic.location.line == 21
    assert second_diagnostic.location.column == 81
    assert second_diagnostic.location.file_path == PurePosixPath("test.dfn")
    assert action_graph(result.reference_graph_result) == [
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
    assert action_graph(result.reference_graph_result) == [
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
    assert action_graph(result.reference_graph_result) == [
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
    assert action_graph(result.reference_graph_result) == [
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
        == "position<box>::action</parent>::position<iface>::action</child>::position<result_b>"
    )
    assert second_diagnostic.location.line == 12
    assert second_diagnostic.location.column == 79
    assert second_diagnostic.location.file_path == PurePosixPath("test.dfn")
    assert action_graph(result.reference_graph_result) == [
        (_PARENT, _CHILD),
        (_TEST, _CHILD),
        (_TEST, _PARENT),
    ]


def test_consumed_child_guarantee_allows_parent_to_trigger(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert action_graph(result.reference_graph_result) == [
        (_PARENT, _CHILD),
        (_TEST, _CHILD),
        (_TEST, _PARENT),
    ]


def test_child_guarantee_moved_out_of_interface_allows_parent_to_trigger(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert action_graph(result.reference_graph_result) == [
        (_PARENT, _CHILD),
        (_TEST, _CHILD),
        (_TEST, _PARENT),
    ]


def test_consumed_action_interface_on_position_child_allows_parent_to_trigger(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert action_graph(result.reference_graph_result) == [
        (_PARENT, _CHILD),
        (_TEST, _CHILD),
        (_TEST, _PARENT),
    ]


def test_implied_position_action_interface_occupied_when_callee_triggers(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    diagnostic = all_diags[0]
    assert isinstance(
        diagnostic, diagnostics.OccupiedActionInterfaceWhenActionTriggersDiagnostic
    )
    assert diagnostic.action_name == "action</outer>"
    assert (
        diagnostic.position_name
        == "position<box>::position</implied>::action</inner>::position<item>"
    )
    assert diagnostic.location.line == 13
    assert diagnostic.location.column == 65
    assert diagnostic.location.file_path == PurePosixPath("test.dfn")
    assert action_graph(result.reference_graph_result) == [
        (_OUTER, _INNER),
        (_TEST, _INNER),
        (_TEST, _OUTER),
    ]


def test_transitively_implied_position_action_interface_occupied_when_callee_triggers(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    diagnostic = all_diags[0]
    assert isinstance(
        diagnostic, diagnostics.OccupiedActionInterfaceWhenActionTriggersDiagnostic
    )
    assert diagnostic.action_name == "action</outer>"
    assert (
        diagnostic.position_name
        == "position<box>::position</implied>::action</inner>::position<item>"
    )
    assert diagnostic.location.line == 13
    assert diagnostic.location.column == 65
    assert diagnostic.location.file_path == PurePosixPath("test.dfn")
    assert action_graph(result.reference_graph_result) == [
        (_HELPER, _INNER),
        (_OUTER, _HELPER),
        (_TEST, _INNER),
        (_TEST, _OUTER),
    ]


def test_implied_action_interface_occupied_when_callee_triggers(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    diagnostic = all_diags[0]
    assert isinstance(
        diagnostic, diagnostics.OccupiedActionInterfaceWhenActionTriggersDiagnostic
    )
    assert diagnostic.action_name == "action</outer>"
    assert diagnostic.position_name == "position<box>::action</inner>::position<item>"
    assert diagnostic.location.line == 12
    assert diagnostic.location.column == 45
    assert diagnostic.location.file_path == PurePosixPath("test.dfn")
    assert action_graph(result.reference_graph_result) == [
        (_OUTER, _INNER),
        (_TEST, _INNER),
        (_TEST, _OUTER),
    ]


def test_transitively_implied_action_interface_occupied_when_callee_triggers(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    diagnostic = all_diags[0]
    assert isinstance(
        diagnostic, diagnostics.OccupiedActionInterfaceWhenActionTriggersDiagnostic
    )
    assert diagnostic.action_name == "action</outer>"
    assert diagnostic.position_name == "position<box>::action</inner>::position<item>"
    assert diagnostic.location.line == 12
    assert diagnostic.location.column == 45
    assert diagnostic.location.file_path == PurePosixPath("test.dfn")
    assert action_graph(result.reference_graph_result) == [
        (_HELPER, _INNER),
        (_OUTER, _HELPER),
        (_TEST, _INNER),
        (_TEST, _OUTER),
    ]


def test_action_interface_under_implied_position_child_occupied_when_callee_triggers(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    diagnostic = all_diags[0]
    assert isinstance(
        diagnostic, diagnostics.OccupiedActionInterfaceWhenActionTriggersDiagnostic
    )
    assert diagnostic.action_name == "action</outer>"
    assert (
        diagnostic.position_name
        == "position<box>::position</implied>::position</holder>::action</inner>::position<item>"
    )
    assert diagnostic.location.line == 14
    assert diagnostic.location.column == 84
    assert diagnostic.location.file_path == PurePosixPath("test.dfn")
    assert action_graph(result.reference_graph_result) == [
        (_OUTER, _INNER),
        (_TEST, _INNER),
        (_TEST, _OUTER),
    ]


def test_current_particle_implied_action_interface_occupied_when_implied_callee_triggers(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    diagnostic = all_diags[0]
    assert isinstance(
        diagnostic, diagnostics.OccupiedActionInterfaceWhenActionTriggersDiagnostic
    )
    assert diagnostic.action_name == "action</outer>"
    assert diagnostic.position_name == "action</inner>::position<item>"
    assert diagnostic.location.line == 7
    assert diagnostic.location.column == 30
    assert diagnostic.location.file_path == PurePosixPath("test.dfn")
    assert action_graph(result.reference_graph_result) == [
        (_OUTER, _INNER),
        (_TEST, _INNER),
        (_TEST, _OUTER),
    ]


def test_unimplied_action_interface_occupied_when_callee_triggers_is_valid(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert action_graph(result.reference_graph_result) == [
        (_TEST, _INNER),
        (_TEST, _OUTER),
    ]


def test_circular_implied_action_does_not_count_as_implying_itself(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 3
    assert isinstance(all_diags[0], diagnostics.CircularGlobalReferenceDiagnostic)
    assert all_diags[0].cycle == [_OUTER, _INNER, _OUTER]
    assert all_diags[0].location.line == 2
    assert all_diags[0].location.column == 25
    assert all_diags[0].location.file_path == PurePosixPath("inner.dfn")
    assert isinstance(all_diags[1], diagnostics.UntriggeredImpliedActionDiagnostic)
    assert all_diags[1].implied_action_name == "action</outer>"
    assert all_diags[1].location.line == 2
    assert all_diags[1].location.column == 25
    assert all_diags[1].location.file_path == PurePosixPath("inner.dfn")
    assert isinstance(all_diags[2], diagnostics.UntriggeredActionInterfaceDiagnostic)
    assert all_diags[2].action_name == "action</outer>"
    assert all_diags[2].position_name == "action</outer>::position<run>"
    assert all_diags[2].location.line == 7
    assert all_diags[2].location.column == 30
    assert all_diags[2].location.file_path == PurePosixPath("inner.dfn")
    assert action_graph(result.reference_graph_result) == [
        (_OUTER, _INNER),
        (_TEST, _OUTER),
    ]


def test_implied_position_action_interface_on_other_particle_is_valid(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert action_graph(result.reference_graph_result) == [
        (_OUTER, _INNER),
        (_TEST, _INNER),
        (_TEST, _OUTER),
    ]


def test_implied_position_action_interface_is_reported_once_for_two_implying_callees(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    diagnostic = all_diags[0]
    assert isinstance(
        diagnostic, diagnostics.OccupiedActionInterfaceWhenActionTriggersDiagnostic
    )
    assert diagnostic.action_name == "action</outer_a>"
    assert (
        diagnostic.position_name
        == "position<box>::position</implied>::action</inner>::position<item>"
    )
    assert diagnostic.location.line == 14
    assert diagnostic.location.column == 65
    assert diagnostic.location.file_path == PurePosixPath("test.dfn")
    assert action_graph(result.reference_graph_result) == [
        (_TEST, _INNER),
        (_TEST, _OUTER_A),
        (_TEST, _OUTER_B),
    ]


def test_each_implied_position_action_interface_is_reported(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 2
    first_diagnostic = all_diags[0]
    assert isinstance(
        first_diagnostic,
        diagnostics.OccupiedActionInterfaceWhenActionTriggersDiagnostic,
    )
    assert first_diagnostic.action_name == "action</outer>"
    assert (
        first_diagnostic.position_name
        == "position<box>::position</first>::action</inner>::position<item>"
    )
    assert first_diagnostic.location.line == 14
    assert first_diagnostic.location.column == 63
    assert first_diagnostic.location.file_path == PurePosixPath("test.dfn")
    second_diagnostic = all_diags[1]
    assert isinstance(
        second_diagnostic,
        diagnostics.OccupiedActionInterfaceWhenActionTriggersDiagnostic,
    )
    assert second_diagnostic.action_name == "action</outer>"
    assert (
        second_diagnostic.position_name
        == "position<box>::position</second>::action</inner>::position<item>"
    )
    assert second_diagnostic.location.line == 16
    assert second_diagnostic.location.column == 64
    assert second_diagnostic.location.file_path == PurePosixPath("test.dfn")
    assert action_graph(result.reference_graph_result) == [
        (_OUTER, _INNER),
        (_OUTER, _INNER),
        (_TEST, _INNER),
        (_TEST, _INNER),
        (_TEST, _OUTER),
    ]


def test_implied_position_action_interface_is_checked_only_for_callees_implying_it(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    diagnostic = all_diags[0]
    assert isinstance(
        diagnostic, diagnostics.OccupiedActionInterfaceWhenActionTriggersDiagnostic
    )
    assert diagnostic.action_name == "action</outer_b>"
    assert (
        diagnostic.position_name
        == "position<box>::position</second>::action</inner>::position<item>"
    )
    assert diagnostic.location.line == 16
    assert diagnostic.location.column == 64
    assert diagnostic.location.file_path == PurePosixPath("test.dfn")
    assert action_graph(result.reference_graph_result) == [
        (_OUTER_A, _INNER),
        (_OUTER_B, _INNER),
        (_TEST, _INNER),
        (_TEST, _OUTER_A),
        (_TEST, _OUTER_B),
    ]
