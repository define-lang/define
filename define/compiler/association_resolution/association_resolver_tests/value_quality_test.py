"""Association resolution of value qualities' encodings."""

from __future__ import annotations

from typing import TYPE_CHECKING

from define.compiler.validator.test_helpers import assert_no_errors

if TYPE_CHECKING:
    from define.compiler.test_fixtures.validation_pipeline import (
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
