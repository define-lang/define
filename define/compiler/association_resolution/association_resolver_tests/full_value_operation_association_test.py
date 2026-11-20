"""Association resolution of executions of Value Operations that have Full Value Operation Associations."""

from __future__ import annotations

from typing import TYPE_CHECKING

from crates.source_rendering.python import rendering
from define.compiler import ast
from define.compiler.association_resolution import concrete_program
from define.compiler.errors import (
    association_resolution_diagnostics,
    config_diagnostics,
)

if TYPE_CHECKING:
    from define.compiler.test_fixtures.validation_pipeline import (
        ValidateTestdataProjectWithReferenceGraph,
    )

pytest_plugins = ["define.compiler.test_fixtures.validation_pipeline"]

_CONFIG_PATH = ".define/encodings/encoding_operations.defcl"


def _flip_runtime_operation(program: concrete_program.ConcreteProgram) -> str:
    """Return the full typed name of the Encoding Operation that the test action's execution of /flip runs."""
    steps = program.actions["action<my.domain.com:my_lib:/test>"].steps
    executions = [
        step
        for step in steps
        if isinstance(step, concrete_program.ActionOperationExecution)
    ]
    (execution,) = executions
    runtime_operation = execution.runtime_operation
    assert isinstance(runtime_operation, ast.GlobalTypedName)
    return runtime_operation.full_typed_name


