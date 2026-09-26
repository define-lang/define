"""Reference graph validation of literal sources in Value Setting Statements."""

from __future__ import annotations

from pathlib import PurePosixPath
from typing import TYPE_CHECKING

from define.compiler import constants, diagnostics, literal_parsers
from define.compiler.validator.reference_graph import action_contract
from define.compiler.validator.reference_graph.reference_graph_validator_tests.test_helpers import (
    assert_propagation_chain,
)
from define.compiler.validator.test_helpers import assert_no_errors

if TYPE_CHECKING:
    import pytest

    from define.compiler.conftest import ValidateTestdataProjectWithReferenceGraph


def test_matching_types(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_result
    assert_no_errors(result)


def test_built_in_literal(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_result
    assert_no_errors(result)
    assert len(result.file_results) == 2


def test_defined_literal_with_built_in_encoding(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_result
    assert_no_errors(result)
    assert len(result.file_results) == 3


def test_empty_literal_content(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_result
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.InvalidLiteralContentDiagnostic)
    assert diagnostic.location.file_path == PurePosixPath("test.dfn")
    assert diagnostic.content == ""
    assert diagnostic.potential_literal == "literal<standard:/number>"
    assert diagnostic.value_encoding == "encoding<standard:/number/decimal/ascii>"
    assert diagnostic.reason == "there must be at least one digit"
    assert diagnostic.location.line == 12
    assert diagnostic.location.column == 72


def test_invalid_literal_content(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_result
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.InvalidLiteralContentDiagnostic)
    assert diagnostic.location.file_path == PurePosixPath("test.dfn")
    assert diagnostic.content == "+5"
    assert diagnostic.potential_literal == "literal<standard:/number>"
    assert diagnostic.value_encoding == "encoding<standard:/number/decimal/ascii>"
    assert diagnostic.reason == "positive numbers are written without a +"
    assert diagnostic.location.line == 12
    assert diagnostic.location.column == 72


def test_invalid_literal_content_with_undefined_target(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_result
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.UndefinedLocalNameDiagnostic)
    assert diagnostic.location.file_path == PurePosixPath("test.dfn")
    assert diagnostic.local_name == "position<missing>"
    assert diagnostic.location.line == 6
    assert diagnostic.location.column == 26


def test_no_literal_parser(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_result
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.LiteralCannotSetValueDiagnostic)
    assert diagnostic.location.file_path == PurePosixPath("test.dfn")
    assert diagnostic.potential_literal == "literal</text>"
    assert diagnostic.literal_encoding == "encoding</text_encoding>"
    assert diagnostic.value_type == "value</number>"
    assert diagnostic.supported_encodings == [
        "encoding<standard:/number/decimal/ascii>"
    ]
    assert diagnostic.example_literals == ["literal<standard:/number>"]
    assert diagnostic.location.line == 12
    assert diagnostic.location.column == 46


def test_only_matching_encodings_suggested(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
    monkeypatch: pytest.MonkeyPatch,
):
    text_encoding = "encoding<standard:/text/utf8>"
    monkeypatch.setitem(
        literal_parsers.LITERAL_PARSERS, (text_encoding, text_encoding), str
    )
    monkeypatch.setitem(
        constants.BUILT_IN_LITERAL_ENCODINGS, "literal<standard:/text>", text_encoding
    )
    result = validate_testdata_project_with_reference_graph().program_result
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.LiteralCannotSetValueDiagnostic)
    assert diagnostic.location.file_path == PurePosixPath("test.dfn")
    assert diagnostic.potential_literal == "literal</text>"
    assert diagnostic.literal_encoding == "encoding</text_encoding>"
    assert diagnostic.value_type == "value</number>"
    assert diagnostic.supported_encodings == [
        "encoding<standard:/number/decimal/ascii>"
    ]
    assert diagnostic.example_literals == ["literal<standard:/number>"]
    assert diagnostic.location.line == 12
    assert diagnostic.location.column == 46


def test_missing_potential_literal(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_result
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.ReferencedFileNotFoundDiagnostic)
    assert diagnostic.location.file_path == PurePosixPath("test.dfn")
    assert diagnostic.file_path == "missing.dfn"
    assert diagnostic.location.line == 12
    assert diagnostic.location.column == 54


def test_target_missing_type(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_result
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.ValueSettingMissingValueTypeDiagnostic)
    assert diagnostic.location.file_path == PurePosixPath("test.dfn")
    assert diagnostic.location.line == 10
    assert diagnostic.location.column == 26
    assert diagnostic.position_name == "position<target>"
    assert diagnostic.origin_position_name == "position<original>"


def test_target_empty(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_result
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.ValueSettingEmptyPositionDiagnostic)
    assert diagnostic.position_name == "position<target>"
    assert diagnostic.location.file_path == PurePosixPath("test.dfn")
    assert diagnostic.location.line == 14
    assert diagnostic.location.column == 26


def test_undefined_position(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_result
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.UndefinedLocalNameDiagnostic)
    assert diagnostic.local_name == "position<missing>"
    assert diagnostic.location.file_path == PurePosixPath("test.dfn")
    assert diagnostic.location.line == 20
    assert diagnostic.location.column == 26


def test_prior_error(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_result
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.MoveFromEmptyPositionDiagnostic)
    assert diagnostic.position_name == "position<empty>"
    assert diagnostic.is_action_interface_position is False
    assert diagnostic.inferred_at is None
    assert diagnostic.location.file_path == PurePosixPath("test.dfn")
    assert diagnostic.location.line == 15
    assert diagnostic.location.column == 30


def test_child_positions(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_result
    assert_no_errors(result)


def test_empty_parent(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_result
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.ParentPositionNotOccupiedDiagnostic)
    assert diagnostic.position_name == "position<parent>::position</child>"
    assert diagnostic.parent_position_name == "position<parent>"
    assert diagnostic.location.file_path == PurePosixPath("test.dfn")
    assert diagnostic.location.line == 11
    assert diagnostic.location.column == 26


def test_invalid_child(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_result
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.ChainElementNotInConstraintsDiagnostic)
    assert diagnostic.element_name == "position<my.domain.com:my_lib:/child>"
    assert diagnostic.parent_name == "position<parent>"
    assert diagnostic.location.file_path == PurePosixPath("test.dfn")
    assert diagnostic.location.line == 8
    assert diagnostic.location.column == 44


def test_callee_requirements_satisfied(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_result
    assert_no_errors(result)


def test_callee_requires_target(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_result
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.InferredRequirementViolationDiagnostic)
    assert diagnostic.required_value is False
    assert_propagation_chain(
        diagnostic,
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/test>",
            "triggered_quality_name": "action<my.domain.com:my_lib:/assign>",
            "line": 12,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/assign>",
            "triggered_quality_name": None,
            "line": 11,
            "column": 26,
            "file_path": "assign.dfn",
        },
    )
    assert diagnostic.action_name == "action<my.domain.com:my_lib:/assign>"
    assert diagnostic.location.file_path == PurePosixPath("test.dfn")
    assert diagnostic.location.line == 12
    assert diagnostic.location.column == 30
    assert (
        diagnostic.position_name
        == "position<worker>::action</assign>::position<target>"
    )
    assert diagnostic.required_empty is False


def test_callee_target_missing_value_type(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_result
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.ValueSettingMissingValueTypeDiagnostic)
    assert diagnostic.location.file_path == PurePosixPath("assign.dfn")
    assert diagnostic.location.line == 7
    assert diagnostic.location.column == 26
    assert diagnostic.position_name == "position<target>"
    assert diagnostic.origin_position_name == "position<target>"
