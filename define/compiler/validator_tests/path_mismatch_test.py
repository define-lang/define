from define.compiler import diagnostics
from define.compiler.validator_tests.test_helpers import parse_transform_validate


def test_path_matches_file_no_error():
    source = "define the potential position<my.domain.com:my_lib:/foo/bar>.\n"
    diags = parse_transform_validate(source, expected_definition_path="foo/bar")
    assert len(diags) == 0


def test_path_mismatch_error():
    source = "define the potential position<my.domain.com:my_lib:/wrong/path>.\n"
    diags = parse_transform_validate(source, expected_definition_path="foo/bar")
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.PathMismatchDiagnostic)
    assert diags[0].expected_path == "/foo/bar"
    assert diags[0].actual_path == "/wrong/path"
    assert diags[0].position.line == 1
    assert diags[0].position.column == 52


def test_no_file_path_skips_validation():
    source = "define the potential position<my.domain.com:my_lib:/any/path>.\n"
    diags = parse_transform_validate(source, expected_definition_path=None)
    assert len(diags) == 0


def test_nested_path_matches():
    source = "define the potential position<my.domain.com:my_lib:/a/b/c>.\n"
    diags = parse_transform_validate(source, expected_definition_path="a/b/c")
    assert len(diags) == 0
