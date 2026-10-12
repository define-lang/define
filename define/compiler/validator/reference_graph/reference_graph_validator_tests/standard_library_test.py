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
            standard_library_file("binary.dfn"),
            standard_library_file("binary/and.dfn"),
            standard_library_file("binary/ascii.dfn"),
            standard_library_file("binary/ascii/and.dfn"),
            standard_library_file("binary/ascii/equal.dfn"),
            standard_library_file("binary/ascii/exclusive_or.dfn"),
            standard_library_file("binary/ascii/or.dfn"),
            standard_library_file("binary/equal.dfn"),
            standard_library_file("binary/exclusive_or.dfn"),
            standard_library_file("binary/or.dfn"),
            standard_library_file("boolean.dfn"),
            standard_library_file("boolean/and.dfn"),
            standard_library_file("boolean/ascii.dfn"),
            standard_library_file("boolean/ascii/and.dfn"),
            standard_library_file("boolean/ascii/exclusive_or.dfn"),
            standard_library_file("boolean/ascii/not.dfn"),
            standard_library_file("boolean/ascii/or.dfn"),
            standard_library_file("boolean/exclusive_or.dfn"),
            standard_library_file("boolean/not.dfn"),
            standard_library_file("boolean/or.dfn"),
            standard_library_file("number.dfn"),
            standard_library_file("number/decimal/ascii.dfn"),
            standard_library_file("number/integer.dfn"),
            standard_library_file("number/integer/absolute_value.dfn"),
            standard_library_file("number/integer/add.dfn"),
            standard_library_file("number/integer/ascii.dfn"),
            standard_library_file("number/integer/ascii/absolute_value.dfn"),
            standard_library_file("number/integer/ascii/add.dfn"),
            standard_library_file("number/integer/ascii/decrement.dfn"),
            standard_library_file("number/integer/ascii/equal.dfn"),
            standard_library_file("number/integer/ascii/increment.dfn"),
            standard_library_file("number/integer/ascii/less_than.dfn"),
            standard_library_file("number/integer/ascii/less_than_or_equal.dfn"),
            standard_library_file("number/integer/ascii/maximum.dfn"),
            standard_library_file("number/integer/ascii/minimum.dfn"),
            standard_library_file("number/integer/ascii/multiply.dfn"),
            standard_library_file("number/integer/ascii/negate.dfn"),
            standard_library_file("number/integer/ascii/subtract.dfn"),
            standard_library_file("number/integer/decrement.dfn"),
            standard_library_file("number/integer/equal.dfn"),
            standard_library_file("number/integer/increment.dfn"),
            standard_library_file("number/integer/less_than.dfn"),
            standard_library_file("number/integer/less_than_or_equal.dfn"),
            standard_library_file("number/integer/maximum.dfn"),
            standard_library_file("number/integer/minimum.dfn"),
            standard_library_file("number/integer/multiply.dfn"),
            standard_library_file("number/integer/negate.dfn"),
            standard_library_file("number/integer/subtract.dfn"),
            standard_library_file("number/natural.dfn"),
            standard_library_file("number/natural/add.dfn"),
            standard_library_file("number/natural/ascii.dfn"),
            standard_library_file("number/natural/ascii/add.dfn"),
            standard_library_file("number/natural/ascii/decrement_saturating.dfn"),
            standard_library_file("number/natural/ascii/equal.dfn"),
            standard_library_file("number/natural/ascii/increment.dfn"),
            standard_library_file("number/natural/ascii/less_than.dfn"),
            standard_library_file("number/natural/ascii/less_than_or_equal.dfn"),
            standard_library_file("number/natural/ascii/maximum.dfn"),
            standard_library_file("number/natural/ascii/minimum.dfn"),
            standard_library_file("number/natural/ascii/multiply.dfn"),
            standard_library_file("number/natural/ascii/subtract.dfn"),
            standard_library_file("number/natural/ascii/subtract_saturating.dfn"),
            standard_library_file("number/natural/decrement_saturating.dfn"),
            standard_library_file("number/natural/equal.dfn"),
            standard_library_file("number/natural/increment.dfn"),
            standard_library_file("number/natural/less_than.dfn"),
            standard_library_file("number/natural/less_than_or_equal.dfn"),
            standard_library_file("number/natural/maximum.dfn"),
            standard_library_file("number/natural/minimum.dfn"),
            standard_library_file("number/natural/multiply.dfn"),
            standard_library_file("number/natural/subtract.dfn"),
            standard_library_file("number/natural/subtract_saturating.dfn"),
            standard_library_file("text.dfn"),
            standard_library_file("text/unicode/scalar.dfn"),
            standard_library_file("text/unicode/utf8.dfn"),
        ]
    )
