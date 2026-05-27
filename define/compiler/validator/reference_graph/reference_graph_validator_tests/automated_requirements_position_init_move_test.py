# pyright: reportUnusedCallResult=false

from pathlib import PurePosixPath

from define.compiler import diagnostics
from define.compiler.conftest import ValidateProjectWithReferenceGraph
from define.compiler.validator.reference_graph import action_contract
from define.compiler.validator.reference_graph.reference_graph_validator_tests.test_helpers import (
    assert_propagation_chain,
)
from define.compiler.validator.test_helpers import assert_no_errors

_P = "position<my.domain.com:my_lib:/p>"


def test_init_block_occupied_requirement_via_destroy_of_child_of_moved_implied(
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
                "define the potential position<my.domain.com:my_lib:/p> {\n"
                "    it also assigns the position</q>.\n"
                "    after it is assigned {\n"
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
    assert isinstance(
        all_diags[0], diagnostics.PositionInitBlockRequiresOccupiedPositionDiagnostic
    )
    assert all_diags[0].location.line == 11
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].create_target_name == "position<box>"
    assert all_diags[0].init_block_position_name == _P
    assert all_diags[0].position_name == "position<box>::position</q>"
    assert_propagation_chain(
        all_diags[0],
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": _P,
            "triggered_quality_name": None,
            "line": 9,
            "column": 30,
            "file_path": "p.dfn",
        },
    )
    assert isinstance(
        all_diags[1], diagnostics.PositionInitBlockRequiresOccupiedPositionDiagnostic
    )
    assert all_diags[1].location.line == 11
    assert all_diags[1].location.column == 30
    assert all_diags[1].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[1].create_target_name == "position<box>"
    assert all_diags[1].init_block_position_name == _P
    assert (
        all_diags[1].position_name == "position<box>::position</q>::position</q_child>"
    )
    assert_propagation_chain(
        all_diags[1],
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": _P,
            "triggered_quality_name": None,
            "line": 10,
            "column": 33,
            "file_path": "p.dfn",
        },
    )


def test_init_block_empty_requirement_via_create_in_child_of_moved_implied(
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
                "    after it is assigned {\n"
                "        create a particle in position</q>.\n"
                "        create a particle in position</q>::position</q_child>.\n"
                "    }\n"
                "}\n"
            ),
            "p.dfn": (
                "define the potential position<my.domain.com:my_lib:/p> {\n"
                "    it also assigns the position</q>.\n"
                "    after it is assigned {\n"
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
        diag, diagnostics.PositionInitBlockRequiresEmptyPositionDiagnostic
    )
    assert diag.location.line == 11
    assert diag.location.column == 30
    assert diag.location.file_path == PurePosixPath("test.dfn")
    assert diag.create_target_name == "position<box>"
    assert diag.init_block_position_name == _P
    assert diag.position_name == "position<box>::position</q>::position</q_child>"
    assert diag.filled_at.line == 7
    assert diag.filled_at.column == 30
    assert diag.filled_at.file_path == PurePosixPath("q.dfn")
    assert_propagation_chain(
        diag,
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": _P,
            "triggered_quality_name": None,
            "line": 10,
            "column": 30,
            "file_path": "p.dfn",
        },
    )


def test_init_block_occupied_requirement_via_destroy_of_child_of_moved_to_implied(
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
                "    after it is assigned {\n"
                "        create a particle in position</q>.\n"
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
            "p.dfn": (
                "define the potential position<my.domain.com:my_lib:/p> {\n"
                "    it also assigns the position</q>.\n"
                "    it also assigns the position</q2>.\n"
                "    after it is assigned {\n"
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
        diag, diagnostics.PositionInitBlockRequiresOccupiedPositionDiagnostic
    )
    assert diag.location.line == 11
    assert diag.location.column == 30
    assert diag.location.file_path == PurePosixPath("test.dfn")
    assert diag.create_target_name == "position<box>"
    assert diag.init_block_position_name == _P
    assert diag.position_name == "position<box>::position</q>::position</q_child>"
    assert_propagation_chain(
        diag,
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": _P,
            "triggered_quality_name": None,
            "line": 6,
            "column": 33,
            "file_path": "p.dfn",
        },
    )


def test_init_block_empty_requirement_via_create_in_child_of_moved_to_implied(
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
                "    after it is assigned {\n"
                "        create a particle in position</q>.\n"
                "        create a particle in position</q>::position</q_child>.\n"
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
            "p.dfn": (
                "define the potential position<my.domain.com:my_lib:/p> {\n"
                "    it also assigns the position</q>.\n"
                "    it also assigns the position</q2>.\n"
                "    after it is assigned {\n"
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
        diag, diagnostics.PositionInitBlockRequiresEmptyPositionDiagnostic
    )
    assert diag.location.line == 11
    assert diag.location.column == 30
    assert diag.location.file_path == PurePosixPath("test.dfn")
    assert diag.create_target_name == "position<box>"
    assert diag.init_block_position_name == _P
    assert diag.position_name == "position<box>::position</q>::position</q_child>"
    assert diag.filled_at.line == 7
    assert diag.filled_at.column == 30
    assert diag.filled_at.file_path == PurePosixPath("q.dfn")
    assert_propagation_chain(
        diag,
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": _P,
            "triggered_quality_name": None,
            "line": 6,
            "column": 30,
            "file_path": "p.dfn",
        },
    )


def test_init_block_occupied_requirement_satisfied_for_moved_to_implied(
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
                "    after it is assigned {\n"
                "        create a particle in position</q>.\n"
                "        create a particle in position</q>::position</q_child>.\n"
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
            "p.dfn": (
                "define the potential position<my.domain.com:my_lib:/p> {\n"
                "    it also assigns the position</q>.\n"
                "    it also assigns the position</q2>.\n"
                "    after it is assigned {\n"
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


def test_init_block_empty_requirement_satisfied_for_moved_to_implied(
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
                "    after it is assigned {\n"
                "        create a particle in position</q>.\n"
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
            "p.dfn": (
                "define the potential position<my.domain.com:my_lib:/p> {\n"
                "    it also assigns the position</q>.\n"
                "    it also assigns the position</q2>.\n"
                "    after it is assigned {\n"
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
