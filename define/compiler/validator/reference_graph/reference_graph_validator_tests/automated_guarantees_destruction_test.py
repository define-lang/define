from __future__ import annotations

import typing
from pathlib import PurePosixPath

from define.compiler import ast
from define.compiler.errors import diagnostics
from define.compiler.validator import codegen_input
from define.compiler.validator.test_helpers import assert_no_errors

if typing.TYPE_CHECKING:
    from define.compiler import conftest

_HOLDER = "position<holder>"
_CHILD_1 = "position<my.domain.com:my_lib:/child_1>"
_CHILD_2 = "position<my.domain.com:my_lib:/child_2>"


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
    assert result.program_result.all_diagnostics == [
        diagnostics.ReferencedFileNotFoundDiagnostic(
            location=ast.SourceLocation(
                line=3,
                column=27,
                end_line=3,
                end_column=35,
                file_path=PurePosixPath("child_2.dfn"),
            ),
            file_path="missing.dfn",
        )
    ]
    automatic = _destruction(result, "action<my.domain.com:my_lib:/test>", -1)
    assert _positions(automatic) == [(_HOLDER, _CHILD_1), (_HOLDER,)]
    assert _destructors(automatic) == []
    assert automatic.contract_destructions == []
