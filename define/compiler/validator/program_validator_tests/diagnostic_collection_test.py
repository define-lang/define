from define.compiler.validator import program_validator


def test_multiple_diagnostics_collected():
    source = (
        "define the potential position<standard:/first>.\n"
        "define the potential position<standard:/second>.\n"
    )
    results = program_validator.ProgramValidator().validate_program_non_filesystem(
        source
    )
    diags = results[0].diagnostics
    assert len(diags) == 2
    assert diags[0].position.line == 1
    assert diags[0].position.column == 31
    assert diags[1].position.line == 2
    assert diags[1].position.column == 31


def test_diagnostics_in_source_order():
    source = (
        "define the potential position<standard:/first>.\n"
        "define the potential position<standard:/second>.\n"
    )
    results = program_validator.ProgramValidator().validate_program_non_filesystem(
        source
    )
    diags = results[0].diagnostics
    assert diags[0].position.line == 1
    assert diags[1].position.line == 2
