"""Reference graph validation of literal sources in Value Setting Statements."""

from __future__ import annotations

from typing import TYPE_CHECKING

from define.compiler.errors import diagnostics
from define.compiler.validator.reference_graph import propagation_step
from define.compiler.validator.reference_graph.reference_graph_validator_tests.test_helpers import (
    assert_propagation_chain,
)
from define.compiler.validator.test_helpers import assert_no_errors

if TYPE_CHECKING:
    from define.compiler.test_fixtures.validation_pipeline import (
        ValidateTestdataProjectWithReferenceGraph,
    )

pytest_plugins = ["define.compiler.test_fixtures.validation_pipeline"]


def test_matching_types(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_validation
    assert_no_errors(result)


def test_invalid_literal_content_with_undefined_target(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_validation
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.UndefinedLocalNameDiagnostic)
    assert diagnostic.location.file_path == "test.dfn"
    assert diagnostic.local_name == "position<missing>"
    assert diagnostic.location.line == 6
    assert diagnostic.location.column == 26


def test_missing_potential_literal(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_validation
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.ReferencedFileNotFoundDiagnostic)
    assert diagnostic.location.file_path == "test.dfn"
    assert diagnostic.file_path == "missing.dfn"
    assert diagnostic.location.line == 8
    assert diagnostic.location.column == 57


def test_target_missing_type(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_validation
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.ValueSettingMissingValueQualityDiagnostic)
    assert diagnostic.location.file_path == "test.dfn"
    assert diagnostic.location.line == 10
    assert diagnostic.location.column == 26
    assert diagnostic.position_name == "position<target>"
    assert diagnostic.origin_position_name == "position<original>"


def test_target_empty(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_validation
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.ValueSettingEmptyPositionDiagnostic)
    assert diagnostic.position_name == "position</target>"
    assert diagnostic.location.file_path == "test.dfn"
    assert diagnostic.location.line == 9
    assert diagnostic.location.column == 26


def test_undefined_position(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_validation
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.UndefinedLocalNameDiagnostic)
    assert diagnostic.local_name == "position<missing>"
    assert diagnostic.location.file_path == "test.dfn"
    assert diagnostic.location.line == 16
    assert diagnostic.location.column == 26


def test_prior_error(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_validation
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.MoveFromEmptyPositionDiagnostic)
    assert diagnostic.position_name == "position<empty>"
    assert diagnostic.is_action_interface_position is False
    assert diagnostic.inferred_at is None
    assert diagnostic.location.file_path == "test.dfn"
    assert diagnostic.location.line == 10
    assert diagnostic.location.column == 30


def test_child_positions(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_validation
    assert_no_errors(result)


def test_empty_parent(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_validation
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.ParentPositionNotOccupiedDiagnostic)
    assert diagnostic.position_name == "position<parent>::position</child>"
    assert diagnostic.parent_position_name == "position<parent>"
    assert diagnostic.location.file_path == "test.dfn"
    assert diagnostic.location.line == 11
    assert diagnostic.location.column == 26


def test_invalid_child(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_validation
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.ChainElementNotAssignedDiagnostic)
    assert diagnostic.element_name == "position<my.domain.com:my_lib:/child>"
    assert diagnostic.parent_name == "position<parent>"
    assert diagnostic.location.file_path == "test.dfn"
    assert diagnostic.location.line == 8
    assert diagnostic.location.column == 44


def test_callee_requirements_satisfied(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_validation
    assert_no_errors(result)


def test_callee_requires_target(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_validation
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.InferredRequirementViolationDiagnostic)
    assert diagnostic.required_value is False
    assert_propagation_chain(
        diagnostic,
        {
            "kind": propagation_step.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/test>",
            "triggered_quality_name": "action<my.domain.com:my_lib:/assign>",
            "line": 12,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": propagation_step.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/assign>",
            "triggered_quality_name": None,
            "line": 11,
            "column": 26,
            "file_path": "assign.dfn",
        },
    )
    assert diagnostic.action_name == "action<my.domain.com:my_lib:/assign>"
    assert diagnostic.location.file_path == "test.dfn"
    assert diagnostic.location.line == 12
    assert diagnostic.location.column == 30
    assert (
        diagnostic.position_name
        == "position<worker>::action</assign>::position<target>"
    )
    assert diagnostic.required_empty is False


def test_callee_target_missing_value_quality(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_validation
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.ValueSettingMissingValueQualityDiagnostic)
    assert diagnostic.location.file_path == "assign.dfn"
    assert diagnostic.location.line == 7
    assert diagnostic.location.column == 26
    assert diagnostic.position_name == "position<target>"
    assert diagnostic.origin_position_name == "position<target>"
