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
_POS_TEST = "position<my.domain.com:my_lib:/test>"
_CLOSE_FILE = "action<my.domain.com:my_lib:/close_file>"
_DELETE_FILE1 = "action<my.domain.com:my_lib:/delete_file1>"
_DELETE_FILE2 = "action<my.domain.com:my_lib:/delete_file2>"
_DELETE_FILE_DESTRUCTOR = "action<my.domain.com:my_lib:/delete_file_destructor>"
_DELETE_EMPTY_DESTRUCTOR = "action<my.domain.com:my_lib:/delete_empty_destructor>"
_DESTRUCTOR = "action<my.domain.com:my_lib:/destructor>"
_DESTRUCTOR_A = "action<my.domain.com:my_lib:/destructor_a>"
_DESTRUCTOR_B = "action<my.domain.com:my_lib:/destructor_b>"
_DESTRUCTOR_C = "action<my.domain.com:my_lib:/destructor_c>"


def test_caller_known_child_state_requirement_satisfied(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """Verifying a caller-attached destructor close_file cannot see passes when /test filled the destructor's required position</file>."""
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
            "close_file.dfn": (
                "define the potential action<my.domain.com:my_lib:/close_file> {\n"
                "    define the position<target> {\n"
                "        it may only contain particles where {\n"
                "            it has the position</file>.\n"
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
                "                it has the position</file>.\n"
                "                it has the action</delete_file_destructor>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<my_file>.\n"
                "        create a particle in position<my_file>::position</file>.\n"
                "        move the particle in position<my_file> to position<box>::action</close_file>::position<target>.\n"
                "        create a particle in position<box>::action</close_file>::position<run>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    assert_no_errors(result.program_result)
    assert result.action_call_graph.edges() == [
        (_CLOSE_FILE, _DELETE_FILE_DESTRUCTOR),
        (_TEST, _CLOSE_FILE),
    ]


def test_caller_known_child_state_requirement_violated(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """Verifying a caller-attached destructor close_file cannot see fails when /test left the destructor's required position</file> empty."""
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
            "close_file.dfn": (
                "define the potential action<my.domain.com:my_lib:/close_file> {\n"
                "    define the position<target> {\n"
                "        it may only contain particles where {\n"
                "            it has the position</file>.\n"
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
                "                it has the position</file>.\n"
                "                it has the action</delete_file_destructor>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<my_file>.\n"
                "        move the particle in position<my_file> to position<box>::action</close_file>::position<target>.\n"
                "        create a particle in position<box>::action</close_file>::position<run>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.InferredRequirementViolationDiagnostic)
    # The violation is observed at the line that triggered close_file.
    assert all_diags[0].location.line == 20
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].required_empty is False
    assert all_diags[0].runner_description == f"'{_CLOSE_FILE}'"
    assert (
        all_diags[0].position_name
        == "position<box>::action</close_file>::position<target>::position</file>"
    )
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
            "line": 20,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DESTRUCTOR_CASCADE,
            "enclosing_quality_name": _CLOSE_FILE,
            "triggered_quality_name": _DELETE_FILE_DESTRUCTOR,
            "line": 11,
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


def test_caller_known_empty_requirement_satisfied(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """A caller-attached must-be-empty destructor close_file cannot see passes when /test leaves the destructor's required position</file> empty."""
    result = validate_project_with_reference_graph(
        {
            "file.dfn": "define the potential position<my.domain.com:my_lib:/file>.\n",
            "delete_empty_destructor.dfn": (
                "define the potential action<my.domain.com:my_lib:/delete_empty_destructor> {\n"
                "    it also assigns the position</file>.\n"
                "    it happens when {\n"
                "        this particle is being destroyed.\n"
                "    } and it does {\n"
                "        create a particle in position</file>.\n"
                "        destroy the particle in position</file>.\n"
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
                "                it has the action</delete_empty_destructor>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<my_file>.\n"
                "        move the particle in position<my_file> to position<box>::action</close_file>::position<target>.\n"
                "        create a particle in position<box>::action</close_file>::position<run>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    assert_no_errors(result.program_result)
    assert result.action_call_graph.edges() == [
        (_CLOSE_FILE, _DELETE_EMPTY_DESTRUCTOR),
        (_TEST, _CLOSE_FILE),
    ]


def test_caller_known_empty_requirement_violated(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """A caller-attached must-be-empty destructor close_file cannot see fails when /test fills the destructor's required position</file>."""
    result = validate_project_with_reference_graph(
        {
            "file.dfn": "define the potential position<my.domain.com:my_lib:/file>.\n",
            "delete_empty_destructor.dfn": (
                "define the potential action<my.domain.com:my_lib:/delete_empty_destructor> {\n"
                "    it also assigns the position</file>.\n"
                "    it happens when {\n"
                "        this particle is being destroyed.\n"
                "    } and it does {\n"
                "        create a particle in position</file>.\n"
                "        destroy the particle in position</file>.\n"
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
                "                it has the action</delete_empty_destructor>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<my_file>.\n"
                "        create a particle in position<my_file>::position</file>.\n"
                "        move the particle in position<my_file> to position<box>::action</close_file>::position<target>.\n"
                "        create a particle in position<box>::action</close_file>::position<run>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.InferredRequirementViolationDiagnostic)
    assert all_diags[0].location.line == 20
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].required_empty is True
    assert all_diags[0].runner_description == f"'{_CLOSE_FILE}'"
    assert (
        all_diags[0].position_name
        == "position<box>::action</close_file>::position<target>::position</file>"
    )
    assert_propagation_chain(
        all_diags[0],
        {
            "kind": action_contract.PropagationKind.DESTRUCTOR_ATTACHED,
            "enclosing_quality_name": "position<my_file>",
            "triggered_quality_name": _DELETE_EMPTY_DESTRUCTOR,
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
            "kind": action_contract.PropagationKind.FILL_SITE,
            "enclosing_quality_name": "position<box>::action</close_file>::position<target>::position</file>",
            "triggered_quality_name": None,
            "line": 18,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DESTRUCTOR_CASCADE,
            "enclosing_quality_name": _CLOSE_FILE,
            "triggered_quality_name": _DELETE_EMPTY_DESTRUCTOR,
            "line": 7,
            "column": 33,
            "file_path": "close_file.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": _DELETE_EMPTY_DESTRUCTOR,
            "triggered_quality_name": None,
            "line": 6,
            "column": 30,
            "file_path": "delete_empty_destructor.dfn",
        },
    )
    assert result.action_call_graph.edges() == [
        (_CLOSE_FILE, _DELETE_EMPTY_DESTRUCTOR),
        (_TEST, _CLOSE_FILE),
    ]


def test_two_caller_attached_destructors_verified_independently(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """Of two caller-attached destructors on one destroyed particle, only the one whose required position is empty produces a diagnostic; each is verified on its own."""
    result = validate_project_with_reference_graph(
        {
            "a.dfn": "define the potential position<my.domain.com:my_lib:/a>.\n",
            "b.dfn": "define the potential position<my.domain.com:my_lib:/b>.\n",
            "destructor_a.dfn": (
                "define the potential action<my.domain.com:my_lib:/destructor_a> {\n"
                "    it also assigns the position</a>.\n"
                "    it happens when {\n"
                "        this particle is being destroyed.\n"
                "    } and it does {\n"
                "        define the position<_holder>.\n"
                "        move the particle in position</a> to position<_holder>.\n"
                "        move the particle in position<_holder> to position</a>.\n"
                "    }\n"
                "}\n"
            ),
            "destructor_b.dfn": (
                "define the potential action<my.domain.com:my_lib:/destructor_b> {\n"
                "    it also assigns the position</b>.\n"
                "    it happens when {\n"
                "        this particle is being destroyed.\n"
                "    } and it does {\n"
                "        define the position<_holder>.\n"
                "        move the particle in position</b> to position<_holder>.\n"
                "        move the particle in position<_holder> to position</b>.\n"
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
                "                it has the action</destructor_a>.\n"
                "                it has the action</destructor_b>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<my_file>.\n"
                "        create a particle in position<my_file>::position</a>.\n"
                "        move the particle in position<my_file> to position<box>::action</close_file>::position<target>.\n"
                "        create a particle in position<box>::action</close_file>::position<run>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.InferredRequirementViolationDiagnostic)
    # destructor_a's position</a> was filled (line 19); only destructor_b fails.
    # The violation is observed at the line that triggered close_file (line 21).
    assert all_diags[0].location.line == 21
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].required_empty is False
    assert all_diags[0].runner_description == f"'{_CLOSE_FILE}'"
    assert (
        all_diags[0].position_name
        == "position<box>::action</close_file>::position<target>::position</b>"
    )
    assert_propagation_chain(
        all_diags[0],
        {
            "kind": action_contract.PropagationKind.DESTRUCTOR_ATTACHED,
            "enclosing_quality_name": "position<my_file>",
            "triggered_quality_name": _DESTRUCTOR_B,
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
            "triggered_quality_name": _DESTRUCTOR_B,
            "line": 7,
            "column": 33,
            "file_path": "close_file.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": _DESTRUCTOR_B,
            "triggered_quality_name": None,
            "line": 7,
            "column": 30,
            "file_path": "destructor_b.dfn",
        },
    )
    # Both destructors fire (and so get edges); only destructor_b is violated.
    assert result.action_call_graph.edges() == [
        (_CLOSE_FILE, _DESTRUCTOR_B),
        (_CLOSE_FILE, _DESTRUCTOR_A),
        (_TEST, _CLOSE_FILE),
    ]


def test_all_caller_attached_destructors_satisfied(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """When every caller-attached destructor's required position is filled, none of them produces a diagnostic."""
    result = validate_project_with_reference_graph(
        {
            "a.dfn": "define the potential position<my.domain.com:my_lib:/a>.\n",
            "b.dfn": "define the potential position<my.domain.com:my_lib:/b>.\n",
            "destructor_a.dfn": (
                "define the potential action<my.domain.com:my_lib:/destructor_a> {\n"
                "    it also assigns the position</a>.\n"
                "    it happens when {\n"
                "        this particle is being destroyed.\n"
                "    } and it does {\n"
                "        define the position<_holder>.\n"
                "        move the particle in position</a> to position<_holder>.\n"
                "        move the particle in position<_holder> to position</a>.\n"
                "    }\n"
                "}\n"
            ),
            "destructor_b.dfn": (
                "define the potential action<my.domain.com:my_lib:/destructor_b> {\n"
                "    it also assigns the position</b>.\n"
                "    it happens when {\n"
                "        this particle is being destroyed.\n"
                "    } and it does {\n"
                "        define the position<_holder>.\n"
                "        move the particle in position</b> to position<_holder>.\n"
                "        move the particle in position<_holder> to position</b>.\n"
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
                "                it has the action</destructor_a>.\n"
                "                it has the action</destructor_b>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<my_file>.\n"
                "        create a particle in position<my_file>::position</a>.\n"
                "        create a particle in position<my_file>::position</b>.\n"
                "        move the particle in position<my_file> to position<box>::action</close_file>::position<target>.\n"
                "        create a particle in position<box>::action</close_file>::position<run>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    assert_no_errors(result.program_result)
    assert result.action_call_graph.edges() == [
        (_CLOSE_FILE, _DESTRUCTOR_B),
        (_CLOSE_FILE, _DESTRUCTOR_A),
        (_TEST, _CLOSE_FILE),
    ]


def test_three_destructors_with_two_violated(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """Of three caller-attached destructors with only position</a> filled, both destructor_c and destructor_b report violations (in firing order), while destructor_a is satisfied."""
    result = validate_project_with_reference_graph(
        {
            "a.dfn": "define the potential position<my.domain.com:my_lib:/a>.\n",
            "b.dfn": "define the potential position<my.domain.com:my_lib:/b>.\n",
            "c.dfn": "define the potential position<my.domain.com:my_lib:/c>.\n",
            "destructor_a.dfn": (
                "define the potential action<my.domain.com:my_lib:/destructor_a> {\n"
                "    it also assigns the position</a>.\n"
                "    it happens when {\n"
                "        this particle is being destroyed.\n"
                "    } and it does {\n"
                "        define the position<_holder>.\n"
                "        move the particle in position</a> to position<_holder>.\n"
                "        move the particle in position<_holder> to position</a>.\n"
                "    }\n"
                "}\n"
            ),
            "destructor_b.dfn": (
                "define the potential action<my.domain.com:my_lib:/destructor_b> {\n"
                "    it also assigns the position</b>.\n"
                "    it happens when {\n"
                "        this particle is being destroyed.\n"
                "    } and it does {\n"
                "        define the position<_holder>.\n"
                "        move the particle in position</b> to position<_holder>.\n"
                "        move the particle in position<_holder> to position</b>.\n"
                "    }\n"
                "}\n"
            ),
            "destructor_c.dfn": (
                "define the potential action<my.domain.com:my_lib:/destructor_c> {\n"
                "    it also assigns the position</c>.\n"
                "    it happens when {\n"
                "        this particle is being destroyed.\n"
                "    } and it does {\n"
                "        define the position<_holder>.\n"
                "        move the particle in position</c> to position<_holder>.\n"
                "        move the particle in position<_holder> to position</c>.\n"
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
                "                it has the action</destructor_a>.\n"
                "                it has the action</destructor_b>.\n"
                "                it has the action</destructor_c>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<my_file>.\n"
                "        create a particle in position<my_file>::position</a>.\n"
                "        move the particle in position<my_file> to position<box>::action</close_file>::position<target>.\n"
                "        create a particle in position<box>::action</close_file>::position<run>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 2
    # Destructors fire in reverse assignment order, so destructor_c is verified
    # before destructor_b.
    assert isinstance(all_diags[0], diagnostics.InferredRequirementViolationDiagnostic)
    assert all_diags[0].required_empty is False
    assert all_diags[0].runner_description == f"'{_CLOSE_FILE}'"
    assert (
        all_diags[0].position_name
        == "position<box>::action</close_file>::position<target>::position</c>"
    )
    assert_propagation_chain(
        all_diags[0],
        {
            "kind": action_contract.PropagationKind.DESTRUCTOR_ATTACHED,
            "enclosing_quality_name": "position<my_file>",
            "triggered_quality_name": _DESTRUCTOR_C,
            "line": 15,
            "column": 28,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.PARTICLE_ORIGIN,
            "enclosing_quality_name": "position<box>::action</close_file>::position<target>",
            "triggered_quality_name": None,
            "line": 19,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _TEST,
            "triggered_quality_name": _CLOSE_FILE,
            "line": 22,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DESTRUCTOR_CASCADE,
            "enclosing_quality_name": _CLOSE_FILE,
            "triggered_quality_name": _DESTRUCTOR_C,
            "line": 7,
            "column": 33,
            "file_path": "close_file.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": _DESTRUCTOR_C,
            "triggered_quality_name": None,
            "line": 7,
            "column": 30,
            "file_path": "destructor_c.dfn",
        },
    )
    assert isinstance(all_diags[1], diagnostics.InferredRequirementViolationDiagnostic)
    assert all_diags[1].required_empty is False
    assert all_diags[1].runner_description == f"'{_CLOSE_FILE}'"
    assert (
        all_diags[1].position_name
        == "position<box>::action</close_file>::position<target>::position</b>"
    )
    assert_propagation_chain(
        all_diags[1],
        {
            "kind": action_contract.PropagationKind.DESTRUCTOR_ATTACHED,
            "enclosing_quality_name": "position<my_file>",
            "triggered_quality_name": _DESTRUCTOR_B,
            "line": 14,
            "column": 28,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.PARTICLE_ORIGIN,
            "enclosing_quality_name": "position<box>::action</close_file>::position<target>",
            "triggered_quality_name": None,
            "line": 19,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _TEST,
            "triggered_quality_name": _CLOSE_FILE,
            "line": 22,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DESTRUCTOR_CASCADE,
            "enclosing_quality_name": _CLOSE_FILE,
            "triggered_quality_name": _DESTRUCTOR_B,
            "line": 7,
            "column": 33,
            "file_path": "close_file.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": _DESTRUCTOR_B,
            "triggered_quality_name": None,
            "line": 7,
            "column": 30,
            "file_path": "destructor_b.dfn",
        },
    )
    assert result.action_call_graph.edges() == [
        (_CLOSE_FILE, _DESTRUCTOR_C),
        (_CLOSE_FILE, _DESTRUCTOR_B),
        (_CLOSE_FILE, _DESTRUCTOR_A),
        (_TEST, _CLOSE_FILE),
    ]


def test_declared_quality_destructor_verified_once(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """When close_file's own target declares the destructor, close_file verifies it (propagating the requirement normally); the caller does not re-verify it through the Destruction Contract, so there is exactly one diagnostic."""
    result = validate_project_with_reference_graph(
        {
            "file.dfn": "define the potential position<my.domain.com:my_lib:/file>.\n",
            "destructor.dfn": (
                "define the potential action<my.domain.com:my_lib:/destructor> {\n"
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
            "close_file.dfn": (
                "define the potential action<my.domain.com:my_lib:/close_file> {\n"
                "    define the position<target> {\n"
                "        it may only contain particles where {\n"
                "            it has the action</destructor>.\n"
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
                "        create a particle in position<box>.\n"
                "        create a particle in position<box>::action</close_file>::position<target>.\n"
                "        create a particle in position<box>::action</close_file>::position<run>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    # close_file knows the destructor (its target declares it), so the
    # requirement surfaces through normal trigger propagation: the destructor is
    # attached on close_file's own target rather than via /test's my_file.
    assert isinstance(all_diags[0], diagnostics.InferredRequirementViolationDiagnostic)
    assert all_diags[0].location.line == 13
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].required_empty is False
    assert all_diags[0].runner_description == f"'{_CLOSE_FILE}'"
    assert (
        all_diags[0].position_name
        == "position<box>::action</close_file>::position<target>::position</file>"
    )
    assert_propagation_chain(
        all_diags[0],
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _TEST,
            "triggered_quality_name": _CLOSE_FILE,
            "line": 13,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DESTRUCTOR_ATTACHED,
            "enclosing_quality_name": "position<target>",
            "triggered_quality_name": _DESTRUCTOR,
            "line": 4,
            "column": 24,
            "file_path": "close_file.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DESTRUCTOR_CASCADE,
            "enclosing_quality_name": _CLOSE_FILE,
            "triggered_quality_name": _DESTRUCTOR,
            "line": 11,
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
        (_CLOSE_FILE, _DESTRUCTOR),
        (_TEST, _CLOSE_FILE),
    ]


def test_declared_quality_destructor_satisfied(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """When the declared-quality destructor's required position is filled, close_file's verification passes and no diagnostic is produced."""
    result = validate_project_with_reference_graph(
        {
            "file.dfn": "define the potential position<my.domain.com:my_lib:/file>.\n",
            "destructor.dfn": (
                "define the potential action<my.domain.com:my_lib:/destructor> {\n"
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
            "close_file.dfn": (
                "define the potential action<my.domain.com:my_lib:/close_file> {\n"
                "    define the position<target> {\n"
                "        it may only contain particles where {\n"
                "            it has the action</destructor>.\n"
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
                "        create a particle in position<box>.\n"
                "        create a particle in position<box>::action</close_file>::position<target>.\n"
                "        create a particle in position<box>::action</close_file>::position<target>::position</file>.\n"
                "        create a particle in position<box>::action</close_file>::position<run>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    assert_no_errors(result.program_result)
    assert result.action_call_graph.edges() == [
        (_CLOSE_FILE, _DESTRUCTOR),
        (_TEST, _CLOSE_FILE),
    ]


def test_position_init_block_consumer_caller_known_satisfied(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """A position init block (the validation root) triggers close_file and verifies its caller-attached destructor through the Destruction Contract; filling position</file> satisfies it."""
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
            "close_file.dfn": (
                "define the potential action<my.domain.com:my_lib:/close_file> {\n"
                "    define the position<target> {\n"
                "        it may only contain particles where {\n"
                "            it has the position</file>.\n"
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
                "define the potential position<my.domain.com:my_lib:/test> {\n"
                "    after it is assigned {\n"
                "        define the position<box> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</close_file>.\n"
                "            }\n"
                "        }\n"
                "        define the position<my_file> {\n"
                "            it may only contain particles where {\n"
                "                it has the position</file>.\n"
                "                it has the action</delete_file_destructor>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<my_file>.\n"
                "        create a particle in position<my_file>::position</file>.\n"
                "        move the particle in position<my_file> to position<box>::action</close_file>::position<target>.\n"
                "        create a particle in position<box>::action</close_file>::position<run>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    assert_no_errors(result.program_result)
    assert result.action_call_graph.edges() == [
        (_CLOSE_FILE, _DELETE_FILE_DESTRUCTOR),
        (_POS_TEST, _CLOSE_FILE),
    ]


def test_position_init_block_consumer_caller_known_violated(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """The same position-init-block consumer reports the unmet destructor requirement when position</file> is left empty; the chain names the position /test as the attacher."""
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
            "close_file.dfn": (
                "define the potential action<my.domain.com:my_lib:/close_file> {\n"
                "    define the position<target> {\n"
                "        it may only contain particles where {\n"
                "            it has the position</file>.\n"
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
                "define the potential position<my.domain.com:my_lib:/test> {\n"
                "    after it is assigned {\n"
                "        define the position<box> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</close_file>.\n"
                "            }\n"
                "        }\n"
                "        define the position<my_file> {\n"
                "            it may only contain particles where {\n"
                "                it has the position</file>.\n"
                "                it has the action</delete_file_destructor>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<my_file>.\n"
                "        move the particle in position<my_file> to position<box>::action</close_file>::position<target>.\n"
                "        create a particle in position<box>::action</close_file>::position<run>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.InferredRequirementViolationDiagnostic)
    assert all_diags[0].location.line == 17
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].required_empty is False
    assert all_diags[0].runner_description == f"'{_CLOSE_FILE}'"
    assert (
        all_diags[0].position_name
        == "position<box>::action</close_file>::position<target>::position</file>"
    )
    # The attacher is the position /test (its init block created my_file).
    assert_propagation_chain(
        all_diags[0],
        {
            "kind": action_contract.PropagationKind.DESTRUCTOR_ATTACHED,
            "enclosing_quality_name": "position<my_file>",
            "triggered_quality_name": _DELETE_FILE_DESTRUCTOR,
            "line": 11,
            "column": 28,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.PARTICLE_ORIGIN,
            "enclosing_quality_name": "position<box>::action</close_file>::position<target>",
            "triggered_quality_name": None,
            "line": 15,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _POS_TEST,
            "triggered_quality_name": _CLOSE_FILE,
            "line": 17,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DESTRUCTOR_CASCADE,
            "enclosing_quality_name": _CLOSE_FILE,
            "triggered_quality_name": _DELETE_FILE_DESTRUCTOR,
            "line": 11,
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
        (_POS_TEST, _CLOSE_FILE),
    ]


def test_visible_and_caller_attached_destructors_coexist(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """A particle carries one destructor close_file can see (declared on its target) and one it cannot (declared only on /test's my_file); the visible one surfaces through normal trigger propagation and the caller-attached one through the contract."""
    result = validate_project_with_reference_graph(
        {
            "file1.dfn": "define the potential position<my.domain.com:my_lib:/file1>.\n",
            "file2.dfn": "define the potential position<my.domain.com:my_lib:/file2>.\n",
            "delete_file1.dfn": (
                "define the potential action<my.domain.com:my_lib:/delete_file1> {\n"
                "    it also assigns the position</file1>.\n"
                "    it happens when {\n"
                "        this particle is being destroyed.\n"
                "    } and it does {\n"
                "        define the position<_holder>.\n"
                "        move the particle in position</file1> to position<_holder>.\n"
                "        move the particle in position<_holder> to position</file1>.\n"
                "    }\n"
                "}\n"
            ),
            "delete_file2.dfn": (
                "define the potential action<my.domain.com:my_lib:/delete_file2> {\n"
                "    it also assigns the position</file2>.\n"
                "    it happens when {\n"
                "        this particle is being destroyed.\n"
                "    } and it does {\n"
                "        define the position<_holder>.\n"
                "        move the particle in position</file2> to position<_holder>.\n"
                "        move the particle in position<_holder> to position</file2>.\n"
                "    }\n"
                "}\n"
            ),
            "close_file.dfn": (
                "define the potential action<my.domain.com:my_lib:/close_file> {\n"
                "    define the position<target> {\n"
                "        it may only contain particles where {\n"
                "            it has the action</delete_file1>.\n"
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
                "                it has the position</file1>.\n"
                "                it has the position</file2>.\n"
                "                it has the action</delete_file1>.\n"
                "                it has the action</delete_file2>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<my_file>.\n"
                "        move the particle in position<my_file> to position<box>::action</close_file>::position<target>.\n"
                "        create a particle in position<box>::action</close_file>::position<run>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 2
    # The visible destructor: close_file knows it, so its requirement propagates
    # with the destructor attached on close_file's own target (no my_file step).
    assert isinstance(all_diags[0], diagnostics.InferredRequirementViolationDiagnostic)
    assert all_diags[0].location.line == 22
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].required_empty is False
    assert all_diags[0].runner_description == f"'{_CLOSE_FILE}'"
    assert (
        all_diags[0].position_name
        == "position<box>::action</close_file>::position<target>::position</file1>"
    )
    assert_propagation_chain(
        all_diags[0],
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _TEST,
            "triggered_quality_name": _CLOSE_FILE,
            "line": 22,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DESTRUCTOR_ATTACHED,
            "enclosing_quality_name": "position<target>",
            "triggered_quality_name": _DELETE_FILE1,
            "line": 4,
            "column": 24,
            "file_path": "close_file.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DESTRUCTOR_CASCADE,
            "enclosing_quality_name": _CLOSE_FILE,
            "triggered_quality_name": _DELETE_FILE1,
            "line": 11,
            "column": 33,
            "file_path": "close_file.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": _DELETE_FILE1,
            "triggered_quality_name": None,
            "line": 7,
            "column": 30,
            "file_path": "delete_file1.dfn",
        },
    )
    # The caller-attached destructor: close_file is blind to it, so /test verifies
    # it through the contract, attributed to my_file.
    assert isinstance(all_diags[1], diagnostics.InferredRequirementViolationDiagnostic)
    assert all_diags[1].location.line == 22
    assert all_diags[1].location.column == 30
    assert all_diags[1].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[1].required_empty is False
    assert all_diags[1].runner_description == f"'{_CLOSE_FILE}'"
    assert (
        all_diags[1].position_name
        == "position<box>::action</close_file>::position<target>::position</file2>"
    )
    assert_propagation_chain(
        all_diags[1],
        {
            "kind": action_contract.PropagationKind.DESTRUCTOR_ATTACHED,
            "enclosing_quality_name": "position<my_file>",
            "triggered_quality_name": _DELETE_FILE2,
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
            "line": 22,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DESTRUCTOR_CASCADE,
            "enclosing_quality_name": _CLOSE_FILE,
            "triggered_quality_name": _DELETE_FILE2,
            "line": 11,
            "column": 33,
            "file_path": "close_file.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": _DELETE_FILE2,
            "triggered_quality_name": None,
            "line": 7,
            "column": 30,
            "file_path": "delete_file2.dfn",
        },
    )
    assert result.action_call_graph.edges() == [
        (_CLOSE_FILE, _DELETE_FILE1),
        (_CLOSE_FILE, _DELETE_FILE2),
        (_TEST, _CLOSE_FILE),
    ]


# TODO: A Destruction Contract recorded while running a Position Initialization
# Block is not propagated up to the action that ran that init block (by creating a
# particle in the position), so a destructor that only that action knows about is
# silently dropped and its requirement is never verified. This is the same
# init-block boundary gap as the missing action-call-graph edge (see the TODO in
# definition_postorder_validator._run_position_init_blocks). The contract would be
# verified normally if /outer moved the particle to /callee itself; the bug is
# that /p's init block performs that move instead.
@pytest.mark.xfail(
    strict=True,
    reason="Destruction Contract is not propagated out of a Position Initialization Block",
)
def test_caller_known_destructor_lost_across_position_init_block(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "d.dfn": (
                "define the potential action<my.domain.com:my_lib:/d> {\n"
                "    define the position<item>.\n"
                "    it happens when {\n"
                "        this particle is being destroyed.\n"
                "    } and it does {\n"
                "        define the position<_holder>.\n"
                "        move the particle in position<item> to position<_holder>.\n"
                "        move the particle in position<_holder> to position<item>.\n"
                "    }\n"
                "}\n"
            ),
            "q.dfn": "define the potential position<my.domain.com:my_lib:/q>.\n",
            "callee.dfn": (
                "define the potential action<my.domain.com:my_lib:/callee> {\n"
                "    define the position<incoming>.\n"
                "    it happens when {\n"
                "        the position<incoming> has a particle.\n"
                "    } and it does {\n"
                "        destroy the particle in position<incoming>.\n"
                "    }\n"
                "}\n"
            ),
            "p.dfn": (
                "define the potential position<my.domain.com:my_lib:/p> {\n"
                "    it also assigns the position</q>.\n"
                "    it also assigns the action</callee>.\n"
                "    after it is assigned {\n"
                "        move the particle in position</q> to action</callee>::position<incoming>.\n"
                "    }\n"
                "}\n"
            ),
            "outer.dfn": (
                "define the potential action<my.domain.com:my_lib:/outer> {\n"
                "    it also assigns the position</q>.\n"
                "    it also assigns the position</p>.\n"
                "    define the position<box> {\n"
                "        it may only contain particles where {\n"
                "            it has the action</d>.\n"
                "        }\n"
                "    }\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<box>.\n"
                "        move the particle in position<box> to position</q>.\n"
                "        create a particle in position</p>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    it also assigns the action</outer>.\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in action</outer>::position<run>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    all_diags = result.program_result.all_diagnostics
    # /outer knows /d, so the destructor's unmet requirement must be verified.
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.InferredRequirementViolationDiagnostic)
    assert all_diags[0].required_empty is False
    assert all_diags[0].position_name.endswith("action</d>::position<item>")
