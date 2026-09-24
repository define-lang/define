"""Reference graph validation of value constraints."""

from __future__ import annotations

from pathlib import PurePosixPath
from typing import TYPE_CHECKING

from define.compiler import diagnostics
from define.compiler.validator.test_helpers import assert_no_errors

if TYPE_CHECKING:
    from define.compiler.conftest import ValidateTestdataProjectWithReferenceGraph


def test_create_and_destroy(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    assert_no_errors(validate_testdata_project_with_reference_graph().program_result)


def test_move_matching_value(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    assert_no_errors(validate_testdata_project_with_reference_graph().program_result)


def test_move_mismatched_value(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_result
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.MoveViolatesConstraintsDiagnostic)
    assert diagnostic.source_position == "position<source>"
    assert diagnostic.target_position == "position<target>"
    assert diagnostic.missing_qualities == ["value</text>"]


def test_move_without_value(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_result
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.MoveViolatesConstraintsDiagnostic)
    assert diagnostic.source_position == "position<source>"
    assert diagnostic.target_position == "position<target>"
    assert diagnostic.missing_qualities == ["value</number>"]


def test_move_through_unconstrained_position(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    assert_no_errors(validate_testdata_project_with_reference_graph().program_result)


def test_action_matching_value(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    assert_no_errors(validate_testdata_project_with_reference_graph().program_result)


def test_action_mismatched_value(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_result
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 2
    untriggered = result.all_diagnostics[0]
    assert isinstance(untriggered, diagnostics.UntriggeredActionDiagnostic)
    assert untriggered.position_name == "position<worker>"
    assert untriggered.constraint_name == "action</consume>"
    diagnostic = result.all_diagnostics[1]
    assert isinstance(diagnostic, diagnostics.MoveViolatesConstraintsDiagnostic)
    assert diagnostic.source_position == "position<source>"
    assert (
        diagnostic.target_position
        == "position<worker>::action</consume>::position<input>"
    )
    assert diagnostic.missing_qualities == ["value</number>"]


def test_action_preserves_value_through_unconstrained_positions(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    assert_no_errors(validate_testdata_project_with_reference_graph().program_result)


def test_unconstrained_callee_destroys_value_particle(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    assert_no_errors(validate_testdata_project_with_reference_graph().program_result)


def test_value_use_keeps_only_origin_alive(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_result
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.DeadValueConstraintDiagnostic)
    assert diagnostic.position_name == "position<target>"
    assert diagnostic.constraint_name == "value</number>"
    assert diagnostic.location.line == 13
    assert diagnostic.location.file_path == PurePosixPath("test.dfn")


def test_value_setting_target_keeps_only_origin_alive(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_result
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.DeadValueConstraintDiagnostic)
    assert diagnostic.position_name == "position<target>"
    assert diagnostic.constraint_name == "value</number>"
    assert diagnostic.location.line == 13
    assert diagnostic.location.file_path == PurePosixPath("test.dfn")


def test_guaranteed_created_value(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph(
        allow_entry_action_interface_positions=True
    ).program_result
    assert_no_errors(result)


def test_guaranteed_moved_value(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph(
        allow_entry_action_interface_positions=True
    ).program_result
    assert_no_errors(result)


def test_guaranteed_value_through_local(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph(
        allow_entry_action_interface_positions=True
    ).program_result
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.DeadValueConstraintDiagnostic)
    assert diagnostic.position_name == "position<middle>"
    assert diagnostic.constraint_name == "value</number>"
    assert diagnostic.location.line == 18
    assert diagnostic.location.file_path == PurePosixPath("test.dfn")


def test_required_value_used_after_move(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph(
        allow_entry_action_interface_positions=True
    ).program_result
    assert_no_errors(result)


def test_callee_contract_keeps_only_origin_alive(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_result
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.DeadValueConstraintDiagnostic)
    assert diagnostic.position_name == "position<middle>"
    assert diagnostic.constraint_name == "value</number>"
    assert diagnostic.location.line == 18
    assert diagnostic.location.file_path == PurePosixPath("test.dfn")


def test_callee_contract_through_unconstrained_position(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_result
    assert_no_errors(result)


def test_unused_local_value_is_dead(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_result
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.DeadValueConstraintDiagnostic)
    assert diagnostic.position_name == "position<item>"
    assert diagnostic.constraint_name == "value</number>"
    assert diagnostic.location.file_path == PurePosixPath("test.dfn")
    assert diagnostic.location.line == 8
    assert diagnostic.location.column == 28


def test_moving_values_does_not_keep_constraints_alive(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_result
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 2
    diagnostic = result.all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.DeadValueConstraintDiagnostic)
    assert diagnostic.position_name == "position<source>"
    assert diagnostic.constraint_name == "value</number>"
    assert diagnostic.location.file_path == PurePosixPath("test.dfn")
    assert diagnostic.location.line == 8
    assert diagnostic.location.column == 28
    diagnostic = result.all_diagnostics[1]
    assert isinstance(diagnostic, diagnostics.DeadValueConstraintDiagnostic)
    assert diagnostic.position_name == "position<target>"
    assert diagnostic.constraint_name == "value</number>"
    assert diagnostic.location.file_path == PurePosixPath("test.dfn")
    assert diagnostic.location.line == 13
    assert diagnostic.location.column == 28


def test_unconstrained_callee_does_not_keep_value_alive(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_result
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.DeadValueConstraintDiagnostic)
    assert diagnostic.position_name == "position<source>"
    assert diagnostic.constraint_name == "value</number>"
    assert diagnostic.location.file_path == PurePosixPath("test.dfn")
    assert diagnostic.location.line == 13
    assert diagnostic.location.column == 28
