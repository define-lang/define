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
_INNER = "action<my.domain.com:my_lib:/inner>"
_MIDDLE = "action<my.domain.com:my_lib:/middle>"


def test_move_carried_child_satisfies_inner_occupied_requirement(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)


def test_move_without_the_carried_child_violates_inner_occupied_requirement(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.InferredRequirementViolationDiagnostic)
    assert all_diags[0].location.line == 18
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.end_line == 18
    assert all_diags[0].location.end_column == 74
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].action_name == _MIDDLE
    assert all_diags[0].required_empty is False
    assert (
        all_diags[0].position_name
        == "position<mw>::action</middle>::position<iface>::position</parent>"
    )
    assert_propagation_chain(
        all_diags[0],
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _TEST,
            "triggered_quality_name": _MIDDLE,
            "line": 18,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _MIDDLE,
            "triggered_quality_name": _INNER,
            "line": 18,
            "column": 30,
            "file_path": "middle.dfn",
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
    assert action_graph_set(result.operation_graphs) == {
        (_TEST, _MIDDLE),
        (_MIDDLE, _INNER),
    }


def test_filled_carried_child_violates_inner_empty_requirement(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.InferredRequirementViolationDiagnostic)
    assert all_diags[0].location.line == 15
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.end_line == 15
    assert all_diags[0].location.end_column == 74
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].action_name == _MIDDLE
    assert all_diags[0].required_empty is True
    assert (
        all_diags[0].position_name
        == "position<mw>::action</middle>::position<iface>::position</marker>"
    )
    assert_propagation_chain(
        all_diags[0],
        {
            "kind": action_contract.PropagationKind.FILL_SITE,
            "enclosing_quality_name": "position<mw>::action</middle>::position<iface>::position</marker>",
            "triggered_quality_name": None,
            "line": 14,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _TEST,
            "triggered_quality_name": _MIDDLE,
            "line": 15,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _MIDDLE,
            "triggered_quality_name": _INNER,
            "line": 18,
            "column": 30,
            "file_path": "middle.dfn",
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
    assert action_graph_set(result.operation_graphs) == {
        (_TEST, _MIDDLE),
        (_MIDDLE, _INNER),
    }


def test_carried_grandchild_satisfies_inner_occupied_requirement(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)


def test_empty_carried_grandchild_and_parent_violate_inner_occupied_requirement(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 2
    assert isinstance(all_diags[0], diagnostics.InferredRequirementViolationDiagnostic)
    assert all_diags[0].location.line == 14
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.end_line == 14
    assert all_diags[0].location.end_column == 74
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].action_name == _MIDDLE
    assert all_diags[0].required_empty is False
    assert (
        all_diags[0].position_name
        == "position<mw>::action</middle>::position<iface>::position</b>"
    )
    assert_propagation_chain(
        all_diags[0],
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _TEST,
            "triggered_quality_name": _MIDDLE,
            "line": 14,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _MIDDLE,
            "triggered_quality_name": _INNER,
            "line": 18,
            "column": 30,
            "file_path": "middle.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": _INNER,
            "triggered_quality_name": None,
            "line": 11,
            "column": 33,
            "file_path": "inner.dfn",
        },
    )
    assert isinstance(all_diags[1], diagnostics.InferredRequirementViolationDiagnostic)
    assert all_diags[1].location.line == 14
    assert all_diags[1].location.column == 30
    assert all_diags[1].location.end_line == 14
    assert all_diags[1].location.end_column == 74
    assert all_diags[1].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[1].action_name == _MIDDLE
    assert all_diags[1].required_empty is False
    assert (
        all_diags[1].position_name
        == "position<mw>::action</middle>::position<iface>::position</b>::position</c>"
    )
    assert_propagation_chain(
        all_diags[1],
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _TEST,
            "triggered_quality_name": _MIDDLE,
            "line": 14,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _MIDDLE,
            "triggered_quality_name": _INNER,
            "line": 18,
            "column": 30,
            "file_path": "middle.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": _INNER,
            "triggered_quality_name": None,
            "line": 11,
            "column": 33,
            "file_path": "inner.dfn",
        },
    )
    assert action_graph_set(result.operation_graphs) == {
        (_TEST, _MIDDLE),
        (_MIDDLE, _INNER),
    }


def test_empty_carried_grandchild_satisfies_inner_empty_requirement(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)


def test_filled_carried_grandchild_violates_inner_empty_requirement(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.InferredRequirementViolationDiagnostic)
    assert all_diags[0].location.line == 16
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.end_line == 16
    assert all_diags[0].location.end_column == 74
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].action_name == _MIDDLE
    assert all_diags[0].required_empty is True
    assert (
        all_diags[0].position_name
        == "position<mw>::action</middle>::position<iface>::position</b>::position</c>"
    )
    assert_propagation_chain(
        all_diags[0],
        {
            "kind": action_contract.PropagationKind.FILL_SITE,
            "enclosing_quality_name": "position<mw>::action</middle>::position<iface>::position</b>::position</c>",
            "triggered_quality_name": None,
            "line": 15,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _TEST,
            "triggered_quality_name": _MIDDLE,
            "line": 16,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _MIDDLE,
            "triggered_quality_name": _INNER,
            "line": 18,
            "column": 30,
            "file_path": "middle.dfn",
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
    assert action_graph_set(result.operation_graphs) == {
        (_TEST, _MIDDLE),
        (_MIDDLE, _INNER),
    }
