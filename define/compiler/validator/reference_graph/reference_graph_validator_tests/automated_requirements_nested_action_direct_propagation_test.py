# pyright: reportUnusedCallResult=false
# Exception to CLAUDE.md "no docstrings in tests" rule: these tests have docstrings
# because the automated guarantee/requirement scenarios are complex enough to need
# prose explanations of what each test verifies.

from pathlib import PurePosixPath

from define.compiler import diagnostics
from define.compiler.conftest import (
    ValidateTestdataProjectWithReferenceGraph,
)
from define.compiler.validator.reference_graph import action_contract
from define.compiler.validator.reference_graph.operation_graph_renderer import (
    action_graph_set,
)
from define.compiler.validator.reference_graph.reference_graph_validator_tests.test_helpers import (
    assert_propagation_chain,
)
from define.compiler.validator.test_helpers import assert_no_errors

_TEST = "action<my.domain.com:my_lib:/test>"
_OUTER = "action<my.domain.com:my_lib:/outer>"
_INNER = "action<my.domain.com:my_lib:/inner>"
_MIDDLE = "action<my.domain.com:my_lib:/middle>"


def test_inner_chained_action_empty_requirement_propagates(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.InferredRequirementViolationDiagnostic)
    assert all_diags[0].location.line == 20
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
            "line": 19,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _TEST,
            "triggered_quality_name": _OUTER,
            "line": 20,
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


def test_doubly_nested_action_requirement_propagates(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    diag = all_diags[0]
    assert isinstance(diag, diagnostics.InferredRequirementViolationDiagnostic)
    assert diag.location.line == 22
    assert diag.location.column == 30
    assert diag.location.file_path == PurePosixPath("test.dfn")
    assert diag.required_empty is True
    assert diag.action_name == "action<my.domain.com:my_lib:/outer>"
    assert (
        diag.position_name
        == "position<box>::action</outer>::position<out_iface>::action</middle>::position<mid_iface>::action</inner>::position<item>"
    )
    assert_propagation_chain(
        diag,
        {
            "kind": action_contract.PropagationKind.FILL_SITE,
            "enclosing_quality_name": "position<box>::action</outer>::position<out_iface>::action</middle>::position<mid_iface>::action</inner>::position<item>",
            "triggered_quality_name": None,
            "line": 21,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _TEST,
            "triggered_quality_name": _OUTER,
            "line": 22,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _OUTER,
            "triggered_quality_name": _MIDDLE,
            "line": 11,
            "column": 30,
            "file_path": "outer.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _MIDDLE,
            "triggered_quality_name": _INNER,
            "line": 11,
            "column": 30,
            "file_path": "middle.dfn",
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
        (_MIDDLE, _INNER),
        (_TEST, _OUTER),
        (_OUTER, _MIDDLE),
    }


def test_four_deep_action_chain_requirement_propagates(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.InferredRequirementViolationDiagnostic)
    assert all_diags[0].location.line == 22
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].required_empty is True
    assert all_diags[0].action_name == "action<my.domain.com:my_lib:/a>"
    assert (
        all_diags[0].position_name
        == "position<box>::action</a>::position<a_iface>::action</b>::position<b_iface>::action</c>::position<c_iface>::action</d>::position<item>"
    )
    assert_propagation_chain(
        all_diags[0],
        {
            "kind": action_contract.PropagationKind.FILL_SITE,
            "enclosing_quality_name": "position<box>::action</a>::position<a_iface>::action</b>::position<b_iface>::action</c>::position<c_iface>::action</d>::position<item>",
            "triggered_quality_name": None,
            "line": 21,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _TEST,
            "triggered_quality_name": "action<my.domain.com:my_lib:/a>",
            "line": 22,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/a>",
            "triggered_quality_name": "action<my.domain.com:my_lib:/b>",
            "line": 11,
            "column": 30,
            "file_path": "a.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/b>",
            "triggered_quality_name": "action<my.domain.com:my_lib:/c>",
            "line": 11,
            "column": 30,
            "file_path": "b.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/c>",
            "triggered_quality_name": "action<my.domain.com:my_lib:/d>",
            "line": 11,
            "column": 30,
            "file_path": "c.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/d>",
            "triggered_quality_name": None,
            "line": 7,
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
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.InferredRequirementViolationDiagnostic)
    assert all_diags[0].location.line == 21
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].required_empty is True
    assert (
        all_diags[0].position_name
        == "position<box>::action</outer>::position<iface>::action</inner>::position<dest>"
    )
    assert_propagation_chain(
        all_diags[0],
        {
            "kind": action_contract.PropagationKind.FILL_SITE,
            "enclosing_quality_name": "position<box>::action</outer>::position<iface>::action</inner>::position<dest>",
            "triggered_quality_name": None,
            "line": 20,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _TEST,
            "triggered_quality_name": _OUTER,
            "line": 21,
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
            "column": 47,
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
