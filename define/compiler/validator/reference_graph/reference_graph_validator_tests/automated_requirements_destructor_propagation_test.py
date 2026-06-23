# pyright: reportUnusedCallResult=false
from pathlib import PurePosixPath

from define.compiler import diagnostics
from define.compiler.conftest import ValidateProjectWithReferenceGraph
from define.compiler.validator.reference_graph import action_contract
from define.compiler.validator.reference_graph.reference_graph_validator_tests.test_helpers import (
    assert_propagation_chain,
)
from define.compiler.validator.test_helpers import assert_no_errors

_TEST = "action<my.domain.com:my_lib:/test>"
_MID = "action<my.domain.com:my_lib:/mid>"
_DESTRUCTOR = "action<my.domain.com:my_lib:/destructor>"

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

_DESTRUCTOR_REQUIRES_EMPTY = (
    "define the potential action<my.domain.com:my_lib:/destructor> {\n"
    "    define the position<item>.\n"
    "    it happens when {\n"
    "        this particle is being destroyed.\n"
    "    } and it does {\n"
    "        create a particle in position<item>.\n"
    "        destroy the particle in position<item>.\n"
    "    }\n"
    "}\n"
)

_DESTRUCTOR_REQUIRES_IMPLIED_OCCUPIED = (
    "define the potential action<my.domain.com:my_lib:/destructor> {\n"
    "    it also assigns the position</marker>.\n"
    "    it happens when {\n"
    "        this particle is being destroyed.\n"
    "    } and it does {\n"
    "        define the position<_holder>.\n"
    "        move the particle in position</marker> to position<_holder>.\n"
    "        move the particle in position<_holder> to position</marker>.\n"
    "    }\n"
    "}\n"
)

_DESTRUCTOR_REQUIRES_CHILD_OCCUPIED = (
    "define the potential action<my.domain.com:my_lib:/destructor> {\n"
    "    define the position<holder> {\n"
    "        it may only contain particles where {\n"
    "            it has the position</leaf>.\n"
    "        }\n"
    "    }\n"
    "    it happens when {\n"
    "        this particle is being destroyed.\n"
    "    } and it does {\n"
    "        define the position<_leaf_holder>.\n"
    "        move the particle in position<holder>::position</leaf> to position<_leaf_holder>.\n"
    "        move the particle in position<_leaf_holder> to position<holder>::position</leaf>.\n"
    "    }\n"
    "}\n"
)


