"""Reference graph validation of Matching View Requirements for Operation Argument Statements."""

from __future__ import annotations

from typing import TYPE_CHECKING

from crates.source_rendering.python import rendering
from define.compiler.errors import diagnostics

if TYPE_CHECKING:
    from define.compiler.conftest import (
        ValidateTestdataNonFilesystemWithReferenceGraph,
        ValidateTestdataProjectWithReferenceGraph,
    )


def test_invalid_literal_content(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.all_diagnostics == [
        diagnostics.InvalidLiteralContentDiagnostic(
            location=rendering.SourceLocation(
                line=34, column=68, end_line=34, end_column=68, file_path=None
            ),
            content="abc",
            potential_literal="literal<standard:/number>",
            value_encoding="encoding<standard:/number/natural/ascii>",
            reason="'a' is not allowed in a number",
        )
    ]


def test_literal_value_has_no_encoding(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_result
    assert result.all_diagnostics == [
        diagnostics.ValueHasNoEncodingDiagnostic(
            location=rendering.SourceLocation(
                line=1, column=22, end_line=1, end_column=55, file_path="count.dfn"
            ),
            value_quality="value<my.domain.com:my_lib:/count>",
        )
    ]


def test_interface_view_value_has_no_encoding(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_result
    assert result.all_diagnostics == [
        diagnostics.ValueHasNoEncodingDiagnostic(
            location=rendering.SourceLocation(
                line=1, column=22, end_line=1, end_column=59, file_path="unencoded.dfn"
            ),
            value_quality="value<my.domain.com:my_lib:/unencoded>",
        )
    ]


def test_invalid_literal_content_in_action(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.all_diagnostics == [
        diagnostics.InvalidLiteralContentDiagnostic(
            location=rendering.SourceLocation(
                line=36, column=68, end_line=36, end_column=68, file_path=None
            ),
            content="x",
            potential_literal="literal<standard:/number>",
            value_encoding="encoding<standard:/number/natural/ascii>",
            reason="'x' is not allowed in a number",
        )
    ]
