"""Diagnostic collection tests.

Follow program validator test authoring rules in program_validator_tests/AGENTS.md.
"""

from define.compiler import diagnostics
from define.compiler.validator import program_validator


def test_multiple_diagnostics_collected():
    source = (
        "define the potential position<standard:/first>.\n"
        "define the potential position<standard:/second>.\n"
    )
    results = (
        program_validator.ProgramValidator()
        .validate_program_non_filesystem(source)
        .file_results
    )
    diags = results[0].diagnostics
    assert len(diags) == 2
    assert isinstance(diags[0], diagnostics.ReservedUniverseNameDiagnostic)
    assert diags[0].position.line == 1
    assert diags[0].position.column == 31
    assert diags[0].reserved_name == "standard"
    assert isinstance(diags[1], diagnostics.ReservedUniverseNameDiagnostic)
    assert diags[1].position.line == 2
    assert diags[1].position.column == 31
    assert diags[1].reserved_name == "standard"


def test_diagnostics_in_source_order():
    source = (
        "define the potential position<standard:/first>.\n"
        "define the potential position<standard:/second>.\n"
    )
    results = (
        program_validator.ProgramValidator()
        .validate_program_non_filesystem(source)
        .file_results
    )
    diags = results[0].diagnostics
    assert isinstance(diags[0], diagnostics.ReservedUniverseNameDiagnostic)
    assert diags[0].position.line == 1
    assert diags[0].position.column == 31
    assert diags[0].reserved_name == "standard"
    assert isinstance(diags[1], diagnostics.ReservedUniverseNameDiagnostic)
    assert diags[1].position.line == 2
    assert diags[1].position.column == 31
    assert diags[1].reserved_name == "standard"
