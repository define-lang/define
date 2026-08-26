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
_MID = "action<my.domain.com:my_lib:/mid>"
_OUTER = "action<my.domain.com:my_lib:/outer>"
_MIDDLE = "action<my.domain.com:my_lib:/middle>"
_INNER = "action<my.domain.com:my_lib:/inner>"
_CLOSE_FILE = "action<my.domain.com:my_lib:/close_file>"
_DESTRUCTOR = "action<my.domain.com:my_lib:/destructor>"
_DELETE_FILE_DESTRUCTOR = "action<my.domain.com:my_lib:/delete_file_destructor>"
_CARRIER = "action<my.domain.com:my_lib:/carrier>"
_D1 = "action<my.domain.com:my_lib:/d1>"
_D2 = "action<my.domain.com:my_lib:/d2>"


def test_destructor_diagnostic_retains_callee_local_assignment(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.InferredRequirementViolationDiagnostic)
    assert_propagation_chain(
        all_diags[0],
        {
            "kind": action_contract.PropagationKind.QUALITY_ASSIGNED,
            "enclosing_quality_name": "position<created>",
            "triggered_quality_name": _DESTRUCTOR,
            "line": 13,
            "column": 28,
            "file_path": "producer.dfn",
        },
        {
            "kind": action_contract.PropagationKind.PARTICLE_ORIGIN,
            "enclosing_quality_name": "position<box>::action</producer>::position<result>",
            "triggered_quality_name": None,
            "line": 16,
            "column": 30,
            "file_path": "producer.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DESTRUCTOR_CASCADE,
            "enclosing_quality_name": _TEST,
            "triggered_quality_name": _DESTRUCTOR,
            "line": 14,
            "column": 33,
            "file_path": "test.dfn",
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


def test_intermediate_verifies_destructor_it_can_resolve(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.InferredRequirementViolationDiagnostic)
    assert all_diags[0].location.line == 19
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("mid.dfn")
    assert all_diags[0].action_name == _CLOSE_FILE
    assert all_diags[0].required_empty is True
    assert (
        all_diags[0].position_name
        == "position<box>::action</close_file>::position<target>::action</destructor>::position<item>"
    )
    assert_propagation_chain(
        all_diags[0],
        {
            "kind": action_contract.PropagationKind.QUALITY_ASSIGNED,
            "enclosing_quality_name": "position<incoming>",
            "triggered_quality_name": _DESTRUCTOR,
            "line": 4,
            "column": 24,
            "file_path": "mid.dfn",
        },
        {
            "kind": action_contract.PropagationKind.PARTICLE_ORIGIN,
            "enclosing_quality_name": "position<box>::action</close_file>::position<target>",
            "triggered_quality_name": None,
            "line": 17,
            "column": 30,
            "file_path": "mid.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _MID,
            "triggered_quality_name": _CLOSE_FILE,
            "line": 19,
            "column": 30,
            "file_path": "mid.dfn",
        },
        {
            "kind": action_contract.PropagationKind.FILL_SITE,
            "enclosing_quality_name": "position<box>::action</close_file>::position<target>::action</destructor>::position<item>",
            "triggered_quality_name": None,
            "line": 17,
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
            "line": 6,
            "column": 30,
            "file_path": "destructor.dfn",
        },
    )
    assert result.action_call_graph.edges() == [
        (_CLOSE_FILE, _DESTRUCTOR),
        (_MID, _CLOSE_FILE),
        (_TEST, _MID),
    ]


def test_intermediate_resolves_satisfied_owner_does_not_re_report(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert result.action_call_graph.edges() == [
        (_CLOSE_FILE, _DESTRUCTOR),
        (_MID, _CLOSE_FILE),
        (_TEST, _MID),
    ]


def test_intermediate_resolves_one_destructor_and_carries_another(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 2
    assert isinstance(all_diags[0], diagnostics.InferredRequirementViolationDiagnostic)
    assert all_diags[0].location.line == 24
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].action_name == _MID
    assert all_diags[0].required_empty is True
    assert (
        all_diags[0].position_name
        == "position<outer_box>::action</mid>::position<incoming>::action</d2>::position<item2>"
    )
    assert_propagation_chain(
        all_diags[0],
        {
            "kind": action_contract.PropagationKind.QUALITY_ASSIGNED,
            "enclosing_quality_name": "position<my_file>",
            "triggered_quality_name": _D2,
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
            "line": 24,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.FILL_SITE,
            "enclosing_quality_name": "position<outer_box>::action</mid>::position<incoming>::action</d2>::position<item2>",
            "triggered_quality_name": None,
            "line": 22,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _MID,
            "triggered_quality_name": _CLOSE_FILE,
            "line": 20,
            "column": 30,
            "file_path": "mid.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DESTRUCTOR_CASCADE,
            "enclosing_quality_name": _CLOSE_FILE,
            "triggered_quality_name": _D2,
            "line": 7,
            "column": 33,
            "file_path": "close_file.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": _D2,
            "triggered_quality_name": None,
            "line": 6,
            "column": 30,
            "file_path": "d2.dfn",
        },
    )
    assert isinstance(all_diags[1], diagnostics.InferredRequirementViolationDiagnostic)
    assert all_diags[1].location.line == 20
    assert all_diags[1].location.column == 30
    assert all_diags[1].location.file_path == PurePosixPath("mid.dfn")
    assert all_diags[1].action_name == _CLOSE_FILE
    assert all_diags[1].required_empty is True
    assert (
        all_diags[1].position_name
        == "position<box>::action</close_file>::position<target>::action</d1>::position<item1>"
    )
    assert_propagation_chain(
        all_diags[1],
        {
            "kind": action_contract.PropagationKind.QUALITY_ASSIGNED,
            "enclosing_quality_name": "position<incoming>",
            "triggered_quality_name": _D1,
            "line": 4,
            "column": 24,
            "file_path": "mid.dfn",
        },
        {
            "kind": action_contract.PropagationKind.PARTICLE_ORIGIN,
            "enclosing_quality_name": "position<box>::action</close_file>::position<target>",
            "triggered_quality_name": None,
            "line": 18,
            "column": 30,
            "file_path": "mid.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _MID,
            "triggered_quality_name": _CLOSE_FILE,
            "line": 20,
            "column": 30,
            "file_path": "mid.dfn",
        },
        {
            "kind": action_contract.PropagationKind.FILL_SITE,
            "enclosing_quality_name": "position<box>::action</close_file>::position<target>::action</d1>::position<item1>",
            "triggered_quality_name": None,
            "line": 18,
            "column": 30,
            "file_path": "mid.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DESTRUCTOR_CASCADE,
            "enclosing_quality_name": _CLOSE_FILE,
            "triggered_quality_name": _D1,
            "line": 7,
            "column": 33,
            "file_path": "close_file.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": _D1,
            "triggered_quality_name": None,
            "line": 6,
            "column": 30,
            "file_path": "d1.dfn",
        },
    )
    assert result.action_call_graph.edges() == [
        (_CLOSE_FILE, _D1),
        (_CLOSE_FILE, _D2),
        (_MID, _CLOSE_FILE),
        (_TEST, _MID),
    ]


def test_five_level_implied_requirements_resolved_across_actions_satisfied(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert result.action_call_graph.edges() == [
        (_MIDDLE, _CLOSE_FILE),
        (_CLOSE_FILE, _DESTRUCTOR),
        (_OUTER, _MIDDLE),
        (_TEST, _OUTER),
    ]


def test_five_level_implied_requirements_resolved_across_actions_violated(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 2
    assert isinstance(all_diags[0], diagnostics.InferredRequirementViolationDiagnostic)
    assert all_diags[0].location.line == 21
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("outer.dfn")
    assert all_diags[0].action_name == _MIDDLE
    assert all_diags[0].required_empty is False
    assert (
        all_diags[0].position_name
        == "position<box>::action</middle>::position<incoming>::position</p1>"
    )
    assert_propagation_chain(
        all_diags[0],
        {
            "kind": action_contract.PropagationKind.QUALITY_ASSIGNED,
            "enclosing_quality_name": "position<incoming>",
            "triggered_quality_name": _DESTRUCTOR,
            "line": 4,
            "column": 24,
            "file_path": "outer.dfn",
        },
        {
            "kind": action_contract.PropagationKind.PARTICLE_ORIGIN,
            "enclosing_quality_name": "position<box>::action</middle>::position<incoming>",
            "triggered_quality_name": None,
            "line": 18,
            "column": 30,
            "file_path": "outer.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _OUTER,
            "triggered_quality_name": _MIDDLE,
            "line": 21,
            "column": 30,
            "file_path": "outer.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _MIDDLE,
            "triggered_quality_name": _CLOSE_FILE,
            "line": 20,
            "column": 30,
            "file_path": "middle.dfn",
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
            "line": 8,
            "column": 30,
            "file_path": "destructor.dfn",
        },
    )
    assert isinstance(all_diags[1], diagnostics.InferredRequirementViolationDiagnostic)
    assert all_diags[1].location.line == 21
    assert all_diags[1].location.column == 30
    assert all_diags[1].location.file_path == PurePosixPath("outer.dfn")
    assert all_diags[1].action_name == _MIDDLE
    assert all_diags[1].required_empty is True
    assert (
        all_diags[1].position_name
        == "position<box>::action</middle>::position<incoming>::position</p2>"
    )
    assert_propagation_chain(
        all_diags[1],
        {
            "kind": action_contract.PropagationKind.QUALITY_ASSIGNED,
            "enclosing_quality_name": "position<incoming>",
            "triggered_quality_name": _DESTRUCTOR,
            "line": 4,
            "column": 24,
            "file_path": "outer.dfn",
        },
        {
            "kind": action_contract.PropagationKind.PARTICLE_ORIGIN,
            "enclosing_quality_name": "position<box>::action</middle>::position<incoming>",
            "triggered_quality_name": None,
            "line": 18,
            "column": 30,
            "file_path": "outer.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _OUTER,
            "triggered_quality_name": _MIDDLE,
            "line": 21,
            "column": 30,
            "file_path": "outer.dfn",
        },
        {
            "kind": action_contract.PropagationKind.FILL_SITE,
            "enclosing_quality_name": "position<box>::action</middle>::position<incoming>::position</p2>",
            "triggered_quality_name": None,
            "line": 18,
            "column": 30,
            "file_path": "middle.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _MIDDLE,
            "triggered_quality_name": _CLOSE_FILE,
            "line": 20,
            "column": 30,
            "file_path": "middle.dfn",
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
            "line": 10,
            "column": 30,
            "file_path": "destructor.dfn",
        },
    )
    assert result.action_call_graph.edges() == [
        (_MIDDLE, _CLOSE_FILE),
        (_CLOSE_FILE, _DESTRUCTOR),
        (_OUTER, _MIDDLE),
        (_TEST, _OUTER),
    ]


def test_six_level_destructor_knower_separate_from_resolvers_satisfied(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert result.action_call_graph.edges() == [
        (_INNER, _CLOSE_FILE),
        (_CLOSE_FILE, _DESTRUCTOR),
        (_MIDDLE, _INNER),
        (_OUTER, _MIDDLE),
        (_TEST, _OUTER),
    ]


def test_six_level_destructor_knower_separate_from_resolvers_violated(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 2
    assert isinstance(all_diags[0], diagnostics.InferredRequirementViolationDiagnostic)
    assert all_diags[0].location.line == 18
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("outer.dfn")
    assert all_diags[0].action_name == _MIDDLE
    assert all_diags[0].required_empty is False
    assert (
        all_diags[0].position_name
        == "position<box>::action</middle>::position<incoming>::position</p1>"
    )
    assert_propagation_chain(
        all_diags[0],
        {
            "kind": action_contract.PropagationKind.QUALITY_ASSIGNED,
            "enclosing_quality_name": "position<incoming>",
            "triggered_quality_name": _DESTRUCTOR,
            "line": 4,
            "column": 24,
            "file_path": "outer.dfn",
        },
        {
            "kind": action_contract.PropagationKind.PARTICLE_ORIGIN,
            "enclosing_quality_name": "position<box>::action</middle>::position<incoming>",
            "triggered_quality_name": None,
            "line": 17,
            "column": 30,
            "file_path": "outer.dfn",
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
            "line": 21,
            "column": 30,
            "file_path": "middle.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _INNER,
            "triggered_quality_name": _CLOSE_FILE,
            "line": 19,
            "column": 30,
            "file_path": "inner.dfn",
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
            "line": 8,
            "column": 30,
            "file_path": "destructor.dfn",
        },
    )
    assert isinstance(all_diags[1], diagnostics.InferredRequirementViolationDiagnostic)
    assert all_diags[1].location.line == 18
    assert all_diags[1].location.column == 30
    assert all_diags[1].location.file_path == PurePosixPath("outer.dfn")
    assert all_diags[1].action_name == _MIDDLE
    assert all_diags[1].required_empty is True
    assert (
        all_diags[1].position_name
        == "position<box>::action</middle>::position<incoming>::position</p2>"
    )
    assert_propagation_chain(
        all_diags[1],
        {
            "kind": action_contract.PropagationKind.QUALITY_ASSIGNED,
            "enclosing_quality_name": "position<incoming>",
            "triggered_quality_name": _DESTRUCTOR,
            "line": 4,
            "column": 24,
            "file_path": "outer.dfn",
        },
        {
            "kind": action_contract.PropagationKind.PARTICLE_ORIGIN,
            "enclosing_quality_name": "position<box>::action</middle>::position<incoming>",
            "triggered_quality_name": None,
            "line": 17,
            "column": 30,
            "file_path": "outer.dfn",
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
            "kind": action_contract.PropagationKind.FILL_SITE,
            "enclosing_quality_name": "position<box>::action</middle>::position<incoming>::position</p2>",
            "triggered_quality_name": None,
            "line": 17,
            "column": 30,
            "file_path": "inner.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _MIDDLE,
            "triggered_quality_name": _INNER,
            "line": 21,
            "column": 30,
            "file_path": "middle.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _INNER,
            "triggered_quality_name": _CLOSE_FILE,
            "line": 19,
            "column": 30,
            "file_path": "inner.dfn",
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
            "line": 10,
            "column": 30,
            "file_path": "destructor.dfn",
        },
    )
    assert result.action_call_graph.edges() == [
        (_INNER, _CLOSE_FILE),
        (_CLOSE_FILE, _DESTRUCTOR),
        (_MIDDLE, _INNER),
        (_OUTER, _MIDDLE),
        (_TEST, _OUTER),
    ]


def test_owner_with_error_required_position_skips_destructor_check(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 2
    assert isinstance(all_diags[0], diagnostics.MoveFromEmptyPositionDiagnostic)
    assert all_diags[0].location.line == 26
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert (
        all_diags[0].position_name
        == "position<box>::action</close_file>::position<target>::position</x>"
    )
    assert all_diags[0].is_action_interface_position is True
    assert all_diags[0].inferred_at is None
    assert isinstance(all_diags[1], diagnostics.DeadChildPositionDiagnostic)
    assert all_diags[1].location.line == 4
    assert all_diags[1].location.column == 24
    assert all_diags[1].location.file_path == PurePosixPath("close_file.dfn")
    assert all_diags[1].constraint_name == "position</x>"
    assert all_diags[1].position_name == "position<target>"
    assert result.action_call_graph.edges() == [
        (_CLOSE_FILE, _DESTRUCTOR),
        (_TEST, _CLOSE_FILE),
    ]
