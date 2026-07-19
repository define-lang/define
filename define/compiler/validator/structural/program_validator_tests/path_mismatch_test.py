"""Path mismatch validation tests.

Follow program validator test authoring rules in program_validator_tests/AGENTS.md.
"""

from pathlib import PurePosixPath

from define.compiler import diagnostics
from define.compiler.conftest import (
    ValidateSourceAsFile,
    ValidateTestdataStructural,
)


def test_path_matches_file_no_error(validate_source_as_file: ValidateSourceAsFile):
    source = "define the potential position<my.domain.com:my_lib:/foo/bar>.\n"
    diags = validate_source_as_file(
        source,
        "my.domain.com:my_lib",
        PurePosixPath("foo/bar.dfn"),
    )
    assert len(diags) == 0


def test_path_mismatch_error(
    validate_testdata_structural: ValidateTestdataStructural,
):
    result = validate_testdata_structural(entry_file="foo/bar.dfn")
    assert result.all_exceptions == []
    diags = result.file_results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.PathMismatchDiagnostic)
    assert diags[0].expected_path == "/foo/bar"
    assert diags[0].actual_path == "/wrong/path"
    assert diags[0].location.line == 1
    assert diags[0].location.column == 52
    assert diags[0].location.end_line == 1
    assert diags[0].location.end_column == 63
    assert diags[0].location.file_path == PurePosixPath("foo/bar.dfn")


def test_no_file_path_skips_validation(validate_source_as_file: ValidateSourceAsFile):
    source = "define the potential position<my.domain.com:my_lib:/any/path>.\n"
    diags = validate_source_as_file(
        source,
        "my.domain.com:my_lib",
        PurePosixPath("any/path.dfn"),
    )
    assert len(diags) == 0


def test_nested_path_matches(validate_source_as_file: ValidateSourceAsFile):
    source = "define the potential position<my.domain.com:my_lib:/a/b/c>.\n"
    diags = validate_source_as_file(
        source,
        "my.domain.com:my_lib",
        PurePosixPath("a/b/c.dfn"),
    )
    assert len(diags) == 0
