# pyright: reportUnusedCallResult=false
# Exception to CLAUDE.md "no docstrings in tests" rule: these tests have docstrings
# because the automated guarantee/requirement scenarios are complex enough to need
# prose explanations of what each test verifies.

from __future__ import annotations

from pathlib import PurePosixPath
from typing import TYPE_CHECKING

import pytest

from define.compiler.errors import diagnostics
from define.compiler.validator.reference_graph import action_contract
from define.compiler.validator.reference_graph.reference_graph_validator_tests.test_helpers import (
    assert_propagation_chain,
)
from define.compiler.validator.reference_graph.test_helpers import (
    action_graph,
)
from define.compiler.validator.test_helpers import assert_no_errors

if TYPE_CHECKING:
    from define.compiler.conftest import (
        ValidateTestdataProjectWithReferenceGraph,
    )

_TEST = "action<my.domain.com:my_lib:/test>"
_OUTER = "action<my.domain.com:my_lib:/outer>"
_MIDDLE = "action<my.domain.com:my_lib:/middle>"
_INNER = "action<my.domain.com:my_lib:/inner>"


def test_destroyed_particle_guarantees_do_not_apply_to_replacement_particle(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert action_graph(result.reference_graph_result) == [
        (
            _MIDDLE,
            "action<my.domain.com:my_lib:/empty_marker>",
        ),
        (
            _MIDDLE,
            "action<my.domain.com:my_lib:/fill_marker>",
        ),
        (_TEST, _MIDDLE),
    ]


def test_destroyed_particle_guarantees_do_not_make_replacement_particle_occupied(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    diag = all_diags[0]
    assert isinstance(diag, diagnostics.DestroyInEmptyInterfacePositionDiagnostic)
    assert diag.location.line == 34
    assert diag.location.column == 33
    assert diag.location.end_line == 34
    assert diag.location.end_column == 104
    assert diag.location.file_path == PurePosixPath("test.dfn")
    assert (
        diag.position_name
        == "position<gateway>::action</middle>::position<target>::position</marker>"
    )
    assert diag.inferred_at is not None
    assert diag.inferred_at.line == 7
    assert diag.inferred_at.column == 33
    assert diag.inferred_at.end_line == 7
    assert diag.inferred_at.end_column == 50
    assert diag.inferred_at.file_path == PurePosixPath("empty_marker.dfn")
    assert action_graph(result.reference_graph_result) == [
        (
            _TEST,
            "action<my.domain.com:my_lib:/empty_marker>",
        ),
        (
            _TEST,
            "action<my.domain.com:my_lib:/fill_marker>",
        ),
        (_TEST, _MIDDLE),
    ]


def test_inner_empty_guarantee_propagates_through_outer(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert action_graph(result.reference_graph_result) == [
        (_OUTER, _INNER),
        (_TEST, _OUTER),
    ]


def test_inner_occupied_guarantee_propagates_through_outer(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert action_graph(result.reference_graph_result) == [
        (_OUTER, _INNER),
        (_TEST, _OUTER),
    ]


def test_occupied_guarantee_creates_empty_requirement(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.InferredRequirementViolationDiagnostic)
    assert all_diags[0].required_value is False
    assert all_diags[0].location.line == 13
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].action_name == "action<my.domain.com:my_lib:/outer>"
    assert all_diags[0].required_empty is True
    assert (
        all_diags[0].position_name
        == "position<box>::action</outer>::position<iface>::position</item>"
    )
    assert_propagation_chain(
        all_diags[0],
        {
            "kind": action_contract.PropagationKind.FILL_SITE,
            "enclosing_quality_name": "position<box>::action</outer>::position<iface>::position</item>",
            "triggered_quality_name": None,
            "line": 12,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _TEST,
            "triggered_quality_name": _OUTER,
            "line": 13,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _OUTER,
            "triggered_quality_name": _INNER,
            "line": 18,
            "column": 30,
            "file_path": "outer.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": _INNER,
            "triggered_quality_name": None,
            "line": 11,
            "column": 30,
            "file_path": "inner.dfn",
        },
    )
    assert action_graph(result.reference_graph_result) == [
        (_OUTER, _INNER),
        (_TEST, _OUTER),
    ]


def test_move_guarantee_creates_occupied_in_distant_caller(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.CreateInOccupiedPositionDiagnostic)
    assert all_diags[0].populated_at.line == 15
    assert all_diags[0].populated_at.column == 83
    assert all_diags[0].populated_at.file_path == PurePosixPath("outer.dfn")
    assert (
        all_diags[0].position_name
        == "position<box>::action</outer>::position<iface>::position</output>"
    )
    assert all_diags[0].location.line == 12
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert action_graph(result.reference_graph_result) == [
        (_OUTER, _INNER),
        (_TEST, _OUTER),
    ]


def test_callee_guarantee_below_particle_its_caller_replaced_does_not_apply(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.CreateInOccupiedPositionDiagnostic)
    assert all_diags[0].populated_at.line == 15
    assert all_diags[0].populated_at.column == 30
    assert all_diags[0].populated_at.file_path == PurePosixPath("test.dfn")
    assert (
        all_diags[0].position_name
        == "position<holder>::position</box>::position</child>"
    )
    assert all_diags[0].location.line == 16
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert action_graph(result.reference_graph_result) == [
        (_MIDDLE, _INNER),
        (_TEST, _MIDDLE),
    ]


def test_caller_guarantee_below_particle_its_callee_created_applies(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.CreateInOccupiedPositionDiagnostic)
    assert all_diags[0].populated_at.line == 10
    assert all_diags[0].populated_at.column == 30
    assert all_diags[0].populated_at.file_path == PurePosixPath("middle.dfn")
    assert (
        all_diags[0].position_name
        == "position<holder>::position</box>::position</child>"
    )
    assert all_diags[0].location.line == 15
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert action_graph(result.reference_graph_result) == [
        (_MIDDLE, _INNER),
        (_TEST, _MIDDLE),
    ]


def test_earlier_callee_move_applies_before_later_callee_refills_its_origin(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.CreateInOccupiedPositionDiagnostic)
    assert all_diags[0].populated_at.line == 9
    assert all_diags[0].populated_at.column == 46
    assert all_diags[0].populated_at.file_path == PurePosixPath("mover.dfn")
    assert all_diags[0].position_name == "position<holder>::position</b>"
    assert all_diags[0].location.line == 20
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")


def test_callee_guarantee_below_particle_its_caller_moved_follows_particle(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.CreateInOccupiedPositionDiagnostic)
    assert all_diags[0].populated_at.line == 8
    assert all_diags[0].populated_at.column == 30
    assert all_diags[0].populated_at.file_path == PurePosixPath("fill_child.dfn")
    assert (
        all_diags[0].position_name
        == "position<top>::position</h>::position</box2>::position</child>"
    )
    assert all_diags[0].location.line == 15
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")


def test_caller_emptying_position_its_child_particle_callee_filled_reads_empty(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.CreateInOccupiedPositionDiagnostic)
    assert all_diags[0].populated_at.line == 17
    assert all_diags[0].populated_at.column == 30
    assert all_diags[0].populated_at.file_path == PurePosixPath("test.dfn")
    assert (
        all_diags[0].position_name
        == "position<holder>::position</box>::position</child>"
    )
    assert all_diags[0].location.line == 18
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")


def test_later_of_two_callees_on_child_particle_decides_position(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.CreateInOccupiedPositionDiagnostic)
    assert all_diags[0].populated_at.line == 8
    assert all_diags[0].populated_at.column == 30
    assert all_diags[0].populated_at.file_path == PurePosixPath("fill.dfn")
    assert (
        all_diags[0].position_name
        == "position<holder>::position</box>::position</child>"
    )
    assert all_diags[0].location.line == 17
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")


def test_child_particle_callee_guarantee_below_position_its_caller_replaced_does_not_apply(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.CreateInOccupiedPositionDiagnostic)
    assert all_diags[0].populated_at.line == 18
    assert all_diags[0].populated_at.column == 30
    assert all_diags[0].populated_at.file_path == PurePosixPath("test.dfn")
    assert (
        all_diags[0].position_name
        == "position<holder>::position</box>::position</child>::position</leaf>"
    )
    assert all_diags[0].location.line == 19
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")


def test_callee_move_into_particle_its_caller_then_moved_follows_particle(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.CreateInOccupiedPositionDiagnostic)
    assert all_diags[0].populated_at.line == 9
    assert all_diags[0].populated_at.column == 46
    assert all_diags[0].populated_at.file_path == PurePosixPath("mover.dfn")
    assert all_diags[0].position_name == "position<second>::position</s>::position</b>"
    assert all_diags[0].location.line == 25
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")


def test_callee_moving_particle_below_new_particle_in_its_origin_applies(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.CreateInOccupiedPositionDiagnostic)
    assert all_diags[0].populated_at.line == 11
    assert all_diags[0].populated_at.column == 47
    assert all_diags[0].populated_at.file_path == PurePosixPath("mover.dfn")
    assert (
        all_diags[0].position_name
        == "position<holder>::position</slot>::position</inner>"
    )
    assert all_diags[0].location.line == 16
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")


def test_callee_moving_particle_and_one_below_it_moves_each_to_its_own_destination(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.CreateInOccupiedPositionDiagnostic)
    assert all_diags[0].populated_at.line == 10
    assert all_diags[0].populated_at.column == 65
    assert all_diags[0].populated_at.file_path == PurePosixPath("mover.dfn")
    assert all_diags[0].position_name == "position<holder>::position</moved_part>"
    assert all_diags[0].location.line == 21
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")


@pytest.mark.xfail(
    strict=True,
    reason=(
        "A particle from the caller that a callee moves away and back to where it"
        " started gets no Guarantee, so its caller moves it along with the"
        " particle above it and then loses it."
    ),
)
def test_callee_moving_particle_back_below_new_particle_leaves_it_there(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.CreateInOccupiedPositionDiagnostic)
    assert all_diags[0].populated_at.line == 13
    assert all_diags[0].populated_at.column == 55
    assert all_diags[0].populated_at.file_path == PurePosixPath("mover.dfn")
    assert (
        all_diags[0].position_name
        == "position<holder>::position</box>::position</part>"
    )
    assert all_diags[0].location.line == 23
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")


def test_transitive_child_guarantee_follows_particle_through_move(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.CreateInOccupiedPositionDiagnostic)
    assert all_diags[0].populated_at.line == 27
    assert all_diags[0].populated_at.column == 57
    assert all_diags[0].populated_at.file_path == PurePosixPath("outer.dfn")
    assert all_diags[0].location.line == 13
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert (
        all_diags[0].position_name
        == "position<gateway>::action</outer>::position<destination>::position</result>"
    )
    assert action_graph(result.reference_graph_result) == [
        (_MIDDLE, _INNER),
        (_OUTER, _MIDDLE),
        (_TEST, _OUTER),
    ]


def test_transitive_child_guarantee_at_moved_position_follows_particle(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    diagnostic = all_diags[0]
    assert isinstance(diagnostic, diagnostics.CreateInOccupiedPositionDiagnostic)
    assert diagnostic.location.line == 14
    assert diagnostic.location.column == 30
    assert diagnostic.location.end_line == 14
    assert diagnostic.location.end_column == 106
    assert diagnostic.location.file_path == PurePosixPath("test.dfn")
    assert (
        diagnostic.position_name
        == "position<gateway>::action</middle>::position<destination>::position</result>"
    )
    assert diagnostic.populated_at.line == 7
    assert diagnostic.populated_at.column == 30
    assert diagnostic.populated_at.end_line == 7
    assert diagnostic.populated_at.end_column == 47
    assert diagnostic.populated_at.file_path == PurePosixPath("inner.dfn")
    assert action_graph(result.reference_graph_result) == [
        (_OUTER, _INNER),
        (_MIDDLE, _OUTER),
        (_TEST, _MIDDLE),
    ]


def test_body_move_carries_pending_callee_guarantees(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    diagnostic = all_diags[0]
    assert isinstance(diagnostic, diagnostics.CreateInOccupiedPositionDiagnostic)
    assert diagnostic.location.line == 22
    assert diagnostic.location.column == 30
    assert diagnostic.location.end_line == 22
    assert diagnostic.location.end_column == 110
    assert diagnostic.location.file_path == PurePosixPath("test.dfn")
    assert (
        diagnostic.position_name
        == "position<destination>::position</holder>::position</child_1>::position</child_2>"
    )
    assert diagnostic.populated_at.line == 8
    assert diagnostic.populated_at.column == 30
    assert diagnostic.populated_at.end_line == 8
    assert diagnostic.populated_at.end_column == 48
    assert diagnostic.populated_at.file_path == PurePosixPath("fill_2.dfn")


def test_guarantee_move_carries_pending_callee_guarantees(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    diagnostic = all_diags[0]
    assert isinstance(diagnostic, diagnostics.CreateInOccupiedPositionDiagnostic)
    assert diagnostic.location.line == 17
    assert diagnostic.location.column == 30
    assert diagnostic.location.end_line == 17
    assert diagnostic.location.end_column == 133
    assert diagnostic.location.file_path == PurePosixPath("test.dfn")
    assert (
        diagnostic.position_name
        == "position<box>::action</mover>::position<out>::position</holder>::position</child_1>::position</child_2>"
    )
    assert diagnostic.populated_at.line == 8
    assert diagnostic.populated_at.column == 30
    assert diagnostic.populated_at.end_line == 8
    assert diagnostic.populated_at.end_column == 48
    assert diagnostic.populated_at.file_path == PurePosixPath("fill_2.dfn")


def test_later_sibling_callee_empties_position_an_earlier_sibling_filled(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    diagnostic = all_diags[0]
    assert isinstance(diagnostic, diagnostics.DestroyInEmptyPositionDiagnostic)
    assert diagnostic.location.line == 17
    assert diagnostic.location.column == 33
    assert diagnostic.location.end_line == 17
    assert diagnostic.location.end_column == 82
    assert diagnostic.location.file_path == PurePosixPath("test.dfn")
    assert (
        diagnostic.position_name == "position<holder>::position</box>::position</item>"
    )


def test_callee_of_callee_empties_position_its_caller_filled(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    diagnostic = all_diags[0]
    assert isinstance(diagnostic, diagnostics.DestroyInEmptyPositionDiagnostic)
    assert diagnostic.location.line == 17
    assert diagnostic.location.column == 33
    assert diagnostic.location.end_line == 17
    assert diagnostic.location.end_column == 82
    assert diagnostic.location.file_path == PurePosixPath("test.dfn")
    assert (
        diagnostic.position_name == "position<holder>::position</box>::position</item>"
    )


def test_implied_callee_of_callee_empties_position_its_caller_filled(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    diagnostic = all_diags[0]
    assert isinstance(diagnostic, diagnostics.DestroyInEmptyPositionDiagnostic)
    assert diagnostic.location.line == 18
    assert diagnostic.location.column == 33
    assert diagnostic.location.end_line == 18
    assert diagnostic.location.end_column == 82
    assert diagnostic.location.file_path == PurePosixPath("test.dfn")
    assert (
        diagnostic.position_name == "position<holder>::position</box>::position</item>"
    )


def test_callee_guarantee_below_particle_the_same_callee_moved_is_published(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.DestroyInEmptyPositionDiagnostic)
    assert all_diags[0].position_name == "position</destination>::position</marker>"
    assert all_diags[0].location.line == 12
    assert all_diags[0].location.column == 33
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")


def test_callee_moving_particle_then_its_child_particle_moves_what_is_below_it(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.CreateInOccupiedPositionDiagnostic)
    assert all_diags[0].populated_at.line == 10
    assert all_diags[0].populated_at.column == 30
    assert all_diags[0].populated_at.file_path == PurePosixPath("test.dfn")
    assert (
        all_diags[0].position_name
        == "position</destination>::position</b>::position</x>"
    )
    assert all_diags[0].location.line == 14
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")


def test_particle_below_child_particle_a_callee_moved_then_destroyed_is_not_published(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.DestroyInEmptyPositionDiagnostic)
    assert all_diags[0].position_name == "position</destination>::position</a>"
    assert all_diags[0].location.line == 12
    assert all_diags[0].location.column == 33
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")


def test_callee_moving_child_particle_then_its_parent_particle_moves_what_is_below_it(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.CreateInOccupiedPositionDiagnostic)
    assert all_diags[0].populated_at.line == 11
    assert all_diags[0].populated_at.column == 30
    assert all_diags[0].populated_at.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].position_name == "position</elsewhere>::position</x>"
    assert all_diags[0].location.line == 15
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")


def test_caller_publishes_child_particle_its_callee_moved_after_its_parent_particle(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.CreateInOccupiedPositionDiagnostic)
    assert all_diags[0].populated_at.line == 8
    assert all_diags[0].populated_at.column == 30
    assert all_diags[0].populated_at.file_path == PurePosixPath("middle.dfn")
    assert (
        all_diags[0].position_name
        == "position</destination>::position</b>::position</x>"
    )
    assert all_diags[0].location.line == 12
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")


def test_callee_moving_particle_out_of_two_particles_it_then_moves_follows_all_three(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.CreateInOccupiedPositionDiagnostic)
    assert all_diags[0].populated_at.line == 10
    assert all_diags[0].populated_at.column == 78
    assert all_diags[0].populated_at.file_path == PurePosixPath("inner.dfn")
    assert all_diags[0].position_name == "position</y>"
    assert all_diags[0].location.line == 17
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")


def test_callee_moving_child_particle_then_destroying_its_parent_particle_keeps_child_particle(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.CreateInOccupiedPositionDiagnostic)
    assert all_diags[0].populated_at.line == 10
    assert all_diags[0].populated_at.column == 30
    assert all_diags[0].populated_at.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].position_name == "position</elsewhere>::position</x>"
    assert all_diags[0].location.line == 14
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")


def test_callee_replacing_particle_removes_what_its_caller_tracked_below_it(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.DestroyInEmptyPositionDiagnostic)
    assert all_diags[0].position_name == "position</input>::position</a>::position</x>"
    assert all_diags[0].location.line == 15
    assert all_diags[0].location.column == 33
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")


def test_callee_moving_two_child_particles_out_then_destroying_their_parent_keeps_both(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 2
    assert isinstance(all_diags[0], diagnostics.CreateInOccupiedPositionDiagnostic)
    assert all_diags[0].populated_at.line == 7
    assert all_diags[0].populated_at.column == 30
    assert all_diags[0].populated_at.file_path == PurePosixPath("filler.dfn")
    assert all_diags[0].position_name == "position</first>::position</x>"
    assert all_diags[0].location.line == 22
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert isinstance(all_diags[1], diagnostics.CreateInOccupiedPositionDiagnostic)
    assert all_diags[1].populated_at.line == 8
    assert all_diags[1].populated_at.column == 30
    assert all_diags[1].populated_at.file_path == PurePosixPath("filler.dfn")
    assert all_diags[1].position_name == "position</second>::position</x>"
    assert all_diags[1].location.line == 23
    assert all_diags[1].location.column == 30
    assert all_diags[1].location.file_path == PurePosixPath("test.dfn")
