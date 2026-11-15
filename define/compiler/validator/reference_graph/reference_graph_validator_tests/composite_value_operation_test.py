"""Reference graph validation of the composite Value Operations that actions execute."""

from __future__ import annotations

from typing import TYPE_CHECKING

from crates.source_rendering.python import rendering
from define.compiler.errors import diagnostics

if TYPE_CHECKING:
    from define.compiler.conftest import (
        ValidateTestdataProjectWithReferenceGraph,
    )

_INTEGER_NATURAL_INTEGER = {
    "view<a>": "encoding<standard:/number/integer/ascii>",
    "view<b>": "encoding<standard:/number/natural/ascii>",
    "view<result>": "encoding<standard:/number/integer/ascii>",
}


def test_missing_encoding_operation(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_diagnostics == [
        diagnostics.MissingEncodingOperationDiagnostic(
            location=rendering.SourceLocation(
                line=22,
                column=21,
                end_line=22,
                end_column=41,
                file_path="test.dfn",
            ),
            logical_operation_name="logical_operation<standard:/number/add>",
            view_encodings=_INTEGER_NATURAL_INTEGER,
            execution_stack=[
                diagnostics.OperationExecutionStep(
                    executing_name="action<my.domain.com:my_lib:/test>",
                    executed_name="operation</mixed_sum>",
                    location=rendering.SourceLocation(
                        line=22,
                        column=21,
                        end_line=22,
                        end_column=41,
                        file_path="test.dfn",
                    ),
                ),
                diagnostics.OperationExecutionStep(
                    executing_name="operation</mixed_sum>",
                    executed_name="logical_operation<standard:/number/add>",
                    location=rendering.SourceLocation(
                        line=22,
                        column=21,
                        end_line=22,
                        end_column=59,
                        file_path="mixed_sum.dfn",
                    ),
                ),
            ],
        )
    ]


def test_missing_encoding_operation_in_executed_value_operation(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_diagnostics == [
        diagnostics.MissingEncodingOperationDiagnostic(
            location=rendering.SourceLocation(
                line=22,
                column=21,
                end_line=22,
                end_column=41,
                file_path="test.dfn",
            ),
            logical_operation_name="logical_operation<standard:/number/add>",
            view_encodings=_INTEGER_NATURAL_INTEGER,
            execution_stack=[
                diagnostics.OperationExecutionStep(
                    executing_name="action<my.domain.com:my_lib:/test>",
                    executed_name="operation</outer_sum>",
                    location=rendering.SourceLocation(
                        line=22,
                        column=21,
                        end_line=22,
                        end_column=41,
                        file_path="test.dfn",
                    ),
                ),
                diagnostics.OperationExecutionStep(
                    executing_name="operation</outer_sum>",
                    executed_name="operation</mixed_sum>",
                    location=rendering.SourceLocation(
                        line=22,
                        column=21,
                        end_line=22,
                        end_column=41,
                        file_path="outer_sum.dfn",
                    ),
                ),
                diagnostics.OperationExecutionStep(
                    executing_name="operation</mixed_sum>",
                    executed_name="logical_operation<standard:/number/add>",
                    location=rendering.SourceLocation(
                        line=22,
                        column=21,
                        end_line=22,
                        end_column=59,
                        file_path="mixed_sum.dfn",
                    ),
                ),
            ],
        )
    ]


def test_executed_value_operation_with_diagnostics(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_diagnostics == [
        diagnostics.LogicalOperationReadNotSupportedDiagnostic(
            location=rendering.SourceLocation(
                line=17,
                column=37,
                end_line=17,
                end_column=43,
                file_path="inner.dfn",
            ),
            looked_at_name="view<a>",
            logical_operation_name="logical_operation<standard:/number/negate>",
            value_name="value<standard:/boolean>",
        )
    ]
