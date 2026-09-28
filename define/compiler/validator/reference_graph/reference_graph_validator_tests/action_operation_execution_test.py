"""Reference graph validation of Operation Execution Statements in actions."""

from __future__ import annotations

from pathlib import PurePosixPath
from typing import TYPE_CHECKING

from define.compiler import diagnostics
from define.compiler.validator.reference_graph import action_contract
from define.compiler.validator.reference_graph.reference_graph_validator_tests.test_helpers import (
    assert_propagation_chain,
)
from define.compiler.validator.test_helpers import assert_no_errors

if TYPE_CHECKING:
    from define.compiler.conftest import (
        ValidateTestdataNonFilesystemWithReferenceGraph,
        ValidateTestdataProjectWithReferenceGraph,
    )


def test_empty_position(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.OperationArgumentEmptyPositionDiagnostic)
    assert diagnostic.location.file_path is None
    assert diagnostic.location.line == 34
    assert diagnostic.location.column == 42
    assert diagnostic.position_name == "position<second>"


def test_empty_parent(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.ParentPositionNotOccupiedDiagnostic)
    assert diagnostic.location.file_path is None
    assert diagnostic.location.line == 43
    assert diagnostic.location.column == 42
    assert diagnostic.position_name == "position<box>::position</child>"
    assert diagnostic.parent_position_name == "position<box>"


def test_unset_value(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.UnsetValueDiagnostic)
    assert diagnostic.location.file_path is None
    assert diagnostic.location.line == 39
    assert diagnostic.location.column == 41
    assert diagnostic.position_name == "position<second>"


def test_unset_value_reported_once(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.UnsetValueDiagnostic)
    assert diagnostic.location.file_path is None
    assert diagnostic.location.line == 40
    assert diagnostic.location.column == 41
    assert diagnostic.position_name == "position<second>"


def test_invalid_looked_at_position(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 2
    first, second = result.all_diagnostics
    assert isinstance(first, diagnostics.UndefinedLocalNameDiagnostic)
    assert first.location.file_path is None
    assert first.location.line == 26
    assert first.location.column == 42
    assert first.local_name == "position<missing>"
    assert isinstance(second, diagnostics.OperationArgumentEmptyPositionDiagnostic)
    assert second.location.file_path is None
    assert second.location.line == 27
    assert second.location.column == 42
    assert second.position_name == "position<second>"


def test_prior_error(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.MoveFromEmptyPositionDiagnostic)
    assert diagnostic.location.file_path is None
    assert diagnostic.location.line == 33
    assert diagnostic.location.column == 30
    assert diagnostic.position_name == "position<empty>"
    assert diagnostic.is_action_interface_position is False
    assert diagnostic.inferred_at is None


def test_requires_set_value_set(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_result
    assert_no_errors(result)


def test_requires_set_value_unset(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_result
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.InferredRequirementViolationDiagnostic)
    assert diagnostic.location.file_path == PurePosixPath("test.dfn")
    assert diagnostic.location.line == 13
    assert diagnostic.location.column == 30
    assert (
        diagnostic.position_name == "position<worker>::action</run>::position<number>"
    )
    assert diagnostic.required_value is True
    assert diagnostic.required_empty is False
    assert diagnostic.action_name == "action<my.domain.com:my_lib:/run>"
    assert_propagation_chain(
        diagnostic,
        {
            "kind": action_contract.PropagationKind.FILL_SITE,
            "enclosing_quality_name": "position<worker>::action</run>::position<number>",
            "triggered_quality_name": None,
            "line": 12,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/test>",
            "triggered_quality_name": "action<my.domain.com:my_lib:/run>",
            "line": 13,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/run>",
            "triggered_quality_name": None,
            "line": 13,
            "column": 41,
            "file_path": "run.dfn",
        },
    )


def test_requires_occupied(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_result
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.InferredRequirementViolationDiagnostic)
    assert diagnostic.location.file_path == PurePosixPath("test.dfn")
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
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/test>",
            "triggered_quality_name": "action<my.domain.com:my_lib:/run>",
            "line": 12,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/run>",
            "triggered_quality_name": None,
            "line": 13,
            "column": 42,
            "file_path": "run.dfn",
        },
    )
