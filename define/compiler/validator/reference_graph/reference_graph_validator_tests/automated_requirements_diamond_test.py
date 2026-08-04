# pyright: reportUnusedCallResult=false
# Exception to CLAUDE.md "no docstrings in tests" rule: these tests have docstrings
# because the automated guarantee/requirement scenarios are complex enough to need
# prose explanations of what each test verifies.

from pathlib import PurePosixPath

from define.compiler import diagnostics
from define.compiler.conftest import (
    ValidateTestdataProjectWithReferenceGraph,
)
from define.compiler.validator.reference_graph import action_contract
from define.compiler.validator.reference_graph.operation_graph_renderer import (
    action_graph_set,
)
from define.compiler.validator.reference_graph.reference_graph_validator_tests.test_helpers import (
    assert_propagation_chain,
)
from define.compiler.validator.test_helpers import assert_no_errors

_TEST = "action<my.domain.com:my_lib:/test>"
_ACT_B = "action<my.domain.com:my_lib:/act_b>"
_ACT_C = "action<my.domain.com:my_lib:/act_c>"
_SHARED = "action<my.domain.com:my_lib:/shared>"

_SHARED_OCCUPIED_REQ = (
    "define the potential action<my.domain.com:my_lib:/shared> {\n"
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

_SHARED_EMPTY_REQ = (
    "define the potential action<my.domain.com:my_lib:/shared> {\n"
    "    define the position<trigger_pos>.\n"
    "    define the position<item>.\n"
    "    it happens when {\n"
    "        the position<trigger_pos> has a particle.\n"
    "    } and it does {\n"
    "        create a particle in position<item>.\n"
    "    }\n"
    "}\n"
)

_ACT_B_TRIGGERS_SHARED = (
    "define the potential action<my.domain.com:my_lib:/act_b> {\n"
    "    define the position<pp>.\n"
    "    define the position<gateway> {\n"
    "        it may only contain particles where {\n"
    "            it has the action</shared>.\n"
    "        }\n"
    "    }\n"
    "    it happens when {\n"
    "        the position<pp> has a particle.\n"
    "    } and it does {\n"
    "        create a particle in position<gateway>::action</shared>::position<trigger_pos>.\n"
    "    }\n"
    "}\n"
)

_ACT_C_TRIGGERS_SHARED = (
    "define the potential action<my.domain.com:my_lib:/act_c> {\n"
    "    define the position<pp>.\n"
    "    define the position<gateway> {\n"
    "        it may only contain particles where {\n"
    "            it has the action</shared>.\n"
    "        }\n"
    "    }\n"
    "    it happens when {\n"
    "        the position<pp> has a particle.\n"
    "    } and it does {\n"
    "        create a particle in position<gateway>::action</shared>::position<trigger_pos>.\n"
    "    }\n"
    "}\n"
)


def test_diamond_both_paths_satisfy_empty_requirement(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert action_graph_set(result.operation_graphs) == {
        (_TEST, _ACT_B),
        (_TEST, _ACT_C),
        (_ACT_B, _SHARED),
        (_ACT_C, _SHARED),
    }


def test_diamond_one_path_violates_empty_requirement(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.InferredRequirementViolationDiagnostic)
    assert all_diags[0].action_name == _ACT_B
    assert all_diags[0].required_empty is True
    assert (
        all_diags[0].position_name
        == "position<box_b>::action</act_b>::position<gateway>::action</shared>::position<item>"
    )
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert action_graph_set(result.operation_graphs) == {
        (_TEST, _ACT_B),
        (_TEST, _ACT_C),
        (_ACT_B, _SHARED),
        (_ACT_C, _SHARED),
    }


def test_diamond_other_path_violates_empty_requirement(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.InferredRequirementViolationDiagnostic)
    assert all_diags[0].action_name == _ACT_C
    assert all_diags[0].required_empty is True
    assert (
        all_diags[0].position_name
        == "position<box_c>::action</act_c>::position<gateway>::action</shared>::position<item>"
    )
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert action_graph_set(result.operation_graphs) == {
        (_TEST, _ACT_B),
        (_TEST, _ACT_C),
        (_ACT_B, _SHARED),
        (_ACT_C, _SHARED),
    }


def test_diamond_occupied_requirement_independent_per_path(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.InferredRequirementViolationDiagnostic)
    assert all_diags[0].action_name == _ACT_C
    assert all_diags[0].required_empty is False
    assert (
        all_diags[0].position_name
        == "position<box_c>::action</act_c>::position<gateway>::action</shared>::position<item>"
    )
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].location.line == 28
    assert all_diags[0].location.column == 30
    assert_propagation_chain(
        all_diags[0],
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _TEST,
            "triggered_quality_name": _ACT_C,
            "line": 28,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _ACT_C,
            "triggered_quality_name": _SHARED,
            "line": 11,
            "column": 30,
            "file_path": "act_c.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": _SHARED,
            "triggered_quality_name": None,
            "line": 8,
            "column": 30,
            "file_path": "shared.dfn",
        },
    )
    assert action_graph_set(result.operation_graphs) == {
        (_TEST, _ACT_B),
        (_TEST, _ACT_C),
        (_ACT_B, _SHARED),
        (_ACT_C, _SHARED),
    }


