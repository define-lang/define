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
    action_graph,
    action_graph_set,
)
from define.compiler.validator.reference_graph.reference_graph_validator_tests.test_helpers import (
    assert_propagation_chain,
)
from define.compiler.validator.test_helpers import assert_no_errors

_TEST = "action<my.domain.com:my_lib:/test>"
_OTHER = "action<my.domain.com:my_lib:/other>"
_OUTER = "action<my.domain.com:my_lib:/outer>"
_INNER = "action<my.domain.com:my_lib:/inner>"
_CONSTRUCT = "action<my.domain.com:my_lib:/construct>"


def test_create_in_interface_position_starts_empty(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)


def test_create_twice_in_interface_position(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.CreateInOccupiedPositionDiagnostic)
    assert all_diags[0].location.line == 14
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].position_name == "position<box>::action</other>::position<item>"
    assert all_diags[0].populated_at.line == 13
    assert all_diags[0].populated_at.column == 30
    assert all_diags[0].populated_at.file_path == PurePosixPath("test.dfn")


def test_later_transitive_guarantee_wins_between_sibling_calls(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.MoveFromEmptyPositionDiagnostic)
    assert all_diags[0].location.line == 9
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].position_name == "position</item>"
    assert all_diags[0].is_action_interface_position is False
    assert all_diags[0].inferred_at is None
    assert action_graph_set(result.operation_graphs) == {
        (_TEST, "action<my.domain.com:my_lib:/run_both>"),
        (
            "action<my.domain.com:my_lib:/run_both>",
            "action<my.domain.com:my_lib:/call_fill>",
        ),
        (
            "action<my.domain.com:my_lib:/run_both>",
            "action<my.domain.com:my_lib:/call_empty>",
        ),
        (
            "action<my.domain.com:my_lib:/call_fill>",
            "action<my.domain.com:my_lib:/fill_item>",
        ),
        (
            "action<my.domain.com:my_lib:/call_empty>",
            "action<my.domain.com:my_lib:/empty_item>",
        ),
    }


def test_untouched_interface_position_preserved_after_trigger(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 2
    assert isinstance(all_diags[0], diagnostics.CreateInOccupiedPositionDiagnostic)
    assert all_diags[0].location.line == 15
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].position_name == "position<box>::action</other>::position<item>"
    assert all_diags[0].populated_at.line == 13
    assert all_diags[0].populated_at.column == 30
    assert all_diags[0].populated_at.file_path == PurePosixPath("test.dfn")
    assert isinstance(all_diags[1], diagnostics.UnreferencedPositionDiagnostic)
    assert all_diags[1].position_name == "position<item>"
    assert all_diags[1].location.line == 3
    assert all_diags[1].location.column == 25
    assert all_diags[1].location.file_path == PurePosixPath("other.dfn")
    assert action_graph_set(result.operation_graphs) == {(_TEST, _OTHER)}


def test_move_from_guarantee_emptied_interface_position(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.MoveFromEmptyPositionDiagnostic)
    assert all_diags[0].location.line == 15
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert (
        all_diags[0].position_name
        == "position<box>::action</other>::position<trigger_pos>"
    )
    assert all_diags[0].is_action_interface_position is True
    assert all_diags[0].inferred_at is not None
    assert all_diags[0].inferred_at.line == 7
    assert all_diags[0].inferred_at.column == 30
    assert all_diags[0].inferred_at.file_path == PurePosixPath("other.dfn")
    assert action_graph_set(result.operation_graphs) == {(_TEST, _OTHER)}


def test_post_trigger_guaranteed_empty_position_allows_create(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert action_graph_set(result.operation_graphs) == {(_TEST, _OTHER)}


def test_post_trigger_guaranteed_occupied_position_rejects_create(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.CreateInOccupiedPositionDiagnostic)
    assert all_diags[0].location.line == 14
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].position_name == "position<box>::action</other>::position<item>"
    assert all_diags[0].populated_at.line == 7
    assert all_diags[0].populated_at.column == 30
    assert all_diags[0].populated_at.file_path == PurePosixPath("other.dfn")
    assert action_graph_set(result.operation_graphs) == {(_TEST, _OTHER)}


