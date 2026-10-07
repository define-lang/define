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
_DESTRUCTOR = "action<my.domain.com:my_lib:/destructor>"
_DESTRUCTOR_EMPTY = "action<my.domain.com:my_lib:/destructor_empty>"
_NESTED_DESTRUCTOR = "action<my.domain.com:my_lib:/nested_destructor>"
_MAKE_THING = "action<my.domain.com:my_lib:/make_thing>"
_DESTROY_CARRIER = "action<my.domain.com:my_lib:/destroy_carrier>"
_P = "action<my.domain.com:my_lib:/p>"
_FIRST_DESTRUCTOR = "action<my.domain.com:my_lib:/first_destructor>"
_SECOND_DESTRUCTOR = "action<my.domain.com:my_lib:/second_destructor>"

# Moves its own interface position's particle out and back, so it requires
# that position to be occupied while leaving it unchanged (no guarantee).
_DESTRUCTOR_REQUIRES_OCCUPIED = (
    "define the potential action<my.domain.com:my_lib:/destructor> {\n"
    "    define the position<item>.\n"
    "    it happens when {\n"
    "        this particle is being destroyed.\n"
    "    } and it does {\n"
    "        define the position<_holder>.\n"
    "        move the particle in position<item> to position<_holder>.\n"
    "        move the particle in position<_holder> to position<item>.\n"
    "    }\n"
    "}\n"
)


