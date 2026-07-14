# pyright: reportUnusedCallResult=false
# Exception to CLAUDE.md "no docstrings in tests" rule: these tests have docstrings
# because the automated guarantee/requirement scenarios are complex enough to need
# prose explanations of what each test verifies.

# TODO: This file is very very big. Split it into multiple files.

from pathlib import PurePosixPath

from define.compiler import diagnostics
from define.compiler.conftest import ValidateProjectWithReferenceGraph
from define.compiler.validator.reference_graph import action_contract
from define.compiler.validator.reference_graph.operation_graph_renderer import (
    action_graph_set,
)
from define.compiler.validator.reference_graph.reference_graph_validator_tests.test_helpers import (
    assert_propagation_chain,
)
from define.compiler.validator.test_helpers import assert_no_errors

_TEST = "action<my.domain.com:my_lib:/test>"
_OUTER = "action<my.domain.com:my_lib:/outer>"
_INNER = "action<my.domain.com:my_lib:/inner>"
_MIDDLE = "action<my.domain.com:my_lib:/middle>"


def test_outer_move_into_inner_trigger_propagates_occupied_requirement(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """A MOVE into /inner's trigger position propagates /inner's OCCUPIED requirement.

    The trigger fires and /inner's OCCUPIED requirement on position<item> must
    propagate into /outer's contract — the scope passed to _check_trigger must
    be the live one, not None, so _get_transitive_required_qualities can
    resolve the propagated requirement's qualities.
    """
    result = validate_project_with_reference_graph(
        {
            "inner.dfn": (
                "define the potential action<my.domain.com:my_lib:/inner> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<item>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        destroy the particle in position<item>.\n"
                "    }\n"
                "}\n"
            ),
            "outer.dfn": (
                "define the potential action<my.domain.com:my_lib:/outer> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<src>.\n"
                "    define the position<iface> {\n"
                "        it may only contain particles where {\n"
                "            it has the action</inner>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<src>.\n"
                "        move the particle in position<src> to position<iface>::action</inner>::position<trigger_pos>.\n"
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
                "        create a particle in position<box>.\n"
                "        create a particle in position<box>::action</outer>::position<iface>.\n"
                "        create a particle in position<box>::action</outer>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.InferredRequirementViolationDiagnostic)
    assert all_diags[0].location.line == 13
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.end_line == 13
    assert all_diags[0].location.end_column == 82
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].action_name == "action<my.domain.com:my_lib:/outer>"
    assert all_diags[0].required_empty is False
    assert (
        all_diags[0].position_name
        == "position<box>::action</outer>::position<iface>::action</inner>::position<item>"
    )
    assert_propagation_chain(
        all_diags[0],
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _TEST,
            "triggered_quality_name": _OUTER,
            "line": 13,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _OUTER,
            "triggered_quality_name": _INNER,
            "line": 13,
            "column": 47,
            "file_path": "outer.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": _INNER,
            "triggered_quality_name": None,
            "line": 7,
            "column": 33,
            "file_path": "inner.dfn",
        },
    )
    assert action_graph_set(result.operation_graphs) == {
        (_TEST, _OUTER),
        (_OUTER, _INNER),
    }


def test_inner_chained_action_empty_requirement_propagates(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """An inner action requires position<item> to be empty (its first reference is a create).

    The test action pre-fills position<box>::action</outer>::position<iface>::action</inner>::position<item>
    before triggering /outer. When /outer triggers /inner internally, /inner's empty requirement
    on position<item> has been propagated into /outer's contract. So the caller gets an error
    because it filled a position that /inner needs empty.
    """
    result = validate_project_with_reference_graph(
        {
            "inner.dfn": (
                "define the potential action<my.domain.com:my_lib:/inner> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<item>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<item>.\n"
                "    }\n"
                "}\n"
            ),
            "outer.dfn": (
                "define the potential action<my.domain.com:my_lib:/outer> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<iface> {\n"
                "        it may only contain particles where {\n"
                "            it has the action</inner>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<iface>::action</inner>::position<trigger_pos>.\n"
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
                "        create a particle in position<box>.\n"
                "        create a particle in position<box>::action</outer>::position<iface>.\n"
                "        create a particle in position<box>::action</outer>::position<iface>::action</inner>::position<item>.\n"
                "        create a particle in position<box>::action</outer>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.InferredRequirementViolationDiagnostic)
    assert all_diags[0].location.line == 14
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].action_name == "action<my.domain.com:my_lib:/outer>"
    assert all_diags[0].required_empty is True
    assert (
        all_diags[0].position_name
        == "position<box>::action</outer>::position<iface>::action</inner>::position<item>"
    )
    assert_propagation_chain(
        all_diags[0],
        {
            "kind": action_contract.PropagationKind.FILL_SITE,
            "enclosing_quality_name": "position<box>::action</outer>::position<iface>::action</inner>::position<item>",
            "triggered_quality_name": None,
            "line": 13,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _TEST,
            "triggered_quality_name": _OUTER,
            "line": 14,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _OUTER,
            "triggered_quality_name": _INNER,
            "line": 11,
            "column": 30,
            "file_path": "outer.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": _INNER,
            "triggered_quality_name": None,
            "line": 7,
            "column": 30,
            "file_path": "inner.dfn",
        },
    )
    assert action_graph_set(result.operation_graphs) == {
        (_TEST, _OUTER),
        (_OUTER, _INNER),
    }


def test_inner_chained_action_empty_requirement_satisfied(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """Same setup as the propagation test, but the caller does NOT pre-fill position<item>.

    Since /inner requires position<item> to be empty and it IS empty when /outer triggers
    /inner, no error occurs.
    """
    result = validate_project_with_reference_graph(
        {
            "inner.dfn": (
                "define the potential action<my.domain.com:my_lib:/inner> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<item>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<item>.\n"
                "    }\n"
                "}\n"
            ),
            "outer.dfn": (
                "define the potential action<my.domain.com:my_lib:/outer> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<iface> {\n"
                "        it may only contain particles where {\n"
                "            it has the action</inner>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<iface>::action</inner>::position<trigger_pos>.\n"
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
                "        create a particle in position<box>.\n"
                "        create a particle in position<box>::action</outer>::position<iface>.\n"
                "        create a particle in position<box>::action</outer>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    assert_no_errors(result.program_result)
    assert action_graph_set(result.operation_graphs) == {
        (_TEST, _OUTER),
        (_OUTER, _INNER),
    }


def test_inner_chained_action_occupied_requirement_propagates(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """/inner requires position<item> occupied. /outer triggers /inner without filling it.

    The OCCUPIED requirement propagates from /inner through /outer to /test.
    /test doesn't fill position<item> either, so the diagnostic appears at /test.
    """
    result = validate_project_with_reference_graph(
        {
            "inner.dfn": (
                "define the potential action<my.domain.com:my_lib:/inner> {\n"
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
            "outer.dfn": (
                "define the potential action<my.domain.com:my_lib:/outer> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<iface> {\n"
                "        it may only contain particles where {\n"
                "            it has the action</inner>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<iface>::action</inner>::position<trigger_pos>.\n"
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
                "        create a particle in position<box>.\n"
                "        create a particle in position<box>::action</outer>::position<iface>.\n"
                "        create a particle in position<box>::action</outer>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.InferredRequirementViolationDiagnostic)
    assert all_diags[0].location.line == 13
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].action_name == "action<my.domain.com:my_lib:/outer>"
    assert all_diags[0].required_empty is False
    assert (
        all_diags[0].position_name
        == "position<box>::action</outer>::position<iface>::action</inner>::position<item>"
    )
    assert_propagation_chain(
        all_diags[0],
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _TEST,
            "triggered_quality_name": _OUTER,
            "line": 13,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _OUTER,
            "triggered_quality_name": _INNER,
            "line": 11,
            "column": 30,
            "file_path": "outer.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": _INNER,
            "triggered_quality_name": None,
            "line": 8,
            "column": 30,
            "file_path": "inner.dfn",
        },
    )
    assert action_graph_set(result.operation_graphs) == {
        (_TEST, _OUTER),
        (_OUTER, _INNER),
    }


def test_inner_chained_action_occupied_requirement_caller_fills(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """/outer triggers /inner without filling position<item> in its own code.

    The OCCUPIED requirement propagates through /outer to /test. /test fills
    position<item> through the chained name, satisfying the propagated requirement.
    """
    result = validate_project_with_reference_graph(
        {
            "inner.dfn": (
                "define the potential action<my.domain.com:my_lib:/inner> {\n"
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
            "outer.dfn": (
                "define the potential action<my.domain.com:my_lib:/outer> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<iface> {\n"
                "        it may only contain particles where {\n"
                "            it has the action</inner>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<iface>::action</inner>::position<trigger_pos>.\n"
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
                "        create a particle in position<box>.\n"
                "        create a particle in position<box>::action</outer>::position<iface>.\n"
                "        create a particle in position<box>::action</outer>::position<iface>::action</inner>::position<item>.\n"
                "        create a particle in position<box>::action</outer>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    assert_no_errors(result.program_result)
    assert action_graph_set(result.operation_graphs) == {
        (_TEST, _OUTER),
        (_OUTER, _INNER),
    }


def test_doubly_nested_action_requirement_propagates(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """Three levels of nesting: /test triggers /outer, /outer triggers /middle, /middle triggers /inner.

    /inner requires position<item> to be empty. Each intermediate has a non-trigger
    interface position with the inner action as a constraint. /outer fills
    position<mid_iface> before triggering /middle (satisfying /middle's OCCUPIED
    requirement), which infers EMPTY on position<mid_iface> in /outer's contract.
    The EMPTY requirement on position<item> propagates through /middle and /outer to
    /test. The test pre-fills both position<mid_iface> and position<item>, producing
    two EMPTY violations.
    """
    result = validate_project_with_reference_graph(
        {
            "inner.dfn": (
                "define the potential action<my.domain.com:my_lib:/inner> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<item>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<item>.\n"
                "    }\n"
                "}\n"
            ),
            "middle.dfn": (
                "define the potential action<my.domain.com:my_lib:/middle> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<mid_iface> {\n"
                "        it may only contain particles where {\n"
                "            it has the action</inner>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<mid_iface>::action</inner>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
            "outer.dfn": (
                "define the potential action<my.domain.com:my_lib:/outer> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<out_iface> {\n"
                "        it may only contain particles where {\n"
                "            it has the action</middle>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<out_iface>::action</middle>::position<mid_iface>.\n"
                "        create a particle in position<out_iface>::action</middle>::position<trigger_pos>.\n"
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
                "        create a particle in position<box>.\n"
                "        create a particle in position<box>::action</outer>::position<out_iface>.\n"
                "        create a particle in position<box>::action</outer>::position<out_iface>::action</middle>::position<mid_iface>.\n"
                "        create a particle in position<box>::action</outer>::position<out_iface>::action</middle>::position<mid_iface>::action</inner>::position<item>.\n"
                "        create a particle in position<box>::action</outer>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 2
    # /test fills position<mid_iface> which /outer requires empty (it creates there)
    assert isinstance(all_diags[0], diagnostics.InferredRequirementViolationDiagnostic)
    assert all_diags[0].location.line == 15
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].required_empty is True
    assert all_diags[0].action_name == "action<my.domain.com:my_lib:/outer>"
    assert (
        all_diags[0].position_name
        == "position<box>::action</outer>::position<out_iface>::action</middle>::position<mid_iface>"
    )
    assert_propagation_chain(
        all_diags[0],
        {
            "kind": action_contract.PropagationKind.FILL_SITE,
            "enclosing_quality_name": "position<box>::action</outer>::position<out_iface>::action</middle>::position<mid_iface>",
            "triggered_quality_name": None,
            "line": 13,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _TEST,
            "triggered_quality_name": _OUTER,
            "line": 15,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": _OUTER,
            "triggered_quality_name": None,
            "line": 11,
            "column": 30,
            "file_path": "outer.dfn",
        },
    )
    # /test fills position<item> which /inner requires empty (propagated through /middle and /outer)
    assert isinstance(all_diags[1], diagnostics.InferredRequirementViolationDiagnostic)
    assert all_diags[1].location.line == 15
    assert all_diags[1].location.column == 30
    assert all_diags[1].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[1].required_empty is True
    assert all_diags[1].action_name == "action<my.domain.com:my_lib:/outer>"
    assert (
        all_diags[1].position_name
        == "position<box>::action</outer>::position<out_iface>::action</middle>::position<mid_iface>::action</inner>::position<item>"
    )
    assert_propagation_chain(
        all_diags[1],
        {
            "kind": action_contract.PropagationKind.FILL_SITE,
            "enclosing_quality_name": "position<box>::action</outer>::position<out_iface>::action</middle>::position<mid_iface>::action</inner>::position<item>",
            "triggered_quality_name": None,
            "line": 14,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _TEST,
            "triggered_quality_name": _OUTER,
            "line": 15,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _OUTER,
            "triggered_quality_name": _MIDDLE,
            "line": 12,
            "column": 30,
            "file_path": "outer.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _MIDDLE,
            "triggered_quality_name": _INNER,
            "line": 11,
            "column": 30,
            "file_path": "middle.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": _INNER,
            "triggered_quality_name": None,
            "line": 7,
            "column": 30,
            "file_path": "inner.dfn",
        },
    )
    assert action_graph_set(result.operation_graphs) == {
        (_MIDDLE, _INNER),
        (_TEST, _OUTER),
        (_OUTER, _MIDDLE),
    }


def test_four_deep_action_chain_requirement_propagates(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """Four levels of nesting: /a triggers /b, /b triggers /c, /c triggers /d.

    /d requires position<item> to be empty (its first reference is a create). Each
    intermediate action just triggers the next one. The test action pre-fills the deeply
    nested position<item> before triggering /a, and this violation is detected because
    /d's requirement propagates through /c, /b, and /a to the test action.
    """
    result = validate_project_with_reference_graph(
        {
            "d.dfn": (
                "define the potential action<my.domain.com:my_lib:/d> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<item>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<item>.\n"
                "    }\n"
                "}\n"
            ),
            "c.dfn": (
                "define the potential action<my.domain.com:my_lib:/c> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<c_iface> {\n"
                "        it may only contain particles where {\n"
                "            it has the action</d>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<c_iface>::action</d>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
            "b.dfn": (
                "define the potential action<my.domain.com:my_lib:/b> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<b_iface> {\n"
                "        it may only contain particles where {\n"
                "            it has the action</c>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<b_iface>::action</c>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
            "a.dfn": (
                "define the potential action<my.domain.com:my_lib:/a> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<a_iface> {\n"
                "        it may only contain particles where {\n"
                "            it has the action</b>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<a_iface>::action</b>::position<trigger_pos>.\n"
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
                "                it has the action</a>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<box>::action</a>::position<a_iface>.\n"
                "        create a particle in position<box>::action</a>::position<a_iface>::action</b>::position<b_iface>.\n"
                "        create a particle in position<box>::action</a>::position<a_iface>::action</b>::position<b_iface>::action</c>::position<c_iface>.\n"
                "        create a particle in position<box>::action</a>::position<a_iface>::action</b>::position<b_iface>::action</c>::position<c_iface>::action</d>::position<item>.\n"
                "        create a particle in position<box>::action</a>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.InferredRequirementViolationDiagnostic)
    assert all_diags[0].location.line == 16
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].required_empty is True
    assert all_diags[0].action_name == "action<my.domain.com:my_lib:/a>"
    assert (
        all_diags[0].position_name
        == "position<box>::action</a>::position<a_iface>::action</b>::position<b_iface>::action</c>::position<c_iface>::action</d>::position<item>"
    )
    assert_propagation_chain(
        all_diags[0],
        {
            "kind": action_contract.PropagationKind.FILL_SITE,
            "enclosing_quality_name": "position<box>::action</a>::position<a_iface>::action</b>::position<b_iface>::action</c>::position<c_iface>::action</d>::position<item>",
            "triggered_quality_name": None,
            "line": 15,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _TEST,
            "triggered_quality_name": "action<my.domain.com:my_lib:/a>",
            "line": 16,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/a>",
            "triggered_quality_name": "action<my.domain.com:my_lib:/b>",
            "line": 11,
            "column": 30,
            "file_path": "a.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/b>",
            "triggered_quality_name": "action<my.domain.com:my_lib:/c>",
            "line": 11,
            "column": 30,
            "file_path": "b.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/c>",
            "triggered_quality_name": "action<my.domain.com:my_lib:/d>",
            "line": 11,
            "column": 30,
            "file_path": "c.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/d>",
            "triggered_quality_name": None,
            "line": 7,
            "column": 30,
            "file_path": "d.dfn",
        },
    )
    assert action_graph_set(result.operation_graphs) == {
        ("action<my.domain.com:my_lib:/c>", "action<my.domain.com:my_lib:/d>"),
        (_TEST, "action<my.domain.com:my_lib:/a>"),
        ("action<my.domain.com:my_lib:/a>", "action<my.domain.com:my_lib:/b>"),
        ("action<my.domain.com:my_lib:/b>", "action<my.domain.com:my_lib:/c>"),
    }


def test_both_requirements_propagate_when_inner_has_both(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """Inner action has two requirements: position<src> OCCUPIED and position<dest> EMPTY.

    /outer triggers /inner without filling position<src>, but /test fills
    position<src> so the OCCUPIED requirement is satisfied at the top level.
    The EMPTY requirement on position<dest> propagates, and /test pre-fills it,
    so /test gets an EMPTY violation. One diagnostic total.
    """
    result = validate_project_with_reference_graph(
        {
            "inner.dfn": (
                "define the potential action<my.domain.com:my_lib:/inner> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<src>.\n"
                "    define the position<dest>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        move the particle in position<src> to position<dest>.\n"
                "    }\n"
                "}\n"
            ),
            "outer.dfn": (
                "define the potential action<my.domain.com:my_lib:/outer> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<iface> {\n"
                "        it may only contain particles where {\n"
                "            it has the action</inner>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<iface>::action</inner>::position<trigger_pos>.\n"
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
                "        create a particle in position<box>.\n"
                "        create a particle in position<box>::action</outer>::position<iface>.\n"
                "        create a particle in position<box>::action</outer>::position<iface>::action</inner>::position<src>.\n"
                "        create a particle in position<box>::action</outer>::position<iface>::action</inner>::position<dest>.\n"
                "        create a particle in position<box>::action</outer>::position<trigger_pos>.\n"
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
    assert all_diags[0].required_empty is True
    assert (
        all_diags[0].position_name
        == "position<box>::action</outer>::position<iface>::action</inner>::position<dest>"
    )
    assert_propagation_chain(
        all_diags[0],
        {
            "kind": action_contract.PropagationKind.FILL_SITE,
            "enclosing_quality_name": "position<box>::action</outer>::position<iface>::action</inner>::position<dest>",
            "triggered_quality_name": None,
            "line": 14,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _TEST,
            "triggered_quality_name": _OUTER,
            "line": 15,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _OUTER,
            "triggered_quality_name": _INNER,
            "line": 11,
            "column": 30,
            "file_path": "outer.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": _INNER,
            "triggered_quality_name": None,
            "line": 8,
            "column": 47,
            "file_path": "inner.dfn",
        },
    )
    assert action_graph_set(result.operation_graphs) == {
        (_TEST, _OUTER),
        (_OUTER, _INNER),
    }


def test_trigger_position_child_empty_requirement_propagates(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """A requirement on a child of the trigger position propagates through the chain.

    /inner has a trigger position constrained with position</x>, and creates in
    position<trigger_pos>::position</x> (EMPTY requirement on that child). /outer
    triggers /inner via its interface position. The EMPTY requirement on the trigger
    position's child propagates to /outer's contract, and /test pre-fills it.
    """
    result = validate_project_with_reference_graph(
        {
            "x.dfn": "define the potential position<my.domain.com:my_lib:/x>.\n",
            "inner.dfn": (
                "define the potential action<my.domain.com:my_lib:/inner> {\n"
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
            "outer.dfn": (
                "define the potential action<my.domain.com:my_lib:/outer> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<iface> {\n"
                "        it may only contain particles where {\n"
                "            it has the action</inner>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<iface>::action</inner>::position<trigger_pos>.\n"
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
                "        create a particle in position<box>.\n"
                "        create a particle in position<box>::action</outer>::position<iface>.\n"
                "        create a particle in position<box>::action</outer>::position<iface>::action</inner>::position<trigger_pos>.\n"
                "        create a particle in position<box>::action</outer>::position<iface>::action</inner>::position<trigger_pos>::position</x>.\n"
                "        create a particle in position<box>::action</outer>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 3
    # Filling the nested trigger at line 13 fires /inner, which creates in
    # trigger_pos::position</x> via guarantee. Line 14 then tries to create
    # in the same position, which is already occupied.
    assert isinstance(all_diags[0], diagnostics.CreateInOccupiedPositionDiagnostic)
    assert all_diags[0].location.line == 14
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert (
        all_diags[0].position_name
        == "position<box>::action</outer>::position<iface>::action</inner>::position<trigger_pos>::position</x>"
    )
    # /test fills position<trigger_pos> which /outer requires empty (it creates there)
    assert isinstance(all_diags[1], diagnostics.InferredRequirementViolationDiagnostic)
    assert all_diags[1].location.line == 15
    assert all_diags[1].location.column == 30
    assert all_diags[1].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[1].required_empty is True
    assert all_diags[1].action_name == "action<my.domain.com:my_lib:/outer>"
    assert (
        all_diags[1].position_name
        == "position<box>::action</outer>::position<iface>::action</inner>::position<trigger_pos>"
    )
    assert_propagation_chain(
        all_diags[1],
        {
            "kind": action_contract.PropagationKind.FILL_SITE,
            "enclosing_quality_name": "position<box>::action</outer>::position<iface>::action</inner>::position<trigger_pos>",
            "triggered_quality_name": None,
            "line": 13,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _TEST,
            "triggered_quality_name": _OUTER,
            "line": 15,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": _OUTER,
            "triggered_quality_name": None,
            "line": 11,
            "column": 30,
            "file_path": "outer.dfn",
        },
    )
    # /test fills position<trigger_pos>::position</x> which /inner requires empty (propagated)
    assert isinstance(all_diags[2], diagnostics.InferredRequirementViolationDiagnostic)
    assert all_diags[2].location.line == 15
    assert all_diags[2].location.column == 30
    assert all_diags[2].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[2].required_empty is True
    assert all_diags[2].action_name == "action<my.domain.com:my_lib:/outer>"
    assert (
        all_diags[2].position_name
        == "position<box>::action</outer>::position<iface>::action</inner>::position<trigger_pos>::position</x>"
    )
    assert_propagation_chain(
        all_diags[2],
        {
            "kind": action_contract.PropagationKind.FILL_SITE,
            "enclosing_quality_name": "position<box>::action</outer>::position<iface>::action</inner>::position<trigger_pos>::position</x>",
            "triggered_quality_name": None,
            "line": 10,
            "column": 30,
            "file_path": "inner.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _TEST,
            "triggered_quality_name": _OUTER,
            "line": 15,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _OUTER,
            "triggered_quality_name": _INNER,
            "line": 11,
            "column": 30,
            "file_path": "outer.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": _INNER,
            "triggered_quality_name": None,
            "line": 10,
            "column": 30,
            "file_path": "inner.dfn",
        },
    )
    assert action_graph_set(result.operation_graphs) == {
        (_TEST, _INNER),
        (_TEST, _OUTER),
        (_OUTER, _INNER),
    }


def test_trigger_position_child_occupied_requirement_propagates(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "x.dfn": "define the potential position<my.domain.com:my_lib:/x>.\n",
            "inner.dfn": (
                "define the potential action<my.domain.com:my_lib:/inner> {\n"
                "    define the position<trigger_pos> {\n"
                "        it may only contain particles where {\n"
                "            it has the position</x>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        define the position<_sink>.\n"
                "        move the particle in position<trigger_pos>::position</x> to position<_sink>.\n"
                "    }\n"
                "}\n"
            ),
            "outer.dfn": (
                "define the potential action<my.domain.com:my_lib:/outer> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<iface> {\n"
                "        it may only contain particles where {\n"
                "            it has the action</inner>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        # Here we fail to fill inner's trigger_pos::/x.\n"
                "        create a particle in position<iface>::action</inner>::position<trigger_pos>.\n"
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
                "        create a particle in position<box>.\n"
                "        create a particle in position<box>::action</outer>::position<iface>.\n"
                "        create a particle in position<box>::action</outer>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.InferredRequirementViolationDiagnostic)
    assert all_diags[0].location.line == 13
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].required_empty is False
    assert all_diags[0].action_name == "action<my.domain.com:my_lib:/outer>"
    assert (
        all_diags[0].position_name
        == "position<box>::action</outer>::position<iface>::action</inner>::position<trigger_pos>::position</x>"
    )
    assert_propagation_chain(
        all_diags[0],
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _TEST,
            "triggered_quality_name": _OUTER,
            "line": 13,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _OUTER,
            "triggered_quality_name": _INNER,
            "line": 12,
            "column": 30,
            "file_path": "outer.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": _INNER,
            "triggered_quality_name": None,
            "line": 11,
            "column": 30,
            "file_path": "inner.dfn",
        },
    )


def test_inner_action_requirement_propagates_after_move(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """Requirement propagates even when the particle is moved to a local position before triggering.

    /outer moves the particle from position<iface> to position<local>, then triggers /inner
    via position<local>::action</inner>::position<trigger_pos>. Since /inner is a
    constraint on position<iface>, its requirements propagate through position<iface>.
    """
    result = validate_project_with_reference_graph(
        {
            "inner.dfn": (
                "define the potential action<my.domain.com:my_lib:/inner> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<item>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<item>.\n"
                "    }\n"
                "}\n"
            ),
            "outer.dfn": (
                "define the potential action<my.domain.com:my_lib:/outer> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<iface> {\n"
                "        it may only contain particles where {\n"
                "            it has the action</inner>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        define the position<local> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</inner>.\n"
                "            }\n"
                "        }\n"
                "        move the particle in position<iface> to position<local>.\n"
                "        create a particle in position<local>::action</inner>::position<trigger_pos>.\n"
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
                "        create a particle in position<box>.\n"
                "        create a particle in position<box>::action</outer>::position<iface>.\n"
                "        create a particle in position<box>::action</outer>::position<iface>::action</inner>::position<item>.\n"
                "        create a particle in position<box>::action</outer>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.InferredRequirementViolationDiagnostic)
    assert all_diags[0].location.line == 14
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].required_empty is True
    assert all_diags[0].action_name == "action<my.domain.com:my_lib:/outer>"
    assert (
        all_diags[0].position_name
        == "position<box>::action</outer>::position<iface>::action</inner>::position<item>"
    )
    assert_propagation_chain(
        all_diags[0],
        {
            "kind": action_contract.PropagationKind.FILL_SITE,
            "enclosing_quality_name": "position<box>::action</outer>::position<iface>::action</inner>::position<item>",
            "triggered_quality_name": None,
            "line": 13,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _TEST,
            "triggered_quality_name": _OUTER,
            "line": 14,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _OUTER,
            "triggered_quality_name": _INNER,
            "line": 17,
            "column": 30,
            "file_path": "outer.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": _INNER,
            "triggered_quality_name": None,
            "line": 7,
            "column": 30,
            "file_path": "inner.dfn",
        },
    )
    assert action_graph_set(result.operation_graphs) == {
        (_TEST, _OUTER),
        (_OUTER, _INNER),
    }


def test_doubly_nested_requirement_propagates_after_move(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """Three-level nesting where /middle moves its interface particle before triggering /inner.

    /middle moves the particle from position<mid_iface> to position<local>, then triggers
    /inner through position<local>::action</inner>::position<trigger_pos>. /inner's
    EMPTY requirement on position<item> should propagate through /middle and /outer
    to /test.
    """
    result = validate_project_with_reference_graph(
        {
            "inner.dfn": (
                "define the potential action<my.domain.com:my_lib:/inner> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<item>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<item>.\n"
                "    }\n"
                "}\n"
            ),
            "middle.dfn": (
                "define the potential action<my.domain.com:my_lib:/middle> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<mid_iface> {\n"
                "        it may only contain particles where {\n"
                "            it has the action</inner>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        define the position<local> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</inner>.\n"
                "            }\n"
                "        }\n"
                "        move the particle in position<mid_iface> to position<local>.\n"
                "        create a particle in position<local>::action</inner>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
            "outer.dfn": (
                "define the potential action<my.domain.com:my_lib:/outer> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<out_iface> {\n"
                "        it may only contain particles where {\n"
                "            it has the action</middle>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<out_iface>::action</middle>::position<mid_iface>.\n"
                "        create a particle in position<out_iface>::action</middle>::position<trigger_pos>.\n"
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
                "        create a particle in position<box>.\n"
                "        create a particle in position<box>::action</outer>::position<out_iface>.\n"
                "        create a particle in position<box>::action</outer>::position<out_iface>::action</middle>::position<mid_iface>.\n"
                "        create a particle in position<box>::action</outer>::position<out_iface>::action</middle>::position<mid_iface>::action</inner>::position<item>.\n"
                "        create a particle in position<box>::action</outer>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 2
    assert isinstance(all_diags[0], diagnostics.InferredRequirementViolationDiagnostic)
    assert all_diags[0].location.line == 15
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].required_empty is True
    assert all_diags[0].action_name == "action<my.domain.com:my_lib:/outer>"
    assert (
        all_diags[0].position_name
        == "position<box>::action</outer>::position<out_iface>::action</middle>::position<mid_iface>"
    )
    assert_propagation_chain(
        all_diags[0],
        {
            "kind": action_contract.PropagationKind.FILL_SITE,
            "enclosing_quality_name": "position<box>::action</outer>::position<out_iface>::action</middle>::position<mid_iface>",
            "triggered_quality_name": None,
            "line": 13,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _TEST,
            "triggered_quality_name": _OUTER,
            "line": 15,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": _OUTER,
            "triggered_quality_name": None,
            "line": 11,
            "column": 30,
            "file_path": "outer.dfn",
        },
    )
    assert isinstance(all_diags[1], diagnostics.InferredRequirementViolationDiagnostic)
    assert all_diags[1].location.line == 15
    assert all_diags[1].location.column == 30
    assert all_diags[1].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[1].required_empty is True
    assert all_diags[1].action_name == "action<my.domain.com:my_lib:/outer>"
    assert (
        all_diags[1].position_name
        == "position<box>::action</outer>::position<out_iface>::action</middle>::position<mid_iface>::action</inner>::position<item>"
    )
    assert_propagation_chain(
        all_diags[1],
        {
            "kind": action_contract.PropagationKind.FILL_SITE,
            "enclosing_quality_name": "position<box>::action</outer>::position<out_iface>::action</middle>::position<mid_iface>::action</inner>::position<item>",
            "triggered_quality_name": None,
            "line": 14,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _TEST,
            "triggered_quality_name": _OUTER,
            "line": 15,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _OUTER,
            "triggered_quality_name": _MIDDLE,
            "line": 12,
            "column": 30,
            "file_path": "outer.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _MIDDLE,
            "triggered_quality_name": _INNER,
            "line": 17,
            "column": 30,
            "file_path": "middle.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": _INNER,
            "triggered_quality_name": None,
            "line": 7,
            "column": 30,
            "file_path": "inner.dfn",
        },
    )
    assert action_graph_set(result.operation_graphs) == {
        (_MIDDLE, _INNER),
        (_TEST, _OUTER),
        (_OUTER, _MIDDLE),
    }


def test_no_propagation_when_action_not_triggered_on_interface_position(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """No propagation when the action is only triggered on a local position, not the interface.

    /outer has both position<iface> and position<local> constrained with action</inner>.
    It only triggers /inner through position<local>, not through position<iface>.
    Even though action</inner> is a constraint on position<iface>, the requirement
    should NOT propagate through it because /inner was never triggered on that path.
    The test pre-fills position<iface>::action</inner>::position<item> without a
    propagation error; iface's never-triggered action</inner> is itself dead code.
    """
    result = validate_project_with_reference_graph(
        {
            "inner.dfn": (
                "define the potential action<my.domain.com:my_lib:/inner> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<item>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<item>.\n"
                "    }\n"
                "}\n"
            ),
            "outer.dfn": (
                "define the potential action<my.domain.com:my_lib:/outer> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<iface> {\n"
                "        it may only contain particles where {\n"
                "            it has the action</inner>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        define the position<local> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</inner>.\n"
                "            }\n"
                "        }\n"
                "        destroy the particle in position<iface>.\n"
                "        create a particle in position<local>.\n"
                "        create a particle in position<local>::action</inner>::position<trigger_pos>.\n"
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
                "        create a particle in position<box>.\n"
                "        create a particle in position<box>::action</outer>::position<iface>.\n"
                "        create a particle in position<box>::action</outer>::position<iface>::action</inner>::position<item>.\n"
                "        create a particle in position<box>::action</outer>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.UntriggeredActionDiagnostic)
    assert all_diags[0].constraint_name == "action</inner>"
    assert all_diags[0].position_name == "position<iface>"
    assert all_diags[0].location.line == 5
    assert all_diags[0].location.column == 24
    assert all_diags[0].location.end_line == 5
    assert all_diags[0].location.end_column == 38
    assert all_diags[0].location.file_path == PurePosixPath("outer.dfn")
    assert action_graph_set(result.operation_graphs) == {
        (_TEST, _OUTER),
        (_OUTER, _INNER),
    }


_MAIN_FQUN = "mv:define-lang.org:main_lib"
_DEP_FQUN = "mv:define-lang.org:dep_lib"


def test_cross_fqun_inner_requirement_renders_correctly(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """Cross-FQUN scenario: the inner action and a position it references are in a different FQUN.

    /inner is in _DEP_FQUN, has position<item> constrained with position</x> (also in
    _DEP_FQUN), and creates in position<item>::position</x>. The propagated requirement's
    position_name should use the source form from /outer's code for the action reference
    (fully-qualified) and the source form from /inner's code for position</x>.
    """
    result = validate_project_with_reference_graph(
        {
            "lib/x.dfn": f"define the potential position<{_DEP_FQUN}:/x>.\n",
            "lib/inner.dfn": (
                f"define the potential action<{_DEP_FQUN}:/inner> {{\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<item> {\n"
                "        it may only contain particles where {\n"
                "            it has the position</x>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<item>::position</x>.\n"
                "    }\n"
                "}\n"
            ),
            "outer.dfn": (
                f"define the potential action<{_MAIN_FQUN}:/outer> {{\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<iface> {\n"
                "        it may only contain particles where {\n"
                f"            it has the action<{_DEP_FQUN}:/inner>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                f"        create a particle in position<iface>::action<{_DEP_FQUN}:/inner>::position<item>.\n"
                f"        create a particle in position<iface>::action<{_DEP_FQUN}:/inner>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                f"define the potential action<{_MAIN_FQUN}:/test> {{\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</outer>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<box>::action</outer>::position<iface>.\n"
                f"        create a particle in position<box>::action</outer>::position<iface>::action<{_DEP_FQUN}:/inner>::position<item>.\n"
                f"        create a particle in position<box>::action</outer>::position<iface>::action<{_DEP_FQUN}:/inner>::position<item>::position<{_DEP_FQUN}:/x>.\n"
                "        create a particle in position<box>::action</outer>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
        },
        universe_name=_MAIN_FQUN,
        local_deps={_DEP_FQUN: "lib"},
        sub_roots={"lib": _DEP_FQUN},
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 2
    # /test fills position<item> which /outer requires empty (it creates there)
    assert isinstance(all_diags[0], diagnostics.InferredRequirementViolationDiagnostic)
    assert all_diags[0].location.line == 15
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].required_empty is True
    assert all_diags[0].action_name == f"action<{_MAIN_FQUN}:/outer>"
    assert (
        all_diags[0].position_name
        == f"position<box>::action</outer>::position<iface>::action<{_DEP_FQUN}:/inner>::position<item>"
    )
    assert_propagation_chain(
        all_diags[0],
        {
            "kind": action_contract.PropagationKind.FILL_SITE,
            "enclosing_quality_name": f"position<box>::action</outer>::position<iface>::action<{_DEP_FQUN}:/inner>::position<item>",
            "triggered_quality_name": None,
            "line": 13,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": f"action<{_MAIN_FQUN}:/test>",
            "triggered_quality_name": f"action<{_MAIN_FQUN}:/outer>",
            "line": 15,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": f"action<{_MAIN_FQUN}:/outer>",
            "triggered_quality_name": None,
            "line": 11,
            "column": 30,
            "file_path": "outer.dfn",
        },
    )
    # /test fills position<item>::position</x> which /inner requires empty (propagated)
    assert isinstance(all_diags[1], diagnostics.InferredRequirementViolationDiagnostic)
    assert all_diags[1].location.line == 15
    assert all_diags[1].location.column == 30
    assert all_diags[1].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[1].required_empty is True
    assert all_diags[1].action_name == f"action<{_MAIN_FQUN}:/outer>"
    assert (
        all_diags[1].position_name
        == f"position<box>::action</outer>::position<iface>::action<{_DEP_FQUN}:/inner>::position<item>::position<{_DEP_FQUN}:/x>"
    )
    assert_propagation_chain(
        all_diags[1],
        {
            "kind": action_contract.PropagationKind.FILL_SITE,
            "enclosing_quality_name": f"position<box>::action</outer>::position<iface>::action<{_DEP_FQUN}:/inner>::position<item>::position<{_DEP_FQUN}:/x>",
            "triggered_quality_name": None,
            "line": 14,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": f"action<{_MAIN_FQUN}:/test>",
            "triggered_quality_name": f"action<{_MAIN_FQUN}:/outer>",
            "line": 15,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": f"action<{_MAIN_FQUN}:/outer>",
            "triggered_quality_name": f"action<{_DEP_FQUN}:/inner>",
            "line": 12,
            "column": 30,
            "file_path": "outer.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": f"action<{_DEP_FQUN}:/inner>",
            "triggered_quality_name": None,
            "line": 11,
            "column": 30,
            "file_path": "lib/inner.dfn",
        },
    )
    assert action_graph_set(result.operation_graphs) == {
        (f"action<{_MAIN_FQUN}:/test>", f"action<{_MAIN_FQUN}:/outer>"),
        (f"action<{_MAIN_FQUN}:/outer>", f"action<{_DEP_FQUN}:/inner>"),
    }


def test_cross_fqun_occupied_requirement_propagates(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """Cross-FQUN OCCUPIED propagation: /inner is in _DEP_FQUN with position</x>.

    /inner moves from position<item>::position</x>, creating an OCCUPIED requirement
    on position<item>::position</x>. This requirement propagates through /outer to
    /test. /test fills it, satisfying the requirement.
    """
    result = validate_project_with_reference_graph(
        {
            "lib/x.dfn": f"define the potential position<{_DEP_FQUN}:/x>.\n",
            "lib/inner.dfn": (
                f"define the potential action<{_DEP_FQUN}:/inner> {{\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<item> {\n"
                "        it may only contain particles where {\n"
                "            it has the position</x>.\n"
                "        }\n"
                "    }\n"
                "    define the position<dest>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        move the particle in position<item>::position</x> to position<dest>.\n"
                "    }\n"
                "}\n"
            ),
            "outer.dfn": (
                f"define the potential action<{_MAIN_FQUN}:/outer> {{\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<iface> {\n"
                "        it may only contain particles where {\n"
                f"            it has the action<{_DEP_FQUN}:/inner>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                f"        create a particle in position<iface>::action<{_DEP_FQUN}:/inner>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                f"define the potential action<{_MAIN_FQUN}:/test> {{\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</outer>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<box>::action</outer>::position<iface>.\n"
                f"        create a particle in position<box>::action</outer>::position<iface>::action<{_DEP_FQUN}:/inner>::position<item>.\n"
                f"        create a particle in position<box>::action</outer>::position<iface>::action<{_DEP_FQUN}:/inner>::position<item>::position<{_DEP_FQUN}:/x>.\n"
                "        create a particle in position<box>::action</outer>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
        },
        universe_name=_MAIN_FQUN,
        local_deps={_DEP_FQUN: "lib"},
        sub_roots={"lib": _DEP_FQUN},
    )
    assert_no_errors(result.program_result)
    assert action_graph_set(result.operation_graphs) == {
        (f"action<{_MAIN_FQUN}:/test>", f"action<{_MAIN_FQUN}:/outer>"),
        (f"action<{_MAIN_FQUN}:/outer>", f"action<{_DEP_FQUN}:/inner>"),
    }


def test_cross_fqun_occupied_requirement_violated(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """Cross-FQUN OCCUPIED violation: /inner is in _DEP_FQUN with position</x>.

    /inner moves from position<item>::position</x>, creating OCCUPIED requirements
    on position<item> and position<item>::position</x>. These propagate through
    /outer to /test. /test fills position<item> but not position<item>::position</x>.
    """
    result = validate_project_with_reference_graph(
        {
            "lib/x.dfn": f"define the potential position<{_DEP_FQUN}:/x>.\n",
            "lib/inner.dfn": (
                f"define the potential action<{_DEP_FQUN}:/inner> {{\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<item> {\n"
                "        it may only contain particles where {\n"
                "            it has the position</x>.\n"
                "        }\n"
                "    }\n"
                "    define the position<dest>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        move the particle in position<item>::position</x> to position<dest>.\n"
                "    }\n"
                "}\n"
            ),
            "outer.dfn": (
                f"define the potential action<{_MAIN_FQUN}:/outer> {{\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<iface> {\n"
                "        it may only contain particles where {\n"
                f"            it has the action<{_DEP_FQUN}:/inner>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                f"        create a particle in position<iface>::action<{_DEP_FQUN}:/inner>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                f"define the potential action<{_MAIN_FQUN}:/test> {{\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</outer>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<box>::action</outer>::position<iface>.\n"
                f"        create a particle in position<box>::action</outer>::position<iface>::action<{_DEP_FQUN}:/inner>::position<item>.\n"
                "        create a particle in position<box>::action</outer>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
        },
        universe_name=_MAIN_FQUN,
        local_deps={_DEP_FQUN: "lib"},
        sub_roots={"lib": _DEP_FQUN},
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.InferredRequirementViolationDiagnostic)
    assert all_diags[0].location.line == 14
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].required_empty is False
    assert all_diags[0].action_name == f"action<{_MAIN_FQUN}:/outer>"
    assert (
        all_diags[0].position_name
        == f"position<box>::action</outer>::position<iface>::action<{_DEP_FQUN}:/inner>::position<item>::position<{_DEP_FQUN}:/x>"
    )
    assert_propagation_chain(
        all_diags[0],
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": f"action<{_MAIN_FQUN}:/test>",
            "triggered_quality_name": f"action<{_MAIN_FQUN}:/outer>",
            "line": 14,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": f"action<{_MAIN_FQUN}:/outer>",
            "triggered_quality_name": f"action<{_DEP_FQUN}:/inner>",
            "line": 11,
            "column": 30,
            "file_path": "outer.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": f"action<{_DEP_FQUN}:/inner>",
            "triggered_quality_name": None,
            "line": 12,
            "column": 30,
            "file_path": "lib/inner.dfn",
        },
    )
    assert action_graph_set(result.operation_graphs) == {
        (f"action<{_MAIN_FQUN}:/test>", f"action<{_MAIN_FQUN}:/outer>"),
        (f"action<{_MAIN_FQUN}:/outer>", f"action<{_DEP_FQUN}:/inner>"),
    }


def test_complex_chain_same_fqun_position_name(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """A deeply-chained trigger path through nested actions in the same FQUN.

    /test triggers /foo through position<local>::position</x>::action</foo>::position<trigger_pos>.
    /foo triggers /middle through position<iface>::action</middle>::position<trigger_pos>.
    /middle triggers /bar through position<mid_iface>::action</bar>::position<trigger_pos>.
    /bar requires position<item> to be empty. The propagated position_name should be:
    position<local>::position</x>::action</foo>::position<iface>::action</middle>::position<mid_iface>::action</bar>::position<item>
    """
    result = validate_project_with_reference_graph(
        {
            "x.dfn": (
                "define the potential position<my.domain.com:my_lib:/x> {\n"
                "    it may only contain particles where {\n"
                "        it has the action</foo>.\n"
                "    }\n"
                "}\n"
            ),
            "foo.dfn": (
                "define the potential action<my.domain.com:my_lib:/foo> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<iface> {\n"
                "        it may only contain particles where {\n"
                "            it has the action</middle>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<iface>::action</middle>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
            "middle.dfn": (
                "define the potential action<my.domain.com:my_lib:/middle> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<mid_iface> {\n"
                "        it may only contain particles where {\n"
                "            it has the action</bar>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<mid_iface>::action</bar>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
            "bar.dfn": (
                "define the potential action<my.domain.com:my_lib:/bar> {\n"
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
                "        define the position<local> {\n"
                "            it may only contain particles where {\n"
                "                it has the position</x>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<local>.\n"
                "        create a particle in position<local>::position</x>.\n"
                "        create a particle in position<local>::position</x>::action</foo>::position<iface>.\n"
                "        create a particle in position<local>::position</x>::action</foo>::position<iface>::action</middle>::position<mid_iface>.\n"
                "        create a particle in position<local>::position</x>::action</foo>::position<iface>::action</middle>::position<mid_iface>::action</bar>::position<item>.\n"
                "        create a particle in position<local>::position</x>::action</foo>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.InferredRequirementViolationDiagnostic)
    assert all_diags[0].location.line == 16
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].required_empty is True
    assert all_diags[0].action_name == "action<my.domain.com:my_lib:/foo>"
    assert (
        all_diags[0].position_name
        == "position<local>::position</x>::action</foo>::position<iface>::action</middle>::position<mid_iface>::action</bar>::position<item>"
    )
    assert_propagation_chain(
        all_diags[0],
        {
            "kind": action_contract.PropagationKind.FILL_SITE,
            "enclosing_quality_name": "position<local>::position</x>::action</foo>::position<iface>::action</middle>::position<mid_iface>::action</bar>::position<item>",
            "triggered_quality_name": None,
            "line": 15,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _TEST,
            "triggered_quality_name": "action<my.domain.com:my_lib:/foo>",
            "line": 16,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/foo>",
            "triggered_quality_name": _MIDDLE,
            "line": 11,
            "column": 30,
            "file_path": "foo.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _MIDDLE,
            "triggered_quality_name": "action<my.domain.com:my_lib:/bar>",
            "line": 11,
            "column": 30,
            "file_path": "middle.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/bar>",
            "triggered_quality_name": None,
            "line": 7,
            "column": 30,
            "file_path": "bar.dfn",
        },
    )
    assert action_graph_set(result.operation_graphs) == {
        ("action<my.domain.com:my_lib:/foo>", _MIDDLE),
        (_TEST, "action<my.domain.com:my_lib:/foo>"),
        (_MIDDLE, "action<my.domain.com:my_lib:/bar>"),
    }


def test_complex_chain_cross_fqun_position_name(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """Same structure as the same-FQUN complex chain, but /bar lives in a different FQUN.

    /bar is in dep_lib and has an interface position with a constraint on position</x>,
    requiring position<item>::position</x> to be empty. /middle fills /bar's
    position<item> to satisfy the occupied requirement. The propagated position_name
    should render /bar and its positions with canonical FQUN names:
    position<local>::position</x>::action</foo>::position<iface>::action</middle>::position<mid_iface>::action<dep_fqun:/bar>::position<item>::position<dep_fqun:/x>
    """
    result = validate_project_with_reference_graph(
        {
            "x.dfn": (
                f"define the potential position<{_MAIN_FQUN}:/x> {{\n"
                "    it may only contain particles where {\n"
                "        it has the action</foo>.\n"
                "    }\n"
                "}\n"
            ),
            "lib/x.dfn": f"define the potential position<{_DEP_FQUN}:/x>.\n",
            "lib/bar.dfn": (
                f"define the potential action<{_DEP_FQUN}:/bar> {{\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<item> {\n"
                "        it may only contain particles where {\n"
                "            it has the position</x>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<item>::position</x>.\n"
                "    }\n"
                "}\n"
            ),
            "middle.dfn": (
                f"define the potential action<{_MAIN_FQUN}:/middle> {{\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<mid_iface> {\n"
                "        it may only contain particles where {\n"
                f"            it has the action<{_DEP_FQUN}:/bar>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                f"        create a particle in position<mid_iface>::action<{_DEP_FQUN}:/bar>::position<item>.\n"
                f"        create a particle in position<mid_iface>::action<{_DEP_FQUN}:/bar>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
            "foo.dfn": (
                f"define the potential action<{_MAIN_FQUN}:/foo> {{\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<iface> {\n"
                "        it may only contain particles where {\n"
                "            it has the action</middle>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<iface>::action</middle>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                f"define the potential action<{_MAIN_FQUN}:/test> {{\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<local> {\n"
                "            it may only contain particles where {\n"
                "                it has the position</x>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<local>.\n"
                "        create a particle in position<local>::position</x>.\n"
                "        create a particle in position<local>::position</x>::action</foo>::position<iface>.\n"
                "        create a particle in position<local>::position</x>::action</foo>::position<iface>::action</middle>::position<mid_iface>.\n"
                f"        create a particle in position<local>::position</x>::action</foo>::position<iface>::action</middle>::position<mid_iface>::action<{_DEP_FQUN}:/bar>::position<item>.\n"
                f"        create a particle in position<local>::position</x>::action</foo>::position<iface>::action</middle>::position<mid_iface>::action<{_DEP_FQUN}:/bar>::position<item>::position<{_DEP_FQUN}:/x>.\n"
                "        create a particle in position<local>::position</x>::action</foo>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
        },
        universe_name=_MAIN_FQUN,
        local_deps={_DEP_FQUN: "lib"},
        sub_roots={"lib": _DEP_FQUN},
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 2
    assert isinstance(all_diags[0], diagnostics.InferredRequirementViolationDiagnostic)
    assert all_diags[0].location.line == 17
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].required_empty is True
    assert all_diags[0].action_name == f"action<{_MAIN_FQUN}:/foo>"
    assert (
        all_diags[0].position_name
        == f"position<local>::position</x>::action</foo>::position<iface>::action</middle>::position<mid_iface>::action<{_DEP_FQUN}:/bar>::position<item>"
    )
    assert_propagation_chain(
        all_diags[0],
        {
            "kind": action_contract.PropagationKind.FILL_SITE,
            "enclosing_quality_name": f"position<local>::position</x>::action</foo>::position<iface>::action</middle>::position<mid_iface>::action<{_DEP_FQUN}:/bar>::position<item>",
            "triggered_quality_name": None,
            "line": 15,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": f"action<{_MAIN_FQUN}:/test>",
            "triggered_quality_name": f"action<{_MAIN_FQUN}:/foo>",
            "line": 17,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": f"action<{_MAIN_FQUN}:/foo>",
            "triggered_quality_name": f"action<{_MAIN_FQUN}:/middle>",
            "line": 11,
            "column": 30,
            "file_path": "foo.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": f"action<{_MAIN_FQUN}:/middle>",
            "triggered_quality_name": None,
            "line": 11,
            "column": 30,
            "file_path": "middle.dfn",
        },
    )
    assert isinstance(all_diags[1], diagnostics.InferredRequirementViolationDiagnostic)
    assert all_diags[1].location.line == 17
    assert all_diags[1].location.column == 30
    assert all_diags[1].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[1].required_empty is True
    assert all_diags[1].action_name == f"action<{_MAIN_FQUN}:/foo>"
    assert (
        all_diags[1].position_name
        == f"position<local>::position</x>::action</foo>::position<iface>::action</middle>::position<mid_iface>::action<{_DEP_FQUN}:/bar>::position<item>::position<{_DEP_FQUN}:/x>"
    )
    assert_propagation_chain(
        all_diags[1],
        {
            "kind": action_contract.PropagationKind.FILL_SITE,
            "enclosing_quality_name": f"position<local>::position</x>::action</foo>::position<iface>::action</middle>::position<mid_iface>::action<{_DEP_FQUN}:/bar>::position<item>::position<{_DEP_FQUN}:/x>",
            "triggered_quality_name": None,
            "line": 16,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": f"action<{_MAIN_FQUN}:/test>",
            "triggered_quality_name": f"action<{_MAIN_FQUN}:/foo>",
            "line": 17,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": f"action<{_MAIN_FQUN}:/foo>",
            "triggered_quality_name": f"action<{_MAIN_FQUN}:/middle>",
            "line": 11,
            "column": 30,
            "file_path": "foo.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": f"action<{_MAIN_FQUN}:/middle>",
            "triggered_quality_name": f"action<{_DEP_FQUN}:/bar>",
            "line": 12,
            "column": 30,
            "file_path": "middle.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": f"action<{_DEP_FQUN}:/bar>",
            "triggered_quality_name": None,
            "line": 11,
            "column": 30,
            "file_path": "lib/bar.dfn",
        },
    )
    assert action_graph_set(result.operation_graphs) == {
        (f"action<{_MAIN_FQUN}:/test>", f"action<{_MAIN_FQUN}:/foo>"),
        (f"action<{_MAIN_FQUN}:/foo>", f"action<{_MAIN_FQUN}:/middle>"),
        (f"action<{_MAIN_FQUN}:/middle>", f"action<{_DEP_FQUN}:/bar>"),
    }


def test_move_carried_child_satisfies_inner_occupied_requirement(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """A move that carries </parent> into inner::input should satisfy inner's occupied requirement on it."""
    result = validate_project_with_reference_graph(
        {
            "a.dfn": "define the potential position<my.domain.com:my_lib:/a>.\n",
            "b.dfn": "define the potential position<my.domain.com:my_lib:/b>.\n",
            "parent.dfn": (
                "define the potential position<my.domain.com:my_lib:/parent> {\n"
                "    it may only contain particles where {\n"
                "        it has the position</a>.\n"
                "        it has the position</b>.\n"
                "    }\n"
                "}\n"
            ),
            "inner.dfn": (
                "define the potential action<my.domain.com:my_lib:/inner> {\n"
                "    define the position<run>.\n"
                "    define the position<input> {\n"
                "        it may only contain particles where {\n"
                "            it has the position</parent>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<input>::position</parent>::position</a>.\n"
                "        create a particle in position<input>::position</parent>::position</b>.\n"
                "    }\n"
                "}\n"
            ),
            "middle.dfn": (
                "define the potential action<my.domain.com:my_lib:/middle> {\n"
                "    define the position<run>.\n"
                "    define the position<iface> {\n"
                "        it may only contain particles where {\n"
                "            it has the position</parent>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<gw> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</inner>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<gw>.\n"
                "        move the particle in position<iface> to position<gw>::action</inner>::position<input>.\n"
                "        create a particle in position<gw>::action</inner>::position<run>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    define the position<mw> {\n"
                "        it may only contain particles where {\n"
                "            it has the action</middle>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<mw>.\n"
                "        create a particle in position<mw>::action</middle>::position<iface>.\n"
                "        create a particle in position<mw>::action</middle>::position<iface>::position</parent>.\n"
                "        create a particle in position<mw>::action</middle>::position<run>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    assert_no_errors(result.program_result)


def test_move_without_the_carried_child_violates_inner_occupied_requirement(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """The moved iface lacks </parent>, so inner's occupied requirement on it is genuinely violated."""
    result = validate_project_with_reference_graph(
        {
            "a.dfn": "define the potential position<my.domain.com:my_lib:/a>.\n",
            "b.dfn": "define the potential position<my.domain.com:my_lib:/b>.\n",
            "parent.dfn": (
                "define the potential position<my.domain.com:my_lib:/parent> {\n"
                "    it may only contain particles where {\n"
                "        it has the position</a>.\n"
                "        it has the position</b>.\n"
                "    }\n"
                "}\n"
            ),
            "inner.dfn": (
                "define the potential action<my.domain.com:my_lib:/inner> {\n"
                "    define the position<run>.\n"
                "    define the position<input> {\n"
                "        it may only contain particles where {\n"
                "            it has the position</parent>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<input>::position</parent>::position</a>.\n"
                "        create a particle in position<input>::position</parent>::position</b>.\n"
                "    }\n"
                "}\n"
            ),
            "middle.dfn": (
                "define the potential action<my.domain.com:my_lib:/middle> {\n"
                "    define the position<run>.\n"
                "    define the position<iface> {\n"
                "        it may only contain particles where {\n"
                "            it has the position</parent>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<gw> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</inner>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<gw>.\n"
                "        move the particle in position<iface> to position<gw>::action</inner>::position<input>.\n"
                "        create a particle in position<gw>::action</inner>::position<run>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    define the position<mw> {\n"
                "        it may only contain particles where {\n"
                "            it has the action</middle>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<mw>.\n"
                "        create a particle in position<mw>::action</middle>::position<iface>.\n"
                "        create a particle in position<mw>::action</middle>::position<run>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.InferredRequirementViolationDiagnostic)
    # The moved iface carries no </parent>, and /middle recorded the missing
    # child as its requirement on iface::/parent, so the violation lands on
    # /test, which never fills it. The chain traces through the move to /inner's
    # inference.
    assert all_diags[0].location.line == 13
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.end_line == 13
    assert all_diags[0].location.end_column == 74
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].action_name == _MIDDLE
    assert all_diags[0].required_empty is False
    assert (
        all_diags[0].position_name
        == "position<mw>::action</middle>::position<iface>::position</parent>"
    )
    assert_propagation_chain(
        all_diags[0],
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _TEST,
            "triggered_quality_name": _MIDDLE,
            "line": 13,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _MIDDLE,
            "triggered_quality_name": _INNER,
            "line": 18,
            "column": 30,
            "file_path": "middle.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": _INNER,
            "triggered_quality_name": None,
            "line": 11,
            "column": 30,
            "file_path": "inner.dfn",
        },
    )
    assert action_graph_set(result.operation_graphs) == {
        (_TEST, _MIDDLE),
        (_MIDDLE, _INNER),
    }


def test_input_carried_through_two_moves_reaches_the_triggered_inner(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """A box carried by two moves into a triggered inner should satisfy inner's occupied requirement on its input."""
    result = validate_project_with_reference_graph(
        {
            "inner.dfn": (
                "define the potential action<my.domain.com:my_lib:/inner> {\n"
                "    define the position<input>.\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        destroy the particle in position<input>.\n"
                "    }\n"
                "}\n"
            ),
            "middle.dfn": (
                "define the potential action<my.domain.com:my_lib:/middle> {\n"
                "    define the position<input> {\n"
                "        it may only contain particles where {\n"
                "            it has the action</inner>.\n"
                "        }\n"
                "    }\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<input>::action</inner>::position<run>.\n"
                "    }\n"
                "}\n"
            ),
            "outer.dfn": (
                "define the potential action<my.domain.com:my_lib:/outer> {\n"
                "    define the position<input> {\n"
                "        it may only contain particles where {\n"
                "            it has the action</inner>.\n"
                "        }\n"
                "    }\n"
                "    define the position<middle_holder> {\n"
                "        it may only contain particles where {\n"
                "            it has the action</middle>.\n"
                "        }\n"
                "    }\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<middle_holder>.\n"
                "        move the particle in position<input> to position<middle_holder>::action</middle>::position<input>.\n"
                "        create a particle in position<middle_holder>::action</middle>::position<run>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<box> {\n"
                "        it may only contain particles where {\n"
                "            it has the action</inner>.\n"
                "        }\n"
                "    }\n"
                "    define the position<outer_holder> {\n"
                "        it may only contain particles where {\n"
                "            it has the action</outer>.\n"
                "        }\n"
                "    }\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<box>::action</inner>::position<input>.\n"
                "        create a particle in position<outer_holder>.\n"
                "        move the particle in position<box> to position<outer_holder>::action</outer>::position<input>.\n"
                "        create a particle in position<outer_holder>::action</outer>::position<run>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    assert_no_errors(result.program_result)


def test_two_moves_without_the_input_violate_the_triggered_inner(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """The box carried through two moves never had its input filled, so the triggered inner's occupied requirement is genuinely violated."""
    result = validate_project_with_reference_graph(
        {
            "inner.dfn": (
                "define the potential action<my.domain.com:my_lib:/inner> {\n"
                "    define the position<input>.\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        destroy the particle in position<input>.\n"
                "    }\n"
                "}\n"
            ),
            "middle.dfn": (
                "define the potential action<my.domain.com:my_lib:/middle> {\n"
                "    define the position<input> {\n"
                "        it may only contain particles where {\n"
                "            it has the action</inner>.\n"
                "        }\n"
                "    }\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<input>::action</inner>::position<run>.\n"
                "    }\n"
                "}\n"
            ),
            "outer.dfn": (
                "define the potential action<my.domain.com:my_lib:/outer> {\n"
                "    define the position<input> {\n"
                "        it may only contain particles where {\n"
                "            it has the action</inner>.\n"
                "        }\n"
                "    }\n"
                "    define the position<middle_holder> {\n"
                "        it may only contain particles where {\n"
                "            it has the action</middle>.\n"
                "        }\n"
                "    }\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<middle_holder>.\n"
                "        move the particle in position<input> to position<middle_holder>::action</middle>::position<input>.\n"
                "        create a particle in position<middle_holder>::action</middle>::position<run>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<box> {\n"
                "        it may only contain particles where {\n"
                "            it has the action</inner>.\n"
                "        }\n"
                "    }\n"
                "    define the position<outer_holder> {\n"
                "        it may only contain particles where {\n"
                "            it has the action</outer>.\n"
                "        }\n"
                "    }\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<outer_holder>.\n"
                "        move the particle in position<box> to position<outer_holder>::action</outer>::position<input>.\n"
                "        create a particle in position<outer_holder>::action</outer>::position<run>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.InferredRequirementViolationDiagnostic)
    # The box moved through /outer into /middle never had its input filled.
    # /outer recorded the missing child as its requirement on
    # input::/inner::input, so the violation lands on /test, which never fills
    # it. The chain traces through both moves to /inner's inference.
    assert all_diags[0].location.line == 19
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.end_line == 19
    assert all_diags[0].location.end_column == 83
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].action_name == _OUTER
    assert all_diags[0].required_empty is False
    assert (
        all_diags[0].position_name
        == "position<outer_holder>::action</outer>::position<input>::action</inner>::position<input>"
    )
    assert_propagation_chain(
        all_diags[0],
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _TEST,
            "triggered_quality_name": _OUTER,
            "line": 19,
            "column": 30,
            "file_path": "test.dfn",
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
            "line": 11,
            "column": 30,
            "file_path": "middle.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": _INNER,
            "triggered_quality_name": None,
            "line": 7,
            "column": 33,
            "file_path": "inner.dfn",
        },
    )
    assert action_graph_set(result.operation_graphs) == {
        (_TEST, _OUTER),
        (_OUTER, _MIDDLE),
        (_MIDDLE, _INNER),
    }


def test_input_carried_into_the_implied_middle_reaches_the_triggered_inner(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """Outer moves its input into a /middle implied on its own parent particle, so filling box's input in the caller satisfies the triggered inner."""
    result = validate_project_with_reference_graph(
        {
            "inner.dfn": (
                "define the potential action<my.domain.com:my_lib:/inner> {\n"
                "    define the position<input>.\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        destroy the particle in position<input>.\n"
                "    }\n"
                "}\n"
            ),
            "middle.dfn": (
                "define the potential action<my.domain.com:my_lib:/middle> {\n"
                "    define the position<input> {\n"
                "        it may only contain particles where {\n"
                "            it has the action</inner>.\n"
                "        }\n"
                "    }\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<input>::action</inner>::position<run>.\n"
                "    }\n"
                "}\n"
            ),
            "outer.dfn": (
                "define the potential action<my.domain.com:my_lib:/outer> {\n"
                "    it also assigns the action</middle>.\n"
                "    define the position<input> {\n"
                "        it may only contain particles where {\n"
                "            it has the action</inner>.\n"
                "        }\n"
                "    }\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        move the particle in position<input> to action</middle>::position<input>.\n"
                "        create a particle in action</middle>::position<run>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<box> {\n"
                "        it may only contain particles where {\n"
                "            it has the action</inner>.\n"
                "        }\n"
                "    }\n"
                "    define the position<outer_holder> {\n"
                "        it may only contain particles where {\n"
                "            it has the action</outer>.\n"
                "        }\n"
                "    }\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<box>::action</inner>::position<input>.\n"
                "        create a particle in position<outer_holder>.\n"
                "        move the particle in position<box> to position<outer_holder>::action</outer>::position<input>.\n"
                "        create a particle in position<outer_holder>::action</outer>::position<run>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    assert_no_errors(result.program_result)


def test_carrying_no_input_into_the_implied_middle_violates_the_triggered_inner(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """The box moved into a /middle implied on outer's parent particle never had its input filled, so the violation lands on the caller."""
    result = validate_project_with_reference_graph(
        {
            "inner.dfn": (
                "define the potential action<my.domain.com:my_lib:/inner> {\n"
                "    define the position<input>.\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        destroy the particle in position<input>.\n"
                "    }\n"
                "}\n"
            ),
            "middle.dfn": (
                "define the potential action<my.domain.com:my_lib:/middle> {\n"
                "    define the position<input> {\n"
                "        it may only contain particles where {\n"
                "            it has the action</inner>.\n"
                "        }\n"
                "    }\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<input>::action</inner>::position<run>.\n"
                "    }\n"
                "}\n"
            ),
            "outer.dfn": (
                "define the potential action<my.domain.com:my_lib:/outer> {\n"
                "    it also assigns the action</middle>.\n"
                "    define the position<input> {\n"
                "        it may only contain particles where {\n"
                "            it has the action</inner>.\n"
                "        }\n"
                "    }\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        move the particle in position<input> to action</middle>::position<input>.\n"
                "        create a particle in action</middle>::position<run>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<box> {\n"
                "        it may only contain particles where {\n"
                "            it has the action</inner>.\n"
                "        }\n"
                "    }\n"
                "    define the position<outer_holder> {\n"
                "        it may only contain particles where {\n"
                "            it has the action</outer>.\n"
                "        }\n"
                "    }\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<outer_holder>.\n"
                "        move the particle in position<box> to position<outer_holder>::action</outer>::position<input>.\n"
                "        create a particle in position<outer_holder>::action</outer>::position<run>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.InferredRequirementViolationDiagnostic)
    assert all_diags[0].location.line == 19
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.end_line == 19
    assert all_diags[0].location.end_column == 83
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].action_name == _OUTER
    assert all_diags[0].required_empty is False
    assert (
        all_diags[0].position_name
        == "position<outer_holder>::action</outer>::position<input>::action</inner>::position<input>"
    )
    assert_propagation_chain(
        all_diags[0],
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _TEST,
            "triggered_quality_name": _OUTER,
            "line": 19,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _OUTER,
            "triggered_quality_name": _MIDDLE,
            "line": 13,
            "column": 30,
            "file_path": "outer.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _MIDDLE,
            "triggered_quality_name": _INNER,
            "line": 11,
            "column": 30,
            "file_path": "middle.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": _INNER,
            "triggered_quality_name": None,
            "line": 7,
            "column": 33,
            "file_path": "inner.dfn",
        },
    )
    assert action_graph_set(result.operation_graphs) == {
        (_TEST, _OUTER),
        (_OUTER, _MIDDLE),
        (_MIDDLE, _INNER),
    }


def test_filled_carried_child_violates_inner_empty_requirement(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """Inner creates into a child the moved iface carries, so filling that child in the caller is reported."""
    result = validate_project_with_reference_graph(
        {
            "marker.dfn": (
                "define the potential position<my.domain.com:my_lib:/marker>.\n"
            ),
            "inner.dfn": (
                "define the potential action<my.domain.com:my_lib:/inner> {\n"
                "    define the position<run>.\n"
                "    define the position<input> {\n"
                "        it may only contain particles where {\n"
                "            it has the position</marker>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<input>::position</marker>.\n"
                "    }\n"
                "}\n"
            ),
            "middle.dfn": (
                "define the potential action<my.domain.com:my_lib:/middle> {\n"
                "    define the position<run>.\n"
                "    define the position<iface> {\n"
                "        it may only contain particles where {\n"
                "            it has the position</marker>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<gw> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</inner>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<gw>.\n"
                "        move the particle in position<iface> to position<gw>::action</inner>::position<input>.\n"
                "        create a particle in position<gw>::action</inner>::position<run>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    define the position<mw> {\n"
                "        it may only contain particles where {\n"
                "            it has the action</middle>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<mw>.\n"
                "        create a particle in position<mw>::action</middle>::position<iface>.\n"
                "        create a particle in position<mw>::action</middle>::position<iface>::position</marker>.\n"
                "        create a particle in position<mw>::action</middle>::position<run>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.InferredRequirementViolationDiagnostic)
    assert all_diags[0].location.line == 14
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.end_line == 14
    assert all_diags[0].location.end_column == 74
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].action_name == _MIDDLE
    assert all_diags[0].required_empty is True
    assert (
        all_diags[0].position_name
        == "position<mw>::action</middle>::position<iface>::position</marker>"
    )
    assert_propagation_chain(
        all_diags[0],
        {
            "kind": action_contract.PropagationKind.FILL_SITE,
            "enclosing_quality_name": "position<mw>::action</middle>::position<iface>::position</marker>",
            "triggered_quality_name": None,
            "line": 13,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _TEST,
            "triggered_quality_name": _MIDDLE,
            "line": 14,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _MIDDLE,
            "triggered_quality_name": _INNER,
            "line": 18,
            "column": 30,
            "file_path": "middle.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": _INNER,
            "triggered_quality_name": None,
            "line": 11,
            "column": 30,
            "file_path": "inner.dfn",
        },
    )
    assert action_graph_set(result.operation_graphs) == {
        (_TEST, _MIDDLE),
        (_MIDDLE, _INNER),
    }


def test_carried_grandchild_satisfies_inner_occupied_requirement(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """Inner destroys input::/b::/c two levels below the moved iface, so filling iface::/b::/c in the caller satisfies it."""
    result = validate_project_with_reference_graph(
        {
            "c.dfn": "define the potential position<my.domain.com:my_lib:/c>.\n",
            "b.dfn": (
                "define the potential position<my.domain.com:my_lib:/b> {\n"
                "    it may only contain particles where {\n"
                "        it has the position</c>.\n"
                "    }\n"
                "}\n"
            ),
            "inner.dfn": (
                "define the potential action<my.domain.com:my_lib:/inner> {\n"
                "    define the position<run>.\n"
                "    define the position<input> {\n"
                "        it may only contain particles where {\n"
                "            it has the position</b>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        destroy the particle in position<input>::position</b>::position</c>.\n"
                "    }\n"
                "}\n"
            ),
            "middle.dfn": (
                "define the potential action<my.domain.com:my_lib:/middle> {\n"
                "    define the position<run>.\n"
                "    define the position<iface> {\n"
                "        it may only contain particles where {\n"
                "            it has the position</b>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<gw> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</inner>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<gw>.\n"
                "        move the particle in position<iface> to position<gw>::action</inner>::position<input>.\n"
                "        create a particle in position<gw>::action</inner>::position<run>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    define the position<mw> {\n"
                "        it may only contain particles where {\n"
                "            it has the action</middle>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<mw>.\n"
                "        create a particle in position<mw>::action</middle>::position<iface>.\n"
                "        create a particle in position<mw>::action</middle>::position<iface>::position</b>.\n"
                "        create a particle in position<mw>::action</middle>::position<iface>::position</b>::position</c>.\n"
                "        create a particle in position<mw>::action</middle>::position<run>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    assert_no_errors(result.program_result)


def test_empty_carried_grandchild_and_parent_violate_inner_occupied_requirement(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """Inner destroys input::/b::/c but the caller fills neither iface::/b nor its /c, so both propagated requirements are violated."""
    result = validate_project_with_reference_graph(
        {
            "c.dfn": "define the potential position<my.domain.com:my_lib:/c>.\n",
            "b.dfn": (
                "define the potential position<my.domain.com:my_lib:/b> {\n"
                "    it may only contain particles where {\n"
                "        it has the position</c>.\n"
                "    }\n"
                "}\n"
            ),
            "inner.dfn": (
                "define the potential action<my.domain.com:my_lib:/inner> {\n"
                "    define the position<run>.\n"
                "    define the position<input> {\n"
                "        it may only contain particles where {\n"
                "            it has the position</b>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        destroy the particle in position<input>::position</b>::position</c>.\n"
                "    }\n"
                "}\n"
            ),
            "middle.dfn": (
                "define the potential action<my.domain.com:my_lib:/middle> {\n"
                "    define the position<run>.\n"
                "    define the position<iface> {\n"
                "        it may only contain particles where {\n"
                "            it has the position</b>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<gw> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</inner>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<gw>.\n"
                "        move the particle in position<iface> to position<gw>::action</inner>::position<input>.\n"
                "        create a particle in position<gw>::action</inner>::position<run>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    define the position<mw> {\n"
                "        it may only contain particles where {\n"
                "            it has the action</middle>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<mw>.\n"
                "        create a particle in position<mw>::action</middle>::position<iface>.\n"
                "        create a particle in position<mw>::action</middle>::position<run>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 2
    assert isinstance(all_diags[0], diagnostics.InferredRequirementViolationDiagnostic)
    assert all_diags[0].location.line == 13
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.end_line == 13
    assert all_diags[0].location.end_column == 74
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].action_name == _MIDDLE
    assert all_diags[0].required_empty is False
    assert (
        all_diags[0].position_name
        == "position<mw>::action</middle>::position<iface>::position</b>"
    )
    assert_propagation_chain(
        all_diags[0],
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _TEST,
            "triggered_quality_name": _MIDDLE,
            "line": 13,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _MIDDLE,
            "triggered_quality_name": _INNER,
            "line": 18,
            "column": 30,
            "file_path": "middle.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": _INNER,
            "triggered_quality_name": None,
            "line": 11,
            "column": 33,
            "file_path": "inner.dfn",
        },
    )
    assert isinstance(all_diags[1], diagnostics.InferredRequirementViolationDiagnostic)
    assert all_diags[1].location.line == 13
    assert all_diags[1].location.column == 30
    assert all_diags[1].location.end_line == 13
    assert all_diags[1].location.end_column == 74
    assert all_diags[1].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[1].action_name == _MIDDLE
    assert all_diags[1].required_empty is False
    assert (
        all_diags[1].position_name
        == "position<mw>::action</middle>::position<iface>::position</b>::position</c>"
    )
    assert_propagation_chain(
        all_diags[1],
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _TEST,
            "triggered_quality_name": _MIDDLE,
            "line": 13,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _MIDDLE,
            "triggered_quality_name": _INNER,
            "line": 18,
            "column": 30,
            "file_path": "middle.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": _INNER,
            "triggered_quality_name": None,
            "line": 11,
            "column": 33,
            "file_path": "inner.dfn",
        },
    )
    assert action_graph_set(result.operation_graphs) == {
        (_TEST, _MIDDLE),
        (_MIDDLE, _INNER),
    }


def test_empty_carried_grandchild_satisfies_inner_empty_requirement(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """Inner creates into input::/b::/c two levels below the moved iface, so leaving iface::/b::/c empty in the caller satisfies it."""
    result = validate_project_with_reference_graph(
        {
            "c.dfn": "define the potential position<my.domain.com:my_lib:/c>.\n",
            "b.dfn": (
                "define the potential position<my.domain.com:my_lib:/b> {\n"
                "    it may only contain particles where {\n"
                "        it has the position</c>.\n"
                "    }\n"
                "}\n"
            ),
            "inner.dfn": (
                "define the potential action<my.domain.com:my_lib:/inner> {\n"
                "    define the position<run>.\n"
                "    define the position<input> {\n"
                "        it may only contain particles where {\n"
                "            it has the position</b>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<input>::position</b>::position</c>.\n"
                "    }\n"
                "}\n"
            ),
            "middle.dfn": (
                "define the potential action<my.domain.com:my_lib:/middle> {\n"
                "    define the position<run>.\n"
                "    define the position<iface> {\n"
                "        it may only contain particles where {\n"
                "            it has the position</b>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<gw> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</inner>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<gw>.\n"
                "        move the particle in position<iface> to position<gw>::action</inner>::position<input>.\n"
                "        create a particle in position<gw>::action</inner>::position<run>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    define the position<mw> {\n"
                "        it may only contain particles where {\n"
                "            it has the action</middle>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<mw>.\n"
                "        create a particle in position<mw>::action</middle>::position<iface>.\n"
                "        create a particle in position<mw>::action</middle>::position<iface>::position</b>.\n"
                "        create a particle in position<mw>::action</middle>::position<run>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    assert_no_errors(result.program_result)


def test_filled_carried_grandchild_violates_inner_empty_requirement(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """Inner creates into input::/b::/c two levels below the moved iface, so filling iface::/b::/c in the caller is reported."""
    result = validate_project_with_reference_graph(
        {
            "c.dfn": "define the potential position<my.domain.com:my_lib:/c>.\n",
            "b.dfn": (
                "define the potential position<my.domain.com:my_lib:/b> {\n"
                "    it may only contain particles where {\n"
                "        it has the position</c>.\n"
                "    }\n"
                "}\n"
            ),
            "inner.dfn": (
                "define the potential action<my.domain.com:my_lib:/inner> {\n"
                "    define the position<run>.\n"
                "    define the position<input> {\n"
                "        it may only contain particles where {\n"
                "            it has the position</b>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<input>::position</b>::position</c>.\n"
                "    }\n"
                "}\n"
            ),
            "middle.dfn": (
                "define the potential action<my.domain.com:my_lib:/middle> {\n"
                "    define the position<run>.\n"
                "    define the position<iface> {\n"
                "        it may only contain particles where {\n"
                "            it has the position</b>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<gw> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</inner>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<gw>.\n"
                "        move the particle in position<iface> to position<gw>::action</inner>::position<input>.\n"
                "        create a particle in position<gw>::action</inner>::position<run>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    define the position<mw> {\n"
                "        it may only contain particles where {\n"
                "            it has the action</middle>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<mw>.\n"
                "        create a particle in position<mw>::action</middle>::position<iface>.\n"
                "        create a particle in position<mw>::action</middle>::position<iface>::position</b>.\n"
                "        create a particle in position<mw>::action</middle>::position<iface>::position</b>::position</c>.\n"
                "        create a particle in position<mw>::action</middle>::position<run>.\n"
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
    assert all_diags[0].location.end_line == 15
    assert all_diags[0].location.end_column == 74
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].action_name == _MIDDLE
    assert all_diags[0].required_empty is True
    assert (
        all_diags[0].position_name
        == "position<mw>::action</middle>::position<iface>::position</b>::position</c>"
    )
    assert_propagation_chain(
        all_diags[0],
        {
            "kind": action_contract.PropagationKind.FILL_SITE,
            "enclosing_quality_name": "position<mw>::action</middle>::position<iface>::position</b>::position</c>",
            "triggered_quality_name": None,
            "line": 14,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _TEST,
            "triggered_quality_name": _MIDDLE,
            "line": 15,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _MIDDLE,
            "triggered_quality_name": _INNER,
            "line": 18,
            "column": 30,
            "file_path": "middle.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": _INNER,
            "triggered_quality_name": None,
            "line": 11,
            "column": 30,
            "file_path": "inner.dfn",
        },
    )
    assert action_graph_set(result.operation_graphs) == {
        (_TEST, _MIDDLE),
        (_MIDDLE, _INNER),
    }
