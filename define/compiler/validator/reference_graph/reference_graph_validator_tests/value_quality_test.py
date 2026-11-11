"""Reference graph validation of value qualities."""

from __future__ import annotations

from typing import TYPE_CHECKING

from crates.source_rendering.python import rendering
from define.compiler.errors import diagnostics
from define.compiler.validator.test_helpers import assert_no_errors

if TYPE_CHECKING:
    from define.compiler.conftest import ValidateTestdataProjectWithReferenceGraph


def test_create_and_destroy(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    assert_no_errors(validate_testdata_project_with_reference_graph().program_result)


def test_move_matching_value(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    assert_no_errors(validate_testdata_project_with_reference_graph().program_result)


def test_move_mismatched_value(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_result
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.MoveMissingQualitiesDiagnostic)
    assert diagnostic.location.line == 27
    assert diagnostic.location.column == 50
    assert diagnostic.location.file_path == "test.dfn"
    assert diagnostic.source_position == "position<source>"
    assert diagnostic.target_position == "position<target>"
    assert diagnostic.missing_qualities == ["value<standard:/number/integer>"]


def test_move_without_value(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_result
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.MoveMissingQualitiesDiagnostic)
    assert diagnostic.location.line == 19
    assert diagnostic.location.column == 50
    assert diagnostic.location.file_path == "test.dfn"
    assert diagnostic.source_position == "position<source>"
    assert diagnostic.target_position == "position<target>"
    assert diagnostic.missing_qualities == ["value<standard:/number/natural>"]


def test_move_through_position_without_qualities(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    assert_no_errors(validate_testdata_project_with_reference_graph().program_result)


def test_action_matching_value(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    assert_no_errors(validate_testdata_project_with_reference_graph().program_result)


def test_action_mismatched_value(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_result
    assert len(result.all_diagnostics) == 2
    untriggered = result.all_diagnostics[0]
    assert isinstance(untriggered, diagnostics.UntriggeredActionDiagnostic)
    assert untriggered.location.line == 9
    assert untriggered.location.column == 28
    assert untriggered.location.file_path == "test.dfn"
    assert untriggered.position_name == "position<worker>"
    assert untriggered.quality_name == "action</consume>"
    diagnostic = result.all_diagnostics[1]
    assert isinstance(diagnostic, diagnostics.MoveMissingQualitiesDiagnostic)
    assert diagnostic.location.line == 22
    assert diagnostic.location.column == 50
    assert diagnostic.location.file_path == "test.dfn"
    assert diagnostic.source_position == "position<source>"
    assert (
        diagnostic.target_position
        == "position<worker>::action</consume>::position<input>"
    )
    assert diagnostic.missing_qualities == ["value</text>"]


def test_action_preserves_value_through_positions_without_qualities(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    assert_no_errors(validate_testdata_project_with_reference_graph().program_result)


def test_callee_without_qualities_destroys_value_particle(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    assert_no_errors(validate_testdata_project_with_reference_graph().program_result)


def test_value_use_keeps_only_origin_alive(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_result
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.DeadValueQualityAssignmentDiagnostic)
    assert diagnostic.location.column == 28
    assert diagnostic.position_name == "position<target>"
    assert diagnostic.quality_name == "value<standard:/number/natural>"
    assert diagnostic.location.line == 14
    assert diagnostic.location.file_path == "test.dfn"


def test_value_setting_target_keeps_only_origin_alive(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_result
    assert len(result.all_diagnostics) == 2
    diagnostic = result.all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.DeadValueQualityAssignmentDiagnostic)
    assert diagnostic.location.column == 28
    assert diagnostic.position_name == "position<target>"
    assert diagnostic.quality_name == "value<standard:/number/natural>"
    assert diagnostic.location.line == 13
    assert diagnostic.location.file_path == "test.dfn"
    dead_write = result.all_diagnostics[1]
    assert isinstance(dead_write, diagnostics.DeadValueWriteDiagnostic)
    assert dead_write.location.line == 26
    assert dead_write.location.column == 26
    assert dead_write.location.file_path == "test.dfn"
    assert dead_write.position_name == "position<target>"


def test_guaranteed_created_value(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph(
        allow_entry_action_interface_positions=True
    ).program_result
    assert_no_errors(result)


def test_guaranteed_moved_value(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph(
        allow_entry_action_interface_positions=True
    ).program_result
    assert_no_errors(result)


def test_guaranteed_value_through_local(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph(
        allow_entry_action_interface_positions=True
    ).program_result
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.DeadValueQualityAssignmentDiagnostic)
    assert diagnostic.location.column == 28
    assert diagnostic.position_name == "position<middle>"
    assert diagnostic.quality_name == "value</number>"
    assert diagnostic.location.line == 18
    assert diagnostic.location.file_path == "test.dfn"


def test_required_value_used_after_move(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph(
        allow_entry_action_interface_positions=True
    ).program_result
    assert_no_errors(result)


def test_callee_contract_keeps_only_origin_alive(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_result
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.DeadValueQualityAssignmentDiagnostic)
    assert diagnostic.location.column == 28
    assert diagnostic.position_name == "position<middle>"
    assert diagnostic.quality_name == "value<standard:/number/natural>"
    assert diagnostic.location.line == 18
    assert diagnostic.location.file_path == "test.dfn"


def test_callee_contract_through_position_without_qualities(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_result
    assert_no_errors(result)


def test_unused_local_value_is_dead(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_result
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.DeadValueQualityAssignmentDiagnostic)
    assert diagnostic.position_name == "position<item>"
    assert diagnostic.quality_name == "value</number>"
    assert diagnostic.location.file_path == "test.dfn"
    assert diagnostic.location.line == 8
    assert diagnostic.location.column == 28


def test_moving_values_does_not_keep_quality_assignments_alive(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_result
    assert len(result.all_diagnostics) == 2
    diagnostic = result.all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.DeadValueQualityAssignmentDiagnostic)
    assert diagnostic.position_name == "position<source>"
    assert diagnostic.quality_name == "value</number>"
    assert diagnostic.location.file_path == "test.dfn"
    assert diagnostic.location.line == 8
    assert diagnostic.location.column == 28
    diagnostic = result.all_diagnostics[1]
    assert isinstance(diagnostic, diagnostics.DeadValueQualityAssignmentDiagnostic)
    assert diagnostic.position_name == "position<target>"
    assert diagnostic.quality_name == "value</number>"
    assert diagnostic.location.file_path == "test.dfn"
    assert diagnostic.location.line == 13
    assert diagnostic.location.column == 28


def test_callee_without_qualities_does_not_keep_value_alive(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_result
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.DeadValueQualityAssignmentDiagnostic)
    assert diagnostic.position_name == "position<source>"
    assert diagnostic.quality_name == "value</number>"
    assert diagnostic.location.file_path == "test.dfn"
    assert diagnostic.location.line == 13
    assert diagnostic.location.column == 28


def test_value_read_keeps_only_interface_origin_alive(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph(
        allow_entry_action_interface_positions=True
    ).program_result
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.DeadValueQualityAssignmentDiagnostic)
    assert diagnostic.position_name == "position<moved>"
    assert diagnostic.quality_name == "value</number>"
    assert diagnostic.location.file_path == "test.dfn"
    assert diagnostic.location.line == 14
    assert diagnostic.location.column == 28


def test_unused_interface_value_is_dead(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph(
        allow_entry_action_interface_positions=True
    ).program_result
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.DeadValueQualityAssignmentDiagnostic)
    assert diagnostic.position_name == "position<input>"
    assert diagnostic.quality_name == "value</number>"
    assert diagnostic.location.file_path == "test.dfn"
    assert diagnostic.location.line == 5
    assert diagnostic.location.column == 24


def test_project_value_encoding(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert result.reference_graph_result.codegen_input.value_encodings == {
        "value<my.domain.com:my_lib:/test>": "encoding<my.domain.com:my_lib:/test/digits>"
    }


def test_associated_encoding_not_defined(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_diagnostics == [
        diagnostics.ReferencedFileNotFoundDiagnostic(
            location=rendering.SourceLocation(
                line=2, column=22, end_line=2, end_column=54, file_path="test.dfn"
            ),
            file_path="test/missing.dfn",
        )
    ]


def test_literal_sets_undefined_value(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_diagnostics == [
        diagnostics.ReferencedFileNotFoundDiagnostic(
            location=rendering.SourceLocation(
                line=8, column=34, end_line=8, end_column=39, file_path="test.dfn"
            ),
            file_path="count.dfn",
        ),
        diagnostics.DeadValueWriteDiagnostic(
            location=rendering.SourceLocation(
                line=12, column=26, end_line=12, end_column=39, file_path="test.dfn"
            ),
            position_name="position<item>",
        ),
    ]
