# pyright: reportUnusedCallResult=false

from __future__ import annotations

from pathlib import PurePosixPath
from typing import TYPE_CHECKING

from define.compiler import diagnostics
from define.compiler.validator.reference_graph import action_contract
from define.compiler.validator.reference_graph.reference_graph_validator_tests.test_helpers import (
    assert_propagation_chain,
)
from define.compiler.validator.test_helpers import assert_no_errors

if TYPE_CHECKING:
    from define.compiler.conftest import (
        ValidateTestdataProjectWithReferenceGraph,
    )

_TEST = "action<my.domain.com:my_lib:/test>"
_CLOSE_FILE = "action<my.domain.com:my_lib:/close_file>"
_INNER = "action<my.domain.com:my_lib:/inner>"
_MID = "action<my.domain.com:my_lib:/mid>"
_DESTRUCTOR = "action<my.domain.com:my_lib:/destructor>"
_DELETE_FILE_DESTRUCTOR = "action<my.domain.com:my_lib:/delete_file_destructor>"
_DELETE_DESTRUCTOR = "action<my.domain.com:my_lib:/delete_destructor>"
_PARENT_DESTRUCTOR = "action<my.domain.com:my_lib:/parent_destructor>"
_CHILD_DESTRUCTOR = "action<my.domain.com:my_lib:/child_destructor>"
_D = "action<my.domain.com:my_lib:/d>"
_CALLEE = "action<my.domain.com:my_lib:/callee>"