def test_runs_associated_encoding_operation(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_validation.sorted_diagnostics() == []
    program = result.concrete_program
    assert (
        _flip_runtime_operation(program)
        == "encoding_operation<my.domain.com:my_lib:/flip/ascii>"
    )
    assert sorted(program.encoding_operations) == [
        "encoding_operation<my.domain.com:my_lib:/flip/ascii>",
        "encoding_operation<standard:/number/integer/ascii/negate>",
    ]
    assert program.composite_value_operations == {}


def test_unmatched_encodings_compile_statement_by_statement(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_validation.sorted_diagnostics() == []
    program = result.concrete_program
    assert (
        _flip_runtime_operation(program)
        == "encoding_operation<standard:/number/integer/ascii/negate>"
    )
    assert sorted(program.encoding_operations) == [
        "encoding_operation<standard:/number/integer/ascii/negate>",
    ]


def test_association_with_different_view_name(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_validation.sorted_diagnostics() == [
        association_resolution_diagnostics.AssociationAbstractOperationViewNameDiagnostic(
            location=rendering.SourceLocation(
                line=13,
                column=19,
                end_line=13,
                end_column=26,
                file_path=_CONFIG_PATH,
            ),
            view_number=2,
            view_name="output",
            encoding_operation_name="encoding_operation</flip/ascii>",
            abstract_operation_name="operation<my.domain.com:my_lib:/flip>",
            abstract_operation_view_name="result",
            definition_location=rendering.SourceLocation(
                line=8, column=16, end_line=8, end_column=27, file_path="flip.dfn"
            ),
        )
    ]


def test_association_with_views_in_different_order(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_validation.sorted_diagnostics() == [
        association_resolution_diagnostics.AssociationAbstractOperationViewNameDiagnostic(
            location=rendering.SourceLocation(
                line=9,
                column=19,
                end_line=9,
                end_column=26,
                file_path=_CONFIG_PATH,
            ),
            view_number=1,
            view_name="result",
            encoding_operation_name="encoding_operation</flip/ascii>",
            abstract_operation_name="operation<my.domain.com:my_lib:/flip>",
            abstract_operation_view_name="a",
            definition_location=rendering.SourceLocation(
                line=2, column=16, end_line=2, end_column=22, file_path="flip.dfn"
            ),
        ),
        association_resolution_diagnostics.AssociationAbstractOperationViewNameDiagnostic(
            location=rendering.SourceLocation(
                line=13,
                column=19,
                end_line=13,
                end_column=21,
                file_path=_CONFIG_PATH,
            ),
            view_number=2,
            view_name="a",
            encoding_operation_name="encoding_operation</flip/ascii>",
            abstract_operation_name="operation<my.domain.com:my_lib:/flip>",
            abstract_operation_view_name="result",
            definition_location=rendering.SourceLocation(
                line=8, column=16, end_line=8, end_column=27, file_path="flip.dfn"
            ),
        ),
    ]


def test_association_with_fewer_views(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_validation.sorted_diagnostics() == [
        association_resolution_diagnostics.AssociationAbstractOperationViewCountDiagnostic(
            location=rendering.SourceLocation(
                line=6,
                column=16,
                end_line=6,
                end_column=26,
                file_path=_CONFIG_PATH,
            ),
            encoding_operation_name="encoding_operation</flip/ascii>",
            view_count=1,
            abstract_operation_name="operation<my.domain.com:my_lib:/flip>",
            abstract_operation_view_count=2,
            definition_location=rendering.SourceLocation(
                line=1, column=12, end_line=1, end_column=48, file_path="flip.dfn"
            ),
        )
    ]


def test_encoding_operation_with_different_view_direction(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    association_location = rendering.SourceLocation(
        line=6, column=16, end_line=6, end_column=26, file_path=_CONFIG_PATH
    )
    assert result.program_validation.sorted_diagnostics() == [
        association_resolution_diagnostics.AssociatedEncodingOperationViewDirectionDiagnostic(
            location=rendering.SourceLocation(
                line=2,
                column=16,
                end_line=2,
                end_column=22,
                file_path="flip/ascii.dfn",
            ),
            view_name="view<a>",
            direction="written",
            encoding_operation_name="encoding_operation<my.domain.com:my_lib:/flip/ascii>",
            abstract_operation_direction="read",
            abstract_operation_name="operation<my.domain.com:my_lib:/flip>",
            association_location=association_location,
        ),
        association_resolution_diagnostics.AssociatedEncodingOperationViewDirectionDiagnostic(
            location=rendering.SourceLocation(
                line=8,
                column=16,
                end_line=8,
                end_column=27,
                file_path="flip/ascii.dfn",
            ),
            view_name="view<result>",
            direction="read",
            encoding_operation_name="encoding_operation<my.domain.com:my_lib:/flip/ascii>",
            abstract_operation_direction="written",
            abstract_operation_name="operation<my.domain.com:my_lib:/flip>",
            association_location=association_location,
        ),
    ]


def test_encoding_operation_with_different_encoding(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_validation.sorted_diagnostics() == [
        association_resolution_diagnostics.AssociationViewEncodingDiagnostic(
            location=rendering.SourceLocation(
                line=10,
                column=24,
                end_line=10,
                end_column=53,
                file_path=_CONFIG_PATH,
            ),
            view_name="view<a>",
            encoding_name="encoding<standard:/number/integer/ascii>",
            encoding_operation_name="encoding_operation<my.domain.com:my_lib:/flip/ascii>",
            encoding_operation_encoding_name="encoding<standard:/number/natural/ascii>",
            definition_location=rendering.SourceLocation(
                line=5,
                column=24,
                end_line=5,
                end_column=63,
                file_path="flip/ascii.dfn",
            ),
        )
    ]


def test_associations_with_same_encodings(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_validation.sorted_diagnostics() == [
        config_diagnostics.DuplicateAssociationEncodingsDiagnostic(
            location=rendering.SourceLocation(
                line=22,
                column=16,
                end_line=22,
                end_column=26,
                file_path=_CONFIG_PATH,
            ),
            abstract_operation="operation</flip>",
            encoding_operation="/flip/other",
            first_encoding_operation="/flip/ascii",
            first_location=rendering.SourceLocation(
                line=6, column=16, end_line=6, end_column=26, file_path=_CONFIG_PATH
            ),
        ),
    ]


def test_same_association_with_different_encodings(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_validation.sorted_diagnostics() == [
        association_resolution_diagnostics.AssociationViewEncodingDiagnostic(
            location=rendering.SourceLocation(
                line=10,
                column=24,
                end_line=10,
                end_column=53,
                file_path=_CONFIG_PATH,
            ),
            view_name="view<a>",
            encoding_name="encoding<standard:/number/integer/ascii>",
            encoding_operation_name="encoding_operation<my.domain.com:my_lib:/flip/ascii>",
            encoding_operation_encoding_name="encoding<standard:/number/natural/ascii>",
            definition_location=rendering.SourceLocation(
                line=5,
                column=24,
                end_line=5,
                end_column=63,
                file_path="flip/ascii.dfn",
            ),
        ),
        config_diagnostics.DuplicateEncodingOperationDiagnostic(
            location=rendering.SourceLocation(
                line=19, column=5, end_line=34, end_column=5, file_path=_CONFIG_PATH
            ),
            abstract_operation="operation</flip>",
            encoding_operation="/flip/ascii",
            first_location=rendering.SourceLocation(
                line=3, column=5, end_line=18, end_column=5, file_path=_CONFIG_PATH
            ),
        ),
    ]
