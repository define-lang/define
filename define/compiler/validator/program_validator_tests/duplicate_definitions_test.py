"""Duplicate definition validation tests.

Follow program validator test authoring rules in program_validator_tests/AGENTS.md.
"""

from define.compiler import diagnostics
from define.compiler.validator.structural import program_validator


def test_no_duplicates_ok():
    source = (
        "define the potential position<my.domain.com:my_lib:/first>.\n"
        "define the potential position<my.domain.com:my_lib:/second>.\n"
    )
    results = (
        program_validator.ProgramStructuralValidator()
        .validate_program_non_filesystem(source)
        .file_results
    )
    diags = results[0].diagnostics
    assert len(diags) == 0


def test_duplicate_position_error():
    source = (
        "define the potential position<my.domain.com:my_lib:/same>.\n"
        "define the potential position<my.domain.com:my_lib:/same>.\n"
    )
    results = (
        program_validator.ProgramStructuralValidator()
        .validate_program_non_filesystem(source)
        .file_results
    )
    diags = results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.DuplicateDefinitionDiagnostic)
    assert diags[0].definition_type == "position"
    assert diags[0].path == "/same"
    assert diags[0].first_definition_line == 1
    assert diags[0].position.line == 2
    assert diags[0].position.column == 1


def test_duplicate_action_error():
    source = (
        "define the potential action<my.domain.com:my_lib:/same>.\n"
        "define the potential action<my.domain.com:my_lib:/same>.\n"
    )
    results = (
        program_validator.ProgramStructuralValidator()
        .validate_program_non_filesystem(source)
        .file_results
    )
    diags = results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.DuplicateDefinitionDiagnostic)
    assert diags[0].definition_type == "action"
    assert diags[0].path == "/same"
    assert diags[0].first_definition_line == 1
    assert diags[0].position.line == 2
    assert diags[0].position.column == 1


def test_same_path_different_types_ok():
    source = (
        "define the potential position<my.domain.com:my_lib:/same>.\n"
        "define the potential action<my.domain.com:my_lib:/same>.\n"
    )
    results = (
        program_validator.ProgramStructuralValidator()
        .validate_program_non_filesystem(source)
        .file_results
    )
    diags = results[0].diagnostics
    assert len(diags) == 0


def test_three_duplicates_two_errors():
    source = (
        "define the potential position<my.domain.com:my_lib:/same>.\n"
        "define the potential position<my.domain.com:my_lib:/same>.\n"
        "define the potential position<my.domain.com:my_lib:/same>.\n"
    )
    results = (
        program_validator.ProgramStructuralValidator()
        .validate_program_non_filesystem(source)
        .file_results
    )
    diags = results[0].diagnostics
    assert len(diags) == 2
    assert isinstance(diags[0], diagnostics.DuplicateDefinitionDiagnostic)
    assert isinstance(diags[1], diagnostics.DuplicateDefinitionDiagnostic)
    assert diags[0].definition_type == "position"
    assert diags[0].path == "/same"
    assert diags[0].first_definition_line == 1
    assert diags[0].position.line == 2
    assert diags[0].position.column == 1
    assert diags[1].definition_type == "position"
    assert diags[1].path == "/same"
    assert diags[1].first_definition_line == 1
    assert diags[1].position.line == 3
    assert diags[1].position.column == 1
