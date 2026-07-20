# pyright: reportUnusedCallResult=false

from pathlib import PurePosixPath

from define.compiler import diagnostics
from define.compiler.conftest import (
    ValidateTestdataProjectWithReferenceGraph,
)
from define.compiler.validator.reference_graph import action_contract
from define.compiler.validator.reference_graph.reference_graph_validator_tests.test_helpers import (
    assert_propagation_chain,
)
from define.compiler.validator.test_helpers import assert_no_errors

_TEST = "action<my.domain.com:my_lib:/test>"
_P = "action<my.domain.com:my_lib:/p>"
_Q = "position<my.domain.com:my_lib:/q>"
_IMPLIED_ACTION = "action<my.domain.com:my_lib:/implied_action>"


def test_constructor_occupied_violation_via_destroy_of_implied(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    diag = all_diags[0]
    assert isinstance(
        diag,
        diagnostics.InferredRequirementViolationDiagnostic,
    )
    assert diag.action_name == _P
    assert diag.required_empty is False
    assert diag.position_name == "position<box>::position</q>"
    assert diag.location.line == 11
    assert diag.location.column == 30
    assert diag.location.end_line == 11
    assert diag.location.end_column == 43
    assert diag.location.file_path == PurePosixPath("test.dfn")
    assert_propagation_chain(
        diag,
        {
            "kind": action_contract.PropagationKind.QUALITY_ASSIGNED,
            "enclosing_quality_name": "position<box>",
            "triggered_quality_name": "action<my.domain.com:my_lib:/p>",
            "line": 8,
            "column": 28,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.CONSTRUCTOR_TRIGGER,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/test>",
            "triggered_quality_name": "action<my.domain.com:my_lib:/p>",
            "line": 11,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/p>",
            "triggered_quality_name": None,
            "line": 6,
            "column": 33,
            "file_path": "p.dfn",
        },
    )


def test_constructor_occupied_violation_via_move_source_of_implied(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    diag = all_diags[0]
    assert isinstance(
        diag,
        diagnostics.InferredRequirementViolationDiagnostic,
    )
    assert diag.action_name == _P
    assert diag.required_empty is False
    assert diag.position_name == "position<box>::position</q>"
    assert diag.location.line == 11
    assert diag.location.column == 30
    assert diag.location.file_path == PurePosixPath("test.dfn")
    assert_propagation_chain(
        diag,
        {
            "kind": action_contract.PropagationKind.QUALITY_ASSIGNED,
            "enclosing_quality_name": "position<box>",
            "triggered_quality_name": "action<my.domain.com:my_lib:/p>",
            "line": 8,
            "column": 28,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.CONSTRUCTOR_TRIGGER,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/test>",
            "triggered_quality_name": "action<my.domain.com:my_lib:/p>",
            "line": 11,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/p>",
            "triggered_quality_name": None,
            "line": 7,
            "column": 30,
            "file_path": "p.dfn",
        },
    )


def test_constructor_satisfied_requirement_emits_no_diagnostic(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)


def test_constructor_multiple_implied_positions_each_check_runs(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 2
    diag_q = all_diags[0]
    diag_r = all_diags[1]
    assert isinstance(diag_q, diagnostics.InferredRequirementViolationDiagnostic)
    assert diag_q.action_name == _P
    assert diag_q.required_empty is False
    assert diag_q.position_name == "position<box>::position</q>"
    assert diag_q.location.line == 11
    assert diag_q.location.column == 30
    assert diag_q.location.file_path == PurePosixPath("test.dfn")
    assert_propagation_chain(
        diag_q,
        {
            "kind": action_contract.PropagationKind.QUALITY_ASSIGNED,
            "enclosing_quality_name": "position<box>",
            "triggered_quality_name": "action<my.domain.com:my_lib:/p>",
            "line": 8,
            "column": 28,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.CONSTRUCTOR_TRIGGER,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/test>",
            "triggered_quality_name": "action<my.domain.com:my_lib:/p>",
            "line": 11,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/p>",
            "triggered_quality_name": None,
            "line": 7,
            "column": 33,
            "file_path": "p.dfn",
        },
    )
    assert isinstance(diag_r, diagnostics.InferredRequirementViolationDiagnostic)
    assert diag_r.action_name == _P
    assert diag_r.required_empty is False
    assert diag_r.position_name == "position<box>::position</r>"
    assert diag_r.location.line == 11
    assert diag_r.location.column == 30
    assert diag_r.location.file_path == PurePosixPath("test.dfn")
    assert_propagation_chain(
        diag_r,
        {
            "kind": action_contract.PropagationKind.QUALITY_ASSIGNED,
            "enclosing_quality_name": "position<box>",
            "triggered_quality_name": _P,
            "line": 8,
            "column": 28,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.CONSTRUCTOR_TRIGGER,
            "enclosing_quality_name": _TEST,
            "triggered_quality_name": _P,
            "line": 11,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": _P,
            "triggered_quality_name": None,
            "line": 8,
            "column": 33,
            "file_path": "p.dfn",
        },
    )


def test_constructor_occupied_violation_via_destroy_of_child_of_implied(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    diag = all_diags[0]
    assert isinstance(
        diag,
        diagnostics.InferredRequirementViolationDiagnostic,
    )
    assert diag.action_name == _P
    assert diag.required_empty is False
    assert diag.position_name == "position<box>::position</q>::position</child>"
    assert diag.location.line == 11
    assert diag.location.column == 30
    assert diag.location.file_path == PurePosixPath("test.dfn")
    assert_propagation_chain(
        diag,
        {
            "kind": action_contract.PropagationKind.QUALITY_ASSIGNED,
            "enclosing_quality_name": "position<box>",
            "triggered_quality_name": "action<my.domain.com:my_lib:/p>",
            "line": 8,
            "column": 28,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.CONSTRUCTOR_TRIGGER,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/test>",
            "triggered_quality_name": "action<my.domain.com:my_lib:/p>",
            "line": 11,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/p>",
            "triggered_quality_name": None,
            "line": 7,
            "column": 33,
            "file_path": "p.dfn",
        },
    )


def test_constructor_occupied_violation_via_move_source_of_child_of_implied(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    diag = all_diags[0]
    assert isinstance(
        diag,
        diagnostics.InferredRequirementViolationDiagnostic,
    )
    assert diag.action_name == _P
    assert diag.required_empty is False
    assert diag.position_name == "position<box>::position</q>::position</child>"
    assert diag.location.line == 11
    assert diag.location.column == 30
    assert diag.location.file_path == PurePosixPath("test.dfn")
    assert_propagation_chain(
        diag,
        {
            "kind": action_contract.PropagationKind.QUALITY_ASSIGNED,
            "enclosing_quality_name": "position<box>",
            "triggered_quality_name": "action<my.domain.com:my_lib:/p>",
            "line": 8,
            "column": 28,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.CONSTRUCTOR_TRIGGER,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/test>",
            "triggered_quality_name": "action<my.domain.com:my_lib:/p>",
            "line": 11,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/p>",
            "triggered_quality_name": None,
            "line": 8,
            "column": 30,
            "file_path": "p.dfn",
        },
    )


def test_constructor_satisfied_requirement_for_child_of_implied_emits_no_diagnostic(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)


def test_constructor_occupied_violation_via_destroy_of_grandchild_of_implied(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    diag = all_diags[0]
    assert isinstance(
        diag,
        diagnostics.InferredRequirementViolationDiagnostic,
    )
    assert diag.action_name == _P
    assert diag.required_empty is False
    assert (
        diag.position_name
        == "position<box>::position</q>::position</child>::position</grandchild>"
    )
    assert diag.location.line == 11
    assert diag.location.column == 30
    assert diag.location.file_path == PurePosixPath("test.dfn")
    assert_propagation_chain(
        diag,
        {
            "kind": action_contract.PropagationKind.QUALITY_ASSIGNED,
            "enclosing_quality_name": "position<box>",
            "triggered_quality_name": "action<my.domain.com:my_lib:/p>",
            "line": 8,
            "column": 28,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.CONSTRUCTOR_TRIGGER,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/test>",
            "triggered_quality_name": "action<my.domain.com:my_lib:/p>",
            "line": 11,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/p>",
            "triggered_quality_name": None,
            "line": 8,
            "column": 33,
            "file_path": "p.dfn",
        },
    )


def test_constructor_occupied_violation_via_destroy_of_iface_of_action_in_implied_chain(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    diag = all_diags[0]
    assert isinstance(
        diag,
        diagnostics.InferredRequirementViolationDiagnostic,
    )
    assert diag.action_name == _P
    assert diag.required_empty is False
    assert (
        diag.position_name
        == "position<box>::position</q>::position</outer>::action</a>::position<iface>"
    )
    assert diag.location.line == 11
    assert diag.location.column == 30
    assert diag.location.file_path == PurePosixPath("test.dfn")
    assert_propagation_chain(
        diag,
        {
            "kind": action_contract.PropagationKind.QUALITY_ASSIGNED,
            "enclosing_quality_name": "position<box>",
            "triggered_quality_name": "action<my.domain.com:my_lib:/p>",
            "line": 8,
            "column": 28,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.CONSTRUCTOR_TRIGGER,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/test>",
            "triggered_quality_name": "action<my.domain.com:my_lib:/p>",
            "line": 11,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/p>",
            "triggered_quality_name": None,
            "line": 8,
            "column": 33,
            "file_path": "p.dfn",
        },
    )


def test_constructor_occupied_violation_via_destroy_of_child_of_iface_of_action_in_implied_chain(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    diag = all_diags[0]
    assert isinstance(
        diag,
        diagnostics.InferredRequirementViolationDiagnostic,
    )
    assert diag.action_name == _P
    assert diag.required_empty is False
    assert (
        diag.position_name
        == "position<box>::position</q>::position</outer>::action</a>::position<iface>::position</child>"
    )
    assert diag.location.line == 11
    assert diag.location.column == 30
    assert diag.location.file_path == PurePosixPath("test.dfn")
    assert_propagation_chain(
        diag,
        {
            "kind": action_contract.PropagationKind.QUALITY_ASSIGNED,
            "enclosing_quality_name": "position<box>",
            "triggered_quality_name": "action<my.domain.com:my_lib:/p>",
            "line": 8,
            "column": 28,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.CONSTRUCTOR_TRIGGER,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/test>",
            "triggered_quality_name": "action<my.domain.com:my_lib:/p>",
            "line": 11,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/p>",
            "triggered_quality_name": None,
            "line": 9,
            "column": 33,
            "file_path": "p.dfn",
        },
    )


def test_constructor_action_requirement_violation_via_triggering_implied_action(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    diag = all_diags[0]
    assert isinstance(diag, diagnostics.InferredRequirementViolationDiagnostic)
    assert diag.location.line == 7
    assert diag.location.column == 30
    assert diag.location.end_line == 7
    assert diag.location.end_column == 96
    assert diag.location.file_path == PurePosixPath("p.dfn")
    assert diag.action_name == _IMPLIED_ACTION
    assert diag.required_empty is False
    assert (
        diag.position_name
        == "position</carrier>::action</implied_action>::position<item>"
    )
    assert_propagation_chain(
        diag,
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _P,
            "triggered_quality_name": _IMPLIED_ACTION,
            "line": 7,
            "column": 30,
            "file_path": "p.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": _IMPLIED_ACTION,
            "triggered_quality_name": None,
            "line": 7,
            "column": 33,
            "file_path": "implied_action.dfn",
        },
    )