def test_inner_kept_child_occupied_requirement_satisfied(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert result.action_call_graph.edges() == [
        (_CLOSE_FILE, _DELETE_FILE_DESTRUCTOR),
        (_TEST, _CLOSE_FILE),
    ]


def test_inner_emptied_child_overrides_caller_knowledge_violated(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.InferredRequirementViolationDiagnostic)
    assert all_diags[0].action_name == _CLOSE_FILE
    assert all_diags[0].required_empty is False
    assert all_diags[0].location.line == 23
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert (
        all_diags[0].position_name
        == "position<box>::action</close_file>::position<target>::position</file>"
    )
    assert_propagation_chain(
        all_diags[0],
        {
            "kind": action_contract.PropagationKind.QUALITY_ASSIGNED,
            "enclosing_quality_name": "position<my_file>",
            "triggered_quality_name": _DELETE_FILE_DESTRUCTOR,
            "line": 16,
            "column": 28,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.PARTICLE_ORIGIN,
            "enclosing_quality_name": "position<box>::action</close_file>::position<target>",
            "triggered_quality_name": None,
            "line": 20,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _TEST,
            "triggered_quality_name": _CLOSE_FILE,
            "line": 23,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DESTRUCTOR_CASCADE,
            "enclosing_quality_name": _CLOSE_FILE,
            "triggered_quality_name": _DELETE_FILE_DESTRUCTOR,
            "line": 12,
            "column": 33,
            "file_path": "close_file.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": _DELETE_FILE_DESTRUCTOR,
            "triggered_quality_name": None,
            "line": 7,
            "column": 30,
            "file_path": "delete_file_destructor.dfn",
        },
    )
    assert result.action_call_graph.edges() == [
        (_CLOSE_FILE, _DELETE_FILE_DESTRUCTOR),
        (_TEST, _CLOSE_FILE),
    ]


def test_cascade_fires_child_then_parent_caller_attached_destructors(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert result.action_call_graph.edges() == [
        (_CLOSE_FILE, _CHILD_DESTRUCTOR),
        (_CLOSE_FILE, _PARENT_DESTRUCTOR),
        (_TEST, _CLOSE_FILE),
    ]


def test_cascade_verifies_child_destructor_requirement_violated(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.InferredRequirementViolationDiagnostic)
    assert all_diags[0].action_name == _CLOSE_FILE
    assert all_diags[0].required_empty is False
    assert all_diags[0].location.line == 21
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert (
        all_diags[0].position_name
        == "position<box>::action</close_file>::position<target>::position</child>::position</file>"
    )
    assert_propagation_chain(
        all_diags[0],
        {
            "kind": action_contract.PropagationKind.QUALITY_ASSIGNED,
            "enclosing_quality_name": "position<my.domain.com:my_lib:/child>",
            "triggered_quality_name": _CHILD_DESTRUCTOR,
            "line": 3,
            "column": 20,
            "file_path": "child.dfn",
        },
        {
            "kind": action_contract.PropagationKind.PARTICLE_ORIGIN,
            "enclosing_quality_name": "position<box>::action</close_file>::position<target>::position</child>",
            "triggered_quality_name": None,
            "line": 19,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _TEST,
            "triggered_quality_name": _CLOSE_FILE,
            "line": 21,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DESTRUCTOR_CASCADE,
            "enclosing_quality_name": _CLOSE_FILE,
            "triggered_quality_name": _CHILD_DESTRUCTOR,
            "line": 7,
            "column": 33,
            "file_path": "close_file.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": _CHILD_DESTRUCTOR,
            "triggered_quality_name": None,
            "line": 7,
            "column": 30,
            "file_path": "child_destructor.dfn",
        },
    )
    assert result.action_call_graph.edges() == [
        (_CLOSE_FILE, _CHILD_DESTRUCTOR),
        (_TEST, _CLOSE_FILE),
    ]


def test_contract_re_records_through_unknowing_middle_and_top_verifies(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert result.action_call_graph.edges() == [
        (_MID, _CLOSE_FILE),
        (_CLOSE_FILE, _DESTRUCTOR),
        (_TEST, _MID),
    ]


def test_contract_re_records_through_unknowing_middle_and_top_violates(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.InferredRequirementViolationDiagnostic)
    assert all_diags[0].action_name == _MID
    assert all_diags[0].required_empty is False
    assert all_diags[0].location.line == 20
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert (
        all_diags[0].position_name
        == "position<outer_box>::action</mid>::position<incoming>::position</file>"
    )
    assert_propagation_chain(
        all_diags[0],
        {
            "kind": action_contract.PropagationKind.QUALITY_ASSIGNED,
            "enclosing_quality_name": "position<my_file>",
            "triggered_quality_name": _DESTRUCTOR,
            "line": 14,
            "column": 28,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.PARTICLE_ORIGIN,
            "enclosing_quality_name": "position<outer_box>::action</mid>::position<incoming>",
            "triggered_quality_name": None,
            "line": 18,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _TEST,
            "triggered_quality_name": _MID,
            "line": 20,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _MID,
            "triggered_quality_name": _CLOSE_FILE,
            "line": 14,
            "column": 30,
            "file_path": "mid.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DESTRUCTOR_CASCADE,
            "enclosing_quality_name": _CLOSE_FILE,
            "triggered_quality_name": _DESTRUCTOR,
            "line": 7,
            "column": 33,
            "file_path": "close_file.dfn",
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
        (_MID, _CLOSE_FILE),
        (_CLOSE_FILE, _DESTRUCTOR),
        (_TEST, _MID),
    ]


def test_constructor_attaches_destructor_and_verifies_via_contract(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.InferredRequirementViolationDiagnostic)
    assert all_diags[0].action_name == _CLOSE_FILE
    assert all_diags[0].required_empty is False
    assert all_diags[0].location.line == 16
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert (
        all_diags[0].position_name
        == "position<box>::action</close_file>::position<target>::position</file>"
    )
    assert_propagation_chain(
        all_diags[0],
        {
            "kind": action_contract.PropagationKind.QUALITY_ASSIGNED,
            "enclosing_quality_name": "position<my.domain.com:my_lib:/carrier>",
            "triggered_quality_name": _DELETE_DESTRUCTOR,
            "line": 4,
            "column": 20,
            "file_path": "carrier.dfn",
        },
        {
            "kind": action_contract.PropagationKind.PARTICLE_ORIGIN,
            "enclosing_quality_name": "position<box>::action</close_file>::position<target>",
            "triggered_quality_name": None,
            "line": 14,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _TEST,
            "triggered_quality_name": _CLOSE_FILE,
            "line": 16,
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


def test_constructor_attached_destructor_requirement_satisfied(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert result.action_call_graph.edges() == [
        (_CLOSE_FILE, _DELETE_DESTRUCTOR),
        (_TEST, _CLOSE_FILE),
    ]


def test_constructor_resolves_implied_action_destruction_contract(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.InferredRequirementViolationDiagnostic)
    assert all_diags[0].action_name == _CALLEE
    assert all_diags[0].required_empty is False
    assert all_diags[0].location.line == 13
    assert all_diags[0].location.column == 47
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert (
        all_diags[0].position_name
        == "action</callee>::position<incoming>::position</item>"
    )
    assert_propagation_chain(
        all_diags[0],
        {
            "kind": action_contract.PropagationKind.QUALITY_ASSIGNED,
            "enclosing_quality_name": "position<box>",
            "triggered_quality_name": _D,
            "line": 9,
            "column": 28,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.PARTICLE_ORIGIN,
            "enclosing_quality_name": "action</callee>::position<incoming>",
            "triggered_quality_name": None,
            "line": 12,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _TEST,
            "triggered_quality_name": _CALLEE,
            "line": 13,
            "column": 47,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DESTRUCTOR_CASCADE,
            "enclosing_quality_name": _CALLEE,
            "triggered_quality_name": _D,
            "line": 6,
            "column": 33,
            "file_path": "callee.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": _D,
            "triggered_quality_name": None,
            "line": 7,
            "column": 30,
            "file_path": "d.dfn",
        },
    )
    assert result.action_call_graph.edges() == [
        (_CALLEE, _D),
        (_TEST, _CALLEE),
    ]


def test_middle_knows_destructor_but_not_child_state_defers_to_owner_satisfied(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert result.action_call_graph.edges() == [
        (_MID, _CLOSE_FILE),
        (_CLOSE_FILE, _DESTRUCTOR),
        (_TEST, _MID),
    ]


def test_middle_knows_destructor_but_not_child_state_defers_to_owner_violated(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.InferredRequirementViolationDiagnostic)
    assert all_diags[0].action_name == _MID
    assert all_diags[0].required_empty is False
    assert all_diags[0].location.line == 23
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert (
        all_diags[0].position_name
        == "position<outer_box>::action</mid>::position<incoming>::position</file>"
    )
    assert_propagation_chain(
        all_diags[0],
        {
            "kind": action_contract.PropagationKind.QUALITY_ASSIGNED,
            "enclosing_quality_name": "position<my_file>",
            "triggered_quality_name": _DESTRUCTOR,
            "line": 17,
            "column": 28,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.PARTICLE_ORIGIN,
            "enclosing_quality_name": "position<outer_box>::action</mid>::position<incoming>",
            "triggered_quality_name": None,
            "line": 21,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _TEST,
            "triggered_quality_name": _MID,
            "line": 23,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _MID,
            "triggered_quality_name": _CLOSE_FILE,
            "line": 18,
            "column": 30,
            "file_path": "mid.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DESTRUCTOR_CASCADE,
            "enclosing_quality_name": _CLOSE_FILE,
            "triggered_quality_name": _DESTRUCTOR,
            "line": 7,
            "column": 33,
            "file_path": "close_file.dfn",
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
        (_MID, _CLOSE_FILE),
        (_CLOSE_FILE, _DESTRUCTOR),
        (_TEST, _MID),
    ]


def test_required_position_error_in_child_state_skips_verification(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.MoveFromEmptyPositionDiagnostic)
    assert all_diags[0].location.line == 12
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("close_file.dfn")
    assert all_diags[0].position_name == "position<spare>"
    assert all_diags[0].is_action_interface_position is False
    assert all_diags[0].inferred_at is None
    assert result.action_call_graph.edges() == [
        (_CLOSE_FILE, _DELETE_FILE_DESTRUCTOR),
        (_TEST, _CLOSE_FILE),
    ]


def test_auto_destruction_re_records_through_middle_and_owner_verifies(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.InferredRequirementViolationDiagnostic)
    assert all_diags[0].action_name == _MID
    assert all_diags[0].required_empty is False
    assert all_diags[0].location.line == 22
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert (
        all_diags[0].position_name
        == "position<outer_box>::action</mid>::position<incoming>::position</file>"
    )
    assert_propagation_chain(
        all_diags[0],
        {
            "kind": action_contract.PropagationKind.QUALITY_ASSIGNED,
            "enclosing_quality_name": "position<my_file>",
            "triggered_quality_name": _DELETE_DESTRUCTOR,
            "line": 16,
            "column": 28,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.PARTICLE_ORIGIN,
            "enclosing_quality_name": "position<outer_box>::action</mid>::position<incoming>",
            "triggered_quality_name": None,
            "line": 20,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _TEST,
            "triggered_quality_name": _MID,
            "line": 22,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _MID,
            "triggered_quality_name": _INNER,
            "line": 14,
            "column": 30,
            "file_path": "mid.dfn",
        },
        {
            "kind": action_contract.PropagationKind.AUTO_DESTRUCTION,
            "enclosing_quality_name": "position<local_box>",
            "triggered_quality_name": _INNER,
            "line": 7,
            "column": 9,
            "file_path": "inner.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DESTRUCTOR_CASCADE,
            "enclosing_quality_name": _INNER,
            "triggered_quality_name": _DELETE_DESTRUCTOR,
            "line": 7,
            "column": 9,
            "file_path": "inner.dfn",
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
        (_MID, _INNER),
        (_INNER, _DELETE_DESTRUCTOR),
        (_TEST, _MID),
    ]


def test_cascade_re_records_through_middle_and_owner_verifies_child_then_parent(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 2
    assert isinstance(all_diags[0], diagnostics.InferredRequirementViolationDiagnostic)
    assert all_diags[0].action_name == _MID
    assert all_diags[0].required_empty is False
    assert all_diags[0].location.line == 23
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert (
        all_diags[0].position_name
        == "position<outer_box>::action</mid>::position<incoming>::position</child>::position</cfile>"
    )
    assert_propagation_chain(
        all_diags[0],
        {
            "kind": action_contract.PropagationKind.QUALITY_ASSIGNED,
            "enclosing_quality_name": "position<my.domain.com:my_lib:/child>",
            "triggered_quality_name": _CHILD_DESTRUCTOR,
            "line": 3,
            "column": 20,
            "file_path": "child.dfn",
        },
        {
            "kind": action_contract.PropagationKind.PARTICLE_ORIGIN,
            "enclosing_quality_name": "position<outer_box>::action</mid>::position<incoming>::position</child>",
            "triggered_quality_name": None,
            "line": 21,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _TEST,
            "triggered_quality_name": _MID,
            "line": 23,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _MID,
            "triggered_quality_name": _CLOSE_FILE,
            "line": 14,
            "column": 30,
            "file_path": "mid.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DESTRUCTOR_CASCADE,
            "enclosing_quality_name": _CLOSE_FILE,
            "triggered_quality_name": _CHILD_DESTRUCTOR,
            "line": 7,
            "column": 33,
            "file_path": "close_file.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": _CHILD_DESTRUCTOR,
            "triggered_quality_name": None,
            "line": 7,
            "column": 30,
            "file_path": "child_destructor.dfn",
        },
    )
    assert isinstance(all_diags[1], diagnostics.InferredRequirementViolationDiagnostic)
    assert all_diags[1].action_name == _MID
    assert all_diags[1].required_empty is False
    assert all_diags[1].location.line == 23
    assert all_diags[1].location.column == 30
    assert all_diags[1].location.file_path == PurePosixPath("test.dfn")
    assert (
        all_diags[1].position_name
        == "position<outer_box>::action</mid>::position<incoming>::position</pfile>"
    )
    assert_propagation_chain(
        all_diags[1],
        {
            "kind": action_contract.PropagationKind.QUALITY_ASSIGNED,
            "enclosing_quality_name": "position<my_file>",
            "triggered_quality_name": _PARENT_DESTRUCTOR,
            "line": 15,
            "column": 28,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.PARTICLE_ORIGIN,
            "enclosing_quality_name": "position<outer_box>::action</mid>::position<incoming>",
            "triggered_quality_name": None,
            "line": 20,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _TEST,
            "triggered_quality_name": _MID,
            "line": 23,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _MID,
            "triggered_quality_name": _CLOSE_FILE,
            "line": 14,
            "column": 30,
            "file_path": "mid.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DESTRUCTOR_CASCADE,
            "enclosing_quality_name": _CLOSE_FILE,
            "triggered_quality_name": _PARENT_DESTRUCTOR,
            "line": 7,
            "column": 33,
            "file_path": "close_file.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": _PARENT_DESTRUCTOR,
            "triggered_quality_name": None,
            "line": 7,
            "column": 30,
            "file_path": "parent_destructor.dfn",
        },
    )
    assert result.action_call_graph.edges() == [
        (_MID, _CLOSE_FILE),
        (_CLOSE_FILE, _CHILD_DESTRUCTOR),
        (_CLOSE_FILE, _PARENT_DESTRUCTOR),
        (_TEST, _MID),
    ]


def test_emptied_child_not_re_destroyed_by_parent_cascade(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.InferredRequirementViolationDiagnostic)
    assert all_diags[0].action_name == _CLOSE_FILE
    assert all_diags[0].required_empty is False
    assert all_diags[0].location.line == 24
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert (
        all_diags[0].position_name
        == "position<box>::action</close_file>::position<target>::position</c>::position</file>"
    )
    assert_propagation_chain(
        all_diags[0],
        {
            "kind": action_contract.PropagationKind.QUALITY_ASSIGNED,
            "enclosing_quality_name": "position<staging>",
            "triggered_quality_name": _D,
            "line": 17,
            "column": 28,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.PARTICLE_ORIGIN,
            "enclosing_quality_name": "position<box>::action</close_file>::position<target>::position</c>",
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
            "triggered_quality_name": _D,
            "line": 11,
            "column": 33,
            "file_path": "close_file.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": _D,
            "triggered_quality_name": None,
            "line": 7,
            "column": 30,
            "file_path": "d.dfn",
        },
    )
    assert result.action_call_graph.edges() == [
        (_CLOSE_FILE, _D),
        (_TEST, _CLOSE_FILE),
    ]
