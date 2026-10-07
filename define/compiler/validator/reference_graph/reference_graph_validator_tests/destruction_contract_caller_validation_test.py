# pyright: reportUnusedCallResult=false

from __future__ import annotations

from pathlib import PurePosixPath
from typing import TYPE_CHECKING

from define.compiler.errors import diagnostics
from define.compiler.validator.reference_graph import action_contract
from define.compiler.validator.reference_graph.reference_graph_validator_tests.test_helpers import (
    assert_propagation_chain,
)
from define.compiler.validator.reference_graph.test_helpers import action_graph
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
_D = "action<my.domain.com:my_lib:/d>"
_KEEP = "action<my.domain.com:my_lib:/keep>"


def test_parent_validation_does_not_skip_child_destructor(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.InferredRequirementViolationDiagnostic)
    assert all_diags[0].location.line == 17
    assert all_diags[0].location.column == 50
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert (
        all_diags[0].position_name
        == "action</destroyer>::position<run>::position</child>::position</item>"
    )
    assert all_diags[0].action_name == "action<my.domain.com:my_lib:/destroyer>"
    assert all_diags[0].required_empty is False
    assert all_diags[0].required_value is False
    assert_propagation_chain(
        all_diags[0],
        {
            "kind": action_contract.PropagationKind.QUALITY_ASSIGNED,
            "enclosing_quality_name": "position<my.domain.com:my_lib:/child>",
            "triggered_quality_name": "action<my.domain.com:my_lib:/destructor>",
            "line": 3,
            "column": 20,
            "file_path": "child.dfn",
        },
        {
            "kind": action_contract.PropagationKind.PARTICLE_ORIGIN,
            "enclosing_quality_name": "action</destroyer>::position<run>::position</child>",
            "triggered_quality_name": None,
            "line": 15,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/test>",
            "triggered_quality_name": "action<my.domain.com:my_lib:/destroyer>",
            "line": 17,
            "column": 50,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DESTRUCTOR_CASCADE,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/destroyer>",
            "triggered_quality_name": "action<my.domain.com:my_lib:/destructor>",
            "line": 10,
            "column": 33,
            "file_path": "destroyer.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/destructor>",
            "triggered_quality_name": None,
            "line": 7,
            "column": 30,
            "file_path": "destructor.dfn",
        },
    )


def test_propagated_child_validation_does_not_skip_parent_destructor(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.InferredRequirementViolationDiagnostic)
    assert all_diags[0].location.line == 15
    assert all_diags[0].location.column == 50
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert (
        all_diags[0].position_name == "action</middle>::position<run>::position</item>"
    )
    assert all_diags[0].action_name == "action<my.domain.com:my_lib:/middle>"
    assert all_diags[0].required_empty is False
    assert all_diags[0].required_value is False
    assert_propagation_chain(
        all_diags[0],
        {
            "kind": action_contract.PropagationKind.QUALITY_ASSIGNED,
            "enclosing_quality_name": "position<source>",
            "triggered_quality_name": "action<my.domain.com:my_lib:/destructor>",
            "line": 9,
            "column": 28,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.PARTICLE_ORIGIN,
            "enclosing_quality_name": "action</middle>::position<run>",
            "triggered_quality_name": None,
            "line": 14,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/test>",
            "triggered_quality_name": "action<my.domain.com:my_lib:/middle>",
            "line": 15,
            "column": 50,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/middle>",
            "triggered_quality_name": "action<my.domain.com:my_lib:/destroyer>",
            "line": 16,
            "column": 47,
            "file_path": "middle.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DESTRUCTOR_CASCADE,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/destroyer>",
            "triggered_quality_name": "action<my.domain.com:my_lib:/destructor>",
            "line": 6,
            "column": 33,
            "file_path": "destroyer.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/destructor>",
            "triggered_quality_name": None,
            "line": 7,
            "column": 30,
            "file_path": "destructor.dfn",
        },
    )


def test_destructor_diagnostic_retains_callee_local_assignment(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.InferredRequirementViolationDiagnostic)
    assert all_diags[0].required_value is False
    assert all_diags[0].location.line == 13
    assert all_diags[0].location.column == 33
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert (
        all_diags[0].position_name
        == "position<box>::action</producer>::position<result>::action</destructor>::position<item>"
    )
    assert all_diags[0].required_empty is False
    assert all_diags[0].action_name == "action<my.domain.com:my_lib:/destructor>"
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
            "line": 13,
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


