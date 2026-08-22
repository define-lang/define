# pyright: reportUnusedCallResult=false

from __future__ import annotations

from pathlib import PurePosixPath
from typing import TYPE_CHECKING

from define.compiler import diagnostics
from define.compiler.validator.test_helpers import assert_no_errors

if TYPE_CHECKING:
    from define.compiler.conftest import (
        ValidateTestdataProjectWithReferenceGraph,
    )

_TEST = "action<my.domain.com:my_lib:/test>"
_DESTRUCTOR = "action<my.domain.com:my_lib:/destructor>"
_INNER = "action<my.domain.com:my_lib:/inner>"
_DESTRUCTOR_A = "action<my.domain.com:my_lib:/destructor_a>"
_DESTRUCTOR_B = "action<my.domain.com:my_lib:/destructor_b>"
_MARKED = "action<my.domain.com:my_lib:/marked>"


def test_and_normal_action(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    assert_no_errors(validate_testdata_project_with_reference_graph().program_result)


def test_destroys_implied_position(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    assert_no_errors(validate_testdata_project_with_reference_graph().program_result)


def test_destruction_contract(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    assert_no_errors(validate_testdata_project_with_reference_graph().program_result)


def test_empty_interface(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    assert_no_errors(validate_testdata_project_with_reference_graph().program_result)


def test_implies_position(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    assert_no_errors(validate_testdata_project_with_reference_graph().program_result)


def test_multiple_on_one_particle(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    assert_no_errors(validate_testdata_project_with_reference_graph().program_result)


def test_nested_cascade(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    assert_no_errors(validate_testdata_project_with_reference_graph().program_result)


def test_occupied_interface(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    assert_no_errors(validate_testdata_project_with_reference_graph().program_result)


def test_via_quality_implication(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    assert_no_errors(validate_testdata_project_with_reference_graph().program_result)


def test_destroy_fires_destructor_via_constraint(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert result.action_call_graph.edges() == [(_TEST, _DESTRUCTOR)]


def test_destroy_fires_destructor_via_quality_implication(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert result.action_call_graph.edges() == [
        (_TEST, _MARKED),
        (_TEST, _DESTRUCTOR),
    ]


def test_destroy_does_not_fire_non_destructor_action_quality(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.UntriggeredActionDiagnostic)
    assert all_diags[0].location.line == 8
    assert all_diags[0].location.column == 28
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].constraint_name == "action</worker>"
    assert all_diags[0].position_name == "position<box>"
    assert result.action_call_graph.edges() == []


def test_destroy_fires_multiple_destructors(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert result.action_call_graph.edges() == [
        (_TEST, _DESTRUCTOR_B),
        (_TEST, _DESTRUCTOR_A),
    ]


def test_destructor_fired_from_constructor(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert result.action_call_graph.edges() == [(_TEST, _DESTRUCTOR)]


def test_destroy_empty_position_does_not_fire_destructor(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.DestroyInEmptyPositionDiagnostic)
    assert all_diags[0].location.line == 11
    assert all_diags[0].location.column == 33
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].position_name == "position<box>"
    assert result.action_call_graph.edges() == []


def test_destroy_parent_not_occupied_does_not_fire_destructor(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 2
    assert isinstance(all_diags[0], diagnostics.UntriggeredActionDiagnostic)
    assert all_diags[0].location.line == 8
    assert all_diags[0].location.column == 28
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].constraint_name == "action</inner>"
    assert all_diags[0].position_name == "position<box>"
    assert isinstance(all_diags[1], diagnostics.ParentPositionNotOccupiedDiagnostic)
    assert all_diags[1].location.line == 11
    assert all_diags[1].location.column == 33
    assert all_diags[1].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[1].position_name == "position<box>::action</inner>::position<slot>"
    assert all_diags[1].parent_position_name == "position<box>"
    assert result.action_call_graph.edges() == []


def test_missing_destructor_file_is_reported_and_skipped(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.ReferencedFileNotFoundDiagnostic)
    assert all_diags[0].file_path == "destructor.dfn"
    assert all_diags[0].location.line == 8
    assert all_diags[0].location.column == 35
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert result.action_call_graph.edges() == []


def test_destroy_via_chained_interface_position_fires_destructor(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert result.action_call_graph.edges() == [(_TEST, _INNER), (_TEST, _DESTRUCTOR)]


def test_destroy_after_move_into_unconstrained_position_fires_destructor(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert result.action_call_graph.edges() == [(_TEST, _DESTRUCTOR)]
