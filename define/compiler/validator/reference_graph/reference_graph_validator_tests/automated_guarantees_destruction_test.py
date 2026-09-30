from __future__ import annotations

import typing
from pathlib import PurePosixPath

from define.compiler.errors import diagnostics
from define.compiler.validator import codegen_input
from define.compiler.validator.reference_graph import action_contract
from define.compiler.validator.reference_graph.reference_graph_validator_tests.test_helpers import (
    assert_propagation_chain,
)
from define.compiler.validator.test_helpers import assert_no_errors

if typing.TYPE_CHECKING:
    from define.compiler import conftest

_HOLDER = "position<holder>"
_CHILD_1 = "position<my.domain.com:my_lib:/child_1>"
_CHILD_2 = "position<my.domain.com:my_lib:/child_2>"
_CLEANUP = "action<my.domain.com:my_lib:/cleanup>"


def _destruction(
    result: conftest.FullValidationResult, action_name: str, index: int
) -> codegen_input.Destruction:
    steps = result.reference_graph_result.codegen_input.actions[action_name].steps
    step = steps[index]
    assert isinstance(step, codegen_input.Destruction)
    return step


def _positions(destruction: codegen_input.Destruction) -> list[tuple[str, ...]]:
    return [position.canonical_chained_name_tuple for position in destruction.positions]


def _destructors(destruction: codegen_input.Destruction) -> list[tuple[str, ...]]:
    return [
        destructor.canonical_chained_name_tuple
        for destructor in destruction.destructors
    ]


def test_discardable_callee_guarantees_are_dropped_for_destroyed_particle(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    automatic = _destruction(result, "action<my.domain.com:my_lib:/test>", -1)
    assert _positions(automatic) == [(_HOLDER, _CHILD_1), (_HOLDER,)]
    assert _destructors(automatic) == []
    assert automatic.contract_destructions == []


def test_callee_guarantees_creating_destructor_are_applied_for_destroyed_particle(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    automatic = _destruction(result, "action<my.domain.com:my_lib:/test>", -1)
    assert _positions(automatic) == [
        (_HOLDER, _CHILD_1, _CHILD_2),
        (_HOLDER, _CHILD_1),
        (_HOLDER,),
    ]
    assert _destructors(automatic) == [
        (_HOLDER, _CHILD_1, _CHILD_2, "action<my.domain.com:my_lib:/cleanup>")
    ]
    assert automatic.contract_destructions == []


def test_callee_guarantees_below_caller_particle_are_applied_for_destroyed_particle(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    holder_destruction = _destruction(
        result, "action<my.domain.com:my_lib:/destroyer>", -3
    )
    assert _positions(holder_destruction) == [
        (_HOLDER, _CHILD_1, _CHILD_2),
        (_HOLDER, _CHILD_1),
        (_HOLDER,),
    ]
    assert _destructors(holder_destruction) == []
    (propagated,) = holder_destruction.contract_destructions
    assert propagated.contracted_position.canonical_chained_name_tuple == (_HOLDER,)


def test_callee_guarantee_over_recorded_state_is_applied_for_destroyed_particle(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    automatic = _destruction(result, "action<my.domain.com:my_lib:/test>", -1)
    assert _positions(automatic) == [
        (_HOLDER, "position<my.domain.com:my_lib:/box>"),
        (_HOLDER,),
    ]
    assert _destructors(automatic) == []
    assert automatic.contract_destructions == []


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
    automatic = _destruction(result, "action<my.domain.com:my_lib:/test>", -1)
    assert _positions(automatic) == [(_HOLDER, _CHILD_1), (_HOLDER,)]
    assert _destructors(automatic) == []
    assert automatic.contract_destructions == []


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
    assert diagnostic.required_empty is True
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
            "kind": action_contract.PropagationKind.FILL_SITE,
            "enclosing_quality_name": "action</destroyer>::position<holder>::position</box>::position</child_a>::position</child_2>",
            "triggered_quality_name": None,
            "line": 8,
            "column": 30,
            "file_path": "fill_2.dfn",
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
            "line": 6,
            "column": 30,
            "file_path": "cleanup.dfn",
        },
    )
