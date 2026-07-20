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
_INNER = "action<my.domain.com:my_lib:/inner>"
_DESTRUCTOR = "action<my.domain.com:my_lib:/destructor>"
_DESTRUCTOR_A = "action<my.domain.com:my_lib:/destructor_a>"
_DESTRUCTOR_B = "action<my.domain.com:my_lib:/destructor_b>"
_DESTRUCTOR_EMPTY = "action<my.domain.com:my_lib:/destructor_empty>"
_CHILD_DESTRUCTOR = "action<my.domain.com:my_lib:/child_destructor>"


def test_local_position_left_occupied_fires_destructor(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert result.action_call_graph.edges() == [(_TEST, _DESTRUCTOR)]


def test_local_position_in_constructor_left_occupied_fires_destructor(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert result.action_call_graph.edges() == [(_TEST, _DESTRUCTOR)]


def test_auto_destruction_in_reverse_definition_order(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    edges = result.action_call_graph.edges()
    assert edges == [(_TEST, _DESTRUCTOR_B), (_TEST, _DESTRUCTOR_A)]


def test_empty_local_position_does_not_fire_destructor(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.UnreferencedPositionDiagnostic)
    assert all_diags[0].position_name == "position<box>"
    assert all_diags[0].location.line == 7
    assert all_diags[0].location.column == 29
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert result.action_call_graph.edges() == []


def test_explicit_destroy_before_block_end_does_not_double_fire(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    edges = result.action_call_graph.edges()
    assert edges == [(_TEST, _DESTRUCTOR)]


def test_auto_destruction_cascades_into_child_particle_destructors(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert result.action_call_graph.edges() == [(_TEST, _CHILD_DESTRUCTOR)]


def test_move_from_interface_position_to_local_then_auto_destroy(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert result.action_call_graph.edges() == [(_TEST, _DESTRUCTOR)]


def test_move_from_implied_position_to_local_then_auto_destroy(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert result.action_call_graph.edges() == [(_TEST, _DESTRUCTOR)]


def test_auto_destruction_failing_empty_requirement(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    diag = all_diags[0]
    assert isinstance(diag, diagnostics.InferredRequirementViolationDiagnostic)
    assert diag.location.line == 11
    assert diag.location.column == 30
    assert diag.location.file_path == PurePosixPath("test.dfn")
    assert diag.action_name == _DESTRUCTOR_EMPTY
    assert diag.required_empty is True
    assert (
        diag.position_name == "position<box>::action</destructor_empty>::position<item>"
    )
    assert_propagation_chain(
        diag,
        {
            "kind": action_contract.PropagationKind.QUALITY_ASSIGNED,
            "enclosing_quality_name": "position<box>",
            "triggered_quality_name": _DESTRUCTOR_EMPTY,
            "line": 8,
            "column": 28,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.PARTICLE_ORIGIN,
            "enclosing_quality_name": "position<box>",
            "triggered_quality_name": None,
            "line": 11,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.FILL_SITE,
            "enclosing_quality_name": "position<box>::action</destructor_empty>::position<item>",
            "triggered_quality_name": None,
            "line": 12,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.AUTO_DESTRUCTION,
            "enclosing_quality_name": "position<box>",
            "triggered_quality_name": _TEST,
            "line": 11,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DESTRUCTOR_CASCADE,
            "enclosing_quality_name": _TEST,
            "triggered_quality_name": _DESTRUCTOR_EMPTY,
            "line": 11,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": _DESTRUCTOR_EMPTY,
            "triggered_quality_name": None,
            "line": 8,
            "column": 30,
            "file_path": "destructor_empty.dfn",
        },
    )


def test_auto_destruction_failing_occupied_requirement(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    diag = all_diags[0]
    assert isinstance(diag, diagnostics.InferredRequirementViolationDiagnostic)
    assert diag.location.line == 13
    assert diag.location.column == 30
    assert diag.location.file_path == PurePosixPath("test.dfn")
    assert diag.action_name == _DESTRUCTOR
    assert diag.required_empty is False
    assert diag.position_name == "position<box>::action</destructor>::position<item>"
    assert_propagation_chain(
        diag,
        {
            "kind": action_contract.PropagationKind.QUALITY_ASSIGNED,
            "enclosing_quality_name": "position<box>",
            "triggered_quality_name": _DESTRUCTOR,
            "line": 10,
            "column": 28,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.PARTICLE_ORIGIN,
            "enclosing_quality_name": "position<box>",
            "triggered_quality_name": None,
            "line": 13,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.AUTO_DESTRUCTION,
            "enclosing_quality_name": "position<box>",
            "triggered_quality_name": _TEST,
            "line": 13,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DESTRUCTOR_CASCADE,
            "enclosing_quality_name": _TEST,
            "triggered_quality_name": _DESTRUCTOR,
            "line": 13,
            "column": 30,
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


def test_constructor_auto_destruction_failing_requirement(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    diag = all_diags[0]
    assert isinstance(diag, diagnostics.InferredRequirementViolationDiagnostic)
    assert diag.location.line == 10
    assert diag.location.column == 30
    assert diag.location.file_path == PurePosixPath("test.dfn")
    assert diag.action_name == _DESTRUCTOR_EMPTY
    assert diag.required_empty is True
    assert (
        diag.position_name == "position<box>::action</destructor_empty>::position<item>"
    )
    assert_propagation_chain(
        diag,
        {
            "kind": action_contract.PropagationKind.QUALITY_ASSIGNED,
            "enclosing_quality_name": "position<box>",
            "triggered_quality_name": _DESTRUCTOR_EMPTY,
            "line": 7,
            "column": 28,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.PARTICLE_ORIGIN,
            "enclosing_quality_name": "position<box>",
            "triggered_quality_name": None,
            "line": 10,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.FILL_SITE,
            "enclosing_quality_name": "position<box>::action</destructor_empty>::position<item>",
            "triggered_quality_name": None,
            "line": 11,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.AUTO_DESTRUCTION,
            "enclosing_quality_name": "position<box>",
            "triggered_quality_name": _TEST,
            "line": 10,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DESTRUCTOR_CASCADE,
            "enclosing_quality_name": _TEST,
            "triggered_quality_name": _DESTRUCTOR_EMPTY,
            "line": 10,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": _DESTRUCTOR_EMPTY,
            "triggered_quality_name": None,
            "line": 8,
            "column": 30,
            "file_path": "destructor_empty.dfn",
        },
    )


def test_auto_destruction_failing_in_reverse_definition_order(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 2
    box_a_diag = all_diags[0]
    assert isinstance(box_a_diag, diagnostics.InferredRequirementViolationDiagnostic)
    assert box_a_diag.location.line == 18
    assert box_a_diag.location.column == 30
    assert box_a_diag.location.file_path == PurePosixPath("test.dfn")
    assert box_a_diag.action_name == _DESTRUCTOR_EMPTY
    assert box_a_diag.required_empty is True
    assert (
        box_a_diag.position_name
        == "position<box_a>::action</destructor_empty>::position<item>"
    )
    assert_propagation_chain(
        box_a_diag,
        {
            "kind": action_contract.PropagationKind.QUALITY_ASSIGNED,
            "enclosing_quality_name": "position<box_a>",
            "triggered_quality_name": _DESTRUCTOR_EMPTY,
            "line": 10,
            "column": 28,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.PARTICLE_ORIGIN,
            "enclosing_quality_name": "position<box_a>",
            "triggered_quality_name": None,
            "line": 18,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.FILL_SITE,
            "enclosing_quality_name": "position<box_a>::action</destructor_empty>::position<item>",
            "triggered_quality_name": None,
            "line": 19,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.AUTO_DESTRUCTION,
            "enclosing_quality_name": "position<box_a>",
            "triggered_quality_name": _TEST,
            "line": 18,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DESTRUCTOR_CASCADE,
            "enclosing_quality_name": _TEST,
            "triggered_quality_name": _DESTRUCTOR_EMPTY,
            "line": 18,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": _DESTRUCTOR_EMPTY,
            "triggered_quality_name": None,
            "line": 8,
            "column": 30,
            "file_path": "destructor_empty.dfn",
        },
    )

    box_b_diag = all_diags[1]
    assert isinstance(box_b_diag, diagnostics.InferredRequirementViolationDiagnostic)
    assert box_b_diag.location.line == 20
    assert box_b_diag.location.column == 30
    assert box_b_diag.location.file_path == PurePosixPath("test.dfn")
    assert box_b_diag.action_name == _DESTRUCTOR_EMPTY
    assert box_b_diag.required_empty is True
    assert (
        box_b_diag.position_name
        == "position<box_b>::action</destructor_empty>::position<item>"
    )
    assert_propagation_chain(
        box_b_diag,
        {
            "kind": action_contract.PropagationKind.QUALITY_ASSIGNED,
            "enclosing_quality_name": "position<box_b>",
            "triggered_quality_name": _DESTRUCTOR_EMPTY,
            "line": 15,
            "column": 28,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.PARTICLE_ORIGIN,
            "enclosing_quality_name": "position<box_b>",
            "triggered_quality_name": None,
            "line": 20,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.FILL_SITE,
            "enclosing_quality_name": "position<box_b>::action</destructor_empty>::position<item>",
            "triggered_quality_name": None,
            "line": 21,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.AUTO_DESTRUCTION,
            "enclosing_quality_name": "position<box_b>",
            "triggered_quality_name": _TEST,
            "line": 20,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DESTRUCTOR_CASCADE,
            "enclosing_quality_name": _TEST,
            "triggered_quality_name": _DESTRUCTOR_EMPTY,
            "line": 20,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": _DESTRUCTOR_EMPTY,
            "triggered_quality_name": None,
            "line": 8,
            "column": 30,
            "file_path": "destructor_empty.dfn",
        },
    )


def test_cascade_child_auto_destruction_failing_requirement(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    diag = all_diags[0]
    assert isinstance(diag, diagnostics.InferredRequirementViolationDiagnostic)
    assert diag.location.line == 11
    assert diag.location.column == 30
    assert diag.location.file_path == PurePosixPath("test.dfn")
    assert diag.action_name == _DESTRUCTOR_EMPTY
    assert diag.required_empty is True
    assert diag.position_name == (
        "position<box>::position</child_q>::action</destructor_empty>::position<item>"
    )
    assert_propagation_chain(
        diag,
        {
            "kind": action_contract.PropagationKind.QUALITY_ASSIGNED,
            "enclosing_quality_name": "position<my.domain.com:my_lib:/child_q>",
            "triggered_quality_name": _DESTRUCTOR_EMPTY,
            "line": 3,
            "column": 20,
            "file_path": "child_q.dfn",
        },
        {
            "kind": action_contract.PropagationKind.PARTICLE_ORIGIN,
            "enclosing_quality_name": "position<box>::position</child_q>",
            "triggered_quality_name": None,
            "line": 12,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.FILL_SITE,
            "enclosing_quality_name": "position<box>::position</child_q>::action</destructor_empty>::position<item>",
            "triggered_quality_name": None,
            "line": 13,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.AUTO_DESTRUCTION,
            "enclosing_quality_name": "position<box>",
            "triggered_quality_name": _TEST,
            "line": 11,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DESTRUCTOR_CASCADE,
            "enclosing_quality_name": _TEST,
            "triggered_quality_name": _DESTRUCTOR_EMPTY,
            "line": 11,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": _DESTRUCTOR_EMPTY,
            "triggered_quality_name": None,
            "line": 8,
            "column": 30,
            "file_path": "destructor_empty.dfn",
        },
    )


def test_interface_to_local_auto_destruction_failing_requirement(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    diag = all_diags[0]
    assert isinstance(diag, diagnostics.InferredRequirementViolationDiagnostic)
    assert diag.location.line == 16
    assert diag.location.column == 52
    assert diag.location.file_path == PurePosixPath("test.dfn")
    assert diag.action_name == _DESTRUCTOR_EMPTY
    assert diag.required_empty is True
    assert (
        diag.position_name
        == "position<local>::action</destructor_empty>::position<item>"
    )
    assert_propagation_chain(
        diag,
        {
            "kind": action_contract.PropagationKind.QUALITY_ASSIGNED,
            "enclosing_quality_name": "position<incoming>",
            "triggered_quality_name": _DESTRUCTOR_EMPTY,
            "line": 4,
            "column": 24,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.PARTICLE_ORIGIN,
            "enclosing_quality_name": "position<local>",
            "triggered_quality_name": None,
            "line": 16,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.FILL_SITE,
            "enclosing_quality_name": "position<local>::action</destructor_empty>::position<item>",
            "triggered_quality_name": None,
            "line": 17,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.AUTO_DESTRUCTION,
            "enclosing_quality_name": "position<local>",
            "triggered_quality_name": _TEST,
            "line": 16,
            "column": 52,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DESTRUCTOR_CASCADE,
            "enclosing_quality_name": _TEST,
            "triggered_quality_name": _DESTRUCTOR_EMPTY,
            "line": 16,
            "column": 52,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": _DESTRUCTOR_EMPTY,
            "triggered_quality_name": None,
            "line": 8,
            "column": 30,
            "file_path": "destructor_empty.dfn",
        },
    )


def test_implied_to_local_auto_destruction_failing_requirement(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    diag = all_diags[0]
    assert isinstance(diag, diagnostics.InferredRequirementViolationDiagnostic)
    assert diag.location.line == 12
    assert diag.location.column == 54
    assert diag.location.file_path == PurePosixPath("test.dfn")
    assert diag.action_name == _DESTRUCTOR_EMPTY
    assert diag.required_empty is True
    assert (
        diag.position_name
        == "position<local>::action</destructor_empty>::position<item>"
    )
    assert_propagation_chain(
        diag,
        {
            "kind": action_contract.PropagationKind.QUALITY_ASSIGNED,
            "enclosing_quality_name": "position<my.domain.com:my_lib:/implied_q>",
            "triggered_quality_name": _DESTRUCTOR_EMPTY,
            "line": 3,
            "column": 20,
            "file_path": "implied_q.dfn",
        },
        {
            "kind": action_contract.PropagationKind.PARTICLE_ORIGIN,
            "enclosing_quality_name": "position<local>",
            "triggered_quality_name": None,
            "line": 12,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.FILL_SITE,
            "enclosing_quality_name": "position<local>::action</destructor_empty>::position<item>",
            "triggered_quality_name": None,
            "line": 13,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.AUTO_DESTRUCTION,
            "enclosing_quality_name": "position<local>",
            "triggered_quality_name": _TEST,
            "line": 12,
            "column": 54,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DESTRUCTOR_CASCADE,
            "enclosing_quality_name": _TEST,
            "triggered_quality_name": _DESTRUCTOR_EMPTY,
            "line": 12,
            "column": 54,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": _DESTRUCTOR_EMPTY,
            "triggered_quality_name": None,
            "line": 8,
            "column": 30,
            "file_path": "destructor_empty.dfn",
        },
    )


def test_destructor_requirement_propagates_to_caller_via_interface(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    diag = all_diags[0]
    assert isinstance(diag, diagnostics.InferredRequirementViolationDiagnostic)
    assert diag.location.line == 15
    assert diag.location.column == 30
    assert diag.location.file_path == PurePosixPath("test.dfn")
    assert diag.action_name == _INNER
    assert diag.required_empty is True
    assert diag.position_name == (
        "position<box>::action</inner>::position<incoming>"
        "::action</destructor_empty>::position<item>"
    )
    assert_propagation_chain(
        diag,
        {
            "kind": action_contract.PropagationKind.FILL_SITE,
            "enclosing_quality_name": "position<box>::action</inner>::position<incoming>::action</destructor_empty>::position<item>",
            "triggered_quality_name": None,
            "line": 14,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _TEST,
            "triggered_quality_name": _INNER,
            "line": 15,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.QUALITY_ASSIGNED,
            "enclosing_quality_name": "position<incoming>",
            "triggered_quality_name": _DESTRUCTOR_EMPTY,
            "line": 4,
            "column": 24,
            "file_path": "inner.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DESTRUCTOR_CASCADE,
            "enclosing_quality_name": _INNER,
            "triggered_quality_name": _DESTRUCTOR_EMPTY,
            "line": 11,
            "column": 9,
            "file_path": "inner.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": _DESTRUCTOR_EMPTY,
            "triggered_quality_name": None,
            "line": 8,
            "column": 30,
            "file_path": "destructor_empty.dfn",
        },
    )
