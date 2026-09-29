"""Reference graph validation of the standard universe's definitions."""

from __future__ import annotations

from typing import TYPE_CHECKING

from define.compiler.validator.test_helpers import (
    assert_no_errors,
    standard_library_file,
)

if TYPE_CHECKING:
    from define.compiler.conftest import (
        ValidateTestdataNonFilesystemWithReferenceGraph,
    )


def test_every_definition_is_valid(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert_no_errors(result)
    assert sorted(
        str(file_result.file_path) for file_result in result.file_results
    ) == sorted(
        [
            "<string>",
            standard_library_file("number.dfn"),
            standard_library_file("number/decimal/ascii.dfn"),
            standard_library_file("number/decimal/ascii/infix_add.dfn"),
            standard_library_file("number/decimal/ascii/infix_increment.dfn"),
            standard_library_file("number/rational.dfn"),
            standard_library_file("number/rational/add.dfn"),
            standard_library_file("number/rational/increment.dfn"),
        ]
    )
