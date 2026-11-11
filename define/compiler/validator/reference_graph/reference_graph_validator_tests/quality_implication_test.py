# pyright: reportUnusedCallResult=false
from __future__ import annotations

from typing import TYPE_CHECKING

from crates.source_rendering.python import rendering
from define.compiler.errors import diagnostics
from define.compiler.validator.reference_graph import propagation_step
from define.compiler.validator.reference_graph.reference_graph_validator_tests.test_helpers import (
    assert_propagation_chain,
)
from define.compiler.validator.test_helpers import assert_no_errors

if TYPE_CHECKING:
    from define.compiler import conftest


def test_action_implies_action(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    assert_no_errors(validate_testdata_project_with_reference_graph().program_result)


def test_action_implies_position(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    assert_no_errors(validate_testdata_project_with_reference_graph().program_result)


def test_action_with_implied_qualities_and_multiple_interface_positions(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    assert_no_errors(validate_testdata_project_with_reference_graph().program_result)


def test_action_with_multiple_implications(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    assert_no_errors(validate_testdata_project_with_reference_graph().program_result)


def test_multiple_implications_one_definition(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    assert_no_errors(validate_testdata_project_with_reference_graph().program_result)


def test_position_implies_action(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    assert_no_errors(validate_testdata_project_with_reference_graph().program_result)


def test_diamond_transitivity(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    assert_no_errors(validate_testdata_project_with_reference_graph().program_result)


def test_multi_level_action_transitivity(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    assert_no_errors(validate_testdata_project_with_reference_graph().program_result)


def test_propagated_particle(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    assert_no_errors(validate_testdata_project_with_reference_graph().program_result)


def test_single_level_transitivity_satisfies_move(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph(
        allow_entry_action_interface_positions=True
    )
    assert_no_errors(result.program_result)


def test_single_level_transitivity_does_not_include_unrelated(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.MoveMissingQualitiesDiagnostic)
    assert all_diags[0].location.line == 16
    assert all_diags[0].location.column == 50
    assert all_diags[0].location.file_path == "test.dfn"
    assert all_diags[0].source_position == "position<source>"
    assert all_diags[0].target_position == "position<dest>"
    assert all_diags[0].missing_qualities == [
        "position</unrelated>",
    ]


def test_multi_level_transitivity(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph(
        allow_entry_action_interface_positions=True
    )
    assert_no_errors(result.program_result)


def test_diamond_transitivity_create_conflict_detected(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph(
        allow_entry_action_interface_positions=True
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    diag = all_diags[0]
    assert isinstance(diag, diagnostics.InferredRequirementViolationDiagnostic)
    assert diag.required_value is False
    assert diag.required_empty is True
    assert diag.action_name == "action<my.domain.com:my_lib:/implier_two>"
    assert diag.position_name == "position<source>::position</implied>"
    assert diag.location.line == 20
    assert diag.location.column == 30
    assert diag.location.file_path == "test.dfn"
    assert_propagation_chain(
        diag,
        {
            "kind": propagation_step.PropagationKind.QUALITY_ASSIGNED,
            "enclosing_quality_name": "position<source>",
            "triggered_quality_name": "action<my.domain.com:my_lib:/implier_two>",
            "line": 17,
            "column": 28,
            "file_path": "test.dfn",
        },
        {
            "kind": propagation_step.PropagationKind.CONSTRUCTOR_TRIGGER,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/test>",
            "triggered_quality_name": "action<my.domain.com:my_lib:/implier_two>",
            "line": 20,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": propagation_step.PropagationKind.FILL_SITE,
            "enclosing_quality_name": "position<source>::position</implied>",
            "triggered_quality_name": None,
            "line": 6,
            "column": 30,
            "file_path": "implier_one.dfn",
        },
        {
            "kind": propagation_step.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/implier_two>",
            "triggered_quality_name": None,
            "line": 6,
            "column": 30,
            "file_path": "implier_two.dfn",
        },
    )


def test_diamond_transitivity_with_create_destroy_succeeds(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph(
        allow_entry_action_interface_positions=True
    )
    assert_no_errors(result.program_result)


def test_action_interface_position_has_quality_with_implication_move_succeeds(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph(
        allow_entry_action_interface_positions=True
    )
    assert_no_errors(result.program_result)


def test_matching_implied_but_not_matching_impliers_for_move(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.MoveMissingQualitiesDiagnostic)
    assert all_diags[0].location.line == 16
    assert all_diags[0].location.column == 50
    assert all_diags[0].location.file_path == "test.dfn"
    assert all_diags[0].source_position == "position<source>"
    assert all_diags[0].target_position == "position<dest>"
    assert all_diags[0].missing_qualities == [
        "position</independent>",
    ]


def test_action_guarantee_preserves_transitive_qualities(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)


def test_action_creates_particle_in_interface_position_with_implying_quality(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)


def test_constructor_quality_with_implication_carried_into_move(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph(
        allow_entry_action_interface_positions=True
    )
    assert_no_errors(result.program_result)


def test_inferred_occupied_interface_position_has_implication_implied(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph(
        allow_entry_action_interface_positions=True
    )
    assert_no_errors(result.program_result)


def test_propagated_requirement_particle_has_implication_implied(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph(
        allow_entry_action_interface_positions=True
    )
    assert_no_errors(result.program_result)


def test_same_path_in_different_fquns_are_distinct_qualities(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    b_fqun = "mv:define-lang.org:cross_implication_lib_b"
    result = validate_testdata_project_with_reference_graph()
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.MoveMissingQualitiesDiagnostic)
    assert all_diags[0].location.line == 16
    assert all_diags[0].location.column == 50
    assert all_diags[0].location.file_path == "test.dfn"
    assert all_diags[0].source_position == "position<source>"
    assert all_diags[0].target_position == "position<dest>"
    assert all_diags[0].missing_qualities == [
        f"position<{b_fqun}:/foo>",
    ]


def test_constructor_fills_implied_position_for_move(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)


def test_constructor_filled_position_blocks_caller_create(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.CreateInOccupiedPositionDiagnostic)
    assert all_diags[0].location.line == 12
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.end_line == 12
    assert all_diags[0].location.end_column == 65
    assert all_diags[0].location.file_path == "test.dfn"
    assert all_diags[0].position_name == "position<source>::position</implied>"
    assert all_diags[0].populated_at.line == 6
    assert all_diags[0].populated_at.column == 30
    assert all_diags[0].populated_at.end_line == 6
    assert all_diags[0].populated_at.end_column == 47
    assert all_diags[0].populated_at.file_path == "implier.dfn"


def test_unresolved_implication_target_is_skipped(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.ReferencedFileNotFoundDiagnostic)
    assert all_diags[0].location.file_path == "implier.dfn"
    assert all_diags[0].file_path == "missing.dfn"
    assert all_diags[0].location.line == 2
    assert all_diags[0].location.column == 34


def test_circular_implication_with_particle_left_in_implied_position(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph(max_workers=1)
    assert result.program_result.all_diagnostics == [
        diagnostics.UntriggeredImpliedActionDiagnostic(
            location=rendering.SourceLocation(
                line=2,
                column=25,
                end_line=2,
                end_column=34,
                file_path="a.dfn",
            ),
            implied_action_name="action</b>",
        ),
        diagnostics.UntriggeredActionInterfaceDiagnostic(
            location=rendering.SourceLocation(
                line=8,
                column=30,
                end_line=8,
                end_column=39,
                file_path="a.dfn",
            ),
            action_name="action</b>",
            position_name="action</b>::position<kept>",
        ),
        diagnostics.UnusedQualityImplicationDiagnostic(
            location=rendering.SourceLocation(
                line=2,
                column=25,
                end_line=2,
                end_column=34,
                file_path="b.dfn",
            ),
            implication_name="action</a>",
        ),
        diagnostics.CircularGlobalReferenceDiagnostic(
            location=rendering.SourceLocation(
                line=2,
                column=25,
                end_line=2,
                end_column=34,
                file_path="b.dfn",
            ),
            cycle=[
                "action<my.domain.com:my_lib:/a>",
                "action<my.domain.com:my_lib:/b>",
                "action<my.domain.com:my_lib:/a>",
            ],
        ),
        diagnostics.UntriggeredImpliedActionDiagnostic(
            location=rendering.SourceLocation(
                line=2,
                column=25,
                end_line=2,
                end_column=34,
                file_path="b.dfn",
            ),
            implied_action_name="action</a>",
        ),
        diagnostics.UnreferencedPositionDiagnostic(
            location=rendering.SourceLocation(
                line=3,
                column=16,
                end_line=3,
                end_column=29,
                file_path="b.dfn",
            ),
            position_name="position<kept>",
        ),
    ]
