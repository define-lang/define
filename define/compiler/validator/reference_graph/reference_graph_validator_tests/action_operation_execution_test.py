"""Reference graph validation of Operation Execution Statements in actions."""

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
    from define.compiler.test_fixtures.validation_pipeline import (
        ValidateTestdataNonFilesystemWithReferenceGraph,
        ValidateTestdataProjectWithReferenceGraph,
    )

pytest_plugins = ["define.compiler.test_fixtures.validation_pipeline"]


def test_empty_position(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.sorted_diagnostics() == [
        diagnostics.OperationArgumentEmptyPositionDiagnostic(
            location=rendering.SourceLocation(
                line=38, column=42, end_line=38, end_column=57, file_path=None
            ),
            position_name="position<second>",
        )
    ]


def test_missing_operation_after_value_write(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.sorted_diagnostics() == [
        diagnostics.StandardDefinitionNotFoundDiagnostic(
            location=rendering.SourceLocation(
                line=22, column=21, end_line=22, end_column=55
            ),
            definition_name="operation<standard:/number/missing>",
        )
    ]


def test_missing_operation_before_value_read(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.sorted_diagnostics() == [
        diagnostics.StandardDefinitionNotFoundDiagnostic(
            location=rendering.SourceLocation(
                line=42, column=21, end_line=42, end_column=55, file_path=None
            ),
            definition_name="operation<standard:/number/missing>",
        )
    ]


def test_undefined_interface_view_after_value_write(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.sorted_diagnostics() == [
        diagnostics.UndefinedOperationViewDiagnostic(
            location=rendering.SourceLocation(
                line=52, column=18, end_line=52, end_column=28, file_path=None
            ),
            view_name="view<extra>",
            operation_name="operation</show>",
            interface_view_names=["view<value>", "view<result>"],
        )
    ]


def test_empty_parent(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.sorted_diagnostics() == [
        diagnostics.ParentPositionNotOccupiedDiagnostic(
            location=rendering.SourceLocation(
                line=47, column=42, end_line=47, end_column=72, file_path=None
            ),
            position_name="position<box>::position</child>",
            parent_position_name="position<box>",
        )
    ]


def test_unset_value(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.sorted_diagnostics() == [
        diagnostics.UnsetValueDiagnostic(
            location=rendering.SourceLocation(
                line=56, column=41, end_line=56, end_column=56, file_path=None
            ),
            position_name="position<second>",
        )
    ]


def test_unset_value_reported_once(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.sorted_diagnostics() == [
        diagnostics.UnsetValueDiagnostic(
            location=rendering.SourceLocation(
                line=57, column=41, end_line=57, end_column=56, file_path=None
            ),
            position_name="position<second>",
        )
    ]


def test_invalid_looked_at_position(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.sorted_diagnostics() == [
        diagnostics.UndefinedLocalNameDiagnostic(
            location=rendering.SourceLocation(
                line=30, column=42, end_line=30, end_column=58, file_path=None
            ),
            local_name="position<missing>",
        ),
        diagnostics.OperationArgumentEmptyPositionDiagnostic(
            location=rendering.SourceLocation(
                line=31, column=42, end_line=31, end_column=57, file_path=None
            ),
            position_name="position<second>",
        ),
    ]


def test_prior_error(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.sorted_diagnostics() == [
        diagnostics.MoveFromEmptyPositionDiagnostic(
            location=rendering.SourceLocation(
                line=37, column=30, end_line=37, end_column=44, file_path=None
            ),
            position_name="position<empty>",
            is_action_interface_position=False,
            inferred_at=None,
        )
    ]


def test_requires_set_value_set(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_validation
    assert_no_errors(result)


def test_requires_set_value_unset(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_validation
    assert result.sorted_diagnostics() == [
        diagnostics.InferredRequirementViolationDiagnostic(
            location=rendering.SourceLocation(
                line=13, column=30, end_line=13, end_column=78, file_path="test.dfn"
            ),
            position_name="position<worker>::action</run>::position<number>",
            propagation_chain=[
                propagation_step.PropagationStep(
                    location=rendering.SourceLocation(
                        line=12,
                        column=30,
                        end_line=12,
                        end_column=77,
                        file_path="test.dfn",
                    ),
                    kind=propagation_step.PropagationKind.FILL_SITE,
                    enclosing_quality_name="position<worker>::action</run>::position<number>",
                    triggered_quality_name=None,
                ),
                propagation_step.PropagationStep(
                    location=rendering.SourceLocation(
                        line=13,
                        column=30,
                        end_line=13,
                        end_column=78,
                        file_path="test.dfn",
                    ),
                    kind=propagation_step.PropagationKind.ACTION_TRIGGER,
                    enclosing_quality_name="action<my.domain.com:my_lib:/test>",
                    triggered_quality_name="action<my.domain.com:my_lib:/run>",
                ),
                propagation_step.PropagationStep(
                    location=rendering.SourceLocation(
                        line=15,
                        column=41,
                        end_line=15,
                        end_column=56,
                        file_path="run.dfn",
                    ),
                    kind=propagation_step.PropagationKind.DIRECT_INFERENCE,
                    enclosing_quality_name="action<my.domain.com:my_lib:/run>",
                    triggered_quality_name=None,
                ),
            ],
            required_empty=False,
            action_name="action<my.domain.com:my_lib:/run>",
            required_value=True,
        )
    ]


def test_requires_occupied(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_validation
    assert len(result.sorted_diagnostics()) == 1
    diagnostic = result.sorted_diagnostics()[0]
    assert isinstance(diagnostic, diagnostics.InferredRequirementViolationDiagnostic)
    assert diagnostic.location.file_path == "test.dfn"
    assert diagnostic.location.line == 12
    assert diagnostic.location.column == 30
    assert (
        diagnostic.position_name == "position<worker>::action</run>::position<number>"
    )
    assert diagnostic.required_value is False
    assert diagnostic.required_empty is False
    assert diagnostic.action_name == "action<my.domain.com:my_lib:/run>"
    assert_propagation_chain(
        diagnostic,
        {
            "kind": propagation_step.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/test>",
            "triggered_quality_name": "action<my.domain.com:my_lib:/run>",
            "line": 12,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": propagation_step.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/run>",
            "triggered_quality_name": None,
            "line": 13,
            "column": 42,
            "file_path": "run.dfn",
        },
    )
