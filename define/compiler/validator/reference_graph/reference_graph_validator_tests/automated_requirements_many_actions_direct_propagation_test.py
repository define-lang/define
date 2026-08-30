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
_INNER = "action<my.domain.com:my_lib:/inner>"
_MIDDLE = "action<my.domain.com:my_lib:/middle>"
_CALL_FILL = "action<my.domain.com:my_lib:/call_fill>"
_CONSUME_ITEM = "action<my.domain.com:my_lib:/consume_item>"
_FILL_ITEM = "action<my.domain.com:my_lib:/fill_item>"
_CONSUME_CHAIN = "action<my.domain.com:my_lib:/consume_chain>"
_CONSUME_BRANCHES = "action<my.domain.com:my_lib:/consume_branches>"
_CONSUME_COMBINED = "action<my.domain.com:my_lib:/consume_combined>"
_CALL_CHILD = "action<my.domain.com:my_lib:/call_child>"
_CALL_PARENT = "action<my.domain.com:my_lib:/call_parent>"
_FILL_CHILD = "action<my.domain.com:my_lib:/fill_child>"
_FILL_PARENT = "action<my.domain.com:my_lib:/fill_parent>"


def test_inner_chained_action_empty_requirement_propagates(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.InferredRequirementViolationDiagnostic)
    assert all_diags[0].location.line == 24
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].action_name == "action<my.domain.com:my_lib:/outer>"
    assert all_diags[0].required_empty is True
    assert (
        all_diags[0].position_name
        == "position<outer_holder>::action</outer>::position<input>::position</item>"
    )
    assert_propagation_chain(
        all_diags[0],
        {
            "kind": action_contract.PropagationKind.FILL_SITE,
            "enclosing_quality_name": "position<outer_holder>::action</outer>::position<input>::position</item>",
            "triggered_quality_name": None,
            "line": 21,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _TEST,
            "triggered_quality_name": _OUTER,
            "line": 24,
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
    assert action_graph_set(result.operation_graphs) == {
        (_TEST, _OUTER),
        (_OUTER, _INNER),
    }


def test_inner_chained_action_empty_requirement_satisfied(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert action_graph_set(result.operation_graphs) == {
        (_TEST, _OUTER),
        (_OUTER, _INNER),
    }


def test_inner_chained_action_occupied_requirement_propagates(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.InferredRequirementViolationDiagnostic)
    assert all_diags[0].location.line == 17
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].action_name == "action<my.domain.com:my_lib:/outer>"
    assert all_diags[0].required_empty is False
    assert (
        all_diags[0].position_name
        == "position<box>::action</outer>::position<iface>::action</inner>::position<item>"
    )
    assert_propagation_chain(
        all_diags[0],
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _TEST,
            "triggered_quality_name": _OUTER,
            "line": 17,
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
            "line": 8,
            "column": 30,
            "file_path": "inner.dfn",
        },
    )
    assert action_graph_set(result.operation_graphs) == {
        (_TEST, _OUTER),
        (_OUTER, _INNER),
    }


def test_inner_chained_action_occupied_requirement_caller_fills(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert action_graph_set(result.operation_graphs) == {
        (_TEST, _OUTER),
        (_OUTER, _INNER),
    }


def test_pending_transitive_guarantee_satisfies_later_action_requirement(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert action_graph_set(result.operation_graphs) == {
        (_TEST, _CALL_FILL),
        (_CALL_FILL, _FILL_ITEM),
        (_TEST, _CONSUME_ITEM),
        (_CONSUME_ITEM, _CALL_FILL),
    }


def test_pending_guarantees_on_one_position_chain_satisfy_later_requirements(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert action_graph_set(result.operation_graphs) == {
        (_TEST, _CALL_PARENT),
        (_CALL_PARENT, _FILL_PARENT),
        (_TEST, _CALL_CHILD),
        (_CALL_CHILD, _FILL_CHILD),
        (_TEST, _CONSUME_CHAIN),
    }


def test_pending_guarantees_on_separate_position_chains_satisfy_later_requirements(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert action_graph_set(result.operation_graphs) == {
        (_TEST, _CALL_FILL),
        (_CALL_FILL, _FILL_ITEM),
        (_TEST, _CONSUME_BRANCHES),
    }


def test_pending_guarantees_on_shared_and_separate_position_chains_satisfy_later_requirements(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert action_graph(result.operation_graphs) == [
        (_CALL_PARENT, _FILL_PARENT),
        (_CALL_CHILD, _FILL_CHILD),
        (_CALL_FILL, _FILL_ITEM),
        (_TEST, _CALL_CHILD),
        (_TEST, _CALL_PARENT),
        (_TEST, _CALL_FILL),
        (_TEST, _CONSUME_COMBINED),
    ]


def test_pending_guarantees_on_shared_and_separate_position_chains_violate_later_requirements(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 3
    parent_marker_diagnostic = all_diags[0]
    assert isinstance(
        parent_marker_diagnostic,
        diagnostics.InferredRequirementViolationDiagnostic,
    )
    assert parent_marker_diagnostic.location.line == 33
    assert parent_marker_diagnostic.location.column == 30
    assert parent_marker_diagnostic.location.end_line == 33
    assert parent_marker_diagnostic.location.end_column == 93
    assert parent_marker_diagnostic.location.file_path == PurePosixPath("test.dfn")
    assert (
        parent_marker_diagnostic.position_name
        == "position<box>::action</consume_combined>::position<left>::position</prepared_input>::position</parent_marker>"
    )
    assert parent_marker_diagnostic.required_empty is True
    assert parent_marker_diagnostic.action_name == _CONSUME_COMBINED
    assert_propagation_chain(
        parent_marker_diagnostic,
        {
            "kind": action_contract.PropagationKind.FILL_SITE,
            "enclosing_quality_name": parent_marker_diagnostic.position_name,
            "triggered_quality_name": None,
            "line": 7,
            "column": 30,
            "file_path": "fill_parent.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _TEST,
            "triggered_quality_name": _CONSUME_COMBINED,
            "line": 33,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": _CONSUME_COMBINED,
            "triggered_quality_name": None,
            "line": 16,
            "column": 30,
            "file_path": "consume_combined.dfn",
        },
    )
    assert parent_marker_diagnostic.propagation_chain[0].location.end_line == 7
    assert parent_marker_diagnostic.propagation_chain[0].location.end_column == 54
    assert parent_marker_diagnostic.propagation_chain[1].location.end_line == 33
    assert parent_marker_diagnostic.propagation_chain[1].location.end_column == 93
    assert parent_marker_diagnostic.propagation_chain[2].location.end_line == 16
    assert parent_marker_diagnostic.propagation_chain[2].location.end_column == 97

    child_marker_diagnostic = all_diags[1]
    assert isinstance(
        child_marker_diagnostic,
        diagnostics.InferredRequirementViolationDiagnostic,
    )
    assert child_marker_diagnostic.location.line == 33
    assert child_marker_diagnostic.location.column == 30
    assert child_marker_diagnostic.location.end_line == 33
    assert child_marker_diagnostic.location.end_column == 93
    assert child_marker_diagnostic.location.file_path == PurePosixPath("test.dfn")
    assert (
        child_marker_diagnostic.position_name
        == "position<box>::action</consume_combined>::position<left>::position</prepared_input>::position</child>::position</child_marker>"
    )
    assert child_marker_diagnostic.required_empty is True
    assert child_marker_diagnostic.action_name == _CONSUME_COMBINED
    assert_propagation_chain(
        child_marker_diagnostic,
        {
            "kind": action_contract.PropagationKind.FILL_SITE,
            "enclosing_quality_name": child_marker_diagnostic.position_name,
            "triggered_quality_name": None,
            "line": 7,
            "column": 30,
            "file_path": "fill_child.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _TEST,
            "triggered_quality_name": _CONSUME_COMBINED,
            "line": 33,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": _CONSUME_COMBINED,
            "triggered_quality_name": None,
            "line": 17,
            "column": 30,
            "file_path": "consume_combined.dfn",
        },
    )
    assert child_marker_diagnostic.propagation_chain[0].location.end_line == 7
    assert child_marker_diagnostic.propagation_chain[0].location.end_column == 53
    assert child_marker_diagnostic.propagation_chain[1].location.end_line == 33
    assert child_marker_diagnostic.propagation_chain[1].location.end_column == 93
    assert child_marker_diagnostic.propagation_chain[2].location.end_line == 17
    assert child_marker_diagnostic.propagation_chain[2].location.end_column == 114

    item_diagnostic = all_diags[2]
    assert isinstance(
        item_diagnostic, diagnostics.InferredRequirementViolationDiagnostic
    )
    assert item_diagnostic.location.line == 33
    assert item_diagnostic.location.column == 30
    assert item_diagnostic.location.end_line == 33
    assert item_diagnostic.location.end_column == 93
    assert item_diagnostic.location.file_path == PurePosixPath("test.dfn")
    assert (
        item_diagnostic.position_name
        == "position<box>::action</consume_combined>::position<right>::position</fillable>::position</item>"
    )
    assert item_diagnostic.required_empty is True
    assert item_diagnostic.action_name == _CONSUME_COMBINED
    assert_propagation_chain(
        item_diagnostic,
        {
            "kind": action_contract.PropagationKind.FILL_SITE,
            "enclosing_quality_name": item_diagnostic.position_name,
            "triggered_quality_name": None,
            "line": 7,
            "column": 30,
            "file_path": "fill_item.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _TEST,
            "triggered_quality_name": _CONSUME_COMBINED,
            "line": 33,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": _CONSUME_COMBINED,
            "triggered_quality_name": None,
            "line": 18,
            "column": 30,
            "file_path": "consume_combined.dfn",
        },
    )
    assert item_diagnostic.propagation_chain[0].location.end_line == 7
    assert item_diagnostic.propagation_chain[0].location.end_column == 45
    assert item_diagnostic.propagation_chain[1].location.end_line == 33
    assert item_diagnostic.propagation_chain[1].location.end_column == 93
    assert item_diagnostic.propagation_chain[2].location.end_line == 18
    assert item_diagnostic.propagation_chain[2].location.end_column == 83
    assert action_graph(result.operation_graphs) == [
        (_CALL_PARENT, _FILL_PARENT),
        (_CALL_CHILD, _FILL_CHILD),
        (_CALL_FILL, _FILL_ITEM),
        (_TEST, _CALL_CHILD),
        (_TEST, _CALL_PARENT),
        (_TEST, _CALL_FILL),
        (_TEST, _CONSUME_COMBINED),
    ]


def test_three_deep_action_chain_requirement_propagates(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    diag = all_diags[0]
    assert isinstance(diag, diagnostics.InferredRequirementViolationDiagnostic)
    assert diag.location.line == 24
    assert diag.location.column == 30
    assert diag.location.file_path == PurePosixPath("test.dfn")
    assert diag.required_empty is True
    assert diag.action_name == "action<my.domain.com:my_lib:/outer>"
    assert (
        diag.position_name
        == "position<outer_holder>::action</outer>::position<input>::position</item>"
    )
    assert_propagation_chain(
        diag,
        {
            "kind": action_contract.PropagationKind.FILL_SITE,
            "enclosing_quality_name": "position<outer_holder>::action</outer>::position<input>::position</item>",
            "triggered_quality_name": None,
            "line": 21,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _TEST,
            "triggered_quality_name": _OUTER,
            "line": 24,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _OUTER,
            "triggered_quality_name": _MIDDLE,
            "line": 18,
            "column": 30,
            "file_path": "outer.dfn",
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
        (_MIDDLE, _INNER),
        (_TEST, _OUTER),
        (_OUTER, _MIDDLE),
    }


def test_four_deep_action_chain_requirement_propagates(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.InferredRequirementViolationDiagnostic)
    assert all_diags[0].location.line == 24
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].required_empty is True
    assert all_diags[0].action_name == "action<my.domain.com:my_lib:/a>"
    assert (
        all_diags[0].position_name
        == "position<a_holder>::action</a>::position<input>::position</item>"
    )
    assert_propagation_chain(
        all_diags[0],
        {
            "kind": action_contract.PropagationKind.FILL_SITE,
            "enclosing_quality_name": "position<a_holder>::action</a>::position<input>::position</item>",
            "triggered_quality_name": None,
            "line": 21,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _TEST,
            "triggered_quality_name": "action<my.domain.com:my_lib:/a>",
            "line": 24,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/a>",
            "triggered_quality_name": "action<my.domain.com:my_lib:/b>",
            "line": 18,
            "column": 30,
            "file_path": "a.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/b>",
            "triggered_quality_name": "action<my.domain.com:my_lib:/c>",
            "line": 18,
            "column": 30,
            "file_path": "b.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/c>",
            "triggered_quality_name": "action<my.domain.com:my_lib:/d>",
            "line": 18,
            "column": 30,
            "file_path": "c.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/d>",
            "triggered_quality_name": None,
            "line": 11,
            "column": 30,
            "file_path": "d.dfn",
        },
    )
    assert action_graph_set(result.operation_graphs) == {
        ("action<my.domain.com:my_lib:/c>", "action<my.domain.com:my_lib:/d>"),
        (_TEST, "action<my.domain.com:my_lib:/a>"),
        ("action<my.domain.com:my_lib:/a>", "action<my.domain.com:my_lib:/b>"),
        ("action<my.domain.com:my_lib:/b>", "action<my.domain.com:my_lib:/c>"),
    }


def test_both_requirements_propagate_when_inner_has_both(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.InferredRequirementViolationDiagnostic)
    assert all_diags[0].location.line == 27
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].required_empty is True
    assert (
        all_diags[0].position_name
        == "position<outer_holder>::action</outer>::position<input>::position</dest>"
    )
    assert_propagation_chain(
        all_diags[0],
        {
            "kind": action_contract.PropagationKind.FILL_SITE,
            "enclosing_quality_name": "position<outer_holder>::action</outer>::position<input>::position</dest>",
            "triggered_quality_name": None,
            "line": 24,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _TEST,
            "triggered_quality_name": _OUTER,
            "line": 27,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _OUTER,
            "triggered_quality_name": _INNER,
            "line": 19,
            "column": 30,
            "file_path": "outer.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": _INNER,
            "triggered_quality_name": None,
            "line": 12,
            "column": 65,
            "file_path": "inner.dfn",
        },
    )
    assert action_graph_set(result.operation_graphs) == {
        (_TEST, _OUTER),
        (_OUTER, _INNER),
    }


def test_trigger_position_child_empty_requirement_propagates(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    diag = all_diags[0]
    assert isinstance(diag, diagnostics.InferredRequirementViolationDiagnostic)
    assert diag.location.line == 24
    assert diag.location.column == 30
    assert diag.location.file_path == PurePosixPath("test.dfn")
    assert diag.required_empty is True
    assert diag.action_name == "action<my.domain.com:my_lib:/outer>"
    assert (
        diag.position_name
        == "position<box>::action</outer>::position<source>::position</x>"
    )
    assert_propagation_chain(
        diag,
        {
            "kind": action_contract.PropagationKind.FILL_SITE,
            "enclosing_quality_name": "position<box>::action</outer>::position<source>::position</x>",
            "triggered_quality_name": None,
            "line": 23,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _TEST,
            "triggered_quality_name": _OUTER,
            "line": 24,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _OUTER,
            "triggered_quality_name": _INNER,
            "line": 16,
            "column": 50,
            "file_path": "outer.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": _INNER,
            "triggered_quality_name": None,
            "line": 10,
            "column": 30,
            "file_path": "inner.dfn",
        },
    )
    assert action_graph_set(result.operation_graphs) == {
        (_TEST, _OUTER),
        (_OUTER, _INNER),
    }


def test_trigger_position_child_occupied_requirement_propagates(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.InferredRequirementViolationDiagnostic)
    assert all_diags[0].location.line == 14
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].required_empty is False
    assert all_diags[0].action_name == "action<my.domain.com:my_lib:/outer>"
    assert (
        all_diags[0].position_name
        == "position<box>::action</outer>::position<source>::position</x>"
    )
    assert_propagation_chain(
        all_diags[0],
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _TEST,
            "triggered_quality_name": _OUTER,
            "line": 14,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _OUTER,
            "triggered_quality_name": _INNER,
            "line": 17,
            "column": 50,
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
