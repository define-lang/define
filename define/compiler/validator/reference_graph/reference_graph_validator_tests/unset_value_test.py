"""Set-value requirements, guarantees, and destruction-time value state."""

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
    from define.compiler.conftest import ValidateTestdataProjectWithReferenceGraph


def test_new_particle_is_unset(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_result
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert diagnostic.location.file_path == PurePosixPath("test.dfn")
    assert diagnostic.location.line == 18
    assert diagnostic.location.column == 46
    assert isinstance(diagnostic, diagnostics.UnsetValueDiagnostic)
    assert diagnostic.position_name == "position<source>"


def test_literal_initializes_value(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_result
    assert_no_errors(result)


def test_move_preserves_set(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_result
    assert_no_errors(result)


def test_move_preserves_unset(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_result
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert diagnostic.location.file_path == PurePosixPath("test.dfn")
    assert diagnostic.location.line == 20
    assert diagnostic.location.column == 46
    assert isinstance(diagnostic, diagnostics.UnsetValueDiagnostic)
    assert diagnostic.position_name == "position<moved>"


def test_replacement_is_unset(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_result
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert diagnostic.location.file_path == PurePosixPath("test.dfn")
    assert diagnostic.location.line == 21
    assert diagnostic.location.column == 46
    assert isinstance(diagnostic, diagnostics.UnsetValueDiagnostic)
    assert diagnostic.position_name == "position<source>"


def test_trigger_requires_set(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_result
    assert_no_errors(result)


def test_trigger_requires_unset(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_result
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert diagnostic.location.file_path == PurePosixPath("test.dfn")
    assert diagnostic.location.line == 18
    assert diagnostic.location.column == 50
    assert isinstance(diagnostic, diagnostics.InferredRequirementViolationDiagnostic)
    assert (
        diagnostic.position_name
        == "position<worker>::action</consume>::position<input>"
    )
    assert diagnostic.required_value is True
    assert diagnostic.required_empty is False
    assert diagnostic.action_name == "action<my.domain.com:my_lib:/consume>"
    assert_propagation_chain(
        diagnostic,
        {
            "kind": action_contract.PropagationKind.FILL_SITE,
            "enclosing_quality_name": "position<worker>::action</consume>::position<input>",
            "triggered_quality_name": None,
            "line": 18,
            "column": 50,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/test>",
            "triggered_quality_name": "action<my.domain.com:my_lib:/consume>",
            "line": 18,
            "column": 50,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/consume>",
            "triggered_quality_name": None,
            "line": 16,
            "column": 44,
            "file_path": "consume.dfn",
        },
    )


def test_transitive_requirement_set(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_result
    assert_no_errors(result)


def test_transitive_requirement_unset(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_result
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert diagnostic.location.file_path == PurePosixPath("test.dfn")
    assert diagnostic.location.line == 18
    assert diagnostic.location.column == 50
    assert isinstance(diagnostic, diagnostics.InferredRequirementViolationDiagnostic)
    assert (
        diagnostic.position_name == "position<worker>::action</relay>::position<input>"
    )
    assert diagnostic.required_value is True
    assert diagnostic.required_empty is False
    assert diagnostic.action_name == "action<my.domain.com:my_lib:/relay>"
    assert_propagation_chain(
        diagnostic,
        {
            "kind": action_contract.PropagationKind.FILL_SITE,
            "enclosing_quality_name": "position<worker>::action</relay>::position<input>",
            "triggered_quality_name": None,
            "line": 18,
            "column": 50,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/test>",
            "triggered_quality_name": "action<my.domain.com:my_lib:/relay>",
            "line": 18,
            "column": 50,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/relay>",
            "triggered_quality_name": "action<my.domain.com:my_lib:/consume>",
            "line": 16,
            "column": 49,
            "file_path": "relay.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/consume>",
            "triggered_quality_name": None,
            "line": 16,
            "column": 44,
            "file_path": "consume.dfn",
        },
    )


def test_transitive_implied_requirement_set(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_result
    assert_no_errors(result)


def test_transitive_implied_requirement_unset(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_result
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert diagnostic.location.file_path == PurePosixPath("test.dfn")
    assert diagnostic.location.line == 14
    assert diagnostic.location.column == 30
    assert isinstance(diagnostic, diagnostics.InferredRequirementViolationDiagnostic)
    assert diagnostic.required_value is True
    assert diagnostic.position_name == "position<worker>::position</value>"
    assert diagnostic.action_name == "action<my.domain.com:my_lib:/relay>"
    assert diagnostic.required_empty is False
    assert_propagation_chain(
        diagnostic,
        {
            "kind": action_contract.PropagationKind.FILL_SITE,
            "enclosing_quality_name": "position<worker>::position</value>",
            "triggered_quality_name": None,
            "line": 13,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/test>",
            "triggered_quality_name": "action<my.domain.com:my_lib:/relay>",
            "line": 14,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/relay>",
            "triggered_quality_name": "action<my.domain.com:my_lib:/read>",
            "line": 7,
            "column": 30,
            "file_path": "relay.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/read>",
            "triggered_quality_name": None,
            "line": 13,
            "column": 44,
            "file_path": "read.dfn",
        },
    )


def test_set_existing_implied_value(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_result
    assert_no_errors(result)


def test_implied_requirement_after_move(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_result
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert diagnostic.location.file_path == PurePosixPath("test.dfn")
    assert diagnostic.location.line == 14
    assert diagnostic.location.column == 30
    assert isinstance(diagnostic, diagnostics.InferredRequirementViolationDiagnostic)
    assert diagnostic.required_value is True
    assert diagnostic.position_name == "position<worker>::position</value>"
    assert diagnostic.action_name == "action<my.domain.com:my_lib:/read>"
    assert diagnostic.required_empty is False
    assert_propagation_chain(
        diagnostic,
        {
            "kind": action_contract.PropagationKind.FILL_SITE,
            "enclosing_quality_name": "position<worker>::position</value>",
            "triggered_quality_name": None,
            "line": 13,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/test>",
            "triggered_quality_name": "action<my.domain.com:my_lib:/read>",
            "line": 14,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/read>",
            "triggered_quality_name": None,
            "line": 15,
            "column": 44,
            "file_path": "read.dfn",
        },
    )


def test_guarantee_new_set(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_result
    assert_no_errors(result)


def test_guarantee_new_unset(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_result
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert diagnostic.location.file_path == PurePosixPath("test.dfn")
    assert diagnostic.location.line == 19
    assert diagnostic.location.column == 44
    assert isinstance(diagnostic, diagnostics.UnsetValueDiagnostic)
    assert (
        diagnostic.position_name == "position<worker>::action</provide>::position<item>"
    )


def test_guarantee_existing_set(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_result
    assert_no_errors(result)


def test_guarantee_existing_unset(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_result
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert diagnostic.location.file_path == PurePosixPath("test.dfn")
    assert diagnostic.location.line == 20
    assert diagnostic.location.column == 44
    assert isinstance(diagnostic, diagnostics.UnsetValueDiagnostic)
    assert (
        diagnostic.position_name == "position<worker>::action</provide>::position<item>"
    )


def test_guarantee_unchanged_set(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_result
    assert_no_errors(result)


def test_guarantee_unchanged_unset(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_result
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert diagnostic.location.file_path == PurePosixPath("test.dfn")
    assert diagnostic.location.line == 20
    assert diagnostic.location.column == 44
    assert isinstance(diagnostic, diagnostics.UnsetValueDiagnostic)
    assert (
        diagnostic.position_name == "position<worker>::action</provide>::position<item>"
    )


def test_guarantee_moved_set(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_result
    assert_no_errors(result)


def test_guarantee_moved_unset(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_result
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert diagnostic.location.file_path == PurePosixPath("test.dfn")
    assert diagnostic.location.line == 20
    assert diagnostic.location.column == 44
    assert isinstance(diagnostic, diagnostics.UnsetValueDiagnostic)
    assert (
        diagnostic.position_name == "position<worker>::action</provide>::position<item>"
    )


def test_destructor_direct_set(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_result
    assert_no_errors(result)


def test_destructor_direct_unset(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_result
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert diagnostic.location.file_path == PurePosixPath("test.dfn")
    assert diagnostic.location.line == 14
    assert diagnostic.location.column == 33
    assert isinstance(diagnostic, diagnostics.InferredRequirementViolationDiagnostic)
    assert diagnostic.position_name == "position<box>::position</value>"
    assert diagnostic.required_value is True
    assert diagnostic.required_empty is False
    assert diagnostic.action_name == "action<my.domain.com:my_lib:/cleanup>"
    assert_propagation_chain(
        diagnostic,
        {
            "kind": action_contract.PropagationKind.QUALITY_ASSIGNED,
            "enclosing_quality_name": "position<box>",
            "triggered_quality_name": "action<my.domain.com:my_lib:/cleanup>",
            "line": 8,
            "column": 28,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.PARTICLE_ORIGIN,
            "enclosing_quality_name": "position<box>",
            "triggered_quality_name": None,
            "line": 12,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.FILL_SITE,
            "enclosing_quality_name": "position<box>::position</value>",
            "triggered_quality_name": None,
            "line": 13,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DESTRUCTOR_CASCADE,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/test>",
            "triggered_quality_name": "action<my.domain.com:my_lib:/cleanup>",
            "line": 14,
            "column": 33,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/cleanup>",
            "triggered_quality_name": None,
            "line": 12,
            "column": 44,
            "file_path": "cleanup.dfn",
        },
    )


def test_destructor_contract_set(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_result
    assert_no_errors(result)


def test_destructor_contract_unset(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_result
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert diagnostic.location.file_path == PurePosixPath("test.dfn")
    assert diagnostic.location.line == 20
    assert diagnostic.location.column == 47
    assert isinstance(diagnostic, diagnostics.InferredRequirementViolationDiagnostic)
    assert (
        diagnostic.position_name
        == "position<worker>::action</close>::position<input>::position</value>"
    )
    assert diagnostic.required_value is True
    assert diagnostic.required_empty is False
    assert diagnostic.action_name == "action<my.domain.com:my_lib:/close>"
    assert_propagation_chain(
        diagnostic,
        {
            "kind": action_contract.PropagationKind.QUALITY_ASSIGNED,
            "enclosing_quality_name": "position<box>",
            "triggered_quality_name": "action<my.domain.com:my_lib:/cleanup>",
            "line": 8,
            "column": 28,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.PARTICLE_ORIGIN,
            "enclosing_quality_name": "position<worker>::action</close>::position<input>",
            "triggered_quality_name": None,
            "line": 12,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/test>",
            "triggered_quality_name": "action<my.domain.com:my_lib:/close>",
            "line": 20,
            "column": 47,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DESTRUCTOR_CASCADE,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/close>",
            "triggered_quality_name": "action<my.domain.com:my_lib:/cleanup>",
            "line": 13,
            "column": 33,
            "file_path": "close.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/cleanup>",
            "triggered_quality_name": None,
            "line": 12,
            "column": 44,
            "file_path": "cleanup.dfn",
        },
    )


def test_destructor_contract_set_set(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_result
    assert_no_errors(result)


def test_destructor_contract_set_unset(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_result
    assert_no_errors(result)


def test_destructor_contract_replace_set(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_result
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert diagnostic.location.file_path == PurePosixPath("test.dfn")
    assert diagnostic.location.line == 21
    assert diagnostic.location.column == 47
    assert isinstance(diagnostic, diagnostics.InferredRequirementViolationDiagnostic)
    assert (
        diagnostic.position_name
        == "position<worker>::action</close>::position<input>::position</value>"
    )
    assert diagnostic.required_value is True
    assert diagnostic.required_empty is False
    assert diagnostic.action_name == "action<my.domain.com:my_lib:/close>"
    assert_propagation_chain(
        diagnostic,
        {
            "kind": action_contract.PropagationKind.QUALITY_ASSIGNED,
            "enclosing_quality_name": "position<box>",
            "triggered_quality_name": "action<my.domain.com:my_lib:/cleanup>",
            "line": 8,
            "column": 28,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.PARTICLE_ORIGIN,
            "enclosing_quality_name": "position<worker>::action</close>::position<input>",
            "triggered_quality_name": None,
            "line": 12,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/test>",
            "triggered_quality_name": "action<my.domain.com:my_lib:/close>",
            "line": 21,
            "column": 47,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DESTRUCTOR_CASCADE,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/close>",
            "triggered_quality_name": "action<my.domain.com:my_lib:/cleanup>",
            "line": 13,
            "column": 33,
            "file_path": "close.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/cleanup>",
            "triggered_quality_name": None,
            "line": 12,
            "column": 44,
            "file_path": "cleanup.dfn",
        },
    )


def test_destructor_contract_replace_unset(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_result
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert diagnostic.location.file_path == PurePosixPath("test.dfn")
    assert diagnostic.location.line == 20
    assert diagnostic.location.column == 47
    assert isinstance(diagnostic, diagnostics.InferredRequirementViolationDiagnostic)
    assert (
        diagnostic.position_name
        == "position<worker>::action</close>::position<input>::position</value>"
    )
    assert diagnostic.required_value is True
    assert diagnostic.required_empty is False
    assert diagnostic.action_name == "action<my.domain.com:my_lib:/close>"
    assert_propagation_chain(
        diagnostic,
        {
            "kind": action_contract.PropagationKind.QUALITY_ASSIGNED,
            "enclosing_quality_name": "position<box>",
            "triggered_quality_name": "action<my.domain.com:my_lib:/cleanup>",
            "line": 8,
            "column": 28,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.PARTICLE_ORIGIN,
            "enclosing_quality_name": "position<worker>::action</close>::position<input>",
            "triggered_quality_name": None,
            "line": 12,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/test>",
            "triggered_quality_name": "action<my.domain.com:my_lib:/close>",
            "line": 20,
            "column": 47,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DESTRUCTOR_CASCADE,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/close>",
            "triggered_quality_name": "action<my.domain.com:my_lib:/cleanup>",
            "line": 13,
            "column": 33,
            "file_path": "close.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/cleanup>",
            "triggered_quality_name": None,
            "line": 12,
            "column": 44,
            "file_path": "cleanup.dfn",
        },
    )


def test_destructor_contract_untouched_set(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_result
    assert_no_errors(result)


def test_destructor_contract_untouched_unset(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_result
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert diagnostic.location.file_path == PurePosixPath("test.dfn")
    assert diagnostic.location.line == 20
    assert diagnostic.location.column == 47
    assert isinstance(diagnostic, diagnostics.InferredRequirementViolationDiagnostic)
    assert (
        diagnostic.position_name
        == "position<worker>::action</close>::position<input>::position</value>"
    )
    assert diagnostic.required_value is True
    assert diagnostic.required_empty is False
    assert diagnostic.action_name == "action<my.domain.com:my_lib:/close>"
    assert_propagation_chain(
        diagnostic,
        {
            "kind": action_contract.PropagationKind.QUALITY_ASSIGNED,
            "enclosing_quality_name": "position<box>",
            "triggered_quality_name": "action<my.domain.com:my_lib:/cleanup>",
            "line": 8,
            "column": 28,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.PARTICLE_ORIGIN,
            "enclosing_quality_name": "position<worker>::action</close>::position<input>",
            "triggered_quality_name": None,
            "line": 12,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/test>",
            "triggered_quality_name": "action<my.domain.com:my_lib:/close>",
            "line": 20,
            "column": 47,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DESTRUCTOR_CASCADE,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/close>",
            "triggered_quality_name": "action<my.domain.com:my_lib:/cleanup>",
            "line": 6,
            "column": 33,
            "file_path": "close.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/cleanup>",
            "triggered_quality_name": None,
            "line": 12,
            "column": 44,
            "file_path": "cleanup.dfn",
        },
    )


def test_transitive_implied_guarantee_set(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_result
    assert_no_errors(result)


def test_transitive_implied_guarantee_unset(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_result
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert diagnostic.location.file_path == PurePosixPath("test.dfn")
    assert diagnostic.location.line == 20
    assert diagnostic.location.column == 44
    assert isinstance(diagnostic, diagnostics.UnsetValueDiagnostic)
    assert diagnostic.position_name == "position<worker>::position</value>"


def test_constructor_guarantee_set(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_result
    assert_no_errors(result)


def test_constructor_guarantee_unset(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_result
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert diagnostic.location.file_path == PurePosixPath("test.dfn")
    assert diagnostic.location.line == 19
    assert diagnostic.location.column == 44
    assert isinstance(diagnostic, diagnostics.UnsetValueDiagnostic)
    assert diagnostic.position_name == "position<worker>::position</value>"


def test_requirement_after_move_set(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_result
    assert_no_errors(result)


def test_requirement_after_move_unset(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_result
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert diagnostic.location.file_path == PurePosixPath("test.dfn")
    assert diagnostic.location.line == 18
    assert diagnostic.location.column == 50
    assert isinstance(diagnostic, diagnostics.InferredRequirementViolationDiagnostic)
    assert (
        diagnostic.position_name
        == "position<worker>::action</consume>::position<input>"
    )
    assert diagnostic.required_value is True
    assert diagnostic.required_empty is False
    assert diagnostic.action_name == "action<my.domain.com:my_lib:/consume>"
    assert_propagation_chain(
        diagnostic,
        {
            "kind": action_contract.PropagationKind.FILL_SITE,
            "enclosing_quality_name": "position<worker>::action</consume>::position<input>",
            "triggered_quality_name": None,
            "line": 18,
            "column": 50,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/test>",
            "triggered_quality_name": "action<my.domain.com:my_lib:/consume>",
            "line": 18,
            "column": 50,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/consume>",
            "triggered_quality_name": None,
            "line": 18,
            "column": 44,
            "file_path": "consume.dfn",
        },
    )


def test_destructor_transitive_requirement_set(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_result
    assert_no_errors(result)


def test_destructor_transitive_requirement_unset(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_result
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert diagnostic.location.file_path == PurePosixPath("test.dfn")
    assert diagnostic.location.line == 20
    assert diagnostic.location.column == 47
    assert isinstance(diagnostic, diagnostics.InferredRequirementViolationDiagnostic)
    assert (
        diagnostic.position_name
        == "position<worker>::action</relay>::position<input>::position</value>"
    )
    assert diagnostic.required_value is True
    assert diagnostic.required_empty is False
    assert diagnostic.action_name == "action<my.domain.com:my_lib:/relay>"
    assert_propagation_chain(
        diagnostic,
        {
            "kind": action_contract.PropagationKind.QUALITY_ASSIGNED,
            "enclosing_quality_name": "position<box>",
            "triggered_quality_name": "action<my.domain.com:my_lib:/cleanup>",
            "line": 8,
            "column": 28,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.PARTICLE_ORIGIN,
            "enclosing_quality_name": "position<worker>::action</relay>::position<input>",
            "triggered_quality_name": None,
            "line": 12,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/test>",
            "triggered_quality_name": "action<my.domain.com:my_lib:/relay>",
            "line": 20,
            "column": 47,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/relay>",
            "triggered_quality_name": "action<my.domain.com:my_lib:/close>",
            "line": 17,
            "column": 49,
            "file_path": "relay.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DESTRUCTOR_CASCADE,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/close>",
            "triggered_quality_name": "action<my.domain.com:my_lib:/cleanup>",
            "line": 13,
            "column": 33,
            "file_path": "close.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/cleanup>",
            "triggered_quality_name": None,
            "line": 12,
            "column": 44,
            "file_path": "cleanup.dfn",
        },
    )


def test_destructor_untouched_requirement_set(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_result
    assert_no_errors(result)


def test_destructor_untouched_requirement_unset(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_result
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert diagnostic.location.file_path == PurePosixPath("test.dfn")
    assert diagnostic.location.line == 20
    assert diagnostic.location.column == 47
    assert isinstance(diagnostic, diagnostics.InferredRequirementViolationDiagnostic)
    assert (
        diagnostic.position_name
        == "position<worker>::action</relay>::position<input>::position</value>"
    )
    assert diagnostic.required_value is True
    assert diagnostic.required_empty is False
    assert diagnostic.action_name == "action<my.domain.com:my_lib:/relay>"
    assert_propagation_chain(
        diagnostic,
        {
            "kind": action_contract.PropagationKind.QUALITY_ASSIGNED,
            "enclosing_quality_name": "position<box>",
            "triggered_quality_name": "action<my.domain.com:my_lib:/cleanup>",
            "line": 8,
            "column": 28,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.PARTICLE_ORIGIN,
            "enclosing_quality_name": "position<worker>::action</relay>::position<input>",
            "triggered_quality_name": None,
            "line": 12,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/test>",
            "triggered_quality_name": "action<my.domain.com:my_lib:/relay>",
            "line": 20,
            "column": 47,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/relay>",
            "triggered_quality_name": "action<my.domain.com:my_lib:/close>",
            "line": 16,
            "column": 49,
            "file_path": "relay.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DESTRUCTOR_CASCADE,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/close>",
            "triggered_quality_name": "action<my.domain.com:my_lib:/cleanup>",
            "line": 6,
            "column": 33,
            "file_path": "close.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/cleanup>",
            "triggered_quality_name": None,
            "line": 12,
            "column": 44,
            "file_path": "cleanup.dfn",
        },
    )


def test_destructor_replaced_child_identity_set(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_result
    assert_no_errors(result)


def test_destructor_replaced_child_identity_unset(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_result
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert diagnostic.location.file_path == PurePosixPath("test.dfn")
    assert diagnostic.location.line == 28
    assert diagnostic.location.column == 47
    assert isinstance(diagnostic, diagnostics.InferredRequirementViolationDiagnostic)
    assert (
        diagnostic.position_name
        == "position<worker>::action</close>::position<input>::position</value>"
    )
    assert diagnostic.required_value is True
    assert diagnostic.required_empty is False
    assert diagnostic.action_name == "action<my.domain.com:my_lib:/close>"
    assert_propagation_chain(
        diagnostic,
        {
            "kind": action_contract.PropagationKind.QUALITY_ASSIGNED,
            "enclosing_quality_name": "position<box>",
            "triggered_quality_name": "action<my.domain.com:my_lib:/cleanup>",
            "line": 8,
            "column": 28,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.PARTICLE_ORIGIN,
            "enclosing_quality_name": "position<worker>::action</close>::position<input>",
            "triggered_quality_name": None,
            "line": 12,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/test>",
            "triggered_quality_name": "action<my.domain.com:my_lib:/close>",
            "line": 28,
            "column": 47,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DESTRUCTOR_CASCADE,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/close>",
            "triggered_quality_name": "action<my.domain.com:my_lib:/cleanup>",
            "line": 24,
            "column": 33,
            "file_path": "close.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/cleanup>",
            "triggered_quality_name": None,
            "line": 12,
            "column": 44,
            "file_path": "cleanup.dfn",
        },
    )


def test_destructor_cannot_set_contracted_value(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_result
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert diagnostic.location.file_path == PurePosixPath("cleanup.dfn")
    assert diagnostic.location.line == 6
    assert diagnostic.location.column == 26
    assert isinstance(diagnostic, diagnostics.DestructorChangesValueDiagnostic)
    assert diagnostic.position_name == "position</value>"


def test_multiple_value_requirements(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_result
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 2
    first, second = result.all_diagnostics
    assert first.location.file_path == PurePosixPath("test.dfn")
    assert first.location.line == 19
    assert first.location.column == 50
    assert second.location.file_path == PurePosixPath("test.dfn")
    assert second.location.line == 19
    assert second.location.column == 50
    assert isinstance(first, diagnostics.InferredRequirementViolationDiagnostic)
    assert isinstance(second, diagnostics.InferredRequirementViolationDiagnostic)
    assert first.required_value is True
    assert second.required_value is True
    assert first.position_name == "position<worker>::action</consume>::position<input>"
    assert second.position_name == "position<worker>::action</consume>::position<other>"
    assert first.required_empty is False
    assert first.action_name == "action<my.domain.com:my_lib:/consume>"
    assert_propagation_chain(
        first,
        {
            "kind": action_contract.PropagationKind.FILL_SITE,
            "enclosing_quality_name": "position<worker>::action</consume>::position<input>",
            "triggered_quality_name": None,
            "line": 19,
            "column": 50,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/test>",
            "triggered_quality_name": "action<my.domain.com:my_lib:/consume>",
            "line": 19,
            "column": 50,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/consume>",
            "triggered_quality_name": None,
            "line": 21,
            "column": 44,
            "file_path": "consume.dfn",
        },
    )
    assert second.required_empty is False
    assert second.action_name == "action<my.domain.com:my_lib:/consume>"
    assert_propagation_chain(
        second,
        {
            "kind": action_contract.PropagationKind.FILL_SITE,
            "enclosing_quality_name": "position<worker>::action</consume>::position<other>",
            "triggered_quality_name": None,
            "line": 18,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/test>",
            "triggered_quality_name": "action<my.domain.com:my_lib:/consume>",
            "line": 19,
            "column": 50,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/consume>",
            "triggered_quality_name": None,
            "line": 22,
            "column": 44,
            "file_path": "consume.dfn",
        },
    )


def test_destructor_value_and_empty_requirements(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_result
    assert_no_errors(result)


def test_interfaces_stop_value_inference(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph(
        allow_entry_action_interface_positions=True
    ).program_result
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert diagnostic.location.file_path == PurePosixPath("test.dfn")
    assert diagnostic.location.line == 11
    assert diagnostic.location.column == 30
    assert isinstance(diagnostic, diagnostics.InferredRequirementViolationDiagnostic)
    assert diagnostic.required_value is True
    assert (
        diagnostic.position_name == "position<input>::action</consume>::position<input>"
    )
    assert diagnostic.required_empty is False
    assert diagnostic.action_name == "action<my.domain.com:my_lib:/consume>"
    assert_propagation_chain(
        diagnostic,
        {
            "kind": action_contract.PropagationKind.FILL_SITE,
            "enclosing_quality_name": "position<input>::action</consume>::position<input>",
            "triggered_quality_name": None,
            "line": 17,
            "column": 44,
            "file_path": "consume.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/test>",
            "triggered_quality_name": "action<my.domain.com:my_lib:/consume>",
            "line": 11,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/consume>",
            "triggered_quality_name": None,
            "line": 17,
            "column": 44,
            "file_path": "consume.dfn",
        },
    )


def test_destructor_transitive_replaced_identity_set(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_result
    assert_no_errors(result)


def test_destructor_transitive_replaced_identity_unset(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_result
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert diagnostic.location.file_path == PurePosixPath("test.dfn")
    assert diagnostic.location.line == 28
    assert diagnostic.location.column == 47
    assert isinstance(diagnostic, diagnostics.InferredRequirementViolationDiagnostic)
    assert diagnostic.required_value is True
    assert (
        diagnostic.position_name
        == "position<worker>::action</relay>::position<input>::position</value>"
    )
    assert diagnostic.required_empty is False
    assert diagnostic.action_name == "action<my.domain.com:my_lib:/relay>"
    assert_propagation_chain(
        diagnostic,
        {
            "kind": action_contract.PropagationKind.QUALITY_ASSIGNED,
            "enclosing_quality_name": "position<box>",
            "triggered_quality_name": "action<my.domain.com:my_lib:/cleanup>",
            "line": 8,
            "column": 28,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.PARTICLE_ORIGIN,
            "enclosing_quality_name": "position<worker>::action</relay>::position<input>",
            "triggered_quality_name": None,
            "line": 12,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/test>",
            "triggered_quality_name": "action<my.domain.com:my_lib:/relay>",
            "line": 28,
            "column": 47,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/relay>",
            "triggered_quality_name": "action<my.domain.com:my_lib:/close>",
            "line": 23,
            "column": 49,
            "file_path": "relay.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DESTRUCTOR_CASCADE,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/close>",
            "triggered_quality_name": "action<my.domain.com:my_lib:/cleanup>",
            "line": 24,
            "column": 33,
            "file_path": "close.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/cleanup>",
            "triggered_quality_name": None,
            "line": 12,
            "column": 44,
            "file_path": "cleanup.dfn",
        },
    )


def test_multiple_destructor_requirements_set(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_result
    assert_no_errors(result)


def test_multiple_destructor_requirements_unset(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_result
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 2
    first, second = result.all_diagnostics
    assert first.location.file_path == PurePosixPath("test.dfn")
    assert first.location.line == 23
    assert first.location.column == 47
    assert second.location.file_path == PurePosixPath("test.dfn")
    assert second.location.line == 23
    assert second.location.column == 47
    assert isinstance(first, diagnostics.InferredRequirementViolationDiagnostic)
    assert isinstance(second, diagnostics.InferredRequirementViolationDiagnostic)
    assert first.required_value is True
    assert second.required_value is True
    assert (
        first.position_name
        == "position<worker>::action</relay>::position<input>::position</value>"
    )
    assert (
        second.position_name
        == "position<worker>::action</relay>::position<input>::position</other_value>"
    )
    assert first.required_empty is False
    assert first.action_name == "action<my.domain.com:my_lib:/relay>"
    assert_propagation_chain(
        first,
        {
            "kind": action_contract.PropagationKind.QUALITY_ASSIGNED,
            "enclosing_quality_name": "position<box>",
            "triggered_quality_name": "action<my.domain.com:my_lib:/cleanup>",
            "line": 9,
            "column": 28,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.PARTICLE_ORIGIN,
            "enclosing_quality_name": "position<worker>::action</relay>::position<input>",
            "triggered_quality_name": None,
            "line": 14,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/test>",
            "triggered_quality_name": "action<my.domain.com:my_lib:/relay>",
            "line": 23,
            "column": 47,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/relay>",
            "triggered_quality_name": "action<my.domain.com:my_lib:/close>",
            "line": 18,
            "column": 49,
            "file_path": "relay.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DESTRUCTOR_CASCADE,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/close>",
            "triggered_quality_name": "action<my.domain.com:my_lib:/cleanup>",
            "line": 13,
            "column": 33,
            "file_path": "close.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/cleanup>",
            "triggered_quality_name": None,
            "line": 12,
            "column": 44,
            "file_path": "cleanup.dfn",
        },
    )
    assert second.required_empty is False
    assert second.action_name == "action<my.domain.com:my_lib:/relay>"
    assert_propagation_chain(
        second,
        {
            "kind": action_contract.PropagationKind.QUALITY_ASSIGNED,
            "enclosing_quality_name": "position<box>",
            "triggered_quality_name": "action<my.domain.com:my_lib:/other_cleanup>",
            "line": 8,
            "column": 28,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.PARTICLE_ORIGIN,
            "enclosing_quality_name": "position<worker>::action</relay>::position<input>",
            "triggered_quality_name": None,
            "line": 14,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/test>",
            "triggered_quality_name": "action<my.domain.com:my_lib:/relay>",
            "line": 23,
            "column": 47,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/relay>",
            "triggered_quality_name": "action<my.domain.com:my_lib:/close>",
            "line": 18,
            "column": 49,
            "file_path": "relay.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DESTRUCTOR_CASCADE,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/close>",
            "triggered_quality_name": "action<my.domain.com:my_lib:/other_cleanup>",
            "line": 13,
            "column": 33,
            "file_path": "close.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/other_cleanup>",
            "triggered_quality_name": None,
            "line": 12,
            "column": 44,
            "file_path": "other_cleanup.dfn",
        },
    )


def test_destructor_multiple_value_requirements(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_result
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 2
    first, second = result.all_diagnostics
    assert first.location.file_path == PurePosixPath("test.dfn")
    assert first.location.line == 22
    assert first.location.column == 47
    assert second.location.file_path == PurePosixPath("test.dfn")
    assert second.location.line == 22
    assert second.location.column == 47
    assert isinstance(first, diagnostics.InferredRequirementViolationDiagnostic)
    assert isinstance(second, diagnostics.InferredRequirementViolationDiagnostic)
    assert first.required_value is True
    assert second.required_value is True
    assert (
        first.position_name
        == "position<worker>::action</relay>::position<input>::position</value>"
    )
    assert (
        second.position_name
        == "position<worker>::action</relay>::position<input>::position</other_value>"
    )
    assert first.required_empty is False
    assert first.action_name == "action<my.domain.com:my_lib:/relay>"
    assert_propagation_chain(
        first,
        {
            "kind": action_contract.PropagationKind.QUALITY_ASSIGNED,
            "enclosing_quality_name": "position<box>",
            "triggered_quality_name": "action<my.domain.com:my_lib:/cleanup>",
            "line": 8,
            "column": 28,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.PARTICLE_ORIGIN,
            "enclosing_quality_name": "position<worker>::action</relay>::position<input>",
            "triggered_quality_name": None,
            "line": 13,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/test>",
            "triggered_quality_name": "action<my.domain.com:my_lib:/relay>",
            "line": 22,
            "column": 47,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/relay>",
            "triggered_quality_name": "action<my.domain.com:my_lib:/close>",
            "line": 17,
            "column": 49,
            "file_path": "relay.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DESTRUCTOR_CASCADE,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/close>",
            "triggered_quality_name": "action<my.domain.com:my_lib:/cleanup>",
            "line": 13,
            "column": 33,
            "file_path": "close.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/cleanup>",
            "triggered_quality_name": None,
            "line": 13,
            "column": 44,
            "file_path": "cleanup.dfn",
        },
    )
    assert second.required_empty is False
    assert second.action_name == "action<my.domain.com:my_lib:/relay>"
    assert_propagation_chain(
        second,
        {
            "kind": action_contract.PropagationKind.QUALITY_ASSIGNED,
            "enclosing_quality_name": "position<box>",
            "triggered_quality_name": "action<my.domain.com:my_lib:/cleanup>",
            "line": 8,
            "column": 28,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.PARTICLE_ORIGIN,
            "enclosing_quality_name": "position<worker>::action</relay>::position<input>",
            "triggered_quality_name": None,
            "line": 13,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/test>",
            "triggered_quality_name": "action<my.domain.com:my_lib:/relay>",
            "line": 22,
            "column": 47,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/relay>",
            "triggered_quality_name": "action<my.domain.com:my_lib:/close>",
            "line": 17,
            "column": 49,
            "file_path": "relay.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DESTRUCTOR_CASCADE,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/close>",
            "triggered_quality_name": "action<my.domain.com:my_lib:/cleanup>",
            "line": 13,
            "column": 33,
            "file_path": "close.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/cleanup>",
            "triggered_quality_name": None,
            "line": 14,
            "column": 44,
            "file_path": "cleanup.dfn",
        },
    )


def test_destructor_value_requirement_deferred_set(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_result
    assert_no_errors(result)


def test_destructor_value_requirement_deferred_unset(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_result
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert diagnostic.location.file_path == PurePosixPath("test.dfn")
    assert diagnostic.location.line == 20
    assert diagnostic.location.column == 47
    assert isinstance(diagnostic, diagnostics.InferredRequirementViolationDiagnostic)
    assert diagnostic.required_value is True
    assert (
        diagnostic.position_name
        == "position<worker>::action</relay>::position<input>::position</value>"
    )
    assert diagnostic.required_empty is False
    assert diagnostic.action_name == "action<my.domain.com:my_lib:/relay>"
    assert_propagation_chain(
        diagnostic,
        {
            "kind": action_contract.PropagationKind.QUALITY_ASSIGNED,
            "enclosing_quality_name": "position<box>",
            "triggered_quality_name": "action<my.domain.com:my_lib:/cleanup>",
            "line": 8,
            "column": 28,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.PARTICLE_ORIGIN,
            "enclosing_quality_name": "position<worker>::action</relay>::position<input>",
            "triggered_quality_name": None,
            "line": 12,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/test>",
            "triggered_quality_name": "action<my.domain.com:my_lib:/relay>",
            "line": 20,
            "column": 47,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/relay>",
            "triggered_quality_name": "action<my.domain.com:my_lib:/close>",
            "line": 16,
            "column": 49,
            "file_path": "relay.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DESTRUCTOR_CASCADE,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/close>",
            "triggered_quality_name": "action<my.domain.com:my_lib:/cleanup>",
            "line": 6,
            "column": 33,
            "file_path": "close.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/cleanup>",
            "triggered_quality_name": None,
            "line": 15,
            "column": 44,
            "file_path": "cleanup.dfn",
        },
    )


def test_repeated_unset_reads(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_result
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.UnsetValueDiagnostic)
    assert diagnostic.location.file_path == PurePosixPath("test.dfn")
    assert diagnostic.location.line == 18
    assert diagnostic.location.column == 46
    assert diagnostic.position_name == "position<source>"


def test_value_error_preserves_occupancy(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_result
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 2
    first, second = result.all_diagnostics
    assert isinstance(first, diagnostics.UnsetValueDiagnostic)
    assert first.location.file_path == PurePosixPath("test.dfn")
    assert first.location.line == 18
    assert first.location.column == 46
    assert first.position_name == "position<source>"
    assert isinstance(second, diagnostics.ValueSettingEmptyPositionDiagnostic)
    assert second.location.file_path == PurePosixPath("test.dfn")
    assert second.location.line == 20
    assert second.location.column == 46
    assert second.position_name == "position<source>"


def test_repeated_interface_value_requirement(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph(
        allow_entry_action_interface_positions=True
    ).program_result
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.InferredRequirementViolationDiagnostic)
    assert diagnostic.location.file_path == PurePosixPath("test.dfn")
    assert diagnostic.location.line == 11
    assert diagnostic.location.column == 30
    assert (
        diagnostic.position_name == "position<input>::action</consume>::position<input>"
    )
    assert diagnostic.required_value is True
    assert diagnostic.required_empty is False
    assert diagnostic.action_name == "action<my.domain.com:my_lib:/consume>"
    assert_propagation_chain(
        diagnostic,
        {
            "kind": action_contract.PropagationKind.FILL_SITE,
            "enclosing_quality_name": "position<input>::action</consume>::position<input>",
            "triggered_quality_name": None,
            "line": 17,
            "column": 44,
            "file_path": "consume.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/test>",
            "triggered_quality_name": "action<my.domain.com:my_lib:/consume>",
            "line": 11,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/consume>",
            "triggered_quality_name": None,
            "line": 17,
            "column": 44,
            "file_path": "consume.dfn",
        },
    )


def test_value_error_new_guarantee(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_result
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.UnsetValueDiagnostic)
    assert diagnostic.location.file_path == PurePosixPath("provide.dfn")
    assert diagnostic.location.line == 18
    assert diagnostic.location.column == 44
    assert diagnostic.position_name == "position<source>"


def test_value_error_existing_guarantee(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_result
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.UnsetValueDiagnostic)
    assert diagnostic.location.file_path == PurePosixPath("provide.dfn")
    assert diagnostic.location.line == 17
    assert diagnostic.location.column == 44
    assert diagnostic.position_name == "position<source>"


def test_value_error_recovered_by_literal(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_result
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 2
    diagnostic = result.all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.DestructorChangesValueDiagnostic)
    assert diagnostic.location.file_path == PurePosixPath("cleanup.dfn")
    assert diagnostic.location.line == 12
    assert diagnostic.location.column == 26
    assert diagnostic.position_name == "position</value>"
    diagnostic = result.all_diagnostics[1]
    assert isinstance(diagnostic, diagnostics.UnsetValueDiagnostic)
    assert diagnostic.location.file_path == PurePosixPath("cleanup.dfn")
    assert diagnostic.location.line == 12
    assert diagnostic.location.column == 46
    assert diagnostic.position_name == "position<source>"


def test_destructor_value_error(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_result
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.UnsetValueDiagnostic)
    assert diagnostic.location.file_path == PurePosixPath("cleanup.dfn")
    assert diagnostic.location.line == 12
    assert diagnostic.location.column == 46
    assert diagnostic.position_name == "position<source>"


def test_value_error_recovered_by_copy(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_result
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 2
    diagnostic = result.all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.DestructorChangesValueDiagnostic)
    assert diagnostic.location.file_path == PurePosixPath("cleanup.dfn")
    assert diagnostic.location.line == 12
    assert diagnostic.location.column == 26
    assert diagnostic.position_name == "position</value>"
    diagnostic = result.all_diagnostics[1]
    assert isinstance(diagnostic, diagnostics.UnsetValueDiagnostic)
    assert diagnostic.location.file_path == PurePosixPath("cleanup.dfn")
    assert diagnostic.location.line == 12
    assert diagnostic.location.column == 46
    assert diagnostic.position_name == "position<source>"