def test_knower_resolves_one_destructor_and_requires_state_for_another_from_its_caller(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 2
    assert isinstance(all_diags[0], diagnostics.InferredRequirementViolationDiagnostic)
    assert all_diags[0].location.line == 22
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert (
        all_diags[0].position_name
        == "position<outer_box>::action</mid>::position<incoming>::position</item2>"
    )
    assert all_diags[0].action_name == "action<my.domain.com:my_lib:/mid>"
    assert all_diags[0].required_empty is False
    assert all_diags[0].required_value is False
    assert_propagation_chain(
        all_diags[0],
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/test>",
            "triggered_quality_name": "action<my.domain.com:my_lib:/mid>",
            "line": 22,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.QUALITY_ASSIGNED,
            "enclosing_quality_name": "position<incoming>",
            "triggered_quality_name": "action<my.domain.com:my_lib:/d2>",
            "line": 5,
            "column": 24,
            "file_path": "mid.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/mid>",
            "triggered_quality_name": "action<my.domain.com:my_lib:/close_file>",
            "line": 22,
            "column": 30,
            "file_path": "mid.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DESTRUCTOR_CASCADE,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/close_file>",
            "triggered_quality_name": "action<my.domain.com:my_lib:/d2>",
            "line": 7,
            "column": 33,
            "file_path": "close_file.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/d2>",
            "triggered_quality_name": None,
            "line": 7,
            "column": 30,
            "file_path": "d2.dfn",
        },
    )
    assert isinstance(all_diags[1], diagnostics.InferredRequirementViolationDiagnostic)
    assert all_diags[1].location.line == 22
    assert all_diags[1].location.column == 30
    assert all_diags[1].location.file_path == PurePosixPath("mid.dfn")
    assert (
        all_diags[1].position_name
        == "position<box>::action</close_file>::position<target>::position</item1>"
    )
    assert all_diags[1].action_name == "action<my.domain.com:my_lib:/close_file>"
    assert all_diags[1].required_empty is False
    assert all_diags[1].required_value is False
    assert_propagation_chain(
        all_diags[1],
        {
            "kind": action_contract.PropagationKind.QUALITY_ASSIGNED,
            "enclosing_quality_name": "position<incoming>",
            "triggered_quality_name": "action<my.domain.com:my_lib:/d1>",
            "line": 4,
            "column": 24,
            "file_path": "mid.dfn",
        },
        {
            "kind": action_contract.PropagationKind.PARTICLE_ORIGIN,
            "enclosing_quality_name": "position<box>::action</close_file>::position<target>",
            "triggered_quality_name": None,
            "line": 19,
            "column": 30,
            "file_path": "mid.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/mid>",
            "triggered_quality_name": "action<my.domain.com:my_lib:/close_file>",
            "line": 22,
            "column": 30,
            "file_path": "mid.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DESTRUCTOR_CASCADE,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/close_file>",
            "triggered_quality_name": "action<my.domain.com:my_lib:/d1>",
            "line": 7,
            "column": 33,
            "file_path": "close_file.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/d1>",
            "triggered_quality_name": None,
            "line": 7,
            "column": 30,
            "file_path": "d1.dfn",
        },
    )
    assert action_graph(result.reference_graph_result) == [
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
    assert action_graph(result.reference_graph_result) == [
        (_CLOSE_FILE, _DESTRUCTOR),
        (_MIDDLE, _CLOSE_FILE),
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
    assert (
        all_diags[0].position_name
        == "position<box>::action</middle>::position<incoming>::position</p1>"
    )
    assert all_diags[0].action_name == "action<my.domain.com:my_lib:/middle>"
    assert all_diags[0].required_empty is False
    assert all_diags[0].required_value is False
    assert_propagation_chain(
        all_diags[0],
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/outer>",
            "triggered_quality_name": "action<my.domain.com:my_lib:/middle>",
            "line": 21,
            "column": 30,
            "file_path": "outer.dfn",
        },
        {
            "kind": action_contract.PropagationKind.QUALITY_ASSIGNED,
            "enclosing_quality_name": "position<incoming>",
            "triggered_quality_name": "action<my.domain.com:my_lib:/destructor>",
            "line": 4,
            "column": 24,
            "file_path": "middle.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/middle>",
            "triggered_quality_name": "action<my.domain.com:my_lib:/close_file>",
            "line": 21,
            "column": 30,
            "file_path": "middle.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DESTRUCTOR_CASCADE,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/close_file>",
            "triggered_quality_name": "action<my.domain.com:my_lib:/destructor>",
            "line": 7,
            "column": 33,
            "file_path": "close_file.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/destructor>",
            "triggered_quality_name": None,
            "line": 8,
            "column": 30,
            "file_path": "destructor.dfn",
        },
    )
    assert isinstance(all_diags[1], diagnostics.InferredRequirementViolationDiagnostic)
    assert all_diags[1].location.line == 21
    assert all_diags[1].location.column == 30
    assert all_diags[1].location.file_path == PurePosixPath("middle.dfn")
    assert (
        all_diags[1].position_name
        == "position<box>::action</close_file>::position<target>::position</p2>"
    )
    assert all_diags[1].action_name == "action<my.domain.com:my_lib:/close_file>"
    assert all_diags[1].required_empty is False
    assert all_diags[1].required_value is False
    assert_propagation_chain(
        all_diags[1],
        {
            "kind": action_contract.PropagationKind.QUALITY_ASSIGNED,
            "enclosing_quality_name": "position<incoming>",
            "triggered_quality_name": "action<my.domain.com:my_lib:/destructor>",
            "line": 4,
            "column": 24,
            "file_path": "middle.dfn",
        },
        {
            "kind": action_contract.PropagationKind.PARTICLE_ORIGIN,
            "enclosing_quality_name": "position<box>::action</close_file>::position<target>",
            "triggered_quality_name": None,
            "line": 18,
            "column": 30,
            "file_path": "middle.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/middle>",
            "triggered_quality_name": "action<my.domain.com:my_lib:/close_file>",
            "line": 21,
            "column": 30,
            "file_path": "middle.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DESTRUCTOR_CASCADE,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/close_file>",
            "triggered_quality_name": "action<my.domain.com:my_lib:/destructor>",
            "line": 7,
            "column": 33,
            "file_path": "close_file.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/destructor>",
            "triggered_quality_name": None,
            "line": 10,
            "column": 30,
            "file_path": "destructor.dfn",
        },
    )
    assert action_graph(result.reference_graph_result) == [
        (_CLOSE_FILE, _DESTRUCTOR),
        (_MIDDLE, _CLOSE_FILE),
        (_OUTER, _MIDDLE),
        (_TEST, _OUTER),
    ]


def test_six_level_destructor_knower_separate_from_resolvers_satisfied(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert action_graph(result.reference_graph_result) == [
        (_INNER, _CLOSE_FILE),
        (_MIDDLE, _INNER),
        (_CLOSE_FILE, _DESTRUCTOR),
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
    assert (
        all_diags[0].position_name
        == "position<box>::action</middle>::position<incoming>::position</p1>"
    )
    assert all_diags[0].action_name == "action<my.domain.com:my_lib:/middle>"
    assert all_diags[0].required_empty is False
    assert all_diags[0].required_value is False
    assert_propagation_chain(
        all_diags[0],
        {
            "kind": action_contract.PropagationKind.QUALITY_ASSIGNED,
            "enclosing_quality_name": "position<incoming>",
            "triggered_quality_name": "action<my.domain.com:my_lib:/destructor>",
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
            "enclosing_quality_name": "action<my.domain.com:my_lib:/outer>",
            "triggered_quality_name": "action<my.domain.com:my_lib:/middle>",
            "line": 18,
            "column": 30,
            "file_path": "outer.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/middle>",
            "triggered_quality_name": "action<my.domain.com:my_lib:/inner>",
            "line": 21,
            "column": 30,
            "file_path": "middle.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/inner>",
            "triggered_quality_name": "action<my.domain.com:my_lib:/close_file>",
            "line": 20,
            "column": 30,
            "file_path": "inner.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DESTRUCTOR_CASCADE,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/close_file>",
            "triggered_quality_name": "action<my.domain.com:my_lib:/destructor>",
            "line": 7,
            "column": 33,
            "file_path": "close_file.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/destructor>",
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
    assert (
        all_diags[1].position_name
        == "position<box>::action</middle>::position<incoming>::position</p2>"
    )
    assert all_diags[1].action_name == "action<my.domain.com:my_lib:/middle>"
    assert all_diags[1].required_empty is False
    assert all_diags[1].required_value is False
    assert_propagation_chain(
        all_diags[1],
        {
            "kind": action_contract.PropagationKind.QUALITY_ASSIGNED,
            "enclosing_quality_name": "position<incoming>",
            "triggered_quality_name": "action<my.domain.com:my_lib:/destructor>",
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
            "enclosing_quality_name": "action<my.domain.com:my_lib:/outer>",
            "triggered_quality_name": "action<my.domain.com:my_lib:/middle>",
            "line": 18,
            "column": 30,
            "file_path": "outer.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/middle>",
            "triggered_quality_name": "action<my.domain.com:my_lib:/inner>",
            "line": 21,
            "column": 30,
            "file_path": "middle.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/inner>",
            "triggered_quality_name": "action<my.domain.com:my_lib:/close_file>",
            "line": 20,
            "column": 30,
            "file_path": "inner.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DESTRUCTOR_CASCADE,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/close_file>",
            "triggered_quality_name": "action<my.domain.com:my_lib:/destructor>",
            "line": 7,
            "column": 33,
            "file_path": "close_file.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/destructor>",
            "triggered_quality_name": None,
            "line": 10,
            "column": 30,
            "file_path": "destructor.dfn",
        },
    )
    assert action_graph(result.reference_graph_result) == [
        (_INNER, _CLOSE_FILE),
        (_MIDDLE, _INNER),
        (_CLOSE_FILE, _DESTRUCTOR),
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
    assert all_diags[0].location.line == 25
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
    assert action_graph(result.reference_graph_result) == [
        (_CLOSE_FILE, _DESTRUCTOR),
        (_TEST, _CLOSE_FILE),
    ]


def test_destroyer_callee_emptying_it_never_applied_violates_caller_destructor_requirement(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.InferredRequirementViolationDiagnostic)
    assert all_diags[0].location.line == 18
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert (
        all_diags[0].position_name
        == "action</destroyer>::position<target>::position</child>::position</grandchild>"
    )
    assert all_diags[0].action_name == "action<my.domain.com:my_lib:/destroyer>"
    assert all_diags[0].required_empty is False
    assert all_diags[0].required_value is False
    assert_propagation_chain(
        all_diags[0],
        {
            "kind": action_contract.PropagationKind.QUALITY_ASSIGNED,
            "enclosing_quality_name": "position<holder>",
            "triggered_quality_name": "action<my.domain.com:my_lib:/watcher>",
            "line": 13,
            "column": 28,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.PARTICLE_ORIGIN,
            "enclosing_quality_name": "action</destroyer>::position<target>",
            "triggered_quality_name": None,
            "line": 16,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/test>",
            "triggered_quality_name": "action<my.domain.com:my_lib:/destroyer>",
            "line": 18,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DESTRUCTOR_CASCADE,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/destroyer>",
            "triggered_quality_name": "action<my.domain.com:my_lib:/watcher>",
            "line": 12,
            "column": 33,
            "file_path": "destroyer.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/watcher>",
            "triggered_quality_name": None,
            "line": 7,
            "column": 30,
            "file_path": "watcher.dfn",
        },
    )


def test_caller_callee_emptying_it_never_applied_violates_caller_destructor_requirement(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.InferredRequirementViolationDiagnostic)
    assert all_diags[0].location.line == 19
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert (
        all_diags[0].position_name
        == "action</destroyer>::position<target>::position</child>::position</grandchild>"
    )
    assert all_diags[0].action_name == "action<my.domain.com:my_lib:/destroyer>"
    assert all_diags[0].required_empty is False
    assert all_diags[0].required_value is False
    assert_propagation_chain(
        all_diags[0],
        {
            "kind": action_contract.PropagationKind.QUALITY_ASSIGNED,
            "enclosing_quality_name": "position<holder>",
            "triggered_quality_name": "action<my.domain.com:my_lib:/watcher>",
            "line": 13,
            "column": 28,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.PARTICLE_ORIGIN,
            "enclosing_quality_name": "action</destroyer>::position<target>",
            "triggered_quality_name": None,
            "line": 16,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/test>",
            "triggered_quality_name": "action<my.domain.com:my_lib:/destroyer>",
            "line": 19,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DESTRUCTOR_CASCADE,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/destroyer>",
            "triggered_quality_name": "action<my.domain.com:my_lib:/watcher>",
            "line": 7,
            "column": 33,
            "file_path": "destroyer.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/watcher>",
            "triggered_quality_name": None,
            "line": 7,
            "column": 30,
            "file_path": "watcher.dfn",
        },
    )


def test_caller_checks_failing_destructor_its_callee_left_below_particle_another_callee_destroys(
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
    assert all_diags[0].location.end_column == 63
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert (
        all_diags[0].position_name
        == "action</destroyer>::position<target>::position</child_1>::position</child_2>::position</needed>"
    )
    assert all_diags[0].required_empty is False
    assert all_diags[0].required_value is False
    assert all_diags[0].action_name == "action<my.domain.com:my_lib:/destroyer>"
    assert_propagation_chain(
        all_diags[0],
        {
            "kind": action_contract.PropagationKind.QUALITY_ASSIGNED,
            "enclosing_quality_name": "position<my.domain.com:my_lib:/child_2>",
            "triggered_quality_name": "action<my.domain.com:my_lib:/cleanup>",
            "line": 3,
            "column": 20,
            "file_path": "child_2.dfn",
        },
        {
            "kind": action_contract.PropagationKind.PARTICLE_ORIGIN,
            "enclosing_quality_name": "action</destroyer>::position<target>::position</child_1>::position</child_2>",
            "triggered_quality_name": None,
            "line": 8,
            "column": 30,
            "file_path": "fill_2.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _TEST,
            "triggered_quality_name": "action<my.domain.com:my_lib:/destroyer>",
            "line": 18,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DESTRUCTOR_CASCADE,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/destroyer>",
            "triggered_quality_name": "action<my.domain.com:my_lib:/cleanup>",
            "line": 7,
            "column": 33,
            "file_path": "destroyer.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/cleanup>",
            "triggered_quality_name": None,
            "line": 7,
            "column": 30,
            "file_path": "cleanup.dfn",
        },
    )


def test_caller_checks_destructor_requirement_on_position_its_callee_left_empty_below_new_particle(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.InferredRequirementViolationDiagnostic)
    assert all_diags[0].location.line == 19
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.end_line == 19
    assert all_diags[0].location.end_column == 63
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert (
        all_diags[0].position_name
        == "action</destroyer>::position<target>::position</child_1>::position</needed>"
    )
    assert all_diags[0].required_empty is False
    assert all_diags[0].required_value is False
    assert all_diags[0].action_name == "action<my.domain.com:my_lib:/destroyer>"
    assert_propagation_chain(
        all_diags[0],
        {
            "kind": action_contract.PropagationKind.QUALITY_ASSIGNED,
            "enclosing_quality_name": "position<my.domain.com:my_lib:/child_1>",
            "triggered_quality_name": "action<my.domain.com:my_lib:/cleanup>",
            "line": 4,
            "column": 20,
            "file_path": "child_1.dfn",
        },
        {
            "kind": action_contract.PropagationKind.PARTICLE_ORIGIN,
            "enclosing_quality_name": "action</destroyer>::position<target>::position</child_1>",
            "triggered_quality_name": None,
            "line": 8,
            "column": 30,
            "file_path": "fill_1.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _TEST,
            "triggered_quality_name": "action<my.domain.com:my_lib:/destroyer>",
            "line": 19,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DESTRUCTOR_CASCADE,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/destroyer>",
            "triggered_quality_name": "action<my.domain.com:my_lib:/cleanup>",
            "line": 7,
            "column": 33,
            "file_path": "destroyer.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/cleanup>",
            "triggered_quality_name": None,
            "line": 7,
            "column": 30,
            "file_path": "cleanup.dfn",
        },
    )


def test_caller_skips_destructor_requirement_on_position_its_callee_left_in_error_below_new_particle(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.MoveFromEmptyPositionDiagnostic)
    assert all_diags[0].location.line == 9
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.end_line == 9
    assert all_diags[0].location.end_column == 67
    assert all_diags[0].location.file_path == PurePosixPath("fill_1.dfn")
    assert all_diags[0].position_name == "position</child_1>::position</needed>"
    assert all_diags[0].is_action_interface_position is False
    assert all_diags[0].inferred_at is None


def test_caller_checks_destructor_value_requirement_on_particle_its_callee_left_below_new_particle(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.InferredRequirementViolationDiagnostic)
    assert all_diags[0].location.line == 19
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.end_line == 19
    assert all_diags[0].location.end_column == 63
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert (
        all_diags[0].position_name
        == "action</destroyer>::position<target>::position</child_1>::position</value>"
    )
    assert all_diags[0].required_empty is False
    assert all_diags[0].required_value is True
    assert all_diags[0].action_name == "action<my.domain.com:my_lib:/destroyer>"
    assert_propagation_chain(
        all_diags[0],
        {
            "kind": action_contract.PropagationKind.QUALITY_ASSIGNED,
            "enclosing_quality_name": "position<my.domain.com:my_lib:/child_1>",
            "triggered_quality_name": "action<my.domain.com:my_lib:/cleanup>",
            "line": 3,
            "column": 20,
            "file_path": "child_1.dfn",
        },
        {
            "kind": action_contract.PropagationKind.PARTICLE_ORIGIN,
            "enclosing_quality_name": "action</destroyer>::position<target>::position</child_1>",
            "triggered_quality_name": None,
            "line": 8,
            "column": 30,
            "file_path": "fill_1.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _TEST,
            "triggered_quality_name": "action<my.domain.com:my_lib:/destroyer>",
            "line": 19,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DESTRUCTOR_CASCADE,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/destroyer>",
            "triggered_quality_name": "action<my.domain.com:my_lib:/cleanup>",
            "line": 7,
            "column": 33,
            "file_path": "destroyer.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/cleanup>",
            "triggered_quality_name": None,
            "line": 13,
            "column": 78,
            "file_path": "cleanup.dfn",
        },
    )


def test_knower_resolves_destructor_requirement_below_position_its_callee_emptied(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 2
    assert isinstance(all_diags[0], diagnostics.InferredRequirementViolationDiagnostic)
    assert all_diags[0].location.line == 19
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("mid.dfn")
    assert (
        all_diags[0].position_name
        == "position<box>::action</inner>::position<target>::position</shelf>"
    )
    assert all_diags[0].action_name == "action<my.domain.com:my_lib:/inner>"
    assert all_diags[0].required_empty is False
    assert all_diags[0].required_value is False
    assert_propagation_chain(
        all_diags[0],
        {
            "kind": action_contract.PropagationKind.QUALITY_ASSIGNED,
            "enclosing_quality_name": "position<incoming>",
            "triggered_quality_name": "action<my.domain.com:my_lib:/destructor>",
            "line": 4,
            "column": 24,
            "file_path": "mid.dfn",
        },
        {
            "kind": action_contract.PropagationKind.PARTICLE_ORIGIN,
            "enclosing_quality_name": "position<box>::action</inner>::position<target>",
            "triggered_quality_name": None,
            "line": 18,
            "column": 30,
            "file_path": "mid.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/mid>",
            "triggered_quality_name": "action<my.domain.com:my_lib:/inner>",
            "line": 19,
            "column": 30,
            "file_path": "mid.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DESTRUCTOR_CASCADE,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/inner>",
            "triggered_quality_name": "action<my.domain.com:my_lib:/destructor>",
            "line": 12,
            "column": 33,
            "file_path": "inner.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/destructor>",
            "triggered_quality_name": None,
            "line": 7,
            "column": 30,
            "file_path": "destructor.dfn",
        },
    )
    assert isinstance(all_diags[1], diagnostics.InferredRequirementViolationDiagnostic)
    assert all_diags[1].location.line == 19
    assert all_diags[1].location.column == 30
    assert all_diags[1].location.file_path == PurePosixPath("mid.dfn")
    assert (
        all_diags[1].position_name
        == "position<box>::action</inner>::position<target>::position</shelf>::position</book>"
    )
    assert all_diags[1].action_name == "action<my.domain.com:my_lib:/inner>"
    assert all_diags[1].required_empty is False
    assert all_diags[1].required_value is False
    assert_propagation_chain(
        all_diags[1],
        {
            "kind": action_contract.PropagationKind.QUALITY_ASSIGNED,
            "enclosing_quality_name": "position<incoming>",
            "triggered_quality_name": "action<my.domain.com:my_lib:/destructor>",
            "line": 4,
            "column": 24,
            "file_path": "mid.dfn",
        },
        {
            "kind": action_contract.PropagationKind.PARTICLE_ORIGIN,
            "enclosing_quality_name": "position<box>::action</inner>::position<target>",
            "triggered_quality_name": None,
            "line": 18,
            "column": 30,
            "file_path": "mid.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/mid>",
            "triggered_quality_name": "action<my.domain.com:my_lib:/inner>",
            "line": 19,
            "column": 30,
            "file_path": "mid.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DESTRUCTOR_CASCADE,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/inner>",
            "triggered_quality_name": "action<my.domain.com:my_lib:/destructor>",
            "line": 12,
            "column": 33,
            "file_path": "inner.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/destructor>",
            "triggered_quality_name": None,
            "line": 7,
            "column": 30,
            "file_path": "destructor.dfn",
        },
    )
    assert action_graph(result.reference_graph_result) == [
        (_INNER, _DESTRUCTOR),
        (_MID, _INNER),
        (_TEST, _MID),
    ]


def test_knower_requires_value_of_position_no_lower_action_knows(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.InferredRequirementViolationDiagnostic)
    assert all_diags[0].location.line == 22
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.end_line == 22
    assert all_diags[0].location.end_column == 78
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert (
        all_diags[0].position_name
        == "position<outer_box>::action</mid>::position<incoming>::position</reading>"
    )
    assert all_diags[0].required_empty is False
    assert all_diags[0].required_value is True
    assert all_diags[0].action_name == _MID
    assert_propagation_chain(
        all_diags[0],
        {
            "kind": action_contract.PropagationKind.FILL_SITE,
            "enclosing_quality_name": "position<outer_box>::action</mid>::position<incoming>::position</reading>",
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
            "kind": action_contract.PropagationKind.QUALITY_ASSIGNED,
            "enclosing_quality_name": "position<incoming>",
            "triggered_quality_name": _DESTRUCTOR,
            "line": 4,
            "column": 24,
            "file_path": "mid.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _MID,
            "triggered_quality_name": _INNER,
            "line": 18,
            "column": 30,
            "file_path": "mid.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DESTRUCTOR_CASCADE,
            "enclosing_quality_name": _INNER,
            "triggered_quality_name": _DESTRUCTOR,
            "line": 7,
            "column": 33,
            "file_path": "inner.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": _DESTRUCTOR,
            "triggered_quality_name": None,
            "line": 13,
            "column": 78,
            "file_path": "destructor.dfn",
        },
    )
    assert action_graph(result.reference_graph_result) == [
        (_DESTRUCTOR, _KEEP),
        (_INNER, _DESTRUCTOR),
        (_MID, _INNER),
        (_TEST, _MID),
    ]


def test_knower_skips_destructor_requirement_below_position_its_callee_left_in_error(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.MoveFromEmptyPositionDiagnostic)
    assert all_diags[0].location.line == 13
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("inner.dfn")
    assert all_diags[0].position_name == "position<target>::position</shelf>"
    assert all_diags[0].is_action_interface_position is False
    assert all_diags[0].inferred_at is None
    assert action_graph(result.reference_graph_result) == [
        (_INNER, _DESTRUCTOR),
        (_MID, _INNER),
        (_TEST, _MID),
    ]


def test_knower_skips_destructor_requirement_below_its_own_position_in_error(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.MoveFromEmptyPositionDiagnostic)
    assert all_diags[0].location.line == 21
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].position_name == "position<my_item>::position</z>"
    assert all_diags[0].is_action_interface_position is False
    assert all_diags[0].inferred_at is None
    assert action_graph(result.reference_graph_result) == [
        (_CLOSE_FILE, _DESTRUCTOR),
        (_TEST, _CLOSE_FILE),
    ]


def test_knower_does_not_follow_requirements_it_gains_below_destroyed_particle(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 2
    assert isinstance(all_diags[0], diagnostics.InferredRequirementViolationDiagnostic)
    assert all_diags[0].required_value is False
    assert all_diags[0].location.line == 19
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.end_line == 19
    assert all_diags[0].location.end_column == 78
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].action_name == _MID
    assert all_diags[0].required_empty is False
    assert (
        all_diags[0].position_name
        == "position<outer_box>::action</mid>::position<incoming>::position</node>"
    )
    assert_propagation_chain(
        all_diags[0],
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _TEST,
            "triggered_quality_name": _MID,
            "line": 19,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.QUALITY_ASSIGNED,
            "enclosing_quality_name": "position<incoming>",
            "triggered_quality_name": _D,
            "line": 4,
            "column": 24,
            "file_path": "mid.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _MID,
            "triggered_quality_name": _INNER,
            "line": 18,
            "column": 30,
            "file_path": "mid.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DESTRUCTOR_CASCADE,
            "enclosing_quality_name": _INNER,
            "triggered_quality_name": _D,
            "line": 7,
            "column": 33,
            "file_path": "inner.dfn",
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
    assert isinstance(all_diags[1], diagnostics.CircularGlobalReferenceDiagnostic)
    assert all_diags[1].location.line == 3
    assert all_diags[1].location.column == 20
    assert all_diags[1].location.end_line == 3
    assert all_diags[1].location.end_column == 30
    assert all_diags[1].location.file_path == PurePosixPath("node.dfn")
    assert all_diags[1].cycle == [_D, "position<my.domain.com:my_lib:/node>", _D]
    assert action_graph(result.reference_graph_result) == [
        (_INNER, _D),
        (_MID, _INNER),
        (_TEST, _MID),
    ]


def test_knower_resolves_destructor_requirement_on_its_own_interface_position(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.InferredRequirementViolationDiagnostic)
    assert all_diags[0].required_value is False
    assert all_diags[0].location.line == 18
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("mid.dfn")
    assert all_diags[0].action_name == _INNER
    assert all_diags[0].required_empty is False
    assert (
        all_diags[0].position_name
        == "position<box>::action</inner>::position<target>::action</destructor>::position<item>"
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
            "enclosing_quality_name": "position<box>::action</inner>::position<target>",
            "triggered_quality_name": None,
            "line": 17,
            "column": 30,
            "file_path": "mid.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _MID,
            "triggered_quality_name": _INNER,
            "line": 18,
            "column": 30,
            "file_path": "mid.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DESTRUCTOR_CASCADE,
            "enclosing_quality_name": _INNER,
            "triggered_quality_name": _DESTRUCTOR,
            "line": 7,
            "column": 33,
            "file_path": "inner.dfn",
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
    assert action_graph(result.reference_graph_result) == [
        (_INNER, _DESTRUCTOR),
        (_MID, _INNER),
        (_TEST, _MID),
    ]


def test_destructor_requirement_violation_through_constructor_names_constructor_trigger(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.InferredRequirementViolationDiagnostic)
    assert all_diags[0].location.line == 16
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert (
        all_diags[0].position_name
        == "position<item>::position</left>::position</needed>"
    )
    assert all_diags[0].action_name == "action<my.domain.com:my_lib:/cleanup>"
    assert all_diags[0].required_empty is False
    assert all_diags[0].required_value is False
    assert_propagation_chain(
        all_diags[0],
        {
            "kind": action_contract.PropagationKind.QUALITY_ASSIGNED,
            "enclosing_quality_name": "position<left>",
            "triggered_quality_name": _DESTRUCTOR,
            "line": 8,
            "column": 28,
            "file_path": "initialize.dfn",
        },
        {
            "kind": action_contract.PropagationKind.PARTICLE_ORIGIN,
            "enclosing_quality_name": "position<item>::position</left>",
            "triggered_quality_name": None,
            "line": 11,
            "column": 30,
            "file_path": "initialize.dfn",
        },
        {
            "kind": action_contract.PropagationKind.CONSTRUCTOR_TRIGGER,
            "enclosing_quality_name": _TEST,
            "triggered_quality_name": "action<my.domain.com:my_lib:/cleanup>",
            "line": 16,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DESTRUCTOR_CASCADE,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/cleanup>",
            "triggered_quality_name": _DESTRUCTOR,
            "line": 6,
            "column": 33,
            "file_path": "cleanup.dfn",
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