def test_occupied_interface_requirement_satisfied(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert action_graph(result.reference_graph_result) == [(_TEST, _DESTRUCTOR)]


def test_occupied_interface_requirement_violated(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.InferredRequirementViolationDiagnostic)
    assert all_diags[0].required_value is False
    assert all_diags[0].location.line == 11
    assert all_diags[0].location.column == 33
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].required_empty is False
    assert all_diags[0].action_name == _DESTRUCTOR
    assert (
        all_diags[0].position_name
        == "position<box>::action</destructor>::position<item>"
    )
    assert_propagation_chain(
        all_diags[0],
        {
            "kind": action_contract.PropagationKind.QUALITY_ASSIGNED,
            "enclosing_quality_name": "position<box>",
            "triggered_quality_name": _DESTRUCTOR,
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
            "kind": action_contract.PropagationKind.DESTRUCTOR_CASCADE,
            "enclosing_quality_name": _TEST,
            "triggered_quality_name": _DESTRUCTOR,
            "line": 11,
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
    assert action_graph(result.reference_graph_result) == [(_TEST, _DESTRUCTOR)]


def test_destructor_requiring_empty_interface_position_is_reported(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(
        all_diags[0], diagnostics.DestructorRequiresEmptyPositionDiagnostic
    )
    assert all_diags[0].location.line == 6
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("destructor_empty.dfn")
    assert all_diags[0].position_name == "position<item>"
    assert action_graph(result.reference_graph_result) == [(_TEST, _DESTRUCTOR_EMPTY)]


def test_intermediate_position_requirement_violated(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.InferredRequirementViolationDiagnostic)
    assert all_diags[0].required_value is False
    assert all_diags[0].location.line == 12
    assert all_diags[0].location.column == 33
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].required_empty is False
    assert all_diags[0].action_name == _NESTED_DESTRUCTOR
    assert (
        all_diags[0].position_name
        == "position<box>::action</nested_destructor>::position<holder>::position</leaf>"
    )
    assert_propagation_chain(
        all_diags[0],
        {
            "kind": action_contract.PropagationKind.QUALITY_ASSIGNED,
            "enclosing_quality_name": "position<box>",
            "triggered_quality_name": _NESTED_DESTRUCTOR,
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
            "kind": action_contract.PropagationKind.DESTRUCTOR_CASCADE,
            "enclosing_quality_name": _TEST,
            "triggered_quality_name": _NESTED_DESTRUCTOR,
            "line": 12,
            "column": 33,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": _NESTED_DESTRUCTOR,
            "triggered_quality_name": None,
            "line": 11,
            "column": 30,
            "file_path": "nested_destructor.dfn",
        },
    )
    assert action_graph(result.reference_graph_result) == [(_TEST, _NESTED_DESTRUCTOR)]


def test_locally_created_interface_particle_fires_destructor_locally(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph(
        allow_entry_action_interface_positions=True
    )
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.InferredRequirementViolationDiagnostic)
    assert all_diags[0].required_value is False
    assert all_diags[0].location.line == 14
    assert all_diags[0].location.column == 33
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].required_empty is False
    assert all_diags[0].action_name == _DESTRUCTOR
    assert (
        all_diags[0].position_name
        == "position<iface>::action</destructor>::position<item>"
    )
    assert_propagation_chain(
        all_diags[0],
        {
            "kind": action_contract.PropagationKind.QUALITY_ASSIGNED,
            "enclosing_quality_name": "position<iface>",
            "triggered_quality_name": _DESTRUCTOR,
            "line": 7,
            "column": 24,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.PARTICLE_ORIGIN,
            "enclosing_quality_name": "position<iface>",
            "triggered_quality_name": None,
            "line": 13,
            "column": 30,
            "file_path": "test.dfn",
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
    assert action_graph(result.reference_graph_result) == [(_TEST, _DESTRUCTOR)]


def test_locally_created_destructor_parent_propagates_requirement_from_moved_child(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    diag = all_diags[0]
    assert isinstance(diag, diagnostics.InferredRequirementViolationDiagnostic)
    assert diag.required_value is False
    assert diag.location.line == 15
    assert diag.location.column == 30
    assert diag.location.file_path == PurePosixPath("test.dfn")
    assert diag.required_empty is False
    assert diag.action_name == _DESTROY_CARRIER
    assert diag.position_name == (
        "position<box>::action</destroy_carrier>::position<incoming>::position</child>"
    )
    assert_propagation_chain(
        diag,
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _TEST,
            "triggered_quality_name": _DESTROY_CARRIER,
            "line": 15,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.QUALITY_ASSIGNED,
            "enclosing_quality_name": "position<carrier>",
            "triggered_quality_name": _DESTRUCTOR,
            "line": 13,
            "column": 28,
            "file_path": "destroy_carrier.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DESTRUCTOR_CASCADE,
            "enclosing_quality_name": _DESTROY_CARRIER,
            "triggered_quality_name": _DESTRUCTOR,
            "line": 18,
            "column": 33,
            "file_path": "destroy_carrier.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": _DESTRUCTOR,
            "triggered_quality_name": None,
            "line": 11,
            "column": 30,
            "file_path": "destructor.dfn",
        },
    )
    assert action_graph(result.reference_graph_result) == [
        (_DESTROY_CARRIER, _DESTRUCTOR),
        (_TEST, _DESTROY_CARRIER),
    ]


def test_destructor_in_constructor_checks_interface_requirement_locally(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.InferredRequirementViolationDiagnostic)
    assert all_diags[0].required_value is False
    assert all_diags[0].location.line == 7
    assert all_diags[0].location.column == 33
    assert all_diags[0].location.file_path == PurePosixPath("p.dfn")
    assert all_diags[0].required_empty is False
    assert all_diags[0].action_name == _DESTRUCTOR
    assert (
        all_diags[0].position_name
        == "position</carrier>::action</destructor>::position<item>"
    )
    assert_propagation_chain(
        all_diags[0],
        {
            "kind": action_contract.PropagationKind.QUALITY_ASSIGNED,
            "enclosing_quality_name": "position<my.domain.com:my_lib:/carrier>",
            "triggered_quality_name": _DESTRUCTOR,
            "line": 3,
            "column": 20,
            "file_path": "carrier.dfn",
        },
        {
            "kind": action_contract.PropagationKind.PARTICLE_ORIGIN,
            "enclosing_quality_name": "position</carrier>",
            "triggered_quality_name": None,
            "line": 6,
            "column": 30,
            "file_path": "p.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DESTRUCTOR_CASCADE,
            "enclosing_quality_name": _P,
            "triggered_quality_name": _DESTRUCTOR,
            "line": 7,
            "column": 33,
            "file_path": "p.dfn",
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
        (_P, _DESTRUCTOR),
        (_TEST, _P),
    ]


def test_callee_attached_destructor_requirement_validated_at_owning_caller(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.InferredRequirementViolationDiagnostic)
    assert all_diags[0].required_value is False
    assert all_diags[0].location.line == 16
    assert all_diags[0].location.column == 33
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].required_empty is False
    assert all_diags[0].action_name == _DESTRUCTOR
    assert (
        all_diags[0].position_name
        == "position<box>::action</make_thing>::position<result>::action</destructor>::position<item>"
    )
    assert_propagation_chain(
        all_diags[0],
        {
            "kind": action_contract.PropagationKind.QUALITY_ASSIGNED,
            "enclosing_quality_name": "position<temp>",
            "triggered_quality_name": "action<my.domain.com:my_lib:/destructor>",
            "line": 9,
            "column": 28,
            "file_path": "make_thing.dfn",
        },
        {
            "kind": action_contract.PropagationKind.PARTICLE_ORIGIN,
            "enclosing_quality_name": "position<box>::action</make_thing>::position<result>",
            "triggered_quality_name": None,
            "line": 12,
            "column": 30,
            "file_path": "make_thing.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DESTRUCTOR_CASCADE,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/test>",
            "triggered_quality_name": "action<my.domain.com:my_lib:/destructor>",
            "line": 16,
            "column": 33,
            "file_path": "test.dfn",
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
        (_TEST, _MAKE_THING),
        (_TEST, _DESTRUCTOR),
    ]


def test_destructor_requirement_checked_when_another_destructor_changes_contracted_position(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 3

    first_violation = all_diags[0]
    assert isinstance(
        first_violation, diagnostics.InferredRequirementViolationDiagnostic
    )
    assert first_violation.location.line == 13
    assert first_violation.location.column == 33
    assert first_violation.location.file_path == PurePosixPath("test.dfn")
    assert first_violation.position_name == "position<thing>::position</p>"
    assert first_violation.action_name == _FIRST_DESTRUCTOR
    assert first_violation.required_empty is False
    assert first_violation.required_value is False
    assert_propagation_chain(
        first_violation,
        {
            "kind": action_contract.PropagationKind.QUALITY_ASSIGNED,
            "enclosing_quality_name": "position<thing>",
            "triggered_quality_name": _FIRST_DESTRUCTOR,
            "line": 8,
            "column": 28,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.PARTICLE_ORIGIN,
            "enclosing_quality_name": "position<thing>",
            "triggered_quality_name": None,
            "line": 12,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DESTRUCTOR_CASCADE,
            "enclosing_quality_name": _TEST,
            "triggered_quality_name": _FIRST_DESTRUCTOR,
            "line": 13,
            "column": 33,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": _FIRST_DESTRUCTOR,
            "triggered_quality_name": None,
            "line": 7,
            "column": 30,
            "file_path": "first_destructor.dfn",
        },
    )

    second_violation = all_diags[1]
    assert isinstance(
        second_violation, diagnostics.InferredRequirementViolationDiagnostic
    )
    assert second_violation.location.line == 13
    assert second_violation.location.column == 33
    assert second_violation.location.file_path == PurePosixPath("test.dfn")
    assert second_violation.position_name == "position<thing>::position</p>"
    assert second_violation.action_name == _SECOND_DESTRUCTOR
    assert second_violation.required_empty is False
    assert second_violation.required_value is False
    assert_propagation_chain(
        second_violation,
        {
            "kind": action_contract.PropagationKind.QUALITY_ASSIGNED,
            "enclosing_quality_name": "position<thing>",
            "triggered_quality_name": _SECOND_DESTRUCTOR,
            "line": 9,
            "column": 28,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.PARTICLE_ORIGIN,
            "enclosing_quality_name": "position<thing>",
            "triggered_quality_name": None,
            "line": 12,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DESTRUCTOR_CASCADE,
            "enclosing_quality_name": _TEST,
            "triggered_quality_name": _SECOND_DESTRUCTOR,
            "line": 13,
            "column": 33,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": _SECOND_DESTRUCTOR,
            "triggered_quality_name": None,
            "line": 7,
            "column": 30,
            "file_path": "second_destructor.dfn",
        },
    )

    emptied_p = all_diags[2]
    assert isinstance(emptied_p, diagnostics.DestructorProducesEmptyGuaranteeDiagnostic)
    assert emptied_p.location.line == 7
    assert emptied_p.location.column == 30
    assert emptied_p.location.file_path == PurePosixPath("first_destructor.dfn")
    assert emptied_p.position_name == "position</p>"
