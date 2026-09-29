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
            standard_library_file("number/decimal/ascii/absolute_value.dfn"),
            standard_library_file("number/decimal/ascii/ceiling.dfn"),
            standard_library_file("number/decimal/ascii/floor.dfn"),
            standard_library_file("number/decimal/ascii/infix_add.dfn"),
            standard_library_file("number/decimal/ascii/infix_decrement.dfn"),
            standard_library_file("number/decimal/ascii/infix_increment.dfn"),
            standard_library_file("number/decimal/ascii/infix_multiply.dfn"),
            standard_library_file("number/decimal/ascii/infix_subtract.dfn"),
            standard_library_file("number/decimal/ascii/maximum.dfn"),
            standard_library_file("number/decimal/ascii/minimum.dfn"),
            standard_library_file("number/decimal/ascii/prefix_negate.dfn"),
            standard_library_file("number/decimal/ascii/truncate.dfn"),
            standard_library_file("number/rational.dfn"),
            standard_library_file("number/rational/absolute_value.dfn"),
            standard_library_file("number/rational/add.dfn"),
            standard_library_file("number/rational/ceiling.dfn"),
            standard_library_file("number/rational/decrement.dfn"),
            standard_library_file("number/rational/floor.dfn"),
            standard_library_file("number/rational/increment.dfn"),
            standard_library_file("number/rational/maximum.dfn"),
            standard_library_file("number/rational/minimum.dfn"),
            standard_library_file("number/rational/multiply.dfn"),
            standard_library_file("number/rational/negate.dfn"),
            standard_library_file("number/rational/subtract.dfn"),
            standard_library_file("number/rational/truncate.dfn"),
        ]
    )
