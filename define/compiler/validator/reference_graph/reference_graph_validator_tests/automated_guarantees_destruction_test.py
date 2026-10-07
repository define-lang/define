from __future__ import annotations

import typing
from pathlib import PurePosixPath

from define.compiler.errors import diagnostics
from define.compiler.validator import codegen_input
from define.compiler.validator.reference_graph import action_contract
from define.compiler.validator.reference_graph.reference_graph_validator_tests.test_helpers import (
    assert_propagation_chain,
)
from define.compiler.validator.reference_graph.test_helpers import action_graph
from define.compiler.validator.test_helpers import assert_no_errors

if typing.TYPE_CHECKING:
    from define.compiler import conftest

_TEST = "action<my.domain.com:my_lib:/test>"
_HOLDER = "position<holder>"
_CHILD_1 = "position<my.domain.com:my_lib:/child_1>"
_CLEANUP = "action<my.domain.com:my_lib:/cleanup>"
_RETIRE = "action<my.domain.com:my_lib:/retire>"
_WRAPPER = "action<my.domain.com:my_lib:/wrapper>"
_EMPTY_MARKER = "action<my.domain.com:my_lib:/empty_marker>"
_BUILD = "action<my.domain.com:my_lib:/build>"


def _destroyed_positions(
    result: conftest.FullValidationResult,
) -> list[tuple[str, ...]]:
    step = result.reference_graph_result.codegen_input.actions[_TEST].steps[-1]
    assert isinstance(step, codegen_input.Destruction)
    return [
        destroyed.position.canonical_chained_name_tuple
        for destroyed in step.contribution.work.positions
    ]