def test_post_trigger_trigger_position_stays_occupied(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.CreateInOccupiedPositionDiagnostic)
    assert all_diags[0].location.line == 14
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert (
        all_diags[0].position_name
        == "position<box>::action</other>::position<trigger_pos>"
    )
    assert all_diags[0].populated_at.line == 13
    assert all_diags[0].populated_at.column == 30
    assert all_diags[0].populated_at.file_path == PurePosixPath("test.dfn")
    assert action_graph_set(result.operation_graphs) == {(_TEST, _OTHER)}


def test_post_trigger_untouched_trigger_allows_move_from(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert action_graph(result.operation_graphs) == [(_TEST, _OTHER)]


def test_second_trigger_cycle_after_guarantee_empties_trigger(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert action_graph_set(result.operation_graphs) == {(_TEST, _OTHER)}


def test_second_trigger_fails_when_guarantee_filled_position(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.InferredRequirementViolationDiagnostic)
    assert all_diags[0].action_name == "action<my.domain.com:my_lib:/other>"
    assert all_diags[0].required_empty is True
    assert all_diags[0].position_name == "position<box>::action</other>::position<item>"
    assert all_diags[0].location.line == 14
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert_propagation_chain(
        all_diags[0],
        {
            "kind": action_contract.PropagationKind.FILL_SITE,
            "enclosing_quality_name": "position<box>::action</other>::position<item>",
            "triggered_quality_name": None,
            "line": 9,
            "column": 30,
            "file_path": "other.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _TEST,
            "triggered_quality_name": _OTHER,
            "line": 14,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": _OTHER,
            "triggered_quality_name": None,
            "line": 9,
            "column": 30,
            "file_path": "other.dfn",
        },
    )
    assert action_graph_set(result.operation_graphs) == {(_TEST, _OTHER)}


def test_second_trigger_fails_when_existing_guarantee_leaves_position_occupied(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.InferredRequirementViolationDiagnostic)
    assert all_diags[0].action_name == "action<my.domain.com:my_lib:/other>"
    assert all_diags[0].required_empty is True
    assert all_diags[0].position_name == "position<box>::action</other>::position<dest>"
    assert all_diags[0].location.line == 20
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert_propagation_chain(
        all_diags[0],
        {
            "kind": action_contract.PropagationKind.FILL_SITE,
            "enclosing_quality_name": "position<box>::action</other>::position<dest>",
            "triggered_quality_name": None,
            "line": 10,
            "column": 48,
            "file_path": "other.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _TEST,
            "triggered_quality_name": _OTHER,
            "line": 20,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": _OTHER,
            "triggered_quality_name": None,
            "line": 10,
            "column": 48,
            "file_path": "other.dfn",
        },
    )
    assert action_graph_set(result.operation_graphs) == {(_TEST, _OTHER)}


def test_second_trigger_fails_occupied_requirement_after_guarantee_empties(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 2
    assert isinstance(all_diags[0], diagnostics.InferredRequirementViolationDiagnostic)
    assert all_diags[0].action_name == "action<my.domain.com:my_lib:/other>"
    assert all_diags[0].required_empty is False
    assert all_diags[0].position_name == "position<box>::action</other>::position<item>"
    assert all_diags[0].location.line == 17
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert_propagation_chain(
        all_diags[0],
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _TEST,
            "triggered_quality_name": _OTHER,
            "line": 17,
            "column": 30,
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
    assert isinstance(all_diags[1], diagnostics.InferredRequirementViolationDiagnostic)
    assert all_diags[1].action_name == "action<my.domain.com:my_lib:/other>"
    assert all_diags[1].required_empty is True
    assert all_diags[1].position_name == "position<box>::action</other>::position<dest>"
    assert all_diags[1].location.line == 17
    assert all_diags[1].location.column == 30
    assert all_diags[1].location.file_path == PurePosixPath("test.dfn")
    assert_propagation_chain(
        all_diags[1],
        {
            "kind": action_contract.PropagationKind.FILL_SITE,
            "enclosing_quality_name": "position<box>::action</other>::position<dest>",
            "triggered_quality_name": None,
            "line": 10,
            "column": 48,
            "file_path": "other.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _TEST,
            "triggered_quality_name": _OTHER,
            "line": 17,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": _OTHER,
            "triggered_quality_name": None,
            "line": 10,
            "column": 48,
            "file_path": "other.dfn",
        },
    )
    assert action_graph_set(result.operation_graphs) == {(_TEST, _OTHER)}


def test_second_trigger_succeeds_with_proper_state_management(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert action_graph_set(result.operation_graphs) == {(_TEST, _OTHER)}


def test_post_trigger_particle_identity_preserved_through_guarantee(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert action_graph_set(result.operation_graphs) == {(_TEST, _OTHER)}


def test_post_trigger_guaranteed_empty_position_allows_move_to(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert action_graph_set(result.operation_graphs) == {(_TEST, _OTHER)}


def test_post_trigger_occupied_by_new_allows_move_from(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert action_graph_set(result.operation_graphs) == {(_TEST, _OTHER)}


def test_post_trigger_occupied_by_new_rejects_move_to(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.MoveToOccupiedPositionDiagnostic)
    assert all_diags[0].location.line == 16
    assert all_diags[0].location.column == 49
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].position_name == "position<box>::action</other>::position<item>"
    assert all_diags[0].occupied_at is not None
    assert all_diags[0].occupied_at.line == 7
    assert all_diags[0].occupied_at.column == 30
    assert all_diags[0].occupied_at.file_path == PurePosixPath("other.dfn")
    assert action_graph_set(result.operation_graphs) == {(_TEST, _OTHER)}


def test_post_trigger_occupied_by_existing_rejects_create(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.CreateInOccupiedPositionDiagnostic)
    assert all_diags[0].location.line == 17
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].position_name == "position<box>::action</other>::position<dest>"
    assert all_diags[0].populated_at.line == 8
    assert all_diags[0].populated_at.column == 48
    assert all_diags[0].populated_at.file_path == PurePosixPath("other.dfn")
    assert action_graph_set(result.operation_graphs) == {(_TEST, _OTHER)}


def test_post_trigger_occupied_by_existing_rejects_move_to(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.MoveToOccupiedPositionDiagnostic)
    assert all_diags[0].location.line == 19
    assert all_diags[0].location.column == 50
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].position_name == "position<box>::action</other>::position<dest>"
    assert all_diags[0].occupied_at is not None
    assert all_diags[0].occupied_at.line == 8
    assert all_diags[0].occupied_at.column == 48
    assert all_diags[0].occupied_at.file_path == PurePosixPath("other.dfn")
    assert action_graph_set(result.operation_graphs) == {(_TEST, _OTHER)}


def test_constructor_trigger_applies_empty_guarantee(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.MoveFromEmptyPositionDiagnostic)
    assert all_diags[0].location.line == 13
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("construct.dfn")
    assert (
        all_diags[0].position_name
        == "position<inner>::action</other>::position<trigger_pos>"
    )
    assert all_diags[0].is_action_interface_position is True
    assert all_diags[0].inferred_at is not None
    assert all_diags[0].inferred_at.line == 7
    assert all_diags[0].inferred_at.column == 30
    assert all_diags[0].inferred_at.file_path == PurePosixPath("other.dfn")
    assert action_graph_set(result.operation_graphs) == {
        (_TEST, _CONSTRUCT),
        (_CONSTRUCT, _OTHER),
    }


def test_constructor_trigger_applies_occupied_guarantee(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.CreateInOccupiedPositionDiagnostic)
    assert all_diags[0].location.line == 12
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("construct.dfn")
    assert (
        all_diags[0].position_name == "position<inner>::action</other>::position<item>"
    )
    assert all_diags[0].populated_at.line == 7
    assert all_diags[0].populated_at.column == 30
    assert all_diags[0].populated_at.file_path == PurePosixPath("other.dfn")
    assert action_graph_set(result.operation_graphs) == {
        (_TEST, _CONSTRUCT),
        (_CONSTRUCT, _OTHER),
    }


def test_trigger_chain_move_guarantee_empties_position(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert action_graph_set(result.operation_graphs) == {(_TEST, _OTHER)}


def test_trigger_chain_create_guarantee_fills_position(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.CreateInOccupiedPositionDiagnostic)
    assert all_diags[0].location.line == 14
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert (
        all_diags[0].position_name
        == "position<box>::action</other>::position<trigger_pos>::position</x>"
    )
    assert all_diags[0].populated_at.line == 10
    assert all_diags[0].populated_at.column == 30
    assert all_diags[0].populated_at.file_path == PurePosixPath("other.dfn")
    assert action_graph_set(result.operation_graphs) == {(_TEST, _OTHER)}


def test_trigger_chain_existing_guarantee_preserves_caller_qualities(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert action_graph_set(result.operation_graphs) == {(_TEST, _OTHER)}


def test_post_trigger_existing_guarantee_on_child_position(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.CreateInOccupiedPositionDiagnostic)
    assert all_diags[0].location.line == 24
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert (
        all_diags[0].position_name
        == "position<box>::action</other>::position<dest>::position</child_q>"
    )
    assert action_graph_set(result.operation_graphs) == {(_TEST, _OTHER)}


def test_post_trigger_empty_guarantee_on_child_position(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.MoveFromEmptyPositionDiagnostic)
    assert all_diags[0].location.line == 22
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert (
        all_diags[0].position_name
        == "position<box>::action</other>::position<item>::position</child_q>"
    )
    assert all_diags[0].is_action_interface_position is True
    assert all_diags[0].inferred_at is None
    assert action_graph_set(result.operation_graphs) == {(_TEST, _OTHER)}


def test_post_trigger_new_guarantee_on_child_position(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.CreateInOccupiedPositionDiagnostic)
    assert all_diags[0].location.line == 14
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert (
        all_diags[0].position_name
        == "position<box>::action</other>::position<item>::position</x>"
    )
    assert action_graph_set(result.operation_graphs) == {(_TEST, _OTHER)}


def test_post_trigger_empty_guarantee_deletes_children(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.ParentPositionNotOccupiedDiagnostic)
    assert all_diags[0].location.line == 29
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert (
        all_diags[0].position_name
        == "position<box>::action</other>::position<item>::position</child_q>"
    )
    assert (
        all_diags[0].parent_position_name
        == "position<box>::action</other>::position<item>"
    )
    assert action_graph_set(result.operation_graphs) == {(_TEST, _OTHER)}


def test_post_trigger_new_guarantee_deletes_old_children(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.MoveFromEmptyPositionDiagnostic)
    assert all_diags[0].location.line == 44
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert (
        all_diags[0].position_name
        == "position<box>::action</other>::position<iface>::position</a>"
    )
    assert all_diags[0].is_action_interface_position is True
    assert all_diags[0].inferred_at is None
    assert action_graph_set(result.operation_graphs) == {(_TEST, _OTHER)}


def test_post_trigger_child_removed_before_parent_move(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert action_graph_set(result.operation_graphs) == {(_TEST, _OTHER)}


def test_post_trigger_parent_and_child_both_have_guarantees(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.CreateInOccupiedPositionDiagnostic)
    assert all_diags[0].location.line == 21
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert (
        all_diags[0].position_name
        == "position<box>::action</other>::position<dest>::position</child_q>"
    )
    assert action_graph_set(result.operation_graphs) == {(_TEST, _OTHER)}


def test_post_trigger_child_guarantee_follows_parent_move(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.CreateInOccupiedPositionDiagnostic)
    assert all_diags[0].location.line == 21
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert (
        all_diags[0].position_name
        == "position<box>::action</other>::position<dest>::position</child_q>"
    )
    assert action_graph_set(result.operation_graphs) == {(_TEST, _OTHER)}


def test_post_trigger_existing_guarantee_empties_origin_children(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.ParentPositionNotOccupiedDiagnostic)
    assert all_diags[0].location.line == 31
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert (
        all_diags[0].position_name
        == "position<box>::action</other>::position<iface>::position</child_q>"
    )
    assert (
        all_diags[0].parent_position_name
        == "position<box>::action</other>::position<iface>"
    )
    assert action_graph_set(result.operation_graphs) == {(_TEST, _OTHER)}


def test_post_trigger_existing_guarantee_on_child_swap(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert action_graph_set(result.operation_graphs) == {(_TEST, _OTHER)}


def test_long_chain_trigger_fires_and_applies_guarantee(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)


def test_long_inner_chained_action_fills_positions_in_caller(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)


def test_long_chain_inner_requirement_enforced_through_nested_trigger(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.InferredRequirementViolationDiagnostic)
    assert all_diags[0].location.line == 20
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].action_name == "action<my.domain.com:my_lib:/outer>"
    assert all_diags[0].required_empty is True
    assert (
        all_diags[0].position_name
        == "position<local>::action</outer>::position<outer_iface>::action</inner>::position<item>"
    )
    assert_propagation_chain(
        all_diags[0],
        {
            "kind": action_contract.PropagationKind.FILL_SITE,
            "enclosing_quality_name": "position<local>::action</outer>::position<outer_iface>::action</inner>::position<item>",
            "triggered_quality_name": None,
            "line": 19,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _TEST,
            "triggered_quality_name": _OUTER,
            "line": 20,
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


def test_destroy_produces_empty_guarantee(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert action_graph_set(result.operation_graphs) == {(_TEST, _OTHER)}


def test_destroy_prunes_children_from_caller(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.ParentPositionNotOccupiedDiagnostic)
    assert all_diags[0].location.line == 26
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert (
        all_diags[0].position_name
        == "position<box>::action</other>::position<item>::position</child_q>"
    )
    assert (
        all_diags[0].parent_position_name
        == "position<box>::action</other>::position<item>"
    )
    assert action_graph_set(result.operation_graphs) == {(_TEST, _OTHER)}


def test_retriggering_same_action_reapplies_its_guarantee_over_a_later_body_change(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    diag = all_diags[0]
    assert isinstance(diag, diagnostics.CreateInOccupiedPositionDiagnostic)
    assert diag.position_name == "position<box>::action</inner>::position<out>"
    assert diag.location.line == 17
    assert diag.location.column == 30
    assert diag.location.file_path == PurePosixPath("test.dfn")


def test_two_actions_with_opposite_guarantees_on_a_shared_position_later_wins(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    diag = all_diags[0]
    assert isinstance(diag, diagnostics.CreateInOccupiedPositionDiagnostic)
    assert diag.position_name == "position<box>::position</shared>"
    assert diag.location.line == 18
    assert diag.location.column == 30
    assert diag.location.file_path == PurePosixPath("test.dfn")


def test_existing_guarantee_on_child_survives_destroying_original_parent(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.CreateInOccupiedPositionDiagnostic)
    assert all_diags[0].location.line == 16
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert (
        all_diags[0].position_name
        == "position<box>::action</other>::position<dest>::position</child_q>"
    )


def test_existing_guarantee_on_child_survives_recreating_original_parent(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.CreateInOccupiedPositionDiagnostic)
    assert all_diags[0].location.line == 16
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert (
        all_diags[0].position_name
        == "position<box>::action</other>::position<dest>::position</child_q>"
    )


def test_nested_existing_guarantees_survive_destroying_original_parent(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.CreateInOccupiedPositionDiagnostic)
    assert all_diags[0].location.line == 17
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert (
        all_diags[0].position_name
        == "position<box>::action</other>::position<dest2>::position</grand>"
    )
    assert all_diags[0].populated_at.line == 23
    assert all_diags[0].populated_at.column == 86
    assert all_diags[0].populated_at.file_path == PurePosixPath("other.dfn")
