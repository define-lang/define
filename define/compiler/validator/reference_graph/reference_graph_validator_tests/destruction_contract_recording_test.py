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
_CLOSE_FILE = "action<my.domain.com:my_lib:/close_file>"
_CLOSE_TWO = "action<my.domain.com:my_lib:/close_two>"
_MID = "action<my.domain.com:my_lib:/mid>"
_DESTRUCTOR = "action<my.domain.com:my_lib:/destructor>"
_DELETE_DESTRUCTOR = "action<my.domain.com:my_lib:/delete_destructor>"


def test_contract_keyed_on_contracted_origin_after_move(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.InferredRequirementViolationDiagnostic)
    assert all_diags[0].location.line == 21
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert not all_diags[0].required_empty
    assert all_diags[0].action_name == _MID
    assert (
        all_diags[0].position_name
        == "position<box>::action</mid>::position<incoming>::position</file>"
    )
    assert_propagation_chain(
        all_diags[0],
        {
            "kind": action_contract.PropagationKind.QUALITY_ASSIGNED,
            "enclosing_quality_name": "position<my_file>",
            "triggered_quality_name": _DELETE_DESTRUCTOR,
            "line": 15,
            "column": 28,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.PARTICLE_ORIGIN,
            "enclosing_quality_name": "position<box>::action</mid>::position<incoming>",
            "triggered_quality_name": None,
            "line": 19,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _TEST,
            "triggered_quality_name": _MID,
            "line": 21,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DESTRUCTOR_CASCADE,
            "enclosing_quality_name": _MID,
            "triggered_quality_name": _DELETE_DESTRUCTOR,
            "line": 9,
            "column": 33,
            "file_path": "mid.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": _DELETE_DESTRUCTOR,
            "triggered_quality_name": None,
            "line": 7,
            "column": 30,
            "file_path": "delete_destructor.dfn",
        },
    )
    assert result.action_call_graph.edges() == [
        (_MID, _DELETE_DESTRUCTOR),
        (_TEST, _MID),
    ]


