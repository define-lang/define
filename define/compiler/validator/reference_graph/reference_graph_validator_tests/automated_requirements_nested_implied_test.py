# pyright: reportUnusedCallResult=false

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

_TEST = "action<my.domain.com:my_lib:/test>"
_OUTER = "action<my.domain.com:my_lib:/outer>"
_MIDDLE = "action<my.domain.com:my_lib:/middle>"
_INNER = "action<my.domain.com:my_lib:/inner>"

_X_DEFINITION = "define the potential position<my.domain.com:my_lib:/x>.\n"

_INNER_DESTROYS_X = (
    "define the potential action<my.domain.com:my_lib:/inner> {\n"
    "    it also assigns the position</x>.\n"
    "    define the position<run>.\n"
    "    it happens when {\n"
    "        the position<run> has a particle.\n"
    "    } and it does {\n"
    "        destroy the particle in position</x>.\n"
    "    }\n"
    "}\n"
)

_INNER_CREATES_X = (
    "define the potential action<my.domain.com:my_lib:/inner> {\n"
    "    it also assigns the position</x>.\n"
    "    define the position<run>.\n"
    "    it happens when {\n"
    "        the position<run> has a particle.\n"
    "    } and it does {\n"
    "        create a particle in position</x>.\n"
    "    }\n"
    "}\n"
)

_MIDDLE_TRIGGERS_INNER = (
    "define the potential action<my.domain.com:my_lib:/middle> {\n"
    "    it also assigns the action</inner>.\n"
    "    define the position<run>.\n"
    "    it happens when {\n"
    "        the position<run> has a particle.\n"
    "    } and it does {\n"
    "        create a particle in action</inner>::position<run>.\n"
    "    }\n"
    "}\n"
)

_TEST_PRE_FILLS_X = (
    "define the potential action<my.domain.com:my_lib:/test> {\n"
    "    define the position<run>.\n"
    "    it happens when {\n"
    "        the position<run> has a particle.\n"
    "    } and it does {\n"
    "        define the position<box> {\n"
    "            it may only contain particles where {\n"
    "                it has the position</x>.\n"
    "                it has the action</middle>.\n"
    "            }\n"
    "        }\n"
    "        create a particle in position<box>.\n"
    "        create a particle in position<box>::position</x>.\n"
    "        create a particle in position<box>::action</middle>::position<run>.\n"
    "    }\n"
    "}\n"
)

_TEST_DOES_NOT_FILL_X = (
    "define the potential action<my.domain.com:my_lib:/test> {\n"
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
    "        create a particle in position<box>::action</middle>::position<run>.\n"
    "    }\n"
    "}\n"
)


def test_empty_guarantee_creates_occupied_requirement_in_caller_and_test_satisfies(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "x.dfn": _X_DEFINITION,
            "inner.dfn": _INNER_DESTROYS_X,
            "middle.dfn": _MIDDLE_TRIGGERS_INNER,
            "test.dfn": _TEST_PRE_FILLS_X,
        }
    )
    assert result.program_result.all_diagnostics == []
    assert action_graph_set(result.operation_graphs) == {
        (_TEST, _MIDDLE),
        (_MIDDLE, _INNER),
    }


def test_empty_guarantee_creates_occupied_requirement_in_caller_and_test_violates(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "x.dfn": _X_DEFINITION,
            "inner.dfn": _INNER_DESTROYS_X,
            "middle.dfn": _MIDDLE_TRIGGERS_INNER,
            "test.dfn": _TEST_DOES_NOT_FILL_X,
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.InferredRequirementViolationDiagnostic)
    assert all_diags[0].location.line == 12
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].action_name == _MIDDLE
    assert all_diags[0].required_empty is False
    assert all_diags[0].position_name == "position<box>::position</x>"
    assert_propagation_chain(
        all_diags[0],
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _TEST,
            "triggered_quality_name": _MIDDLE,
            "line": 12,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _MIDDLE,
            "triggered_quality_name": _INNER,
            "line": 7,
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
        (_TEST, _MIDDLE),
        (_MIDDLE, _INNER),
    }


def test_occupied_guarantee_creates_empty_requirement_in_caller_and_test_satisfies(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "x.dfn": _X_DEFINITION,
            "inner.dfn": _INNER_CREATES_X,
            "middle.dfn": _MIDDLE_TRIGGERS_INNER,
            "test.dfn": _TEST_DOES_NOT_FILL_X,
        }
    )
    assert result.program_result.all_diagnostics == []
    assert action_graph_set(result.operation_graphs) == {
        (_TEST, _MIDDLE),
        (_MIDDLE, _INNER),
    }


