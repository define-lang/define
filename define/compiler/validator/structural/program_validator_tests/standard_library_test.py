"""Structural validation of programs that use the standard universe.

Follow program validator test authoring rules in program_validator_tests/AGENTS.md.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from define.compiler.validator.test_helpers import (
    assert_no_errors,
    standard_library_file,
)

if TYPE_CHECKING:
    from define.compiler.conftest import ValidateTestdataStructuralNonFilesystem


def test_referenced_definition_loads_only_its_file(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert_no_errors(result)
    assert [str(file_result.file_path) for file_result in result.file_results] == [
        "<string>",
        standard_library_file("number/rational.dfn"),
    ]
    assert sorted(name.full_typed_name for name in result.definition_results) == [
        "position<my.domain.com:my_lib:/total>",
        "value<standard:/number/rational>",
    ]


def test_standard_references_load_their_files(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert_no_errors(result)
    assert sorted(
        str(file_result.file_path) for file_result in result.file_results
    ) == sorted(
        [
            "<string>",
            standard_library_file("number.dfn"),
            standard_library_file("number/decimal/ascii.dfn"),
            standard_library_file("number/rational.dfn"),
        ]
    )
    assert sorted(name.full_typed_name for name in result.definition_results) == [
        "action<my.domain.com:my_lib:/test>",
        "encoding<standard:/number/decimal/ascii>",
        "literal<standard:/number>",
        "value<standard:/number/rational>",
    ]
