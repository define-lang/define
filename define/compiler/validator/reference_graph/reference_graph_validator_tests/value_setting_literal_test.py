"""Reference graph validation of literal sources in Value Setting Statements."""

from __future__ import annotations

from typing import TYPE_CHECKING

from crates.source_rendering.python import rendering
from define.compiler import literal_parsers
from define.compiler.errors import diagnostics
from define.compiler.validator.reference_graph import propagation_step
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


def test_defined_literal_with_built_in_encoding(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_result
    assert_no_errors(result)


def test_empty_literal_content(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_result
    assert result.all_diagnostics == [
        diagnostics.InvalidLiteralContentDiagnostic(
            location=rendering.SourceLocation(
                line=8, column=75, end_line=8, end_column=75, file_path="test.dfn"
            ),
            content="",
            potential_literal="literal<standard:/number>",
            value_encoding="encoding<standard:/number/natural/ascii>",
            reason="there must be at least one digit",
        )
    ]


def test_invalid_literal_content(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_result
    assert result.all_diagnostics == [
        diagnostics.InvalidLiteralContentDiagnostic(
            location=rendering.SourceLocation(
                line=8, column=75, end_line=8, end_column=75, file_path="test.dfn"
            ),
            content="+5",
            potential_literal="literal<standard:/number>",
            value_encoding="encoding<standard:/number/natural/ascii>",
            reason="positive numbers are written without a +",
        )
    ]


def test_invalid_literal_content_with_undefined_target(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_result
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.UndefinedLocalNameDiagnostic)
    assert diagnostic.location.file_path == "test.dfn"
    assert diagnostic.local_name == "position<missing>"
    assert diagnostic.location.line == 6
    assert diagnostic.location.column == 26


def test_no_literal_parser(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_result
    assert result.all_diagnostics == [
        diagnostics.LiteralCannotSetValueDiagnostic(
            location=rendering.SourceLocation(
                line=8, column=49, end_line=8, end_column=62, file_path="test.dfn"
            ),
            potential_literal="literal</text>",
            literal_encoding="encoding</text_encoding>",
            value_quality="value<standard:/number/natural>",
            supported_encodings=[
                "encoding<standard:/binary/ascii>",
                "encoding<standard:/number/decimal/ascii>",
                "encoding<standard:/number/hex/ascii>",
            ],
        )
    ]


def test_only_matching_encodings_suggested(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
    monkeypatch: pytest.MonkeyPatch,
):
    text_encoding = "encoding<standard:/text/utf8>"
    monkeypatch.setitem(
        literal_parsers.LITERAL_PARSERS, (text_encoding, text_encoding), str
    )
    result = validate_testdata_project_with_reference_graph().program_result
    assert result.all_diagnostics == [
        diagnostics.LiteralCannotSetValueDiagnostic(
            location=rendering.SourceLocation(
                line=8, column=49, end_line=8, end_column=62, file_path="test.dfn"
            ),
            potential_literal="literal</text>",
            literal_encoding="encoding</text_encoding>",
            value_quality="value<standard:/number/natural>",
            supported_encodings=[
                "encoding<standard:/binary/ascii>",
                "encoding<standard:/number/decimal/ascii>",
                "encoding<standard:/number/hex/ascii>",
            ],
        )
    ]


def test_value_has_no_encoding(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_result
    assert result.all_diagnostics == [
        diagnostics.ValueHasNoEncodingDiagnostic(
            location=rendering.SourceLocation(
                line=1, column=22, end_line=1, end_column=56, file_path="number.dfn"
            ),
            value_quality="value<my.domain.com:my_lib:/number>",
        )
    ]


def test_missing_potential_literal(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_result
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
    result = validate_testdata_project_with_reference_graph().program_result
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
    result = validate_testdata_project_with_reference_graph().program_result
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
    result = validate_testdata_project_with_reference_graph().program_result
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
    result = validate_testdata_project_with_reference_graph().program_result
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
    result = validate_testdata_project_with_reference_graph().program_result
    assert_no_errors(result)


def test_empty_parent(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_result
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
    result = validate_testdata_project_with_reference_graph().program_result
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
    result = validate_testdata_project_with_reference_graph().program_result
    assert_no_errors(result)


def test_callee_requires_target(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_result
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
    result = validate_testdata_project_with_reference_graph().program_result
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.ValueSettingMissingValueQualityDiagnostic)
    assert diagnostic.location.file_path == "assign.dfn"
    assert diagnostic.location.line == 7
    assert diagnostic.location.column == 26
    assert diagnostic.position_name == "position<target>"
    assert diagnostic.origin_position_name == "position<target>"


def test_boolean_literal(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_result
    assert_no_errors(result)


def test_invalid_boolean_literal_content(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_result
    assert result.all_diagnostics == [
        diagnostics.InvalidLiteralContentDiagnostic(
            location=rendering.SourceLocation(
                line=8, column=76, end_line=8, end_column=76, file_path="test.dfn"
            ),
            content="True",
            potential_literal="literal<standard:/boolean>",
            value_encoding="encoding<standard:/boolean/ascii>",
            reason="booleans are written in lowercase",
        )
    ]


def test_boolean_literal_sets_natural(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_result
    assert result.all_diagnostics == [
        diagnostics.LiteralCannotSetValueDiagnostic(
            location=rendering.SourceLocation(
                line=8, column=49, end_line=8, end_column=74, file_path="test.dfn"
            ),
            potential_literal="literal<standard:/boolean>",
            literal_encoding="encoding<standard:/boolean/ascii>",
            value_quality="value<standard:/number/natural>",
            supported_encodings=[
                "encoding<standard:/binary/ascii>",
                "encoding<standard:/number/decimal/ascii>",
                "encoding<standard:/number/hex/ascii>",
            ],
        )
    ]


def test_binary_literal(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_result
    assert_no_errors(result)


def test_invalid_binary_literal_content(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_result
    assert result.all_diagnostics == [
        diagnostics.InvalidLiteralContentDiagnostic(
            location=rendering.SourceLocation(
                line=8, column=77, end_line=8, end_column=77, file_path="test.dfn"
            ),
            content="1021",
            potential_literal="literal<standard:/binary>",
            value_encoding="encoding<standard:/binary/ascii>",
            reason="only the bits 0 and 1 are allowed",
        )
    ]


def test_binary_literal_sets_boolean(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_result
    assert result.all_diagnostics == [
        diagnostics.LiteralCannotSetValueDiagnostic(
            location=rendering.SourceLocation(
                line=8, column=49, end_line=8, end_column=73, file_path="test.dfn"
            ),
            potential_literal="literal<standard:/binary>",
            literal_encoding="encoding<standard:/binary/ascii>",
            value_quality="value<standard:/boolean>",
            supported_encodings=["encoding<standard:/boolean/ascii>"],
        )
    ]


def test_binary_literal_sets_natural(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_result
    assert_no_errors(result)


def test_decimal_literal_sets_binary(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_result
    assert_no_errors(result)


def test_negative_decimal_literal_sets_binary(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_result
    assert result.all_diagnostics == [
        diagnostics.InvalidLiteralContentDiagnostic(
            location=rendering.SourceLocation(
                line=8, column=75, end_line=8, end_column=75, file_path="test.dfn"
            ),
            content="-3",
            potential_literal="literal<standard:/number>",
            value_encoding="encoding<standard:/binary/ascii>",
            reason="negative numbers are not allowed",
        )
    ]


def test_binary_literal_sets_integer(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_result
    assert_no_errors(result)


def test_negative_decimal_literal_sets_natural(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_result
    assert result.all_diagnostics == [
        diagnostics.InvalidLiteralContentDiagnostic(
            location=rendering.SourceLocation(
                line=8, column=75, end_line=8, end_column=75, file_path="test.dfn"
            ),
            content="-3",
            potential_literal="literal<standard:/number>",
            value_encoding="encoding<standard:/number/natural/ascii>",
            reason="negative numbers are not allowed",
        )
    ]


def test_fractional_decimal_literal_sets_integer(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_result
    assert result.all_diagnostics == [
        diagnostics.InvalidLiteralContentDiagnostic(
            location=rendering.SourceLocation(
                line=8, column=76, end_line=8, end_column=76, file_path="test.dfn"
            ),
            content="2.5",
            potential_literal="literal<standard:/number>",
            value_encoding="encoding<standard:/number/integer/ascii>",
            reason="only whole numbers are allowed",
        )
    ]


def test_text_literal(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_result
    assert_no_errors(result)


def test_text_literal_with_two_scalars(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_result
    assert result.all_diagnostics == [
        diagnostics.InvalidLiteralContentDiagnostic(
            location=rendering.SourceLocation(
                line=8, column=74, end_line=8, end_column=74, file_path="test.dfn"
            ),
            content="é",
            potential_literal="literal<standard:/text>",
            value_encoding="encoding<standard:/text/unicode/scalar/utf8>",
            reason="there must be exactly one scalar",
        )
    ]


def test_code_point_literal(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_result
    assert_no_errors(result)


def test_invalid_code_point_literal_content(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_result
    assert result.all_diagnostics == [
        diagnostics.InvalidLiteralContentDiagnostic(
            location=rendering.SourceLocation(
                line=8, column=92, end_line=8, end_column=92, file_path="test.dfn"
            ),
            content="U+0301",
            potential_literal="literal<standard:/text/unicode/code_point>",
            value_encoding="encoding<standard:/text/unicode/scalar/utf8>",
            reason="'U' is not allowed in a code point",
        )
    ]


def test_hex_literal_sets_integer(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_result
    assert_no_errors(result)


def test_invalid_hex_literal_content(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_result
    assert result.all_diagnostics == [
        diagnostics.InvalidLiteralContentDiagnostic(
            location=rendering.SourceLocation(
                line=8, column=80, end_line=8, end_column=80, file_path="test.dfn"
            ),
            content="0x1F",
            potential_literal="literal<standard:/number/hex>",
            value_encoding="encoding<standard:/number/natural/ascii>",
            reason="'x' is not allowed in a hex number",
        )
    ]
