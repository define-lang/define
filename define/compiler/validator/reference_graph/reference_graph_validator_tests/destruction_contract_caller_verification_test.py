# pyright: reportUnusedCallResult=false

from pathlib import PurePosixPath

import pytest

from define.compiler import diagnostics
from define.compiler.conftest import ValidateProjectWithReferenceGraph
from define.compiler.validator.reference_graph import action_contract
from define.compiler.validator.reference_graph.reference_graph_validator_tests.test_helpers import (
    assert_propagation_chain,
)
from define.compiler.validator.test_helpers import assert_no_errors

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


@pytest.mark.xfail(
    raises=AssertionError,
    strict=True,
    reason=(
        "lifecycle diagnostics do not yet use the assignment provenance carried"
        " by a particle created in a callee-local position"
    ),
)
def test_destructor_diagnostic_retains_callee_local_assignment(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """The propagation chain includes the callee-local destructor assignment."""
    result = validate_project_with_reference_graph(
        {
            "destructor.dfn": (
                "define the potential action<my.domain.com:my_lib:/destructor> {\n"
                "    define the position<item>.\n"
                "    it happens when {\n"
                "        this particle is being destroyed.\n"
                "    } and it does {\n"
                "        define the position<holder>.\n"
                "        move the particle in position<item> to position<holder>.\n"
                "        move the particle in position<holder> to position<item>.\n"
                "    }\n"
                "}\n"
            ),
            "producer.dfn": (
                "define the potential action<my.domain.com:my_lib:/producer> {\n"
                "    define the position<result> {\n"
                "        it may only contain particles where {\n"
                "            it has the action</destructor>.\n"
                "        }\n"
                "    }\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<created> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</destructor>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<created>.\n"
                "        move the particle in position<created> to position<result>.\n"
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
                "                it has the action</producer>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<box>::action</producer>::position<run>.\n"
                "        destroy the particle in position<box>::action</producer>::position<result>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.InferredRequirementViolationDiagnostic)
    assert [step.kind for step in all_diags[0].propagation_chain] == [
        action_contract.PropagationKind.DESTRUCTOR_ATTACHED,
        action_contract.PropagationKind.PARTICLE_ORIGIN,
        action_contract.PropagationKind.DESTRUCTOR_CASCADE,
        action_contract.PropagationKind.DIRECT_INFERENCE,
    ]
    attachment = all_diags[0].propagation_chain[0]
    assert attachment.location.file_path == PurePosixPath("producer.dfn")
    assert attachment.location.line == 13
    assert attachment.location.column == 24
    assert attachment.enclosing_quality_name == "position<created>"
    assert (
        attachment.triggered_quality_name == "action<my.domain.com:my_lib:/destructor>"
    )


def test_intermediate_verifies_destructor_it_can_resolve(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """Filling the destructor's required-empty position inside mid and then passing the particle to close_file makes mid (not the owner /test) report the violation, attributed to mid's own interface constraint."""
    result = validate_project_with_reference_graph(
        {
            "destructor.dfn": (
                "define the potential action<my.domain.com:my_lib:/destructor> {\n"
                "    define the position<item>.\n"
                "    it happens when {\n"
                "        this particle is being destroyed.\n"
                "    } and it does {\n"
                "        create a particle in position<item>.\n"
                "        destroy the particle in position<item>.\n"
                "    }\n"
                "}\n"
            ),
            "close_file.dfn": (
                "define the potential action<my.domain.com:my_lib:/close_file> {\n"
                "    define the position<target>.\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        destroy the particle in position<target>.\n"
                "    }\n"
                "}\n"
            ),
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
                "        define the position<box> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</close_file>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<incoming>::action</destructor>::position<item>.\n"
                "        move the particle in position<incoming> to position<box>::action</close_file>::position<target>.\n"
                "        create a particle in position<box>::action</close_file>::position<run>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<outer_box> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</mid>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<outer_box>.\n"
                "        create a particle in position<outer_box>::action</mid>::position<incoming>.\n"
                "        create a particle in position<outer_box>::action</mid>::position<run>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.InferredRequirementViolationDiagnostic)
    # The intermediate mid reports the violation, not the owner /test.
    assert all_diags[0].location.line == 19
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("mid.dfn")
    assert all_diags[0].action_name == _CLOSE_FILE
    assert all_diags[0].required_empty is True
    assert (
        all_diags[0].position_name
        == "position<box>::action</close_file>::position<target>::action</destructor>::position<item>"
    )
    # Attribution is mid's own interface constraint, even though /test created
    # the particle.
    assert_propagation_chain(
        all_diags[0],
        {
            "kind": action_contract.PropagationKind.DESTRUCTOR_ATTACHED,
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


def test_transitively_implied_destructor_attributes_to_implying_constraint(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """A destructor reaches the particle only because a constraint requires the carrier action that implies it, so the attachment points at that `it has the action</carrier>` constraint, not the implication clause."""
    result = validate_project_with_reference_graph(
        {
            "file.dfn": "define the potential position<my.domain.com:my_lib:/file>.\n",
            "delete_file_destructor.dfn": (
                "define the potential action<my.domain.com:my_lib:/delete_file_destructor> {\n"
                "    it also assigns the position</file>.\n"
                "    it happens when {\n"
                "        this particle is being destroyed.\n"
                "    } and it does {\n"
                "        define the position<_holder>.\n"
                "        move the particle in position</file> to position<_holder>.\n"
                "        move the particle in position<_holder> to position</file>.\n"
                "    }\n"
                "}\n"
            ),
            "carrier.dfn": (
                "define the potential action<my.domain.com:my_lib:/carrier> {\n"
                "    it also assigns the action</delete_file_destructor>.\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<_unused>.\n"
                "        create a particle in position<_unused>.\n"
                "    }\n"
                "}\n"
            ),
            "close_file.dfn": (
                "define the potential action<my.domain.com:my_lib:/close_file> {\n"
                "    define the position<target>.\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        destroy the particle in position<target>.\n"
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
                "                it has the action</close_file>.\n"
                "            }\n"
                "        }\n"
                "        define the position<my_file> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</carrier>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<my_file>.\n"
                "        create a particle in position<my_file>::action</carrier>::position<run>.\n"
                "        move the particle in position<my_file> to position<box>::action</close_file>::position<target>.\n"
                "        create a particle in position<box>::action</close_file>::position<run>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 2
    assert isinstance(all_diags[0], diagnostics.InferredRequirementViolationDiagnostic)
    assert all_diags[0].location.line == 20
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].action_name == _CLOSE_FILE
    assert all_diags[0].required_empty is False
    assert (
        all_diags[0].position_name
        == "position<box>::action</close_file>::position<target>::position</file>"
    )
    # The attachment points at the directly-declared `it has the action</carrier>`
    # constraint that pulls in the carrier (which implies the destructor), not at
    # the carrier's implication clause.
    assert_propagation_chain(
        all_diags[0],
        {
            "kind": action_contract.PropagationKind.DESTRUCTOR_ATTACHED,
            "enclosing_quality_name": "position<my_file>",
            "triggered_quality_name": _DELETE_FILE_DESTRUCTOR,
            "line": 13,
            "column": 28,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.PARTICLE_ORIGIN,
            "enclosing_quality_name": "position<box>::action</close_file>::position<target>",
            "triggered_quality_name": None,
            "line": 17,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _TEST,
            "triggered_quality_name": _CLOSE_FILE,
            "line": 20,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DESTRUCTOR_CASCADE,
            "enclosing_quality_name": _CLOSE_FILE,
            "triggered_quality_name": _DELETE_FILE_DESTRUCTOR,
            "line": 7,
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
    # Implying a destructor that the carrier never triggers is intrinsically an
    # unused implication; it is incidental to what this test checks.
    # TODO: Decide whether to allow an action to imply a destructor it does not
    # use. A destructor can never be triggered from the implier's own body, so
    # implying one always trips this diagnostic; if we allow it, this assertion
    # goes away and the destructor count above drops to one.
    assert isinstance(all_diags[1], diagnostics.UnusedQualityImplicationDiagnostic)
    assert all_diags[1].location.line == 2
    assert all_diags[1].location.column == 25
    assert all_diags[1].location.file_path == PurePosixPath("carrier.dfn")
    assert all_diags[1].implication_name == "action</delete_file_destructor>"
    assert result.action_call_graph.edges() == [
        (_TEST, _CARRIER),
        (_TEST, _CLOSE_FILE),
        (_CLOSE_FILE, _DELETE_FILE_DESTRUCTOR),
    ]


def test_intermediate_resolves_satisfied_owner_does_not_re_report(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """Filling and then emptying the destructor's required-empty position inside mid means mid knows the position is empty at destruction and resolves the destructor as satisfied; no diagnostic surfaces at mid or the owner /test."""
    result = validate_project_with_reference_graph(
        {
            "destructor.dfn": (
                "define the potential action<my.domain.com:my_lib:/destructor> {\n"
                "    define the position<item>.\n"
                "    it happens when {\n"
                "        this particle is being destroyed.\n"
                "    } and it does {\n"
                "        create a particle in position<item>.\n"
                "        destroy the particle in position<item>.\n"
                "    }\n"
                "}\n"
            ),
            "close_file.dfn": (
                "define the potential action<my.domain.com:my_lib:/close_file> {\n"
                "    define the position<target>.\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        destroy the particle in position<target>.\n"
                "    }\n"
                "}\n"
            ),
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
                "        define the position<box> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</close_file>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<incoming>::action</destructor>::position<item>.\n"
                "        destroy the particle in position<incoming>::action</destructor>::position<item>.\n"
                "        move the particle in position<incoming> to position<box>::action</close_file>::position<target>.\n"
                "        create a particle in position<box>::action</close_file>::position<run>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<outer_box> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</mid>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<outer_box>.\n"
                "        create a particle in position<outer_box>::action</mid>::position<incoming>.\n"
                "        create a particle in position<outer_box>::action</mid>::position<run>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    assert_no_errors(result.program_result)
    assert result.action_call_graph.edges() == [
        (_CLOSE_FILE, _DESTRUCTOR),
        (_MID, _CLOSE_FILE),
        (_TEST, _MID),
    ]


def test_intermediate_resolves_one_destructor_and_carries_another(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """The particle carries two caller-attached destructors; mid fills d1's position so it resolves d1 itself, while d2's position is filled only by the owner, so mid carries d2 up and /test resolves it."""
    result = validate_project_with_reference_graph(
        {
            "d1.dfn": (
                "define the potential action<my.domain.com:my_lib:/d1> {\n"
                "    define the position<item1>.\n"
                "    it happens when {\n"
                "        this particle is being destroyed.\n"
                "    } and it does {\n"
                "        create a particle in position<item1>.\n"
                "        destroy the particle in position<item1>.\n"
                "    }\n"
                "}\n"
            ),
            "d2.dfn": (
                "define the potential action<my.domain.com:my_lib:/d2> {\n"
                "    define the position<item2>.\n"
                "    it happens when {\n"
                "        this particle is being destroyed.\n"
                "    } and it does {\n"
                "        create a particle in position<item2>.\n"
                "        destroy the particle in position<item2>.\n"
                "    }\n"
                "}\n"
            ),
            "close_file.dfn": (
                "define the potential action<my.domain.com:my_lib:/close_file> {\n"
                "    define the position<target>.\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        destroy the particle in position<target>.\n"
                "    }\n"
                "}\n"
            ),
            "mid.dfn": (
                "define the potential action<my.domain.com:my_lib:/mid> {\n"
                "    define the position<incoming> {\n"
                "        it may only contain particles where {\n"
                "            it has the action</d1>.\n"
                "            it has the action</d2>.\n"
                "        }\n"
                "    }\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</close_file>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<incoming>::action</d1>::position<item1>.\n"
                "        move the particle in position<incoming> to position<box>::action</close_file>::position<target>.\n"
                "        create a particle in position<box>::action</close_file>::position<run>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<outer_box> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</mid>.\n"
                "            }\n"
                "        }\n"
                "        define the position<my_file> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</d1>.\n"
                "                it has the action</d2>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<outer_box>.\n"
                "        create a particle in position<my_file>.\n"
                "        create a particle in position<my_file>::action</d2>::position<item2>.\n"
                "        move the particle in position<my_file> to position<outer_box>::action</mid>::position<incoming>.\n"
                "        create a particle in position<outer_box>::action</mid>::position<run>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 2
    # d2 is carried past mid and resolved by the owner /test, attributed to my_file.
    assert isinstance(all_diags[0], diagnostics.InferredRequirementViolationDiagnostic)
    assert all_diags[0].location.line == 21
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
            "kind": action_contract.PropagationKind.DESTRUCTOR_ATTACHED,
            "enclosing_quality_name": "position<my_file>",
            "triggered_quality_name": _D2,
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
            "line": 21,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.FILL_SITE,
            "enclosing_quality_name": "position<outer_box>::action</mid>::position<incoming>::action</d2>::position<item2>",
            "triggered_quality_name": None,
            "line": 19,
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
    # d1 is resolved low, by mid itself, attributed to mid's own interface.
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
            "kind": action_contract.PropagationKind.DESTRUCTOR_ATTACHED,
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


def test_directly_declared_destructor_attribution_wins_over_implication(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """When a constraint both requires the carrier that implies the destructor and directly requires the destructor itself, the attachment points at the direct declaration even though the carrier constraint is listed first."""
    result = validate_project_with_reference_graph(
        {
            "file.dfn": "define the potential position<my.domain.com:my_lib:/file>.\n",
            "delete_file_destructor.dfn": (
                "define the potential action<my.domain.com:my_lib:/delete_file_destructor> {\n"
                "    it also assigns the position</file>.\n"
                "    it happens when {\n"
                "        this particle is being destroyed.\n"
                "    } and it does {\n"
                "        define the position<_holder>.\n"
                "        move the particle in position</file> to position<_holder>.\n"
                "        move the particle in position<_holder> to position</file>.\n"
                "    }\n"
                "}\n"
            ),
            "carrier.dfn": (
                "define the potential action<my.domain.com:my_lib:/carrier> {\n"
                "    it also assigns the action</delete_file_destructor>.\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<_unused>.\n"
                "        create a particle in position<_unused>.\n"
                "    }\n"
                "}\n"
            ),
            "close_file.dfn": (
                "define the potential action<my.domain.com:my_lib:/close_file> {\n"
                "    define the position<target>.\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        destroy the particle in position<target>.\n"
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
                "                it has the action</close_file>.\n"
                "            }\n"
                "        }\n"
                "        define the position<my_file> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</carrier>.\n"
                "                it has the action</delete_file_destructor>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<my_file>.\n"
                "        create a particle in position<my_file>::action</carrier>::position<run>.\n"
                "        move the particle in position<my_file> to position<box>::action</close_file>::position<target>.\n"
                "        create a particle in position<box>::action</close_file>::position<run>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 2
    assert isinstance(all_diags[0], diagnostics.InferredRequirementViolationDiagnostic)
    assert all_diags[0].location.line == 21
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].action_name == _CLOSE_FILE
    assert all_diags[0].required_empty is False
    assert (
        all_diags[0].position_name
        == "position<box>::action</close_file>::position<target>::position</file>"
    )
    # The attachment points at the directly-declared destructor constraint
    # (test.dfn line 15), not the carrier constraint listed before it (line 14).
    assert_propagation_chain(
        all_diags[0],
        {
            "kind": action_contract.PropagationKind.DESTRUCTOR_ATTACHED,
            "enclosing_quality_name": "position<my_file>",
            "triggered_quality_name": _DELETE_FILE_DESTRUCTOR,
            "line": 14,
            "column": 28,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.PARTICLE_ORIGIN,
            "enclosing_quality_name": "position<box>::action</close_file>::position<target>",
            "triggered_quality_name": None,
            "line": 18,
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
            "triggered_quality_name": _DELETE_FILE_DESTRUCTOR,
            "line": 7,
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
    # Implying a destructor the carrier never triggers is intrinsically an unused
    # implication; it is incidental to what this test checks.
    assert isinstance(all_diags[1], diagnostics.UnusedQualityImplicationDiagnostic)
    assert all_diags[1].location.line == 2
    assert all_diags[1].location.column == 25
    assert all_diags[1].location.file_path == PurePosixPath("carrier.dfn")
    assert all_diags[1].implication_name == "action</delete_file_destructor>"
    assert result.action_call_graph.edges() == [
        (_TEST, _CARRIER),
        (_TEST, _CLOSE_FILE),
        (_CLOSE_FILE, _DELETE_FILE_DESTRUCTOR),
    ]


def test_five_level_implied_requirements_resolved_across_actions_satisfied(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """Filling the destructor's occupied-required implied position in outer and emptying its empty-required one in middle lets the destructor be checked once, where every required state is finally known, and pass."""
    result = validate_project_with_reference_graph(
        {
            "p1.dfn": "define the potential position<my.domain.com:my_lib:/p1>.\n",
            "p2.dfn": "define the potential position<my.domain.com:my_lib:/p2>.\n",
            "destructor.dfn": (
                "define the potential action<my.domain.com:my_lib:/destructor> {\n"
                "    it also assigns the position</p1>.\n"
                "    it also assigns the position</p2>.\n"
                "    it happens when {\n"
                "        this particle is being destroyed.\n"
                "    } and it does {\n"
                "        define the position<_holder>.\n"
                "        move the particle in position</p1> to position<_holder>.\n"
                "        move the particle in position<_holder> to position</p1>.\n"
                "        create a particle in position</p2>.\n"
                "        destroy the particle in position</p2>.\n"
                "    }\n"
                "}\n"
            ),
            "close_file.dfn": (
                "define the potential action<my.domain.com:my_lib:/close_file> {\n"
                "    define the position<target>.\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        destroy the particle in position<target>.\n"
                "    }\n"
                "}\n"
            ),
            "middle.dfn": (
                "define the potential action<my.domain.com:my_lib:/middle> {\n"
                "    define the position<incoming> {\n"
                "        it may only contain particles where {\n"
                "            it has the action</destructor>.\n"
                "            it has the position</p2>.\n"
                "        }\n"
                "    }\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</close_file>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<incoming>::position</p2>.\n"
                "        destroy the particle in position<incoming>::position</p2>.\n"
                "        move the particle in position<incoming> to position<box>::action</close_file>::position<target>.\n"
                "        create a particle in position<box>::action</close_file>::position<run>.\n"
                "    }\n"
                "}\n"
            ),
            "outer.dfn": (
                "define the potential action<my.domain.com:my_lib:/outer> {\n"
                "    define the position<incoming> {\n"
                "        it may only contain particles where {\n"
                "            it has the action</destructor>.\n"
                "            it has the position</p1>.\n"
                "        }\n"
                "    }\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</middle>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<incoming>::position</p1>.\n"
                "        move the particle in position<incoming> to position<box>::action</middle>::position<incoming>.\n"
                "        create a particle in position<box>::action</middle>::position<run>.\n"
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
                "                it has the action</outer>.\n"
                "            }\n"
                "        }\n"
                "        define the position<my_file> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</destructor>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<my_file>.\n"
                "        move the particle in position<my_file> to position<box>::action</outer>::position<incoming>.\n"
                "        create a particle in position<box>::action</outer>::position<run>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    assert_no_errors(result.program_result)
    assert result.action_call_graph.edges() == [
        (_MIDDLE, _CLOSE_FILE),
        (_CLOSE_FILE, _DESTRUCTOR),
        (_OUTER, _MIDDLE),
        (_TEST, _OUTER),
    ]


def test_five_level_implied_requirements_resolved_across_actions_violated(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """Making the occupied-required implied position known-empty in outer and filling the empty-required one in middle means neither alone knows both states, so the destructor is checked once at outer and reports both violations there."""
    result = validate_project_with_reference_graph(
        {
            "p1.dfn": "define the potential position<my.domain.com:my_lib:/p1>.\n",
            "p2.dfn": "define the potential position<my.domain.com:my_lib:/p2>.\n",
            "destructor.dfn": (
                "define the potential action<my.domain.com:my_lib:/destructor> {\n"
                "    it also assigns the position</p1>.\n"
                "    it also assigns the position</p2>.\n"
                "    it happens when {\n"
                "        this particle is being destroyed.\n"
                "    } and it does {\n"
                "        define the position<_holder>.\n"
                "        move the particle in position</p1> to position<_holder>.\n"
                "        move the particle in position<_holder> to position</p1>.\n"
                "        create a particle in position</p2>.\n"
                "        destroy the particle in position</p2>.\n"
                "    }\n"
                "}\n"
            ),
            "close_file.dfn": (
                "define the potential action<my.domain.com:my_lib:/close_file> {\n"
                "    define the position<target>.\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        destroy the particle in position<target>.\n"
                "    }\n"
                "}\n"
            ),
            "middle.dfn": (
                "define the potential action<my.domain.com:my_lib:/middle> {\n"
                "    define the position<incoming> {\n"
                "        it may only contain particles where {\n"
                "            it has the action</destructor>.\n"
                "            it has the position</p2>.\n"
                "        }\n"
                "    }\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</close_file>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<incoming>::position</p2>.\n"
                "        move the particle in position<incoming> to position<box>::action</close_file>::position<target>.\n"
                "        create a particle in position<box>::action</close_file>::position<run>.\n"
                "    }\n"
                "}\n"
            ),
            "outer.dfn": (
                "define the potential action<my.domain.com:my_lib:/outer> {\n"
                "    define the position<incoming> {\n"
                "        it may only contain particles where {\n"
                "            it has the action</destructor>.\n"
                "            it has the position</p1>.\n"
                "        }\n"
                "    }\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</middle>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<incoming>::position</p1>.\n"
                "        destroy the particle in position<incoming>::position</p1>.\n"
                "        move the particle in position<incoming> to position<box>::action</middle>::position<incoming>.\n"
                "        create a particle in position<box>::action</middle>::position<run>.\n"
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
                "                it has the action</outer>.\n"
                "            }\n"
                "        }\n"
                "        define the position<my_file> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</destructor>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<my_file>.\n"
                "        move the particle in position<my_file> to position<box>::action</outer>::position<incoming>.\n"
                "        create a particle in position<box>::action</outer>::position<run>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
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
            "kind": action_contract.PropagationKind.DESTRUCTOR_ATTACHED,
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
    # p2 was filled by middle; outer never touched it, so the fill site is the
    # one the contract carried up from middle.
    assert_propagation_chain(
        all_diags[1],
        {
            "kind": action_contract.PropagationKind.DESTRUCTOR_ATTACHED,
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
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """When outer knows the destructor but no required states, while middle (blind to the destructor) fills the occupied-required position and inner (also blind) empties the empty-required one, the destructor is checked once at outer using the contract-carried states and passes."""
    result = validate_project_with_reference_graph(
        {
            "p1.dfn": "define the potential position<my.domain.com:my_lib:/p1>.\n",
            "p2.dfn": "define the potential position<my.domain.com:my_lib:/p2>.\n",
            "destructor.dfn": (
                "define the potential action<my.domain.com:my_lib:/destructor> {\n"
                "    it also assigns the position</p1>.\n"
                "    it also assigns the position</p2>.\n"
                "    it happens when {\n"
                "        this particle is being destroyed.\n"
                "    } and it does {\n"
                "        define the position<_holder>.\n"
                "        move the particle in position</p1> to position<_holder>.\n"
                "        move the particle in position<_holder> to position</p1>.\n"
                "        create a particle in position</p2>.\n"
                "        destroy the particle in position</p2>.\n"
                "    }\n"
                "}\n"
            ),
            "close_file.dfn": (
                "define the potential action<my.domain.com:my_lib:/close_file> {\n"
                "    define the position<target>.\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        destroy the particle in position<target>.\n"
                "    }\n"
                "}\n"
            ),
            "inner.dfn": (
                "define the potential action<my.domain.com:my_lib:/inner> {\n"
                "    define the position<incoming> {\n"
                "        it may only contain particles where {\n"
                "            it has the position</p2>.\n"
                "        }\n"
                "    }\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</close_file>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<incoming>::position</p2>.\n"
                "        destroy the particle in position<incoming>::position</p2>.\n"
                "        move the particle in position<incoming> to position<box>::action</close_file>::position<target>.\n"
                "        create a particle in position<box>::action</close_file>::position<run>.\n"
                "    }\n"
                "}\n"
            ),
            "middle.dfn": (
                "define the potential action<my.domain.com:my_lib:/middle> {\n"
                "    define the position<incoming> {\n"
                "        it may only contain particles where {\n"
                "            it has the position</p1>.\n"
                "            it has the position</p2>.\n"
                "        }\n"
                "    }\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</inner>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<incoming>::position</p1>.\n"
                "        move the particle in position<incoming> to position<box>::action</inner>::position<incoming>.\n"
                "        create a particle in position<box>::action</inner>::position<run>.\n"
                "    }\n"
                "}\n"
            ),
            "outer.dfn": (
                "define the potential action<my.domain.com:my_lib:/outer> {\n"
                "    define the position<incoming> {\n"
                "        it may only contain particles where {\n"
                "            it has the action</destructor>.\n"
                "        }\n"
                "    }\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</middle>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "        move the particle in position<incoming> to position<box>::action</middle>::position<incoming>.\n"
                "        create a particle in position<box>::action</middle>::position<run>.\n"
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
                "                it has the action</outer>.\n"
                "            }\n"
                "        }\n"
                "        define the position<my_file> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</destructor>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<my_file>.\n"
                "        move the particle in position<my_file> to position<box>::action</outer>::position<incoming>.\n"
                "        create a particle in position<box>::action</outer>::position<run>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    assert_no_errors(result.program_result)
    assert result.action_call_graph.edges() == [
        (_INNER, _CLOSE_FILE),
        (_CLOSE_FILE, _DESTRUCTOR),
        (_MIDDLE, _INNER),
        (_OUTER, _MIDDLE),
        (_TEST, _OUTER),
    ]


def test_six_level_destructor_knower_separate_from_resolvers_violated(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """When outer knows the destructor but no required states, while middle (blind) makes the occupied-required position known-empty and inner (blind) fills the empty-required one, outer is the only place every state is known, so it reports both violations there with p2's fill site carried from inner."""
    result = validate_project_with_reference_graph(
        {
            "p1.dfn": "define the potential position<my.domain.com:my_lib:/p1>.\n",
            "p2.dfn": "define the potential position<my.domain.com:my_lib:/p2>.\n",
            "destructor.dfn": (
                "define the potential action<my.domain.com:my_lib:/destructor> {\n"
                "    it also assigns the position</p1>.\n"
                "    it also assigns the position</p2>.\n"
                "    it happens when {\n"
                "        this particle is being destroyed.\n"
                "    } and it does {\n"
                "        define the position<_holder>.\n"
                "        move the particle in position</p1> to position<_holder>.\n"
                "        move the particle in position<_holder> to position</p1>.\n"
                "        create a particle in position</p2>.\n"
                "        destroy the particle in position</p2>.\n"
                "    }\n"
                "}\n"
            ),
            "close_file.dfn": (
                "define the potential action<my.domain.com:my_lib:/close_file> {\n"
                "    define the position<target>.\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        destroy the particle in position<target>.\n"
                "    }\n"
                "}\n"
            ),
            "inner.dfn": (
                "define the potential action<my.domain.com:my_lib:/inner> {\n"
                "    define the position<incoming> {\n"
                "        it may only contain particles where {\n"
                "            it has the position</p2>.\n"
                "        }\n"
                "    }\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</close_file>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<incoming>::position</p2>.\n"
                "        move the particle in position<incoming> to position<box>::action</close_file>::position<target>.\n"
                "        create a particle in position<box>::action</close_file>::position<run>.\n"
                "    }\n"
                "}\n"
            ),
            "middle.dfn": (
                "define the potential action<my.domain.com:my_lib:/middle> {\n"
                "    define the position<incoming> {\n"
                "        it may only contain particles where {\n"
                "            it has the position</p1>.\n"
                "            it has the position</p2>.\n"
                "        }\n"
                "    }\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</inner>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<incoming>::position</p1>.\n"
                "        destroy the particle in position<incoming>::position</p1>.\n"
                "        move the particle in position<incoming> to position<box>::action</inner>::position<incoming>.\n"
                "        create a particle in position<box>::action</inner>::position<run>.\n"
                "    }\n"
                "}\n"
            ),
            "outer.dfn": (
                "define the potential action<my.domain.com:my_lib:/outer> {\n"
                "    define the position<incoming> {\n"
                "        it may only contain particles where {\n"
                "            it has the action</destructor>.\n"
                "        }\n"
                "    }\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</middle>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "        move the particle in position<incoming> to position<box>::action</middle>::position<incoming>.\n"
                "        create a particle in position<box>::action</middle>::position<run>.\n"
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
                "                it has the action</outer>.\n"
                "            }\n"
                "        }\n"
                "        define the position<my_file> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</destructor>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<my_file>.\n"
                "        move the particle in position<my_file> to position<box>::action</outer>::position<incoming>.\n"
                "        create a particle in position<box>::action</outer>::position<run>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
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
            "kind": action_contract.PropagationKind.DESTRUCTOR_ATTACHED,
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
    # inner filled p2; outer never touched it, so the fill site is the one the
    # contract carried up from inner.
    assert_propagation_chain(
        all_diags[1],
        {
            "kind": action_contract.PropagationKind.DESTRUCTOR_ATTACHED,
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
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """When the owner leaves a destructor's required position in an error state (here by moving from it while empty), the destructor cannot be verified and is skipped rather than reported, so only the move-from-empty diagnostic surfaces."""
    result = validate_project_with_reference_graph(
        {
            "x.dfn": "define the potential position<my.domain.com:my_lib:/x>.\n",
            "destructor.dfn": (
                "define the potential action<my.domain.com:my_lib:/destructor> {\n"
                "    it also assigns the position</x>.\n"
                "    it happens when {\n"
                "        this particle is being destroyed.\n"
                "    } and it does {\n"
                "        define the position<_holder>.\n"
                "        move the particle in position</x> to position<_holder>.\n"
                "        move the particle in position<_holder> to position</x>.\n"
                "    }\n"
                "}\n"
            ),
            "close_file.dfn": (
                "define the potential action<my.domain.com:my_lib:/close_file> {\n"
                "    define the position<target> {\n"
                "        it may only contain particles where {\n"
                "            it has the position</x>.\n"
                "        }\n"
                "    }\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        destroy the particle in position<target>.\n"
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
                "                it has the action</close_file>.\n"
                "            }\n"
                "        }\n"
                "        define the position<my_file> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</destructor>.\n"
                "            }\n"
                "        }\n"
                "        define the position<sink>.\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<my_file>.\n"
                "        move the particle in position<my_file> to position<box>::action</close_file>::position<target>.\n"
                "        move the particle in position<box>::action</close_file>::position<target>::position</x> to position<sink>.\n"
                "        create a particle in position<box>::action</close_file>::position<run>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 2
    # The move-from-empty: the destructor's requirement on position</x> is error to
    # the owner, so it is skipped rather than reported as a violation.
    assert isinstance(all_diags[0], diagnostics.MoveFromEmptyPositionDiagnostic)
    assert all_diags[0].location.line == 20
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert (
        all_diags[0].position_name
        == "position<box>::action</close_file>::position<target>::position</x>"
    )
    assert all_diags[0].is_action_interface_position is True
    assert all_diags[0].inferred_at is None
    # close_file declares target's position</x> constraint but its own body never
    # references it; only the caller's move does, which is a different definition,
    # so within close_file the constraint is dead.
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
