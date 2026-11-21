"""Association resolution of value qualities' encodings."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

import pytest

from crates.source_rendering.python import rendering
from define.compiler.errors import (
    association_resolution_diagnostics,
    config_diagnostics,
    reference_graph_diagnostics,
    structural_diagnostics,
    syntax_errors,
)
from define.compiler.validator.reference_graph import propagation_step
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


def test_value_quality_with_two_encodings(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    with pytest.raises(
        NotImplementedError,
        match=re.escape(
            "value<my.domain.com:my_lib:/test> has more than one encoding:"
            + " ['encoding<my.domain.com:my_lib:/test/digits>',"
            + " 'encoding<my.domain.com:my_lib:/test/letters>']"
        ),
    ):
        _ = validate_testdata_project_with_reference_graph()


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
        config_diagnostics.ExternalUniverseNotConfiguredDiagnostic(
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


def test_unused_encoding_in_unconfigured_universe(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_validation)


def test_encodings_in_same_unconfigured_universe(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph(max_workers=1)
    assert result.program_validation.sorted_diagnostics() == [
        config_diagnostics.ExternalUniverseNotConfiguredDiagnostic(
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
        association_resolution_diagnostics.NoProjectRootForAssociationsDiagnostic(
            location=rendering.SourceLocation(
                line=2,
                column=22,
                end_line=2,
                end_column=54,
                file_path=None,
            ),
            value_quality="value<my.domain.com:my_lib:/test>",
            config_path=".define/project/config.defcl",
        ),
        association_resolution_diagnostics.NoProjectRootForAssociationsDiagnostic(
            location=rendering.SourceLocation(
                line=7,
                column=22,
                end_line=7,
                end_column=55,
                file_path=None,
            ),
            value_quality="value<my.domain.com:my_lib:/other>",
            config_path=".define/project/config.defcl",
        ),
    ]


def test_non_filesystem_source_uses_project_encodings(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert_no_errors(result)


def test_non_filesystem_source_defines_its_encoding(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert_no_errors(result)


def test_non_filesystem_source_uses_only_standard(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert_no_errors(result)


def test_non_filesystem_source_broken_project_config(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.sorted_diagnostics() == [
        syntax_errors.FqunContainsSpace(
            location=rendering.SourceLocation(
                line=2,
                column=22,
                end_line=2,
                end_column=22,
                file_path=".define/project/config.defcl",
            )
        )
    ]


def test_value_quality_after_reference_without_project_root(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.sorted_diagnostics() == [
        structural_diagnostics.NoProjectRootForDefinitionNotInSuppliedSourceDiagnostic(
            location=rendering.SourceLocation(
                line=3,
                column=21,
                end_line=3,
                end_column=47,
                file_path=None,
            ),
            definition_name="logical_operation</missing>",
            config_path=".define/project/config.defcl",
        )
    ]


def test_non_filesystem_source_universe_not_in_project(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.sorted_diagnostics() == [
        association_resolution_diagnostics.ValueHasNoEncodingDiagnostic(
            location=rendering.SourceLocation(
                line=2,
                column=22,
                end_line=2,
                end_column=55,
                file_path=None,
            ),
            value_quality="value<other.example.com:lib:/test>",
        )
    ]


def test_local_positions_value_never_set_has_no_encoding(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.sorted_diagnostics() == [
        association_resolution_diagnostics.ValueHasNoEncodingDiagnostic(
            location=rendering.SourceLocation(
                line=2, column=22, end_line=2, end_column=54, file_path=None
            ),
            value_quality="value<my.domain.com:my_lib:/flag>",
        ),
        reference_graph_diagnostics.UnsetValueDiagnostic(
            location=rendering.SourceLocation(
                line=24, column=46, end_line=24, end_column=60, file_path=None
            ),
            position_name="position<value>",
        ),
    ]


def test_interface_positions_value_never_set_has_no_encoding(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.sorted_diagnostics() == [
        association_resolution_diagnostics.ValueHasNoEncodingDiagnostic(
            location=rendering.SourceLocation(
                line=2, column=22, end_line=2, end_column=54, file_path=None
            ),
            value_quality="value<my.domain.com:my_lib:/flag>",
        ),
        reference_graph_diagnostics.InferredRequirementViolationDiagnostic(
            location=rendering.SourceLocation(
                line=40, column=30, end_line=40, end_column=78, file_path=None
            ),
            position_name="position<copying>::action</copier>::position<value>",
            propagation_chain=[
                propagation_step.PropagationStep(
                    location=rendering.SourceLocation(
                        line=38, column=30, end_line=38, end_column=80, file_path=None
                    ),
                    kind=propagation_step.PropagationKind.FILL_SITE,
                    enclosing_quality_name="position<copying>::action</copier>::position<value>",
                    triggered_quality_name=None,
                ),
                propagation_step.PropagationStep(
                    location=rendering.SourceLocation(
                        line=40, column=30, end_line=40, end_column=78, file_path=None
                    ),
                    kind=propagation_step.PropagationKind.ACTION_TRIGGER,
                    enclosing_quality_name="action<my.domain.com:my_lib:/test>",
                    triggered_quality_name="action<my.domain.com:my_lib:/copier>",
                ),
                propagation_step.PropagationStep(
                    location=rendering.SourceLocation(
                        line=23, column=46, end_line=23, end_column=60, file_path=None
                    ),
                    kind=propagation_step.PropagationKind.DIRECT_INFERENCE,
                    enclosing_quality_name="action<my.domain.com:my_lib:/copier>",
                    triggered_quality_name=None,
                ),
            ],
            required_empty=False,
            action_name="action<my.domain.com:my_lib:/copier>",
            required_value=True,
        ),
    ]
