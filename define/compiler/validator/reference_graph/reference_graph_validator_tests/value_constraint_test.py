"""Reference graph validation of value constraints."""

from __future__ import annotations

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
