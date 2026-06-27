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
_P = "position<my.domain.com:my_lib:/p>"
_Q = "position<my.domain.com:my_lib:/q>"
_IMPLIED_ACTION = "action<my.domain.com:my_lib:/implied_action>"


def test_init_block_occupied_violation_via_destroy_of_implied(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "q.dfn": "define the potential position<my.domain.com:my_lib:/q>.\n",
            "p.dfn": (
                "define the potential position<my.domain.com:my_lib:/p> {\n"
                "    it also assigns the position</q>.\n"
                "    after it is assigned {\n"
                "        destroy the particle in position</q>.\n"
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
                "                it has the position</p>.\n"
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
    assert isinstance(
        diag,
        diagnostics.InferredRequirementViolationDiagnostic,
    )
    assert diag.runner_description == f"the Position Initialization Block of '{_P}'"
    assert diag.required_empty is False
    assert diag.position_name == "position<box>::position</q>"
    assert diag.location.line == 11
    assert diag.location.column == 30
    assert diag.location.file_path == PurePosixPath("test.dfn")
    assert_propagation_chain(
        diag,
        {
            "kind": action_contract.PropagationKind.INIT_BLOCK_TRIGGER,
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
            "line": 4,
            "column": 33,
            "file_path": "p.dfn",
        },
    )


def test_init_block_occupied_violation_via_move_source_of_implied(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "q.dfn": "define the potential position<my.domain.com:my_lib:/q>.\n",
            "p.dfn": (
                "define the potential position<my.domain.com:my_lib:/p> {\n"
                "    it also assigns the position</q>.\n"
                "    after it is assigned {\n"
                "        define the position<_sink>.\n"
                "        move the particle in position</q> to position<_sink>.\n"
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
                "                it has the position</p>.\n"
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
    assert isinstance(
        diag,
        diagnostics.InferredRequirementViolationDiagnostic,
    )
    assert diag.runner_description == f"the Position Initialization Block of '{_P}'"
    assert diag.required_empty is False
    assert diag.position_name == "position<box>::position</q>"
    assert diag.location.line == 11
    assert diag.location.column == 30
    assert diag.location.file_path == PurePosixPath("test.dfn")
    assert_propagation_chain(
        diag,
        {
            "kind": action_contract.PropagationKind.INIT_BLOCK_TRIGGER,
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
            "line": 5,
            "column": 30,
            "file_path": "p.dfn",
        },
    )


def test_init_block_empty_violation_via_create_in_implied(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "q.dfn": (
                "define the potential position<my.domain.com:my_lib:/q> {\n"
                "    after it is assigned {\n"
                "        create a particle in position</q>.\n"
                "    }\n"
                "}\n"
            ),
            "p.dfn": (
                "define the potential position<my.domain.com:my_lib:/p> {\n"
                "    it also assigns the position</q>.\n"
                "    after it is assigned {\n"
                "        create a particle in position</q>.\n"
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
                "                it has the position</p>.\n"
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
    assert isinstance(
        diag,
        diagnostics.InferredRequirementViolationDiagnostic,
    )
    assert diag.runner_description == f"the Position Initialization Block of '{_P}'"
    assert diag.required_empty is True
    assert diag.position_name == "position<box>::position</q>"
    assert diag.location.line == 11
    assert diag.location.column == 30
    assert diag.location.file_path == PurePosixPath("test.dfn")
    assert_propagation_chain(
        diag,
        {
            "kind": action_contract.PropagationKind.INIT_BLOCK_TRIGGER,
            "enclosing_quality_name": _TEST,
            "triggered_quality_name": _P,
            "line": 11,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.FILL_SITE,
            "enclosing_quality_name": "position<box>::position</q>",
            "triggered_quality_name": None,
            "line": 3,
            "column": 30,
            "file_path": "q.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": _P,
            "triggered_quality_name": None,
            "line": 4,
            "column": 30,
            "file_path": "p.dfn",
        },
    )


def test_init_block_satisfied_requirement_emits_no_diagnostic(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "q.dfn": (
                "define the potential position<my.domain.com:my_lib:/q> {\n"
                "    after it is assigned {\n"
                "        create a particle in position</q>.\n"
                "    }\n"
                "}\n"
            ),
            "p.dfn": (
                "define the potential position<my.domain.com:my_lib:/p> {\n"
                "    it also assigns the position</q>.\n"
                "    after it is assigned {\n"
                "        destroy the particle in position</q>.\n"
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
                "                it has the position</p>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    assert_no_errors(result.program_result)


def test_init_block_multiple_implied_positions_each_check_runs(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "q.dfn": "define the potential position<my.domain.com:my_lib:/q>.\n",
            "r.dfn": "define the potential position<my.domain.com:my_lib:/r>.\n",
            "p.dfn": (
                "define the potential position<my.domain.com:my_lib:/p> {\n"
                "    it also assigns the position</q>.\n"
                "    it also assigns the position</r>.\n"
                "    after it is assigned {\n"
                "        destroy the particle in position</q>.\n"
                "        destroy the particle in position</r>.\n"
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
                "                it has the position</p>.\n"
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
    diag_q = all_diags[0]
    diag_r = all_diags[1]
    assert isinstance(diag_q, diagnostics.InferredRequirementViolationDiagnostic)
    assert diag_q.runner_description == f"the Position Initialization Block of '{_P}'"
    assert diag_q.required_empty is False
    assert diag_q.position_name == "position<box>::position</q>"
    assert diag_q.location.line == 11
    assert diag_q.location.column == 30
    assert diag_q.location.file_path == PurePosixPath("test.dfn")
    assert_propagation_chain(
        diag_q,
        {
            "kind": action_contract.PropagationKind.INIT_BLOCK_TRIGGER,
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
            "line": 5,
            "column": 33,
            "file_path": "p.dfn",
        },
    )
    assert isinstance(diag_r, diagnostics.InferredRequirementViolationDiagnostic)
    assert diag_r.runner_description == f"the Position Initialization Block of '{_P}'"
    assert diag_r.required_empty is False
    assert diag_r.position_name == "position<box>::position</r>"
    assert diag_r.location.line == 11
    assert diag_r.location.column == 30
    assert diag_r.location.file_path == PurePosixPath("test.dfn")
    assert_propagation_chain(
        diag_r,
        {
            "kind": action_contract.PropagationKind.INIT_BLOCK_TRIGGER,
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
            "line": 6,
            "column": 33,
            "file_path": "p.dfn",
        },
    )


def test_self_reference_in_init_block_publishes_no_requirement(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "child.dfn": "define the potential position<my.domain.com:my_lib:/child>.\n",
            "p.dfn": (
                "define the potential position<my.domain.com:my_lib:/p> {\n"
                "    it may only contain particles where {\n"
                "        it has the position</child>.\n"
                "    }\n"
                "    after it is assigned {\n"
                "        create a particle in position</p>.\n"
                "        create a particle in position</p>::position</child>.\n"
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
                "                it has the position</p>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    assert_no_errors(result.program_result)


def test_init_block_occupied_violation_via_destroy_of_child_of_implied(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "child.dfn": "define the potential position<my.domain.com:my_lib:/child>.\n",
            "q.dfn": (
                "define the potential position<my.domain.com:my_lib:/q> {\n"
                "    it may only contain particles where {\n"
                "        it has the position</child>.\n"
                "    }\n"
                "    after it is assigned {\n"
                "        create a particle in position</q>.\n"
                "    }\n"
                "}\n"
            ),
            "p.dfn": (
                "define the potential position<my.domain.com:my_lib:/p> {\n"
                "    it also assigns the position</q>.\n"
                "    after it is assigned {\n"
                "        destroy the particle in position</q>::position</child>.\n"
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
                "                it has the position</p>.\n"
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
    assert isinstance(
        diag,
        diagnostics.InferredRequirementViolationDiagnostic,
    )
    assert diag.runner_description == f"the Position Initialization Block of '{_P}'"
    assert diag.required_empty is False
    assert diag.position_name == "position<box>::position</q>::position</child>"
    assert diag.location.line == 11
    assert diag.location.column == 30
    assert diag.location.file_path == PurePosixPath("test.dfn")
    assert_propagation_chain(
        diag,
        {
            "kind": action_contract.PropagationKind.INIT_BLOCK_TRIGGER,
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
            "line": 4,
            "column": 33,
            "file_path": "p.dfn",
        },
    )


def test_init_block_occupied_violation_via_move_source_of_child_of_implied(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "child.dfn": "define the potential position<my.domain.com:my_lib:/child>.\n",
            "q.dfn": (
                "define the potential position<my.domain.com:my_lib:/q> {\n"
                "    it may only contain particles where {\n"
                "        it has the position</child>.\n"
                "    }\n"
                "    after it is assigned {\n"
                "        create a particle in position</q>.\n"
                "    }\n"
                "}\n"
            ),
            "p.dfn": (
                "define the potential position<my.domain.com:my_lib:/p> {\n"
                "    it also assigns the position</q>.\n"
                "    after it is assigned {\n"
                "        define the position<_sink>.\n"
                "        move the particle in position</q>::position</child> to position<_sink>.\n"
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
                "                it has the position</p>.\n"
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
    assert isinstance(
        diag,
        diagnostics.InferredRequirementViolationDiagnostic,
    )
    assert diag.runner_description == f"the Position Initialization Block of '{_P}'"
    assert diag.required_empty is False
    assert diag.position_name == "position<box>::position</q>::position</child>"
    assert diag.location.line == 11
    assert diag.location.column == 30
    assert diag.location.file_path == PurePosixPath("test.dfn")
    assert_propagation_chain(
        diag,
        {
            "kind": action_contract.PropagationKind.INIT_BLOCK_TRIGGER,
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
            "line": 5,
            "column": 30,
            "file_path": "p.dfn",
        },
    )


def test_init_block_empty_violation_via_create_in_child_of_implied(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "child.dfn": "define the potential position<my.domain.com:my_lib:/child>.\n",
            "q.dfn": (
                "define the potential position<my.domain.com:my_lib:/q> {\n"
                "    it may only contain particles where {\n"
                "        it has the position</child>.\n"
                "    }\n"
                "    after it is assigned {\n"
                "        create a particle in position</q>.\n"
                "        create a particle in position</q>::position</child>.\n"
                "    }\n"
                "}\n"
            ),
            "p.dfn": (
                "define the potential position<my.domain.com:my_lib:/p> {\n"
                "    it also assigns the position</q>.\n"
                "    after it is assigned {\n"
                "        create a particle in position</q>::position</child>.\n"
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
                "                it has the position</p>.\n"
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
    assert isinstance(
        diag,
        diagnostics.InferredRequirementViolationDiagnostic,
    )
    assert diag.runner_description == f"the Position Initialization Block of '{_P}'"
    assert diag.required_empty is True
    assert diag.position_name == "position<box>::position</q>::position</child>"
    assert diag.location.line == 11
    assert diag.location.column == 30
    assert diag.location.file_path == PurePosixPath("test.dfn")
    assert_propagation_chain(
        diag,
        {
            "kind": action_contract.PropagationKind.INIT_BLOCK_TRIGGER,
            "enclosing_quality_name": _TEST,
            "triggered_quality_name": _P,
            "line": 11,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.FILL_SITE,
            "enclosing_quality_name": "position<box>::position</q>::position</child>",
            "triggered_quality_name": None,
            "line": 7,
            "column": 30,
            "file_path": "q.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": _P,
            "triggered_quality_name": None,
            "line": 4,
            "column": 30,
            "file_path": "p.dfn",
        },
    )


def test_init_block_satisfied_requirement_for_child_of_implied_emits_no_diagnostic(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "child.dfn": "define the potential position<my.domain.com:my_lib:/child>.\n",
            "q.dfn": (
                "define the potential position<my.domain.com:my_lib:/q> {\n"
                "    it may only contain particles where {\n"
                "        it has the position</child>.\n"
                "    }\n"
                "    after it is assigned {\n"
                "        create a particle in position</q>.\n"
                "        create a particle in position</q>::position</child>.\n"
                "    }\n"
                "}\n"
            ),
            "p.dfn": (
                "define the potential position<my.domain.com:my_lib:/p> {\n"
                "    it also assigns the position</q>.\n"
                "    after it is assigned {\n"
                "        destroy the particle in position</q>::position</child>.\n"
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
                "                it has the position</p>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    assert_no_errors(result.program_result)


def test_init_block_occupied_violation_via_destroy_of_grandchild_of_implied(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "grandchild.dfn": "define the potential position<my.domain.com:my_lib:/grandchild>.\n",
            "child.dfn": (
                "define the potential position<my.domain.com:my_lib:/child> {\n"
                "    it may only contain particles where {\n"
                "        it has the position</grandchild>.\n"
                "    }\n"
                "}\n"
            ),
            "q.dfn": (
                "define the potential position<my.domain.com:my_lib:/q> {\n"
                "    it may only contain particles where {\n"
                "        it has the position</child>.\n"
                "    }\n"
                "    after it is assigned {\n"
                "        create a particle in position</q>.\n"
                "        create a particle in position</q>::position</child>.\n"
                "    }\n"
                "}\n"
            ),
            "p.dfn": (
                "define the potential position<my.domain.com:my_lib:/p> {\n"
                "    it also assigns the position</q>.\n"
                "    after it is assigned {\n"
                "        destroy the particle in position</q>::position</child>::position</grandchild>.\n"
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
                "                it has the position</p>.\n"
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
    assert isinstance(
        diag,
        diagnostics.InferredRequirementViolationDiagnostic,
    )
    assert diag.runner_description == f"the Position Initialization Block of '{_P}'"
    assert diag.required_empty is False
    assert (
        diag.position_name
        == "position<box>::position</q>::position</child>::position</grandchild>"
    )
    assert diag.location.line == 11
    assert diag.location.column == 30
    assert diag.location.file_path == PurePosixPath("test.dfn")
    assert_propagation_chain(
        diag,
        {
            "kind": action_contract.PropagationKind.INIT_BLOCK_TRIGGER,
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
            "line": 4,
            "column": 33,
            "file_path": "p.dfn",
        },
    )


def test_init_block_occupied_violation_via_destroy_of_iface_of_action_in_implied_chain(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "a.dfn": (
                "define the potential action<my.domain.com:my_lib:/a> {\n"
                "    define the position<iface>.\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<iface>.\n"
                "        define the position<_noop>.\n"
                "        create a particle in position<_noop>.\n"
                "    }\n"
                "}\n"
            ),
            "outer.dfn": (
                "define the potential position<my.domain.com:my_lib:/outer> {\n"
                "    it may only contain particles where {\n"
                "        it has the action</a>.\n"
                "    }\n"
                "}\n"
            ),
            "q.dfn": (
                "define the potential position<my.domain.com:my_lib:/q> {\n"
                "    it may only contain particles where {\n"
                "        it has the position</outer>.\n"
                "    }\n"
                "    after it is assigned {\n"
                "        create a particle in position</q>.\n"
                "        create a particle in position</q>::position</outer>.\n"
                "    }\n"
                "}\n"
            ),
            "p.dfn": (
                "define the potential position<my.domain.com:my_lib:/p> {\n"
                "    it also assigns the position</q>.\n"
                "    after it is assigned {\n"
                "        destroy the particle in position</q>::position</outer>::action</a>::position<iface>.\n"
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
                "                it has the position</p>.\n"
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
    assert isinstance(
        diag,
        diagnostics.InferredRequirementViolationDiagnostic,
    )
    assert diag.runner_description == f"the Position Initialization Block of '{_P}'"
    assert diag.required_empty is False
    assert (
        diag.position_name
        == "position<box>::position</q>::position</outer>::action</a>::position<iface>"
    )
    assert diag.location.line == 11
    assert diag.location.column == 30
    assert diag.location.file_path == PurePosixPath("test.dfn")
    assert_propagation_chain(
        diag,
        {
            "kind": action_contract.PropagationKind.INIT_BLOCK_TRIGGER,
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
            "line": 4,
            "column": 33,
            "file_path": "p.dfn",
        },
    )


def test_init_block_occupied_violation_via_destroy_of_child_of_iface_of_action_in_implied_chain(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "child.dfn": "define the potential position<my.domain.com:my_lib:/child>.\n",
            "a.dfn": (
                "define the potential action<my.domain.com:my_lib:/a> {\n"
                "    define the position<iface> {\n"
                "        it may only contain particles where {\n"
                "            it has the position</child>.\n"
                "        }\n"
                "    }\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<iface>.\n"
                "        define the position<_noop>.\n"
                "        create a particle in position<_noop>.\n"
                "    }\n"
                "}\n"
            ),
            "outer.dfn": (
                "define the potential position<my.domain.com:my_lib:/outer> {\n"
                "    it may only contain particles where {\n"
                "        it has the action</a>.\n"
                "    }\n"
                "}\n"
            ),
            "q.dfn": (
                "define the potential position<my.domain.com:my_lib:/q> {\n"
                "    it may only contain particles where {\n"
                "        it has the position</outer>.\n"
                "    }\n"
                "    after it is assigned {\n"
                "        create a particle in position</q>.\n"
                "        create a particle in position</q>::position</outer>.\n"
                "        create a particle in position</q>::position</outer>::action</a>::position<iface>.\n"
                "    }\n"
                "}\n"
            ),
            "p.dfn": (
                "define the potential position<my.domain.com:my_lib:/p> {\n"
                "    it also assigns the position</q>.\n"
                "    after it is assigned {\n"
                "        destroy the particle in position</q>::position</outer>::action</a>::position<iface>::position</child>.\n"
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
                "                it has the position</p>.\n"
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
    assert isinstance(
        diag,
        diagnostics.InferredRequirementViolationDiagnostic,
    )
    assert diag.runner_description == f"the Position Initialization Block of '{_P}'"
    assert diag.required_empty is False
    assert (
        diag.position_name
        == "position<box>::position</q>::position</outer>::action</a>::position<iface>::position</child>"
    )
    assert diag.location.line == 11
    assert diag.location.column == 30
    assert diag.location.file_path == PurePosixPath("test.dfn")
    assert_propagation_chain(
        diag,
        {
            "kind": action_contract.PropagationKind.INIT_BLOCK_TRIGGER,
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
            "line": 4,
            "column": 33,
            "file_path": "p.dfn",
        },
    )


def test_init_block_action_requirement_violation_via_triggering_implied_action(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "implied_action.dfn": (
                "define the potential action<my.domain.com:my_lib:/implied_action> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<item>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        destroy the particle in position<item>.\n"
                "    }\n"
                "}\n"
            ),
            "carrier.dfn": (
                "define the potential position<my.domain.com:my_lib:/carrier> {\n"
                "    it may only contain particles where {\n"
                "        it has the action</implied_action>.\n"
                "    }\n"
                "}\n"
            ),
            "p.dfn": (
                "define the potential position<my.domain.com:my_lib:/p> {\n"
                "    it also assigns the position</carrier>.\n"
                "    after it is assigned {\n"
                "        create a particle in position</p>.\n"
                "        create a particle in position</carrier>.\n"
                "        create a particle in position</carrier>::action</implied_action>::position<trigger_pos>.\n"
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
                "                it has the position</p>.\n"
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
    assert diag.location.line == 6
    assert diag.location.column == 30
    assert diag.location.end_line == 6
    assert diag.location.end_column == 96
    assert diag.location.file_path == PurePosixPath("p.dfn")
    assert diag.runner_description == f"'{_IMPLIED_ACTION}'"
    assert diag.required_empty is False
    assert (
        diag.position_name
        == "position</carrier>::action</implied_action>::position<item>"
    )
    assert_propagation_chain(
        diag,
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _P,
            "triggered_quality_name": _IMPLIED_ACTION,
            "line": 6,
            "column": 30,
            "file_path": "p.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": _IMPLIED_ACTION,
            "triggered_quality_name": None,
            "line": 7,
            "column": 33,
            "file_path": "implied_action.dfn",
        },
    )
