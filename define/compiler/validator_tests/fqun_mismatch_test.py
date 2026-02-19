from define.compiler import diagnostics
from define.compiler.validator_tests.test_helpers import parse_transform_validate


def test_matching_authority_universe():
    source = "define the potential position<my.domain.com:my_lib:/path>.\n"
    diags = parse_transform_validate(
        source, expected_universe_name="my.domain.com:my_lib"
    )
    assert len(diags) == 0


def test_mismatched_universe():
    source = "define the potential position<my.domain.com:wrong_lib:/path>.\n"
    diags = parse_transform_validate(
        source, expected_universe_name="my.domain.com:my_lib"
    )
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.FqunMismatchDiagnostic)
    assert diags[0].expected == "my.domain.com:my_lib"
    assert diags[0].actual == "my.domain.com:wrong_lib"
    assert diags[0].position.column == 31


def test_mismatched_authority():
    source = "define the potential position<other.org:my_lib:/path>.\n"
    diags = parse_transform_validate(
        source, expected_universe_name="my.domain.com:my_lib"
    )
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.FqunMismatchDiagnostic)
    assert diags[0].expected == "my.domain.com:my_lib"
    assert diags[0].actual == "other.org:my_lib"


def test_mismatched_multiverse():
    source = "define the potential position<npm:my.domain.com:my_lib:/path>.\n"
    diags = parse_transform_validate(
        source, expected_universe_name="mv:my.domain.com:my_lib"
    )
    npm_diags = [d for d in diags if isinstance(d, diagnostics.FqunMismatchDiagnostic)]
    assert len(npm_diags) == 1
    assert npm_diags[0].expected == "mv:my.domain.com:my_lib"
    assert npm_diags[0].actual == "npm:my.domain.com:my_lib"


def test_none_skips_check():
    source = "define the potential position<my.domain.com:my_lib:/path>.\n"
    diags = parse_transform_validate(source, expected_universe_name=None)
    assert len(diags) == 0


def test_standard_universe_matching():
    source = "define the potential position<standard:/path>.\n"
    diags = parse_transform_validate(source, expected_universe_name="standard")
    fqun_diags = [d for d in diags if isinstance(d, diagnostics.FqunMismatchDiagnostic)]
    assert len(fqun_diags) == 0


def test_authority_with_path():
    source = "define the potential position<my.domain.com/org:my_lib:/path>.\n"
    diags = parse_transform_validate(
        source, expected_universe_name="my.domain.com/org:my_lib"
    )
    assert len(diags) == 0


def test_authority_with_path_mismatch():
    source = "define the potential position<my.domain.com/org:my_lib:/path>.\n"
    diags = parse_transform_validate(
        source, expected_universe_name="my.domain.com:my_lib"
    )
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.FqunMismatchDiagnostic)
    assert diags[0].actual == "my.domain.com/org:my_lib"


def test_multiverse_matching():
    source = "define the potential position<mv:my.domain.com:my_lib:/path>.\n"
    diags = parse_transform_validate(
        source, expected_universe_name="mv:my.domain.com:my_lib"
    )
    assert len(diags) == 0
