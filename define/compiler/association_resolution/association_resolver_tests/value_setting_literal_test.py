"""Association resolution of literal sources in Value Setting Statements."""

from __future__ import annotations

from typing import TYPE_CHECKING

from crates.source_rendering.python import rendering
from define.compiler import literal_parsers
from define.compiler.errors import diagnostics
from define.compiler.validator.test_helpers import assert_no_errors

if TYPE_CHECKING:
    import pytest

    from define.compiler.test_fixtures.validation_pipeline import (
        ValidateTestdataProjectWithReferenceGraph,
    )

pytest_plugins = ["define.compiler.test_fixtures.validation_pipeline"]


def test_built_in_literal(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_validation
    assert_no_errors(result)


def test_defined_literal_with_built_in_encoding(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_validation
    assert_no_errors(result)


def test_empty_literal_content(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_validation
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
    result = validate_testdata_project_with_reference_graph().program_validation
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


def test_no_literal_parser(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_validation
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
    result = validate_testdata_project_with_reference_graph().program_validation
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
    result = validate_testdata_project_with_reference_graph().program_validation
    assert result.all_diagnostics == [
        diagnostics.ValueHasNoEncodingDiagnostic(
            location=rendering.SourceLocation(
                line=1, column=22, end_line=1, end_column=56, file_path="number.dfn"
            ),
            value_quality="value<my.domain.com:my_lib:/number>",
        )
    ]


def test_boolean_literal(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_validation
    assert_no_errors(result)


def test_invalid_boolean_literal_content(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_validation
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
    result = validate_testdata_project_with_reference_graph().program_validation
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
    result = validate_testdata_project_with_reference_graph().program_validation
    assert_no_errors(result)


def test_invalid_binary_literal_content(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_validation
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
    result = validate_testdata_project_with_reference_graph().program_validation
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
    result = validate_testdata_project_with_reference_graph().program_validation
    assert_no_errors(result)


def test_decimal_literal_sets_binary(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_validation
    assert_no_errors(result)


def test_negative_decimal_literal_sets_binary(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_validation
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
    result = validate_testdata_project_with_reference_graph().program_validation
    assert_no_errors(result)


def test_negative_decimal_literal_sets_natural(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_validation
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
    result = validate_testdata_project_with_reference_graph().program_validation
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
    result = validate_testdata_project_with_reference_graph().program_validation
    assert_no_errors(result)


def test_text_literal_with_two_scalars(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_validation
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
    result = validate_testdata_project_with_reference_graph().program_validation
    assert_no_errors(result)


def test_invalid_code_point_literal_content(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_validation
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
    result = validate_testdata_project_with_reference_graph().program_validation
    assert_no_errors(result)


def test_invalid_hex_literal_content(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_validation
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
