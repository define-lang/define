"""Association resolution of local views."""

from __future__ import annotations

from typing import TYPE_CHECKING

from crates.source_rendering.python import rendering
from define.compiler.errors import diagnostics

if TYPE_CHECKING:
    from define.compiler.conftest import (
        ValidateTestdataProjectWithReferenceGraph,
    )


def test_value_has_no_encoding(
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
