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
_P = "action<my.domain.com:my_lib:/p>"


def test_constructor_occupied_requirement_via_destroy_of_child_of_moved_implied(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "q_child.dfn": "define the potential position<my.domain.com:my_lib:/q_child>.\n",
            "q.dfn": (
                "define the potential position<my.domain.com:my_lib:/q> {\n"
                "    it may only contain particles where {\n"
                "        it has the position</q_child>.\n"
                "    }\n"
                "}\n"
            ),
            "p.dfn": (
                "define the potential action<my.domain.com:my_lib:/p> {\n"
                "    it also assigns the position</q>.\n"
                "    it happens when {\n"
                "        this particle is created.\n"
                "    } and it does {\n"
                "        define the position<local> {\n"
                "            it may only contain particles where {\n"
                "                it has the position</q_child>.\n"
                "            }\n"
                "        }\n"
                "        move the particle in position</q> to position<local>.\n"
                "        destroy the particle in position<local>::position</q_child>.\n"
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
                "                it has the action</p>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 2
    assert isinstance(all_diags[0], diagnostics.InferredRequirementViolationDiagnostic)
    assert all_diags[0].location.line == 11
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].required_empty is False
    assert all_diags[0].action_name == _P
    assert all_diags[0].position_name == "position<box>::position</q>"
    assert_propagation_chain(
        all_diags[0],
        {
            "kind": action_contract.PropagationKind.QUALITY_ASSIGNED,
            "enclosing_quality_name": "position<box>",
            "triggered_quality_name": "action<my.domain.com:my_lib:/p>",
            "line": 8,
            "column": 28,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.CONSTRUCTOR_TRIGGER,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/test>",
            "triggered_quality_name": "action<my.domain.com:my_lib:/p>",
            "line": 11,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/p>",
            "triggered_quality_name": None,
            "line": 11,
            "column": 30,
            "file_path": "p.dfn",
        },
    )
    assert isinstance(all_diags[1], diagnostics.InferredRequirementViolationDiagnostic)
    assert all_diags[1].location.line == 11
    assert all_diags[1].location.column == 30
    assert all_diags[1].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[1].required_empty is False
    assert all_diags[1].action_name == _P
    assert (
        all_diags[1].position_name == "position<box>::position</q>::position</q_child>"
    )
    assert_propagation_chain(
        all_diags[1],
        {
            "kind": action_contract.PropagationKind.QUALITY_ASSIGNED,
            "enclosing_quality_name": "position<box>",
            "triggered_quality_name": _P,
            "line": 8,
            "column": 28,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.CONSTRUCTOR_TRIGGER,
            "enclosing_quality_name": _TEST,
            "triggered_quality_name": _P,
            "line": 11,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": _P,
            "triggered_quality_name": None,
            "line": 12,
            "column": 33,
            "file_path": "p.dfn",
        },
    )


# A separate "filler" constructor occupies the implied position before /p's
# constructor runs, so the occupancy is a cross-definition guarantee /p must
# account for -- the constructor-era analog of an implied position that used to
# fill itself.
def test_constructor_empty_requirement_via_create_in_child_of_moved_implied(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "q_child.dfn": "define the potential position<my.domain.com:my_lib:/q_child>.\n",
            "q.dfn": (
                "define the potential position<my.domain.com:my_lib:/q> {\n"
                "    it may only contain particles where {\n"
                "        it has the position</q_child>.\n"
                "    }\n"
                "}\n"
            ),
            "filler.dfn": (
                "define the potential action<my.domain.com:my_lib:/filler> {\n"
                "    it also assigns the position</q>.\n"
                "    it happens when {\n"
                "        this particle is created.\n"
                "    } and it does {\n"
                "        create a particle in position</q>.\n"
                "        create a particle in position</q>::position</q_child>.\n"
                "    }\n"
                "}\n"
            ),
            "p.dfn": (
                "define the potential action<my.domain.com:my_lib:/p> {\n"
                "    it also assigns the position</q>.\n"
                "    it happens when {\n"
                "        this particle is created.\n"
                "    } and it does {\n"
                "        define the position<local> {\n"
                "            it may only contain particles where {\n"
                "                it has the position</q_child>.\n"
                "            }\n"
                "        }\n"
                "        move the particle in position</q> to position<local>.\n"
                "        create a particle in position<local>::position</q_child>.\n"
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
                "                it has the action</filler>.\n"
                "                it has the action</p>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    diag = all_diags[0]
    assert isinstance(diag, diagnostics.InferredRequirementViolationDiagnostic)
    assert diag.required_empty is True
    assert diag.action_name == _P
    assert diag.position_name == "position<box>::position</q>::position</q_child>"
    assert diag.location.line == 12
    assert diag.location.column == 30
    assert diag.location.file_path == PurePosixPath("test.dfn")
    assert_propagation_chain(
        diag,
        {
            "kind": action_contract.PropagationKind.QUALITY_ASSIGNED,
            "enclosing_quality_name": "position<box>",
            "triggered_quality_name": "action<my.domain.com:my_lib:/p>",
            "line": 9,
            "column": 28,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.CONSTRUCTOR_TRIGGER,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/test>",
            "triggered_quality_name": "action<my.domain.com:my_lib:/p>",
            "line": 12,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.FILL_SITE,
            "enclosing_quality_name": "position<box>::position</q>::position</q_child>",
            "triggered_quality_name": None,
            "line": 7,
            "column": 30,
            "file_path": "filler.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/p>",
            "triggered_quality_name": None,
            "line": 12,
            "column": 30,
            "file_path": "p.dfn",
        },
    )


def test_constructor_occupied_requirement_via_destroy_of_child_of_moved_to_implied(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "q_child.dfn": "define the potential position<my.domain.com:my_lib:/q_child>.\n",
            "q.dfn": (
                "define the potential position<my.domain.com:my_lib:/q> {\n"
                "    it may only contain particles where {\n"
                "        it has the position</q_child>.\n"
                "    }\n"
                "}\n"
            ),
            "q2.dfn": (
                "define the potential position<my.domain.com:my_lib:/q2> {\n"
                "    it may only contain particles where {\n"
                "        it has the position</q_child>.\n"
                "    }\n"
                "}\n"
            ),
            "filler.dfn": (
                "define the potential action<my.domain.com:my_lib:/filler> {\n"
                "    it also assigns the position</q>.\n"
                "    it happens when {\n"
                "        this particle is created.\n"
                "    } and it does {\n"
                "        create a particle in position</q>.\n"
                "    }\n"
                "}\n"
            ),
            "p.dfn": (
                "define the potential action<my.domain.com:my_lib:/p> {\n"
                "    it also assigns the position</q>.\n"
                "    it also assigns the position</q2>.\n"
                "    it happens when {\n"
                "        this particle is created.\n"
                "    } and it does {\n"
                "        move the particle in position</q> to position</q2>.\n"
                "        destroy the particle in position</q2>::position</q_child>.\n"
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
                "                it has the action</filler>.\n"
                "                it has the action</p>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    diag = all_diags[0]
    assert isinstance(diag, diagnostics.InferredRequirementViolationDiagnostic)
    assert diag.required_empty is False
    assert diag.action_name == _P
    assert diag.position_name == "position<box>::position</q>::position</q_child>"
    assert diag.location.line == 12
    assert diag.location.column == 30
    assert diag.location.file_path == PurePosixPath("test.dfn")
    assert_propagation_chain(
        diag,
        {
            "kind": action_contract.PropagationKind.QUALITY_ASSIGNED,
            "enclosing_quality_name": "position<box>",
            "triggered_quality_name": "action<my.domain.com:my_lib:/p>",
            "line": 9,
            "column": 28,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.CONSTRUCTOR_TRIGGER,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/test>",
            "triggered_quality_name": "action<my.domain.com:my_lib:/p>",
            "line": 12,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/p>",
            "triggered_quality_name": None,
            "line": 8,
            "column": 33,
            "file_path": "p.dfn",
        },
    )


def test_constructor_empty_requirement_via_create_in_child_of_moved_to_implied(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "q_child.dfn": "define the potential position<my.domain.com:my_lib:/q_child>.\n",
            "q.dfn": (
                "define the potential position<my.domain.com:my_lib:/q> {\n"
                "    it may only contain particles where {\n"
                "        it has the position</q_child>.\n"
                "    }\n"
                "}\n"
            ),
            "q2.dfn": (
                "define the potential position<my.domain.com:my_lib:/q2> {\n"
                "    it may only contain particles where {\n"
                "        it has the position</q_child>.\n"
                "    }\n"
                "}\n"
            ),
            "filler.dfn": (
                "define the potential action<my.domain.com:my_lib:/filler> {\n"
                "    it also assigns the position</q>.\n"
                "    it happens when {\n"
                "        this particle is created.\n"
                "    } and it does {\n"
                "        create a particle in position</q>.\n"
                "        create a particle in position</q>::position</q_child>.\n"
                "    }\n"
                "}\n"
            ),
            "p.dfn": (
                "define the potential action<my.domain.com:my_lib:/p> {\n"
                "    it also assigns the position</q>.\n"
                "    it also assigns the position</q2>.\n"
                "    it happens when {\n"
                "        this particle is created.\n"
                "    } and it does {\n"
                "        move the particle in position</q> to position</q2>.\n"
                "        create a particle in position</q2>::position</q_child>.\n"
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
                "                it has the action</filler>.\n"
                "                it has the action</p>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    diag = all_diags[0]
    assert isinstance(diag, diagnostics.InferredRequirementViolationDiagnostic)
    assert diag.required_empty is True
    assert diag.action_name == _P
    assert diag.position_name == "position<box>::position</q>::position</q_child>"
    assert diag.location.line == 12
    assert diag.location.column == 30
    assert diag.location.file_path == PurePosixPath("test.dfn")
    assert_propagation_chain(
        diag,
        {
            "kind": action_contract.PropagationKind.QUALITY_ASSIGNED,
            "enclosing_quality_name": "position<box>",
            "triggered_quality_name": "action<my.domain.com:my_lib:/p>",
            "line": 9,
            "column": 28,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.CONSTRUCTOR_TRIGGER,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/test>",
            "triggered_quality_name": "action<my.domain.com:my_lib:/p>",
            "line": 12,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.FILL_SITE,
            "enclosing_quality_name": "position<box>::position</q>::position</q_child>",
            "triggered_quality_name": None,
            "line": 7,
            "column": 30,
            "file_path": "filler.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/p>",
            "triggered_quality_name": None,
            "line": 8,
            "column": 30,
            "file_path": "p.dfn",
        },
    )


def test_constructor_occupied_requirement_satisfied_for_moved_to_implied(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "q_child.dfn": "define the potential position<my.domain.com:my_lib:/q_child>.\n",
            "q.dfn": (
                "define the potential position<my.domain.com:my_lib:/q> {\n"
                "    it may only contain particles where {\n"
                "        it has the position</q_child>.\n"
                "    }\n"
                "}\n"
            ),
            "q2.dfn": (
                "define the potential position<my.domain.com:my_lib:/q2> {\n"
                "    it may only contain particles where {\n"
                "        it has the position</q_child>.\n"
                "    }\n"
                "}\n"
            ),
            "filler.dfn": (
                "define the potential action<my.domain.com:my_lib:/filler> {\n"
                "    it also assigns the position</q>.\n"
                "    it happens when {\n"
                "        this particle is created.\n"
                "    } and it does {\n"
                "        create a particle in position</q>.\n"
                "        create a particle in position</q>::position</q_child>.\n"
                "    }\n"
                "}\n"
            ),
            "p.dfn": (
                "define the potential action<my.domain.com:my_lib:/p> {\n"
                "    it also assigns the position</q>.\n"
                "    it also assigns the position</q2>.\n"
                "    it happens when {\n"
                "        this particle is created.\n"
                "    } and it does {\n"
                "        move the particle in position</q> to position</q2>.\n"
                "        destroy the particle in position</q2>::position</q_child>.\n"
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
                "                it has the action</filler>.\n"
                "                it has the action</p>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    assert_no_errors(result.program_result)


def test_constructor_empty_requirement_satisfied_for_moved_to_implied(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "q_child.dfn": "define the potential position<my.domain.com:my_lib:/q_child>.\n",
            "q.dfn": (
                "define the potential position<my.domain.com:my_lib:/q> {\n"
                "    it may only contain particles where {\n"
                "        it has the position</q_child>.\n"
                "    }\n"
                "}\n"
            ),
            "q2.dfn": (
                "define the potential position<my.domain.com:my_lib:/q2> {\n"
                "    it may only contain particles where {\n"
                "        it has the position</q_child>.\n"
                "    }\n"
                "}\n"
            ),
            "filler.dfn": (
                "define the potential action<my.domain.com:my_lib:/filler> {\n"
                "    it also assigns the position</q>.\n"
                "    it happens when {\n"
                "        this particle is created.\n"
                "    } and it does {\n"
                "        create a particle in position</q>.\n"
                "    }\n"
                "}\n"
            ),
            "p.dfn": (
                "define the potential action<my.domain.com:my_lib:/p> {\n"
                "    it also assigns the position</q>.\n"
                "    it also assigns the position</q2>.\n"
                "    it happens when {\n"
                "        this particle is created.\n"
                "    } and it does {\n"
                "        move the particle in position</q> to position</q2>.\n"
                "        create a particle in position</q2>::position</q_child>.\n"
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
                "                it has the action</filler>.\n"
                "                it has the action</p>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    assert_no_errors(result.program_result)
