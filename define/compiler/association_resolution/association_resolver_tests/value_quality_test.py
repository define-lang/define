"""Association resolution of value qualities' encodings."""

from __future__ import annotations

from typing import TYPE_CHECKING

from crates.source_rendering.python import rendering
from define.compiler.errors import diagnostics
from define.compiler.validator.test_helpers import assert_no_errors

if TYPE_CHECKING:
    from define.compiler.test_fixtures.validation_pipeline import (
        ValidateTestdataNonFilesystemWithReferenceGraph,
        ValidateTestdataProjectWithReferenceGraph,
    )

pytest_plugins = ["define.compiler.test_fixtures.validation_pipeline"]


def test_project_value_encoding(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_validation)
    value_encodings = result.concrete_program.value_encodings
    assert {
        value_quality: encoding.full_typed_name
        for value_quality, encoding in value_encodings.items()
    } == {
        "value<my.domain.com:my_lib:/test>": "encoding<my.domain.com:my_lib:/test/digits>"
    }


def test_encoding_from_another_universe(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_validation)
    value_encodings = result.concrete_program.value_encodings
    assert {
        value_quality: encoding.full_typed_name
        for value_quality, encoding in value_encodings.items()
    } == {
        "value<my.domain.com:my_lib:/test>": "encoding<mv:define-lang.org:numbers:/number/digits>"
    }


def test_encoding_from_universe_without_multiverse(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_validation)
    value_encodings = result.concrete_program.value_encodings
    assert {
        value_quality: encoding.full_typed_name
        for value_quality, encoding in value_encodings.items()
    } == {
        "value<my.domain.com:my_lib:/test>": "encoding<define-lang.org:numbers:/number/digits>"
    }


def test_standard_encoding(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_validation)
    value_encodings = result.concrete_program.value_encodings
    assert {
        value_quality: encoding.full_typed_name
        for value_quality, encoding in value_encodings.items()
    } == {"value<my.domain.com:my_lib:/test>": "encoding<standard:/binary/ascii>"}


def test_encoding_only_in_unconfigured_universe(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_validation.sorted_diagnostics() == [
        diagnostics.ExternalUniverseNotConfiguredDiagnostic(
            location=rendering.SourceLocation(
                line=5,
                column=18,
                end_line=5,
                end_column=38,
                file_path=".define/encodings/encodings.defcl",
            ),
            universe="other.example.com:lib",
            current_universe_name="my.domain.com:my_lib",
        )
    ]


def test_value_quality_without_project_root(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.sorted_diagnostics() == [
        diagnostics.ValueHasNoEncodingDiagnostic(
            location=rendering.SourceLocation(
                line=2,
                column=22,
                end_line=2,
                end_column=54,
                file_path=None,
            ),
            value_quality="value<my.domain.com:my_lib:/test>",
        )
    ]
