from define.compiler import diagnostics
from define.compiler.program_validator_tests.conftest import ValidateSourceAsFile


def test_matching_authority_universe(validate_source_as_file: ValidateSourceAsFile):
    source = "define the potential position<my.domain.com:my_lib:/path>.\n"
    diags = validate_source_as_file(
        source,
        "my.domain.com:my_lib",
    )
    assert len(diags) == 0


def test_mismatched_universe(validate_source_as_file: ValidateSourceAsFile):
    source = "define the potential position<my.domain.com:wrong_lib:/path>.\n"
    diags = validate_source_as_file(
        source,
        "my.domain.com:my_lib",
    )
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.FqunMismatchDiagnostic)
    assert diags[0].expected == "my.domain.com:my_lib"
    assert diags[0].actual == "my.domain.com:wrong_lib"
    assert diags[0].position.line == 1
    assert diags[0].position.column == 31


def test_mismatched_authority(validate_source_as_file: ValidateSourceAsFile):
    source = "define the potential position<other.org:my_lib:/path>.\n"
    diags = validate_source_as_file(
        source,
        "my.domain.com:my_lib",
    )
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.FqunMismatchDiagnostic)
    assert diags[0].expected == "my.domain.com:my_lib"
    assert diags[0].actual == "other.org:my_lib"
    assert diags[0].position.line == 1
    assert diags[0].position.column == 31


def test_mismatched_multiverse(validate_source_as_file: ValidateSourceAsFile):
    source = "define the potential position<npm:my.domain.com:my_lib:/path>.\n"
    diags = validate_source_as_file(
        source,
        "mv:my.domain.com:my_lib",
    )
    npm_diags = [d for d in diags if isinstance(d, diagnostics.FqunMismatchDiagnostic)]
    assert len(npm_diags) == 1
    assert npm_diags[0].expected == "mv:my.domain.com:my_lib"
    assert npm_diags[0].actual == "npm:my.domain.com:my_lib"
    assert npm_diags[0].position.line == 1
    assert npm_diags[0].position.column == 31


def test_none_skips_check(validate_source_as_file: ValidateSourceAsFile):
    source = "define the potential position<my.domain.com:my_lib:/path>.\n"
    diags = validate_source_as_file(
        source,
        "my.domain.com:my_lib",
    )
    assert len(diags) == 0


def test_standard_universe_matching(validate_source_as_file: ValidateSourceAsFile):
    source = "define the potential position<standard:/path>.\n"
    diags = validate_source_as_file(
        source,
        "standard",
    )
    fqun_diags = [d for d in diags if isinstance(d, diagnostics.FqunMismatchDiagnostic)]
    assert len(fqun_diags) == 0


def test_authority_with_path(validate_source_as_file: ValidateSourceAsFile):
    source = "define the potential position<my.domain.com/org:my_lib:/path>.\n"
    diags = validate_source_as_file(
        source,
        "my.domain.com/org:my_lib",
    )
    assert len(diags) == 0


def test_authority_with_path_mismatch(
    validate_source_as_file: ValidateSourceAsFile,
):
    source = "define the potential position<my.domain.com/org:my_lib:/path>.\n"
    diags = validate_source_as_file(
        source,
        "my.domain.com:my_lib",
    )
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.FqunMismatchDiagnostic)
    assert diags[0].expected == "my.domain.com:my_lib"
    assert diags[0].actual == "my.domain.com/org:my_lib"
    assert diags[0].position.line == 1
    assert diags[0].position.column == 31


def test_multiverse_matching(validate_source_as_file: ValidateSourceAsFile):
    source = "define the potential position<mv:my.domain.com:my_lib:/path>.\n"
    diags = validate_source_as_file(
        source,
        "mv:my.domain.com:my_lib",
    )
    assert len(diags) == 0
