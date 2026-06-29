# pyright: reportUnusedCallResult=false
# Exception to CLAUDE.md "no docstrings in tests" rule: these tests have docstrings
# because the automated guarantee/requirement scenarios are complex enough to need
# prose explanations of what each test verifies.

from pathlib import PurePosixPath

from define.compiler import diagnostics
from define.compiler.conftest import ValidateProjectWithReferenceGraph
from define.compiler.validator.reference_graph import action_contract
from define.compiler.validator.reference_graph.reference_graph_validator_tests.test_helpers import (
    assert_propagation_chain,
)
from define.compiler.validator.test_helpers import assert_action_calls, assert_no_errors

_TEST = "action<my.domain.com:my_lib:/test>"
_OTHER = "action<my.domain.com:my_lib:/other>"


def test_satisfy_requirements_then_trigger(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """Satisfying an action's occupied requirement before triggering succeeds."""
    result = validate_project_with_reference_graph(
        {
            "other.dfn": (
                "define the potential action<my.domain.com:my_lib:/other> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<item>.\n"
                "    define the position<dest>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        move the particle in position<item> to position<dest>.\n"
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
                "                it has the action</other>.\n"
                "            }\n"
                "        }\n"
                "        define the position<spare>.\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<spare>.\n"
                "        move the particle in position<spare> to position<box>::action</other>::position<item>.\n"
                "        create a particle in position<box>::action</other>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    assert_no_errors(result.program_result)
    assert_action_calls(result.action_call_graph, _TEST, _OTHER)


def test_violate_occupied_requirement(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """Triggering without filling a required occupied position produces a requirement-violation diagnostic."""
    result = validate_project_with_reference_graph(
        {
            "other.dfn": (
                "define the potential action<my.domain.com:my_lib:/other> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<item>.\n"
                "    define the position<dest>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        move the particle in position<item> to position<dest>.\n"
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
                "                it has the action</other>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<box>::action</other>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.InferredRequirementViolationDiagnostic)
    assert all_diags[0].location.line == 12
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].action_name == "action<my.domain.com:my_lib:/other>"
    assert all_diags[0].required_empty is False
    assert all_diags[0].position_name == "position<box>::action</other>::position<item>"
    assert_propagation_chain(
        all_diags[0],
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _TEST,
            "triggered_quality_name": _OTHER,
            "line": 12,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": _OTHER,
            "triggered_quality_name": None,
            "line": 8,
            "column": 30,
            "file_path": "other.dfn",
        },
    )
    assert_action_calls(result.action_call_graph, _TEST, _OTHER)


def test_caller_violates_occupied_requirement(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """Caller triggering without filling a required occupied position produces a diagnostic at the trigger site."""
    result = validate_project_with_reference_graph(
        {
            "other.dfn": (
                "define the potential action<my.domain.com:my_lib:/other> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<item>.\n"
                "    define the position<dest>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        move the particle in position<item> to position<dest>.\n"
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
                "                it has the action</other>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<box>::action</other>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.InferredRequirementViolationDiagnostic)
    assert all_diags[0].location.line == 12
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].action_name == "action<my.domain.com:my_lib:/other>"
    assert all_diags[0].required_empty is False
    assert all_diags[0].position_name == "position<box>::action</other>::position<item>"
    assert_propagation_chain(
        all_diags[0],
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _TEST,
            "triggered_quality_name": _OTHER,
            "line": 12,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": _OTHER,
            "triggered_quality_name": None,
            "line": 8,
            "column": 30,
            "file_path": "other.dfn",
        },
    )
    assert_action_calls(result.action_call_graph, _TEST, _OTHER)


def test_caller_satisfies_empty_requirement(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """Triggering an action whose body creates in a position succeeds when the caller leaves it empty."""
    result = validate_project_with_reference_graph(
        {
            "other.dfn": (
                "define the potential action<my.domain.com:my_lib:/other> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<item>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<item>.\n"
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
                "                it has the action</other>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<box>::action</other>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    assert_no_errors(result.program_result)
    assert_action_calls(result.action_call_graph, _TEST, _OTHER)


def test_caller_violates_empty_requirement(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """Triggering an action whose body creates in a position fails when the caller already filled it."""
    result = validate_project_with_reference_graph(
        {
            "other.dfn": (
                "define the potential action<my.domain.com:my_lib:/other> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<item>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<item>.\n"
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
                "                it has the action</other>.\n"
                "            }\n"
                "        }\n"
                "        define the position<spare>.\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<spare>.\n"
                "        move the particle in position<spare> to position<box>::action</other>::position<item>.\n"
                "        create a particle in position<box>::action</other>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.InferredRequirementViolationDiagnostic)
    assert all_diags[0].location.line == 15
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].action_name == "action<my.domain.com:my_lib:/other>"
    assert all_diags[0].required_empty is True
    assert all_diags[0].position_name == "position<box>::action</other>::position<item>"
    assert_propagation_chain(
        all_diags[0],
        {
            "kind": action_contract.PropagationKind.FILL_SITE,
            "enclosing_quality_name": "position<box>::action</other>::position<item>",
            "triggered_quality_name": None,
            "line": 14,
            "column": 49,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _TEST,
            "triggered_quality_name": _OTHER,
            "line": 15,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": _OTHER,
            "triggered_quality_name": None,
            "line": 7,
            "column": 30,
            "file_path": "other.dfn",
        },
    )
    assert_action_calls(result.action_call_graph, _TEST, _OTHER)


def test_empty_requirement_with_error_state_is_silent(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """When position state is error from a failed move, no empty requirement diagnostic is produced."""
    result = validate_project_with_reference_graph(
        {
            "other.dfn": (
                "define the potential action<my.domain.com:my_lib:/other> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<item>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<item>.\n"
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
                "                it has the action</other>.\n"
                "            }\n"
                "        }\n"
                "        define the position<spare>.\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<spare>.\n"
                "        move the particle in position<spare> to position<box>::action</other>::position<item>.\n"
                "        move the particle in position<spare> to position<box>::action</other>::position<item>.\n"
                "        create a particle in position<box>::action</other>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 2
    assert isinstance(all_diags[0], diagnostics.MoveFromEmptyPositionDiagnostic)
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert isinstance(all_diags[1], diagnostics.MoveToOccupiedPositionDiagnostic)
    assert all_diags[1].location.file_path == PurePosixPath("test.dfn")
    assert_action_calls(result.action_call_graph, _TEST, _OTHER)


def test_occupied_requirement_with_error_state_is_silent(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """When position state is error from a failed move, no occupied requirement diagnostic is produced."""
    result = validate_project_with_reference_graph(
        {
            "other.dfn": (
                "define the potential action<my.domain.com:my_lib:/other> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<item>.\n"
                "    define the position<dest>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        move the particle in position<item> to position<dest>.\n"
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
                "                it has the action</other>.\n"
                "            }\n"
                "        }\n"
                "        define the position<spare>.\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<spare>.\n"
                "        move the particle in position<spare> to position<box>::action</other>::position<item>.\n"
                "        move the particle in position<spare> to position<box>::action</other>::position<item>.\n"
                "        create a particle in position<box>::action</other>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 2
    assert isinstance(all_diags[0], diagnostics.MoveFromEmptyPositionDiagnostic)
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert isinstance(all_diags[1], diagnostics.MoveToOccupiedPositionDiagnostic)
    assert all_diags[1].location.file_path == PurePosixPath("test.dfn")
    assert_action_calls(result.action_call_graph, _TEST, _OTHER)


def test_error_requirement_does_not_skip_later_unsatisfied_requirement(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """An error-state requirement does not skip subsequent requirements.

    When one inferred requirement's position is error, subsequent
    requirements must still be checked. Ensures `_check_requirements` uses
    `continue` to skip the error one rather than `break` out of the loop.
    """
    result = validate_project_with_reference_graph(
        {
            "inner.dfn": (
                "define the potential action<my.domain.com:my_lib:/inner> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<a>.\n"
                "    define the position<b>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        destroy the particle in position<a>.\n"
                "        destroy the particle in position<b>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    define the position<src>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</inner>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<src>.\n"
                "        move the particle in position<src> to position<box>::action</inner>::position<a>.\n"
                "        move the particle in position<src> to position<box>::action</inner>::position<a>.\n"
                "        create a particle in position<box>::action</inner>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 3
    assert isinstance(all_diags[0], diagnostics.MoveFromEmptyPositionDiagnostic)
    assert all_diags[0].location.line == 15
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.end_line == 15
    assert all_diags[0].location.end_column == 43
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].position_name == "position<src>"
    assert isinstance(all_diags[1], diagnostics.MoveToOccupiedPositionDiagnostic)
    assert all_diags[1].location.line == 15
    assert all_diags[1].location.column == 47
    assert all_diags[1].location.end_line == 15
    assert all_diags[1].location.end_column == 89
    assert all_diags[1].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[1].position_name == "position<box>::action</inner>::position<a>"
    assert all_diags[1].occupied_at is not None
    assert all_diags[1].occupied_at.line == 14
    assert all_diags[1].occupied_at.column == 47
    assert all_diags[1].occupied_at.end_line == 14
    assert all_diags[1].occupied_at.end_column == 89
    assert all_diags[1].occupied_at.file_path == PurePosixPath("test.dfn")
    assert isinstance(all_diags[2], diagnostics.InferredRequirementViolationDiagnostic)
    assert all_diags[2].location.line == 16
    assert all_diags[2].location.column == 30
    assert all_diags[2].location.end_line == 16
    assert all_diags[2].location.end_column == 82
    assert all_diags[2].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[2].action_name == "action<my.domain.com:my_lib:/inner>"
    assert all_diags[2].required_empty is False
    assert all_diags[2].position_name == "position<box>::action</inner>::position<b>"
    assert_propagation_chain(
        all_diags[2],
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _TEST,
            "triggered_quality_name": "action<my.domain.com:my_lib:/inner>",
            "line": 16,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/inner>",
            "triggered_quality_name": None,
            "line": 9,
            "column": 33,
            "file_path": "inner.dfn",
        },
    )
    assert_action_calls(
        result.action_call_graph, _TEST, "action<my.domain.com:my_lib:/inner>"
    )


def test_multiple_requirements_one_empty_one_occupied(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """An action with both occupied and empty requirements succeeds when both are satisfied."""
    result = validate_project_with_reference_graph(
        {
            "other.dfn": (
                "define the potential action<my.domain.com:my_lib:/other> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<src>.\n"
                "    define the position<tgt>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        move the particle in position<src> to position<tgt>.\n"
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
                "                it has the action</other>.\n"
                "            }\n"
                "        }\n"
                "        define the position<spare>.\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<spare>.\n"
                "        move the particle in position<spare> to position<box>::action</other>::position<src>.\n"
                "        create a particle in position<box>::action</other>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    assert_no_errors(result.program_result)
    assert_action_calls(result.action_call_graph, _TEST, _OTHER)


def test_caller_satisfies_occupied_requirement(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """Filling an action's required occupied position before triggering succeeds."""
    result = validate_project_with_reference_graph(
        {
            "other.dfn": (
                "define the potential action<my.domain.com:my_lib:/other> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<item>.\n"
                "    define the position<dest>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        move the particle in position<item> to position<dest>.\n"
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
                "                it has the action</other>.\n"
                "            }\n"
                "        }\n"
                "        define the position<spare>.\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<spare>.\n"
                "        move the particle in position<spare> to position<box>::action</other>::position<item>.\n"
                "        create a particle in position<box>::action</other>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    assert_no_errors(result.program_result)
    assert_action_calls(result.action_call_graph, _TEST, _OTHER)


_OTHER_WITH_OCCUPIED_REQUIREMENT = (
    "define the potential action<my.domain.com:my_lib:/other> {\n"
    "    define the position<trigger_pos>.\n"
    "    define the position<item>.\n"
    "    define the position<dest>.\n"
    "    it happens when {\n"
    "        the position<trigger_pos> has a particle.\n"
    "    } and it does {\n"
    "        move the particle in position<item> to position<dest>.\n"
    "    }\n"
    "}\n"
)

_OTHER_WITH_EMPTY_REQUIREMENT = (
    "define the potential action<my.domain.com:my_lib:/other> {\n"
    "    define the position<trigger_pos>.\n"
    "    define the position<item>.\n"
    "    it happens when {\n"
    "        the position<trigger_pos> has a particle.\n"
    "    } and it does {\n"
    "        create a particle in position<item>.\n"
    "    }\n"
    "}\n"
)


def test_constructor_violates_occupied_requirement(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """Triggering from a constructor without filling the required occupied position fails."""
    result = validate_project_with_reference_graph(
        {
            "other.dfn": _OTHER_WITH_OCCUPIED_REQUIREMENT,
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    it happens when {\n"
                "        this particle is created.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</other>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<box>::action</other>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.InferredRequirementViolationDiagnostic)
    assert all_diags[0].location.line == 11
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].action_name == "action<my.domain.com:my_lib:/other>"
    assert all_diags[0].required_empty is False
    assert all_diags[0].position_name == "position<box>::action</other>::position<item>"
    assert_propagation_chain(
        all_diags[0],
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _TEST,
            "triggered_quality_name": _OTHER,
            "line": 11,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": _OTHER,
            "triggered_quality_name": None,
            "line": 8,
            "column": 30,
            "file_path": "other.dfn",
        },
    )
    assert_action_calls(result.action_call_graph, _TEST, _OTHER)


def test_constructor_violates_empty_requirement(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """Triggering from a constructor after filling a position the action requires empty fails."""
    result = validate_project_with_reference_graph(
        {
            "other.dfn": _OTHER_WITH_EMPTY_REQUIREMENT,
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    it happens when {\n"
                "        this particle is created.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</other>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<box>::action</other>::position<item>.\n"
                "        create a particle in position<box>::action</other>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.InferredRequirementViolationDiagnostic)
    assert all_diags[0].location.line == 12
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].action_name == "action<my.domain.com:my_lib:/other>"
    assert all_diags[0].required_empty is True
    assert all_diags[0].position_name == "position<box>::action</other>::position<item>"
    assert_propagation_chain(
        all_diags[0],
        {
            "kind": action_contract.PropagationKind.FILL_SITE,
            "enclosing_quality_name": "position<box>::action</other>::position<item>",
            "triggered_quality_name": None,
            "line": 11,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _TEST,
            "triggered_quality_name": _OTHER,
            "line": 12,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": _OTHER,
            "triggered_quality_name": None,
            "line": 7,
            "column": 30,
            "file_path": "other.dfn",
        },
    )
    assert_action_calls(result.action_call_graph, _TEST, _OTHER)


def test_constructor_satisfies_requirements(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """Triggering from a constructor with all requirements satisfied succeeds."""
    result = validate_project_with_reference_graph(
        {
            "other.dfn": _OTHER_WITH_OCCUPIED_REQUIREMENT,
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    it happens when {\n"
                "        this particle is created.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</other>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<box>::action</other>::position<item>.\n"
                "        create a particle in position<box>::action</other>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    assert_no_errors(result.program_result)
    assert_action_calls(result.action_call_graph, _TEST, _OTHER)


def test_no_requirement_check_on_unknown_global_chain_start(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """When the chain starts with an unknown global name, requirement checking is skipped."""
    result = validate_project_with_reference_graph(
        {
            "other.dfn": (
                "define the potential action<my.domain.com:my_lib:/other> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<item>.\n"
                "    define the position<dest>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        move the particle in position<item> to position<dest>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in action</other>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.UnknownGlobalNameDiagnostic)
    assert all_diags[0].source_global_name == "action</other>"
    assert all_diags[0].full_global_name == "action<my.domain.com:my_lib:/other>"


def test_trigger_chain_occupied_requirement_satisfied(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """A trigger chain's child occupied requirement is satisfied when the caller fills the child position."""
    result = validate_project_with_reference_graph(
        {
            "x.dfn": "define the potential position<my.domain.com:my_lib:/x>.\n",
            "y.dfn": "define the potential position<my.domain.com:my_lib:/y>.\n",
            "other.dfn": (
                "define the potential action<my.domain.com:my_lib:/other> {\n"
                "    define the position<trigger_pos> {\n"
                "        it may only contain particles where {\n"
                "            it has the position</x>.\n"
                "        }\n"
                "    }\n"
                "    define the position<item> {\n"
                "        it may only contain particles where {\n"
                "            it has the position</y>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        move the particle in position<item>::position</y> to position<trigger_pos>::position</x>.\n"
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
                "                it has the action</other>.\n"
                "            }\n"
                "        }\n"
                "        define the position<spare> {\n"
                "            it may only contain particles where {\n"
                "                it has the position</y>.\n"
                "            }\n"
                "        }\n"
                "        define the position<spare2>.\n"
                "        create a particle in position<spare2>.\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<spare>.\n"
                "        move the particle in position<spare> to position<box>::action</other>::position<item>.\n"
                "        create a particle in position<box>::action</other>::position<item>::position</y>.\n"
                "        create a particle in position<box>::action</other>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    assert_no_errors(result.program_result)
    assert_action_calls(result.action_call_graph, _TEST, _OTHER)


def test_trigger_chain_occupied_requirement_violated(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """A trigger chain's child occupied requirement is violated when the caller doesn't fill the child positions."""
    result = validate_project_with_reference_graph(
        {
            "x.dfn": "define the potential position<my.domain.com:my_lib:/x>.\n",
            "y.dfn": "define the potential position<my.domain.com:my_lib:/y>.\n",
            "other.dfn": (
                "define the potential action<my.domain.com:my_lib:/other> {\n"
                "    define the position<trigger_pos> {\n"
                "        it may only contain particles where {\n"
                "            it has the position</x>.\n"
                "        }\n"
                "    }\n"
                "    define the position<item> {\n"
                "        it may only contain particles where {\n"
                "            it has the position</y>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        move the particle in position<item>::position</y> to position<trigger_pos>::position</x>.\n"
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
                "                it has the action</other>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<box>::action</other>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 2
    assert isinstance(all_diags[0], diagnostics.InferredRequirementViolationDiagnostic)
    assert all_diags[0].position_name == "position<box>::action</other>::position<item>"
    assert all_diags[0].location.line == 12
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].action_name == "action<my.domain.com:my_lib:/other>"
    assert all_diags[0].required_empty is False
    assert_propagation_chain(
        all_diags[0],
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _TEST,
            "triggered_quality_name": _OTHER,
            "line": 12,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": _OTHER,
            "triggered_quality_name": None,
            "line": 15,
            "column": 30,
            "file_path": "other.dfn",
        },
    )
    assert isinstance(all_diags[1], diagnostics.InferredRequirementViolationDiagnostic)
    assert (
        all_diags[1].position_name
        == "position<box>::action</other>::position<item>::position</y>"
    )
    assert all_diags[1].location.line == 12
    assert all_diags[1].location.column == 30
    assert all_diags[1].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[1].action_name == "action<my.domain.com:my_lib:/other>"
    assert all_diags[1].required_empty is False
    assert_propagation_chain(
        all_diags[1],
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _TEST,
            "triggered_quality_name": _OTHER,
            "line": 12,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": _OTHER,
            "triggered_quality_name": None,
            "line": 15,
            "column": 30,
            "file_path": "other.dfn",
        },
    )
    assert_action_calls(result.action_call_graph, _TEST, _OTHER)


def test_trigger_chain_empty_requirement_satisfied(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """A trigger chain's child empty requirement is satisfied when the caller leaves it empty."""
    result = validate_project_with_reference_graph(
        {
            "x.dfn": "define the potential position<my.domain.com:my_lib:/x>.\n",
            "other.dfn": (
                "define the potential action<my.domain.com:my_lib:/other> {\n"
                "    define the position<trigger_pos> {\n"
                "        it may only contain particles where {\n"
                "            it has the position</x>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<trigger_pos>::position</x>.\n"
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
                "                it has the action</other>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<box>::action</other>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    assert_no_errors(result.program_result)
    assert_action_calls(result.action_call_graph, _TEST, _OTHER)


def test_trigger_chain_empty_requirement_violated(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """A trigger chain's child empty requirement is violated when the caller fills it before triggering."""
    result = validate_project_with_reference_graph(
        {
            "x.dfn": "define the potential position<my.domain.com:my_lib:/x>.\n",
            "other.dfn": (
                "define the potential action<my.domain.com:my_lib:/other> {\n"
                "    define the position<trigger_pos> {\n"
                "        it may only contain particles where {\n"
                "            it has the position</x>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<trigger_pos>::position</x>.\n"
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
                "                it has the action</other>.\n"
                "            }\n"
                "        }\n"
                "        define the position<spare> {\n"
                "            it may only contain particles where {\n"
                "                it has the position</x>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<spare>.\n"
                "        create a particle in position<spare>::position</x>.\n"
                "        move the particle in position<spare> to position<box>::action</other>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.InferredRequirementViolationDiagnostic)
    assert all_diags[0].location.line == 19
    assert all_diags[0].location.column == 49
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].action_name == "action<my.domain.com:my_lib:/other>"
    assert all_diags[0].required_empty is True
    assert (
        all_diags[0].position_name
        == "position<box>::action</other>::position<trigger_pos>::position</x>"
    )
    assert_propagation_chain(
        all_diags[0],
        {
            "kind": action_contract.PropagationKind.FILL_SITE,
            "enclosing_quality_name": "position<box>::action</other>::position<trigger_pos>::position</x>",
            "triggered_quality_name": None,
            "line": 18,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _TEST,
            "triggered_quality_name": _OTHER,
            "line": 19,
            "column": 49,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": _OTHER,
            "triggered_quality_name": None,
            "line": 10,
            "column": 30,
            "file_path": "other.dfn",
        },
    )
    assert_action_calls(result.action_call_graph, _TEST, _OTHER)


def test_trigger_chain_parent_requirement_violated(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """A trigger chain fails when the parent interface position is not occupied."""
    result = validate_project_with_reference_graph(
        {
            "x.dfn": "define the potential position<my.domain.com:my_lib:/x>.\n",
            "other.dfn": (
                "define the potential action<my.domain.com:my_lib:/other> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<iface> {\n"
                "        it may only contain particles where {\n"
                "            it has the position</x>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<iface>::position</x>.\n"
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
                "                it has the action</other>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<box>::action</other>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.InferredRequirementViolationDiagnostic)
    assert all_diags[0].action_name == "action<my.domain.com:my_lib:/other>"
    assert all_diags[0].required_empty is False
    assert (
        all_diags[0].position_name == "position<box>::action</other>::position<iface>"
    )
    assert all_diags[0].location.line == 12
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert_propagation_chain(
        all_diags[0],
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _TEST,
            "triggered_quality_name": _OTHER,
            "line": 12,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": _OTHER,
            "triggered_quality_name": None,
            "line": 11,
            "column": 30,
            "file_path": "other.dfn",
        },
    )
    assert_action_calls(result.action_call_graph, _TEST, _OTHER)


def test_destroy_infers_occupied_requirement(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """Destroying an interface position infers an OCCUPIED requirement.

    Triggering without filling it produces a requirement-violation diagnostic.
    """
    result = validate_project_with_reference_graph(
        {
            "other.dfn": (
                "define the potential action<my.domain.com:my_lib:/other> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<item>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        destroy the particle in position<item>.\n"
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
                "                it has the action</other>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<box>::action</other>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.InferredRequirementViolationDiagnostic)
    assert all_diags[0].location.line == 12
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].action_name == "action<my.domain.com:my_lib:/other>"
    assert all_diags[0].required_empty is False
    assert all_diags[0].position_name == "position<box>::action</other>::position<item>"
    assert_propagation_chain(
        all_diags[0],
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _TEST,
            "triggered_quality_name": _OTHER,
            "line": 12,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": _OTHER,
            "triggered_quality_name": None,
            "line": 7,
            "column": 33,
            "file_path": "other.dfn",
        },
    )
    assert_action_calls(result.action_call_graph, _TEST, _OTHER)


def test_inner_action_local_failure_does_not_propagate_to_caller(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """Operations on body-local positions inside a triggered action do not propagate requirements to the caller.

    The inner action errors on its own body (destroying an empty body-local
    position), but that body-local position is purely local to the inner
    action and must not appear in the caller's requirements.
    """
    result = validate_project_with_reference_graph(
        {
            "other.dfn": (
                "define the potential action<my.domain.com:my_lib:/other> {\n"
                "    define the position<trigger_pos>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        define the position<body_local>.\n"
                "        destroy the particle in position<body_local>.\n"
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
                "                it has the action</other>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<box>::action</other>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.DestroyInEmptyPositionDiagnostic)
    assert all_diags[0].location.line == 7
    assert all_diags[0].location.column == 33
    assert all_diags[0].location.file_path == PurePosixPath("other.dfn")
    assert all_diags[0].position_name == "position<body_local>"
    assert_action_calls(result.action_call_graph, _TEST, _OTHER)
