# pyright: reportUnusedCallResult=false
# Exception to CLAUDE.md "no docstrings in tests" rule: these tests have docstrings
# because the automated guarantee/requirement scenarios are complex enough to need
# prose explanations of what each test verifies.

from __future__ import annotations

from pathlib import PurePosixPath
from typing import TYPE_CHECKING

from define.compiler import diagnostics
from define.compiler.validator.reference_graph import action_contract
from define.compiler.validator.reference_graph.operation_graph_renderer import (
    action_graph,
    action_graph_set,
)
from define.compiler.validator.reference_graph.reference_graph_validator_tests.test_helpers import (
    assert_propagation_chain,
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
    assert action_graph_set(result.operation_graphs) == {
        (_TEST, _MIDDLE),
        (
            _MIDDLE,
            "action<my.domain.com:my_lib:/empty_marker>",
        ),
        (
            _MIDDLE,
            "action<my.domain.com:my_lib:/fill_marker>",
        ),
    }


def test_destroyed_particle_guarantees_do_not_make_replacement_particle_occupied(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    diag = all_diags[0]
    assert isinstance(diag, diagnostics.DestroyInEmptyInterfacePositionDiagnostic)
    assert diag.location.line == 19
    assert diag.location.column == 33
    assert diag.location.end_line == 19
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
    assert action_graph_set(result.operation_graphs) == {
        (_TEST, _MIDDLE),
        (
            _TEST,
            "action<my.domain.com:my_lib:/empty_marker>",
        ),
        (
            _TEST,
            "action<my.domain.com:my_lib:/fill_marker>",
        ),
    }


def test_inner_empty_guarantee_propagates_through_outer(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert action_graph_set(result.operation_graphs) == {
        (_TEST, _OUTER),
        (_OUTER, _INNER),
    }


def test_inner_occupied_guarantee_propagates_through_outer(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert action_graph_set(result.operation_graphs) == {
        (_TEST, _OUTER),
        (_OUTER, _INNER),
    }


def test_occupied_guarantee_creates_empty_requirement(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.InferredRequirementViolationDiagnostic)
    assert all_diags[0].location.line == 12
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].action_name == "action<my.domain.com:my_lib:/outer>"
    assert all_diags[0].required_empty is True
    assert (
        all_diags[0].position_name
        == "position<box>::action</outer>::position<iface>::action</inner>::position<item>"
    )
    assert_propagation_chain(
        all_diags[0],
        {
            "kind": action_contract.PropagationKind.FILL_SITE,
            "enclosing_quality_name": "position<box>::action</outer>::position<iface>::action</inner>::position<item>",
            "triggered_quality_name": None,
            "line": 11,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _TEST,
            "triggered_quality_name": _OUTER,
            "line": 12,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _OUTER,
            "triggered_quality_name": _INNER,
            "line": 11,
            "column": 30,
            "file_path": "outer.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": _INNER,
            "triggered_quality_name": None,
            "line": 7,
            "column": 30,
            "file_path": "inner.dfn",
        },
    )
    assert action_graph_set(result.operation_graphs) == {
        (_TEST, _OUTER),
        (_OUTER, _INNER),
    }


def test_move_guarantee_creates_occupied_in_distant_caller(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.CreateInOccupiedPositionDiagnostic)
    assert (
        all_diags[0].position_name
        == "position<box>::action</outer>::position<iface>::action</inner>::position<output>"
    )
    assert all_diags[0].location.line == 12
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert action_graph_set(result.operation_graphs) == {
        (_TEST, _OUTER),
        (_OUTER, _INNER),
    }


def test_transitive_child_guarantee_follows_particle_through_move(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.CreateInOccupiedPositionDiagnostic)
    assert all_diags[0].location.line == 15
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert (
        all_diags[0].position_name
        == "position<gateway>::action</outer>::position<destination>::action</middle>::position<inner_parent>::action</inner>::position<result>"
    )
    assert action_graph_set(result.operation_graphs) == {
        (_TEST, _OUTER),
        (_OUTER, _MIDDLE),
        (_MIDDLE, _INNER),
    }


def test_transitive_child_guarantee_at_moved_position_follows_particle(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    diagnostic = all_diags[0]
    assert isinstance(diagnostic, diagnostics.CreateInOccupiedPositionDiagnostic)
    assert diagnostic.location.line == 15
    assert diagnostic.location.column == 30
    assert diagnostic.location.end_line == 15
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
    assert action_graph(result.operation_graphs) == [
        (_OUTER, _INNER),
        (_MIDDLE, _OUTER),
        (_TEST, _MIDDLE),
    ]
