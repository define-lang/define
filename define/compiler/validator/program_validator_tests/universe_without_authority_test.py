from define.compiler import diagnostics
from define.compiler.validator import program_validator


def test_standard_without_authority_ok():
    source = "define the potential position<standard:/path>.\n"
    results = program_validator.ProgramValidator().validate_program_non_filesystem(
        source
    )
    diags = results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.ReservedUniverseNameDiagnostic)
    assert diags[0].reserved_name == "standard"
    assert diags[0].position.line == 1
    assert diags[0].position.column == 31


def test_non_standard_without_authority_error():
    source = "define the potential position<my_universe:/path>.\n"
    results = program_validator.ProgramValidator().validate_program_non_filesystem(
        source
    )
    diags = results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.UniverseWithoutAuthorityDiagnostic)
    assert diags[0].universe_name == "my_universe"
    assert diags[0].position.line == 1
    assert diags[0].position.column == 31


def test_with_authority_ok():
    source = "define the potential position<my.domain.com:my_universe:/path>.\n"
    results = program_validator.ProgramValidator().validate_program_non_filesystem(
        source
    )
    diags = results[0].diagnostics
    assert len(diags) == 0


def test_case_insensitive_standard():
    source = "define the potential position<STANDARD:/path>.\n"
    results = program_validator.ProgramValidator().validate_program_non_filesystem(
        source
    )
    diags = results[0].diagnostics
    assert len(diags) == 2
    assert isinstance(diags[0], diagnostics.UniverseNameInvalidCharDiagnostic)
    assert diags[0].universe_name == "STANDARD"
    assert diags[0].char == "S"
    assert diags[0].position.line == 1
    assert diags[0].position.column == 31
    assert isinstance(diags[1], diagnostics.ReservedUniverseNameDiagnostic)
    assert diags[1].reserved_name == "STANDARD"
    assert diags[1].position.line == 1
    assert diags[1].position.column == 31
