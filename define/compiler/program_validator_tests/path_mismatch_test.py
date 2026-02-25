from pathlib import PurePosixPath

from define.compiler import diagnostics
from define.compiler.program_validator_tests.conftest import ValidateSourceAsFile


def test_path_matches_file_no_error(validate_source_as_file: ValidateSourceAsFile):
    source = "define the potential position<my.domain.com:my_lib:/foo/bar>.\n"
    diags = validate_source_as_file(
        source,
        "my.domain.com:my_lib",
        PurePosixPath("foo/bar.def"),
    )
    assert len(diags) == 0


def test_path_mismatch_error(validate_source_as_file: ValidateSourceAsFile):
    source = "define the potential position<my.domain.com:my_lib:/wrong/path>.\n"
    diags = validate_source_as_file(
        source,
        "my.domain.com:my_lib",
        PurePosixPath("foo/bar.def"),
    )
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.PathMismatchDiagnostic)
    assert diags[0].expected_path == "/foo/bar"
    assert diags[0].actual_path == "/wrong/path"
    assert diags[0].position.line == 1
    assert diags[0].position.column == 52


def test_no_file_path_skips_validation(validate_source_as_file: ValidateSourceAsFile):
    source = "define the potential position<my.domain.com:my_lib:/any/path>.\n"
    diags = validate_source_as_file(
        source,
        "my.domain.com:my_lib",
        PurePosixPath("any/path.def"),
    )
    assert len(diags) == 0


def test_nested_path_matches(validate_source_as_file: ValidateSourceAsFile):
    source = "define the potential position<my.domain.com:my_lib:/a/b/c>.\n"
    diags = validate_source_as_file(
        source,
        "my.domain.com:my_lib",
        PurePosixPath("a/b/c.def"),
    )
    assert len(diags) == 0
