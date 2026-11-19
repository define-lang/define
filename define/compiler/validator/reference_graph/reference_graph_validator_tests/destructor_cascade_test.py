# pyright: reportUnusedCallResult=false

from __future__ import annotations

from typing import TYPE_CHECKING

from define.compiler.errors import reference_graph_diagnostics, structural_diagnostics
from define.compiler.validator.reference_graph.test_helpers import action_graph
from define.compiler.validator.test_helpers import assert_no_errors

if TYPE_CHECKING:
    from define.compiler.test_fixtures.validation_pipeline import (
        ValidateTestdataProjectWithReferenceGraph,
    )

pytest_plugins = ["define.compiler.test_fixtures.validation_pipeline"]

_TEST = "action<my.domain.com:my_lib:/test>"
_DESTRUCTOR = "action<my.domain.com:my_lib:/destructor>"
_INNER = "action<my.domain.com:my_lib:/inner>"
_DESTRUCTOR_A = "action<my.domain.com:my_lib:/destructor_a>"
_DESTRUCTOR_B = "action<my.domain.com:my_lib:/destructor_b>"
_DESTRUCTOR_C = "action<my.domain.com:my_lib:/destructor_c>"
_CHILD_DESTRUCTOR = "action<my.domain.com:my_lib:/child_destructor>"
_PARENT_DESTRUCTOR = "action<my.domain.com:my_lib:/parent_destructor>"
_GRANDCHILD_DESTRUCTOR = "action<my.domain.com:my_lib:/grandchild_destructor>"
_A_BRANCH_DESTRUCTOR = "action<my.domain.com:my_lib:/a_branch_destructor>"
_A_LEAF_DESTRUCTOR = "action<my.domain.com:my_lib:/a_leaf_destructor>"
_B_BRANCH_DESTRUCTOR = "action<my.domain.com:my_lib:/b_branch_destructor>"
_B_LEAF_DESTRUCTOR = "action<my.domain.com:my_lib:/b_leaf_destructor>"


def test_invalid_destructor_child_guarantee_during_auto_destruction(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    all_diags = result.program_validation.sorted_diagnostics()
    assert len(all_diags) == 2
    assert isinstance(
        all_diags[0],
        reference_graph_diagnostics.DestructorProducesEmptyGuaranteeDiagnostic,
    )
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == "cleanup.dfn"
    assert all_diags[0].location.line == 7
    assert all_diags[0].position_name == "position</child>"
    assert isinstance(all_diags[1], structural_diagnostics.UndefinedLocalNameDiagnostic)
    assert all_diags[1].location.column == 30
    assert all_diags[1].location.file_path == "cleanup.dfn"
    assert all_diags[1].location.line == 8
    assert all_diags[1].local_name == "position<emporary>"


def test_destroy_parent_fires_position_quality_child_destructor(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_validation)
    assert action_graph(result.concrete_program) == [(_TEST, _CHILD_DESTRUCTOR)]


def test_destroy_parent_fires_interface_position_child_destructor(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_validation)
    assert action_graph(result.concrete_program) == [
        (_TEST, _INNER),
        (_TEST, _DESTRUCTOR),
    ]


def test_transitive_destruction_fires_interface_position_destructors(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_validation)
    assert action_graph(result.concrete_program) == [
        (_TEST, _INNER),
        (_TEST, _DESTRUCTOR_A),
        (_TEST, _DESTRUCTOR_B),
        (_TEST, _DESTRUCTOR_C),
    ]


def test_transitive_destruction_fires_child_and_grandchild_destructors(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_validation)
    assert action_graph(result.concrete_program) == [
        (_TEST, _CHILD_DESTRUCTOR),
        (_TEST, _GRANDCHILD_DESTRUCTOR),
    ]


def test_transitive_destruction_fires_destructors_on_both_branches(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_validation)
    assert action_graph(result.concrete_program) == [
        (_TEST, _A_BRANCH_DESTRUCTOR),
        (_TEST, _A_LEAF_DESTRUCTOR),
        (_TEST, _B_BRANCH_DESTRUCTOR),
        (_TEST, _B_LEAF_DESTRUCTOR),
    ]


def test_destroy_parent_fires_parent_and_child_destructors(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_validation)
    assert action_graph(result.concrete_program) == [
        (_TEST, _PARENT_DESTRUCTOR),
        (_TEST, _CHILD_DESTRUCTOR),
    ]


def test_cascade_skips_error_position_own_destructor(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    all_diags = result.program_validation.sorted_diagnostics()
    assert len(all_diags) == 1
    assert isinstance(
        all_diags[0], structural_diagnostics.MoveIntoDefiningPositionDiagnostic
    )
    assert all_diags[0].location.line == 13
    assert all_diags[0].location.column == 98
    assert all_diags[0].location.file_path == "test.dfn"
    assert all_diags[0].source_position == "position<box>::position</child>"
    assert (
        all_diags[0].target_position
        == "position<box>::position</child>::position</noop>"
    )
    assert action_graph(result.concrete_program) == []


def test_cascade_does_not_walk_subtree_of_error_position(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    all_diags = result.program_validation.sorted_diagnostics()
    assert len(all_diags) == 1
    assert isinstance(
        all_diags[0], structural_diagnostics.MoveIntoDefiningPositionDiagnostic
    )
    assert all_diags[0].location.line == 14
    assert all_diags[0].location.column == 98
    assert all_diags[0].location.file_path == "test.dfn"
    assert all_diags[0].source_position == "position<box>::position</child>"
    assert (
        all_diags[0].target_position
        == "position<box>::position</child>::position</grandchild>"
    )
    assert action_graph(result.concrete_program) == []


def test_destroy_parent_does_not_fire_empty_child_destructor(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    all_diags = result.program_validation.sorted_diagnostics()
    assert len(all_diags) == 1
    assert isinstance(
        all_diags[0], reference_graph_diagnostics.DeadChildPositionDiagnostic
    )
    assert all_diags[0].location.line == 7
    assert all_diags[0].location.column == 28
    assert all_diags[0].location.file_path == "test.dfn"
    assert all_diags[0].quality_name == "position</child>"
    assert all_diags[0].position_name == "position<box>"
    assert action_graph(result.concrete_program) == []