def test_interface_occupied_requirement_propagates_and_is_violated_at_caller(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "destructor.dfn": _DESTRUCTOR_REQUIRES_OCCUPIED,
            "mid.dfn": (
                "define the potential action<my.domain.com:my_lib:/mid> {\n"
                "    define the position<incoming> {\n"
                "        it may only contain particles where {\n"
                "            it has the action</destructor>.\n"
                "        }\n"
                "    }\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        destroy the particle in position<incoming>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</mid>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<box>::action</mid>::position<incoming>.\n"
                "        create a particle in position<box>::action</mid>::position<run>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.InferredRequirementViolationDiagnostic)
    assert all_diags[0].location.line == 13
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.end_line == 13
    assert all_diags[0].location.end_column == 72
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].required_empty is False
    assert all_diags[0].runner_description == f"'{_MID}'"
    assert (
        all_diags[0].position_name
        == "position<box>::action</mid>::position<incoming>::action</destructor>::position<item>"
    )
    assert_propagation_chain(
        all_diags[0],
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _TEST,
            "triggered_quality_name": _MID,
            "line": 13,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DESTRUCTOR_ATTACHED,
            "enclosing_quality_name": "position<incoming>",
            "triggered_quality_name": _DESTRUCTOR,
            "line": 4,
            "column": 24,
            "file_path": "mid.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DESTRUCTOR_CASCADE,
            "enclosing_quality_name": _MID,
            "triggered_quality_name": _DESTRUCTOR,
            "line": 11,
            "column": 33,
            "file_path": "mid.dfn",
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
    assert result.action_call_graph.unique_edges() == {
        (_TEST, _MID),
        (_MID, _DESTRUCTOR),
    }


def test_interface_empty_requirement_propagates_and_is_violated_at_caller(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "destructor.dfn": _DESTRUCTOR_REQUIRES_EMPTY,
            "mid.dfn": (
                "define the potential action<my.domain.com:my_lib:/mid> {\n"
                "    define the position<incoming> {\n"
                "        it may only contain particles where {\n"
                "            it has the action</destructor>.\n"
                "        }\n"
                "    }\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        destroy the particle in position<incoming>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</mid>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<box>::action</mid>::position<incoming>.\n"
                "        create a particle in position<box>::action</mid>::position<incoming>::action</destructor>::position<item>.\n"
                "        create a particle in position<box>::action</mid>::position<run>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.InferredRequirementViolationDiagnostic)
    assert all_diags[0].location.line == 14
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.end_line == 14
    assert all_diags[0].location.end_column == 72
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].required_empty is True
    assert all_diags[0].runner_description == f"'{_MID}'"
    assert (
        all_diags[0].position_name
        == "position<box>::action</mid>::position<incoming>::action</destructor>::position<item>"
    )
    assert_propagation_chain(
        all_diags[0],
        {
            "kind": action_contract.PropagationKind.FILL_SITE,
            "enclosing_quality_name": "position<box>::action</mid>::position<incoming>::action</destructor>::position<item>",
            "triggered_quality_name": None,
            "line": 13,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _TEST,
            "triggered_quality_name": _MID,
            "line": 14,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DESTRUCTOR_ATTACHED,
            "enclosing_quality_name": "position<incoming>",
            "triggered_quality_name": _DESTRUCTOR,
            "line": 4,
            "column": 24,
            "file_path": "mid.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DESTRUCTOR_CASCADE,
            "enclosing_quality_name": _MID,
            "triggered_quality_name": _DESTRUCTOR,
            "line": 11,
            "column": 33,
            "file_path": "mid.dfn",
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
    assert result.action_call_graph.unique_edges() == {
        (_TEST, _MID),
        (_MID, _DESTRUCTOR),
    }


def test_implied_requirement_propagates_and_is_violated_at_caller(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "marker.dfn": "define the potential position<my.domain.com:my_lib:/marker>.\n",
            "destructor.dfn": _DESTRUCTOR_REQUIRES_IMPLIED_OCCUPIED,
            "mid.dfn": (
                "define the potential action<my.domain.com:my_lib:/mid> {\n"
                "    define the position<incoming> {\n"
                "        it may only contain particles where {\n"
                "            it has the action</destructor>.\n"
                "        }\n"
                "    }\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        destroy the particle in position<incoming>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</mid>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<box>::action</mid>::position<incoming>.\n"
                "        create a particle in position<box>::action</mid>::position<run>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.InferredRequirementViolationDiagnostic)
    assert all_diags[0].location.line == 13
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.end_line == 13
    assert all_diags[0].location.end_column == 72
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].required_empty is False
    assert all_diags[0].runner_description == f"'{_MID}'"
    assert (
        all_diags[0].position_name
        == "position<box>::action</mid>::position<incoming>::position</marker>"
    )
    assert_propagation_chain(
        all_diags[0],
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _TEST,
            "triggered_quality_name": _MID,
            "line": 13,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DESTRUCTOR_ATTACHED,
            "enclosing_quality_name": "position<incoming>",
            "triggered_quality_name": _DESTRUCTOR,
            "line": 4,
            "column": 24,
            "file_path": "mid.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DESTRUCTOR_CASCADE,
            "enclosing_quality_name": _MID,
            "triggered_quality_name": _DESTRUCTOR,
            "line": 11,
            "column": 33,
            "file_path": "mid.dfn",
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
    assert result.action_call_graph.unique_edges() == {
        (_TEST, _MID),
        (_MID, _DESTRUCTOR),
    }


def test_child_requirement_propagates_and_is_violated_at_caller(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "leaf.dfn": "define the potential position<my.domain.com:my_lib:/leaf>.\n",
            "destructor.dfn": _DESTRUCTOR_REQUIRES_CHILD_OCCUPIED,
            "mid.dfn": (
                "define the potential action<my.domain.com:my_lib:/mid> {\n"
                "    define the position<incoming> {\n"
                "        it may only contain particles where {\n"
                "            it has the action</destructor>.\n"
                "        }\n"
                "    }\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        destroy the particle in position<incoming>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</mid>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<box>::action</mid>::position<incoming>.\n"
                "        create a particle in position<box>::action</mid>::position<incoming>::action</destructor>::position<holder>.\n"
                "        create a particle in position<box>::action</mid>::position<run>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.InferredRequirementViolationDiagnostic)
    assert all_diags[0].location.line == 14
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.end_line == 14
    assert all_diags[0].location.end_column == 72
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].required_empty is False
    assert all_diags[0].runner_description == f"'{_MID}'"
    assert (
        all_diags[0].position_name
        == "position<box>::action</mid>::position<incoming>::action</destructor>::position<holder>::position</leaf>"
    )
    assert_propagation_chain(
        all_diags[0],
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _TEST,
            "triggered_quality_name": _MID,
            "line": 14,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DESTRUCTOR_ATTACHED,
            "enclosing_quality_name": "position<incoming>",
            "triggered_quality_name": _DESTRUCTOR,
            "line": 4,
            "column": 24,
            "file_path": "mid.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DESTRUCTOR_CASCADE,
            "enclosing_quality_name": _MID,
            "triggered_quality_name": _DESTRUCTOR,
            "line": 11,
            "column": 33,
            "file_path": "mid.dfn",
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
    assert result.action_call_graph.unique_edges() == {
        (_TEST, _MID),
        (_MID, _DESTRUCTOR),
    }


def test_requirement_follows_moved_in_particle_to_contracted_origin(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "destructor.dfn": _DESTRUCTOR_REQUIRES_OCCUPIED,
            "mid.dfn": (
                "define the potential action<my.domain.com:my_lib:/mid> {\n"
                "    define the position<incoming> {\n"
                "        it may only contain particles where {\n"
                "            it has the action</destructor>.\n"
                "        }\n"
                "    }\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<local_box>.\n"
                "        move the particle in position<incoming> to position<local_box>.\n"
                "        destroy the particle in position<local_box>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</mid>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<box>::action</mid>::position<incoming>.\n"
                "        create a particle in position<box>::action</mid>::position<run>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.InferredRequirementViolationDiagnostic)
    assert all_diags[0].location.line == 13
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.end_line == 13
    assert all_diags[0].location.end_column == 72
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].required_empty is False
    assert all_diags[0].runner_description == f"'{_MID}'"
    assert (
        all_diags[0].position_name
        == "position<box>::action</mid>::position<incoming>::action</destructor>::position<item>"
    )
    assert_propagation_chain(
        all_diags[0],
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _TEST,
            "triggered_quality_name": _MID,
            "line": 13,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DESTRUCTOR_ATTACHED,
            "enclosing_quality_name": "position<incoming>",
            "triggered_quality_name": _DESTRUCTOR,
            "line": 4,
            "column": 24,
            "file_path": "mid.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DESTRUCTOR_CASCADE,
            "enclosing_quality_name": _MID,
            "triggered_quality_name": _DESTRUCTOR,
            "line": 13,
            "column": 33,
            "file_path": "mid.dfn",
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
    assert result.action_call_graph.unique_edges() == {
        (_TEST, _MID),
        (_MID, _DESTRUCTOR),
    }


def test_propagated_requirement_satisfied_at_caller_produces_no_error(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "destructor.dfn": _DESTRUCTOR_REQUIRES_OCCUPIED,
            "mid.dfn": (
                "define the potential action<my.domain.com:my_lib:/mid> {\n"
                "    define the position<incoming> {\n"
                "        it may only contain particles where {\n"
                "            it has the action</destructor>.\n"
                "        }\n"
                "    }\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        destroy the particle in position<incoming>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</mid>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<box>::action</mid>::position<incoming>.\n"
                "        create a particle in position<box>::action</mid>::position<incoming>::action</destructor>::position<item>.\n"
                "        create a particle in position<box>::action</mid>::position<run>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    assert_no_errors(result.program_result)
    assert result.action_call_graph.unique_edges() == {
        (_TEST, _MID),
        (_MID, _DESTRUCTOR),
    }