def test_occupied_guarantee_creates_empty_requirement_in_caller_and_test_violates(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "x.dfn": _X_DEFINITION,
            "inner.dfn": _INNER_CREATES_X,
            "middle.dfn": _MIDDLE_TRIGGERS_INNER,
            "test.dfn": _TEST_PRE_FILLS_X,
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.InferredRequirementViolationDiagnostic)
    assert all_diags[0].location.line == 14
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].action_name == _MIDDLE
    assert all_diags[0].required_empty is True
    assert all_diags[0].position_name == "position<box>::position</x>"
    assert_propagation_chain(
        all_diags[0],
        {
            "kind": action_contract.PropagationKind.FILL_SITE,
            "enclosing_quality_name": "position<box>::position</x>",
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
            "line": 7,
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
        (_TEST, _MIDDLE),
        (_MIDDLE, _INNER),
    }


_X_HAS_INNER = (
    "define the potential position<my.domain.com:my_lib:/x> {\n"
    "    it may only contain particles where {\n"
    "        it has the action</inner>.\n"
    "    }\n"
    "}\n"
)

_INNER_REQUIRES_ITEM_OCCUPIED = (
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
)


def test_caller_filled_implied_position_propagates_inner_action_requirement(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """When the caller fills an implied position used to reach an inner action, the inner action's requirements propagate to the caller."""
    result = validate_project_with_reference_graph(
        {
            "x.dfn": _X_HAS_INNER,
            "inner.dfn": _INNER_REQUIRES_ITEM_OCCUPIED,
            "middle.dfn": (
                "define the potential action<my.domain.com:my_lib:/middle> {\n"
                "    it also assigns the position</x>.\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position</x>::action</inner>::position<trigger_pos>.\n"
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
                "                it has the position</x>.\n"
                "                it has the action</middle>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<box>::position</x>.\n"
                "        create a particle in position<box>::action</middle>::position<run>.\n"
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
    assert all_diags[0].action_name == _MIDDLE
    assert all_diags[0].required_empty is False
    assert (
        all_diags[0].position_name
        == "position<box>::position</x>::action</inner>::position<item>"
    )
    assert_propagation_chain(
        all_diags[0],
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
            "line": 7,
            "column": 30,
            "file_path": "middle.dfn",
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
        (_TEST, _MIDDLE),
        (_MIDDLE, _INNER),
    }


def test_inner_action_requirement_does_not_propagate_past_local_filler_of_implied_position(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """When the current action fills an implied position before triggering an inner action through it, the inner action's requirement is checked at the trigger site but does not propagate further up to the caller."""
    result = validate_project_with_reference_graph(
        {
            "x.dfn": _X_HAS_INNER,
            "inner.dfn": _INNER_REQUIRES_ITEM_OCCUPIED,
            "middle.dfn": (
                "define the potential action<my.domain.com:my_lib:/middle> {\n"
                "    it also assigns the position</x>.\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position</x>.\n"
                "        create a particle in position</x>::action</inner>::position<trigger_pos>.\n"
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
                "                it has the action</middle>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<box>::action</middle>::position<run>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.InferredRequirementViolationDiagnostic)
    assert all_diags[0].location.line == 8
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("middle.dfn")
    assert all_diags[0].action_name == _INNER
    assert all_diags[0].required_empty is False
    assert all_diags[0].position_name == "position</x>::action</inner>::position<item>"
    assert_propagation_chain(
        all_diags[0],
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _MIDDLE,
            "triggered_quality_name": _INNER,
            "line": 8,
            "column": 30,
            "file_path": "middle.dfn",
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
        (_TEST, _MIDDLE),
        (_MIDDLE, _INNER),
    }


def test_doubly_nested_implied_action_chain_propagates(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """An interface requirement from /inner propagates two levels up through /middle and /outer when each is reached as an implied action of its caller."""
    result = validate_project_with_reference_graph(
        {
            "inner.dfn": (
                "define the potential action<my.domain.com:my_lib:/inner> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<extra>.\n"
                "    define the position<dest>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        move the particle in position<extra> to position<dest>.\n"
                "    }\n"
                "}\n"
            ),
            "middle.dfn": (
                "define the potential action<my.domain.com:my_lib:/middle> {\n"
                "    it also assigns the action</inner>.\n"
                "    define the position<trigger_pos>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in action</inner>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
            "outer.dfn": (
                "define the potential action<my.domain.com:my_lib:/outer> {\n"
                "    it also assigns the action</middle>.\n"
                "    define the position<trigger_pos>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in action</middle>::position<trigger_pos>.\n"
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
                "        create a particle in position<box>::action</outer>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    diag = all_diags[0]
    assert isinstance(diag, diagnostics.InferredRequirementViolationDiagnostic)
    assert diag.location.line == 12
    assert diag.location.column == 30
    assert diag.location.file_path == PurePosixPath("test.dfn")
    assert diag.action_name == _OUTER
    assert diag.required_empty is False
    assert diag.position_name == "position<box>::action</inner>::position<extra>"
    assert_propagation_chain(
        diag,
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _TEST,
            "triggered_quality_name": _OUTER,
            "line": 12,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _OUTER,
            "triggered_quality_name": _MIDDLE,
            "line": 7,
            "column": 30,
            "file_path": "outer.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _MIDDLE,
            "triggered_quality_name": _INNER,
            "line": 7,
            "column": 30,
            "file_path": "middle.dfn",
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
        (_OUTER, _MIDDLE),
        (_MIDDLE, _INNER),
    }