def test_moved_in_contracted_origin_requirement_satisfied(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert result.action_call_graph.edges() == [
        (_MID, _DELETE_DESTRUCTOR),
        (_TEST, _MID),
    ]


def test_auto_destruction_records_contract_verified_by_caller(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.InferredRequirementViolationDiagnostic)
    assert all_diags[0].location.line == 21
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert not all_diags[0].required_empty
    assert all_diags[0].action_name == _MID
    assert (
        all_diags[0].position_name
        == "position<box>::action</mid>::position<incoming>::position</file>"
    )
    assert_propagation_chain(
        all_diags[0],
        {
            "kind": action_contract.PropagationKind.QUALITY_ASSIGNED,
            "enclosing_quality_name": "position<my_file>",
            "triggered_quality_name": _DELETE_DESTRUCTOR,
            "line": 15,
            "column": 28,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.PARTICLE_ORIGIN,
            "enclosing_quality_name": "position<box>::action</mid>::position<incoming>",
            "triggered_quality_name": None,
            "line": 19,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _TEST,
            "triggered_quality_name": _MID,
            "line": 21,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.AUTO_DESTRUCTION,
            "enclosing_quality_name": "position<local_box>",
            "triggered_quality_name": _MID,
            "line": 7,
            "column": 9,
            "file_path": "mid.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DESTRUCTOR_CASCADE,
            "enclosing_quality_name": _MID,
            "triggered_quality_name": _DELETE_DESTRUCTOR,
            "line": 7,
            "column": 9,
            "file_path": "mid.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": _DELETE_DESTRUCTOR,
            "triggered_quality_name": None,
            "line": 7,
            "column": 30,
            "file_path": "delete_destructor.dfn",
        },
    )
    assert result.action_call_graph.edges() == [
        (_MID, _DELETE_DESTRUCTOR),
        (_TEST, _MID),
    ]


def test_auto_destruction_contract_requirement_satisfied(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert result.action_call_graph.edges() == [
        (_MID, _DELETE_DESTRUCTOR),
        (_TEST, _MID),
    ]


def test_destroyer_destroys_implied_position_requirement_satisfied(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert result.action_call_graph.edges() == [
        (_CLOSE_FILE, _DELETE_DESTRUCTOR),
        (_TEST, _CLOSE_FILE),
    ]


def test_destroyer_destroys_implied_position_requirement_violated(
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
    assert not all_diags[0].required_empty
    assert all_diags[0].action_name == _CLOSE_FILE
    assert (
        all_diags[0].position_name == "position<box>::position</slot>::position</file>"
    )
    assert_propagation_chain(
        all_diags[0],
        {
            "kind": action_contract.PropagationKind.QUALITY_ASSIGNED,
            "enclosing_quality_name": "position<my_file>",
            "triggered_quality_name": _DELETE_DESTRUCTOR,
            "line": 18,
            "column": 28,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.PARTICLE_ORIGIN,
            "enclosing_quality_name": "position<box>::position</slot>",
            "triggered_quality_name": None,
            "line": 22,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _TEST,
            "triggered_quality_name": _CLOSE_FILE,
            "line": 24,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DESTRUCTOR_CASCADE,
            "enclosing_quality_name": _CLOSE_FILE,
            "triggered_quality_name": _DELETE_DESTRUCTOR,
            "line": 7,
            "column": 33,
            "file_path": "close_file.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": _DELETE_DESTRUCTOR,
            "triggered_quality_name": None,
            "line": 7,
            "column": 30,
            "file_path": "delete_destructor.dfn",
        },
    )
    assert result.action_call_graph.edges() == [
        (_CLOSE_FILE, _DELETE_DESTRUCTOR),
        (_TEST, _CLOSE_FILE),
    ]


def test_destruction_contracts_verified_in_execution_order(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 2
    assert isinstance(all_diags[0], diagnostics.InferredRequirementViolationDiagnostic)
    assert isinstance(all_diags[1], diagnostics.InferredRequirementViolationDiagnostic)
    assert not all_diags[0].required_empty
    assert all_diags[0].action_name == _CLOSE_TWO
    assert (
        all_diags[0].position_name
        == "position<box>::action</close_two>::position<target1>::position</file>"
    )
    assert all_diags[0].location.line == 28
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert_propagation_chain(
        all_diags[0],
        {
            "kind": action_contract.PropagationKind.QUALITY_ASSIGNED,
            "enclosing_quality_name": "position<one>",
            "triggered_quality_name": _DESTRUCTOR,
            "line": 15,
            "column": 28,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.PARTICLE_ORIGIN,
            "enclosing_quality_name": "position<box>::action</close_two>::position<target1>",
            "triggered_quality_name": None,
            "line": 24,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _TEST,
            "triggered_quality_name": _CLOSE_TWO,
            "line": 28,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DESTRUCTOR_CASCADE,
            "enclosing_quality_name": _CLOSE_TWO,
            "triggered_quality_name": _DESTRUCTOR,
            "line": 8,
            "column": 33,
            "file_path": "close_two.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": _DESTRUCTOR,
            "triggered_quality_name": None,
            "line": 7,
            "column": 30,
            "file_path": "destructor.dfn",
        },
    )
    assert not all_diags[1].required_empty
    assert all_diags[1].action_name == _CLOSE_TWO
    assert (
        all_diags[1].position_name
        == "position<box>::action</close_two>::position<target2>::position</file>"
    )
    assert all_diags[1].location.line == 28
    assert all_diags[1].location.column == 30
    assert all_diags[1].location.file_path == PurePosixPath("test.dfn")
    assert_propagation_chain(
        all_diags[1],
        {
            "kind": action_contract.PropagationKind.QUALITY_ASSIGNED,
            "enclosing_quality_name": "position<two>",
            "triggered_quality_name": _DESTRUCTOR,
            "line": 20,
            "column": 28,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.PARTICLE_ORIGIN,
            "enclosing_quality_name": "position<box>::action</close_two>::position<target2>",
            "triggered_quality_name": None,
            "line": 25,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _TEST,
            "triggered_quality_name": _CLOSE_TWO,
            "line": 28,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DESTRUCTOR_CASCADE,
            "enclosing_quality_name": _CLOSE_TWO,
            "triggered_quality_name": _DESTRUCTOR,
            "line": 9,
            "column": 33,
            "file_path": "close_two.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": _DESTRUCTOR,
            "triggered_quality_name": None,
            "line": 7,
            "column": 30,
            "file_path": "destructor.dfn",
        },
    )
    assert result.action_call_graph.edges() == [
        (_CLOSE_TWO, _DESTRUCTOR),
        (_CLOSE_TWO, _DESTRUCTOR),
        (_TEST, _CLOSE_TWO),
    ]


def test_both_destructions_satisfied(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert result.action_call_graph.edges() == [
        (_CLOSE_TWO, _DESTRUCTOR),
        (_CLOSE_TWO, _DESTRUCTOR),
        (_TEST, _CLOSE_TWO),
    ]
