# pyright: reportUnusedCallResult=false

from __future__ import annotations

from pathlib import PurePosixPath

from define.compiler import conftest, diagnostics
from define.compiler.validator.reference_graph import action_contract
from define.compiler.validator.reference_graph.reference_graph_validator_tests.test_helpers import (
    assert_propagation_chain,
)
from define.compiler.validator.test_helpers import assert_no_errors

_IMPLIED_DFN = "define the potential position<my.domain.com:my_lib:/implied>.\n"

_TRANSITIVE_IMPLIED_DFN = (
    "define the potential position<my.domain.com:my_lib:/transitive_implied>.\n"
)


def test_create_in_implied_position(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)


def test_duplicate_direct_constraint_triggers_action_once(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 2
    assert isinstance(all_diags[0], diagnostics.DuplicatePositionConstraintDiagnostic)
    assert all_diags[0].constraint_name == "action</requirer>"
    assert all_diags[0].first_constraint_line == 5
    assert all_diags[0].location.line == 6
    assert all_diags[0].location.column == 24
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert isinstance(all_diags[1], diagnostics.InferredRequirementViolationDiagnostic)
    assert all_diags[1].required_empty is False
    assert all_diags[1].action_name == "action<my.domain.com:my_lib:/requirer>"
    assert all_diags[1].position_name == "position<box>::position</slot>"
    assert all_diags[1].location.line == 12
    assert all_diags[1].location.column == 30
    assert all_diags[1].location.file_path == PurePosixPath("test.dfn")
    assert_propagation_chain(
        all_diags[1],
        {
            "kind": action_contract.PropagationKind.QUALITY_ASSIGNED,
            "enclosing_quality_name": "position<box>",
            "triggered_quality_name": "action<my.domain.com:my_lib:/requirer>",
            "line": 6,
            "column": 24,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.CONSTRUCTOR_TRIGGER,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/test>",
            "triggered_quality_name": "action<my.domain.com:my_lib:/requirer>",
            "line": 12,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/requirer>",
            "triggered_quality_name": None,
            "line": 6,
            "column": 33,
            "file_path": "requirer.dfn",
        },
    )
    assert result.action_call_graph.edges() == [
        (
            "action<my.domain.com:my_lib:/test>",
            "action<my.domain.com:my_lib:/requirer>",
        )
    ]


def test_move_between_implied_positions(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)


def test_child_of_locally_created_implied_particle_is_known_empty(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    diag = all_diags[0]
    assert isinstance(diag, diagnostics.DestroyInEmptyPositionDiagnostic)
    assert diag.location.line == 8
    assert diag.location.column == 33
    assert diag.location.end_line == 8
    assert diag.location.end_column == 68
    assert diag.location.file_path == PurePosixPath("test.dfn")
    assert diag.position_name == "position</parent>::position</child>"


def test_destroy_after_create_in_implied_position(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)


def test_move_into_implied_position_missing_quality(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.MoveViolatesConstraintsDiagnostic)
    assert all_diags[0].location.line == 9
    assert all_diags[0].location.column == 50
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].source_position == "position</plain>"
    assert all_diags[0].target_position == "position</parent>"
    assert all_diags[0].missing_qualities == [
        "position</child>",
    ]


def test_create_in_occupied_implied_position(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.CreateInOccupiedPositionDiagnostic)
    assert all_diags[0].location.line == 8
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].position_name == "position</implied>"
    assert all_diags[0].populated_at.line == 7
    assert all_diags[0].populated_at.column == 30
    assert all_diags[0].populated_at.file_path == PurePosixPath("test.dfn")


def test_destroy_in_empty_implied_position_inferrs_created(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)


def test_move_from_empty_implied_position_infers_occupied(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)


def test_round_trip_local_to_implied_back_to_local_preserves_quality(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)


def test_round_trip_implied_to_local_back_to_implied_preserves_quality(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)


def test_move_from_local_to_implied_marks_local_empty(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.DestroyInEmptyPositionDiagnostic)
    assert all_diags[0].location.line == 10
    assert all_diags[0].location.column == 33
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].position_name == "position<local>"


def test_move_from_implied_to_local_marks_implied_empty(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.DestroyInEmptyPositionDiagnostic)
    assert all_diags[0].location.line == 10
    assert all_diags[0].location.column == 33
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].position_name == "position</implied>"


def test_move_respects_direct_implied_qualities(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)


def test_move_respects_transitively_constructed_occupancy(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)


def test_two_different_implier_constructors_conflict(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    diag = all_diags[0]
    assert isinstance(diag, diagnostics.InferredRequirementViolationDiagnostic)
    assert diag.required_empty is True
    assert diag.action_name == "action<my.domain.com:my_lib:/second_implier>"
    assert diag.position_name == "position<box>::position</implied>"
    assert diag.location.line == 12
    assert diag.location.column == 30
    assert diag.location.end_line == 12
    assert diag.location.end_column == 43
    assert diag.location.file_path == PurePosixPath("test.dfn")
    assert_propagation_chain(
        diag,
        {
            "kind": action_contract.PropagationKind.QUALITY_ASSIGNED,
            "enclosing_quality_name": "position<box>",
            "triggered_quality_name": "action<my.domain.com:my_lib:/second_implier>",
            "line": 6,
            "column": 24,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.CONSTRUCTOR_TRIGGER,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/test>",
            "triggered_quality_name": "action<my.domain.com:my_lib:/second_implier>",
            "line": 12,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.FILL_SITE,
            "enclosing_quality_name": "position<box>::position</implied>",
            "triggered_quality_name": None,
            "line": 6,
            "column": 30,
            "file_path": "first_implier.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/second_implier>",
            "triggered_quality_name": None,
            "line": 6,
            "column": 30,
            "file_path": "second_implier.dfn",
        },
    )


def test_three_level_chain_create_destroy_create_constructors(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)


def test_sibling_constructor_empty_guarantee_violates_later_occupied_requirement(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    diag = all_diags[0]
    assert isinstance(diag, diagnostics.InferredRequirementViolationDiagnostic)
    assert diag.required_empty is False
    assert diag.action_name == "action<my.domain.com:my_lib:/requirer>"
    assert diag.position_name == "position<box>::position</slot>"
    assert diag.location.line == 12
    assert diag.location.column == 30
    assert diag.location.end_line == 12
    assert diag.location.end_column == 43
    assert diag.location.file_path == PurePosixPath("test.dfn")
    assert_propagation_chain(
        diag,
        {
            "kind": action_contract.PropagationKind.QUALITY_ASSIGNED,
            "enclosing_quality_name": "position<box>",
            "triggered_quality_name": "action<my.domain.com:my_lib:/requirer>",
            "line": 6,
            "column": 24,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.CONSTRUCTOR_TRIGGER,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/test>",
            "triggered_quality_name": "action<my.domain.com:my_lib:/requirer>",
            "line": 12,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/requirer>",
            "triggered_quality_name": None,
            "line": 6,
            "column": 33,
            "file_path": "requirer.dfn",
        },
    )


def test_destroy_in_emptied_interface_child_after_constructor_fills_it(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    diag = all_diags[0]
    assert isinstance(diag, diagnostics.DestroyInEmptyPositionDiagnostic)
    assert diag.location.line == 14
    assert diag.location.column == 33
    assert diag.location.end_line == 14
    assert diag.location.end_column == 69
    assert diag.location.file_path == PurePosixPath("test.dfn")
    assert diag.position_name == "position<source>::position</emptier>"
