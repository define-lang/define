"""FQUN mismatch validation tests.

Follow program validator test authoring rules in program_validator_tests/AGENTS.md.
"""

from define.compiler import diagnostics
from define.compiler.validator.program_validator_tests.conftest import (
    ValidateSourceAsFile,
)


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
    source = "define the potential position<other_mv:my.domain.com:my_lib:/path>.\n"
    diags = validate_source_as_file(
        source,
        "mv:my.domain.com:my_lib",
    )
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.FqunMismatchDiagnostic)
    assert diags[0].expected == "mv:my.domain.com:my_lib"
    assert diags[0].actual == "other_mv:my.domain.com:my_lib"
    assert diags[0].position.line == 1
    assert diags[0].position.column == 31
    assert diags[0].position.end_line == 1
    assert diags[0].position.end_column == 60


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
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.ReservedUniverseNameDiagnostic)
    assert diags[0].reserved_name == "standard"
    assert diags[0].position.line == 1
    assert diags[0].position.column == 31
    assert diags[0].position.end_line == 1
    assert diags[0].position.end_column == 39


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