def test_diamond_top_caller_satisfies_occupied_requirement(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert action_graph_set(result.operation_graphs) == {
        (_TEST, _ACT_B),
        (_TEST, _ACT_C),
        (_ACT_B, _SHARED),
        (_ACT_C, _SHARED),
    }


def test_diamond_one_path_violates_occupied_requirement(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.InferredRequirementViolationDiagnostic)
    assert all_diags[0].action_name == _ACT_C
    assert all_diags[0].required_empty is False
    assert (
        all_diags[0].position_name
        == "position<box_c>::action</act_c>::position<gateway>::action</shared>::position<item>"
    )
    assert all_diags[0].location.line == 26
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert_propagation_chain(
        all_diags[0],
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _TEST,
            "triggered_quality_name": _ACT_C,
            "line": 26,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _ACT_C,
            "triggered_quality_name": _SHARED,
            "line": 11,
            "column": 30,
            "file_path": "act_c.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": _SHARED,
            "triggered_quality_name": None,
            "line": 8,
            "column": 30,
            "file_path": "shared.dfn",
        },
    )
    assert action_graph_set(result.operation_graphs) == {
        (_TEST, _ACT_B),
        (_TEST, _ACT_C),
        (_ACT_B, _SHARED),
        (_ACT_C, _SHARED),
    }


def test_diamond_neither_path_satisfies_occupied_requirement(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 2
    assert isinstance(all_diags[0], diagnostics.InferredRequirementViolationDiagnostic)
    assert all_diags[0].action_name == _ACT_B
    assert all_diags[0].required_empty is False
    assert (
        all_diags[0].position_name
        == "position<box_b>::action</act_b>::position<gateway>::action</shared>::position<item>"
    )
    assert all_diags[0].location.line == 22
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert_propagation_chain(
        all_diags[0],
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _TEST,
            "triggered_quality_name": _ACT_B,
            "line": 22,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _ACT_B,
            "triggered_quality_name": _SHARED,
            "line": 11,
            "column": 30,
            "file_path": "act_b.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": _SHARED,
            "triggered_quality_name": None,
            "line": 8,
            "column": 30,
            "file_path": "shared.dfn",
        },
    )
    assert isinstance(all_diags[1], diagnostics.InferredRequirementViolationDiagnostic)
    assert all_diags[1].action_name == _ACT_C
    assert all_diags[1].required_empty is False
    assert (
        all_diags[1].position_name
        == "position<box_c>::action</act_c>::position<gateway>::action</shared>::position<item>"
    )
    assert all_diags[1].location.line == 25
    assert all_diags[1].location.column == 30
    assert all_diags[1].location.file_path == PurePosixPath("test.dfn")
    assert_propagation_chain(
        all_diags[1],
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _TEST,
            "triggered_quality_name": _ACT_C,
            "line": 25,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _ACT_C,
            "triggered_quality_name": _SHARED,
            "line": 11,
            "column": 30,
            "file_path": "act_c.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": _SHARED,
            "triggered_quality_name": None,
            "line": 8,
            "column": 30,
            "file_path": "shared.dfn",
        },
    )
    assert action_graph_set(result.operation_graphs) == {
        (_TEST, _ACT_B),
        (_TEST, _ACT_C),
        (_ACT_B, _SHARED),
        (_ACT_C, _SHARED),
    }