def test_discardable_callee_guarantees_are_dropped_for_destroyed_particle(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert _destroyed_positions(result) == [
        (_HOLDER, "position<my.domain.com:my_lib:/child_1>"),
        (_HOLDER,),
    ]


def test_callee_guarantees_moving_particles_are_dropped_for_destroyed_particle(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert _destroyed_positions(result) == [
        (_HOLDER, "position<my.domain.com:my_lib:/child_1>"),
        (_HOLDER,),
    ]


def test_callee_guarantees_on_received_particle_are_destroyed_individually(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert _destroyed_positions(result) == [
        (
            _HOLDER,
            "position<my.domain.com:my_lib:/box>",
            "position<my.domain.com:my_lib:/inner>",
            "position<my.domain.com:my_lib:/marker>",
        ),
        (
            _HOLDER,
            "position<my.domain.com:my_lib:/box>",
            "position<my.domain.com:my_lib:/inner>",
        ),
        (_HOLDER, "position<my.domain.com:my_lib:/box>"),
        (_HOLDER,),
    ]


def test_callee_guarantees_creating_destructor_are_applied_for_destroyed_particle(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    diagnostic = all_diags[0]
    assert isinstance(diagnostic, diagnostics.InferredRequirementViolationDiagnostic)
    assert diagnostic.location.line == 13
    assert diagnostic.location.column == 30
    assert diagnostic.location.end_line == 13
    assert diagnostic.location.end_column == 46
    assert diagnostic.location.file_path == PurePosixPath("test.dfn")
    assert (
        diagnostic.position_name
        == "position<holder>::position</child_1>::position</child_2>::position</needed>"
    )
    assert diagnostic.required_empty is False
    assert diagnostic.required_value is False
    assert diagnostic.action_name == _CLEANUP
    assert_propagation_chain(
        diagnostic,
        {
            "kind": action_contract.PropagationKind.QUALITY_ASSIGNED,
            "enclosing_quality_name": "position<my.domain.com:my_lib:/child_2>",
            "triggered_quality_name": _CLEANUP,
            "line": 3,
            "column": 20,
            "file_path": "child_2.dfn",
        },
        {
            "kind": action_contract.PropagationKind.PARTICLE_ORIGIN,
            "enclosing_quality_name": "position<holder>::position</child_1>::position</child_2>",
            "triggered_quality_name": None,
            "line": 8,
            "column": 30,
            "file_path": "fill_2.dfn",
        },
        {
            "kind": action_contract.PropagationKind.AUTO_DESTRUCTION,
            "enclosing_quality_name": _HOLDER,
            "triggered_quality_name": _TEST,
            "line": 13,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DESTRUCTOR_CASCADE,
            "enclosing_quality_name": _TEST,
            "triggered_quality_name": _CLEANUP,
            "line": 13,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": _CLEANUP,
            "triggered_quality_name": None,
            "line": 7,
            "column": 30,
            "file_path": "cleanup.dfn",
        },
    )


def test_unrelated_callee_error_does_not_hide_destructor_requirement(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 2
    diagnostic = all_diags[0]
    assert isinstance(diagnostic, diagnostics.InferredRequirementViolationDiagnostic)
    assert diagnostic.location.line == 13
    assert diagnostic.location.column == 30
    assert diagnostic.location.end_line == 13
    assert diagnostic.location.end_column == 46
    assert diagnostic.location.file_path == PurePosixPath("test.dfn")
    assert (
        diagnostic.position_name
        == "position<holder>::position</child_1>::position</child_2>::position</needed>"
    )
    assert diagnostic.required_empty is False
    assert diagnostic.required_value is False
    assert diagnostic.action_name == _CLEANUP
    assert_propagation_chain(
        diagnostic,
        {
            "kind": action_contract.PropagationKind.QUALITY_ASSIGNED,
            "enclosing_quality_name": "position<my.domain.com:my_lib:/child_2>",
            "triggered_quality_name": _CLEANUP,
            "line": 3,
            "column": 20,
            "file_path": "child_2.dfn",
        },
        {
            "kind": action_contract.PropagationKind.PARTICLE_ORIGIN,
            "enclosing_quality_name": "position<holder>::position</child_1>::position</child_2>",
            "triggered_quality_name": None,
            "line": 8,
            "column": 30,
            "file_path": "fill_2.dfn",
        },
        {
            "kind": action_contract.PropagationKind.AUTO_DESTRUCTION,
            "enclosing_quality_name": _HOLDER,
            "triggered_quality_name": _TEST,
            "line": 13,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DESTRUCTOR_CASCADE,
            "enclosing_quality_name": _TEST,
            "triggered_quality_name": _CLEANUP,
            "line": 13,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": _CLEANUP,
            "triggered_quality_name": None,
            "line": 7,
            "column": 30,
            "file_path": "cleanup.dfn",
        },
    )
    assert isinstance(all_diags[1], diagnostics.DestroyInEmptyPositionDiagnostic)
    assert all_diags[1].location.line == 9
    assert all_diags[1].location.column == 33
    assert all_diags[1].location.end_line == 9
    assert all_diags[1].location.end_column == 48
    assert all_diags[1].location.file_path == PurePosixPath("fill_1.dfn")
    assert all_diags[1].position_name == "position<spare>"


def test_deep_callee_creating_destructor_below_child_particle_is_applied_for_destroyed_particle(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    diagnostic = all_diags[0]
    assert isinstance(diagnostic, diagnostics.InferredRequirementViolationDiagnostic)
    assert diagnostic.location.line == 14
    assert diagnostic.location.column == 30
    assert diagnostic.location.end_line == 14
    assert diagnostic.location.end_column == 46
    assert diagnostic.location.file_path == PurePosixPath("test.dfn")
    assert (
        diagnostic.position_name
        == "position<holder>::position</child_0>::position</child_1>::position</child_2>::position</child_3>::position</needed>"
    )
    assert diagnostic.required_empty is False
    assert diagnostic.required_value is False
    assert diagnostic.action_name == _CLEANUP
    assert_propagation_chain(
        diagnostic,
        {
            "kind": action_contract.PropagationKind.QUALITY_ASSIGNED,
            "enclosing_quality_name": "position<my.domain.com:my_lib:/child_3>",
            "triggered_quality_name": _CLEANUP,
            "line": 3,
            "column": 20,
            "file_path": "child_3.dfn",
        },
        {
            "kind": action_contract.PropagationKind.PARTICLE_ORIGIN,
            "enclosing_quality_name": "position<holder>::position</child_0>::position</child_1>::position</child_2>::position</child_3>",
            "triggered_quality_name": None,
            "line": 8,
            "column": 30,
            "file_path": "fill_3.dfn",
        },
        {
            "kind": action_contract.PropagationKind.AUTO_DESTRUCTION,
            "enclosing_quality_name": _HOLDER,
            "triggered_quality_name": _TEST,
            "line": 14,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DESTRUCTOR_CASCADE,
            "enclosing_quality_name": _TEST,
            "triggered_quality_name": _CLEANUP,
            "line": 14,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": _CLEANUP,
            "triggered_quality_name": None,
            "line": 7,
            "column": 30,
            "file_path": "cleanup.dfn",
        },
    )


def test_deep_callee_creating_destructor_on_same_particle_is_applied_for_destroyed_particle(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    diagnostic = all_diags[0]
    assert isinstance(diagnostic, diagnostics.InferredRequirementViolationDiagnostic)
    assert diagnostic.location.line == 15
    assert diagnostic.location.column == 30
    assert diagnostic.location.end_line == 15
    assert diagnostic.location.end_column == 46
    assert diagnostic.location.file_path == PurePosixPath("test.dfn")
    assert (
        diagnostic.position_name
        == "position<holder>::position</part>::position</needed>"
    )
    assert diagnostic.required_empty is False
    assert diagnostic.required_value is False
    assert diagnostic.action_name == _CLEANUP
    assert_propagation_chain(
        diagnostic,
        {
            "kind": action_contract.PropagationKind.QUALITY_ASSIGNED,
            "enclosing_quality_name": "position<my.domain.com:my_lib:/part>",
            "triggered_quality_name": _CLEANUP,
            "line": 3,
            "column": 20,
            "file_path": "part.dfn",
        },
        {
            "kind": action_contract.PropagationKind.PARTICLE_ORIGIN,
            "enclosing_quality_name": "position<holder>::position</part>",
            "triggered_quality_name": None,
            "line": 8,
            "column": 30,
            "file_path": "builder.dfn",
        },
        {
            "kind": action_contract.PropagationKind.AUTO_DESTRUCTION,
            "enclosing_quality_name": _HOLDER,
            "triggered_quality_name": _TEST,
            "line": 15,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DESTRUCTOR_CASCADE,
            "enclosing_quality_name": _TEST,
            "triggered_quality_name": _CLEANUP,
            "line": 15,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": _CLEANUP,
            "triggered_quality_name": None,
            "line": 7,
            "column": 30,
            "file_path": "cleanup.dfn",
        },
    )


def test_callee_guarantees_below_caller_particle_are_applied_for_destroyed_particle(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    diagnostic = all_diags[0]
    assert isinstance(diagnostic, diagnostics.InferredRequirementViolationDiagnostic)
    assert diagnostic.location.line == 18
    assert diagnostic.location.column == 30
    assert diagnostic.location.end_line == 18
    assert diagnostic.location.end_column == 63
    assert diagnostic.location.file_path == PurePosixPath("test.dfn")
    assert (
        diagnostic.position_name
        == "action</destroyer>::position<holder>::position</child_1>::position</child_2>"
    )
    assert diagnostic.required_empty is False
    assert diagnostic.required_value is False
    assert diagnostic.action_name == "action<my.domain.com:my_lib:/destroyer>"
    assert_propagation_chain(
        diagnostic,
        {
            "kind": action_contract.PropagationKind.QUALITY_ASSIGNED,
            "enclosing_quality_name": "position<mine>",
            "triggered_quality_name": _CLEANUP,
            "line": 13,
            "column": 28,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.PARTICLE_ORIGIN,
            "enclosing_quality_name": "action</destroyer>::position<holder>",
            "triggered_quality_name": None,
            "line": 16,
            "column": 30,
            "file_path": "test.dfn",
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
            "triggered_quality_name": _CLEANUP,
            "line": 12,
            "column": 33,
            "file_path": "destroyer.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": _CLEANUP,
            "triggered_quality_name": None,
            "line": 7,
            "column": 30,
            "file_path": "cleanup.dfn",
        },
    )


def test_callee_guarantee_over_recorded_state_is_applied_for_destroyed_particle(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    diagnostic = all_diags[0]
    assert isinstance(diagnostic, diagnostics.InferredRequirementViolationDiagnostic)
    assert diagnostic.location.line == 19
    assert diagnostic.location.column == 30
    assert diagnostic.location.end_line == 19
    assert diagnostic.location.end_column == 79
    assert diagnostic.location.file_path == PurePosixPath("test.dfn")
    assert (
        diagnostic.position_name
        == "position<holder>::position</box>::position</marker>::position</needed>"
    )
    assert diagnostic.required_empty is False
    assert diagnostic.required_value is False
    assert diagnostic.action_name == _WRAPPER
    assert_propagation_chain(
        diagnostic,
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _TEST,
            "triggered_quality_name": _WRAPPER,
            "line": 19,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _WRAPPER,
            "triggered_quality_name": _EMPTY_MARKER,
            "line": 7,
            "column": 30,
            "file_path": "wrapper.dfn",
        },
        {
            "kind": action_contract.PropagationKind.QUALITY_ASSIGNED,
            "enclosing_quality_name": "position<my.domain.com:my_lib:/marker>",
            "triggered_quality_name": _RETIRE,
            "line": 3,
            "column": 20,
            "file_path": "marker.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DESTRUCTOR_CASCADE,
            "enclosing_quality_name": _EMPTY_MARKER,
            "triggered_quality_name": _RETIRE,
            "line": 7,
            "column": 33,
            "file_path": "empty_marker.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": _RETIRE,
            "triggered_quality_name": None,
            "line": 7,
            "column": 30,
            "file_path": "retire.dfn",
        },
    )


def test_callee_of_pending_guarantee_empties_recorded_particle_for_destroyed_particle(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    diagnostic = all_diags[0]
    assert isinstance(diagnostic, diagnostics.InferredRequirementViolationDiagnostic)
    assert diagnostic.location.line == 22
    assert diagnostic.location.column == 30
    assert diagnostic.location.end_line == 22
    assert diagnostic.location.end_column == 79
    assert diagnostic.location.file_path == PurePosixPath("test.dfn")
    assert (
        diagnostic.position_name
        == "position<holder>::position</box>::position</inner>::position</marker>::position</needed>"
    )
    assert diagnostic.required_empty is False
    assert diagnostic.required_value is False
    assert diagnostic.action_name == _WRAPPER
    assert_propagation_chain(
        diagnostic,
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _TEST,
            "triggered_quality_name": _WRAPPER,
            "line": 22,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _WRAPPER,
            "triggered_quality_name": "action<my.domain.com:my_lib:/middle>",
            "line": 7,
            "column": 30,
            "file_path": "wrapper.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/middle>",
            "triggered_quality_name": _EMPTY_MARKER,
            "line": 7,
            "column": 30,
            "file_path": "middle.dfn",
        },
        {
            "kind": action_contract.PropagationKind.QUALITY_ASSIGNED,
            "enclosing_quality_name": "position<my.domain.com:my_lib:/marker>",
            "triggered_quality_name": _RETIRE,
            "line": 3,
            "column": 20,
            "file_path": "marker.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DESTRUCTOR_CASCADE,
            "enclosing_quality_name": _EMPTY_MARKER,
            "triggered_quality_name": _RETIRE,
            "line": 7,
            "column": 33,
            "file_path": "empty_marker.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": _RETIRE,
            "triggered_quality_name": None,
            "line": 7,
            "column": 30,
            "file_path": "retire.dfn",
        },
    )


def test_unresolved_quality_does_not_prevent_dropping_for_destroyed_particle(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    diagnostic = all_diags[0]
    assert isinstance(diagnostic, diagnostics.ReferencedFileNotFoundDiagnostic)
    assert diagnostic.location.line == 3
    assert diagnostic.location.column == 27
    assert diagnostic.location.end_line == 3
    assert diagnostic.location.end_column == 35
    assert diagnostic.location.file_path == PurePosixPath("child_2.dfn")
    assert diagnostic.file_path == "missing.dfn"
    assert _destroyed_positions(result) == [
        (_HOLDER, "position<my.domain.com:my_lib:/child_1>"),
        (_HOLDER,),
    ]


def test_caller_resolves_several_pending_callee_guarantees_below_destroyed_particle(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    diagnostic = all_diags[0]
    assert isinstance(diagnostic, diagnostics.InferredRequirementViolationDiagnostic)
    assert diagnostic.location.line == 20
    assert diagnostic.location.column == 30
    assert diagnostic.location.end_line == 20
    assert diagnostic.location.end_column == 63
    assert diagnostic.location.file_path == PurePosixPath("test.dfn")
    assert (
        diagnostic.position_name
        == "action</destroyer>::position<holder>::position</box>::position</child_a>::position</child_2>"
    )
    assert diagnostic.required_empty is False
    assert diagnostic.required_value is False
    assert diagnostic.action_name == "action<my.domain.com:my_lib:/destroyer>"
    assert_propagation_chain(
        diagnostic,
        {
            "kind": action_contract.PropagationKind.QUALITY_ASSIGNED,
            "enclosing_quality_name": "position<mine>",
            "triggered_quality_name": _CLEANUP,
            "line": 13,
            "column": 28,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.PARTICLE_ORIGIN,
            "enclosing_quality_name": "action</destroyer>::position<holder>::position</box>",
            "triggered_quality_name": None,
            "line": 16,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/test>",
            "triggered_quality_name": "action<my.domain.com:my_lib:/destroyer>",
            "line": 20,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DESTRUCTOR_CASCADE,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/destroyer>",
            "triggered_quality_name": _CLEANUP,
            "line": 11,
            "column": 33,
            "file_path": "destroyer.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": _CLEANUP,
            "triggered_quality_name": None,
            "line": 7,
            "column": 30,
            "file_path": "cleanup.dfn",
        },
    )


def test_pending_callee_on_own_particle_creating_failing_destructor_is_applied_for_destroyed_particle(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    diagnostic = all_diags[0]
    assert isinstance(diagnostic, diagnostics.InferredRequirementViolationDiagnostic)
    assert diagnostic.location.line == 16
    assert diagnostic.location.column == 30
    assert diagnostic.location.end_line == 16
    assert diagnostic.location.end_column == 46
    assert diagnostic.location.file_path == PurePosixPath("test.dfn")
    assert (
        diagnostic.position_name
        == "position<holder>::position</q>::position</r>::position</needed>"
    )
    assert diagnostic.required_empty is False
    assert diagnostic.required_value is False
    assert diagnostic.action_name == _CLEANUP
    assert_propagation_chain(
        diagnostic,
        {
            "kind": action_contract.PropagationKind.QUALITY_ASSIGNED,
            "enclosing_quality_name": "position<my.domain.com:my_lib:/r>",
            "triggered_quality_name": _CLEANUP,
            "line": 3,
            "column": 20,
            "file_path": "r.dfn",
        },
        {
            "kind": action_contract.PropagationKind.PARTICLE_ORIGIN,
            "enclosing_quality_name": "position<holder>::position</q>::position</r>",
            "triggered_quality_name": None,
            "line": 8,
            "column": 30,
            "file_path": "builder.dfn",
        },
        {
            "kind": action_contract.PropagationKind.AUTO_DESTRUCTION,
            "enclosing_quality_name": _HOLDER,
            "triggered_quality_name": _TEST,
            "line": 16,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DESTRUCTOR_CASCADE,
            "enclosing_quality_name": _TEST,
            "triggered_quality_name": _CLEANUP,
            "line": 16,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": _CLEANUP,
            "triggered_quality_name": None,
            "line": 7,
            "column": 30,
            "file_path": "cleanup.dfn",
        },
    )


def test_unpublished_destructor_contract_is_skipped_for_destroyed_particle(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph(max_workers=1)
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 2
    untriggered = all_diags[0]
    assert isinstance(untriggered, diagnostics.UntriggeredActionDiagnostic)
    assert untriggered.location.line == 7
    assert untriggered.location.column == 28
    assert untriggered.location.end_line == 7
    assert untriggered.location.end_column == 43
    assert untriggered.location.file_path == PurePosixPath("cleanup.dfn")
    assert untriggered.constraint_name == "action</fill_1>"
    assert untriggered.position_name == "position<dependency>"
    circular = all_diags[1]
    assert isinstance(circular, diagnostics.CircularGlobalReferenceDiagnostic)
    assert circular.location.line == 3
    assert circular.location.column == 20
    assert circular.location.end_line == 3
    assert circular.location.end_column == 36
    assert circular.location.file_path == PurePosixPath("child_2.dfn")
    assert circular.cycle == [
        _CLEANUP,
        "action<my.domain.com:my_lib:/fill_1>",
        "action<my.domain.com:my_lib:/fill_2>",
        "position<my.domain.com:my_lib:/child_2>",
        _CLEANUP,
    ]


def test_callee_particle_whose_destructor_requirements_hold_is_not_expanded_when_destroyed(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert _destroyed_positions(result) == [
        (_HOLDER, "position<my.domain.com:my_lib:/box>"),
        (_HOLDER,),
    ]
    assert action_graph(result.reference_graph_result) == [
        (_CLEANUP, "action<my.domain.com:my_lib:/keep>"),
        (_CLEANUP, "action<my.domain.com:my_lib:/keep>"),
        (_TEST, "action<my.domain.com:my_lib:/make>"),
        (_TEST, _CLEANUP),
    ]


def test_destructor_requirement_inside_what_a_callee_left_holds_without_expanding(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    step = result.reference_graph_result.codegen_input.actions[_TEST].steps[-1]
    assert isinstance(step, codegen_input.Destruction)
    assert step.contribution.work.destructors == []
    (run,) = step.contribution.work.guaranteed_particle_destructors
    assert run.position.canonical_chained_name_tuple == (
        _HOLDER,
        "position<my.domain.com:my_lib:/box>",
        "position<my.domain.com:my_lib:/child>",
    )
    assert run.action.full_typed_name == _BUILD
    assert run.position_in_action == (
        "position<my.domain.com:my_lib:/box>",
        "position<my.domain.com:my_lib:/child>",
    )
    assert _destroyed_positions(result) == [
        (_HOLDER, "position<my.domain.com:my_lib:/box>"),
        (_HOLDER,),
    ]


def test_destructor_value_requirement_inside_what_a_callee_left_fails_when_destroyed(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    (diagnostic,) = result.program_result.all_diagnostics
    assert isinstance(diagnostic, diagnostics.InferredRequirementViolationDiagnostic)
    assert diagnostic.location.line == 13
    assert diagnostic.location.column == 30
    assert diagnostic.location.file_path == PurePosixPath("test.dfn")
    assert (
        diagnostic.position_name
        == "position<holder>::position</box>::position</child>::position</inner>::position</value>"
    )
    assert diagnostic.action_name == _CLEANUP
    assert diagnostic.required_value is True
    assert diagnostic.required_empty is False
    assert_propagation_chain(
        diagnostic,
        {
            "kind": action_contract.PropagationKind.QUALITY_ASSIGNED,
            "enclosing_quality_name": "position<my.domain.com:my_lib:/child>",
            "triggered_quality_name": _CLEANUP,
            "line": 3,
            "column": 20,
            "file_path": "child.dfn",
        },
        {
            "kind": action_contract.PropagationKind.PARTICLE_ORIGIN,
            "enclosing_quality_name": "position<holder>::position</box>::position</child>",
            "triggered_quality_name": None,
            "line": 8,
            "column": 30,
            "file_path": "make.dfn",
        },
        {
            "kind": action_contract.PropagationKind.FILL_SITE,
            "enclosing_quality_name": "position<holder>::position</box>::position</child>::position</inner>::position</value>",
            "triggered_quality_name": None,
            "line": 10,
            "column": 30,
            "file_path": "make.dfn",
        },
        {
            "kind": action_contract.PropagationKind.AUTO_DESTRUCTION,
            "enclosing_quality_name": _HOLDER,
            "triggered_quality_name": _TEST,
            "line": 13,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DESTRUCTOR_CASCADE,
            "enclosing_quality_name": _TEST,
            "triggered_quality_name": _CLEANUP,
            "line": 13,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": _CLEANUP,
            "triggered_quality_name": None,
            "line": 13,
            "column": 78,
            "file_path": "cleanup.dfn",
        },
    )
    step = result.reference_graph_result.codegen_input.actions[_TEST].steps[-1]
    assert isinstance(step, codegen_input.Destruction)
    assert [
        destructor.canonical_chained_name_tuple
        for destructor in step.contribution.work.destructors
    ] == [
        (
            *(
                _HOLDER,
                "position<my.domain.com:my_lib:/box>",
                "position<my.domain.com:my_lib:/child>",
            ),
            _CLEANUP,
        )
    ]
    assert step.contribution.work.guaranteed_particle_destructors == []
    assert _destroyed_positions(result) == [
        (
            _HOLDER,
            "position<my.domain.com:my_lib:/box>",
            "position<my.domain.com:my_lib:/child>",
        ),
        (_HOLDER, "position<my.domain.com:my_lib:/box>"),
        (_HOLDER,),
    ]


def test_destructor_requirement_below_empty_position_a_callee_left_fails_when_destroyed(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    (diagnostic,) = result.program_result.all_diagnostics
    assert isinstance(diagnostic, diagnostics.InferredRequirementViolationDiagnostic)
    assert diagnostic.location.line == 13
    assert diagnostic.location.column == 30
    assert diagnostic.location.file_path == PurePosixPath("test.dfn")
    assert (
        diagnostic.position_name
        == "position<holder>::position</box>::position</child>::position</inner>::position</value>"
    )
    assert diagnostic.action_name == _CLEANUP
    assert diagnostic.required_value is False
    assert diagnostic.required_empty is False
    assert_propagation_chain(
        diagnostic,
        {
            "kind": action_contract.PropagationKind.QUALITY_ASSIGNED,
            "enclosing_quality_name": "position<my.domain.com:my_lib:/child>",
            "triggered_quality_name": _CLEANUP,
            "line": 3,
            "column": 20,
            "file_path": "child.dfn",
        },
        {
            "kind": action_contract.PropagationKind.PARTICLE_ORIGIN,
            "enclosing_quality_name": "position<holder>::position</box>::position</child>",
            "triggered_quality_name": None,
            "line": 8,
            "column": 30,
            "file_path": "make.dfn",
        },
        {
            "kind": action_contract.PropagationKind.AUTO_DESTRUCTION,
            "enclosing_quality_name": _HOLDER,
            "triggered_quality_name": _TEST,
            "line": 13,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DESTRUCTOR_CASCADE,
            "enclosing_quality_name": _TEST,
            "triggered_quality_name": _CLEANUP,
            "line": 13,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": _CLEANUP,
            "triggered_quality_name": None,
            "line": 13,
            "column": 78,
            "file_path": "cleanup.dfn",
        },
    )
    step = result.reference_graph_result.codegen_input.actions[_TEST].steps[-1]
    assert isinstance(step, codegen_input.Destruction)
    assert [
        destructor.canonical_chained_name_tuple
        for destructor in step.contribution.work.destructors
    ] == [
        (
            *(
                _HOLDER,
                "position<my.domain.com:my_lib:/box>",
                "position<my.domain.com:my_lib:/child>",
            ),
            _CLEANUP,
        )
    ]
    assert step.contribution.work.guaranteed_particle_destructors == []
    assert _destroyed_positions(result) == [
        (
            _HOLDER,
            "position<my.domain.com:my_lib:/box>",
            "position<my.domain.com:my_lib:/child>",
        ),
        (_HOLDER, "position<my.domain.com:my_lib:/box>"),
        (_HOLDER,),
    ]


def test_destructor_requirement_on_position_a_callee_never_filled_fails_when_destroyed(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    inner, value = result.program_result.all_diagnostics
    assert isinstance(inner, diagnostics.InferredRequirementViolationDiagnostic)
    assert inner.location.line == 12
    assert inner.location.column == 30
    assert inner.location.file_path == PurePosixPath("test.dfn")
    assert (
        inner.position_name
        == "position<holder>::position</box>::position</child>::position</inner>"
    )
    assert inner.action_name == _CLEANUP
    assert inner.required_value is False
    assert inner.required_empty is False
    assert_propagation_chain(
        inner,
        {
            "kind": action_contract.PropagationKind.QUALITY_ASSIGNED,
            "enclosing_quality_name": "position<my.domain.com:my_lib:/child>",
            "triggered_quality_name": _CLEANUP,
            "line": 3,
            "column": 20,
            "file_path": "child.dfn",
        },
        {
            "kind": action_contract.PropagationKind.PARTICLE_ORIGIN,
            "enclosing_quality_name": "position<holder>::position</box>::position</child>",
            "triggered_quality_name": None,
            "line": 8,
            "column": 30,
            "file_path": "make.dfn",
        },
        {
            "kind": action_contract.PropagationKind.AUTO_DESTRUCTION,
            "enclosing_quality_name": _HOLDER,
            "triggered_quality_name": _TEST,
            "line": 12,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DESTRUCTOR_CASCADE,
            "enclosing_quality_name": _TEST,
            "triggered_quality_name": _CLEANUP,
            "line": 12,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": _CLEANUP,
            "triggered_quality_name": None,
            "line": 13,
            "column": 78,
            "file_path": "cleanup.dfn",
        },
    )
    assert isinstance(value, diagnostics.InferredRequirementViolationDiagnostic)
    assert value.location.line == 12
    assert value.location.column == 30
    assert value.location.file_path == PurePosixPath("test.dfn")
    assert (
        value.position_name
        == "position<holder>::position</box>::position</child>::position</inner>::position</value>"
    )
    assert value.action_name == _CLEANUP
    assert value.required_value is False
    assert value.required_empty is False
    assert_propagation_chain(
        value,
        {
            "kind": action_contract.PropagationKind.QUALITY_ASSIGNED,
            "enclosing_quality_name": "position<my.domain.com:my_lib:/child>",
            "triggered_quality_name": _CLEANUP,
            "line": 3,
            "column": 20,
            "file_path": "child.dfn",
        },
        {
            "kind": action_contract.PropagationKind.PARTICLE_ORIGIN,
            "enclosing_quality_name": "position<holder>::position</box>::position</child>",
            "triggered_quality_name": None,
            "line": 8,
            "column": 30,
            "file_path": "make.dfn",
        },
        {
            "kind": action_contract.PropagationKind.AUTO_DESTRUCTION,
            "enclosing_quality_name": _HOLDER,
            "triggered_quality_name": _TEST,
            "line": 12,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DESTRUCTOR_CASCADE,
            "enclosing_quality_name": _TEST,
            "triggered_quality_name": _CLEANUP,
            "line": 12,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": _CLEANUP,
            "triggered_quality_name": None,
            "line": 13,
            "column": 78,
            "file_path": "cleanup.dfn",
        },
    )
    step = result.reference_graph_result.codegen_input.actions[_TEST].steps[-1]
    assert isinstance(step, codegen_input.Destruction)
    assert [
        destructor.canonical_chained_name_tuple
        for destructor in step.contribution.work.destructors
    ] == [
        (
            *(
                _HOLDER,
                "position<my.domain.com:my_lib:/box>",
                "position<my.domain.com:my_lib:/child>",
            ),
            _CLEANUP,
        )
    ]
    assert step.contribution.work.guaranteed_particle_destructors == []
    assert _destroyed_positions(result) == [
        (
            _HOLDER,
            "position<my.domain.com:my_lib:/box>",
            "position<my.domain.com:my_lib:/child>",
        ),
        (_HOLDER, "position<my.domain.com:my_lib:/box>"),
        (_HOLDER,),
    ]


def test_destructor_requirement_on_position_a_callee_left_in_error_does_not_prevent_running_it(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    (diagnostic,) = result.program_result.all_diagnostics
    assert isinstance(diagnostic, diagnostics.MoveToOccupiedPositionDiagnostic)
    assert diagnostic.location.line == 12
    assert diagnostic.location.column == 49
    assert diagnostic.location.file_path == PurePosixPath("make.dfn")
    assert diagnostic.position_name == "position</child>::position</inner>"
    assert diagnostic.occupied_at.line == 9
    assert diagnostic.occupied_at.column == 30
    assert diagnostic.occupied_at.file_path == PurePosixPath("make.dfn")
    step = result.reference_graph_result.codegen_input.actions[_TEST].steps[-1]
    assert isinstance(step, codegen_input.Destruction)
    assert step.contribution.work.destructors == []
    (run,) = step.contribution.work.guaranteed_particle_destructors
    assert run.position.canonical_chained_name_tuple == (
        _HOLDER,
        "position<my.domain.com:my_lib:/box>",
        "position<my.domain.com:my_lib:/child>",
    )
    assert run.action.full_typed_name == _BUILD
    assert run.position_in_action == (
        "position<my.domain.com:my_lib:/box>",
        "position<my.domain.com:my_lib:/child>",
    )
    assert _destroyed_positions(result) == [
        (_HOLDER, "position<my.domain.com:my_lib:/box>"),
        (_HOLDER,),
    ]


def test_destructor_requirement_on_position_the_caller_emptied_fails_when_destroyed(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    (diagnostic,) = result.program_result.all_diagnostics
    assert isinstance(diagnostic, diagnostics.InferredRequirementViolationDiagnostic)
    assert diagnostic.location.line == 12
    assert diagnostic.location.column == 30
    assert diagnostic.location.file_path == PurePosixPath("test.dfn")
    assert (
        diagnostic.position_name
        == "position<holder>::position</box>::position</child>::position</inner>::position</value>"
    )
    assert diagnostic.action_name == _CLEANUP
    assert diagnostic.required_value is False
    assert diagnostic.required_empty is False
    assert_propagation_chain(
        diagnostic,
        {
            "kind": action_contract.PropagationKind.QUALITY_ASSIGNED,
            "enclosing_quality_name": "position<my.domain.com:my_lib:/child>",
            "triggered_quality_name": _CLEANUP,
            "line": 3,
            "column": 20,
            "file_path": "child.dfn",
        },
        {
            "kind": action_contract.PropagationKind.PARTICLE_ORIGIN,
            "enclosing_quality_name": "position<holder>::position</box>::position</child>",
            "triggered_quality_name": None,
            "line": 8,
            "column": 30,
            "file_path": "make.dfn",
        },
        {
            "kind": action_contract.PropagationKind.AUTO_DESTRUCTION,
            "enclosing_quality_name": _HOLDER,
            "triggered_quality_name": _TEST,
            "line": 12,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DESTRUCTOR_CASCADE,
            "enclosing_quality_name": _TEST,
            "triggered_quality_name": _CLEANUP,
            "line": 12,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": _CLEANUP,
            "triggered_quality_name": None,
            "line": 13,
            "column": 78,
            "file_path": "cleanup.dfn",
        },
    )
    step = result.reference_graph_result.codegen_input.actions[_TEST].steps[-1]
    assert isinstance(step, codegen_input.Destruction)
    assert [
        destructor.canonical_chained_name_tuple
        for destructor in step.contribution.work.destructors
    ] == [
        (
            *(
                _HOLDER,
                "position<my.domain.com:my_lib:/box>",
                "position<my.domain.com:my_lib:/child>",
            ),
            _CLEANUP,
        )
    ]
    assert step.contribution.work.guaranteed_particle_destructors == []
    assert _destroyed_positions(result) == [
        (
            _HOLDER,
            "position<my.domain.com:my_lib:/box>",
            "position<my.domain.com:my_lib:/child>",
        ),
        (_HOLDER, "position<my.domain.com:my_lib:/box>"),
        (_HOLDER,),
    ]


def test_destructor_requirement_on_position_the_caller_left_in_error_does_not_prevent_running_it(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    (diagnostic,) = result.program_result.all_diagnostics
    assert isinstance(diagnostic, diagnostics.MoveToOccupiedPositionDiagnostic)
    assert diagnostic.location.line == 12
    assert diagnostic.location.column == 49
    assert diagnostic.location.file_path == PurePosixPath("build.dfn")
    assert (
        diagnostic.position_name == "position</box>::position</child>::position</inner>"
    )
    assert diagnostic.occupied_at.line == 9
    assert diagnostic.occupied_at.column == 30
    assert diagnostic.occupied_at.file_path == PurePosixPath("make.dfn")
    step = result.reference_graph_result.codegen_input.actions[_TEST].steps[-1]
    assert isinstance(step, codegen_input.Destruction)
    assert step.contribution.work.destructors == []
    (run,) = step.contribution.work.guaranteed_particle_destructors
    assert run.position.canonical_chained_name_tuple == (
        _HOLDER,
        "position<my.domain.com:my_lib:/box>",
        "position<my.domain.com:my_lib:/child>",
    )
    assert run.action.full_typed_name == _BUILD
    assert run.position_in_action == (
        "position<my.domain.com:my_lib:/box>",
        "position<my.domain.com:my_lib:/child>",
    )
    assert _destroyed_positions(result) == [
        (_HOLDER, "position<my.domain.com:my_lib:/box>"),
        (_HOLDER,),
    ]
